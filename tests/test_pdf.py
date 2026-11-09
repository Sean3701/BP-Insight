from io import BytesIO
from pypdf import PdfReader
from backend.report_pdf import render_pdf


def test_long_chinese_report_has_embedded_font_and_complete_text():
    data={'project_name':'中文研究报告','model_name':'ChatGPT','model':'test','created_at':'2026-11-09',
          'result':{'summary':'摘要','sections':[{'title':'长报告','body':('测试中文分页和符号 <>&\n'*150)+'最后一行结束标记','source_ids':[]}],
                    'questions':['核查来源']},'sources':[]}
    pdf=PdfReader(BytesIO(render_pdf(data)))
    text=''.join(p.extract_text() for p in pdf.pages)
    assert len(pdf.pages)>1 and '最后一行结束标记' in text and '<>&' in text
    fonts=[ref.get_object() for page in pdf.pages for ref in page['/Resources']['/Font'].values()]
    assert any('/FontFile2' in f.get('/FontDescriptor',{}) for f in fonts)
