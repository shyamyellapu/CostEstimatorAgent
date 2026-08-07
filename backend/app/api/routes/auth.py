"""Authentication endpoints: register, login, refresh, logout, me, change-password, password reset,
and self-service session management.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import AuthContext, get_current_user
from app.auth.cookies import clear_auth_cookies, set_auth_cookies
from app.auth.csrf import verify_csrf
from app.config import settings
from app.core.exceptions import AppError, refresh_invalid
from app.core.rate_limit import enforce_rate_limit
from app.database import get_db
from app.models import User, UserSession
from app.schemas.auth import (
    ChangePasswordRequest, ForgotPasswordRequest, LoginRequest, LoginResponse, MessageResponse,
    RegisterRequest, ResetPasswordRequest, SessionOut, UserPublic,
)
from app.services import auth_audit_service, auth_service, password_reset_service, session_service, token_service

router = APIRouter()


def _client_ip(request: Request) -> Optional[str]:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def _request_id(request: Request) -> Optional[str]:
    return getattr(request.state, "request_id", None)


def _to_public(user: User) -> UserPublic:
    return UserPublic(
        id=str(user.id),
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        role=user.role.name if user.role else "user",
        permissions=[p.code for p in user.role.permissions] if user.role else [],
    )


async def _issue_login_session(
    db: AsyncSession, response: Response, user: User, request: Request,
) -> LoginResponse:
    ip = _client_ip(request)
    ua = request.headers.get("User-Agent")

    session = await session_service.create_session(db, user_id=str(user.id), ip_address=ip, user_agent=ua)
    raw_refresh, _row = await token_service.issue_refresh_token(
        db, user_id=str(user.id), session_id=str(session.id), ip_address=ip, user_agent=ua,
    )
    session.current_refresh_token_id = _row.id
    access_token, expires_in = token_service.issue_access_token(user, str(session.id))

    await db.commit()

    csrf_token = set_auth_cookies(response, refresh_token=raw_refresh)
    return LoginResponse(access_token=access_token, expires_in=expires_in, user=_to_public(user), csrf_token=csrf_token)


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    # TEMP: rate limit disabled for local dev testing — re-enable before shipping.
    # await enforce_rate_limit(f"register:{_client_ip(request)}", limit=3, window_seconds=3600)
    user = await auth_service.register_user(
        db, email=body.email, username=body.username, full_name=body.full_name, password=body.password,
        ip_address=_client_ip(request), user_agent=request.headers.get("User-Agent"), request_id=_request_id(request),
    )
    return _to_public(user)


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    await enforce_rate_limit(f"login:{_client_ip(request)}", limit=5, window_seconds=60)
    user = await auth_service.authenticate_user(
        db, identifier=body.identifier, password=body.password,
        ip_address=_client_ip(request), user_agent=request.headers.get("User-Agent"), request_id=_request_id(request),
    )
    return await _issue_login_session(db, response, user, request)


@router.post("/refresh", response_model=LoginResponse)
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    await enforce_rate_limit(f"refresh:{_client_ip(request)}", limit=900, window_seconds=60)

    raw_token = request.cookies.get(settings.refresh_cookie_name)
    if not raw_token:
        # No session cookie at all (e.g. first-ever page load) — this is a normal "not logged in"
        # outcome, not a CSRF violation. Checking CSRF first would incorrectly surface a 403 here.
        raise refresh_invalid()

    verify_csrf(request)

    new_raw, access_token, expires_in, user = await token_service.rotate_refresh_token(
        db, raw_token=raw_token, ip_address=_client_ip(request),
        user_agent=request.headers.get("User-Agent"), request_id=_request_id(request),
    )
    csrf_token = set_auth_cookies(response, refresh_token=new_raw)
    return LoginResponse(access_token=access_token, expires_in=expires_in, user=_to_public(user), csrf_token=csrf_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request, response: Response, db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_current_user),
):
    verify_csrf(request)
    raw_token = request.cookies.get(settings.refresh_cookie_name)
    await auth_service.logout(
        db, raw_refresh_token=raw_token, session_id=ctx.session_id, user_id=str(ctx.user.id),
        ip_address=_client_ip(request), user_agent=request.headers.get("User-Agent"), request_id=_request_id(request),
    )
    clear_auth_cookies(response)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(
    request: Request, response: Response, db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_current_user),
):
    verify_csrf(request)
    await auth_service.logout_all(
        db, user_id=str(ctx.user.id), ip_address=_client_ip(request),
        user_agent=request.headers.get("User-Agent"), request_id=_request_id(request),
    )
    clear_auth_cookies(response)


@router.get("/me", response_model=UserPublic)
async def me(ctx: AuthContext = Depends(get_current_user)):
    return _to_public(ctx.user)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest, request: Request, response: Response,
    db: AsyncSession = Depends(get_db), ctx: AuthContext = Depends(get_current_user),
):
    verify_csrf(request)
    await auth_service.change_password(
        db, user=ctx.user, current_password=body.current_password, new_password=body.new_password,
        session_id=ctx.session_id, ip_address=_client_ip(request),
        user_agent=request.headers.get("User-Agent"), request_id=_request_id(request),
    )
    # All sessions (including this one) were revoked as part of the password change.
    clear_auth_cookies(response)


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(body: ForgotPasswordRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await enforce_rate_limit(f"forgot-password:{_client_ip(request)}:{body.email.lower()}", limit=3, window_seconds=3600)
    await password_reset_service.request_password_reset(
        db, email=body.email, ip_address=_client_ip(request),
        user_agent=request.headers.get("User-Agent"), request_id=_request_id(request),
    )
    # Generic response regardless of whether the account exists — prevents email enumeration.
    return MessageResponse(message="If an account exists for that email, password reset instructions have been sent.")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(body: ResetPasswordRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await enforce_rate_limit(f"reset-password:{_client_ip(request)}", limit=5, window_seconds=3600)
    await password_reset_service.reset_password(
        db, raw_token=body.token, new_password=body.new_password, ip_address=_client_ip(request),
        user_agent=request.headers.get("User-Agent"), request_id=_request_id(request),
    )
    return MessageResponse(message="Your password has been reset. Please sign in with your new password.")


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(db: AsyncSession = Depends(get_db), ctx: AuthContext = Depends(get_current_user)):
    sessions = await session_service.list_sessions_for_user(db, str(ctx.user.id))
    return [
        SessionOut(
            id=str(s.id), device_name=s.device_name, browser=s.browser, operating_system=s.operating_system,
            ip_address=s.ip_address, created_at=s.created_at, last_activity_at=s.last_activity_at,
            expires_at=s.expires_at, is_current=str(s.id) == str(ctx.session_id),
        )
        for s in sessions
    ]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(
    session_id: str, request: Request, db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_current_user),
):
    verify_csrf(request)
    session = (
        await db.execute(select(UserSession).where(UserSession.id == session_id, UserSession.user_id == ctx.user.id))
    ).scalar_one_or_none()
    if session is None:
        raise AppError("NOT_FOUND", "Session not found.", 404)
    await session_service.revoke_session(db, session_id, reason="user_revoked")
    await token_service.revoke_tokens_for_session(db, session_id, reason="user_revoked_session")
    await auth_audit_service.log_event(
        db, action=auth_audit_service.ACTION_SESSION_REVOKED, status="success", user_id=str(ctx.user.id),
        ip_address=_client_ip(request), user_agent=request.headers.get("User-Agent"), request_id=_request_id(request),
        metadata={"session_id": session_id},
    )
    await db.commit()


@router.delete("/sessions", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_all_other_sessions(
    request: Request, db: AsyncSession = Depends(get_db), ctx: AuthContext = Depends(get_current_user),
):
    verify_csrf(request)
    await session_service.revoke_all_sessions_for_user(
        db, str(ctx.user.id), reason="user_revoked_all", except_session_id=ctx.session_id
    )
    await auth_audit_service.log_event(
        db, action=auth_audit_service.ACTION_SESSION_REVOKED, status="success", user_id=str(ctx.user.id),
        ip_address=_client_ip(request), user_agent=request.headers.get("User-Agent"), request_id=_request_id(request),
        metadata={"scope": "all_other_sessions"},
    )
    await db.commit()
