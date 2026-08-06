"""Forgot-password / reset-password flow.

Always returns a generic response regardless of whether the email exists, to prevent account
enumeration. Only the SHA-256 hash of the one-time reset token is ever persisted.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.passwords import hash_password, validate_password_policy
from app.config import settings
from app.core.exceptions import AppError
from app.models import PasswordResetToken, User
from app.services import auth_audit_service as audit
from app.services import session_service, token_service


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def request_password_reset(
    db: AsyncSession, *, email: str, ip_address: Optional[str], user_agent: Optional[str], request_id: Optional[str],
) -> None:
    email_norm = email.strip().lower()
    user = (await db.execute(select(User).where(User.email == email_norm))).scalar_one_or_none()

    if user and user.is_active:
        raw_token = secrets.token_urlsafe(32)
        reset_row = PasswordResetToken(
            user_id=user.id,
            token_hash=_hash(raw_token),
            expires_at=_now() + timedelta(minutes=settings.password_reset_expire_minutes),
            requested_ip=ip_address,
        )
        db.add(reset_row)
        await audit.log_event(
            db, action=audit.ACTION_PASSWORD_RESET_REQUESTED, status="success", user_id=str(user.id),
            ip_address=ip_address, user_agent=user_agent, request_id=request_id,
        )
        # In production this token is emailed to the user, never returned in the API response.
        # TODO: wire to a transactional email provider. Logged at DEBUG only for local dev use.
        import logging
        logging.getLogger(__name__).debug("password_reset_token issued for user_id=%s", user.id)

    # Always commit + return the same generic outcome whether or not the email existed.
    await db.commit()


async def reset_password(
    db: AsyncSession, *, raw_token: str, new_password: str, ip_address: Optional[str],
    user_agent: Optional[str], request_id: Optional[str],
) -> None:
    token_hash = _hash(raw_token)
    result = await db.execute(select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash))
    row = result.scalar_one_or_none()

    if row is None or row.used_at is not None or row.expires_at < _now():
        await audit.log_event(
            db, action=audit.ACTION_PASSWORD_RESET_COMPLETED, status="failure",
            ip_address=ip_address, user_agent=user_agent, request_id=request_id,
            metadata={"reason": "invalid_or_expired_token"},
        )
        await db.commit()
        raise AppError("AUTH_REFRESH_INVALID", "This password reset link is invalid or has expired.", 400)

    user = (await db.execute(select(User).where(User.id == row.user_id))).scalar_one_or_none()
    if user is None or not user.is_active:
        await db.commit()
        raise AppError("AUTH_ACCOUNT_DISABLED", "This account cannot reset its password.", 403)

    validate_password_policy(new_password, email=user.email, username=user.username)

    user.hashed_password = hash_password(new_password)
    user.password_changed_at = _now()
    user.failed_login_attempts = 0
    user.locked_until = None
    row.used_at = _now()

    # A successful reset invalidates every existing credential for this account.
    await token_service.revoke_all_tokens_for_user(db, str(user.id), reason="password_reset")
    await session_service.revoke_all_sessions_for_user(db, str(user.id), reason="password_reset")

    await audit.log_event(
        db, action=audit.ACTION_PASSWORD_RESET_COMPLETED, status="success", user_id=str(user.id),
        ip_address=ip_address, user_agent=user_agent, request_id=request_id,
    )
    await db.commit()
