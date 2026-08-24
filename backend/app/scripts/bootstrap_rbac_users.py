"""One-time CLI to bootstrap the RBAC system accounts (admin / manager / estimator).

Usage:
    cd CostEstimatorAgent/backend
    python -m app.scripts.bootstrap_rbac_users

Requires BOOTSTRAP_RBAC_USERS=true and the BOOTSTRAP_<ROLE>_* environment variables (see
backend/.env.example). Idempotent — safe to re-run. Never prints or logs a plaintext password.
After a successful run in an environment, set BOOTSTRAP_RBAC_USERS=false.
"""
import asyncio
import logging

from app.database import AsyncSessionLocal
from app.services.rbac_bootstrap_service import bootstrap_rbac_users

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    async with AsyncSessionLocal() as db:
        summary = await bootstrap_rbac_users(db, user_agent="bootstrap-cli")

    print(
        f"RBAC bootstrap summary: created={summary.created} "
        f"updated_roles={summary.updated_roles} skipped={summary.skipped}"
    )
    if summary.errors:
        print("Warnings:")
        for err in summary.errors:
            print(f"  - {err}")


if __name__ == "__main__":
    asyncio.run(main())
