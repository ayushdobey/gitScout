from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "GitScout"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # Security
    SECRET_KEY: str = "supersecretkey_change_me_in_production_gitscout_jwt_secret_2026"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # Database (Defaults to zero-dependency SQLite; automatically uses PostgreSQL when DATABASE_URL is set)
    DATABASE_URL: str = "sqlite:///./gitscout.db"
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_url(cls, v: str | None) -> str:
        import os
        # Fall back to zero-config SQLite if unset or if pointing to unreachable localhost in cloud/Render
        is_cloud = bool(os.environ.get("RENDER") or os.environ.get("VERCEL") or os.environ.get("PORT"))
        if not v or v.strip() == "":
            return "sqlite:///./gitscout.db"
        if is_cloud and ("localhost" in v or "127.0.0.1" in v):
            return "sqlite:///./gitscout.db"
        # Fix Render/Heroku legacy postgres:// scheme for SQLAlchemy 2.0
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+psycopg2://", 1)
        if v.startswith("postgresql://") and not v.startswith("postgresql+psycopg2://"):
            return v.replace("postgresql://", "postgresql+psycopg2://", 1)
        return v
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Ingestion & Limits
    GITHUB_TOKEN: str | None = None
    MAX_REPO_SIZE_MB: int = 50
    MAX_FILES_COUNT: int = 2500
    RATE_LIMIT_PER_MINUTE: int = 30

    # Code Intelligence & AI
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384
    LLM_PROVIDER: str = "gemini"  # "gemini" | "openai" | "mock"
    GEMINI_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()

