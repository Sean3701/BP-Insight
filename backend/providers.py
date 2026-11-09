"""Provider configuration, encrypted secrets and bounded HTTP transport."""
import json
import os
import threading
import urllib.request
import urllib.error
from urllib.parse import urlparse
from cryptography.fernet import Fernet
from backend.database import DATA_ROOT

_key_lock = threading.Lock()


class ProviderError(Exception):
    pass


def cipher():
    path = DATA_ROOT / 'secrets' / 'master.key'
    with _key_lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            with path.open('xb') as f:
                f.write(Fernet.generate_key())
            os.chmod(path, 0o600)
        return Fernet(path.read_bytes())


def encrypt(key):
    return cipher().encrypt(key.encode()).decode() if key else ''


def decrypt(secret):
    try:
        return cipher().decrypt(secret.encode()).decode()
    except Exception:
        raise ProviderError('无法解密 API 密钥，请在模型设置中重新填写。') from None


def valid_url(value):
    value = value.strip().rstrip('/')
    u = urlparse(value)
    if (not u.hostname or u.username or u.password or u.query or u.fragment or
        not (u.scheme == 'https' or (u.scheme == 'http' and u.hostname in ('localhost', '127.0.0.1')))):
        raise ValueError('API 地址需为 HTTPS Base URL，本机 localhost/127.0.0.1 可使用 HTTP。')
    return value


def public_config(p):
    return dict(id=p.id, name=p.name, model=p.model, base_url=p.base_url,
                api_kind=p.api_kind, enabled=p.enabled, max_output_tokens=p.max_output_tokens,
                key_configured=bool(p.secret))


def snapshot_config(p):
    return {**public_config(p), 'secret': p.secret}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward Authorization to a redirected host.


def generate(config, messages):
    key = decrypt(config['secret'])
    if not key:
        raise ProviderError('请先配置 API 密钥。')
    if config['api_kind'] == 'responses':
        endpoint = '/responses'
        payload = {'model': config['model'], 'input': messages, 'store': False,
                   'max_output_tokens': config['max_output_tokens']}
    else:
        endpoint = '/chat/completions'
        payload = {'model': config['model'], 'messages': messages,
                   'max_tokens': config['max_output_tokens']}
    req = urllib.request.Request(config['base_url'] + endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode(), method='POST',
        headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=120) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ProviderError('模型响应过大，请降低输出上限后重试。')
        data = json.loads(raw)
        if config['api_kind'] == 'responses':
            if data.get('status') != 'completed':
                raise ProviderError('模型未完整返回结果，可能达到输出上限或被拒绝；请调整设置后重试。')
            text = '\n'.join(part['text'] for item in data.get('output', [])
                             if item.get('type') == 'message' for part in item.get('content', [])
                             if part.get('type') == 'output_text')
        else:
            choice = data['choices'][0]
            if choice.get('finish_reason') != 'stop':
                raise ProviderError('模型响应未完成，请调整输出上限后重试。')
            text = choice['message']['content']
        if not isinstance(text, str) or not text.strip():
            raise ProviderError('模型返回空文本或拒绝回答，请调整资料后重试。')
        return {'text': text, 'usage': data.get('usage') or {}}
    except urllib.error.HTTPError as exc:
        reasons = {401:'API 密钥无效',403:'接口或模型无访问权限',404:'模型或 API 地址不存在',
                   429:'服务商限流或额度不足'}
        raise ProviderError(reasons.get(exc.code, '模型接口请求失败') + f'（HTTP {exc.code}）。') from None
    except ProviderError:
        raise
    except Exception:
        raise ProviderError('模型连接超时、网络异常或响应格式错误，请检查设置后重试。') from None
