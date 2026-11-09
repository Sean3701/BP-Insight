import json
import uuid
import time
import threading
from io import BytesIO
from docx import Document
from fastapi.testclient import TestClient
from backend.main import app
from functools import lru_cache


@lru_cache
def doc_bytes(text):
    buf = BytesIO()
    d = Document()
    for line in text.splitlines():
        d.add_paragraph(line)
    d.save(buf)
    return buf.getvalue()


def import_bp(client, text='企业名称：星河机器人\n核心产品为工业机器人。', request_id=None):
    return client.post('/api/v2/imports', data={'request_id': request_id or str(uuid.uuid4())},
                       files={'file': ('company.docx', doc_bytes(text))})


def test_default_model_and_secret_updates():
    with TestClient(app) as c:
        response = c.get('/api/v2/models')
        assert response.status_code == 200
        models = response.json()
        assert len(models) == 1 and models[0]['name'] == 'ChatGPT'
        m = models[0]
        result = c.put(f"/api/v2/models/{m['id']}", json={**m, 'api_key': 'test-secret-123'})
        assert result.status_code == 200, result.text
        assert result.json()['key_configured']
        assert 'test-secret' not in result.text
        # Editing a URL must not silently forward a saved key to a new endpoint.
        moved = c.put(f"/api/v2/models/{m['id']}", json={**m, 'base_url': 'https://other.example/v1'})
        assert moved.status_code == 422
        whitespace = c.put(f"/api/v2/models/{m['id']}", json={**m, 'base_url':'https://other.example/v1','api_key':' '})
        assert whitespace.status_code == 422
        from backend.database import DB_PATH
        assert b'test-secret-123' not in DB_PATH.read_bytes()


def test_connection_test_is_explicit_and_sanitized(monkeypatch):
    from backend import providers
    monkeypatch.setattr(providers,'generate',lambda cfg,msg:{'text':'ok','usage':{'total_tokens':1}})
    with TestClient(app) as c:
        model=configure(c)
        r=c.post(f"/api/v2/models/{model['id']}/test")
        assert r.status_code==200,r.text
        assert r.json()['ok'] is True and 'secret' not in r.text


def test_frontend_served_and_invalid_host_rejected():
    with TestClient(app) as c:
        assert c.get('/app/').status_code==200
        assert c.get('/app/app.js').status_code==200
        assert c.get('/api/v2/models',headers={'Host':'attacker.example'}).status_code==400


def test_import_auto_name_reuse_and_rename():
    with TestClient(app) as c:
        rid = str(uuid.uuid4())
        r = import_bp(c, request_id=rid)
        assert r.status_code == 201, r.text
        p = r.json()['project']
        assert p['name'] == '星河机器人'
        reused = import_bp(c, request_id=rid)
        assert reused.status_code == 201 and reused.json()['project']['id'] == p['id']
        conflict = import_bp(c, text='不同资料', request_id=rid)
        assert conflict.status_code == 409
        assert c.patch(f"/api/v2/projects/{p['id']}", json={'name':'  新名称  '}).json()['name']=='新名称'
        assert c.patch(f"/api/v2/projects/{p['id']}", json={'name':'  '}).status_code == 422
        assert any(x['id']==p['id'] for x in c.get('/api/v2/projects').json())


def test_invalid_import_does_not_create_project():
    with TestClient(app) as c:
        before = len(c.get('/api/projects').json())
        r=c.post('/api/v2/imports',data={'request_id':str(uuid.uuid4())},files={'file':('bad.exe',b'bad')})
        assert r.status_code==400
        assert len(c.get('/api/projects').json())==before


def test_missing_key_and_cross_project_report_are_rejected():
    with TestClient(app) as c:
        r=import_bp(c)
        assert r.status_code==201
        pid=r.json()['project']['id']
        model=c.post('/api/v2/models',json={'name':'No key', 'model':'gpt-5-mini', 'base_url':'https://api.openai.com/v1', 'api_kind':'responses'}).json()
        r=c.post(f'/api/v2/projects/{pid}/runs',json={'model_ids':[model['id']], 'request_id':str(uuid.uuid4())})
        assert r.status_code==422 and '密钥' in r.text
        r=c.post(f'/api/v2/projects/{pid}/messages',json={'model_id':model['id'],'question':'test','report_id':999999,'request_id':str(uuid.uuid4())})
        assert r.status_code==404


def test_api_rejects_cross_origin_mutation():
    with TestClient(app) as c:
        r=c.post('/api/projects',json={'name':'unwanted'},headers={'Origin':'https://evil.example'})
        assert r.status_code==403


def configure(c, name='ChatGPT'):
    models=c.get('/api/v2/models').json()
    m=next((x for x in models if x['name']==name),None)
    payload={'name':name,'model':'gpt-5-mini','base_url':'https://api.openai.com/v1','api_kind':'responses','api_key':'test-only-key'}
    return (c.put(f"/api/v2/models/{m['id']}",json=payload) if m else c.post('/api/v2/models',json=payload)).json()


def wait_job(c,job_id):
    for _ in range(100):
        r=c.get(f'/api/v2/jobs/{job_id}')
        assert r.status_code==200, r.text
        j=r.json()
        if j['status'] in ('completed','failed'):
            return j
        time.sleep(.03)
    raise AssertionError('job did not finish')


def fake_report(config,messages):
    context=json.loads(messages[-1]['content'])
    source=context['sources'][0]['id']
    return {'text':json.dumps({'summary':'企业自述为机器人企业，尚未核验。','sections':[{'title':'项目概况','body':'工业机器人。','source_ids':[source]}],'questions':['请提供订单依据。']},ensure_ascii=False),'usage':{'total_tokens':100}}


def test_parallel_reports_snapshot_pdf_and_chat(monkeypatch):
    from backend import providers
    barrier=threading.Barrier(2)
    def parallel(config,messages):
        barrier.wait(timeout=5)
        return fake_report(config,messages)
    monkeypatch.setattr(providers,'generate',parallel)
    with TestClient(app) as c:
        pid=import_bp(c).json()['project']['id']
        a,b=configure(c),configure(c,'Second')
        payload={'model_ids':[a['id'],b['id']], 'request_id':str(uuid.uuid4())}
        r=c.post(f'/api/v2/projects/{pid}/runs',json=payload)
        assert r.status_code==202,r.text
        ids=[j['id'] for j in r.json()]
        jobs=[wait_job(c,x) for x in ids]
        assert all(j['status']=='completed' for j in jobs),jobs
        repeat=c.post(f'/api/v2/projects/{pid}/runs',json=payload)
        assert [j['id'] for j in repeat.json()]==ids
        assert all('secret' not in json.dumps(j) for j in jobs)
        c.patch(f'/api/v2/projects/{pid}',json={'name':'已修改项目名'})
        assert c.get(f'/api/v2/jobs/{ids[0]}').json()['project_name']=='星河机器人'
        pdf=c.get(f'/api/v2/reports/{ids[0]}/pdf')
        assert pdf.status_code==200 and pdf.content.startswith(b'%PDF-')
        from pypdf import PdfReader
        text=''.join(p.extract_text() for p in PdfReader(BytesIO(pdf.content)).pages)
        assert '星河机器人' in text and '工业机器人' in text and 'company.docx' in text
        def answer(config,messages):
            context=json.loads(messages[-1]['content'])
            assert context['report']['summary'].startswith('企业自述')
            assert context['question']=='核心产品？'
            return {'text':json.dumps({'answer':'工业机器人，来自企业自述。','source_ids':[context['sources'][0]['id']]}),'usage':{}}
        monkeypatch.setattr(providers,'generate',answer)
        q={'model_id':a['id'],'report_id':ids[0],'question':'核心产品？','request_id':str(uuid.uuid4())}
        res=c.post(f'/api/v2/projects/{pid}/messages',json=q)
        assert res.status_code==202,res.text
        message=wait_job(c,res.json()['id'])
        assert message['status']=='completed' and message['result']['answer'].startswith('工业机器人')
        assert len(c.get(f'/api/v2/projects/{pid}/messages').json())==1
        other=import_bp(c,text='公司名称：另一个项目').json()['project']['id']
        assert c.post(f'/api/v2/projects/{other}/messages',json=q).status_code==404
        assert c.get(f'/api/v2/projects/{other}/messages').json()==[]


def test_provider_failure_and_invalid_citation_not_completed(monkeypatch):
    from backend import providers
    def invalid(config,messages):
        if config['name']=='Broken':
            raise providers.ProviderError('API 密钥无效（HTTP 401）。')
        return {'text':json.dumps({'summary':'x','sections':[{'title':'x','body':'x','source_ids':[999999]}],'questions':[]}), 'usage':{}}
    monkeypatch.setattr(providers,'generate',invalid)
    with TestClient(app) as c:
        pid=import_bp(c).json()['project']['id']
        a,b=configure(c),configure(c,'Broken')
        r=c.post(f'/api/v2/projects/{pid}/runs',json={'model_ids':[a['id'],b['id']], 'request_id':str(uuid.uuid4())})
        assert r.status_code==202,r.text
        jobs=[wait_job(c,j['id']) for j in r.json()]
        assert all(j['status']=='failed' for j in jobs)
        assert '引用' in jobs[0]['error']
        assert '401' in jobs[1]['error']
        assert not any(j['id'] in [x['id'] for x in jobs] for j in c.get('/api/v2/reports').json() if not j.get('legacy'))


def test_corrected_facts_are_in_model_input_and_batch_identity_is_immutable(monkeypatch):
    from backend import providers
    def inspect(config,messages):
        context=json.loads(messages[-1]['content'])
        assert context['facts'][0]['value']=='已人工补充的产品'
        return fake_report(config,messages)
    monkeypatch.setattr(providers,'generate',inspect)
    with TestClient(app) as c:
        imported=import_bp(c).json();pid=imported['project']['id']
        segment=c.get(f"/api/documents/{imported['document']['id']}/segments").json()['items'][0]
        c.post(f'/api/projects/{pid}/facts',json={'segment_id':segment['id'],'field_key':'product','value_text':'已人工补充的产品','evidence_quote':segment['content']})
        a,b=configure(c),configure(c,'Other model')
        request_id=str(uuid.uuid4())
        r=c.post(f'/api/v2/projects/{pid}/runs',json={'model_ids':[a['id']], 'request_id':request_id})
        assert wait_job(c,r.json()[0]['id'])['status']=='completed'
        changed=c.post(f'/api/v2/projects/{pid}/runs',json={'model_ids':[b['id']], 'request_id':request_id})
        assert changed.status_code==409
