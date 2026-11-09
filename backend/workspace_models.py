"""Additive tables: legacy projects and reports are never migrated in place."""
from datetime import datetime, timezone
from sqlalchemy import Boolean, Integer, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


def now():
    return datetime.now(timezone.utc)


class Provider(Base):
    __tablename__ = 'ai_providers'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(200))
    base_url: Mapped[str] = mapped_column(String(500))
    api_kind: Mapped[str] = mapped_column(String(30), default='responses')
    secret: Mapped[str] = mapped_column(Text, default='')
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    max_output_tokens: Mapped[int] = mapped_column(Integer, default=6000)


class ImportReceipt(Base):
    __tablename__ = 'import_receipts'
    request_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    digest: Mapped[str] = mapped_column(String(64))
    project_id: Mapped[int] = mapped_column(Integer)
    document_id: Mapped[int] = mapped_column(Integer)
    name_source: Mapped[str] = mapped_column(String(80))


class AIJob(Base):
    __tablename__ = 'ai_jobs'
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(Integer, index=True)
    request_id: Mapped[str] = mapped_column(String(120), unique=True)
    kind: Mapped[str] = mapped_column(String(20), default='report')
    provider_id: Mapped[int] = mapped_column(Integer)
    provider_json: Mapped[str] = mapped_column(Text)
    input_json: Mapped[str] = mapped_column(Text)
    question: Mapped[str] = mapped_column(Text, default='')
    report_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default='queued')
    result_json: Mapped[str] = mapped_column(Text, default='{}')
    error: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
