"""Admin content-packs wizard + integrations status page tests.

Exercises the gated routes without touching the network: the download manager's
``start`` is stubbed and the LLM reachability probe is forced.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from horizon.main import app
from horizon.services import llm
from horizon.services import packs as packs_service

TOKEN = "test-secret-token"
PACK = "wikipedia-en-mini"  # from the shipped catalog


def _client(monkeypatch) -> TestClient:
    monkeypatch.setenv("HORIZON_ADMIN_TOKEN", TOKEN)
    client = TestClient(app)
    client.post("/admin/login", data={"token": TOKEN})
    return client


def test_packs_page_requires_auth(monkeypatch):
    monkeypatch.setenv("HORIZON_ADMIN_TOKEN", TOKEN)
    with TestClient(app) as client:
        resp = client.get("/admin/packs", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/admin/login"


def test_packs_page_lists_catalog(monkeypatch):
    with _client(monkeypatch) as client:
        resp = client.get("/admin/packs")
        assert resp.status_code == 200
        assert "Content packs" in resp.text
        assert PACK in resp.text


def test_download_starts_background_job(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        packs_service.download_manager, "start", lambda pid: calls.append(pid) or {}
    )
    with _client(monkeypatch) as client:
        resp = client.post(f"/admin/packs/{PACK}/download")
        assert resp.status_code == 200
        assert f"pack-row-{PACK}" in resp.text
    assert calls == [PACK]


def test_download_unknown_pack_does_not_start(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        packs_service.download_manager, "start", lambda pid: calls.append(pid) or {}
    )
    with _client(monkeypatch) as client:
        resp = client.post("/admin/packs/ghost/download")
        assert resp.status_code == 404
    assert calls == []


def test_remove_returns_row_fragment(monkeypatch):
    monkeypatch.setattr(packs_service, "remove_pack", lambda pid: True)
    with _client(monkeypatch) as client:
        resp = client.post(f"/admin/packs/{PACK}/remove")
        assert resp.status_code == 200
        assert f"pack-row-{PACK}" in resp.text


def test_integrations_page(monkeypatch):
    monkeypatch.setattr(llm, "available", lambda: False)
    with _client(monkeypatch) as client:
        resp = client.get("/admin/integrations")
        assert resp.status_code == 200
        assert "moral-core" in resp.text
        assert "Content packs" in resp.text
        # Ethics hook is off by default, so it shows as disabled.
        assert "disabled" in resp.text.lower()
