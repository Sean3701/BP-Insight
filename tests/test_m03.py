from pathlib import Path
from tempfile import TemporaryDirectory
from io import BytesIO
from fastapi.testclient import TestClient
from docx import Document
from pptx import Presentation
from openpyxl import Workbook
from backend.document_parser import extract
from backend.main import app


def make_files(root):
    doc = Document(); doc.add_paragraph('Revenue 2025: 100'); doc.save(root/'sample.docx')
    prs = Presentation(); slide = prs.slides.add_slide(prs.slide_layouts[5]); slide.shapes.title.text = 'Company overview'; prs.save(root/'sample.pptx')
    wb=Workbook(); wb.active['A1']='Revenue'; wb.active['B1']=100; wb.save(root/'sample.xlsx')
    from reportlab.pdfgen.canvas import Canvas
    c=Canvas(str(root/'sample.pdf')); c.drawString(50,750,'Revenue 2025: 100'); c.save()


def test_formats_and_locations():
    with TemporaryDirectory() as tmp:
        root=Path(tmp);make_files(root)
        for suffix, location in [('.docx','段落'),('.pptx','幻灯片'),('.xlsx','工作表'),('.pdf','第1页')]:
            p=root/('sample'+suffix)
            segs,_=extract(p)
            assert segs and any(location in s.location for s in segs)


def test_api_preserves_project_and_upload():
    client=TestClient(app)
    with client:
        project = client.post('/api/projects',json={'name':'M03 test', 'description':''}).json()
        bio=BytesIO()
        d=Document(); d.add_paragraph('M03 example claim'); d.save(bio)
        result=client.post(f"/api/projects/{project['id']}/documents", files={'file':('case.docx',bio.getvalue(),'application/octet-stream')})
        assert result.status_code==201, result.text
        info=result.json(); assert info['status']=='processed'
        listed=client.get(f"/api/projects/{project['id']}/documents").json()
        assert any(x['id']==info['id'] for x in listed)
        segments=client.get(f"/api/documents/{info['id']}/segments").json()['items']
        assert any('M03 example claim' in x['content'] for x in segments)
        assert client.post(f"/api/projects/{project['id']}/documents", files={'file':('bad.exe',b'evil')}).status_code==400
