"""
FastAPI main application entry point.
Registers all routers and starts the database.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from sqlalchemy import text

from app.config import settings
from app.database import engine, Base, check_database_connection

# Import all models so SQLAlchemy creates tables
from app.models import job, uploaded_file, extracted_data, costing_sheet
from app.models import quotation, cover_letter, rate_config, chat_history, audit_log

from app.api.routes import estimate, cover_letter as cl_routes, chat, boq, drawing, history, settings as settings_routes
from app.api.routes import drawing_costing as drawing_costing_routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate database connectivity and prepare runtime storage."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))

    # Ensure local storage directories exist
    Path(settings.local_storage_path).mkdir(parents=True, exist_ok=True)
    (Path(settings.local_storage_path) / "uploads").mkdir(exist_ok=True)
    (Path(settings.local_storage_path) / "outputs").mkdir(exist_ok=True)

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
