"""AI assistant + RAG tests.

These run fully offline (no Ollama/Chroma). Retrieval exercises the pure keyword
fallback, and the answer endpoint exercises both the local-content fallback (no
model) and a monkeypatched model path. The app lifespan seeds bundled content,
so assertions target stable seed ids.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from horizon.main import app
from horizon.services import llm, rag


def test_load_chunks_includes_guides_and_skills():
    with TestClient(app):  # trigger lifespan seeding
        chunks = rag._load_chunks()
    kinds = {c["kind"] for c in chunks}
    source_ids = {c["source_id"] for c in chunks}
    assert kinds == {"guide", "md_skill"}
    assert "water-slow-sand-filter" in source_ids  # a guide
    assert "values" in source_ids  # an md skill


def test_retrieve_keyword_fallback_finds_water_guide():
    """With no embedding model, retrieve falls back to keyword search."""
    with TestClient(app):
        chunks = rag.retrieve("how do I make river water safe to drink")
    guide_ids = {c["source_id"] for c in chunks if c["kind"] == "guide"}
    assert "water-slow-sand-filter" in guide_ids


def test_retrieve_empty_query_is_empty():
    with TestClient(app):
        assert rag.retrieve("   ") == []


def test_embed_empty_returns_empty():
    # Pure short-circuit: no network call, no model needed.
    assert llm.embed([]) == []


def test_api_answer_offline_falls_back_to_local_guides():
    """No model running: the endpoint still returns 200 with cited guides."""
    with TestClient(app) as client:
        resp = client.post(
            "/api/ai/answer",
            json={"question": "how do I make water safe to drink"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "water-slow-sand-filter" in data["citations"]
    assert data["answer"]  # non-empty fallback text


def test_api_answer_no_match_has_empty_citations():
    with TestClient(app) as client:
        resp = client.post("/api/ai/answer", json={"question": "xyzzy qwerty nonsense"})
    assert resp.status_code == 200
    assert resp.json()["citations"] == []


def test_api_answer_uses_model_when_available(monkeypatch):
    """When generation succeeds, its output is returned (citations still local)."""

    def fake_generate(system, prompt, *, no_jargon=False):
        assert "horizon" in system.lower()  # values/answer-style steering present
        return "Boil it or run it through a slow sand filter [water-slow-sand-filter]."

    monkeypatch.setattr("horizon.api.ai.generate", fake_generate)
    with TestClient(app) as client:
        resp = client.post(
            "/api/ai/answer",
            json={"question": "how do I make water safe to drink"},
        )
    data = resp.json()
    assert data["answer"].startswith("Boil it")
    assert "water-slow-sand-filter" in data["citations"]


def test_assistant_page_renders_form():
    with TestClient(app) as client:
        resp = client.get("/assistant")
    assert resp.status_code == 200
    assert 'name="question"' in resp.text


def test_assistant_answer_fragment_links_cited_guide():
    with TestClient(app) as client:
        resp = client.post(
            "/assistant/answer",
            data={"question": "how do I make water safe to drink"},
        )
    assert resp.status_code == 200
    assert "/guides/water-slow-sand-filter" in resp.text
