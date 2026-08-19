"""Shared pytest fixtures for the authentication test suite.

Requires a dedicated, disposable PostgreSQL database (the app enforces postgresql+asyncpg://
everywhere, so SQLite/aiosqlite cannot be substituted). Point it at a throwaway database — never
the development or production database — via TEST_DATABASE_URL, e.g.:

    postgresql+asyncpg://postgres:0000@localhost:5432/cost_estimator_auth_test

Run with:
    cd CostEstimatorAgent/backend
    python -m pytest tests/ -v
"""
import asyncio
import os

# ── Environment MUST be set before any `app.*` module is imported ──────────────────────────────
os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get("TEST_DATABASE_URL", "postgresql+asyncpg://postgres:0000@localhost:5432/cost_estimator_auth_test"),
)
os.environ["ENVIRONMENT"] = "development"
os.environ["JWT_SECRET_KEY"] = "pytest-only-secret-key-do-not-use-in-any-real-environment-please"
os.environ["COOKIE_SECURE"] = "false"
os.environ["MAX_LOGIN_ATTEMPTS"] = "5"
os.environ["ACCOUNT_LOCK_MINUTES"] = "15"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy.pool import NullPool

import app.database as database_module
from app.auth.passwords import hash_password
from app.database import Base
from app.models import Permission, Role, User

# Our manual `run_async()` test helper and the TestClient's own internal event loop are different
# asyncio event loops. The app's default pooled engine keeps asyncpg connections alive across
# checkouts, and a connection created under one loop cannot be reused under another ("Event loop
# is closed"). NullPool opens a fresh physical connection per checkout instead, which is safe
# across loops — correctness over pooling performance, perfectly fine for a test suite.
database_module.engine = create_async_engine(database_module.settings.database_url, poolclass=NullPool)
database_module.AsyncSessionLocal = async_sessionmaker(
    database_module.engine, class_=AsyncSession, expire_on_commit=False, autocommit=False, autoflush=False,
)
engine = database_module.engine
AsyncSessionLocal = database_module.AsyncSessionLocal


# Mirrors the default RBAC seed in alembic/versions/0003_auth_system.py. Kept as a small,
# self-contained duplicate here so the test suite can bootstrap a clean schema directly via
# SQLAlchemy metadata without depending on the (pre-existing, unrelated) migration-0001-vs-0002
# create_all/op.create_table overlap issue — see session notes for details.
PERMISSION_DEFS = [
    ("dashboard.read", "View dashboard", "dashboard", "read"),
    ("estimates.create", "Create estimates", "estimates", "create"),
    ("estimates.read", "View estimates", "estimates", "read"),
    ("estimates.update", "Edit estimates", "estimates", "update"),
    ("estimates.delete", "Delete estimates", "estimates", "delete"),
    ("drawings.process", "Process drawings", "drawings", "process"),
    ("boq.parse", "Parse BOQ documents", "boq", "parse"),
    ("quotations.generate", "Generate quotations", "quotations", "generate"),
    ("quotations.read", "View quotations", "quotations", "read"),
    ("excel.generate", "Generate Excel sheets", "excel", "generate"),
    ("cover_letters.generate", "Generate cover letters", "cover_letters", "generate"),
    ("rfq.read", "View RFQ inbox", "rfq", "read"),
    ("rfq.manage", "Manage RFQ records", "rfq", "manage"),
    ("job_history.read", "View job history", "job_history", "read"),
    ("users.read", "View users", "users", "read"),
    ("users.create", "Create users", "users", "create"),
    ("users.update", "Update users", "users", "update"),
    ("users.disable", "Disable/activate users", "users", "disable"),
    ("users.assign_role", "Assign user roles", "users", "assign_role"),
    ("sessions.read", "View sessions", "sessions", "read"),
    ("sessions.revoke", "Revoke sessions", "sessions", "revoke"),
    ("settings.read", "View settings", "settings", "read"),
    ("settings.update", "Update settings", "settings", "update"),
    ("audit_logs.read", "View audit logs", "audit_logs", "read"),
]
ROLE_PERMISSIONS = {
    "admin": [code for code, *_ in PERMISSION_DEFS],
    "manager": [
        "dashboard.read", "estimates.create", "estimates.read", "estimates.update",
        "drawings.process", "boq.parse", "quotations.generate", "quotations.read",
        "excel.generate", "cover_letters.generate", "rfq.read", "rfq.manage",
        "job_history.read", "users.read", "sessions.read", "settings.read",
    ],
    "estimator": [
        "dashboard.read", "estimates.create", "estimates.read", "estimates.update",
        "drawings.process", "boq.parse", "quotations.generate", "quotations.read",
        "excel.generate", "cover_letters.generate", "rfq.read", "job_history.read",
    ],
    "user": ["dashboard.read", "estimates.read", "quotations.read", "job_history.read"],
}


async def _bootstrap_schema_and_seed():
    # Import every model module so all tables are registered on Base.metadata before create_all.
    import app.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        permissions_by_code = {}
        for code, name, resource, action in PERMISSION_DEFS:
            perm = Permission(code=code, name=name, resource=resource, action=action)
            db.add(perm)
            permissions_by_code[code] = perm
        await db.flush()

        for role_name, codes in ROLE_PERMISSIONS.items():
            role = Role(name=role_name, description=f"{role_name} role", is_system_role=True)
            role.permissions = [permissions_by_code[c] for c in codes]
            db.add(role)

        await db.commit()


def run_async(coro):
    """Run a one-off async DB operation from synchronous test code."""
    return asyncio.run(coro)


@pytest.fixture(scope="session")
def client():
    run_async(_bootstrap_schema_and_seed())
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """The in-memory rate limiter is a process-wide singleton — reset it before every test so
    one test's requests never exhaust another test's quota."""
    from app.core.rate_limit import rate_limiter
    rate_limiter._hits.clear()
    yield
    rate_limiter._hits.clear()


@pytest.fixture(autouse=True)
def _clean_cookie_jar(client):
    """The TestClient (and its cookie jar) is shared across the whole session for speed. Tests
    that manually inject cookies with slightly different domain/path attributes than a real
    Set-Cookie response can otherwise leave multiple same-name entries behind, which makes
    httpx.Cookies.get() raise CookieConflict for every later test. Starting each test with an
    empty jar keeps tests independent."""
    client.cookies.clear()
    yield
    client.cookies.clear()


async def _create_user(email: str, username: str, password: str, role_name: str, is_active: bool = True) -> str:
    async with AsyncSessionLocal() as db:
        role = (await db.execute(select(Role).where(Role.name == role_name))).scalar_one()
        user = User(
            email=email, username=username, full_name=username.title(),
            hashed_password=hash_password(password), role_id=role.id,
            is_active=is_active, is_verified=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return str(user.id)


def create_user(email: str, username: str, password: str, role_name: str, is_active: bool = True) -> str:
    """Create a user directly in the DB with a specific role — bypasses the public registration
    endpoint (which always assigns the default self-registration role) so RBAC tests can exercise
    admin/manager/estimator/user accounts without a bootstrap chicken-and-egg problem."""
    return run_async(_create_user(email, username, password, role_name, is_active))


@pytest.fixture
def strong_password() -> str:
    return "Str0ng!Passw0rd"
