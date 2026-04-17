"""
config.py — Centralised application settings via pydantic-settings.
All values are read from environment variables / .env file.
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "AI Support Automation"
    app_env: str = "production"
    app_host: str = "0.0.0.0"
    app_port: int = 8000  # overridden by PORT env var on Render

    @property
    def port(self) -> int:
        import os
        return int(os.environ.get("PORT", self.app_port))
    log_level: str = "INFO"

    # NVIDIA LLM API
    nvidia_api_key: str = "your-nvidia-api-key-here"
    nvidia_model: str = "google/gemma-3-27b-it"
    nvidia_max_tokens: int = 512
    nvidia_temperature: float = 0.20
    nvidia_timeout: int = 60

    # Embeddings
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_device: str = "cpu"

    # ChromaDB (replaces FAISS — pip-friendly, no compilation required)
    chroma_persist_dir: str = "./data/chroma_db"
    retriever_top_k: int = 5

    # Data
    knowledge_base_dir: str = "./data/knowledge_base"
    upload_dir: str = "./data/uploads"

    # Security
    api_secret_key: str = "change-this-in-production"
    allowed_origins: str = "*"

    def ensure_directories(self) -> None:
        """Create required directories if they don't exist."""
        for path_str in [
            self.chroma_persist_dir,
            self.knowledge_base_dir,
            self.upload_dir,
        ]:
            Path(path_str).mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    settings = Settings()
    settings.ensure_directories()
    return settings
