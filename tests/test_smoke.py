"""Smoke tests: the app imports and registers its routes, and the landing page
renders with no external services running."""

from __future__ import annotations

from fastapi.testclient import TestClient

from horizon.main import app


def _routes() -> set[str]:
    """All registered API paths, via the OpenAPI schema."""
    return set(app.openapi()["paths"].keys())


def test_knowledge_api_routes_registered():
    paths = _routes()
    assert "/api/journeys" in paths
    assert "/api/journeys/{journey_id}" in paths
    assert "/api/guides/{guide_id}" in paths
    assert "/api/recommend" in paths
    assert "/api/ai/answer" in paths


def test_healthz_ok():
    client = TestClient(app)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_landing_page_renders():
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    # Landing page lists the six categories.
    for category in ["water", "food", "energy", "shelter", "health", "cooperation"]:
        assert category in resp.text
