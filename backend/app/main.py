"""
FastAPI main application entry point.
Registers all routers and starts the database.
"""
import logging
from contextlib import asynccontextmanager
import logging
import time
import traceback

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from sqlalchemy import text

# ── Logging configuration ─────────────────────────────────────────────────────
import logging.handlers
from pathlib import Path as _Path

_LOG_DIR = _Path(__file__).parent.parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)

_fmt = logging.Formatter("%(asctime)s  %(levelname)-8s  %(name)s - %(message)s")

# Console handler
_console = logging.StreamHandler()
_console.setFormatter(_fmt)

# Rotating file handler — 5 MB per file, keep 5 backups
_file_handler = logging.handlers.RotatingFileHandler(
    _LOG_DIR / "app.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
)
_file_handler.setFormatter(_fmt)

logging.basicConfig(level=logging.INFO, handlers=[_console, _file_handler])

# SQLAlchemy echoes every SQL statement at INFO — suppress to WARNING
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
# Uvicorn access log is already handled by uvicorn itself
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
# httpx logs every request — suppress
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
# WatchFiles reload noise
logging.getLogger("watchfiles").setLevel(logging.WARNING)

from app.config import settings
from app.database import engine, Base, check_database_connection
from app.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

# Import all models so SQLAlchemy creates tables
from app.models import job, uploaded_file, extracted_data, costing_sheet
from app.models import quotation, cover_letter, rate_config, chat_history, audit_log
from app.models import (
    GmailCredential, RFQEmail, RFQAttachment, RFQRecord,
    RFQLineItem, ValidationResult, ExtractionReview, TaskQueue, MaterialMaster,
)
from app.models import (
    Role, Permission, User, RefreshToken, UserSession,
    AuthAuditLog, PasswordResetToken,
)

from app.api.routes import estimate, cover_letter as cl_routes, chat, boq, drawing, history, settings as settings_routes
from app.api.routes import drawing_costing as drawing_costing_routes
from app.api.routes import rfq as rfq_routes
from app.api.routes import gmail as gmail_routes
from app.api.routes import auth as auth_routes
from app.api.routes import admin_users as admin_users_routes
from app.api.routes import sessions as admin_sessions_routes
from app.api.routes import audit_logs as audit_logs_routes
from app.api.dependencies.auth import get_current_user
from app.api.dependencies.permissions import require_permission
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.core.exceptions import AppError


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate database connectivity and prepare runtime storage."""
    logger.info("Starting Cost Estimator API")
    # Bounded + non-fatal: an unreachable DB (e.g. firewall blocking the App Service's
    # outbound IP) must not hang the sole gunicorn worker forever at startup — that
    # leaves every request (including CORS preflights) returning a bare 503, which the
    # browser then misreports as a CORS failure instead of the real connectivity issue.
    try:
        import asyncio as _asyncio
        async with engine.connect() as conn:
            await _asyncio.wait_for(conn.execute(text("SELECT 1")), timeout=10)
        logger.info("Database connectivity verified")
    except Exception:
        logger.exception("Database connectivity check failed at startup (continuing)")

    # Run Alembic migrations to ensure schema is up to date
    try:
        import asyncio
        from alembic.config import Config as AlembicConfig
        from alembic import command as alembic_command
        from pathlib import Path as _APath
        _alembic_cfg = AlembicConfig(str(_APath(__file__).parent.parent / "alembic.ini"))
        await asyncio.to_thread(alembic_command.upgrade, _alembic_cfg, "head")
        logger.info("Alembic migrations applied successfully")
    except Exception as _exc:
        logger.warning("Alembic migration failed (continuing): %s", _exc)

    # One-time, idempotent RBAC system-account bootstrap (admin/manager/estimator). No-op unless
    # BOOTSTRAP_RBAC_USERS=true. A Postgres advisory lock serializes concurrent Gunicorn workers.
    if settings.bootstrap_rbac_users:
        try:
            from app.database import AsyncSessionLocal
            from app.services.rbac_bootstrap_service import bootstrap_rbac_users
            async with AsyncSessionLocal() as _db:
                _summary = await bootstrap_rbac_users(_db, user_agent="startup-bootstrap")
            logger.info(
                "RBAC bootstrap on startup: created=%d updated_roles=%d skipped=%d",
                _summary.created, _summary.updated_roles, _summary.skipped,
            )
        except Exception:
            logger.exception("RBAC bootstrap on startup failed (continuing)")

    # Ensure local storage directories exist
    Path(settings.local_storage_path).mkdir(parents=True, exist_ok=True)
    (Path(settings.local_storage_path) / "uploads").mkdir(exist_ok=True)
    (Path(settings.local_storage_path) / "outputs").mkdir(exist_ok=True)
    (Path(settings.local_storage_path) / "rfq_uploads").mkdir(exist_ok=True)
    logger.info("Storage directories ready at %s", settings.local_storage_path)

    # Start background task queue worker
    import asyncio
    from app.tasks.rfq_tasks import run_worker
    asyncio.create_task(
        run_worker(
            poll_interval=settings.task_worker_poll_interval,
            max_concurrent=settings.task_worker_max_concurrent,
        )
    )
    logger.info(
        "Task worker scheduled poll_interval=%.1fs max_concurrent=%d",
        settings.task_worker_poll_interval,
        settings.task_worker_max_concurrent,
    )

    # Background auth-data cleanup (expired refresh tokens, password-reset tokens, stale
    # sessions, old audit logs). See app.tasks.auth_cleanup module docstring for the
    # multi-worker/production scheduling caveat.
    from app.tasks.auth_cleanup import start_scheduler as start_auth_cleanup_scheduler
    start_auth_cleanup_scheduler()

    yield


app = FastAPI(
    title="Cost Estimator AI Agent",
    description="AI-powered cost estimation for fabrication, EPC, structural, and piping industries",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIDMiddleware)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    client_ip = request.client.host if request.client else "unknown"
    logger.debug(
        "request_start method=%s path=%s client=%s",
        request.method,
        request.url.path,
        client_ip,
    )
    try:
        response = await call_next(request)
    except Exception as exc:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.error(
            "request_unhandled_exception method=%s path=%s client=%s duration_ms=%.1f "
            "exc_type=%s exc=%s\n%s",
            request.method,
            request.url.path,
            client_ip,
            duration_ms,
            type(exc).__name__,
            exc,
            traceback.format_exc(),
        )
        raise

    duration_ms = (time.perf_counter() - start) * 1000
    # Log all 4xx/5xx as warnings/errors; log API routes at INFO; skip static/health noise
    if response.status_code >= 500:
        logger.error(
            "request_server_error method=%s path=%s status=%d client=%s duration_ms=%.1f",
            request.method, request.url.path, response.status_code, client_ip, duration_ms,
        )
    elif response.status_code >= 400:
        logger.warning(
            "request_client_error method=%s path=%s status=%d client=%s duration_ms=%.1f",
            request.method, request.url.path, response.status_code, client_ip, duration_ms,
        )
    elif request.url.path.startswith("/api/") or request.url.path.startswith("/health"):
        logger.info(
            "request_complete method=%s path=%s status=%d client=%s duration_ms=%.1f",
            request.method, request.url.path, response.status_code, client_ip, duration_ms,
        )
    else:
        logger.debug(
            "request_complete method=%s path=%s status=%d client=%s duration_ms=%.1f",
            request.method, request.url.path, response.status_code, client_ip, duration_ms,
        )
    return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    """Consistent error envelope for all application/auth errors — never leaks internals."""
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message, "request_id": request_id}},
        headers=exc.headers,
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled exceptions — log full traceback and return 500.

    NOTE: FastAPI/Starlette registers handlers for the bare `Exception` class on the outermost
    `ServerErrorMiddleware`, which sits OUTSIDE `CORSMiddleware`. That means a response built here
    never passes back through `CORSMiddleware` and won't get `Access-Control-Allow-Origin`
    headers — the browser then reports a misleading "blocked by CORS policy" error that hides the
    real 500. We add the CORS headers manually so the frontend can actually see the error.
    """
    logger.critical(
        "unhandled_exception method=%s path=%s exc_type=%s exc=%s\n%s",
        request.method,
        request.url.path,
        type(exc).__name__,
        exc,
        traceback.format_exc(),
    )
    headers = {}
    origin = request.headers.get("origin")
    if origin and origin in settings.allowed_origins:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
        headers["Vary"] = "Origin"
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please check server logs."},
        headers=headers,
    )

# API Routers
app.include_router(auth_routes.router,            prefix="/api/auth",           tags=["Auth"])
app.include_router(admin_users_routes.router,     prefix="/api/admin",         tags=["Admin"])
app.include_router(admin_sessions_routes.router,  prefix="/api/admin",         tags=["Admin"])
app.include_router(audit_logs_routes.router,      prefix="/api/admin",         tags=["Admin"])

app.include_router(estimate.router,       prefix="/api/estimate",      tags=["Estimate"])
app.include_router(cl_routes.router,      prefix="/api/cover-letter",  tags=["Cover Letter"],
                   dependencies=[Depends(require_permission("cover_letters.generate"))])
app.include_router(chat.router,           prefix="/api/chat",          tags=["Chat"],
                   dependencies=[Depends(get_current_user)])
app.include_router(boq.router,            prefix="/api/boq",           tags=["BOQ"],
                   dependencies=[Depends(require_permission("boq.parse"))])
app.include_router(drawing.router,        prefix="/api/drawing",       tags=["Drawing"],
                   dependencies=[Depends(require_permission("drawings.process"))])
app.include_router(history.router,        prefix="/api/history",       tags=["History"],
                   dependencies=[Depends(require_permission("job_history.read"))])
app.include_router(settings_routes.router,    prefix="/api/settings",         tags=["Settings"])
app.include_router(drawing_costing_routes.router, prefix="/api/drawing-costing", tags=["Drawing Costing"],
                   dependencies=[Depends(require_permission("drawings.process"))])
app.include_router(rfq_routes.router,             prefix="/api/rfq",            tags=["RFQ"],
                   dependencies=[Depends(require_permission("rfq.read"))])
app.include_router(gmail_routes.router,           prefix="/api/gmail",          tags=["Gmail"],
                   dependencies=[Depends(require_permission("rfq.manage"))])

# Static files for local storage
storage_path = Path(settings.local_storage_path)
if storage_path.exists():
    app.mount("/storage", StaticFiles(directory=str(storage_path)), name="storage")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/health/db")
async def health_db():
    return await check_database_connection()


@app.get("/api/ai/info")
async def ai_info():
    """Return the currently active AI provider and model configuration."""
    provider = settings.ai_provider.strip().lower()

    MODEL_MAP = {
        "openai":      {"primary_model": settings.openai_model,      "fast_model": settings.openai_model_fast,      "vision_model": settings.openai_model_vision},
        "claude":      {"primary_model": settings.claude_model,       "fast_model": settings.claude_model,           "vision_model": settings.claude_model},
        "groq":        {"primary_model": settings.groq_model_large,   "fast_model": settings.groq_model_fast,        "vision_model": settings.groq_vision_model},
        "openrouter":  {"primary_model": settings.openrouter_model,   "fast_model": settings.openrouter_model_fast,  "vision_model": settings.openrouter_model_vision},
        "gemini":      {"primary_model": settings.gemini_model,       "fast_model": settings.gemini_model_fast,      "vision_model": settings.gemini_model_vision},
    }

    models = MODEL_MAP.get(provider, {"primary_model": "unknown", "fast_model": "unknown", "vision_model": "unknown"})
    return {
        "provider": provider,
        **models,
        "fallback_provider": None,
        "fallback_model": None,
    }


@app.get("/api/company/info")
async def company_info():
    """Return company branding config from .env for display in Settings UI."""
    return {
        "company_name":    settings.company_name,
        "company_address": settings.company_address,
        "company_phone":   settings.company_phone,
        "company_email":   settings.company_email,
        "company_website": settings.company_website,
        "signatory_name":  settings.signatory_name,
        "signatory_title": settings.signatory_title,
    }


@app.get("/")
async def root():
    return {
        "message": "Cost Estimator AI Agent API",
        "docs": "/docs",
        "health": "/health",
    }
