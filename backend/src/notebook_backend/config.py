from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = (
        "postgresql+psycopg://notebook:local_notebook_password@localhost:5433/notebook"
    )
    cors_origins: list[str] = ["http://localhost:3000"]
    ai_mode: Literal["rag", "extractive"] = "rag"
    groq_api_key: SecretStr = SecretStr("")
    groq_model: str = "openai/gpt-oss-20b"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    model_cache_path: str = ".models"
    qdrant_path: str = ".qdrant"
    qdrant_url: str | None = None
    rag_top_k: int = 6
    rag_min_score: float = 0.35
    max_upload_bytes: int = 10 * 1024 * 1024


settings = Settings()
