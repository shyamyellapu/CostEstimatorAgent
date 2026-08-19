"""Tests for the RBAC system-account bootstrap service (app.services.rbac_bootstrap_service)."""
from app.auth.passwords import verify_password
from app.config import settings
from app.models import Role, User
from sqlalchemy import select

from tests.conftest import AsyncSessionLocal, run_async
from tests.helpers import auth_headers, csrf_headers, login, unique


def _set_bootstrap_env(admin_suffix: str, *, update_passwords: bool = False):
    settings.bootstrap_rbac_users = True
    settings.bootstrap_update_existing_passwords = update_passwords

    settings.bootstrap_admin_email = f"admin-{admin_suffix}@example.com"
    settings.bootstrap_admin_username = f"admin{admin_suffix}"
    settings.bootstrap_admin_full_name = "Bootstrap Admin"
    settings.bootstrap_admin_password = "Str0ng!Passw0rd"

    settings.bootstrap_manager_email = f"manager-{admin_suffix}@example.com"
    settings.bootstrap_manager_username = f"manager{admin_suffix}"
    settings.bootstrap_manager_full_name = "Bootstrap Manager"
    settings.bootstrap_manager_password = "Str0ng!Passw0rd"

    settings.bootstrap_estimator_email = f"estimator-{admin_suffix}@example.com"
    settings.bootstrap_estimator_username = f"estimator{admin_suffix}"
    settings.bootstrap_estimator_full_name = "Bootstrap Estimator"
    settings.bootstrap_estimator_password = "Str0ng!Passw0rd"


def _reset_bootstrap_env():
    settings.bootstrap_rbac_users = False
    settings.bootstrap_update_existing_passwords = False
    for role in ("admin", "manager", "estimator"):
        setattr(settings, f"bootstrap_{role}_email", "")
        setattr(settings, f"bootstrap_{role}_username", "")
        setattr(settings, f"bootstrap_{role}_full_name", "")
        setattr(settings, f"bootstrap_{role}_password", "")


async def _run_bootstrap():
    from app.services.rbac_bootstrap_service import bootstrap_rbac_users
    async with AsyncSessionLocal() as db:
        return await bootstrap_rbac_users(db)


async def _get_user_by_username(username: str) -> User:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.username == username))
        user = result.scalar_one()
        await db.refresh(user, attribute_names=["role"])
        return user


def test_bootstrap_creates_three_accounts_with_correct_roles(client):
    suffix = unique("boot").replace("-", "")
    _set_bootstrap_env(suffix)
    try:
        summary = run_async(_run_bootstrap())
        assert summary.created == 3
        assert summary.updated_roles == 0

        admin_user = run_async(_get_user_by_username(f"admin{suffix}"))
        manager_user = run_async(_get_user_by_username(f"manager{suffix}"))
        estimator_user = run_async(_get_user_by_username(f"estimator{suffix}"))

        assert admin_user.role.name == "admin"
        assert manager_user.role.name == "manager"
        assert estimator_user.role.name == "estimator"
        assert admin_user.is_active and admin_user.is_verified
        # Password is stored only as a hash, never plaintext.
        assert admin_user.hashed_password != "Str0ng!Passw0rd"
        assert verify_password("Str0ng!Passw0rd", admin_user.hashed_password)
    finally:
        _reset_bootstrap_env()


def test_bootstrap_rerun_is_idempotent_and_preserves_existing_password(client):
    suffix = unique("boot2").replace("-", "")
    _set_bootstrap_env(suffix)
    try:
        first = run_async(_run_bootstrap())
        assert first.created == 3

        admin_before = run_async(_get_user_by_username(f"admin{suffix}"))
        original_hash = admin_before.hashed_password

        # Change the configured password, rerun without BOOTSTRAP_UPDATE_EXISTING_PASSWORDS —
        # the stored hash must not change.
        settings.bootstrap_admin_password = "Different!Passw0rd9"
        second = run_async(_run_bootstrap())
        assert second.created == 0
        assert second.skipped == 3  # nothing to correct on the second run

        admin_after = run_async(_get_user_by_username(f"admin{suffix}"))
        assert admin_after.hashed_password == original_hash
    finally:
        _reset_bootstrap_env()


def test_bootstrap_corrects_role_drift(client):
    suffix = unique("boot3").replace("-", "")
    _set_bootstrap_env(suffix)
    try:
        run_async(_run_bootstrap())

        # Simulate role drift: someone manually reassigned the bootstrapped estimator to `user`.
        async def _drift():
            async with AsyncSessionLocal() as db:
                user_role = (await db.execute(select(Role).where(Role.name == "user"))).scalar_one()
                result = await db.execute(select(User).where(User.username == f"estimator{suffix}"))
                u = result.scalar_one()
                u.role_id = user_role.id
                await db.commit()
        run_async(_drift())

        summary = run_async(_run_bootstrap())
        assert summary.updated_roles == 1

        estimator_user = run_async(_get_user_by_username(f"estimator{suffix}"))
        assert estimator_user.role.name == "estimator"
    finally:
        _reset_bootstrap_env()


def test_bootstrap_disabled_by_default_is_noop(client):
    _reset_bootstrap_env()  # BOOTSTRAP_RBAC_USERS=false
    summary = run_async(_run_bootstrap())
    assert summary.created == 0
    assert summary.updated_roles == 0
    assert summary.skipped == 0


def test_bootstrap_missing_required_var_skips_that_account_safely(client):
    suffix = unique("boot4").replace("-", "")
    _set_bootstrap_env(suffix)
    settings.bootstrap_manager_password = ""  # incomplete config for manager
    try:
        summary = run_async(_run_bootstrap())
        assert summary.created == 2  # admin + estimator only; manager skipped due to missing password
        assert summary.skipped == 0
    finally:
        _reset_bootstrap_env()


def test_final_admin_cannot_be_demoted_or_disabled(client):
    """The last active admin must never lose administrative access via role change or disable."""
    admin_email = f"{unique('soleadmin')}@example.com"
    admin_username = unique("soleadminuser")
    from tests.conftest import create_user
    admin_id = create_user(admin_email, admin_username, "Str0ng!Passw0rd", "admin")

    # This shared test DB may already contain other admins created by earlier tests — deactivate
    # them so the account under test is genuinely the last *active* admin for this assertion.
    async def _deactivate_other_admins():
        async with AsyncSessionLocal() as db:
            admin_role = (await db.execute(select(Role).where(Role.name == "admin"))).scalar_one()
            result = await db.execute(
                select(User).where(User.role_id == admin_role.id, User.is_active.is_(True), User.id != admin_id)
            )
            for other in result.scalars().all():
                other.is_active = False
            await db.commit()
    run_async(_deactivate_other_admins())

    token = login(client, admin_email).json()["access_token"]

    demote_resp = client.patch(
        f"/api/admin/users/{admin_id}/role",
        headers={**auth_headers(token), **csrf_headers(client)}, json={"role": "manager"},
    )
    assert demote_resp.status_code in (400, 403)

    disable_resp = client.patch(
        f"/api/admin/users/{admin_id}/status",
        headers={**auth_headers(token), **csrf_headers(client)}, json={"is_active": False},
    )
    assert disable_resp.status_code in (400, 403)
