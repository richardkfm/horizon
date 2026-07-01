"""Admin "Import content" wizard tests (WikiHow page / book -> guide).

Network is faked the same way as ``test_content_cli_import.py``; the re-seed
step (which touches the real database/search index) is stubbed out so these
tests stay focused on the route/form glue, not ``seed.reseed`` internals
(covered elsewhere).
"""

from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from horizon.config import settings
from horizon.main import app
from horizon.web import admin as admin_module

TOKEN = "test-secret-token"

WIKIHOW_HTML = """
<h1>How to Build a Story Circle</h1>
<p>Gathering around a fire to tell stories builds community.</p>
<h2>Steps</h2>
<ol>
<li><b>Pick a spot.</b> Choose a safe, flat clearing.</li>
<li><b>Invite people.</b> Tell neighbours the time and place.</li>
</ol>
"""

BOOK_TEXT = """Chapter 1: Greetings
Greetings here are never rushed.

Chapter 2: Festivals
Every household brings a dish to share.
"""


class _FakeResponse:
    def __init__(self, text: str = "", content: bytes = b""):
        self.text = text
        self.content = content or text.encode("utf-8")

    def raise_for_status(self) -> None:
        pass


class _FakeClient:
    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, url: str):
        return _FakeResponse(text=WIKIHOW_HTML)

    def post(self, *a, **k):
        # The app's startup lifespan tries to reindex (embedding via Ollama)
        # while this fake client is patched in; simulate "no runtime reachable"
        # so it falls back gracefully instead of raising AttributeError.
        raise httpx.ConnectError("no network in tests")


def _client(monkeypatch, tmp_path) -> TestClient:
    monkeypatch.setenv("HORIZON_ADMIN_TOKEN", TOKEN)
    monkeypatch.setattr(settings, "content_dir", str(tmp_path / "content"))
    monkeypatch.setattr(admin_module, "_reseed_after_import", lambda: "Re-seeded (stubbed).")
    client = TestClient(app)
    client.post("/admin/login", data={"token": TOKEN})
    return client


def test_import_page_requires_auth():
    with TestClient(app) as client:
        resp = client.get("/admin/import", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/admin/login"


def test_import_page_lists_categories(monkeypatch, tmp_path):
    with _client(monkeypatch, tmp_path) as client:
        resp = client.get("/admin/import")
        assert resp.status_code == 200
        assert "Import a how-to page" in resp.text
        assert "Import a book" in resp.text
        assert "water" in resp.text  # a known category option


def test_import_wikihow_writes_guide(monkeypatch, tmp_path):
    monkeypatch.setattr(httpx, "Client", _FakeClient)
    with _client(monkeypatch, tmp_path) as client:
        resp = client.post(
            "/admin/import/wikihow",
            data={
                "url": "https://www.wikihow.com/Build-a-Story-Circle",
                "category": "culture",
                "difficulty": "2",
            },
        )
        assert resp.status_code == 200
        assert "Imported" in resp.text
        assert "how-to-build-a-story-circle" in resp.text

    out = tmp_path / "content" / "guides" / "how-to-build-a-story-circle.md"
    assert out.is_file()


def test_import_wikihow_duplicate_without_force_reports_error(monkeypatch, tmp_path):
    monkeypatch.setattr(httpx, "Client", _FakeClient)
    with _client(monkeypatch, tmp_path) as client:
        data = {
            "url": "https://www.wikihow.com/X",
            "category": "culture",
            "guide_id": "dup",
        }
        client.post("/admin/import/wikihow", data=data)
        resp = client.post("/admin/import/wikihow", data=data)
        assert resp.status_code == 200
        assert "Import failed" in resp.text
        assert "already exists" in resp.text


def test_import_book_splits_chapters(monkeypatch, tmp_path):
    with _client(monkeypatch, tmp_path) as client:
        files = {"file": ("valley-customs.txt", BOOK_TEXT, "text/plain")}
        resp = client.post(
            "/admin/import/book",
            data={"category": "culture", "id_prefix": "culture-valley-customs"},
            files=files,
        )
        assert resp.status_code == 200
        assert "Imported" in resp.text
        assert "culture-valley-customs-01-greetings" in resp.text
        assert "culture-valley-customs-02-festivals" in resp.text

    guides_dir = tmp_path / "content" / "guides"
    written = sorted(p.name for p in guides_dir.glob("culture-valley-customs-*.md"))
    assert written == [
        "culture-valley-customs-01-greetings.md",
        "culture-valley-customs-02-festivals.md",
    ]


def test_import_book_all_skipped_reports_failure(monkeypatch, tmp_path):
    with _client(monkeypatch, tmp_path) as client:
        files = {"file": ("book.txt", BOOK_TEXT, "text/plain")}
        data = {"category": "culture", "id_prefix": "x"}
        client.post("/admin/import/book", data=data, files=files)
        files = {"file": ("book.txt", BOOK_TEXT, "text/plain")}
        resp = client.post("/admin/import/book", data=data, files=files)
        assert resp.status_code == 200
        assert "Import failed" in resp.text
        assert "already existed" in resp.text
