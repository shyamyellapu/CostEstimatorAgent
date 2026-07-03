"""Application settings from environment variables."""
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import List

_ENV_FILE = str(Path(__file__).parent.parent / ".env")


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/cost_estimator"
    
    # Database Pool Settings (for PostgreSQL)
    db_pool_size: int = 20
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_pool_recycle: int = 3600

    # Storage
    storage_backend: str = "local"
    local_storage_path: str = "./storage"

    # Azure (optional)
    azure_storage_connection_string: str = ""
    azure_container_name: str = "cost-estimator"

    # AWS (optional)
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    aws_bucket_name: str = ""

    # LlamaParse
    llama_parse_api_key: str = ""

    # AI
    ai_provider: str = "openai"
    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_model_fast: str = "gpt-4o-mini"
    openai_model_vision: str = "gpt-4o"
    # Groq
    groq_api_key: str = ""
    groq_model_large: str = "llama-3.3-70b-versatile"
    groq_model_fast: str = "llama-3.1-8b-instant"
    groq_vision_model: str = "llama-3.2-11b-vision-preview"
    # OpenRouter (OpenAI-compatible, free models available)
    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-oss-20b:free"
    openrouter_model_fast: str = "openai/gpt-oss-20b:free"
    openrouter_model_vision: str = "openai/gpt-oss-20b:free"

    # Google Gemini (OpenAI-compatible via AI Studio)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3-flash"
    gemini_model_fast: str = "gemini-3-flash"
    gemini_model_vision: str = "gemini-3-flash"

    # Anthropic (Claude) — used as fallback when ai_provider=openai
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"
    claude_model_drawing: str = "claude-sonnet-4-6"
    claude_drawing_pdf_mode: str = "images"  # auto | native_pdf | images
    claude_drawing_image_dpi: int = 300
    claude_drawing_standard_dpi: int = 300
    claude_drawing_dense_dpi: int = 400          # A0/A1 dense drawings
    max_llm_pages_per_batch: int = 15            # MAX_LLM_PAGES_PER_BATCH
    drawing_costing_template_path: str = "ReferenceFiles/Sample Job Costing Sheet.xlsx"

    # Company branding
    company_name: str = "C&J Gulf Equipment Manufacturing LLC"
    company_address: str = "Musaffah, Abu Dhabi, UAE"
    company_phone: str = "+971-XX-XXXXXXX"
    company_email: str = "estimation@cnjgulf.com"
    company_website: str = "www.cnjgulf.com"
    signatory_name: str = "Bilal Ahmed"
    signatory_title: str = "Cost & Estimation Engineer"

    # Cover letter template
    cover_letter_master_template_path: str = "ReferenceFiles/MASTER FABRICATION Template.docx"
    cover_letter_header_footer_docx_path: str = "ReferenceFiles/Header and Footer.docx"

    # Gmail OAuth2
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_redirect_uri: str = "http://localhost:5173/gmail/callback"

    # RFQ settings
    rfq_confidence_threshold: float = 0.75
    rfq_auto_extract: bool = True
    rfq_auto_validate: bool = True
    task_worker_poll_interval: float = 3.0
    task_worker_max_concurrent: int = 3

    # CORS
    allowed_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # App
    debug: bool = True
    log_level: str = "INFO"
    log_dir: str = "logs"
    log_max_bytes: int = 10 * 1024 * 1024  # 10 MB
    log_backup_count: int = 5

    class Config:
        env_file = _ENV_FILE
        env_file_encoding = "utf-8"
        extra = "ignore"

    def __init__(self, **values):
        super().__init__(**values)
        if not self.database_url.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "DATABASE_URL must use postgresql+asyncpg:// for production PostgreSQL support"
            )


settings = Settings()
