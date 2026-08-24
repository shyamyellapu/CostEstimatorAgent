"""Pydantic schemas for admin user-management endpoints."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserAdminOut(BaseModel):
    id: str
    email: str
    username: str
    full_name: str
    role: Optional[str] = None
    is_active: bool
    is_verified: bool
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    items: list[UserAdminOut]
    total: int
    page: int
    page_size: int


class CreateUserRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=100)
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(description="admin | manager | estimator | user")


class UpdateUserRequest(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=255)


class AssignRoleRequest(BaseModel):
    role: str


class SetStatusRequest(BaseModel):
    is_active: bool


class RoleOut(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    is_system_role: bool

    model_config = {"from_attributes": True}


class PermissionOut(BaseModel):
    id: str
    code: str
    name: str
    resource: Optional[str] = None
    action: Optional[str] = None

    model_config = {"from_attributes": True}
