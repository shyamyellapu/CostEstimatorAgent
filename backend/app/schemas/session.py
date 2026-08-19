"""Pydantic schemas for admin session-management endpoints."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AdminSessionOut(BaseModel):
    id: str
    user_id: str
    user_email: Optional[str] = None
    device_name: Optional[str] = None
    browser: Optional[str] = None
    operating_system: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime
    last_activity_at: Optional[datetime] = None
    expires_at: datetime

    model_config = {"from_attributes": True}
