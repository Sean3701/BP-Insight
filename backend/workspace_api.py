"""Single-user workspace APIs. New tables preserve the original M04D data."""
import hashlib
import json
import re
import threading
import uuid
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from sqlalchemy import select
from backend.database import SessionLocal, DATA_ROOT
from backend.models import Project, DocumentFile, DocumentSegment
from backend.workspace_models import Provider, ImportReceipt, AIJob
from backend.document_parser import extract, MAX_BYTES, SUPPORTED, DocumentParseError
from backend.providers import public_config, encrypt, valid_url

router = APIRouter(prefix='/api/v2', tags=['Workspace'])
mutation_lock = threading.RLock()


def db_session():
    with SessionLocal() as db:
        yield db


def project_info(p):
    return {'id': p.id, 'name': p.name, 'description': p.description, 'created_at': p.created_at.isoformat()}


def project_or_404(db, pid):
    p = db.get(Project, pid)
    if not p:
        raise HTTPException(404, '项目不存在')
    return p


class ModelInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=200)
    base_url: str = Field(max_length=500)
    api_kind: Literal['responses', 'chat_completions'] = 'responses'
    enabled: bool = True
    max_output_tokens: int = Field(default=6000, ge=500, le=16000)
    api_key: str | None = Field(default=None, max_length=1000)
    clear_key: bool = False


def initialize_workspace():
    with SessionLocal() as db:
        # Include tombstones: intentionally deleting all models must not resurrect defaults.
        if not db.scalar(select(Provider.id).limit(1)):
            db.add(Provider(name='ChatGPT', model='gpt-5-mini', base_url='https://api.openai.com/v1', api_kind='responses'))
        for job in db.scalars(select(AIJob).where(AIJob.status.in_(['queued', 'running']))):
            from backend.workspace_models import now
            job.status = 'failed'
            job.error = '服务中断，任务未完成；请手动重试。'
            job.finished_at = now()
        db.commit()


@router.get('/models')
def models(db=Depends(db_session)):
    return [public_config(p) for p in db.scalars(select(Provider).where(Provider.deleted == False).order_by(Provider.id))]


def save_model(db, payload, p=None):
    new_key=(payload.api_key or '').strip()
    data = payload.model_dump(exclude={'api_key','clear_key'})
    data['name'], data['model'] = data['name'].strip(), data['model'].strip()
    if not data['name'] or not data['model']:
        raise HTTPException(422, '名称和模型 ID 不能为空')
    try:
        data['base_url'] = valid_url(data['base_url'])
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    existing = db.scalar(select(Provider).where(Provider.name == data['name'], Provider.deleted == False))
    if existing and (not p or existing.id != p.id):
        raise HTTPException(409, '模型显示名称已存在')
    if p and p.secret and data['base_url'] != p.base_url and not new_key and not payload.clear_key:
        raise HTTPException(422, '修改 API 地址时请重新输入密钥或清除旧密钥，避免误发送。')
    p = p or Provider()
    for k,v in data.items():
        setattr(p,k,v)
    if payload.clear_key:
        p.secret = ''
    elif new_key:
        p.secret = encrypt(new_key)
    db.add(p)
    db.commit()
    db.refresh(p)
    return public_config(p)


@router.post('/models', status_code=201)
def create_model(payload: ModelInput, db=Depends(db_session)):
    with mutation_lock:
        return save_model(db,payload)


@router.put('/models/{model_id}')
def update_model(model_id:int, payload:ModelInput, db=Depends(db_session)):
    with mutation_lock:
        p=db.get(Provider,model_id)
        if not p or p.deleted:
            raise HTTPException(404,'模型不存在')
        return save_model(db,payload,p)


@router.delete('/models/{model_id}')
def delete_model(model_id:int,db=Depends(db_session)):
    with mutation_lock:
        p=db.get(Provider,model_id)
        if not p or p.deleted:
            raise HTTPException(404,'模型不存在')
        p.deleted,p.enabled,p.secret=True,False,''
        db.commit()
        return {'ok':True}


def suggest_name(parts, filename):
    lines=[line.strip() for part in parts[:6] for line in part.text.splitlines() if line.strip()]
    for line in lines:
        m=re.match(r'^(?:企业名称|公司名称|项目名称|企业|公司|项目)\s*[:：]\s*(.{2,80})$',line)
        if m:
            return m.group(1),'BP 原文名称标签'
    for line in lines[:10]:
        if 3<=len(line)<=50 and re.fullmatch(r'[\w\u4e00-\u9fff（）()· ]+(?:有限公司|股份公司)',line):
            return line,'BP 首页公司名'
    name=re.sub(r'[_\-\s]*(商业计划书|融资计划书|BP)$','',Path(filename).stem,flags=re.I).strip()
    return (name or '未命名项目')[:200],'文件名候选（可手动修改）'


def receipt_info(db, receipt):
    d=db.get(DocumentFile,receipt.document_id)
    return {'project':project_info(db.get(Project,receipt.project_id)), 'name_source':receipt.name_source,
            'document':{'id':d.id,'filename':d.original_name,'status':d.status,'segments':d.segment_count,'warning':d.warning}}


@router.post('/imports',status_code=201)
def import_document(file:UploadFile=File(...),request_id:str=Form(...,min_length=8,max_length=80),db=Depends(db_session)):
    filename=Path((file.filename or '').replace('\\','/')).name.strip()
    ext=Path(filename).suffix.lower()
    if not filename or len(filename)>240 or ext not in SUPPORTED:
        raise HTTPException(400,'仅支持 PDF/PPTX/DOCX/XLSX，文件名最长240字符')
    content=file.file.read(MAX_BYTES+1)
    file.file.close()
    if not content:
        raise HTTPException(400,'文件为空')
    if len(content)>MAX_BYTES:
        raise HTTPException(413,'单个文件不能超过25MB')
    digest=hashlib.sha256(content).hexdigest()
    with mutation_lock:
        receipt=db.get(ImportReceipt,request_id)
        if receipt:
            if receipt.digest!=digest:
                raise HTTPException(409,'上传请求标识已用于其他文件，请重新选择')
            return receipt_info(db,receipt)
        target=DATA_ROOT/'uploads'/'inbox'/f'{uuid.uuid4().hex}{ext}'
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(content)
        try:
            try:
                parts,warning=extract(target)
                status='processed' if parts else 'empty'
            except DocumentParseError as exc:
                parts,warning,status=[],str(exc),'failed'
            name,source=suggest_name(parts,filename)
            p=Project(name=name,description='')
            db.add(p); db.flush()
            d=DocumentFile(project_id=p.id,original_name=filename,stored_name=target.name,
                sha256=digest,bytes_size=len(content),status=status,segment_count=len(parts),warning=warning)
            db.add(d);db.flush()
            db.add_all(DocumentSegment(document_id=d.id,location=x.location,content=x.text) for x in parts)
            receipt=ImportReceipt(request_id=request_id,digest=digest,project_id=p.id,document_id=d.id,name_source=source)
            db.add(receipt)
            project_dir=DATA_ROOT/'uploads'/str(p.id)
            project_dir.mkdir(parents=True,exist_ok=True)
            dest=project_dir/target.name
            target.replace(dest)
            db.commit()
            return receipt_info(db,receipt)
        except Exception:
            db.rollback()
            target.unlink(missing_ok=True)
            if 'dest' in locals():
                dest.unlink(missing_ok=True)
            raise


@router.get('/projects')
def projects(db=Depends(db_session)):
    return [project_info(p) for p in db.scalars(select(Project).order_by(Project.id.desc()))]


class Rename(BaseModel):
    name:str=Field(min_length=1,max_length=200)


@router.patch('/projects/{pid}')
def rename(pid:int,payload:Rename,db=Depends(db_session)):
    p=project_or_404(db,pid)
    if not payload.name.strip():
        raise HTTPException(422,'项目名称不能为空')
    p.name=payload.name.strip()
    db.commit()
    return project_info(p)
