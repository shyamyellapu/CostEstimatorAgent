"""Core authentication flows: registration, login (with lockout), logout, password change."""
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.passwords import hash_password, validate_password_policy, verify_password
from app.config import settings
from app.core.exceptions import (
    account_disabled, account_locked, email_exists, invalid_credentials, username_exists,
)
from app.models import Role, User
from app.services import auth_audit_service as audit
from app.services import session_service, token_service


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def get_role_by_name(db: AsyncSession, name: str) -> Optional[Role]:
    result = await db.execute(select(Role).where(Role.name == name))
    return result.scalar_one_or_none()


async def register_user(
    db: AsyncSession,
    *,
    email: str,
    username: str,
    full_name: str,
    password: str,
    ip_address: Optional[str],
    user_agent: Optional[str],
    request_id: Optional[str],
) -> User:
    email = email.strip().lower()
    username = username.strip().lower()

    existing_email = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing_email:
        await audit.log_event(
            db, action=audit.ACTION_REGISTRATION_FAILURE, status="failure",
            ip_address=ip_address, user_agent=user_agent, request_id=request_id,
            metadata={"reason": "email_exists", "email": email},
        )
        await db.commit()
        raise email_exists()

    existing_username = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
    if existing_username:
        await audit.log_event(
            db, action=audit.ACTION_REGISTRATION_FAILURE, status="failure",
            ip_address=ip_address, user_agent=user_agent, request_id=request_id,
            metadata={"reason": "username_exists", "username": username},
        )
        await db.commit()
        raise username_exists()

    # Never trust a client-supplied role — always assign the server-configured default.
    validate_password_policy(password, email=email, username=username)
    role = await get_role_by_name(db, settings.default_signup_role)

    user = User(
        email=email,
        username=username,
        full_name=full_name.strip(),
        hashed_password=hash_password(password),
        role_id=role.id if role else None,
        is_active=True,
        is_verified=False,
        password_changed_at=_now(),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user, attribute_names=["role"])

    await audit.log_event(
        db, action=audit.ACTION_REGISTRATION_SUCCESS, status="success",
        user_id=str(user.id), ip_address=ip_address, user_agent=user_agent, request_id=request_id,
    )
    await db.commit()
    return user


async def authenticate_user(
    db: AsyncSession,
    *,
    identifier: str,
    password: str,
    ip_address: Optional[str],
    user_agent: Optional[str],
    request_id: Optional[str],
) -> User:
    """identifier = email or username. Raises AuthError on any failure (generic message)."""
    identifier_norm = identifier.strip().lower()
    result = await db.execute(
        select(User).where((User.email == identifier_norm) | (User.username == identifier_norm))
    )
    user = result.scalar_one_or_none()

    if user is None:
        # Constant-shape failure path to avoid revealing whether the account exists.
        await audit.log_event(
            db, action=audit.ACTION_LOGIN_FAILURE, status="failure",
            ip_address=ip_address, user_agent=user_agent, request_id=request_id,
            metadata={"reason": "no_such_user", "identifier": identifier_norm},
        )
        await db.commit()
        raise invalid_credentials()

    if user.locked_until and user.locked_until > _now():
        await audit.log_event(
            db, action=audit.ACTION_LOGIN_FAILURE, status="failure", user_id=str(user.id),
            ip_address=ip_address, user_agent=user_agent, request_id=request_id,
            metadata={"reason": "locked"},
        )
        await db.commit()
        raise account_locked()

    if not user.is_active:
        await audit.log_event(
            db, action=audit.ACTION_LOGIN_FAILURE, status="failure", user_id=str(user.id),
            ip_address=ip_address, user_agent=user_agent, request_id=request_id,
            metadata={"reason": "disabled"},
        )
        await db.commit()
        raise account_disabled()

    if not verify_password(password, user.hashed_password):
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        locked_now = False
        if user.failed_login_attempts >= settings.max_login_attempts:
            user.locked_until = _now() + timedelta(minutes=settings.account_lock_minutes)
            user.failed_login_attempts = 0
            locked_now = True
        await audit.log_event(
            db, action=audit.ACTION_LOGIN_FAILURE, status="failure", user_id=str(user.id),
            ip_address=ip_address, user_agent=user_agent, request_id=request_id,
            metadata={"reason": "bad_password"},
        )
        if locked_now:
            await audit.log_event(
                db, action=audit.ACTION_ACCOUNT_LOCKED, status="failure", user_id=str(user.id),
                ip_address=ip_address, user_agent=user_agent, request_id=request_id,
            )
        await db.commit()
        raise account_locked() if locked_now else invalid_credentials()

    # Success — reset lockout counters, record last login.
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = _now()
    await db.flush()
    await db.refresh(user, attribute_names=["role"])

    await audit.log_event(
        db, action=audit.ACTION_LOGIN_SUCCESS, status="success", user_id=str(user.id),
        ip_address=ip_address, user_agent=user_agent, request_id=request_id,
    )
    return user


async def logout(db: AsyncSession, *, raw_refresh_token: Optional[str], session_id: Optional[str], user_id: str,
                  ip_address: Optional[str], user_agent: Optional[str], request_id: Optional[str]) -> None:
    if raw_refresh_token:
        await token_service.revoke_refresh_token_by_raw(db, raw_refresh_token, reason="logout")
    if session_id:
        await session_service.revoke_session(db, session_id, reason="logout")
    await audit.log_event(
        db, action=audit.ACTION_LOGOUT, status="success", user_id=user_id,
        ip_address=ip_address, user_agent=user_agent, request_id=request_id,
    )
    await db.commit()


async def logout_all(db: AsyncSession, *, user_id: str, ip_address: Optional[str], user_agent: Optional[str],
                      request_id: Optional[str]) -> None:
    await token_service.revoke_all_tokens_for_user(db, user_id, reason="logout_all")
    await session_service.revoke_all_sessions_for_user(db, user_id, reason="logout_all")
    await audit.log_event(
        db, action=audit.ACTION_LOGOUT_ALL, status="success", user_id=user_id,
        ip_address=ip_address, user_agent=user_agent, request_id=request_id,
    )
    await db.commit()


async def change_password(
    db: AsyncSession, *, user: User, current_password: str, new_password: str, session_id: str,
    ip_address: Optional[str], user_agent: Optional[str], request_id: Optional[str],
) -> None:
    if not verify_password(current_password, user.hashed_password):
        await audit.log_event(
            db, action=audit.ACTION_PASSWORD_CHANGED, status="failure", user_id=str(user.id),
            ip_address=ip_address, user_agent=user_agent, request_id=request_id,
            metadata={"reason": "bad_current_password"},
        )
        await db.commit()
        raise invalid_credentials()

    validate_password_policy(new_password, email=user.email, username=user.username)

    user.hashed_password = hash_password(new_password)
    user.password_changed_at = _now()

    # Revoke every active refresh-token family and every session — including the current one —
    # so a changed password immediately invalidates any credential that might already be
    # compromised. The caller (route) treats this the same as a logout for the current device:
    # cookies are cleared and the client must sign in again with the new password.
    await token_service.revoke_all_tokens_for_user(db, str(user.id), reason="password_changed")
    await session_service.revoke_all_sessions_for_user(db, str(user.id), reason="password_changed")

    await audit.log_event(
        db, action=audit.ACTION_PASSWORD_CHANGED, status="success", user_id=str(user.id),
        ip_address=ip_address, user_agent=user_agent, request_id=request_id,
    )
    await db.commit()
