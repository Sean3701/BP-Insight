"""Tests run against a disposable assembled project directory, never user's db."""
from io import BytesIO
from fastapi.testclient import TestClient
from backend.main import app
from docx import Document


def test_m04a_grounding_and_profile():
    with TestClient(app) as client:
        p=client.post('/api/projects',json={'name':'M04A demo','description':''})
        assert p.status_code==201,p.text
        pid=p.json()['id']
        b=BytesIO();d=Document();d.add_paragraph('本轮计划融资5000万元，2025年营收2800万元。');d.save(b)
        res=client.post(f'/api/projects/{pid}/documents',files={'file':('demo.docx',b.getvalue(),'application/vnd.openxmlformats-officedocument.wordprocessingml.document')})
        assert res.status_code==201,res.text
        docid=res.json()['id']
        segments=client.get(f'/api/documents/{docid}/segments').json()['items']
        sid=next(s['id'] for s in segments if '融资' in s['content'])
        base={'segment_id':sid,'field_key':'financing_amount','value_text':'5000万元','evidence_quote':'本轮计划融资5000万元'}
        assert client.post(f'/api/projects/{pid}/facts',json={**base,'evidence_quote':'不存在的引文'}).status_code==422
        fact=client.post(f'/api/projects/{pid}/facts',json=base)
        assert fact.status_code==201,fact.text
        fid=fact.json()['id']
        assert fact.json()['verification_status']=='unverified'
        assert client.get(f'/api/projects/{pid}/structured-profile').json()['fields']=={}
        approve=client.patch(f'/api/facts/{fid}/review',json={'review_status':'confirmed','reviewer_note':'原文一致'})
        assert approve.status_code==200,approve.text
        profile=client.get(f'/api/projects/{pid}/structured-profile').json()
        assert profile['fields']['financing_amount'][0]['value']=='5000万元'
        assert profile['fields']['financing_amount'][0]['verification_status']=='unverified'
        assert 'revenue' in profile['missing_fields']
        another=client.post(f'/api/projects/{pid}/facts',json={**base,'value_text':'6000万元'})
        fid2=another.json()['id']
        client.patch(f'/api/facts/{fid2}/review',json={'review_status':'confirmed'})
        profile=client.get(f'/api/projects/{pid}/structured-profile').json()
        assert profile['potential_conflicts'][0]['field_key']=='financing_amount'
        preview=client.post(f'/api/projects/{pid}/extraction/preview').json()
        assert preview['mode']=='mock' and preview['candidates']==[]
