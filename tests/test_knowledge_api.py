"""Knowledge API + seeding tests.

These exercise the data-model → seed → Knowledge API slice end to end with no
external services running. Seeding loads the bundled content into SQLite via the
app lifespan; the assertions target stable seed ids.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from horizon.main import app
from horizon.models import Category


def test_seed_loads_all_categories():
    """The bundled seed covers every category and links guides/prerequisites."""
    with TestClient(app) as client:
        resp = client.get("/api/journeys")
        assert resp.status_code == 200
        journeys = resp.json()

    ids = {j["id"] for j in journeys}
    # A representative journey from each category is present.
    assert {
        "water-testing-basics",
        "water-slow-sand-filter",
        "food-staple-crops",
        "energy-low-tech-solar",
        "shelter-insulation-basics",
        "health-first-aid-basics",
        "cooperation-group-decisions",
    } <= ids

    # Every category defined in the model has at least one seeded journey.
    categories = {j["category"] for j in journeys}
    assert categories == {c.value for c in Category}


def test_list_journeys_category_filter():
    with TestClient(app) as client:
        resp = client.get("/api/journeys", params={"category": "water"})
        assert resp.status_code == 200
        water = resp.json()
        assert water  # non-empty
        assert all(j["category"] == "water" for j in water)

        bad = client.get("/api/journeys", params={"category": "nonsense"})
        assert bad.status_code == 400


def test_get_journey_detail_with_prereqs_and_guides():
    with TestClient(app) as client:
        resp = client.get("/api/journeys/water-slow-sand-filter")
        assert resp.status_code == 200
        journey = resp.json()

    assert journey["id"] == "water-slow-sand-filter"
    assert journey["category"] == "water"
    prereq_ids = {p["id"] for p in journey["prerequisites"]}
    assert "water-testing-basics" in prereq_ids
    guide_ids = {g["id"] for g in journey["guides"]}
    assert "water-slow-sand-filter" in guide_ids


def test_get_journey_404():
    with TestClient(app) as client:
        resp = client.get("/api/journeys/does-not-exist")
        assert resp.status_code == 404


def test_get_guide_metadata_and_source():
    with TestClient(app) as client:
        resp = client.get("/api/guides/water-slow-sand-filter", params={"format": "markdown"})
        assert resp.status_code == 200
        guide = resp.json()

    assert guide["id"] == "water-slow-sand-filter"
    assert guide["category"] == "water"
    assert guide["summary"]
    # Raw Markdown source is returned and looks like the guide body.
    assert "slow sand filter" in guide["markdown"].lower()


def test_get_guide_html_format_renders_markdown():
    with TestClient(app) as client:
        resp = client.get("/api/guides/water-slow-sand-filter")
        assert resp.status_code == 200
        guide = resp.json()

    # Markdown is always available; html is now rendered (rendering slice landed).
    assert guide["markdown"]
    assert guide["html"]
    # Rendered HTML, with the YAML front matter stripped out.
    assert "<h1>" in guide["html"]
    assert "id: water-slow-sand-filter" not in guide["html"]


def test_get_guide_404():
    with TestClient(app) as client:
        resp = client.get("/api/guides/does-not-exist")
        assert resp.status_code == 404
