"""
TRACE — Application Configuration
Reads all config from environment variables via pydantic-settings.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # ─── PostgreSQL ───────────────────────────────────────
    database_url: str = "postgresql://trace:trace_dev_password@localhost:5432/trace"

    # ─── Neo4j ────────────────────────────────────────────
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "trace_neo4j_dev"

    # ─── JWT ──────────────────────────────────────────────
    jwt_secret: str = "change-this-to-a-random-64-char-string-in-production"
    jwt_refresh_secret: str = "change-this-refresh-secret-in-production-too"
    jwt_expiry_minutes: int = 30
    jwt_refresh_expiry_days: int = 7

    # ─── LLM (optional) ──────────────────────────────────
    llm_api_base: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_model: str = "gpt-4o-mini"

    # ─── spaCy ────────────────────────────────────────────
    spacy_model: str = "en_core_web_sm"

    # ─── File Storage ─────────────────────────────────────
    upload_dir: str = "/uploads"
    migrations_dir: str = "db/postgres/migrations"

    # ─── CORS ─────────────────────────────────────────────
    frontend_url: str = "http://localhost:5173"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
