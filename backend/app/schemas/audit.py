"""Pydantic schemas for the auth-audit-log admin endpoint."""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class AuthAuditLogOut(BaseModel):
    id: str
    user_id: Optional[str] = None
    action: str
    status: str
    ip_address: Optional[str] = None
    request_id: Optional[str] = None
    timestamp: datetime
    metadata_json: Optional[dict[str, Any]] = None

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    items: list[AuthAuditLogOut]
    total: int
    page: int
    page_size: int
