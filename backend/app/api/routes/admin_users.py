"""Admin-only user administration endpoints. All require an authenticated admin-permission caller."""
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import AuthContext, get_current_user
from app.api.dependencies.permissions import require_permission
from app.auth.csrf import verify_csrf
from app.core.exceptions import AppError
from app.database import get_db
from app.models import Permission, Role
from app.schemas.user import (
    AssignRoleRequest, CreateUserRequest, PermissionOut, RoleOut, SetStatusRequest,
    UpdateUserRequest, UserAdminOut, UserListResponse,
)
from app.services import user_service

router = APIRouter()


def _client_ip(request: Request) -> Optional[str]:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def _to_admin_out(user) -> UserAdminOut:
    return UserAdminOut(
        id=str(user.id), email=user.email, username=user.username, full_name=user.full_name,
        role=user.role.name if user.role else None, is_active=user.is_active, is_verified=user.is_verified,
        last_login=user.last_login, created_at=user.created_at, updated_at=user.updated_at,
    )


@router.get("/users", response_model=UserListResponse, dependencies=[Depends(require_permission("users.read"))])
async def list_users(
    db: AsyncSession = Depends(get_db),
    search: Optional[str] = Query(default=None),
    role: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    users, total = await user_service.list_users(
        db, search=search, role_name=role, is_active=is_active, page=page, page_size=page_size
    )
    return UserListResponse(items=[_to_admin_out(u) for u in users], total=total, page=page, page_size=page_size)


@router.get("/users/{user_id}", response_model=UserAdminOut, dependencies=[Depends(require_permission("users.read"))])
async def get_user(user_id: str, db: AsyncSession = Depends(get_db)):
    user = await user_service.get_user(db, user_id)
    if user is None:
        raise AppError("NOT_FOUND", "User not found.", 404)
    return _to_admin_out(user)


@router.post(
    "/users", response_model=UserAdminOut, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("users.create"))],
)
async def create_user(
    body: CreateUserRequest, request: Request, db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_current_user),
):
    verify_csrf(request)
    user = await user_service.create_user(
        db, email=body.email, username=body.username, full_name=body.full_name, password=body.password,
        role_name=body.role, actor_id=str(ctx.user.id), ip_address=_client_ip(request),
        user_agent=request.headers.get("User-Agent"), request_id=getattr(request.state, "request_id", None),
    )
    return _to_admin_out(user)


@router.patch("/users/{user_id}", response_model=UserAdminOut, dependencies=[Depends(require_permission("users.update"))])
async def update_user(user_id: str, body: UpdateUserRequest, request: Request, db: AsyncSession = Depends(get_db)):
    verify_csrf(request)
    user = await user_service.get_user(db, user_id)
    if user is None:
        raise AppError("NOT_FOUND", "User not found.", 404)
    user = await user_service.update_user(db, user=user, full_name=body.full_name)
    return _to_admin_out(user)


@router.patch(
    "/users/{user_id}/role", response_model=UserAdminOut,
    dependencies=[Depends(require_permission("users.assign_role"))],
)
async def assign_role(
    user_id: str, body: AssignRoleRequest, request: Request, db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_current_user),
):
    verify_csrf(request)
    user = await user_service.get_user(db, user_id)
    if user is None:
        raise AppError("NOT_FOUND", "User not found.", 404)
    user = await user_service.assign_role(
        db, user=user, role_name=body.role, actor_id=str(ctx.user.id), actor_role_name=ctx.role,
        ip_address=_client_ip(request), user_agent=request.headers.get("User-Agent"),
        request_id=getattr(request.state, "request_id", None),
    )
    return _to_admin_out(user)


@router.patch(
    "/users/{user_id}/status", response_model=UserAdminOut,
    dependencies=[Depends(require_permission("users.disable"))],
)
async def set_user_status(
    user_id: str, body: SetStatusRequest, request: Request, db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_current_user),
):
    verify_csrf(request)
    user = await user_service.get_user(db, user_id)
    if user is None:
        raise AppError("NOT_FOUND", "User not found.", 404)
    user = await user_service.set_user_status(
        db, user=user, is_active=body.is_active, actor_id=str(ctx.user.id), actor_role_name=ctx.role,
        ip_address=_client_ip(request), user_agent=request.headers.get("User-Agent"),
        request_id=getattr(request.state, "request_id", None),
    )
    return _to_admin_out(user)


@router.get("/roles", response_model=list[RoleOut], dependencies=[Depends(require_permission("users.read"))])
async def list_roles(db: AsyncSession = Depends(get_db)):
    roles = (await db.execute(select(Role).order_by(Role.name))).scalars().all()
    return [RoleOut(id=str(r.id), name=r.name, description=r.description, is_system_role=r.is_system_role) for r in roles]


@router.get("/permissions", response_model=list[PermissionOut], dependencies=[Depends(require_permission("users.read"))])
async def list_permissions(db: AsyncSession = Depends(get_db)):
    permissions = (await db.execute(select(Permission).order_by(Permission.code))).scalars().all()
    return [
        PermissionOut(id=str(p.id), code=p.code, name=p.name, resource=p.resource, action=p.action)
        for p in permissions
    ]
