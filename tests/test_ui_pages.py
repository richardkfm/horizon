"""Web UI: error pages, caching/compression, navigation, browse lists, assistant."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from horizon.main import app
from horizon.models import Category

CATEGORY_ORDER = [c.value for c in Category]


# --- friendly errors, API errors unchanged ---------------------------------


def test_unknown_page_is_friendly_html_404():
    with TestClient(app) as client:
        resp = client.get("/no-such-page")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("text/html")
    assert "couldn&#39;t find that page" in resp.text
    assert 'action="/guides"' in resp.text  # search box
    for href in ('href="/guides"', 'href="/recommend"', 'href="/"'):
        assert href in resp.text


def test_unknown_guide_is_friendly_html_404():
    with TestClient(app) as client:
        resp = client.get("/guides/no-such-guide")
    assert resp.status_code == 404
    assert "couldn&#39;t find that guide" in resp.text


def test_bad_category_is_friendly_html_400():
    with TestClient(app) as client:
        resp = client.get("/guides?category=bogus")
    assert resp.status_code == 400
    assert "didn&#39;t quite work" in resp.text


def test_bad_query_type_is_friendly_html_422():
    with TestClient(app) as client:
        resp = client.get("/recommend?goal=x&people=lots")
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("text/html")


def test_api_errors_stay_json():
    with TestClient(app) as client:
        missing = client.get("/api/guides/no-such-guide")
        bad = client.get("/api/journeys?category=bogus")
        invalid = client.post("/api/recommend", json={})
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Guide not found: no-such-guide"}
    assert bad.status_code == 400
    assert "detail" in bad.json()
    assert invalid.status_code == 422
    assert isinstance(invalid.json()["detail"], list)


# --- performance -------------------------------------------------------------


def test_pages_are_gzipped():
    with TestClient(app) as client:
        resp = client.get("/guides", headers={"Accept-Encoding": "gzip"})
    assert resp.headers.get("content-encoding") == "gzip"


def test_static_cache_headers():
    with TestClient(app) as client:
        versioned = client.get("/static/app.css?v=abc123")
        plain = client.get("/static/app.css")
    assert "immutable" in versioned.headers["cache-control"]
    assert "max-age=31536000" in versioned.headers["cache-control"]
    assert "immutable" not in plain.headers["cache-control"]


def test_favicon_ico_is_served():
    with TestClient(app) as client:
        resp = client.get("/favicon.ico")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/svg+xml")


def test_htmx_only_where_used_and_no_alpine():
    with TestClient(app) as client:
        home = client.get("/")
        guide = client.get("/guides/survival-knots")
        assistant = client.get("/assistant")
    for page in (home, guide):
        assert "htmx.min.js" not in page.text
        assert "alpine" not in page.text.lower()
    assert "htmx.min.js" in assistant.text


# --- navigation & reading ----------------------------------------------------


def test_nav_marks_current_section():
    with TestClient(app) as client:
        index = client.get("/guides")
        guide = client.get("/guides/survival-knots")
    assert '<a href="/guides" aria-current="page">How-to guides</a>' in index.text
    assert '<a href="/guides" aria-current="true">How-to guides</a>' in guide.text


def test_guide_page_has_single_h1_and_difficulty_stamp():
    with TestClient(app) as client:
        resp = client.get("/guides/survival-knots")
    assert resp.text.count("<h1") == 1
    assert "Difficulty 1 of 5" in resp.text
    assert "[■□□□□]" in resp.text


def test_guides_overview_groups_by_category_in_enum_order():
    with TestClient(app) as client:
        resp = client.get("/guides")
    shelves = re.findall(r'<section class="guide-shelf" data-cat="([a-z]+)"', resp.text)
    assert shelves == [c for c in CATEGORY_ORDER if c in shelves]
    assert shelves[0] == "water"
    assert 'href="/guides?category=food">Show all' in resp.text


def test_filtered_guides_are_a_flat_list():
    with TestClient(app) as client:
        resp = client.get("/guides?category=water")
        search = client.get("/guides?q=water")
    assert "guide-shelf" not in resp.text
    assert "guide-shelf" not in search.text
    assert "/guides/water-slow-sand-filter" in resp.text


def test_search_links_are_url_encoded():
    with TestClient(app) as client:
        resp = client.get("/guides", params={"q": "a&b c"})
    assert "q=a%26b%20c" in resp.text


def test_plans_sorted_by_category_order():
    with TestClient(app) as client:
        resp = client.get("/journeys")
    cats = re.findall(r'<li class="track-card" data-cat="([a-z]+)"', resp.text)
    assert cats == sorted(cats, key=CATEGORY_ORDER.index)


def test_plan_detail_has_start_button():
    with TestClient(app) as client:
        resp = client.get("/journeys/safe-drinking-water")
    assert "Start with step 1" in resp.text
    assert 'class="trail"' in resp.text


def test_footer_shows_dashboard_with_admin_cookie():
    with TestClient(app) as client:
        anon = client.get("/")
        client.cookies.set("horizon_admin", "anything")
        signed = client.get("/")
    assert "Operator login" in anon.text
    assert ">Dashboard<" in signed.text


# --- assistant -----------------------------------------------------------------


def test_assistant_form_has_no_autofocus_and_requires_text():
    with TestClient(app) as client:
        resp = client.get("/assistant")
    assert "autofocus" not in resp.text
    assert "required" in resp.text
    assert "hx-disabled-elt" in resp.text


def test_empty_question_has_no_contradictory_no_match():
    with TestClient(app) as client:
        resp = client.post("/assistant/answer", data={"question": "   "})
    assert "Type a question first" in resp.text
    assert "No local guide matched" not in resp.text


def test_fallback_answer_links_guides_once(monkeypatch):
    from horizon.services.llm import LLMUnavailable

    def _no_model(*args, **kwargs):
        raise LLMUnavailable("off")

    monkeypatch.delenv("HORIZON_LOW_POWER", raising=False)
    monkeypatch.setattr("horizon.api.ai.generate", _no_model)
    with TestClient(app) as client:
        resp = client.post(
            "/assistant/answer", data={"question": "how do I make water safe to drink"}
        )
    assert resp.status_code == 200
    # Linked in the answer itself, with no raw [guide-id] tags...
    assert 'class="xref" href="/guides/water-slow-sand-filter"' in resp.text
    assert "[water-slow-sand-filter]" not in resp.text
    # ...and not repeated under Sources.
    assert "<h3>Sources</h3>" not in resp.text


def test_unexpected_crash_is_friendly_html_500_but_api_stays_plain(monkeypatch):
    from fastapi.routing import APIRoute

    def boom() -> None:
        raise RuntimeError("boom")

    routes = [APIRoute("/__boom", boom), APIRoute("/api/__boom", boom)]
    monkeypatch.setattr(app.router, "routes", routes + app.router.routes)
    with TestClient(app, raise_server_exceptions=False) as client:
        page = client.get("/__boom")
        api = client.get("/api/__boom")
    assert page.status_code == 500
    assert page.headers["content-type"].startswith("text/html")
    assert 'action="/guides"' in page.text
    assert api.status_code == 500
    assert api.text == "Internal Server Error"
