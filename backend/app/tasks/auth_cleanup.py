"""Background cleanup for expired/stale authentication data.

Uses APScheduler's AsyncIOScheduler for the current single-service deployment. The scheduler is
started once from `app.main`'s lifespan handler.

Multi-worker / multi-instance note:
    If the app is ever run with multiple uvicorn/gunicorn workers (or multiple container
    replicas), starting this scheduler in every process would run the cleanup job N times
    concurrently. Guard against that in production by either:
      1. Running APScheduler in exactly one dedicated worker/process (e.g. a separate
         "beat"-like deployment), or
      2. Replacing this with a Celery-beat task (the functions below are already pure and easy
         to wrap in a Celery task — no FastAPI/APScheduler-specific state is captured), or
      3. Using a Postgres advisory lock (`pg_try_advisory_lock`) at the top of `run_cleanup()` so
         only the worker that acquires the lock executes the job.
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import AuthAuditLog, PasswordResetToken, RefreshToken, UserSession

logger = logging.getLogger(__name__)

_scheduler = None  # module-level singleton guard — see start_scheduler()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def run_cleanup() -> dict[str, int]:
    """Delete expired/stale auth rows past their retention window. Returns counts for logging."""
    now = _now()
    retention_cutoff = now - timedelta(days=settings.revoked_token_retention_days)
    audit_cutoff = now - timedelta(days=settings.audit_log_retention_days)

    counts: dict[str, int] = {}
    async with AsyncSessionLocal() as db:
        try:
            # Expired, never-used password-reset tokens
            result = await db.execute(
                delete(PasswordResetToken).where(PasswordResetToken.expires_at < now)
            )
            counts["password_reset_tokens"] = result.rowcount or 0

            # Refresh tokens that are revoked/expired and past the retention window
            result = await db.execute(
                delete(RefreshToken).where(
                    RefreshToken.expires_at < retention_cutoff,
                )
            )
            counts["refresh_tokens"] = result.rowcount or 0

            # Sessions that expired and are no longer active, past the retention window
            result = await db.execute(
                delete(UserSession).where(
                    UserSession.is_active.is_(False),
                    UserSession.expires_at < retention_cutoff,
                )
            )
            counts["user_sessions"] = result.rowcount or 0

            # Old audit logs past the configured retention period
            result = await db.execute(
                delete(AuthAuditLog).where(AuthAuditLog.timestamp < audit_cutoff)
            )
            counts["auth_audit_logs"] = result.rowcount or 0

            await db.commit()
        except Exception:
            await db.rollback()
            logger.exception("auth_cleanup_failed")
            raise

    logger.info("auth_cleanup_complete counts=%s", counts)
    return counts


def start_scheduler() -> None:
    """Start the APScheduler job exactly once per process. Safe to call multiple times."""
    global _scheduler
    if _scheduler is not None:
        return

    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        run_cleanup,
        "interval",
        hours=settings.auth_cleanup_interval_hours,
        id="auth_cleanup",
        replace_existing=True,
        next_run_time=None,  # first run after one full interval, not immediately on boot
    )
    _scheduler.start()
    logger.info("auth_cleanup scheduler started interval_hours=%.1f", settings.auth_cleanup_interval_hours)
