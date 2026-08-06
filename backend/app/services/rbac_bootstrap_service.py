"""One-time, idempotent bootstrap of the RBAC system accounts (admin / manager / estimator).

Controlled entirely by backend environment variables (see `app.config.Settings`) — credentials
are never hard-coded here or anywhere else. Safe to call repeatedly (on every worker startup,
or via the CLI in `app.scripts.bootstrap_rbac_users`):

- Missing accounts are created with the requested role and a hashed password.
- Existing accounts have their role corrected if it drifted, but keep their current password
  unless `BOOTSTRAP_UPDATE_EXISTING_PASSWORDS=true`.
- Nothing here ever logs, prints, or returns a plaintext password or password hash.
- A Postgres advisory transaction lock serializes concurrent bootstrap attempts from multiple
  Gunicorn workers so they never race each other; the operation is idempotent either way.
"""
from dataclasses import dataclass, field
import logging
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.passwords import hash_password, validate_password_policy
from app.config import settings
from app.models import Role, User
from app.services import auth_audit_service as audit

logger = logging.getLogger(__name__)

# Arbitrary fixed key for the Postgres advisory lock guarding this bootstrap routine.
_ADVISORY_LOCK_KEY = 0x52424143_424F4F54  # "RBACBOOT" as hex, just needs to be a stable bigint


@dataclass
class _AccountSpec:
    role_name: str
    email: str
    username: str
    full_name: str
    password: str


@dataclass
class BootstrapSummary:
    """Safe summary returned to callers — counts only, never credentials."""
    created: int = 0
    updated_roles: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


def _load_account_specs() -> list[_AccountSpec]:
    raw = [
        ("admin", settings.bootstrap_admin_email, settings.bootstrap_admin_username,
         settings.bootstrap_admin_full_name, settings.bootstrap_admin_password),
        ("manager", settings.bootstrap_manager_email, settings.bootstrap_manager_username,
         settings.bootstrap_manager_full_name, settings.bootstrap_manager_password),
        ("estimator", settings.bootstrap_estimator_email, settings.bootstrap_estimator_username,
         settings.bootstrap_estimator_full_name, settings.bootstrap_estimator_password),
    ]
    specs: list[_AccountSpec] = []
    for role_name, email, username, full_name, password in raw:
        if not (email and username and full_name and password):
            # Fail safely: an incompletely-configured account is skipped, never guessed at.
            logger.warning(
                "RBAC bootstrap: skipping '%s' account setup - one or more required "
                "BOOTSTRAP_%s_* environment variables are missing.",
                role_name, role_name.upper(),
            )
            continue
        specs.append(_AccountSpec(
            role_name=role_name, email=email.strip().lower(), username=username.strip().lower(),
            full_name=full_name.strip(), password=password,
        ))
    return specs


async def bootstrap_rbac_users(
    db: AsyncSession, *, ip_address: Optional[str] = None, user_agent: Optional[str] = "rbac-bootstrap",
    request_id: Optional[str] = None,
) -> BootstrapSummary:
    """Create/repair the admin, manager, and estimator system accounts. No-op unless
    `BOOTSTRAP_RBAC_USERS=true`. Returns a safe summary — never passwords or hashes."""
    summary = BootstrapSummary()

    if not settings.bootstrap_rbac_users:
        logger.info("RBAC bootstrap skipped: BOOTSTRAP_RBAC_USERS is not enabled.")
        return summary

    specs = _load_account_specs()
    if not specs:
        logger.warning("RBAC bootstrap enabled but no complete account specs were found - nothing to do.")
        return summary

    try:
        # Serializes concurrent bootstrap attempts across multiple worker processes; released
        # automatically when this transaction commits or rolls back.
        await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _ADVISORY_LOCK_KEY})

        for spec in specs:
            await _bootstrap_one_account(
                db, spec, summary, ip_address=ip_address, user_agent=user_agent, request_id=request_id,
            )
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("RBAC bootstrap failed; all changes rolled back.")
        raise

    logger.info(
        "RBAC bootstrap complete: created=%d updated_roles=%d skipped=%d",
        summary.created, summary.updated_roles, summary.skipped,
    )
    return summary


async def _bootstrap_one_account(
    db: AsyncSession, spec: _AccountSpec, summary: BootstrapSummary, *,
    ip_address: Optional[str], user_agent: Optional[str], request_id: Optional[str],
) -> None:
    role = (await db.execute(select(Role).where(Role.name == spec.role_name))).scalar_one_or_none()
    if role is None:
        summary.errors.append(f"Role '{spec.role_name}' does not exist yet - run migrations first.")
        summary.skipped += 1
        return

    existing = (
        await db.execute(select(User).where((User.email == spec.email) | (User.username == spec.username)))
    ).scalar_one_or_none()

    if existing is None:
        try:
            validate_password_policy(spec.password, email=spec.email, username=spec.username)
        except Exception:
            summary.errors.append(f"Password for '{spec.username}' fails policy - account not created.")
            summary.skipped += 1
            return

        user = User(
            email=spec.email, username=spec.username, full_name=spec.full_name,
            hashed_password=hash_password(spec.password), role_id=role.id,
            is_active=True, is_verified=True,
        )
        db.add(user)
        await db.flush()
        await audit.log_event(
            db, action="rbac_bootstrap_account_created", status="success", user_id=str(user.id),
            ip_address=ip_address, user_agent=user_agent, request_id=request_id,
            metadata={"role": spec.role_name, "username": spec.username, "email": spec.email},
        )
        summary.created += 1
        return

    # Existing account: correct role only when necessary; never overwrite the password unless
    # explicitly opted into via BOOTSTRAP_UPDATE_EXISTING_PASSWORDS.
    changed = False

    if existing.role is None or existing.role.name != spec.role_name:
        old_role = existing.role.name if existing.role else None
        existing.role_id = role.id
        await audit.log_event(
            db, action="rbac_bootstrap_role_corrected", status="success", user_id=str(existing.id),
            ip_address=ip_address, user_agent=user_agent, request_id=request_id,
            metadata={"username": spec.username, "old_role": old_role, "new_role": spec.role_name},
        )
        summary.updated_roles += 1
        changed = True

    if settings.bootstrap_update_existing_passwords:
        existing.hashed_password = hash_password(spec.password)
        await audit.log_event(
            db, action="rbac_bootstrap_password_reset", status="success", user_id=str(existing.id),
            ip_address=ip_address, user_agent=user_agent, request_id=request_id,
            metadata={"username": spec.username},
        )
        changed = True

    if not changed:
        summary.skipped += 1
