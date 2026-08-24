"""Writes immutable AuthAuditLog rows for authentication/authorization events."""
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuthAuditLog

# Canonical audit actions (kept as plain strings — not a DB enum — so new actions can be added
# without a migration).
ACTION_REGISTRATION_SUCCESS = "registration_success"
ACTION_REGISTRATION_FAILURE = "registration_failure"
ACTION_LOGIN_SUCCESS = "login_success"
ACTION_LOGIN_FAILURE = "login_failure"
ACTION_ACCOUNT_LOCKED = "account_locked"
ACTION_ACCESS_TOKEN_ISSUED = "access_token_issued"
ACTION_REFRESH_SUCCESS = "refresh_success"
ACTION_REFRESH_FAILURE = "refresh_failure"
ACTION_REFRESH_REUSE_DETECTED = "refresh_token_reuse_detected"
ACTION_LOGOUT = "logout"
ACTION_LOGOUT_ALL = "logout_all"
ACTION_PASSWORD_CHANGED = "password_changed"
ACTION_PASSWORD_RESET_REQUESTED = "password_reset_requested"
ACTION_PASSWORD_RESET_COMPLETED = "password_reset_completed"
ACTION_ROLE_CHANGED = "role_changed"
ACTION_USER_DISABLED = "user_disabled"
ACTION_SESSION_REVOKED = "session_revoked"


async def log_event(
    db: AsyncSession,
    *,
    action: str,
    status: str = "success",
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    request_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    entry = AuthAuditLog(
        user_id=user_id,
        action=action,
        status=status,
        ip_address=ip_address,
        user_agent=(user_agent or "")[:1000] or None,
        request_id=request_id,
        metadata_json=metadata,
    )
    db.add(entry)
    await db.flush()
