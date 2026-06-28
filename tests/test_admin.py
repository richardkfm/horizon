"""Token-based admin area tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from horizon.main import app

TOKEN = "test-secret-token"


def test_admin_disabled_without_token(monkeypatch):
    monkeypatch.delenv("HORIZON_ADMIN_TOKEN", raising=False)
    monkeypatch.setattr("horizon.config.settings.admin.token", "", raising=False)
    with TestClient(app) as client:
        # Login page explains how to enable; submitting is rejected.
        page = client.get("/admin/login")
        assert page.status_code == 200
        assert "disabled" in page.text.lower()

        resp = client.post("/admin/login", data={"token": "anything"})
        assert resp.status_code == 403


def test_admin_requires_login(monkeypatch):
    monkeypatch.setenv("HORIZON_ADMIN_TOKEN", TOKEN)
    with TestClient(app) as client:
        resp = client.get("/admin", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/admin/login"


def test_admin_wrong_token_rejected(monkeypatch):
    monkeypatch.setenv("HORIZON_ADMIN_TOKEN", TOKEN)
    with TestClient(app) as client:
        resp = client.post("/admin/login", data={"token": "wrong"})
        assert resp.status_code == 401
        # No cookie was set, so the dashboard is still gated.
        gated = client.get("/admin", follow_redirects=False)
        assert gated.status_code == 303


def test_admin_login_and_dashboard(monkeypatch):
    monkeypatch.setenv("HORIZON_ADMIN_TOKEN", TOKEN)
    with TestClient(app) as client:
        login = client.post("/admin/login", data={"token": TOKEN})
        assert login.status_code == 200  # followed redirect to /admin
        assert "Content dashboard" in login.text
        # Seed content counts are shown.
        assert "journeys" in login.text.lower()

        # Cookie persists, so a fresh request to /admin renders the dashboard.
        again = client.get("/admin")
        assert again.status_code == 200
        assert "By category" in again.text

        # Logout clears access.
        client.post("/admin/logout")
        after = client.get("/admin", follow_redirects=False)
        assert after.status_code == 303


def test_admin_library_requires_login(monkeypatch):
    monkeypatch.setenv("HORIZON_ADMIN_TOKEN", TOKEN)
    with TestClient(app) as client:
        resp = client.get("/admin/library", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/admin/login"


def test_admin_library_lists_guides_journeys_and_skills(monkeypatch):
    monkeypatch.setenv("HORIZON_ADMIN_TOKEN", TOKEN)
    with TestClient(app) as client:
        client.post("/admin/login", data={"token": TOKEN})
        page = client.get("/admin/library")
        assert page.status_code == 200
        # All three sections render, with seed content present.
        assert "Guides" in page.text
        assert "Journeys" in page.text
        assert "md skills" in page.text
        # A known seed guide and md skill appear.
        assert "water-choosing-treatment" in page.text
        assert "choosing-well" in page.text


def test_admin_library_previews(monkeypatch):
    monkeypatch.setenv("HORIZON_ADMIN_TOKEN", TOKEN)
    with TestClient(app) as client:
        client.post("/admin/login", data={"token": TOKEN})

        guide = client.get("/admin/library/guides/water-choosing-treatment")
        assert guide.status_code == 200
        # Decision-guide callout class is rendered in the preview.
        assert "callout" in guide.text

        skill = client.get("/admin/library/skills/choosing-well")
        assert skill.status_code == 200
        assert "Helping people choose well" in skill.text

        journey = client.get("/admin/library/journeys/water-slow-sand-filter")
        assert journey.status_code == 200
        assert "Builds on" in journey.text

        missing = client.get("/admin/library/guides/does-not-exist")
        assert missing.status_code == 404


def test_admin_health_requires_login(monkeypatch):
    monkeypatch.setenv("HORIZON_ADMIN_TOKEN", TOKEN)
    with TestClient(app) as client:
        resp = client.get("/admin/health", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/admin/login"


def test_admin_health_page_renders_checks_and_feed(monkeypatch):
    monkeypatch.setenv("HORIZON_ADMIN_TOKEN", TOKEN)
    with TestClient(app) as client:
        client.post("/admin/login", data={"token": TOKEN})
        page = client.get("/admin/health")
        assert page.status_code == 200
        # The diagnostics, repairs, and event feed are all present.
        assert "Checks" in page.text
        assert "Database" in page.text
        assert "Search index" in page.text
        assert "Rebuild search index" in page.text
        assert "Re-seed content" in page.text
        assert "Recent events" in page.text


def test_admin_health_reseed_repair_via_htmx(monkeypatch):
    monkeypatch.setenv("HORIZON_ADMIN_TOKEN", TOKEN)
    with TestClient(app) as client:
        client.post("/admin/login", data={"token": TOKEN})
        # An HTMX repair returns the refreshed body fragment with a result banner.
        resp = client.post(
            "/admin/health/repair",
            data={"action": "reseed"},
            headers={"HX-Request": "true"},
        )
        assert resp.status_code == 200
        assert "Re-seeded content from disk" in resp.text
        # The fragment is the live region, not a full page.
        assert "<!DOCTYPE html>" not in resp.text


def test_admin_health_repair_without_js_redirects(monkeypatch):
    monkeypatch.setenv("HORIZON_ADMIN_TOKEN", TOKEN)
    with TestClient(app) as client:
        client.post("/admin/login", data={"token": TOKEN})
        # No HX-Request header: a plain form post redirects (PRG) back to the page.
        resp = client.post(
            "/admin/health/repair",
            data={"action": "reindex"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert resp.headers["location"] == "/admin/health"


def test_admin_health_repair_requires_login(monkeypatch):
    monkeypatch.setenv("HORIZON_ADMIN_TOKEN", TOKEN)
    with TestClient(app) as client:
        resp = client.post(
            "/admin/health/repair", data={"action": "reseed"}, follow_redirects=False
        )
        assert resp.status_code == 303
        assert resp.headers["location"] == "/admin/login"
