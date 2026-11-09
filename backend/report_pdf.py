"""A4 Chinese PDF exports; all model text escaped before ReportLab markup."""
from io import BytesIO
import json
import os
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

FONT='VCChinese'
font_path=Path(os.getenv('VC_PDF_FONT', 'C:/Windows/Fonts/simsun.ttc'))
if font_path.exists():
    pdfmetrics.registerFont(TTFont(FONT,str(font_path),subfontIndex=0))
else:
    FONT='STSong-Light'
    pdfmetrics.registerFont(UnicodeCIDFont(FONT))


def legacy_report(run):
    r=json.loads(run.report_json)
    sections=[]
    for s in r.get('sections',[]):
        body='\n'.join(f['label']+'：'+v['value'] for f in s['fields'] for v in f['records'])
        sections.append({'title':s['title'],'body':body or '暂无记录','source_ids':[]})
    return {'project_name':r.get('project',{}).get('name','历史报告'),'model_name':'历史 Mock','model':'mock',
            'created_at':run.created_at.isoformat(),'legacy':True,'sources':r.get('source_preview',[]),
            'result':{'summary':r.get('notice','模拟报告'),'sections':sections,'questions':[q['question'] for q in r.get('questions',[])]}}


def render_pdf(data):
    buf=BytesIO()
    base=ParagraphStyle('body',fontName=FONT,fontSize=10.5,leading=18,wordWrap='CJK',spaceAfter=8,textColor=colors.HexColor('#26384d'))
    heading=ParagraphStyle('heading',parent=base,fontSize=15,leading=22,spaceBefore=16,keepWithNext=True)
    title=ParagraphStyle('title',parent=base,fontSize=23,leading=30,spaceAfter=18)
    muted=ParagraphStyle('muted',parent=base,fontSize=9,leading=15,textColor=colors.HexColor('#6c7c91'))
    def p(text,style=base):
        return Paragraph(escape(str(text)).replace('\n','<br/>'),style)
    story=[p('VC INTELLIGENCE',muted),p(data['project_name'],title),
           p(f"模型：{data['model_name']} / {data['model']}    生成时间：{data['created_at']}",muted),
           p('历史模拟报告，非真实模型分析。' if data.get('legacy') else 'AI 辅助研究报告。材料为企业自述，引用仅说明文本来源，未经独立事实核验；模型推断需人工复核。',muted)]
    if data.get('context_limited'):
        story.append(p('输入资料超过上限，本报告仅基于部分文字。',muted))
    r=data['result']
    story += [p('研究摘要',heading),p(r.get('summary',''))]
    cited=set()
    for section in r.get('sections',[]):
        story += [p(section['title'],heading),p(section['body'])]
        ids=section.get('source_ids',[]);cited.update(ids)
        if ids:
            story.append(p('来源片段：'+', '.join('#'+str(i) for i in ids),muted))
    if r.get('questions'):
        story.append(p('后续尽调问题',heading))
        story.extend(p(f'{i}. {q}') for i,q in enumerate(r['questions'],1))
    story.append(p('来源原文',heading))
    for s in data.get('sources',[]):
        if not cited or s['id'] in cited:
            story += [p(f"#{s['id']} · {s.get('document_name','资料')} · {s['location']}",muted),p(s['content'])]
    def footer(canvas,doc):
        canvas.setFont(FONT,9)
        canvas.setFillColor(colors.HexColor('#8390a3'))
        canvas.drawString(48,30,'VC Intelligence / 本地研究报告')
        canvas.drawRightString(A4[0]-48,30,str(doc.page))
    doc=SimpleDocTemplate(buf,pagesize=A4,rightMargin=48,leftMargin=48,topMargin=42,bottomMargin=48,
                          title=data['project_name'],author='VC Intelligence')
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return buf.getvalue()
