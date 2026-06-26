"""Typed configuration loaded from ``config.yaml`` (with sensible defaults).

horizon must run fully offline at runtime. All network endpoints configured here
(Ollama, the optional moral-core ethics hook) are local-network or opt-in, and
horizon stays functional if they are unreachable.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8080


class LLMConfig(BaseModel):
    provider: str = "ollama"  # ollama | openai-compatible
    endpoint: str = "http://ollama:11434"
    model: str = "llama3.2:3b"
    embedding_model: str = "nomic-embed-text"


class VectorDBConfig(BaseModel):
    provider: str = "chroma"
    path: str = "/data/chroma"


class RAGConfig(BaseModel):
    top_k: int = 5


class AIConfig(BaseModel):
    no_jargon_default: bool = False


class EthicsConfig(BaseModel):
    """Optional external ethics refinement (moral-core). Off by default."""

    enabled: bool = False
    endpoint: str = "http://moral-core.local/api/evaluate"


class ContentPacksConfig(BaseModel):
    dir: str = "/data/packs"


class Settings(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    data_dir: str = "/data"
    database: str = "/data/horizon.db"
    content_dir: str = "/data/content"
    llm: LLMConfig = Field(default_factory=LLMConfig)
    vectordb: VectorDBConfig = Field(default_factory=VectorDBConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    ethics: EthicsConfig = Field(default_factory=EthicsConfig)
    content_packs: ContentPacksConfig = Field(default_factory=ContentPacksConfig)


def _config_path() -> Path:
    """Resolve the config file path (``HORIZON_CONFIG`` env var overrides)."""
    return Path(os.environ.get("HORIZON_CONFIG", "config.yaml"))


def load_settings() -> Settings:
    """Load settings from ``config.yaml`` if present, else use defaults."""
    path = _config_path()
    if path.is_file():
        data = yaml.safe_load(path.read_text()) or {}
        return Settings.model_validate(data)
    return Settings()


# Singleton settings instance used across the app.
settings = load_settings()
