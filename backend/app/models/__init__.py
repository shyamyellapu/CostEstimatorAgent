"""Consolidated SQLAlchemy models for all entities."""
import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    String, Float, Boolean, DateTime, Text, Integer, Enum as SAEnum,
    ForeignKey, Index, Table, Column, UniqueConstraint, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
import enum

from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


def json_type():
    """Return PostgreSQL JSONB for structured application data."""
    return JSONB()


def gen_uuid_obj():
    return uuid.uuid4()


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
    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
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
    company: Mapped[Optional["Company"]] = relationship("Company", back_populates="jobs")

    __table_args__ = (
        Index('idx_job_status_created', 'status', 'created_at'),
        Index('idx_job_client_status', 'client_name', 'status'),
    )


class UploadedFile(Base):
    __tablename__ = "uploaded_files"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    job_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=True, index=True)
    uploaded_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    original_filename: Mapped[str] = mapped_column(String(500))
    stored_filename: Mapped[str] = mapped_column(String(500))
    file_type: Mapped[str] = mapped_column(String(50), default="other", index=True)
    file_origin: Mapped[str] = mapped_column(String(20), default="upload", index=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(200))
    file_size: Mapped[Optional[int]] = mapped_column(Integer)
    storage_path: Mapped[str] = mapped_column(String(1000))
    storage_url: Mapped[Optional[str]] = mapped_column(String(1000))
    storage_provider: Mapped[Optional[str]] = mapped_column(String(50))
    blob_reference: Mapped[Optional[str]] = mapped_column(String(1000))
    checksum_sha256: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    is_processed: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    processing_status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(json_type())
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
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


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=gen_uuid_obj)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    legal_name: Mapped[Optional[str]] = mapped_column(String(255))
    tax_number: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(100))
    website: Mapped[Optional[str]] = mapped_column(String(255))
    address_json: Mapped[Optional[dict]] = mapped_column(json_type())
    settings_json: Mapped[Optional[dict]] = mapped_column(json_type())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=datetime.utcnow)

    jobs: Mapped[List["Job"]] = relationship("Job", back_populates="company")


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=gen_uuid_obj)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=datetime.utcnow)


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=gen_uuid_obj)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", PGUUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", PGUUID(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", PGUUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class AppUser(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=gen_uuid_obj)
    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    profile_settings_json: Mapped[Optional[dict]] = mapped_column(json_type())
    preferences_json: Mapped[Optional[dict]] = mapped_column(json_type())
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=datetime.utcnow)

    roles: Mapped[List["Role"]] = relationship("Role", secondary=user_roles, lazy="selectin")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=gen_uuid_obj)
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    jti: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    device_info_json: Mapped[Optional[dict]] = mapped_column(json_type())
    ip_address: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class LoginHistory(Base):
    __tablename__ = "login_history"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=gen_uuid_obj)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(100))
    user_agent: Mapped[Optional[str]] = mapped_column(String(1000))
    metadata_json: Mapped[Optional[dict]] = mapped_column(json_type())
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=gen_uuid_obj)
    key: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    value_json: Mapped[Optional[dict]] = mapped_column(json_type())
    value_text: Mapped[Optional[str]] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(100), default="general", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=datetime.utcnow)


class UserSetting(Base):
    __tablename__ = "user_settings"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=gen_uuid_obj)
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(200), index=True)
    value_json: Mapped[Optional[dict]] = mapped_column(json_type())
    value_text: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "key", name="uq_user_settings_user_key"),
    )


class AiProcessingLog(Base):
    __tablename__ = "ai_processing_logs"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=gen_uuid_obj)
    job_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=True, index=True)
    file_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("uploaded_files.id", ondelete="SET NULL"), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(50), index=True)
    model: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    operation: Mapped[str] = mapped_column(String(100), index=True)
    prompt_json: Mapped[Optional[dict]] = mapped_column(json_type())
    response_json: Mapped[Optional[dict]] = mapped_column(json_type())
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(30), default="success", index=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    tokens_json: Mapped[Optional[dict]] = mapped_column(json_type())
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
