from datetime import datetime, timezone
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base

class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class DocumentFile(Base):
    __tablename__ = "document_files"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    original_name: Mapped[str] = mapped_column(String(260), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(300), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    bytes_size: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="processed")
    segment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warning: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class DocumentSegment(Base):
    __tablename__ = "document_segments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    location: Mapped[str] = mapped_column(String(300), nullable=False)
    content: Mapped[str] = mapped_column(String(12000), nullable=False)


# M04-A: assertion records are separate from original document segments.
from sqlalchemy import ForeignKey, Text
class FactAssertion(Base):
    __tablename__ = "fact_assertions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True, nullable=False)
    document_id: Mapped[int] = mapped_column(ForeignKey("document_files.id"), nullable=False)
    segment_id: Mapped[int] = mapped_column(ForeignKey("document_segments.id"), nullable=False)
    field_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    value_text: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_quote: Mapped[str] = mapped_column(Text, nullable=False)
    origin: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    review_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    evidence_grade: Mapped[str] = mapped_column(String(3), nullable=False, default="A")
    reviewer_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AnalysisRun(Base):
    __tablename__ = 'analysis_runs'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True, nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default='mock')
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='queued')
    pipeline_version: Mapped[str] = mapped_column(String(80), nullable=False)
    input_json: Mapped[str] = mapped_column(Text, nullable=False)
    steps_json: Mapped[str] = mapped_column(Text, nullable=False, default='[]')
    report_json: Mapped[str] = mapped_column(Text, nullable=False, default='{}')
    error: Mapped[str] = mapped_column(Text, nullable=False, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
