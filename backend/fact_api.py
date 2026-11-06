"""M04-A human-reviewed, source-grounded fact API. No real model calls."""
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend.models import Project, DocumentFile, DocumentSegment, FactAssertion
from core.extraction.contracts import FIELD_LABELS, MockExtractor, SourceSegment

router = APIRouter(prefix="/api", tags=["M04-A structured facts"])

def get_db():
    with SessionLocal() as db:
        yield db

class FactCreate(BaseModel):
    segment_id: int = Field(gt=0)
    field_key: str
    value_text: str = Field(min_length=1, max_length=3000)
    evidence_quote: str = Field(min_length=1, max_length=4000)

class FactReview(BaseModel):
    review_status: str
    reviewer_note: str = Field(default="", max_length=1000)

def project_or_404(db, project_id):
    if db.get(Project, project_id) is None:
        raise HTTPException(404, "项目不存在")

def format_fact(f, location):
    return {"id":f.id,"project_id":f.project_id,"document_id":f.document_id,"segment_id":f.segment_id,
            "location":location,"field_key":f.field_key,"field_label":FIELD_LABELS[f.field_key],
            "value_text":f.value_text,"evidence_quote":f.evidence_quote,"origin":f.origin,
            "review_status":f.review_status,"evidence_grade":f.evidence_grade,"reviewer_note":f.reviewer_note,
            "verification_status":"unverified", "created_at":f.created_at.isoformat() if f.created_at else None}

@router.get('/extraction/fields')
def extraction_fields():
    return {"fields":FIELD_LABELS, "extractor":"mock", "external_llm_enabled":False,
            "notice":"M04-A 不使用真实模型；人工确认不代表外部真实性核验。"}

@router.post('/projects/{project_id}/extraction/preview')
def mock_preview(project_id: int, db: Session=Depends(get_db)):
    project_or_404(db, project_id)
    rows=db.execute(select(DocumentSegment.id,DocumentSegment.document_id,DocumentSegment.location,DocumentSegment.content)
                    .join(DocumentFile, DocumentFile.id == DocumentSegment.document_id)
                    .where(DocumentFile.project_id==project_id).limit(500)).all()
    sources=[SourceSegment(id=r.id,document_id=r.document_id,location=r.location,text=r.content) for r in rows]
    candidates=MockExtractor().extract(sources)
    return {"mode":"mock","scanned_segments":len(sources),"candidates":[vars(c) for c in candidates],
            "message":"Mock 仅验证接口，不自动推断 BP 事实。请从原文片段人工建立事实记录。"}

@router.post('/projects/{project_id}/facts',status_code=201)
def create_fact(project_id: int, payload: FactCreate, db: Session=Depends(get_db)):
    project_or_404(db,project_id)
    if payload.field_key not in FIELD_LABELS:
        raise HTTPException(422,"未知字段")
    segment=db.get(DocumentSegment,payload.segment_id)
    if segment is None:
        raise HTTPException(404,"来源片段不存在")
    doc=db.get(DocumentFile,segment.document_id)
    if doc is None or doc.project_id != project_id:
        raise HTTPException(422,"来源片段不属于该项目")
    quote=payload.evidence_quote.strip()
    if not quote or quote not in segment.content:
        raise HTTPException(422,"证据引文必须逐字出现在来源片段中")
    value=payload.value_text.strip()
    if not value:
        raise HTTPException(422,"字段值不能为空")
    f=FactAssertion(project_id=project_id,document_id=doc.id,segment_id=segment.id,
                    field_key=payload.field_key,value_text=value,evidence_quote=quote,
                    origin='manual',review_status='pending',evidence_grade='A')
    db.add(f);db.commit();db.refresh(f)
    return format_fact(f,segment.location)

@router.get('/projects/{project_id}/facts')
def list_facts(project_id: int,db: Session=Depends(get_db)):
    project_or_404(db,project_id)
    rows=db.execute(select(FactAssertion,DocumentSegment.location).join(DocumentSegment,DocumentSegment.id==FactAssertion.segment_id)
                    .where(FactAssertion.project_id==project_id).order_by(FactAssertion.id.desc())).all()
    return [format_fact(f,loc) for f,loc in rows]

@router.patch('/facts/{fact_id}/review')
def review_fact(fact_id: int,payload: FactReview,db: Session=Depends(get_db)):
    if payload.review_status not in ('pending','confirmed','rejected'):
        raise HTTPException(422,"review_status 只能是 pending/confirmed/rejected")
    f=db.get(FactAssertion,fact_id)
    if f is None: raise HTTPException(404,"事实记录不存在")
    f.review_status=payload.review_status
    f.reviewer_note=payload.reviewer_note.strip()
    db.commit();db.refresh(f)
    location=db.get(DocumentSegment,f.segment_id).location
    return format_fact(f,location)

@router.get('/projects/{project_id}/structured-profile')
def structured_profile(project_id: int,db: Session=Depends(get_db)):
    project_or_404(db,project_id)
    facts=db.scalars(select(FactAssertion).where(FactAssertion.project_id==project_id,
                      FactAssertion.review_status=='confirmed').order_by(FactAssertion.id)).all()
    grouped=defaultdict(list)
    for f in facts:
        grouped[f.field_key].append({"value":f.value_text,"assertion_id":f.id,"segment_id":f.segment_id,
                                     "evidence_grade":f.evidence_grade,"verification_status":"unverified"})
    conflicts=[{"field_key":key,"values":sorted({v['value'] for v in vals}),"assertion_ids":[v['assertion_id'] for v in vals]}
               for key,vals in grouped.items() if len({v['value'] for v in vals})>1]
    return {"project_id":project_id,"fields":dict(grouped),"missing_fields":[k for k in FIELD_LABELS if k not in grouped],
            "potential_conflicts":conflicts,"notice":"仅汇总人工审核的 BP 自述；确认不代表真实性已核验。不同值只是潜在冲突，需结合时间与口径核查。"}
