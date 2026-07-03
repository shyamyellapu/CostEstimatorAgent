"""
FastAPI main application entry point.
Registers all routers and starts the database.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))

    # Ensure local storage directories exist
    Path(settings.local_storage_path).mkdir(parents=True, exist_ok=True)
    (Path(settings.local_storage_path) / "uploads").mkdir(exist_ok=True)
    (Path(settings.local_storage_path) / "outputs").mkdir(exist_ok=True)
    (Path(settings.local_storage_path) / "rfq_uploads").mkdir(exist_ok=True)

    # Start background task queue worker
    import asyncio
    from app.tasks.rfq_tasks import run_worker
    asyncio.create_task(
        run_worker(
            poll_interval=settings.task_worker_poll_interval,
            max_concurrent=settings.task_worker_max_concurrent,
        )
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
