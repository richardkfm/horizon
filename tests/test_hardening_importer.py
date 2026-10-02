"""Hardening regressions for content import (CLI + admin web wizard)."""

from __future__ import annotations

import inspect

import pytest
from fastapi.testclient import TestClient

from horizon.config import settings
from horizon.main import app
from horizon.services import import_content, importer
from horizon.web import admin as admin_module

TOKEN = "hardening-import-token"
ARTICLE = (
    "<h1>Boil &lt;b&gt;water&lt;/b&gt;</h1>"
    "<p>intro &lt;img src=x onerror=alert(1)&gt; &amp; more</p>"
    "<ol><li>step &lt;script&gt;alert(1)&lt;/script&gt;</li><li>&gt; not a quote</li></ol>"
)


def test_wikihow_import_keeps_escaped_html_escaped():
    md = importer.render_wikihow_guide(
        importer.parse_html_article(ARTICLE), guide_id="t", source="https://x/<y>"
    )
    _front, body = md.split("\n---\n", 1)
    assert "<img" not in body and "<script" not in body and "<b>" not in body
    assert "&lt;img src=x onerror=alert(1)&gt; &amp; more" in body
    assert "&lt;script&gt;" in body
    assert "2. &gt; not a quote" in body  # can't become a blockquote/callout
    assert "https://x/&lt;y&gt;" in body
    # The title in front matter stays plain text (templates escape it).
    assert "title: Boil <b>water</b>" in md


def test_escape_markdown_html():
    assert importer.escape_markdown_html("a<b>&c") == "a&lt;b&gt;&amp;c"


def test_validation_helpers():
    with pytest.raises(import_content.ContentImportError, match="Unknown category"):
        import_content.validate_category("bogus")
    assert import_content.validate_category("Water") == "water"
    assert import_content.clamp_difficulty(99) == 5
    assert import_content.clamp_difficulty("abc") == 2
    assert import_content.safe_id("../../x", fallback="y") == "x"
    assert import_content.safe_id("", fallback="My Book.txt") == "my-book-txt"


def test_import_wikihow_rejects_bad_category_before_fetching(monkeypatch, tmp_path):
    def no_fetch(url: str) -> str:  # pragma: no cover - must not be reached
        raise AssertionError("fetched despite invalid input")

    monkeypatch.setattr(import_content, "fetch_text", no_fetch)
    with pytest.raises(import_content.ContentImportError):
        import_content.import_wikihow("http://x/y", category="bogus", dest_dir=tmp_path)


def test_import_wikihow_slugifies_id_and_clamps_difficulty(monkeypatch, tmp_path):
    monkeypatch.setattr(import_content, "fetch_text", lambda url: ARTICLE)
    dest = tmp_path / "root" / "guides"
    out = import_content.import_wikihow(
        "http://x/y",
        category="water",
        difficulty=99,
        guide_id="../../escaped",
        dest_dir=dest,
        download_images_flag=False,
    )
    assert out["guide_id"] == "escaped"
    assert out["path"].parent == dest
    assert not (tmp_path / "escaped.md").exists()
    assert "difficulty: 5" in out["path"].read_text("utf-8")


def test_import_book_slugifies_prefix(tmp_path):
    dest = tmp_path / "root" / "guides"
    out = import_content.import_book(
        "hello", source_name="b.txt", category="culture", id_prefix="../../bk", dest_dir=dest
    )
    assert [w["guide_id"] for w in out["written"]] == ["bk"]
    assert not (tmp_path / "bk.md").exists()
    with pytest.raises(import_content.ContentImportError):
        import_content.import_book("hello", source_name="b.txt", category="nope", dest_dir=dest)


def _client(monkeypatch, tmp_path) -> TestClient:
    monkeypatch.setenv("HORIZON_ADMIN_TOKEN", TOKEN)
    monkeypatch.setattr(settings, "content_dir", str(tmp_path / "content"))
    monkeypatch.setattr(admin_module, "_reseed_after_import", lambda: "Re-seeded (stubbed).")
    return TestClient(app)


def test_admin_wizard_shows_friendly_error_for_bad_category(monkeypatch, tmp_path):
    monkeypatch.setattr(import_content, "fetch_text", lambda url: ARTICLE)
    with _client(monkeypatch, tmp_path) as client:
        client.post("/admin/login", data={"token": TOKEN})
        resp = client.post(
            "/admin/import/wikihow",
            data={"url": "http://x/y", "category": "bogus", "difficulty": "99"},
        )
    assert resp.status_code == 200
    assert "Unknown category" in resp.text
    assert not (tmp_path / "content" / "guides" / "boil-b-water-b.md").exists()
    assert not list((tmp_path / "content" / "guides").glob("boil*.md"))


def test_admin_wizard_book_upload_stays_in_guides_dir(monkeypatch, tmp_path):
    with _client(monkeypatch, tmp_path) as client:
        client.post("/admin/login", data={"token": TOKEN})
        resp = client.post(
            "/admin/import/book",
            files={"file": ("b.txt", b"hello world")},
            data={"id_prefix": "../../bk", "category": "culture", "difficulty": "abc"},
        )
    assert resp.status_code == 200
    assert (tmp_path / "content" / "guides" / "bk.md").is_file()
    assert not (tmp_path / "bk.md").exists()


def test_import_routes_do_not_block_the_event_loop():
    # Sync routes run in FastAPI's threadpool; an ``async def`` doing blocking
    # reseed/reindex/file I/O would stall every other request.
    assert not inspect.iscoroutinefunction(admin_module.import_book_submit)
    assert not inspect.iscoroutinefunction(admin_module.import_wikihow_submit)
