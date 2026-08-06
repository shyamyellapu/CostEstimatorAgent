"""Pydantic schemas for authentication endpoints. Never includes hashed_password or raw tokens."""
import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserPublic(BaseModel):
    id: str
    email: str
    username: str
    full_name: str
    role: str
    permissions: list[str]

    model_config = {"from_attributes": True}


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=100)
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    # Accepted for UX (e.g. "I'd like estimator access") but NEVER trusted — the server always
    # assigns settings.default_signup_role. Admin accounts can only be created via the admin API.
    requested_role: Optional[str] = None

    @field_validator("username")
    @classmethod
    def username_format(cls, v: str) -> str:
        if not re.fullmatch(r"[a-zA-Z0-9_.-]+", v):
            raise ValueError("Username may only contain letters, numbers, dots, underscores and hyphens.")
        return v.lower()


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=1, description="Email or username")
    password: str = Field(min_length=1, max_length=128)
    remember_me: bool = False


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserPublic


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class MessageResponse(BaseModel):
    message: str


class SessionOut(BaseModel):
    id: str
    device_name: Optional[str] = None
    browser: Optional[str] = None
    operating_system: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime
    last_activity_at: Optional[datetime] = None
    expires_at: datetime
    is_current: bool = False

    model_config = {"from_attributes": True}
