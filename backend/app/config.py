"""Application settings from environment variables."""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite+aiosqlite:///./cost_estimator.db"

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
    ai_provider: str = "groq"
    groq_api_key: str = ""
    groq_model_large: str = "llama-3.3-70b-versatile"
    groq_model_fast: str = "llama-3.1-8b-instant"
    groq_vision_model: str = "llama-3.2-11b-vision-preview"
    anthropic_api_key: str = ""
    claude_model: str = "claude-3-5-sonnet-20241022"

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

    # CORS
    allowed_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # App
    debug: bool = True
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
