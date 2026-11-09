from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from core.llm.client import get_settings, ModelError
from core.agents.demo import run_demo_agent
from time import monotonic
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.database import SessionLocal, initialize_database
from backend.models import Project
from backend.schemas import ProjectCreate, ProjectRead

@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    from backend.analysis_api import recover_interrupted_runs
    recover_interrupted_runs()
    from backend.workspace_api import initialize_workspace
    initialize_workspace()
    yield

app = FastAPI(title="VC Intelligence Platform API", version="0.4.0d", lifespan=lifespan)

# Local-only application: reject browser cross-origin requests and DNS rebinding.
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse
from urllib.parse import urlparse
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1','localhost','testserver'])

@app.middleware('http')
async def local_origin(request, call_next):
    origin = request.headers.get('origin')
    if request.method not in ('GET','HEAD','OPTIONS') and origin:
        expected = f'{request.url.scheme}://{request.headers.get("host", "")}'
        if origin != expected:
            return JSONResponse({'detail':'不允许跨站操作本地应用'},status_code=403)
    return await call_next(request)

def get_db():
    with SessionLocal() as db:
        yield db

@app.get("/health")
def health():
    return {"status": "ok", "service": "vc-platform-backend", "time": datetime.now(timezone.utc).isoformat()}

@app.get("/api/projects", response_model=list[ProjectRead])
def list_projects(db: Session = Depends(get_db)):
    return list(db.scalars(select(Project).order_by(Project.id.desc())).all())

@app.post("/api/projects", response_model=ProjectRead, status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="项目名称不能为空")
    project = Project(name=name, description=payload.description.strip())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


class TestQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=3000)

@app.get("/api/model/status")
def model_status():
    s = get_settings()
    return {"provider": s.provider, "model": s.model, "base_url": "(mock mode)" if s.provider == "mock" else s.base_url, "key_configured": bool(s.api_key), "mode": "mock" if s.provider == "mock" else "external"}

@app.post("/api/agents/demo")
def test_agent(payload: TestQuestion):
    t0 = monotonic()
    try:
        output = run_demo_agent(payload.question)
        return {**output, "elapsed_ms": round((monotonic() - t0)*1000)}
    except ModelError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None

# M03: uploaded documents are always local, associated with a Project.
import hashlib
import os
import uuid
from pathlib import Path
from fastapi import File, UploadFile
from backend.models import DocumentFile, DocumentSegment
from backend.document_parser import SUPPORTED, MAX_BYTES, DocumentParseError, extract
from backend.database import ROOT, DATA_ROOT

UPLOAD_ROOT = DATA_ROOT / 'uploads'
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)


def _file_info(d):
    return {'id': d.id, 'project_id': d.project_id, 'filename': d.original_name,
            'size_bytes': d.bytes_size, 'sha256': d.sha256, 'status': d.status,
            'segments': d.segment_count, 'warning': d.warning,
            'created_at': d.created_at.isoformat() if d.created_at else None}


@app.get('/api/projects/{project_id}/documents')
def list_documents(project_id: int, db: Session = Depends(get_db)):
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail='项目不存在')
    files = db.scalars(select(DocumentFile).where(DocumentFile.project_id == project_id).order_by(DocumentFile.id.desc())).all()
    return [_file_info(d) for d in files]


@app.post('/api/projects/{project_id}/documents', status_code=201)
async def upload_document(project_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail='项目不存在')
    # Do not trust arbitrary upload paths or MIME supplied by browsers.
    filename = Path((file.filename or '').replace('\\', '/')).name.strip()
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED or not filename or len(filename) > 240:
        raise HTTPException(status_code=400, detail='仅支持有效文件名的 PDF/PPTX/DOCX/XLSX，文件名不得超过240字符')
    project_dir = UPLOAD_ROOT / str(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    temp_path = project_dir / f'{uuid.uuid4().hex}.upload'
    total = 0
    sha = hashlib.sha256()
    try:
        with temp_path.open('wb') as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_BYTES:
                    raise HTTPException(status_code=413, detail='单个文件不能超过25MB')
                sha.update(chunk)
                out.write(chunk)
        if total == 0:
            raise HTTPException(status_code=400, detail='文件为空')
        stored_name = f'{uuid.uuid4().hex}{ext}'
        stored_path = project_dir / stored_name
        os.replace(temp_path, stored_path)
        try:
            parts, warning = extract(stored_path)
        except DocumentParseError as exc:
            # Keep the original file for troubleshooting, but explicitly mark failure.
            parts, warning = [], str(exc)
            status = 'failed'
        else:
            status = 'processed' if parts else 'empty'
        record = DocumentFile(project_id=project_id, original_name=filename,
                              stored_name=stored_name, sha256=sha.hexdigest(),
                              bytes_size=total, status=status,
                              segment_count=len(parts), warning=warning)
        db.add(record)
        db.flush()
        db.add_all(DocumentSegment(document_id=record.id, location=p.location, content=p.text) for p in parts)
        db.commit()
        db.refresh(record)
        return _file_info(record)
    except Exception:
        db.rollback()
        raise
    finally:
        await file.close()
        if temp_path.exists():
            temp_path.unlink()


@app.get('/api/documents/{document_id}/segments')
def get_segments(document_id: int, offset: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    if not db.get(DocumentFile, document_id):
        raise HTTPException(status_code=404, detail='文件不存在')
    if offset < 0 or not 1 <= limit <= 200:
        raise HTTPException(status_code=422, detail='分页参数无效')
    q = select(DocumentSegment).where(DocumentSegment.document_id == document_id).order_by(DocumentSegment.id).offset(offset).limit(limit)
    items = db.scalars(q).all()
    return {'document_id': document_id, 'offset': offset, 'limit': limit,
            'items': [{'id': s.id, 'location': s.location, 'content': s.content} for s in items]}


# M04-A: versioned extension, no changes to old M01-M03 routes.
from backend.fact_api import router as fact_router
app.include_router(fact_router)

# M04-B: additive investor overview routes, no change to historical routes.
from backend.overview_api import router as overview_router
app.include_router(overview_router)

# M04D: mock workflow and immutable report snapshots.
from backend.analysis_api import router as analysis_router
app.include_router(analysis_router)

from backend.workspace_api import router as workspace_router
from backend import workspace_jobs  # register routes before including router
app.include_router(workspace_router)

from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
app.mount('/app',StaticFiles(directory=ROOT/'frontend'/'web',html=True),name='workspace')

@app.get('/')
def home():
    return RedirectResponse('/app/')
