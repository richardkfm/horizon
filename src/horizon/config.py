"""Typed configuration loaded from ``config.yaml`` (with sensible defaults).

horizon must run fully offline at runtime. All network endpoints configured here
(Ollama, the optional moral-core ethics hook) are local-network or opt-in, and
horizon stays functional if they are unreachable.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger("horizon")


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
    # Plain-language answers by default: horizon's audience includes
    # non-technical neighbours, so favour accessibility. Operators can opt out
    # per request or flip this in config.yaml.
    no_jargon_default: bool = True


class AssistantConfig(BaseModel):
    """The optional local chat assistant (web UI).

    On by default. Operators who would rather not offer a chat box can turn it
    off; the rest of horizon (journeys, guides, recommend) is unaffected. The
    ``HORIZON_ASSISTANT_ENABLED`` environment variable overrides ``config.yaml``
    at request time, so it can be toggled without a restart.
    """

    enabled: bool = True


class WebConfig(BaseModel):
    """The server-rendered web UI.

    On by default. Now that horizon ships a full ``horizon-admin`` CLI (browse
    journeys/guides, recommend, ask the assistant, operator maintenance), a
    headless operator can run a node with the browser UI turned off entirely —
    leaving only the JSON API and the CLI. The ``HORIZON_WEB_ENABLED``
    environment variable overrides ``config.yaml`` at startup, so the UI can be
    toggled without editing the file.

    Disabling the UI only removes the HTML pages, admin web area, and static
    assets; the documented JSON API (``/api/...``) and ``/healthz`` stay up so
    integrations and probes are unaffected.
    """

    enabled: bool = True


class EthicsConfig(BaseModel):
    """Optional external ethics refinement (moral-core). Off by default."""

    enabled: bool = False
    endpoint: str = "http://moral-core.local/api/evaluate"


class PowerConfig(BaseModel):
    """Low-power mode for solar / battery deployments.

    When enabled, horizon skips its energy-hungry paths so the node sips power on
    a weak supply: the vector index is **not** built on startup, and the AI
    assistant answers from local content via keyword retrieval instead of running
    the local LLM. The UI also switches to a flat, e-ink-friendly stylesheet.

    The effective value also honours the ``HORIZON_LOW_POWER`` environment
    variable at request time, so an operator — or a battery-monitoring script that
    flips the node into low power when the charge drops — can toggle it without
    editing ``config.yaml`` or restarting.
    """

    low_power: bool = False


class ContentPacksConfig(BaseModel):
    dir: str = "/data/packs"


class AdminConfig(BaseModel):
    """Token-gated admin area. On by default.

    The effective token also honours the ``HORIZON_ADMIN_TOKEN`` environment
    variable at request time, so operators can enable admin without editing
    ``config.yaml``. When both this and the env var are blank, horizon
    auto-generates a random token on first run and persists it under
    ``data_dir`` (see ``horizon.web.admin``) so the area is usable out of the
    box without shipping a shared secret in the repo.
    """

    token: str = ""


class Settings(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    data_dir: str = "/data"
    database: str = "/data/horizon.db"
    content_dir: str = "/data/content"
    llm: LLMConfig = Field(default_factory=LLMConfig)
    vectordb: VectorDBConfig = Field(default_factory=VectorDBConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    assistant: AssistantConfig = Field(default_factory=AssistantConfig)
    web: WebConfig = Field(default_factory=WebConfig)
    ethics: EthicsConfig = Field(default_factory=EthicsConfig)
    power: PowerConfig = Field(default_factory=PowerConfig)
    content_packs: ContentPacksConfig = Field(default_factory=ContentPacksConfig)
    admin: AdminConfig = Field(default_factory=AdminConfig)


def _config_path() -> Path:
    """Resolve the config file path (``HORIZON_CONFIG`` env var overrides)."""
    return Path(os.environ.get("HORIZON_CONFIG", "config.yaml"))


def load_settings() -> Settings:
    """Load settings from ``config.yaml`` if present, else use defaults.

    Resilient by design: a malformed or invalid ``config.yaml`` must never take
    the node down. ``load_settings`` runs at import time, so an unhandled error
    here would crash startup — under Docker's ``restart: unless-stopped`` that is
    an endless restart loop with nothing served. Instead we log a clear, loud
    warning naming the file and the problem, and fall back to built-in defaults
    so the node still boots and serves its local content (offline-first).
    """
    path = _config_path()
    if not path.is_file():
        return Settings()
    try:
        data = yaml.safe_load(path.read_text()) or {}
        return Settings.model_validate(data)
    except Exception as exc:  # noqa: BLE001 - never crash startup on a bad config
        logger.error(
            "Could not load configuration from %s: %s. Falling back to built-in "
            "defaults so the node still starts — fix the file and restart to apply "
            "your settings.",
            path,
            exc,
        )
        return Settings()


# Singleton settings instance used across the app.
settings = load_settings()


_TRUTHY = {"1", "true", "yes", "on"}


def low_power_enabled() -> bool:
    """True when low-power mode is active.

    The ``HORIZON_LOW_POWER`` environment variable overrides ``config.yaml`` when
    set (any of ``1/true/yes/on``, case-insensitive, enables it; anything else
    disables it). This is read live, so a battery-monitoring script can toggle the
    node into and out of low power without a restart.
    """
    env = os.environ.get("HORIZON_LOW_POWER")
    if env is not None:
        return env.strip().lower() in _TRUTHY
    return settings.power.low_power


def web_enabled() -> bool:
    """True when the server-rendered web UI should be mounted.

    The ``HORIZON_WEB_ENABLED`` environment variable overrides ``config.yaml``
    when set (any of ``1/true/yes/on`` enables it; anything else disables it).
    Read at startup, when the app decides whether to mount the UI routes.
    """
    env = os.environ.get("HORIZON_WEB_ENABLED")
    if env is not None:
        return env.strip().lower() in _TRUTHY
    return settings.web.enabled


def assistant_enabled() -> bool:
    """True when the optional chat assistant (web UI) is turned on.

    The ``HORIZON_ASSISTANT_ENABLED`` environment variable overrides
    ``config.yaml`` when set, read live so an operator can toggle the assistant
    without a restart.
    """
    env = os.environ.get("HORIZON_ASSISTANT_ENABLED")
    if env is not None:
        return env.strip().lower() in _TRUTHY
    return settings.assistant.enabled
