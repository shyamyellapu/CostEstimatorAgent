"""User session (device/browser) lifecycle management."""
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import UserSession

# Throttle window for last_activity_at writes — avoid a DB write on every single API request.
ACTIVITY_THROTTLE = timedelta(minutes=5)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def parse_device_info(user_agent: Optional[str]) -> dict[str, Optional[str]]:
    if not user_agent:
        return {"device_name": None, "browser": None, "operating_system": None}
    try:
        from user_agents import parse
        ua = parse(user_agent)
        device_name = ua.device.family if ua.device and ua.device.family != "Other" else ("Mobile" if ua.is_mobile else "Desktop")
        return {
            "device_name": device_name,
            "browser": f"{ua.browser.family} {ua.browser.version_string}".strip(),
            "operating_system": f"{ua.os.family} {ua.os.version_string}".strip(),
        }
    except Exception:
        return {"device_name": None, "browser": None, "operating_system": None}


async def create_session(
    db: AsyncSession, *, user_id: str, ip_address: Optional[str], user_agent: Optional[str]
) -> UserSession:
    device_info = parse_device_info(user_agent)
    session = UserSession(
        user_id=user_id,
        ip_address=ip_address,
        user_agent=(user_agent or "")[:1000] or None,
        device_name=device_info["device_name"],
        browser=device_info["browser"],
        operating_system=device_info["operating_system"],
        created_at=_now(),
        last_activity_at=_now(),
        expires_at=_now() + timedelta(days=settings.refresh_token_expire_days),
        is_active=True,
    )
    db.add(session)
    await db.flush()
    return session


async def get_active_session(db: AsyncSession, session_id: str) -> Optional[UserSession]:
    result = await db.execute(
        select(UserSession).where(UserSession.id == session_id, UserSession.is_active.is_(True))
    )
    return result.scalar_one_or_none()


async def touch_activity(db: AsyncSession, session: UserSession) -> None:
    """Throttled last_activity_at update — at most once per ACTIVITY_THROTTLE window."""
    now = _now()
    if session.last_activity_at is None or (now - session.last_activity_at) >= ACTIVITY_THROTTLE:
        session.last_activity_at = now
        await db.flush()


async def revoke_session(db: AsyncSession, session_id: str, reason: str) -> None:
    await db.execute(
        update(UserSession)
        .where(UserSession.id == session_id, UserSession.is_active.is_(True))
        .values(is_active=False, revoked_at=_now(), revocation_reason=reason)
    )


async def revoke_all_sessions_for_user(
    db: AsyncSession, user_id: str, reason: str, *, except_session_id: Optional[str] = None
) -> None:
    stmt = update(UserSession).where(UserSession.user_id == user_id, UserSession.is_active.is_(True))
    if except_session_id:
        stmt = stmt.where(UserSession.id != except_session_id)
    await db.execute(stmt.values(is_active=False, revoked_at=_now(), revocation_reason=reason))


async def list_sessions_for_user(db: AsyncSession, user_id: str) -> list[UserSession]:
    result = await db.execute(
        select(UserSession)
        .where(UserSession.user_id == user_id, UserSession.is_active.is_(True))
        .order_by(UserSession.last_activity_at.desc().nullslast())
    )
    return list(result.scalars().all())
