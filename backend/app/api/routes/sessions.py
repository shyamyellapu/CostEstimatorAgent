"""Admin-only session visibility and revocation across all users."""
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import AuthContext, get_current_user
from app.api.dependencies.permissions import require_permission
from app.auth.csrf import verify_csrf
from app.core.exceptions import AppError
from app.database import get_db
from app.models import User, UserSession
from app.schemas.session import AdminSessionOut
from app.services import auth_audit_service, session_service, token_service

router = APIRouter()


@router.get("/sessions", response_model=list[AdminSessionOut], dependencies=[Depends(require_permission("sessions.read"))])
async def list_all_sessions(
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
):
    query = (
        select(UserSession, User.email)
        .join(User, User.id == UserSession.user_id)
        .where(UserSession.is_active.is_(True))
        .order_by(UserSession.last_activity_at.desc().nullslast())
        .limit(limit)
    )
    if user_id:
        query = query.where(UserSession.user_id == user_id)

    rows = (await db.execute(query)).all()
    return [
        AdminSessionOut(
            id=str(s.id), user_id=str(s.user_id), user_email=email, device_name=s.device_name,
            browser=s.browser, operating_system=s.operating_system, ip_address=s.ip_address,
            created_at=s.created_at, last_activity_at=s.last_activity_at, expires_at=s.expires_at,
        )
        for s, email in rows
    ]


@router.delete("/sessions/{session_id}", status_code=204, dependencies=[Depends(require_permission("sessions.revoke"))])
async def revoke_session(
    session_id: str, request: Request, db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_current_user),
):
    verify_csrf(request)
    session = (await db.execute(select(UserSession).where(UserSession.id == session_id))).scalar_one_or_none()
    if session is None:
        raise AppError("NOT_FOUND", "Session not found.", 404)

    await session_service.revoke_session(db, session_id, reason="admin_revoked")
    await token_service.revoke_tokens_for_session(db, session_id, reason="admin_revoked")
    await auth_audit_service.log_event(
        db, action=auth_audit_service.ACTION_SESSION_REVOKED, status="success", user_id=str(ctx.user.id),
        ip_address=request.client.host if request.client else None, user_agent=request.headers.get("User-Agent"),
        request_id=getattr(request.state, "request_id", None),
        metadata={"target_session_id": session_id, "target_user_id": str(session.user_id), "by": "admin"},
    )
    await db.commit()
