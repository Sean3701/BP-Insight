"""M02 model adapter. API keys stay in the backend environment, never browser input."""
import json
import os
import urllib.request
from dataclasses import dataclass

@dataclass(frozen=True)
class ModelSettings:
    provider: str
    model: str
    base_url: str
    api_key: str


def get_settings() -> ModelSettings:
    # Load local optional .env without forcing the package to be installed globally.
    from dotenv import load_dotenv
    from pathlib import Path
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    return ModelSettings(
        provider=os.getenv("VC_LLM_PROVIDER", "mock").lower().strip(),
        model=os.getenv("VC_LLM_MODEL", "mock-demo").strip(),
        base_url=os.getenv("VC_LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
        api_key=os.getenv("VC_LLM_API_KEY", "").strip(),
    )

class ModelError(RuntimeError):
    pass


def generate(prompt: str, system_prompt: str = "你是严谨的投资分析助手。不得编造数据。") -> dict:
    settings = get_settings()
    if settings.provider == "mock":
        return {"provider": "mock", "model": "mock-demo", "answer": "【模拟结果，非真实模型】已收到测试问题：" + prompt[:200] + "。当前未调用任何外部模型。"}
    if settings.provider != "openai-compatible":
        raise ModelError("不支持的模型提供方，请检查 VC_LLM_PROVIDER")
    if not settings.api_key:
        raise ModelError("未配置 VC_LLM_API_KEY；请先编辑项目根目录的 .env")
    if not settings.model:
        raise ModelError("未配置 VC_LLM_MODEL")
    if not settings.base_url.startswith("https://") and not settings.base_url.startswith("http://127.0.0.1:") and not settings.base_url.startswith("http://localhost:"):
        raise ModelError("远程模型接口必须使用 HTTPS")
    request_data = json.dumps({"model": settings.model, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}], "temperature": 0.2}).encode("utf-8")
    req = urllib.request.Request(settings.base_url + "/chat/completions", data=request_data, method="POST", headers={"Content-Type": "application/json", "Authorization": "Bearer " + settings.api_key})
    try:
        with urllib.request.urlopen(req, timeout=75) as resp:
            result = json.load(resp)
        answer = result["choices"][0]["message"]["content"]
        if not isinstance(answer, str):
            raise ModelError("模型响应不是文本，请检查兼容接口")
        return {"provider": settings.provider, "model": settings.model, "answer": answer}
    except Exception as exc:
        if isinstance(exc, ModelError):
            raise
        # Do not expose URLs, headers, payloads or remote raw error bodies.
        raise ModelError("模型请求失败。请检查网络、服务商地址、模型名称、余额及密钥配置。错误类型：" + type(exc).__name__) from None
