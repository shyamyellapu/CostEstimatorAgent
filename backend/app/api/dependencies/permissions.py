"""RBAC dependency factories: require_role / require_any_role / require_permission /
require_all_permissions / require_any_permission.

Backend authorization is mandatory — the frontend hiding a button is a UX nicety only.
"""
from fastapi import Depends

from app.api.dependencies.auth import AuthContext, get_current_user
from app.auth.permissions import has_all_permissions, has_any_permission, has_any_role, has_permission
from app.core.exceptions import permission_denied


def require_role(role: str):
    async def _dep(ctx: AuthContext = Depends(get_current_user)) -> AuthContext:
        if ctx.role != role:
            raise permission_denied()
        return ctx
    return _dep


def require_any_role(*roles: str):
    async def _dep(ctx: AuthContext = Depends(get_current_user)) -> AuthContext:
        if not has_any_role(ctx.role, list(roles)):
            raise permission_denied()
        return ctx
    return _dep


def require_permission(code: str):
    async def _dep(ctx: AuthContext = Depends(get_current_user)) -> AuthContext:
        if not has_permission(ctx.permissions, code):
            raise permission_denied()
        return ctx
    return _dep


def require_any_permission(*codes: str):
    async def _dep(ctx: AuthContext = Depends(get_current_user)) -> AuthContext:
        if not has_any_permission(ctx.permissions, list(codes)):
            raise permission_denied()
        return ctx
    return _dep


def require_all_permissions(*codes: str):
    async def _dep(ctx: AuthContext = Depends(get_current_user)) -> AuthContext:
        if not has_all_permissions(ctx.permissions, list(codes)):
            raise permission_denied()
        return ctx
    return _dep
