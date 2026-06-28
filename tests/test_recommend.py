"""Recommendation service, API, and scenario-page tests.

Pure keyword matching over the seeded content — no LLM or vector DB. The app
lifespan seeds the bundled journeys/guides, so assertions target stable seed ids.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from horizon.main import app
from horizon.services.recommend import recommend_journeys


def test_service_matches_food_goal():
    with TestClient(app):  # trigger lifespan seeding
        result = recommend_journeys("grow staple crops")
    guide_ids = {g["id"] for g in result["guides"]}
    track_ids = {j["id"] for j in result["journeys"]}
    # Guides are the primary unit; the staple-crops guide leads.
    assert "food-staple-crops-500m2" in guide_ids
    # The matching curated track is surfaced alongside.
    assert "grow-and-store-food" in track_ids


def test_service_water_goal_surfaces_guides_and_track():
    with TestClient(app):
        result = recommend_journeys("safe drinking water for our group")
    track_ids = {j["id"] for j in result["journeys"]}
    guide_ids = {g["id"] for g in result["guides"]}
    assert "water-slow-sand-filter" in guide_ids
    assert "safe-drinking-water" in track_ids


def test_generic_words_do_not_pull_off_topic_results():
    """A water goal should not surface cooperation just because both say 'group'."""
    with TestClient(app):
        result = recommend_journeys("safe drinking water for our group")
    guide_ids = {g["id"] for g in result["guides"]}
    assert "water-slow-sand-filter" in guide_ids
    assert "cooperation-group-decisions" not in guide_ids


def test_resources_context_is_folded_in():
    """A solar resource should surface the solar guide even for a vague goal."""
    with TestClient(app):
        result = recommend_journeys("set up power", resources=["solar"])
    guide_ids = {g["id"] for g in result["guides"]}
    assert "energy-low-tech-solar" in guide_ids


def test_empty_goal_returns_empty():
    with TestClient(app):
        result = recommend_journeys("   ")
    assert result == {"journeys": [], "guides": []}


def test_api_recommend_returns_ranked_results():
    with TestClient(app) as client:
        resp = client.post("/api/recommend", json={"goal": "safe drinking water"})
    assert resp.status_code == 200
    data = resp.json()
    assert "journeys" in data and "guides" in data
    assert data["journeys"]  # non-empty
    assert data["journeys"][0]["category"] == "water"


def test_api_recommend_no_match_is_empty_not_error():
    with TestClient(app) as client:
        resp = client.post("/api/recommend", json={"goal": "xyzzy nonsense qwerty"})
    assert resp.status_code == 200
    assert resp.json() == {"journeys": [], "guides": []}


def test_recommend_page_renders_form():
    with TestClient(app) as client:
        resp = client.get("/recommend")
    assert resp.status_code == 200
    assert 'name="goal"' in resp.text


def test_recommend_page_shows_results():
    with TestClient(app) as client:
        resp = client.get("/recommend", params={"goal": "safe drinking water"})
    assert resp.status_code == 200
    # Guides lead the results; the matching curated plan is shown too.
    assert "/guides/water-slow-sand-filter" in resp.text
    assert "/journeys/safe-drinking-water" in resp.text
