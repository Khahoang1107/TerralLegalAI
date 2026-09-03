"""
TerraLegalAI — Application Settings
Loads all configuration from environment variables / .env file
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 720
    cors_origins: list[str] = ["http://localhost:3000"]

    # ── Gemini ───────────────────────────────────────────────────
    gemini_api_key: str = Field(..., description="Gemini API Key")
    gemini_model: str = "gemini-2.5-flash"
    gemini_temperature: float = 0.1
    gemini_max_tokens: int = 2048

    # ── Qdrant ───────────────────────────────────────────────────
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection_name: str = "land_law_chunks"

    # ── Embedding ─────────────────────────────────────────────────
    embedding_model_name: str = "BAAI/bge-m3"
    embedding_dimension: int = 1024
    embedding_batch_size: int = 32

    # ── Reranker ──────────────────────────────────────────────────
    reranker_model_name: str = "BAAI/bge-reranker-v2-m3"
    reranker_top_k: int = 3
    reranker_enabled: bool = True

    # ── PostgreSQL ────────────────────────────────────────────────
    database_url: str = (
        "postgresql+asyncpg://terralegal_user:terralegal_pass_dev@localhost:5432/terralegal"
    )

    # ── Redis ─────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── RAG Settings ─────────────────────────────────────────────
    retrieval_top_k: int = 10
    chunk_size: int = 500
    chunk_overlap: int = 80
    similarity_threshold: float = 0.65

    # ── Langfuse (optional) ───────────────────────────────────────
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"


@lru_cache()
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()


settings = get_settings()
