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
def test_new_category_journeys_listed(category, expected_title):
    with TestClient(app) as client:
        resp = client.get("/journeys", params={"category": category})
    assert resp.status_code == 200
    assert expected_title in resp.text


def test_emergencies_cover_natural_disasters():
    # Natural-disaster coverage in the emergencies category (urban and rural).
    with TestClient(app) as client:
        resp = client.get("/journeys", params={"category": "emergencies"})
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


def test_every_category_has_a_seeded_journey():
    # Guard against adding a category to the enum without any content behind it.
    with TestClient(app) as client:
        for category in Category:
            resp = client.get("/api/journeys", params={"category": category.value})
            assert resp.status_code == 200
            assert resp.json(), f"no seeded journeys for category {category.value}"


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


def test_entry_journey_shows_start_here_badge():
    with TestClient(app) as client:
        listing = client.get("/journeys")
        detail = client.get("/journeys/water-testing-basics")  # no prerequisites
    assert "Start here" in listing.text
    assert "Start here" in detail.text


def test_journeys_page_groups_into_topic_tracks():
    # The list is grouped into per-topic "skill tracks", each with a heading and
    # a plain-language example, rather than one undifferentiated grid.
    with TestClient(app) as client:
        resp = client.get("/journeys")
    assert resp.status_code == 200
    assert 'class="skill-track"' in resp.text
    assert 'id="track-water"' in resp.text
    assert "Make river or rain water safe to drink" in resp.text  # category example


def test_journey_card_shows_builds_on_prerequisite():
    # water-slow-sand-filter builds on water-testing-basics, so its card in the
    # listing surfaces that prerequisite as a "Builds on …" connector.
    with TestClient(app) as client:
        resp = client.get("/journeys", params={"category": "water"})
    assert resp.status_code == 200
    assert "Builds on" in resp.text


def test_journey_detail_shows_next_step_chain():
    # water-testing-basics is a prerequisite of water-slow-sand-filter, so the
    # latter should appear as a next step on the former's page.
    with TestClient(app) as client:
        resp = client.get("/journeys/water-testing-basics")
    assert "What comes next" in resp.text
    assert "/journeys/water-slow-sand-filter" in resp.text


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


def test_nav_links_to_checklists():
    with TestClient(app) as client:
        resp = client.get("/")
    assert "Checklists" in resp.text
    assert "/checklists" in resp.text


def test_checklists_index_lists_seeded_checklists():
    with TestClient(app) as client:
        resp = client.get("/checklists")
    assert resp.status_code == 200
    assert "/checklists/go-bag" in resp.text
    assert "/checklists/first-aid-kit" in resp.text


def test_checklist_page_renders_checkboxes():
    with TestClient(app) as client:
        resp = client.get("/checklists/go-bag")
    assert resp.status_code == 200
    # Task-list items become real checkboxes inside a task-list.
    assert 'class="task-list"' in resp.text
    assert 'type="checkbox"' in resp.text
    # Front matter is stripped; the print affordance is present.
    assert "id: go-bag" not in resp.text
    assert "window.print()" in resp.text


def test_checklist_page_404():
    with TestClient(app) as client:
        resp = client.get("/checklists/does-not-exist")
    assert resp.status_code == 404


def test_guide_renders_figure_with_caption():
    # The make-your-own-tools guide demonstrates the figure convention.
    with TestClient(app) as client:
        resp = client.get("/guides/crafts-make-tools")
    assert resp.status_code == 200
    assert "<figure" in resp.text and "guide-figure" in resp.text
    assert "<figcaption>" in resp.text
    assert "images/hafted-tool.svg" in resp.text


def test_guide_image_is_served():
    with TestClient(app) as client:
        resp = client.get("/guides/images/hafted-tool.svg")
    assert resp.status_code == 200
    assert "svg" in resp.headers["content-type"]


def test_new_medical_and_fire_guides_are_seeded():
    with TestClient(app) as client:
        for guide_id, expected in (
            ("health-bleeding-control", "Stop severe bleeding"),
            ("health-choking-and-cpr", "not breathing"),
            ("emergency-extinguish-fire", "Put out a fire safely"),
            ("crafts-make-tools", "hand tools"),
        ):
            resp = client.get(f"/guides/{guide_id}")
            assert resp.status_code == 200, guide_id
            assert expected in resp.text


def test_do_now_callout_renders_on_fire_guide():
    with TestClient(app) as client:
        resp = client.get("/guides/emergency-extinguish-fire")
    assert "callout-now" in resp.text


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
