"""Hardening regressions: ZIM sanitising + headers, map tiles, admin auth, PDF, recommend."""

from __future__ import annotations

import json
import shutil
import sqlite3
import time
from datetime import date

import pytest
from fastapi.testclient import TestClient

from horizon.config import settings
from horizon.main import app
from horizon.services import mbtiles, packs, zim_reader
from horizon.web import admin as admin_module

# --- ZIM article sanitising -----------------------------------------------------


def _clean(html: str) -> str:
    return zim_reader.rewrite_article_html(html, pack_id="p", entry_path="A/x")


@pytest.mark.parametrize(
    "payload",
    [
        '<img src="a.png" onerror="alert(1)">',
        '<a href="javascript:alert(1)">x</a>',
        '<a href=" java&#x09;script:alert(1)">x</a>',
        '<a href="VBScript:msgbox(1)">x</a>',
        '<a href="data:text/html,<script>alert(1)</script>">x</a>',
        '<iframe src="javascript:alert(1)"></iframe>',
        "<object data=x></object><embed src=y><frameset><frame src=z></frameset>",
        "<svg onload=alert(1)><script>alert(1)</script></svg>",
        '<div onmouseover="alert(1)" ONCLICK="alert(1)">x</div>',
        '<div hx-get="/admin" data-hx-post="/x" x-data="{}" @click="alert(1)">x</div>',
        '<p style="background:url(javascript:alert(1))">x</p>',
        "<style>@import url(http://evil/x.css); .a{color:red}</style>",
        "<base href=http://evil/><meta http-equiv=refresh content=0;url=http://evil>",
        "<form action=http://evil><input name=q><button>go</button></form>",
    ],
)
def test_zim_sanitiser_strips_active_content(payload):
    out = _clean(f"<body>{payload}</body>").lower()
    for needle in (
        "onerror",
        "onload",
        "onclick",
        "onmouseover",
        "javascript:",
        "vbscript:",
        "data:text",
        "<script",
        "<iframe",
        "<object",
        "<embed",
        "<frame",
        "<svg",
        "hx-",
        "x-data",
        "@click",
        "@import",
        "<base",
        "<meta",
        "<form",
        "<input",
    ):
        assert needle not in out, (needle, out)


def test_zim_sanitiser_keeps_ordinary_content():
    out = _clean(
        '<h2 id="s">Section</h2><p class="lead">A <b>bold</b> &amp; <a href="Other">link</a>'
        '</p><img src="data:image/png;base64,AAAA" alt="pic"><table><tr><td colspan="2">'
        "cell</td></tr></table>"
    )
    assert '<h2 id="s">Section</h2>' in out
    assert '<a href="/reference/p/A/Other">link</a>' in out
    assert "&amp;" in out
    assert 'src="data:image/png;base64,AAAA"' in out
    assert '<td colspan="2">cell</td>' in out


def test_zim_sanitiser_balances_tags():
    out = _clean("<div><p>unclosed</div></div></div><span>tail")
    assert out.count("<div>") == out.count("</div>") == 1
    assert out.endswith("</span>")


def test_zim_mimetype_helpers():
    assert zim_reader.safe_mimetype("text/html; charset=utf-8") == "text/html"
    assert zim_reader.safe_mimetype("bad\r\nheader: x") == "application/octet-stream"
    assert zim_reader.is_active_mimetype("image/svg+xml")
    assert not zim_reader.is_active_mimetype("image/png")


# --- reference routes: security headers --------------------------------------------

PACK_ID = "test-hardening-zim"


@pytest.fixture
def zim_pack(fixture_zim):
    pack_dir = packs.packs_dir() / PACK_ID
    pack_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(fixture_zim, pack_dir / "fixture.zim")
    manifest = {"id": PACK_ID, "title": "Z", "category": "reference", "format": "zim"}
    manifest["file"] = "fixture.zim"
    (pack_dir / "manifest.json").write_text(json.dumps(manifest), "utf-8")
    yield
    shutil.rmtree(pack_dir)


def test_reference_article_has_script_forbidding_csp(zim_pack):
    with TestClient(app) as client:
        resp = client.get(f"/reference/{PACK_ID}/Home")
    assert resp.status_code == 200
    csp = resp.headers["content-security-policy"]
    assert "script-src 'self'" in csp
    assert "'unsafe-inline'" not in csp.split("script-src", 1)[1].split(";", 1)[0]
    assert "object-src 'none'" in csp and "frame-src 'none'" in csp
    # horizon's own inline chrome scripts are allowed by hash, nothing else.
    assert "'sha256-" in csp
    assert "zimTrackerPixel" not in resp.text


def test_reference_raw_entry_is_nosniff_and_sandboxed(zim_pack):
    with TestClient(app) as client:
        resp = client.get(f"/reference/{PACK_ID}/logo.png")
    assert resp.status_code == 200
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'none'" in resp.headers["content-security-policy"]
    assert "sandbox" in resp.headers["content-security-policy"]


# --- map tiles -----------------------------------------------------------------------


def test_tile_coordinates_are_bounded(tmp_path):
    path = tmp_path / "m.mbtiles"
    conn = sqlite3.connect(path)
    conn.execute("create table metadata(name, value)")
    conn.execute("create table tiles(zoom_level, tile_column, tile_row, tile_data)")
    conn.execute("insert into tiles values (1, 1, 0, x'01')")
    conn.commit()
    conn.close()
    assert mbtiles.get_tile(path, 1, 1, 1) == b"\x01"
    for z, x, y in ((64, 0, 0), (10**8, 0, 0), (-1, 0, 0), (1, 2, 0), (1, 0, -1), (25, 0, 0)):
        assert mbtiles.get_tile(path, z, x, y) is None
        assert not mbtiles.valid_tile_coords(z, x, y)


def test_tile_route_rejects_out_of_range(monkeypatch, tmp_path):
    monkeypatch.setattr(packs, "pack_mbtiles_path", lambda pack_id: tmp_path / "missing")
    with TestClient(app) as client:
        assert client.get("/maps/x/tiles/64/0/0.pbf").status_code == 404
        assert client.get("/maps/x/tiles/3/8/0.pbf").status_code == 404
        assert client.get("/maps/x/tiles/3/0/-1.pbf").status_code in (404, 422)


# --- admin auth -------------------------------------------------------------------------

TOKEN = "hardening-web-token"


def test_non_ascii_token_is_rejected_cleanly(monkeypatch):
    monkeypatch.setenv("HORIZON_ADMIN_TOKEN", TOKEN)
    with TestClient(app) as client:
        assert client.post("/admin/login", data={"token": "é☃"}).status_code == 401
    assert not admin_module._cookie_valid(f"{int(time.time())}.é☃")


def test_admin_cookie_expires_server_side(monkeypatch):
    monkeypatch.setenv("HORIZON_ADMIN_TOKEN", TOKEN)
    fresh = admin_module._expected_cookie()
    assert admin_module._cookie_valid(fresh)
    old = admin_module._expected_cookie(int(time.time()) - admin_module._COOKIE_MAX_AGE - 10)
    assert not admin_module._cookie_valid(old)
    future = admin_module._expected_cookie(int(time.time()) + 3600)
    assert not admin_module._cookie_valid(future)
    issued, sig = fresh.split(".")
    assert not admin_module._cookie_valid(f"{int(issued) + 1}.{sig}")  # tampered time
    assert not admin_module._cookie_valid(sig)  # old v1-style cookie

    with TestClient(app) as client:
        client.post("/admin/login", data={"token": TOKEN})
        assert client.get("/admin", follow_redirects=False).status_code == 200
        client.cookies.set(admin_module.COOKIE_NAME, old)
        assert client.get("/admin", follow_redirects=False).status_code == 303


# --- PDF ----------------------------------------------------------------------------------


@pytest.fixture
def pdf_module(tmp_path, monkeypatch):
    pdf = pytest.importorskip("horizon.services.pdf")
    content = tmp_path / "content"
    (content / "guides" / "images").mkdir(parents=True)
    (content / "guides" / "images" / "d.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="4" height="4"/>', "utf-8"
    )
    monkeypatch.setattr(settings, "content_dir", str(content))
    pdf.clear_cache()
    return pdf


def test_pdf_fetcher_serves_only_guide_files(pdf_module):
    guides = pdf_module._base_url()
    data, mime, _ = pdf_module._fetch(guides + "images/d.svg")
    assert mime == "image/svg+xml" and data.startswith(b"<svg")
    assert pdf_module._fetch("data:image/png;base64,AAAA")[1] == "image/png"
    for url in (
        "file:///etc/hostname",
        guides + "images/../../../../../etc/passwd",
        "http://127.0.0.1:9/remote.png",
        "https://example.com/x.png",
        "ftp://example.com/x",
    ):
        with pytest.raises(pdf_module.PDFResourceRefused):
            pdf_module._fetch(url)


def test_pdf_render_never_touches_network_or_files(pdf_module, monkeypatch):
    import urllib.request

    def no_network(*args, **kwargs):
        url = str(args[0]) if args else ""
        if not url.startswith("data:"):
            raise AssertionError(f"network/file access attempted: {url}")
        return real_urlopen(*args, **kwargs)

    real_urlopen = urllib.request.urlopen
    monkeypatch.setattr(urllib.request, "urlopen", no_network)
    doc = (
        "<html><head><title>Boil &amp; filter — horizon</title></head><body><h1>Boil</h1>"
        '<img src="images/d.svg"><img src="http://127.0.0.1:9/x.png">'
        '<a rel="attachment" href="file:///etc/hostname">h</a></body></html>'
    )
    first = pdf_module.render_pdf(doc, printed_on=date(2026, 1, 2))
    assert first.startswith(b"%PDF")
    assert b"EmbeddedFile" not in first
    # Cached: the same document renders once.
    assert pdf_module.render_pdf(doc, printed_on=date(2026, 1, 2)) is first


def test_pdf_colophon(pdf_module):
    assert pdf_module._title_of("<title>Boil &amp; filter — horizon</title>") == "Boil & filter"
    css = pdf_module._colophon_css('Say "hi"\\', "2026-01-02")
    assert '"horizon · Say \\"hi\\"\\\\ · printed 2026-01-02"' in css
    assert "@top-center" in css and "@bottom-left" in css and "counter(page)" in css


# --- recommend --------------------------------------------------------------------------


def test_recommend_drops_filler_words_and_weak_matches():
    from horizon.services.recommend import _tokenize, recommend_journeys

    assert _tokenize("How to make my water safe, I want") == {"water"}
    with TestClient(app):
        assert recommend_journeys("I want to keep my family safe") == {
            "journeys": [],
            "guides": [],
        }
        result = recommend_journeys("how to make water safe")
    assert result["guides"]
    assert all("water" in (g["id"] + g["title"] + g["summary"]).lower() for g in result["guides"])
