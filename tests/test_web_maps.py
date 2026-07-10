"""Map-viewer web routes (/maps/...), TestClient-based.

Installs a real fixture maps pack directly on disk (manifest.json, a dummy
.osm.pbf payload, and the tiny synthetic .mbtiles from the ``fixture_mbtiles``
fixture in conftest.py, dropped in as if an operator had rendered it) under
the shared test session's content_packs.dir -- no network, no download flow,
no Planetiler involved.
"""

from __future__ import annotations

import json
import shutil
import time

from fastapi.testclient import TestClient

from horizon.main import app
from horizon.services import packs as packs_service

PACK_ID = "test-maps-pack"


def _install_fixture_map_pack(fixture_mbtiles, *, with_mbtiles: bool = True) -> None:
    pack_dir = packs_service.packs_dir() / PACK_ID
    pack_dir.mkdir(parents=True, exist_ok=True)
    dest = pack_dir / "data.osm.pbf"
    dest.write_bytes(b"not-really-a-pbf")
    manifest = {
        "id": PACK_ID,
        "title": "Test Maps Pack",
        "category": "maps",
        "format": "osm.pbf",
        "file": dest.name,
        "size_bytes": dest.stat().st_size,
        "sha256": "",
        "installed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (pack_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    if with_mbtiles:
        shutil.copy2(fixture_mbtiles, pack_dir / "rendered.mbtiles")


def teardown_function() -> None:
    pack_dir = packs_service.packs_dir() / PACK_ID
    if pack_dir.is_dir():
        shutil.rmtree(pack_dir)


def test_maps_index_empty_state_when_nothing_installed():
    with TestClient(app) as client:
        resp = client.get("/maps")
        assert resp.status_code == 200
        assert "No maps ready to view" in resp.text


def test_maps_index_lists_pack_with_rendered_mbtiles(fixture_mbtiles):
    _install_fixture_map_pack(fixture_mbtiles)
    with TestClient(app) as client:
        resp = client.get("/maps")
        assert resp.status_code == 200
        assert "Test Maps Pack" in resp.text


def test_maps_index_omits_pack_without_rendered_mbtiles(fixture_mbtiles):
    _install_fixture_map_pack(fixture_mbtiles, with_mbtiles=False)
    with TestClient(app) as client:
        resp = client.get("/maps")
        assert resp.status_code == 200
        assert "Test Maps Pack" not in resp.text
        assert "No maps ready to view" in resp.text


def test_map_viewer_page_renders(fixture_mbtiles):
    _install_fixture_map_pack(fixture_mbtiles)
    with TestClient(app) as client:
        resp = client.get(f"/maps/{PACK_ID}")
        assert resp.status_code == 200
        assert "Test Maps Pack" in resp.text
        assert f"/maps/{PACK_ID}/tiles/" in resp.text


def test_map_viewer_unrendered_pack_404s(fixture_mbtiles):
    _install_fixture_map_pack(fixture_mbtiles, with_mbtiles=False)
    with TestClient(app) as client:
        resp = client.get(f"/maps/{PACK_ID}")
        assert resp.status_code == 404


def test_map_viewer_unknown_pack_404s():
    with TestClient(app) as client:
        resp = client.get("/maps/ghost-pack")
        assert resp.status_code == 404


def test_tile_endpoint_serves_gzipped_tile(fixture_mbtiles):
    _install_fixture_map_pack(fixture_mbtiles)
    with TestClient(app) as client:
        resp = client.get(f"/maps/{PACK_ID}/tiles/0/0/0.pbf")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/x-protobuf"
        assert resp.headers.get("content-encoding") == "gzip"
        # httpx transparently decodes a gzip Content-Encoding, so .content is
        # already the plain tile bytes here -- the header assertion above is
        # what actually proves the server marked the body as compressed.
        assert resp.content == b"not-really-a-vector-tile"


def test_tile_endpoint_missing_tile_returns_204(fixture_mbtiles):
    _install_fixture_map_pack(fixture_mbtiles)
    with TestClient(app) as client:
        resp = client.get(f"/maps/{PACK_ID}/tiles/5/5/5.pbf")
        assert resp.status_code == 204


def test_tile_endpoint_unrendered_pack_404s(fixture_mbtiles):
    _install_fixture_map_pack(fixture_mbtiles, with_mbtiles=False)
    with TestClient(app) as client:
        resp = client.get(f"/maps/{PACK_ID}/tiles/0/0/0.pbf")
        assert resp.status_code == 404
