"""Local background mock tasks, durable snapshots, no model API calls."""
import json
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from typing import Literal
from sqlalchemy import select, func
from backend.database import SessionLocal
from backend.models import AnalysisRun, Project, DocumentFile, DocumentSegment, FactAssertion
from core.workflows.investment import PIPELINE_VERSION, STEPS, run_step

logger = logging.getLogger(__name__)
router = APIRouter(prefix='/api', tags=['Investment workflow'])

class RunCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    mode: Literal['mock'] = 'mock'

def get_db():
    with SessionLocal() as db:
        yield db

def encode(value):
    return json.dumps(value, ensure_ascii=False)

def run_info(run, detail=False):
    result = {'id': run.id, 'project_id': run.project_id, 'mode': run.mode,
        'status': run.status, 'pipeline_version': run.pipeline_version,
        'steps': json.loads(run.steps_json), 'error': run.error,
        'created_at': run.created_at.isoformat(),
        'finished_at': run.finished_at.isoformat() if run.finished_at else None}
    if detail:
        result['report'] = json.loads(run.report_json)
    return result


def input_snapshot(db, project):
    documents = db.scalars(select(DocumentFile).where(DocumentFile.project_id == project.id).order_by(DocumentFile.id)).all()
    total = db.scalar(select(func.count(DocumentSegment.id)).join(DocumentFile, DocumentFile.id == DocumentSegment.document_id).where(DocumentFile.project_id == project.id)) or 0
    if not total:
        raise HTTPException(422, '请先上传并成功解析至少一份有文字的 BP。无需先人工录入或审核字段。')
    rows = db.scalars(select(DocumentSegment).join(DocumentFile, DocumentFile.id == DocumentSegment.document_id).where(DocumentFile.project_id == project.id).order_by(DocumentSegment.id).limit(500)).all()
    sources = []
    size = 0
    for row in rows:
        if size + len(row.content) > 200000:
            break
        sources.append({'id': row.id, 'document_id': row.document_id,
                        'location': row.location, 'content': row.content})
        size += len(row.content)
    facts = []
    records = db.execute(select(FactAssertion, DocumentSegment, DocumentFile)
        .join(DocumentSegment, DocumentSegment.id == FactAssertion.segment_id)
        .join(DocumentFile, DocumentFile.id == FactAssertion.document_id)
        .where(FactAssertion.project_id == project.id, FactAssertion.review_status != 'rejected',
               DocumentFile.project_id == project.id,
               DocumentSegment.document_id == FactAssertion.document_id)
        .order_by(FactAssertion.id)).all()
    for fact, segment, document in records:
        facts.append({'assertion_id': fact.id, 'field_key': fact.field_key, 'value': fact.value_text,
            'origin': fact.origin, 'review_status': fact.review_status,
            'verification_status': 'unverified', 'quote_matches': bool(fact.evidence_quote and fact.evidence_quote in segment.content),
            'evidence': {'document_id': document.id, 'document_name': document.original_name,
                         'segment_id': segment.id, 'location': segment.location, 'quote': fact.evidence_quote}})
    return {'project': {'id': project.id, 'name': project.name},
        'documents': [{'id': d.id, 'filename': d.original_name, 'sha256': d.sha256,
                       'status': d.status, 'segments': d.segment_count, 'warning': d.warning} for d in documents],
        'total_segments': total, 'sources': sources,
        'context_limited': len(sources) < total, 'facts': facts}


def execute_run(run_id):
    with SessionLocal() as db:
        run = db.get(AnalysisRun, run_id)
        if run is None or run.status != 'queued':
            return
        try:
            snapshot = json.loads(run.input_json)
            run.status = 'running'
            db.commit()
            logger.info('Mock analysis started run=%s project=%s', run.id, run.project_id)
            intermediate, steps = {}, []
            for key, title in STEPS:
                steps.append({'key': key, 'title': title, 'status': 'running'})
                run.steps_json = encode(steps)
                db.commit()
                intermediate[key] = run_step(key, snapshot, intermediate)
                steps[-1]['status'] = 'completed'
                run.steps_json = encode(steps)
                db.commit()
            run.report_json = encode(intermediate['report'])
            run.status = 'completed'
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
            logger.info('Mock analysis completed run=%s', run.id)
        except Exception as exc:
            db.rollback()
            run = db.get(AnalysisRun, run_id)
            if run is not None:
                run.status = 'failed'
                run.error = '模拟任务执行失败，请重新发起。错误类型：' + type(exc).__name__
                steps = json.loads(run.steps_json)
                for step in steps:
                    if step['status'] == 'running': step['status'] = 'failed'
                run.steps_json = encode(steps)
                run.finished_at = datetime.now(timezone.utc)
                db.commit()
            # Do not log raw BP text, keys, or exceptions containing payloads.
            logger.error('Mock analysis failed run=%s error_type=%s', run_id, type(exc).__name__)


def recover_interrupted_runs():
    with SessionLocal() as db:
        for run in db.scalars(select(AnalysisRun).where(AnalysisRun.status.in_(['queued', 'running']))):
            run.status = 'failed'
            run.error = '服务曾中断，任务未完成；请重新发起。'
            steps = json.loads(run.steps_json)
            for step in steps:
                if step['status'] == 'running': step['status'] = 'failed'
            run.steps_json = encode(steps)
            run.finished_at = datetime.now(timezone.utc)
        db.commit()


@router.post('/projects/{project_id}/analysis-runs', status_code=202)
def create_run(project_id: int, payload: RunCreate, background_tasks: BackgroundTasks, db=Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, '项目不存在')
    active = db.scalar(select(AnalysisRun).where(AnalysisRun.project_id == project_id, AnalysisRun.status.in_(['queued', 'running'])))
    if active:
        raise HTTPException(409, '该项目已有执行中的任务，请先刷新任务状态。')
    snapshot = input_snapshot(db, project)
    run = AnalysisRun(project_id=project_id, mode='mock', pipeline_version=PIPELINE_VERSION,
                      input_json=encode(snapshot), status='queued')
    db.add(run)
    db.commit()
    db.refresh(run)
    result = run_info(run)
    background_tasks.add_task(execute_run, run.id)
    return result


@router.get('/projects/{project_id}/analysis-runs')
def list_runs(project_id: int, db=Depends(get_db)):
    if not db.get(Project, project_id):
        raise HTTPException(404, '项目不存在')
    runs = db.scalars(select(AnalysisRun).where(AnalysisRun.project_id == project_id).order_by(AnalysisRun.id.desc()).limit(100)).all()
    return [run_info(run) for run in runs]


@router.get('/analysis-runs/{run_id}')
def get_run(run_id: int, db=Depends(get_db)):
    run = db.get(AnalysisRun, run_id)
    if not run:
        raise HTTPException(404, '任务不存在')
    return run_info(run, detail=True)
