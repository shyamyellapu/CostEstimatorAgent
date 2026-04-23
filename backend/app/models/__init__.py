"""Consolidated SQLAlchemy models for all entities."""
import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Float, Boolean, DateTime, JSON, Text, Integer, Enum as SAEnum, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
import enum

from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


def json_type():
    """Return JSONB for PostgreSQL, JSON for others (SQLite)."""
    return JSONB().with_variant(JSON(), 'sqlite')


# ─── Enums ────────────────────────────────────────────────────────────────────

class JobStatus(str, enum.Enum):
    DRAFT = "draft"
    EXTRACTING = "extracting"
    PENDING_CONFIRMATION = "pending_confirmation"
    CALCULATING = "calculating"
    COMPLETED = "completed"
    FAILED = "failed"


class FileTypeEnum(str, enum.Enum):
    PDF = "pdf"
    IMAGE = "image"
    EXCEL = "excel"
    DOCX = "docx"
    QUOTATION = "quotation"
    OTHER = "other"


# ─── Models ───────────────────────────────────────────────────────────────────

class Job(Base):
    __tablename__ = "jobs"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    job_number: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    client_name: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    project_name: Mapped[Optional[str]] = mapped_column(String(500))
    project_ref: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), default="draft", index=True)
    currency: Mapped[str] = mapped_column(String(10), default="AED")
    total_weight_kg: Mapped[Optional[float]] = mapped_column(Float)
    total_cost: Mapped[Optional[float]] = mapped_column(Float)
    selling_price: Mapped[Optional[float]] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=datetime.utcnow)

    # Relationships
    files: Mapped[List["UploadedFile"]] = relationship("UploadedFile", back_populates="job", cascade="all, delete-orphan", lazy="selectin")
    extracted_data: Mapped[List["ExtractedData"]] = relationship("ExtractedData", back_populates="job", cascade="all, delete-orphan", lazy="selectin")
    costing_sheets: Mapped[List["CostingSheet"]] = relationship("CostingSheet", back_populates="job", cascade="all, delete-orphan", lazy="selectin")
    quotations: Mapped[List["Quotation"]] = relationship("Quotation", back_populates="job", cascade="all, delete-orphan", lazy="selectin")
    cover_letters: Mapped[List["CoverLetter"]] = relationship("CoverLetter", back_populates="job", cascade="all, delete-orphan", lazy="selectin")
    audit_logs: Mapped[List["AuditLog"]] = relationship("AuditLog", back_populates="job", cascade="all, delete-orphan", lazy="select")
    chat_history: Mapped[List["ChatHistory"]] = relationship("ChatHistory", back_populates="job", cascade="all, delete-orphan", lazy="select")

    __table_args__ = (
        Index('idx_job_status_created', 'status', 'created_at'),
        Index('idx_job_client_status', 'client_name', 'status'),
    )


class UploadedFile(Base):
    __tablename__ = "uploaded_files"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    original_filename: Mapped[str] = mapped_column(String(500))
    stored_filename: Mapped[str] = mapped_column(String(500))
    file_type: Mapped[str] = mapped_column(String(50), default="other", index=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(200))
    file_size: Mapped[Optional[int]] = mapped_column(Integer)
    storage_path: Mapped[str] = mapped_column(String(1000))
    storage_url: Mapped[Optional[str]] = mapped_column(String(1000))
    is_processed: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    
    job: Mapped["Job"] = relationship("Job", back_populates="files")

    __table_args__ = (
        Index('idx_file_job_type', 'job_id', 'file_type'),
        Index('idx_file_processed', 'is_processed', 'created_at'),
    )


class ExtractedData(Base):
    __tablename__ = "extracted_data"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    file_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("uploaded_files.id", ondelete="SET NULL"), nullable=True, index=True)
    data_type: Mapped[str] = mapped_column(String(100), index=True)
    extracted_json: Mapped[Optional[dict]] = mapped_column(json_type())
    raw_text: Mapped[Optional[str]] = mapped_column(Text)
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    flags: Mapped[Optional[list]] = mapped_column(json_type())
    extraction_model: Mapped[Optional[str]] = mapped_column(String(100))
    extracted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    
    job: Mapped["Job"] = relationship("Job", back_populates="extracted_data")

    __table_args__ = (
        Index('idx_extracted_job_type', 'job_id', 'data_type'),
        Index('idx_extracted_confirmed', 'is_confirmed', 'extracted_at'),
    )


class CostingSheet(Base):
    __tablename__ = "costing_sheets"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    line_items_json: Mapped[Optional[list]] = mapped_column(json_type())
    totals_json: Mapped[Optional[dict]] = mapped_column(json_type())
    rates_snapshot_json: Mapped[Optional[dict]] = mapped_column(json_type())
    audit_trail_json: Mapped[Optional[list]] = mapped_column(json_type())
    excel_path: Mapped[Optional[str]] = mapped_column(String(1000))
    excel_url: Mapped[Optional[str]] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    
    job: Mapped["Job"] = relationship("Job", back_populates="costing_sheets")

    __table_args__ = (
        Index('idx_costing_job_created', 'job_id', 'created_at'),
    )


class Quotation(Base):
    __tablename__ = "quotations"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    file_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("uploaded_files.id", ondelete="SET NULL"), nullable=True, index=True)
    client: Mapped[Optional[str]] = mapped_column(String(500))
    reference_number: Mapped[Optional[str]] = mapped_column(String(200), index=True)
    project: Mapped[Optional[str]] = mapped_column(String(500))
    subject: Mapped[Optional[str]] = mapped_column(String(500))
    scope: Mapped[Optional[str]] = mapped_column(Text)
    exclusions: Mapped[Optional[list]] = mapped_column(json_type())
    payment_terms: Mapped[Optional[str]] = mapped_column(Text)
    delivery_terms: Mapped[Optional[str]] = mapped_column(Text)
    validity: Mapped[Optional[str]] = mapped_column(String(200))
    commercial_assumptions: Mapped[Optional[list]] = mapped_column(json_type())
    raw_extracted_json: Mapped[Optional[dict]] = mapped_column(json_type())
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    
    job: Mapped["Job"] = relationship("Job", back_populates="quotations")

    __table_args__ = (
        Index('idx_quotation_job_created', 'job_id', 'created_at'),
    )


class CoverLetter(Base):
    __tablename__ = "cover_letters"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    quotation_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("quotations.id", ondelete="SET NULL"), nullable=True, index=True)
    content_json: Mapped[Optional[dict]] = mapped_column(json_type())
    pdf_path: Mapped[Optional[str]] = mapped_column(String(1000))
    pdf_url: Mapped[Optional[str]] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    
    job: Mapped["Job"] = relationship("Job", back_populates="cover_letters")

    __table_args__ = (
        Index('idx_cover_job_created', 'job_id', 'created_at'),
    )


class RateConfiguration(Base):
    __tablename__ = "rate_configurations"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    key: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(500))
    category: Mapped[str] = mapped_column(String(100), default="general", index=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[Optional[str]] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_rate_category_active', 'category', 'is_active'),
    )


class ChatHistory(Base):
    __tablename__ = "chat_history"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    job_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=True, index=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    model_used: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    
    job: Mapped[Optional["Job"]] = relationship("Job", back_populates="chat_history")

    __table_args__ = (
        Index('idx_chat_session_created', 'session_id', 'created_at'),
        Index('idx_chat_job_created', 'job_id', 'created_at'),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    job_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(200), index=True)
    actor: Mapped[str] = mapped_column(String(100), default="system", index=True)
    details_json: Mapped[Optional[dict]] = mapped_column(json_type())
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    
    job: Mapped[Optional["Job"]] = relationship("Job", back_populates="audit_logs")

    __table_args__ = (
        Index('idx_audit_action_created', 'action', 'created_at'),
        Index('idx_audit_actor_created', 'actor', 'created_at'),
        Index('idx_audit_job_created', 'job_id', 'created_at'),
    )
