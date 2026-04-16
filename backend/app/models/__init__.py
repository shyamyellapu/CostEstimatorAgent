"""Consolidated SQLAlchemy models for all entities."""
import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Float, Boolean, DateTime, JSON, Text, Integer, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


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
    client_name: Mapped[Optional[str]] = mapped_column(String(255))
    project_name: Mapped[Optional[str]] = mapped_column(String(500))
    project_ref: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), default="draft")
    currency: Mapped[str] = mapped_column(String(10), default="AED")
    total_weight_kg: Mapped[Optional[float]] = mapped_column(Float)
    total_cost: Mapped[Optional[float]] = mapped_column(Float)
    selling_price: Mapped[Optional[float]] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=datetime.utcnow)

    files: Mapped[List["UploadedFile"]] = relationship("UploadedFile", back_populates="job", cascade="all, delete-orphan")
    extracted_data: Mapped[List["ExtractedData"]] = relationship("ExtractedData", back_populates="job", cascade="all, delete-orphan")
    costing_sheets: Mapped[List["CostingSheet"]] = relationship("CostingSheet", back_populates="job", cascade="all, delete-orphan")
    quotations: Mapped[List["Quotation"]] = relationship("Quotation", back_populates="job", cascade="all, delete-orphan")
    cover_letters: Mapped[List["CoverLetter"]] = relationship("CoverLetter", back_populates="job", cascade="all, delete-orphan")
    audit_logs: Mapped[List["AuditLog"]] = relationship("AuditLog", back_populates="job", cascade="all, delete-orphan")
    chat_history: Mapped[List["ChatHistory"]] = relationship("ChatHistory", back_populates="job", cascade="all, delete-orphan")


class UploadedFile(Base):
    __tablename__ = "uploaded_files"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"))
    original_filename: Mapped[str] = mapped_column(String(500))
    stored_filename: Mapped[str] = mapped_column(String(500))
    file_type: Mapped[str] = mapped_column(String(50), default="other")
    mime_type: Mapped[Optional[str]] = mapped_column(String(200))
    file_size: Mapped[Optional[int]] = mapped_column(Integer)
    storage_path: Mapped[str] = mapped_column(String(1000))
    storage_url: Mapped[Optional[str]] = mapped_column(String(1000))
    is_processed: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    job: Mapped["Job"] = relationship("Job", back_populates="files")


class ExtractedData(Base):
    __tablename__ = "extracted_data"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"))
    file_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("uploaded_files.id", ondelete="SET NULL"), nullable=True)
    data_type: Mapped[str] = mapped_column(String(100))
    extracted_json: Mapped[Optional[dict]] = mapped_column(JSON)
    raw_text: Mapped[Optional[str]] = mapped_column(Text)
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    flags: Mapped[Optional[list]] = mapped_column(JSON)
    extraction_model: Mapped[Optional[str]] = mapped_column(String(100))
    extracted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    job: Mapped["Job"] = relationship("Job", back_populates="extracted_data")


class CostingSheet(Base):
    __tablename__ = "costing_sheets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"))
    line_items_json: Mapped[Optional[list]] = mapped_column(JSON)
    totals_json: Mapped[Optional[dict]] = mapped_column(JSON)
    rates_snapshot_json: Mapped[Optional[dict]] = mapped_column(JSON)
    audit_trail_json: Mapped[Optional[list]] = mapped_column(JSON)
    excel_path: Mapped[Optional[str]] = mapped_column(String(1000))
    excel_url: Mapped[Optional[str]] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    job: Mapped["Job"] = relationship("Job", back_populates="costing_sheets")


class Quotation(Base):
    __tablename__ = "quotations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"))
    file_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("uploaded_files.id", ondelete="SET NULL"), nullable=True)
    client: Mapped[Optional[str]] = mapped_column(String(500))
    reference_number: Mapped[Optional[str]] = mapped_column(String(200))
    project: Mapped[Optional[str]] = mapped_column(String(500))
    subject: Mapped[Optional[str]] = mapped_column(String(500))
    scope: Mapped[Optional[str]] = mapped_column(Text)
    exclusions: Mapped[Optional[list]] = mapped_column(JSON)
    payment_terms: Mapped[Optional[str]] = mapped_column(Text)
    delivery_terms: Mapped[Optional[str]] = mapped_column(Text)
    validity: Mapped[Optional[str]] = mapped_column(String(200))
    commercial_assumptions: Mapped[Optional[list]] = mapped_column(JSON)
    raw_extracted_json: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    job: Mapped["Job"] = relationship("Job", back_populates="quotations")


class CoverLetter(Base):
    __tablename__ = "cover_letters"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"))
    quotation_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("quotations.id", ondelete="SET NULL"), nullable=True)
    content_json: Mapped[Optional[dict]] = mapped_column(JSON)
    pdf_path: Mapped[Optional[str]] = mapped_column(String(1000))
    pdf_url: Mapped[Optional[str]] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    job: Mapped["Job"] = relationship("Job", back_populates="cover_letters")


class RateConfiguration(Base):
    __tablename__ = "rate_configurations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    key: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(500))
    category: Mapped[str] = mapped_column(String(100), default="general")
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[Optional[str]] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=datetime.utcnow)


class ChatHistory(Base):
    __tablename__ = "chat_history"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    job_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    model_used: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    job: Mapped[Optional["Job"]] = relationship("Job", back_populates="chat_history")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    job_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=True)
    action: Mapped[str] = mapped_column(String(200))
    actor: Mapped[str] = mapped_column(String(100), default="system")
    details_json: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    job: Mapped[Optional["Job"]] = relationship("Job", back_populates="audit_logs")
