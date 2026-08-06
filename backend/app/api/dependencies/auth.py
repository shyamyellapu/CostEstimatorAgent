"""FastAPI dependencies that authenticate the caller from the access-token JWT.

Reusable across every protected route in the application:

    @router.get("/costing/projects", dependencies=[Depends(require_permission("estimates.read"))])
    async def list_projects(ctx: AuthContext = Depends(get_current_user)): ...
"""
from dataclasses import dataclass

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import decode_access_token
from app.core.exceptions import account_disabled, session_revoked, token_invalid
from app.database import get_db
from app.models import User
from app.services import session_service

# `auto_error=False` lets us raise our own consistent AUTH_TOKEN_INVALID error instead of FastAPI's
# default 403 "Not authenticated". Declaring this scheme is also what makes the Swagger UI
# "Authorize" button appear for every endpoint that depends on get_current_user.
_bearer_scheme = HTTPBearer(auto_error=False, description="Access token issued by POST /api/auth/login")


@dataclass
class AuthContext:
    """Everything a route needs about the authenticated caller, derived from the access token."""
    user: User
    role: str
    permissions: list[str]
    session_id: str


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> AuthContext:
    if credentials is None or not credentials.credentials:
        raise token_invalid()
    payload = decode_access_token(credentials.credentials)

    user_id = payload["sub"]
    session_id = payload.get("session_id")

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise token_invalid()
    if not user.is_active:
        raise account_disabled()

    # Reject tokens belonging to a session that has since been revoked (logout / logout-all /
    # admin session revocation / replay detection all mark the session inactive immediately).
    if session_id:
        session = await session_service.get_active_session(db, session_id)
        if session is None:
            raise session_revoked()

    return AuthContext(
        user=user,
        role=payload.get("role", "user"),
        permissions=payload.get("permissions", []),
        session_id=session_id,
    )


async def get_current_active_user(ctx: AuthContext = Depends(get_current_user)) -> AuthContext:
    # is_active is already enforced in get_current_user; kept as a distinct dependency name for
    # readability at call sites and to match the required dependency surface.
    return ctx
