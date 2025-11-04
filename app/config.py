# app/config.py
from __future__ import annotations
from pathlib import Path
from typing import Literal, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

EmbedProvider = Literal["stub", "cohere"]

class Settings(BaseSettings):
    # --- Embeddings ---
    embedding_provider: EmbedProvider = Field(default="stub")   # stub | cohere
    embedding_dim: int = 384

    cohere_api_key: Optional[str] = None
    cohere_model: str = "embed-english-v3.0"        # or "embed-multilingual-v3.0"
    cohere_input_type: str = "search_query"         # "search_query" | "search_document" | ...
    cohere_truncate: str = "END"                    # "NONE" | "START" | "END"

    # --- Temporal ---
    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"

    # --- Persistence (optional) ---
    # disk_store_root: str = "/data"

    # --- Logging (optional) ---
    log_level: str = "INFO"

    # Tell Pydantic Settings to load .env automatically
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",        # ignore unexpected envs
    )

    @field_validator("embedding_provider")
    @classmethod
    def _validate_provider(cls, v: str) -> str:
        v = v.lower()
        if v not in ("stub", "cohere"):
            raise ValueError("EMBEDDING_PROVIDER must be 'stub' or 'cohere'")
        return v

# Singleton
settings = Settings()
