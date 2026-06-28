"""Configuration loading is resilient: a bad ``config.yaml`` never crashes the node.

``load_settings`` runs at import time, so an unhandled error there would crash
startup — and under Docker's ``restart: unless-stopped`` that becomes an endless
restart loop with nothing served. These tests pin the fail-open behaviour: a
malformed or invalid config logs and falls back to built-in defaults.
"""

from __future__ import annotations

from pathlib import Path

from horizon.config import Settings, load_settings


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_missing_config_uses_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("HORIZON_CONFIG", str(tmp_path / "does-not-exist.yaml"))
    settings = load_settings()
    assert isinstance(settings, Settings)
    assert settings.llm.provider == "ollama"


def test_malformed_yaml_falls_back_to_defaults(tmp_path, monkeypatch, caplog):
    # Broken indentation: yaml.safe_load raises. Startup must survive it.
    cfg = _write(
        tmp_path / "config.yaml",
        "llm:\n  provider: openai-compatible\n   endpoint: oops\n",
    )
    monkeypatch.setenv("HORIZON_CONFIG", str(cfg))
    with caplog.at_level("ERROR"):
        settings = load_settings()
    assert settings.llm.provider == "ollama"  # defaults, not the broken file
    assert any("Could not load configuration" in r.message for r in caplog.records)


def test_invalid_value_falls_back_to_defaults(tmp_path, monkeypatch):
    # Valid YAML, but a type pydantic cannot coerce: model_validate raises.
    cfg = _write(tmp_path / "config.yaml", "server:\n  port: not-a-number\n")
    monkeypatch.setenv("HORIZON_CONFIG", str(cfg))
    settings = load_settings()
    assert settings.server.port == 8080  # default, file ignored


def test_valid_config_is_applied(tmp_path, monkeypatch):
    cfg = _write(
        tmp_path / "config.yaml",
        "llm:\n  provider: openai-compatible\n  endpoint: http://host:8081/v1\n",
    )
    monkeypatch.setenv("HORIZON_CONFIG", str(cfg))
    settings = load_settings()
    assert settings.llm.provider == "openai-compatible"
    assert settings.llm.endpoint == "http://host:8081/v1"
