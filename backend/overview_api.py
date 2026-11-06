"""M04-B investor-facing compact overview. Read-only over existing M04-A facts.
No external LLM, no new migrations, no changes to historical records.
"""
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend.models import Project, FactAssertion, DocumentFile, DocumentSegment
from core.extraction.catalog import CATEGORIES, FIELD_CATALOG, FIELD_BY_KEY
from core.extraction.llm_contracts import DisabledExtractor, ExtractionInput

router = APIRouter(prefix='/api',tags=['M04-B overview'])

def get_db():
    with SessionLocal() as db:
        yield db

@router.get('/vc/field-catalog')
def field_catalog():
    return {'version':'vc-core-1','categories':CATEGORIES,'fields':FIELD_CATALOG,
            'extension_policy':'industry/stage add-ons can extend catalog; base keys stay stable'}

@router.get('/projects/{project_id}/vc-overview')
def overview(project_id:int,db:Session=Depends(get_db)):
    project=db.get(Project,project_id)
    if not project:
        raise HTTPException(404,'项目不存在')
    rows=db.execute(select(FactAssertion,DocumentSegment.location,DocumentFile.original_name)
        .join(DocumentSegment,DocumentSegment.id==FactAssertion.segment_id)
        .join(DocumentFile,DocumentFile.id==FactAssertion.document_id)
        .where(FactAssertion.project_id==project_id,FactAssertion.review_status!='rejected')
        .order_by(FactAssertion.id.desc())).all()
    grouped=defaultdict(list)
    for f,loc,filename in rows:
        if f.field_key not in FIELD_BY_KEY:
            continue
        grouped[f.field_key].append({
            'assertion_id':f.id,'value':f.value_text,'origin':f.origin,'review_status':f.review_status,
            'derivation':'source_claim','verification_status':'unverified',
            'evidence':{'document_id':f.document_id,'segment_id':f.segment_id,
                        'document_name':filename,'location':loc,'quote':f.evidence_quote}})
    sections=[]
    for category,title in CATEGORIES.items():
        fields=[]
        for field in FIELD_CATALOG:
            if field['category']!=category: continue
            candidates=grouped[field['key']]
            confirmed=[x for x in candidates if x['review_status']=='confirmed']
            preferred=confirmed[0] if confirmed else (candidates[0] if candidates else None)
            distinct={x['value'] for x in candidates if x['review_status']=='confirmed'}
            fields.append({'key':field['key'],'label':field['label'],
                'value':preferred['value'] if preferred else None,
                'state':('missing' if not preferred else 'potential_conflict' if len(distinct)>1 else
                         'source_claim_reviewed' if preferred['review_status']=='confirmed' else 'source_claim_pending'),
                'evidence':preferred['evidence'] if preferred else None,
                'candidate_count':len(candidates),'has_conflict':len(distinct)>1})
        sections.append({'key':category,'title':title,'fields':fields})
    return {'project_id':project.id,'project_name':project.name,'sections':sections,
            'summary':{'catalog_fields':len(FIELD_CATALOG),'with_candidates':sum(bool(grouped[f['key']]) for f in FIELD_CATALOG)},
            'notice':'已确认只表示人工审核了原文记录，绝不代表独立核实。未披露不等于企业不存在该信息。'}

@router.post('/projects/{project_id}/vc-extraction/dry-run')
def extraction_dry_run(project_id:int,db:Session=Depends(get_db)):
    if not db.get(Project,project_id):
        raise HTTPException(404,'项目不存在')
    count=db.execute(select(DocumentSegment.id).join(DocumentFile,DocumentFile.id==DocumentSegment.document_id)
        .where(DocumentFile.project_id==project_id)).all()
    extractor=DisabledExtractor()
    result=extractor.extract(ExtractionInput(project_id=project_id,segments=[]))
    return {'mode':'disabled_mock','scanned_segments':len(count),'candidates':result,
            'llm_enabled':False,'notice':'当前只验证统一接口；没有真实模型，不会自动生成 BP 字段或虚构结论。'}
