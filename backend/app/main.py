"""
FastAPI main application entry point.
Registers all routers and starts the database.
"""
from contextlib import asynccontextmanager
import logging
import time
import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from sqlalchemy import text

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

from app.api.routes import estimate, cover_letter as cl_routes, chat, boq, drawing, history, settings as settings_routes
from app.api.routes import drawing_costing as drawing_costing_routes
from app.api.routes import rfq as rfq_routes
from app.api.routes import gmail as gmail_routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate database connectivity and prepare runtime storage."""
    logger.info("Starting Cost Estimator API")
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("Database connectivity verified")
    """Create all DB tables on startup."""
    # async with engine.begin() as conn:
    #     await conn.run_sync(lambda conn: Base.metadata.create_all(conn, checkfirst=True))

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
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled exceptions — log full traceback and return 500."""
    logger.critical(
        "unhandled_exception method=%s path=%s exc_type=%s exc=%s\n%s",
        request.method,
        request.url.path,
        type(exc).__name__,
        exc,
        traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please check server logs."},
    )

# API Routers
app.include_router(estimate.router,       prefix="/api/estimate",      tags=["Estimate"])
app.include_router(cl_routes.router,      prefix="/api/cover-letter",  tags=["Cover Letter"])
app.include_router(chat.router,           prefix="/api/chat",          tags=["Chat"])
app.include_router(boq.router,            prefix="/api/boq",           tags=["BOQ"])
app.include_router(drawing.router,        prefix="/api/drawing",       tags=["Drawing"])
app.include_router(history.router,        prefix="/api/history",       tags=["History"])
app.include_router(settings_routes.router,    prefix="/api/settings",         tags=["Settings"])
app.include_router(drawing_costing_routes.router, prefix="/api/drawing-costing", tags=["Drawing Costing"])
app.include_router(rfq_routes.router,             prefix="/api/rfq",            tags=["RFQ"])
app.include_router(gmail_routes.router,           prefix="/api/gmail",          tags=["Gmail"])

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
    provider = settings.ai_provider.lower()
    if provider == "openai":
        return {
            "provider": "openai",
            "primary_model": settings.openai_model,
            "fast_model": settings.openai_model_fast,
            "vision_model": settings.openai_model_vision,
            "fallback_provider": "claude",
            "fallback_model": settings.claude_model,
        }
    if provider == "claude":
        return {
            "provider": "claude",
            "primary_model": settings.claude_model,
            "fallback_provider": None,
            "fallback_model": None,
        }
    # groq
    return {
        "provider": "groq",
        "primary_model": settings.groq_model_large,
        "fast_model": settings.groq_model_fast,
        "vision_model": settings.groq_vision_model,
        "fallback_provider": None,
        "fallback_model": None,
    }


@app.get("/")
async def root():
    return {
        "message": "Cost Estimator AI Agent API",
        "docs": "/docs",
        "health": "/health",
    }
