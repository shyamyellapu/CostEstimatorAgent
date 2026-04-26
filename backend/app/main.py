"""
FastAPI main application entry point.
Registers all routers and starts the database.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.config import settings
from app.database import engine, Base

# Import all models so SQLAlchemy creates tables
from app.models import job, uploaded_file, extracted_data, costing_sheet
from app.models import quotation, cover_letter, rate_config, chat_history, audit_log

from app.api.routes import estimate, cover_letter as cl_routes, chat, boq, drawing, history, settings as settings_routes
from app.api.routes import drawing_costing as drawing_costing_routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create all DB tables on startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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


@app.get("/")
async def root():
    return {
        "message": "Cost Estimator AI Agent API",
        "docs": "/docs",
        "health": "/health",
    }
