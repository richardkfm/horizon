"""Knowledge API + seeding tests.

These exercise the data-model → seed → Knowledge API slice end to end with no
external services running. Seeding loads the bundled content into SQLite via the
app lifespan; the assertions target stable seed ids.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from horizon.main import app
from horizon.models import Category


def test_seed_loads_curated_tracks():
    """The bundled seed exposes the curated multi-guide tracks."""
    with TestClient(app) as client:
        resp = client.get("/api/journeys")
        assert resp.status_code == 200
        journeys = resp.json()

    ids = {j["id"] for j in journeys}
    # The curated tracks are present…
    assert {
        "safe-drinking-water",
        "off-grid-power",
        "build-a-shelter",
        "grow-and-store-food",
    } <= ids
    # …and every track sits in a known category.
    categories = {j["category"] for j in journeys}
    assert categories <= {c.value for c in Category}


def test_list_journeys_category_filter():
    with TestClient(app) as client:
        resp = client.get("/api/journeys", params={"category": "water"})
        assert resp.status_code == 200
        water = resp.json()
        assert water  # non-empty
        assert all(j["category"] == "water" for j in water)

        bad = client.get("/api/journeys", params={"category": "nonsense"})
        assert bad.status_code == 400


def test_get_track_detail_returns_ordered_guides():
    with TestClient(app) as client:
        resp = client.get("/api/journeys/safe-drinking-water")
        assert resp.status_code == 200
        journey = resp.json()

    assert journey["id"] == "safe-drinking-water"
    assert journey["category"] == "water"
    # Tracks have no prerequisite graph; the key stays for shape compatibility.
    assert journey["prerequisites"] == []
    # Guides are returned in their stored order, and carry their own context.
    guide_ids = [g["id"] for g in journey["guides"]]
    assert guide_ids == [
        "water-rainwater-harvesting",
        "water-wells-and-springs",
        "water-field-testing",
        "water-choosing-treatment",
        "water-slow-sand-filter",
    ]
    assert all("difficulty" in g and "estimated_time" in g for g in journey["guides"])


def test_get_journey_404():
    with TestClient(app) as client:
        resp = client.get("/api/journeys/does-not-exist")
        assert resp.status_code == 404


def test_thin_journey_is_hidden_from_list_and_detail():
    """A journey with fewer than 2 guides is never surfaced (CLAUDE.md: plans
    are a curated multi-guide layer, a single guide never needs one).
    """
    from sqlmodel import Session, select

    from horizon.db import engine
    from horizon.models import Guide, Journey, JourneyGuideLink

    with Session(engine) as session:
        guide_id = session.exec(select(Guide.id)).first()
        session.add(Journey(id="thin-plan", title="Thin plan", category=Category.water))
        session.add(JourneyGuideLink(journey_id="thin-plan", guide_id=guide_id, position=0))
        session.commit()
    try:
        with TestClient(app) as client:
            ids = {j["id"] for j in client.get("/api/journeys").json()}
            assert "thin-plan" not in ids
            resp = client.get("/api/journeys/thin-plan")
            assert resp.status_code == 404
    finally:
        with Session(engine) as session:
            for link in session.exec(
                select(JourneyGuideLink).where(JourneyGuideLink.journey_id == "thin-plan")
            ).all():
                session.delete(link)
            journey = session.get(Journey, "thin-plan")
            if journey:
                session.delete(journey)
            session.commit()


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
