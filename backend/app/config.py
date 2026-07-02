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
    # Anthropic (Claude) — used as fallback when ai_provider=openai
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"
    claude_model_drawing: str = "claude-sonnet-4-6"
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
    # gmail_redirect_uri: str = "http://localhost:5173/gmail/callback"
    gmail_redirect_uri: str = "https://red-hill-090bbae00.7.azurestaticapps.net/gmail/callback"

    # RFQ settings
    rfq_confidence_threshold: float = 0.75
    rfq_auto_extract: bool = True
    rfq_auto_validate: bool = True
    task_worker_poll_interval: float = 3.0
    task_worker_max_concurrent: int = 3

    # CORS
    allowed_origins: List[str] = [
        # Local development
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        # LAN access (e.g. testing from another device on the same network)
        "http://192.168.5.187:5173",
        "http://192.168.5.187:3000",
        # Azure deployed frontend
        "https://red-hill-090bbae00.7.azurestaticapps.net",
    ]

    # App
    debug: bool = True
    log_level: str = "INFO"
    log_dir: str = "./logs"
    log_max_bytes: int = 10 * 1024 * 1024   # 10 MB per rotating file
    log_backup_count: int = 5               # keep 5 backup files

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
