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
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_ai_provider_created', 'provider', 'created_at'),
        Index('idx_ai_job_created', 'job_id', 'created_at'),
        Index('idx_ai_status_created', 'status', 'created_at'),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# RFQ PLATFORM MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class RFQStatusEnum(str, enum.Enum):
    RECEIVED    = "received"
    CLASSIFYING = "classifying"
    EXTRACTING  = "extracting"
    REVIEW      = "review"
    VALIDATED   = "validated"
    COSTING     = "costing"
    QUOTED      = "quoted"
    CLOSED      = "closed"
    REJECTED    = "rejected"


class GmailCredential(Base):
    """Stores OAuth2 credentials for connected Gmail mailboxes."""
    __tablename__ = "gmail_credentials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    email_address: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255))
    credentials_json: Mapped[Optional[dict]] = mapped_column(json_type())   # OAuth2 token dict
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_synced: Mapped[Optional[datetime]] = mapped_column(DateTime)
    sync_history_id: Mapped[Optional[str]] = mapped_column(String(100))    # Gmail historyId for incremental sync
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=datetime.utcnow)

    emails: Mapped[List["RFQEmail"]] = relationship("RFQEmail", back_populates="mailbox_credential", lazy="select")

    __table_args__ = (
        Index('idx_gmail_active', 'is_active'),
    )


class RFQEmail(Base):
    """An email fetched from Gmail that may contain an RFQ."""
    __tablename__ = "rfq_emails"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    gmail_message_id: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    gmail_thread_id: Mapped[Optional[str]] = mapped_column(String(200), index=True)
    mailbox_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("gmail_credentials.id", ondelete="SET NULL"), nullable=True, index=True)
    mailbox_email: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    subject: Mapped[Optional[str]] = mapped_column(String(1000))
    sender_email: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    sender_name: Mapped[Optional[str]] = mapped_column(String(500))
    recipients: Mapped[Optional[list]] = mapped_column(json_type())
    body_text: Mapped[Optional[str]] = mapped_column(Text)
    body_html: Mapped[Optional[str]] = mapped_column(Text)
    received_at: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)
    labels: Mapped[Optional[list]] = mapped_column(json_type())
    email_type: Mapped[str] = mapped_column(String(50), default="unknown", index=True)  # rfq, revision, clarification, other
    rfq_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("rfq_records.id", ondelete="SET NULL"), nullable=True, index=True)
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    mailbox_credential: Mapped[Optional["GmailCredential"]] = relationship("GmailCredential", back_populates="emails")
    attachments: Mapped[List["RFQAttachment"]] = relationship("RFQAttachment", back_populates="email", lazy="selectin")
    rfq: Mapped[Optional["RFQRecord"]] = relationship("RFQRecord", back_populates="emails", foreign_keys=[rfq_id])

    __table_args__ = (
        Index('idx_rfqemail_type_processed', 'email_type', 'is_processed'),
        Index('idx_rfqemail_received', 'received_at'),
    )


class RFQAttachment(Base):
    """A file attachment associated with an RFQ (from email or direct upload)."""
    __tablename__ = "rfq_attachments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    email_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("rfq_emails.id", ondelete="SET NULL"), nullable=True, index=True)
    rfq_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("rfq_records.id", ondelete="CASCADE"), nullable=True, index=True)
    gmail_attachment_id: Mapped[Optional[str]] = mapped_column(String(500))
    original_filename: Mapped[str] = mapped_column(String(500))
    stored_filename: Mapped[Optional[str]] = mapped_column(String(500))
    mime_type: Mapped[Optional[str]] = mapped_column(String(200))
    file_size: Mapped[Optional[int]] = mapped_column(Integer)
    storage_path: Mapped[Optional[str]] = mapped_column(String(1000))
    storage_url: Mapped[Optional[str]] = mapped_column(String(1000))
    # Classification
    file_category: Mapped[str] = mapped_column(String(50), default="other", index=True)  # pdf, excel, word, dwg, zip, image
    document_type: Mapped[str] = mapped_column(String(100), default="unknown", index=True)  # bom, datasheet, pid, ga_drawing, isometric, specification, rfq
    revision_number: Mapped[Optional[str]] = mapped_column(String(50))
    document_number: Mapped[Optional[str]] = mapped_column(String(200))
    classification_confidence: Mapped[Optional[float]] = mapped_column(Float)
    classification_metadata: Mapped[Optional[dict]] = mapped_column(json_type())
    # Processing
    extraction_status: Mapped[str] = mapped_column(String(50), default="pending", index=True)  # pending, running, completed, failed
    extraction_error: Mapped[Optional[str]] = mapped_column(Text)
    extracted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    email: Mapped[Optional["RFQEmail"]] = relationship("RFQEmail", back_populates="attachments")
    rfq: Mapped[Optional["RFQRecord"]] = relationship("RFQRecord", back_populates="attachments", foreign_keys=[rfq_id])
    line_items: Mapped[List["RFQLineItem"]] = relationship("RFQLineItem", back_populates="source_attachment", lazy="select")

    __table_args__ = (
        Index('idx_rfqatt_rfq_type', 'rfq_id', 'document_type'),
        Index('idx_rfqatt_extraction', 'extraction_status'),
    )


class RFQRecord(Base):
    """Central RFQ object — created from email, upload, or manual entry."""
    __tablename__ = "rfq_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    rfq_number: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    client_name: Mapped[Optional[str]] = mapped_column(String(500), index=True)
    client_email: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    project_name: Mapped[Optional[str]] = mapped_column(String(500))
    project_reference: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    enquiry_date: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime)
    subject: Mapped[Optional[str]] = mapped_column(String(1000))
    scope_summary: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="received", index=True)
    priority: Mapped[str] = mapped_column(String(20), default="normal", index=True)  # low, normal, high, urgent
    revision_number: Mapped[int] = mapped_column(Integer, default=0)
    parent_rfq_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("rfq_records.id", ondelete="SET NULL"), nullable=True, index=True)
    job_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(50), default="upload", index=True)  # gmail, upload, manual
    assigned_to: Mapped[Optional[str]] = mapped_column(String(255))
    tags: Mapped[Optional[list]] = mapped_column(json_type())
    extra_metadata: Mapped[Optional[dict]] = mapped_column("metadata", json_type())
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=datetime.utcnow)

    emails: Mapped[List["RFQEmail"]] = relationship("RFQEmail", back_populates="rfq", foreign_keys="RFQEmail.rfq_id", lazy="select")
    attachments: Mapped[List["RFQAttachment"]] = relationship("RFQAttachment", back_populates="rfq", foreign_keys="RFQAttachment.rfq_id", lazy="selectin")
    line_items: Mapped[List["RFQLineItem"]] = relationship("RFQLineItem", back_populates="rfq", cascade="all, delete-orphan", lazy="selectin")
    validation_results: Mapped[List["ValidationResult"]] = relationship("ValidationResult", back_populates="rfq", cascade="all, delete-orphan", lazy="select")
    extraction_reviews: Mapped[List["ExtractionReview"]] = relationship("ExtractionReview", back_populates="rfq", cascade="all, delete-orphan", lazy="select")
    revisions: Mapped[List["RFQRecord"]] = relationship("RFQRecord", foreign_keys=[parent_rfq_id], lazy="select")

    __table_args__ = (
        Index('idx_rfq_status_created', 'status', 'created_at'),
        Index('idx_rfq_client_status', 'client_name', 'status'),
        Index('idx_rfq_enquiry', 'enquiry_date'),
    )


class RFQLineItem(Base):
    """A single line item extracted from an RFQ (BOM row, specification item, etc.)."""
    __tablename__ = "rfq_line_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    rfq_id: Mapped[str] = mapped_column(String(36), ForeignKey("rfq_records.id", ondelete="CASCADE"), index=True)
    source_attachment_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("rfq_attachments.id", ondelete="SET NULL"), nullable=True, index=True)
    line_number: Mapped[Optional[str]] = mapped_column(String(50))
    tag_number: Mapped[Optional[str]] = mapped_column(String(200), index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    material: Mapped[Optional[str]] = mapped_column(String(500), index=True)
    material_grade: Mapped[Optional[str]] = mapped_column(String(200))
    material_standard: Mapped[Optional[str]] = mapped_column(String(200))  # ASTM A106, EN 10216, etc.
    quantity: Mapped[Optional[float]] = mapped_column(Float)
    unit: Mapped[Optional[str]] = mapped_column(String(50))
    weight_each_kg: Mapped[Optional[float]] = mapped_column(Float)
    total_weight_kg: Mapped[Optional[float]] = mapped_column(Float)
    dimensions: Mapped[Optional[dict]] = mapped_column(json_type())   # {length, width, height, diameter, thickness, etc.}
    pressure_class: Mapped[Optional[str]] = mapped_column(String(100))
    surface_treatment: Mapped[Optional[str]] = mapped_column(String(200))
    drawing_reference: Mapped[Optional[str]] = mapped_column(String(500))
    remarks: Mapped[Optional[str]] = mapped_column(Text)
    # Validation & confidence
    confidence_score: Mapped[Optional[float]] = mapped_column(Float)
    validation_flags: Mapped[Optional[list]] = mapped_column(json_type())
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    confirmed_by: Mapped[Optional[str]] = mapped_column(String(255))
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    raw_extracted: Mapped[Optional[dict]] = mapped_column(json_type())
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=datetime.utcnow)

    rfq: Mapped["RFQRecord"] = relationship("RFQRecord", back_populates="line_items")
    source_attachment: Mapped[Optional["RFQAttachment"]] = relationship("RFQAttachment", back_populates="line_items")

    __table_args__ = (
        Index('idx_lineitem_rfq_confirmed', 'rfq_id', 'is_confirmed'),
        Index('idx_lineitem_material', 'material'),
    )


class ValidationResult(Base):
    """A single validation finding for an RFQ."""
    __tablename__ = "validation_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    rfq_id: Mapped[str] = mapped_column(String(36), ForeignKey("rfq_records.id", ondelete="CASCADE"), index=True)
    line_item_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("rfq_line_items.id", ondelete="SET NULL"), nullable=True, index=True)
    attachment_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("rfq_attachments.id", ondelete="SET NULL"), nullable=True, index=True)
    validation_type: Mapped[str] = mapped_column(String(100), index=True)  # quantity, unit, material, dimension, duplicate, scope, revision
    severity: Mapped[str] = mapped_column(String(20), default="warning", index=True)  # error, warning, info
    message: Mapped[str] = mapped_column(Text)
    field_name: Mapped[Optional[str]] = mapped_column(String(200))
    extracted_value: Mapped[Optional[str]] = mapped_column(String(500))
    suggested_value: Mapped[Optional[str]] = mapped_column(String(500))
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(255))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    resolution_note: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    rfq: Mapped["RFQRecord"] = relationship("RFQRecord", back_populates="validation_results")

    __table_args__ = (
        Index('idx_validation_rfq_severity', 'rfq_id', 'severity'),
        Index('idx_validation_resolved', 'is_resolved'),
    )


class ExtractionReview(Base):
    """Human review record for an RFQ extraction."""
    __tablename__ = "extraction_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    rfq_id: Mapped[str] = mapped_column(String(36), ForeignKey("rfq_records.id", ondelete="CASCADE"), index=True)
    attachment_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("rfq_attachments.id", ondelete="SET NULL"), nullable=True, index=True)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(255))
    review_status: Mapped[str] = mapped_column(String(50), default="pending", index=True)  # pending, in_review, approved, rejected
    changes_made: Mapped[Optional[list]] = mapped_column(json_type())
    notes: Mapped[Optional[str]] = mapped_column(Text)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    rfq: Mapped["RFQRecord"] = relationship("RFQRecord", back_populates="extraction_reviews")

    __table_args__ = (
        Index('idx_review_rfq_status', 'rfq_id', 'review_status'),
    )


class TaskQueue(Base):
    """Persistent async task queue backed by the database."""
    __tablename__ = "task_queue"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    task_type: Mapped[str] = mapped_column(String(100), index=True)  # classify_attachment, extract_rfq, validate_rfq, sync_gmail
    entity_type: Mapped[Optional[str]] = mapped_column(String(50))    # rfq, attachment, email, mailbox
    entity_id: Mapped[Optional[str]] = mapped_column(String(36), index=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)  # pending, running, completed, failed, retrying
    priority: Mapped[int] = mapped_column(Integer, default=5, index=True)  # 1=highest, 10=lowest
    payload: Mapped[Optional[dict]] = mapped_column(json_type())
    result: Mapped[Optional[dict]] = mapped_column(json_type())
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index('idx_task_status_priority', 'status', 'priority'),
        Index('idx_task_entity', 'entity_type', 'entity_id'),
        Index('idx_task_type_status', 'task_type', 'status'),
    )


class MaterialMaster(Base):
    """Engineering material master database."""
    __tablename__ = "material_master"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(500), index=True)
    category: Mapped[str] = mapped_column(String(100), default="steel", index=True)  # steel, stainless, alloy, etc.
    grade_standard: Mapped[Optional[str]] = mapped_column(String(100))   # ASTM, EN, IS, DIN
    grade_code: Mapped[Optional[str]] = mapped_column(String(100), index=True)       # A106, 316L, P91, etc.
    density_kg_m3: Mapped[Optional[float]] = mapped_column(Float)
    unit_cost_per_kg: Mapped[Optional[float]] = mapped_column(Float)
    aliases: Mapped[Optional[list]] = mapped_column(json_type())          # normalised alternate names
    properties: Mapped[Optional[dict]] = mapped_column(json_type())       # UTS, yield, temp limits, etc.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_material_category_active', 'category', 'is_active'),
        Index('idx_material_grade', 'grade_standard', 'grade_code'),
    )
