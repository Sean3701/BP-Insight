import json
import urllib.error
from contextlib import contextmanager
import pytest
from backend import providers


def cfg(kind='responses'):
    return {'secret':providers.encrypt('local-test-key'),'model':'example-model','base_url':'https://api.openai.com/v1',
            'api_kind':kind,'max_output_tokens':2000}


def transport(monkeypatch,result,check=None):
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,n):return json.dumps(result).encode()
    class Opener:
        def open(self,req,timeout):
            if check:check(req,timeout)
            return Response()
    monkeypatch.setattr(providers.urllib.request,'build_opener',lambda *args:Opener())


def test_responses_request_and_output(monkeypatch):
    def check(req,timeout):
        body=json.loads(req.data)
        assert req.full_url=='https://api.openai.com/v1/responses'
        assert body['store'] is False and body['max_output_tokens']==2000
        assert body['input'][0]['content']=='hello'
        assert 'api_key' not in body and timeout==120
    transport(monkeypatch,{'status':'completed','output':[{'type':'reasoning'},{'type':'message','content':[{'type':'output_text','text':'answer'}]}],'usage':{'total_tokens':9}},check)
    assert providers.generate(cfg(),[{'role':'user','content':'hello'}])=={'text':'answer','usage':{'total_tokens':9}}


def test_incomplete_output_never_becomes_report(monkeypatch):
    transport(monkeypatch,{'status':'incomplete','output':[]})
    with pytest.raises(providers.ProviderError,match='未完整'):
        providers.generate(cfg(),[])


def test_chat_compatible_request(monkeypatch):
    def check(req,timeout):
        body=json.loads(req.data)
        assert req.full_url.endswith('/chat/completions')
        assert body['messages'][0]['content']=='hello' and body['max_tokens']==2000
    transport(monkeypatch,{'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':'ok'}}],'usage':{}},check)
    assert providers.generate(cfg('chat_completions'),[{'role':'user','content':'hello'}])['text']=='ok'


def test_http_error_does_not_leak_server_body(monkeypatch):
    class Opener:
        def open(self,*a,**kw):
            raise urllib.error.HTTPError('https://secret-url',401,'secret-response',{},None)
    monkeypatch.setattr(providers.urllib.request,'build_opener',lambda *args:Opener())
    with pytest.raises(providers.ProviderError) as exc:providers.generate(cfg(),[])
    assert '401' in str(exc.value) and 'secret' not in str(exc.value)


def test_redirect_credentials_not_forwarded():
    assert providers.NoRedirect().redirect_request(None,None,302,'',{},'https://attacker.example') is None
