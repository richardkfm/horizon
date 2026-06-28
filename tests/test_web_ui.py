"""Server-rendered web UI tests (no external services required)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from horizon.main import app
from horizon.models import Category


def test_landing_lists_categories():
    with TestClient(app) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert "water" in resp.text


def test_landing_lists_new_categories():
    # The expanded built-in library adds survival, culture, language, and crafts.
    with TestClient(app) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    for name in (
        "survival",
        "culture",
        "language",
        "crafts",
        "emergencies",
        "cooking",
        "calculations",
    ):
        assert name in resp.text


@pytest.mark.parametrize(
    ("category", "expected_title"),
    [
        ("survival", "Make and keep a fire without matches"),
        ("culture", "Lead group singing"),
        ("language", "Learn and teach essential phrases"),
        ("crafts", "Make rope and cordage from plant fibre"),
        ("emergencies", "Prepare for and live through a long blackout"),
        ("cooking", "Cook simple one-pot plant-based meals"),
        ("calculations", "Size an energy system"),
    ],
)
def test_category_guides_listed(category, expected_title):
    # Guides are browsed directly from the library, filtered by category.
    with TestClient(app) as client:
        resp = client.get("/guides", params={"category": category})
    assert resp.status_code == 200
    assert expected_title in resp.text


def test_emergencies_cover_natural_disasters():
    # Natural-disaster coverage in the emergencies category (urban and rural).
    with TestClient(app) as client:
        resp = client.get("/guides", params={"category": "emergencies"})
    assert resp.status_code == 200
    for title in (
        "Stay safe in a flood",
        "Stay safe in an earthquake",
        "Get through a drought",
        "Stay safe in a nuclear or radiological emergency",
        "Stay safe in a wildfire",
        "Stay safe in severe storms",
    ):
        assert title in resp.text


def test_every_category_has_a_seeded_guide():
    # Guard against adding a category to the enum without any content behind it.
    # Guides — not tracks — are the unit that must cover every category.
    with TestClient(app) as client:
        for category in Category:
            resp = client.get("/guides", params={"category": category.value})
            assert resp.status_code == 200
            assert "No guides in this category yet" not in resp.text, (
                f"no seeded guides for category {category.value}"
            )


def test_landing_tiles_link_straight_to_guides():
    # A category tile takes a visitor straight to the guide library, not an
    # interstitial step-by-step plan.
    with TestClient(app) as client:
        resp = client.get("/")
    assert "/guides?category=water" in resp.text


def test_journeys_page_lists_tracks():
    with TestClient(app) as client:
        resp = client.get("/journeys")
    assert resp.status_code == 200
    assert 'class="track-list"' in resp.text
    assert "Set up off-grid power" in resp.text
    # A track previews its ordered guides, each linking straight to the guide.
    assert "/guides/energy-low-tech-solar" in resp.text


def test_journeys_page_category_filter():
    with TestClient(app) as client:
        resp = client.get("/journeys", params={"category": "water"})
        assert resp.status_code == 200
        assert "Provide safe drinking water for a group" in resp.text

        bad = client.get("/journeys", params={"category": "nonsense"})
        assert bad.status_code == 400


def test_track_detail_lists_ordered_guides():
    with TestClient(app) as client:
        resp = client.get("/journeys/off-grid-power")
    assert resp.status_code == 200
    # The track's guides appear as direct links, in order; no prerequisite
    # scaffolding to click through.
    for gid in (
        "energy-sizing-solar-battery",
        "energy-low-tech-solar",
        "energy-battery-storage",
        "energy-wind-power",
    ):
        assert f"/guides/{gid}" in resp.text
    assert "Prerequisite" not in resp.text


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


def test_guide_page_shows_difficulty_and_track_backlink():
    with TestClient(app) as client:
        resp = client.get("/guides/energy-low-tech-solar")
    assert resp.status_code == 200
    # The guide carries its own context now (no enclosing journey needed)…
    assert "Difficulty" in resp.text
    # …and links back to the curated plan it is part of.
    assert "/journeys/off-grid-power" in resp.text


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


def test_nav_uses_plain_labels_and_hides_admin():
    with TestClient(app) as client:
        resp = client.get("/")
    assert "Step-by-step plans" in resp.text
    assert "Ask a question" in resp.text
    # Admin no longer advertised in the public header (footer link only).
    assert ">Admin<" not in resp.text


def test_guides_search_filters_by_term():
    with TestClient(app) as client:
        resp = client.get("/guides", params={"q": "water"})
        miss = client.get("/guides", params={"q": "zzzznope"})
    assert "/guides/water-slow-sand-filter" in resp.text
    assert "/guides/food-staple-crops-500m2" not in resp.text
    assert "No guides match" in miss.text


def test_assistant_can_be_disabled_by_operator(monkeypatch):
    monkeypatch.setenv("HORIZON_ASSISTANT_ENABLED", "false")
    with TestClient(app) as client:
        home = client.get("/")
        page = client.get("/assistant")
        answer = client.post("/assistant/answer", data={"question": "hi"})
    assert ">Ask a question<" not in home.text
    assert "turned off" in page.text
    assert "assistant-form" not in page.text
    assert "turned off by the operator" in answer.text
