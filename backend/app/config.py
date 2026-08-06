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
    gemini_model: str = "gemini-3.1-flash-lite"
    gemini_model_fast: str = "gemini-3.1-flash-lite"
    gemini_model_vision: str = "gemini-3.1-flash-lite"

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
    # NOTE: kept as a plain str (not List[str]) — pydantic-settings' EnvSettingsSource tries to
    # json.loads() env values for List[...] fields *before* any field_validator runs, so a plain
    # comma-separated ALLOWED_ORIGINS value (e.g. set via Azure App Service > Configuration) makes
    # the whole app fail to import with a SettingsError, crash-looping every gunicorn worker.
    allowed_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,"
        "http://127.0.0.1:3000,http://127.0.0.1:8000,"
        "https://red-hill-090bbae00.7.azurestaticapps.net"
    )

    @property
    def allowed_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    # App
    debug: bool = True
    log_level: str = "INFO"
    log_dir: str = "logs"
    log_max_bytes: int = 10 * 1024 * 1024  # 10 MB
    log_backup_count: int = 5
    environment: str = "development"  # development | production

    # ── Authentication ──────────────────────────────────────────────────────
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "cost-estimator-api"
    jwt_audience: str = "cost-estimator-web"

    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    refresh_cookie_name: str = "cost_estimator_refresh"
    csrf_cookie_name: str = "cost_estimator_csrf"

    cookie_secure: bool = True
    cookie_samesite: str = "lax"  # lax | strict | none
    cookie_domain: str = ""
    cookie_path: str = "/api/auth"

    frontend_url: str = "http://localhost:5173"

    password_reset_expire_minutes: int = 30
    max_login_attempts: int = 5
    account_lock_minutes: int = 15

    # Public self-registration default role (server-side; never trust client-supplied role)
    default_signup_role: str = "user"

    # Retention (days) for the background auth-data cleanup task
    auth_cleanup_interval_hours: float = 6.0
    revoked_token_retention_days: int = 30
    audit_log_retention_days: int = 180

    # ── RBAC system-account bootstrap (one-time, idempotent — see rbac_bootstrap_service) ────
    bootstrap_rbac_users: bool = False
    bootstrap_update_existing_passwords: bool = False

    bootstrap_admin_email: str = ""
    bootstrap_admin_username: str = ""
    bootstrap_admin_full_name: str = ""
    bootstrap_admin_password: str = ""

    bootstrap_manager_email: str = ""
    bootstrap_manager_username: str = ""
    bootstrap_manager_full_name: str = ""
    bootstrap_manager_password: str = ""

    bootstrap_estimator_email: str = ""
    bootstrap_estimator_username: str = ""
    bootstrap_estimator_full_name: str = ""
    bootstrap_estimator_password: str = ""

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
        if self.environment.lower() == "production":
            if not self.jwt_secret_key or len(self.jwt_secret_key) < 32:
                raise ValueError(
                    "JWT_SECRET_KEY must be set to a random string of at least 32 characters "
                    "in production (e.g. `python -c \"import secrets; print(secrets.token_urlsafe(64))\"`)."
                )
        elif not self.jwt_secret_key:
            # Development convenience only — never used when environment=production.
            import secrets
            self.jwt_secret_key = secrets.token_urlsafe(64)


settings = Settings()
