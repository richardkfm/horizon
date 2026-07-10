"""Admin content-packs wizard + integrations status page tests.

Exercises the gated routes without touching the network: the download manager's
``start`` is stubbed and the LLM reachability probe is forced.
"""

from __future__ import annotations

import json
import shutil
import time

from fastapi.testclient import TestClient

from horizon.main import app
from horizon.services import llm
from horizon.services import packs as packs_service

TOKEN = "test-secret-token"
PACK = "wikipedia-en-mini"  # from the shipped catalog
MAPS_PACK_ID = "test-admin-maps-pack"


def _install_fixture_maps_pack(*, with_mbtiles_from=None) -> None:
    pack_dir = packs_service.packs_dir() / MAPS_PACK_ID
    pack_dir.mkdir(parents=True, exist_ok=True)
    dest = pack_dir / "data.osm.pbf"
    dest.write_bytes(b"not-really-a-pbf")
    manifest = {
        "id": MAPS_PACK_ID,
        "title": "Test Admin Maps Pack",
        "category": "maps",
        "format": "osm.pbf",
        "file": dest.name,
        "size_bytes": dest.stat().st_size,
        "sha256": "",
        "installed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (pack_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    if with_mbtiles_from is not None:
        shutil.copy2(with_mbtiles_from, pack_dir / "rendered.mbtiles")


def _teardown_maps_pack() -> None:
    pack_dir = packs_service.packs_dir() / MAPS_PACK_ID
    if pack_dir.is_dir():
        shutil.rmtree(pack_dir)


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


def test_packs_page_maps_pack_without_mbtiles_shows_render_hint(monkeypatch):
    _install_fixture_maps_pack()
    try:
        with _client(monkeypatch) as client:
            resp = client.get("/admin/packs")
            assert resp.status_code == 200
            assert "installed · raw data only" in resp.text
            assert "Planetiler" in resp.text
            assert f"/maps/{MAPS_PACK_ID}" not in resp.text
    finally:
        _teardown_maps_pack()


def test_packs_page_maps_pack_with_mbtiles_shows_view_map_link(monkeypatch, fixture_mbtiles):
    _install_fixture_maps_pack(with_mbtiles_from=fixture_mbtiles)
    try:
        with _client(monkeypatch) as client:
            resp = client.get("/admin/packs")
            assert resp.status_code == 200
            assert "map ready" in resp.text
            assert f'href="/maps/{MAPS_PACK_ID}"' in resp.text
    finally:
        _teardown_maps_pack()
