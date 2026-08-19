"""Access-token issuance and refresh-token rotation with replay detection.

── Refresh-token rotation ──────────────────────────────────────────────────────────────────────
Every refresh request retires the presented refresh token and issues a brand-new one
("rotation"). The old row is kept (not deleted) with `is_revoked=True` and
`replaced_by_token_id` pointing at its replacement, forming an append-only chain per
`token_family_id`.

── Replay detection ─────────────────────────────────────────────────────────────────────────────
Because rotated tokens are kept (not deleted), presenting an already-rotated or already-revoked
token is detectable: if the looked-up row is already `is_revoked`, the presented token is either
a replay (stolen/duplicated token) or the loser of a race between two concurrent refresh calls.
Both cases are treated the same, conservatively, as suspected theft: the entire token family is
revoked and the associated session is terminated, forcing re-authentication.

── Concurrent refresh handling ─────────────────────────────────────────────────────────────────
`SELECT ... FOR UPDATE` locks the refresh-token row for the duration of the DB transaction, so
two simultaneous requests presenting the same token serialize: the first to commit rotates the
token; the second, once unblocked, sees `is_revoked=True`.

A *legitimate* client (e.g. a browser with several tabs open, or a React effect that fires twice
in dev StrictMode) can easily present the same still-valid token twice within milliseconds of
each other — that is not theft, just a race with itself. To avoid punishing that case with a
full session revocation, the raw result of a rotation is cached in-process for a short grace
window (`_ROTATION_GRACE_SECONDS`) keyed by the *old* token's hash: a repeat presentation within
that window is treated as idempotent and replays the same rotation response instead of raising
`refresh_reused`. Only a presentation *after* the grace window (or of a token rotated more than
once ago) is treated as suspected replay/theft.

NOTE: like `InMemoryRateLimiter` (see `app.core.rate_limit`), this cache is per-process. Replace
with a shared store (e.g. Redis) for a multi-worker/multi-instance deployment.
"""
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token
from app.auth.refresh_tokens import generate_refresh_token, hash_token
from app.config import settings
from app.core.exceptions import refresh_invalid, refresh_reused, account_disabled, session_revoked
from app.models import RefreshToken, User, UserSession
from app.services import auth_audit_service as audit
from app.services import session_service

_ROTATION_GRACE_SECONDS = 60
# old_token_hash -> (rotated_at_monotonic, new_raw_token, access_token, expires_in, user_id)
_rotation_grace_cache: dict[str, tuple[float, str, str, int, str]] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _remember_rotation(old_token_hash: str, *, new_raw: str, access_token: str, expires_in: int, user_id: str) -> None:
    now = time.monotonic()
    # Opportunistically prune expired entries so the dict doesn't grow unbounded.
    for key, (rotated_at, *_rest) in list(_rotation_grace_cache.items()):
        if now - rotated_at >= _ROTATION_GRACE_SECONDS:
            _rotation_grace_cache.pop(key, None)
    _rotation_grace_cache[old_token_hash] = (now, new_raw, access_token, expires_in, user_id)


def _recall_rotation(old_token_hash: str) -> Optional[tuple[str, str, int, str]]:
    cached = _rotation_grace_cache.get(old_token_hash)
    if cached is None:
        return None
    rotated_at, new_raw, access_token, expires_in, user_id = cached
    if time.monotonic() - rotated_at >= _ROTATION_GRACE_SECONDS:
        _rotation_grace_cache.pop(old_token_hash, None)
        return None
    return new_raw, access_token, expires_in, user_id


def _permissions_for_user(user: User) -> list[str]:
    if not user.role:
        return []
    return [p.code for p in user.role.permissions]


def issue_access_token(user: User, session_id: str) -> tuple[str, int]:
    token, expires_in, _jti = create_access_token(
        user_id=str(user.id),
        email=user.email,
        role=user.role.name if user.role else "user",
        permissions=_permissions_for_user(user),
        session_id=str(session_id),
    )
    return token, expires_in


async def issue_refresh_token(
    db: AsyncSession,
    *,
    user_id: str,
    session_id: str,
    ip_address: Optional[str],
    user_agent: Optional[str],
    token_family_id: Optional[str] = None,
    parent_token_id: Optional[str] = None,
) -> tuple[str, RefreshToken]:
    """Create a new refresh_tokens row and return (raw_token, row). Caller must commit."""
    raw_token = generate_refresh_token()
    row = RefreshToken(
        user_id=user_id,
        session_id=session_id,
        token_hash=hash_token(raw_token),
        token_family_id=token_family_id or uuid.uuid4(),
        parent_token_id=parent_token_id,
        issued_at=_now(),
        expires_at=_now() + timedelta(days=settings.refresh_token_expire_days),
        created_by_ip=ip_address,
        last_used_ip=ip_address,
        user_agent=(user_agent or "")[:1000] or None,
    )
    db.add(row)
    await db.flush()
    return raw_token, row


async def rotate_refresh_token(
    db: AsyncSession,
    *,
    raw_token: str,
    ip_address: Optional[str],
    user_agent: Optional[str],
    request_id: Optional[str],
) -> tuple[str, str, int, User]:
    """Validate + rotate a presented refresh token.

    Returns (new_raw_refresh_token, new_access_token, expires_in, user).
    Raises AuthError (401) on any invalid/reused/revoked condition.
    """
    token_hash = hash_token(raw_token)

    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
    )
    stored = result.scalar_one_or_none()

    if stored is None:
        await audit.log_event(
            db, action=audit.ACTION_REFRESH_FAILURE, status="failure",
            ip_address=ip_address, user_agent=user_agent, request_id=request_id,
            metadata={"reason": "not_found"},
        )
        await db.commit()
        raise refresh_invalid()

    if stored.is_revoked:
        # Within the grace window this is almost certainly the client racing itself (duplicate
        # tab, StrictMode double-effect, proactive-refresh timer overlapping a 401-triggered
        # refresh) rather than theft — replay the same rotation result instead of nuking the
        # session out from under a legitimate, still-connected client.
        if stored.revocation_reason == "rotated":
            cached = _recall_rotation(token_hash)
            if cached is not None:
                new_raw, access_token, expires_in, user_id = cached
                cached_user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
                await db.commit()
                if cached_user is not None:
                    await audit.log_event(
                        db, action=audit.ACTION_REFRESH_SUCCESS, status="success",
                        user_id=str(cached_user.id), ip_address=ip_address, user_agent=user_agent,
                        request_id=request_id, metadata={"reason": "rotation_grace_replay"},
                    )
                    return new_raw, access_token, expires_in, cached_user

        # Replay (or a duplicate presentation after the grace window has elapsed) — revoke the
        # whole family.
        await _revoke_family(db, stored.token_family_id, reason="reuse_detected")
        if stored.session_id:
            await session_service.revoke_session(db, str(stored.session_id), reason="refresh_token_reuse_detected")
        await audit.log_event(
            db, action=audit.ACTION_REFRESH_REUSE_DETECTED, status="failure",
            user_id=str(stored.user_id), ip_address=ip_address, user_agent=user_agent,
            request_id=request_id, metadata={"token_family_id": str(stored.token_family_id)},
        )
        await db.commit()
        raise refresh_reused()

    if stored.expires_at < _now():
        stored.is_revoked = True
        stored.revoked_at = _now()
        stored.revocation_reason = "expired"
        await audit.log_event(
            db, action=audit.ACTION_REFRESH_FAILURE, status="failure",
            user_id=str(stored.user_id), ip_address=ip_address, user_agent=user_agent,
            request_id=request_id, metadata={"reason": "expired"},
        )
        await db.commit()
        raise refresh_invalid()

    # Load user + session, verify both are still active.
    user = (await db.execute(select(User).where(User.id == stored.user_id))).scalar_one_or_none()
    if user is None or not user.is_active:
        await audit.log_event(
            db, action=audit.ACTION_REFRESH_FAILURE, status="failure",
            user_id=str(stored.user_id), ip_address=ip_address, user_agent=user_agent,
            request_id=request_id, metadata={"reason": "user_inactive"},
        )
        await db.commit()
        raise account_disabled()

    session_row: Optional[UserSession] = None
    if stored.session_id:
        session_row = await session_service.get_active_session(db, str(stored.session_id))
        if session_row is None:
            await audit.log_event(
                db, action=audit.ACTION_REFRESH_FAILURE, status="failure",
                user_id=str(user.id), ip_address=ip_address, user_agent=user_agent,
                request_id=request_id, metadata={"reason": "session_revoked"},
            )
            await db.commit()
            raise session_revoked()

    # ── Rotate: issue replacement, retire the presented token ──────────────────────────────
    new_raw, new_row = await issue_refresh_token(
        db,
        user_id=str(user.id),
        session_id=str(stored.session_id) if stored.session_id else None,
        ip_address=ip_address,
        user_agent=user_agent,
        token_family_id=stored.token_family_id,
        parent_token_id=stored.id,
    )

    stored.is_revoked = True
    stored.revoked_at = _now()
    stored.revocation_reason = "rotated"
    stored.replaced_by_token_id = new_row.id
    stored.last_used_ip = ip_address

    if session_row:
        session_row.current_refresh_token_id = new_row.id
        await session_service.touch_activity(db, session_row)

    # Reload role/permissions relationship for the token payload
    await db.refresh(user, attribute_names=["role"])
    access_token, expires_in = issue_access_token(user, str(stored.session_id) if stored.session_id else "")

    # Let a racing duplicate presentation of `raw_token` within the grace window replay this
    # same result instead of being treated as theft (see module docstring).
    _remember_rotation(token_hash, new_raw=new_raw, access_token=access_token, expires_in=expires_in, user_id=str(user.id))

    await audit.log_event(
        db, action=audit.ACTION_REFRESH_SUCCESS, status="success",
        user_id=str(user.id), ip_address=ip_address, user_agent=user_agent, request_id=request_id,
    )
    await db.commit()

    return new_raw, access_token, expires_in, user


async def _revoke_family(db: AsyncSession, token_family_id, reason: str) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.token_family_id == token_family_id, RefreshToken.is_revoked.is_(False))
        .values(is_revoked=True, revoked_at=_now(), revocation_reason=reason)
    )


async def revoke_refresh_token_by_raw(db: AsyncSession, raw_token: str, reason: str) -> Optional[RefreshToken]:
    token_hash = hash_token(raw_token)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    stored = result.scalar_one_or_none()
    if stored and not stored.is_revoked:
        stored.is_revoked = True
        stored.revoked_at = _now()
        stored.revocation_reason = reason
    return stored


async def revoke_all_tokens_for_user(db: AsyncSession, user_id: str, reason: str) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.is_revoked.is_(False))
        .values(is_revoked=True, revoked_at=_now(), revocation_reason=reason)
    )


async def revoke_tokens_for_session(db: AsyncSession, session_id: str, reason: str) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.session_id == session_id, RefreshToken.is_revoked.is_(False))
        .values(is_revoked=True, revoked_at=_now(), revocation_reason=reason)
    )
