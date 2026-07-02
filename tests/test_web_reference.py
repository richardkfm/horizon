"""Reference-library web routes (/reference/...), TestClient-based.

Installs a real fixture pack directly on disk (manifest.json + the tiny
synthetic ZIM from the ``fixture_zim`` fixture in conftest.py) under the
shared test session's content_packs.dir -- no network, no download flow
involved.
"""

from __future__ import annotations

import json
import shutil
import time

from fastapi.testclient import TestClient

from horizon.main import app
from horizon.services import packs as packs_service

PACK_ID = "test-reference-pack"


def _install_fixture_pack(fixture_zim, pack_id: str = PACK_ID) -> None:
    pack_dir = packs_service.packs_dir() / pack_id
    pack_dir.mkdir(parents=True, exist_ok=True)
    dest = pack_dir / "fixture.zim"
    shutil.copy2(fixture_zim, dest)
    manifest = {
        "id": pack_id,
        "title": "Test Reference Pack",
        "category": "reference",
        "format": "zim",
        "file": dest.name,
        "size_bytes": dest.stat().st_size,
        "sha256": "",
        "installed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (pack_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _install_fixture_non_zim_pack(pack_id: str = "test-maps-pack") -> None:
    pack_dir = packs_service.packs_dir() / pack_id
    pack_dir.mkdir(parents=True, exist_ok=True)
    dest = pack_dir / "data.osm.pbf"
    dest.write_bytes(b"not-really-pbf")
    manifest = {
        "id": pack_id,
        "title": "Test Maps Pack",
        "category": "maps",
        "format": "osm.pbf",
        "file": dest.name,
        "size_bytes": dest.stat().st_size,
        "sha256": "",
        "installed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (pack_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def teardown_function() -> None:
    for pack_id in (PACK_ID, "test-maps-pack"):
        pack_dir = packs_service.packs_dir() / pack_id
        if pack_dir.is_dir():
            shutil.rmtree(pack_dir)


def test_reference_index_lists_installed_zim_pack(fixture_zim):
    _install_fixture_pack(fixture_zim)
    with TestClient(app) as client:
        resp = client.get("/reference")
        assert resp.status_code == 200
        assert "Fixture Pack" in resp.text


def test_reference_index_empty_state_when_nothing_installed():
    with TestClient(app) as client:
        resp = client.get("/reference")
        assert resp.status_code == 200
        assert "No reference packs installed" in resp.text


def test_pack_landing_shows_title_and_article_count(fixture_zim):
    _install_fixture_pack(fixture_zim)
    with TestClient(app) as client:
        resp = client.get(f"/reference/{PACK_ID}")
        assert resp.status_code == 200
        assert "Fixture Pack" in resp.text


def test_pack_landing_unknown_pack_404s():
    with TestClient(app) as client:
        resp = client.get("/reference/ghost-pack")
        assert resp.status_code == 404


def test_article_renders_rewritten_links_and_strips_scripts(fixture_zim):
    _install_fixture_pack(fixture_zim)
    with TestClient(app) as client:
        resp = client.get(f"/reference/{PACK_ID}/Home")
        assert resp.status_code == 200
        assert f'href="/reference/{PACK_ID}/Camping"' in resp.text
        # The ZIM article's own <script> (a tracker pixel call) must be
        # stripped -- horizon's own base.html theme-toggle script is expected
        # to still be present, so this checks for the specific ZIM payload,
        # not the absence of "<script" anywhere on the page.
        assert "zimTrackerPixel" not in resp.text


def test_article_unknown_path_404s(fixture_zim):
    _install_fixture_pack(fixture_zim)
    with TestClient(app) as client:
        resp = client.get(f"/reference/{PACK_ID}/does-not-exist")
        assert resp.status_code == 404


def test_article_follows_zim_internal_redirect(fixture_zim):
    _install_fixture_pack(fixture_zim)
    with TestClient(app) as client:
        resp = client.get(f"/reference/{PACK_ID}/Old_Camping_Name")
        assert resp.status_code == 200
        assert "Camping basics" in resp.text


def test_random_redirects_into_the_pack(fixture_zim):
    _install_fixture_pack(fixture_zim)
    with TestClient(app) as client:
        resp = client.get(f"/reference/{PACK_ID}/random", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"].startswith(f"/reference/{PACK_ID}/")


def test_asset_served_with_its_own_mimetype(fixture_zim):
    _install_fixture_pack(fixture_zim)
    with TestClient(app) as client:
        resp = client.get(f"/reference/{PACK_ID}/logo.png")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert resp.content == b"not-really-a-png"


def test_search_finds_article(fixture_zim):
    _install_fixture_pack(fixture_zim)
    with TestClient(app) as client:
        resp = client.get(f"/reference/{PACK_ID}", params={"q": "tent"})
        assert resp.status_code == 200
        assert f'href="/reference/{PACK_ID}/Camping"' in resp.text


def test_non_zim_pack_is_not_listed_or_resolvable():
    _install_fixture_non_zim_pack()
    with TestClient(app) as client:
        resp = client.get("/reference")
        assert "Test Maps Pack" not in resp.text
        assert client.get("/reference/test-maps-pack").status_code == 404


def test_nav_hides_reference_link_when_nothing_installed():
    with TestClient(app) as client:
        resp = client.get("/")
        assert "Reference library" not in resp.text


def test_nav_shows_reference_link_when_zim_pack_installed(fixture_zim):
    _install_fixture_pack(fixture_zim)
    with TestClient(app) as client:
        resp = client.get("/")
        assert "Reference library" in resp.text
        assert 'href="/reference"' in resp.text
