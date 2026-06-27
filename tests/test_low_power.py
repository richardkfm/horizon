"""Low-power mode tests.

Low-power mode targets solar / battery nodes: it must skip the energy-hungry
paths (vector index build, LLM generation) while keeping the offline-first
contract — the API still returns 200 with cited local guides, and the UI still
renders. The mode is driven by the ``HORIZON_LOW_POWER`` env override so tests
can toggle it without touching ``config.yaml``.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from horizon import config
from horizon.main import app


@pytest.fixture
def low_power(monkeypatch):
    """Enable low-power mode via the env override for the duration of a test."""
    monkeypatch.setenv("HORIZON_LOW_POWER", "1")
    return None


def test_low_power_enabled_env_override(monkeypatch):
    monkeypatch.setenv("HORIZON_LOW_POWER", "on")
    assert config.low_power_enabled() is True
    monkeypatch.setenv("HORIZON_LOW_POWER", "0")
    assert config.low_power_enabled() is False


def test_low_power_defaults_off(monkeypatch):
    monkeypatch.delenv("HORIZON_LOW_POWER", raising=False)
    assert config.low_power_enabled() is False


def test_low_power_skips_model_but_still_cites(low_power, monkeypatch):
    """In low-power mode the model is never called, yet citations still resolve."""

    def boom(*args, **kwargs):  # pragma: no cover - must not be reached
        raise AssertionError("generate() must not run in low-power mode")

    monkeypatch.setattr("horizon.api.ai.generate", boom)

    with TestClient(app) as client:
        resp = client.post(
            "/api/ai/answer",
            json={"question": "how do I make water safe to drink"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "water-slow-sand-filter" in data["citations"]
    assert "low-power mode" in data["answer"].lower()


def test_normal_mode_still_uses_model(monkeypatch):
    """Sanity check: with low power off, generation is used when available."""
    monkeypatch.delenv("HORIZON_LOW_POWER", raising=False)
    monkeypatch.setattr(
        "horizon.api.ai.generate",
        lambda system, prompt, *, no_jargon=False: "Boil it [water-slow-sand-filter].",
    )
    with TestClient(app) as client:
        resp = client.post(
            "/api/ai/answer",
            json={"question": "how do I make water safe to drink"},
        )
    assert resp.json()["answer"].startswith("Boil it")


def test_low_power_banner_and_body_class_render(low_power):
    with TestClient(app) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert 'class="low-power"' in resp.text
    assert "low-power-banner" in resp.text
    # The non-essential Alpine bundle is not loaded in low-power mode.
    assert "alpine.min.js" not in resp.text
    # htmx still drives the assistant form.
    assert "htmx.min.js" in resp.text


def test_normal_mode_has_no_banner(monkeypatch):
    monkeypatch.delenv("HORIZON_LOW_POWER", raising=False)
    with TestClient(app) as client:
        resp = client.get("/")
    assert "low-power-banner" not in resp.text
    assert "alpine.min.js" in resp.text


def test_assistant_page_shows_low_power_note(low_power):
    with TestClient(app) as client:
        resp = client.get("/assistant")
    assert resp.status_code == 200
    assert "Low-power mode is on" in resp.text
