"""Server-rendered web UI tests (no external services required)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from horizon.main import app


def test_landing_lists_categories():
    with TestClient(app) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert "water" in resp.text


def test_journeys_page_lists_seed_journeys():
    with TestClient(app) as client:
        resp = client.get("/journeys")
    assert resp.status_code == 200
    assert "Grow staple crops on 500 m" in resp.text


def test_journeys_page_category_filter():
    with TestClient(app) as client:
        resp = client.get("/journeys", params={"category": "water"})
        assert resp.status_code == 200
        assert "safe drinking water" in resp.text.lower()

        bad = client.get("/journeys", params={"category": "nonsense"})
        assert bad.status_code == 400


def test_journey_detail_shows_prereqs_and_guides():
    with TestClient(app) as client:
        resp = client.get("/journeys/water-slow-sand-filter")
    assert resp.status_code == 200
    # Prerequisite journey and linked guide both appear, as clickable links.
    assert "/journeys/water-testing-basics" in resp.text
    assert "/guides/water-slow-sand-filter" in resp.text


def test_journey_detail_404():
    with TestClient(app) as client:
        resp = client.get("/journeys/does-not-exist")
    assert resp.status_code == 404


def test_guide_page_renders_markdown():
    with TestClient(app) as client:
        resp = client.get("/guides/water-slow-sand-filter")
    assert resp.status_code == 200
    # Rendered HTML, with the YAML front matter stripped.
    assert "<h1>" in resp.text
    assert "id: water-slow-sand-filter" not in resp.text
    # The print and PDF-download affordances are present.
    assert "window.print()" in resp.text
    assert "/guides/water-slow-sand-filter.pdf" in resp.text


def test_guide_page_404():
    with TestClient(app) as client:
        resp = client.get("/guides/does-not-exist")
    assert resp.status_code == 404


def test_guide_pdf_download():
    with TestClient(app) as client:
        resp = client.get("/guides/water-slow-sand-filter.pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "water-slow-sand-filter.pdf" in resp.headers["content-disposition"]
    assert resp.content.startswith(b"%PDF-")


def test_guide_pdf_404():
    with TestClient(app) as client:
        resp = client.get("/guides/does-not-exist.pdf")
    assert resp.status_code == 404
