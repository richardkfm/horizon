"""Hardening regressions for the LLM client, retrieval, and index builds."""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from horizon.config import settings
from horizon.main import app
from horizon.services import llm, rag
from horizon.services.plaintext import wiki_link_targets, wiki_links_to_text


def _mock_runtime(monkeypatch, body: bytes, status: int = 200) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=body, headers={"content-type": "application/json"})

    monkeypatch.setattr(
        llm, "_client", lambda timeout: httpx.Client(transport=httpx.MockTransport(handler))
    )


@pytest.mark.parametrize(
    "body",
    [
        b"<html>proxy error</html>",
        b'{"unexpected": true}',
        b"[1, 2, 3]",
        b'{"response": 5, "embedding": "nope"}',
        b'{"embedding": []}',
        b'{"choices": [], "data": [{"index": 0}]}',
    ],
)
@pytest.mark.parametrize("provider", ["ollama", "openai-compatible"])
def test_malformed_model_responses_raise_llm_unavailable(monkeypatch, body, provider):
    monkeypatch.setattr(settings.llm, "provider", provider)
    _mock_runtime(monkeypatch, body)
    with pytest.raises(llm.LLMUnavailable):
        llm.generate("system", "prompt")
    with pytest.raises(llm.LLMUnavailable):
        llm.embed(["text"])


def test_well_formed_model_responses_still_work(monkeypatch):
    monkeypatch.setattr(settings.llm, "provider", "ollama")
    _mock_runtime(monkeypatch, b'{"response": " hi ", "embedding": [0.1, 2]}')
    assert llm.generate("s", "p") == "hi"
    assert llm.embed(["a", "b"]) == [[0.1, 2], [0.1, 2]]


def test_answer_endpoint_degrades_on_garbage_model_output(monkeypatch):
    monkeypatch.delenv("HORIZON_LOW_POWER", raising=False)
    _mock_runtime(monkeypatch, b"not json at all")
    with TestClient(app) as client:
        resp = client.post("/api/ai/answer", json={"question": "how do I filter water"})
    assert resp.status_code == 200
    assert resp.json()["citations"]


def test_retrieve_never_raises(monkeypatch):
    monkeypatch.delenv("HORIZON_LOW_POWER", raising=False)

    def boom(*args, **kwargs):
        raise RuntimeError("chroma exploded")

    monkeypatch.setattr(rag, "_retrieve_vector", boom)
    with TestClient(app):
        assert rag.retrieve("water filter")  # keyword fallback still answers
    monkeypatch.setattr(rag, "_retrieve_keyword", boom)
    assert rag.retrieve("water filter") == []


def test_low_power_retrieval_never_embeds(monkeypatch):
    monkeypatch.setenv("HORIZON_LOW_POWER", "1")

    def no_embed(texts):  # pragma: no cover - must not be reached
        raise AssertionError("embed() called in low-power mode")

    monkeypatch.setattr(llm, "embed", no_embed)
    with TestClient(app):
        assert rag.retrieve("water filter")


def test_reindex_without_chromadb_never_embeds(monkeypatch):
    monkeypatch.setattr(rag, "chromadb_available", lambda: False)

    def no_embed(texts):  # pragma: no cover - must not be reached
        raise AssertionError("embedded chunks with no vector store to put them in")

    monkeypatch.setattr(llm, "embed", no_embed)
    rag.reindex_content()
    assert rag.start_background_reindex() is None


def test_reindex_never_raises(monkeypatch):
    monkeypatch.setattr(rag, "_reindex_locked", lambda force: 1 / 0)
    rag.reindex_content()  # logged, not raised


def test_reindex_skips_unchanged_content(monkeypatch, tmp_path):
    pytest.importorskip("chromadb")
    monkeypatch.setattr(settings.vectordb, "path", str(tmp_path / "chroma"))
    calls: list[int] = []

    def fake_embed(texts):
        calls.append(len(texts))
        return [[0.1, 0.2, 0.3] for _ in texts]

    monkeypatch.setattr(llm, "embed", fake_embed)
    with TestClient(app):  # seed content
        pass
    rag.reindex_content()
    assert len(calls) == 1
    rag.reindex_content()  # content + model unchanged: no re-embedding
    assert len(calls) == 1
    rag.reindex_content(force=True)
    assert len(calls) == 2
    monkeypatch.setattr(settings.llm, "embedding_model", "another-model")
    rag.reindex_content()  # a different embedding model invalidates the index
    assert len(calls) == 3


def test_startup_reindex_runs_in_background(monkeypatch):
    monkeypatch.delenv("HORIZON_LOW_POWER", raising=False)
    started: list[bool] = []
    monkeypatch.setattr(rag, "start_background_reindex", lambda: started.append(True))
    monkeypatch.setattr(
        rag, "reindex_content", lambda **k: pytest.fail("startup must not reindex inline")
    )
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
    assert started == [True]


# --- wiki links in plain-text paths ------------------------------------------


def test_wiki_links_to_text():
    titles = {("guide", "water-boil"): "Boil water", ("plan", "safe-water"): "Safe water"}
    text = (
        "See [[water-boil]], [[water-boil|boiling]], [[plan:safe-water]], "
        "[[checklist:go-bag]] and [[guide:unknown-id]]."
    )
    out = wiki_links_to_text(text, lambda kind, i: titles.get((kind, i)))
    assert out == "See Boil water, boiling, Safe water, go-bag and unknown-id."
    assert wiki_links_to_text("[[a|b]] [[c]]") == "b c"
    assert wiki_link_targets("[[plan:x]] [[y|z]]") == [("plan", "x"), ("guide", "y")]


def test_rag_chunks_resolve_wiki_links(monkeypatch, tmp_path):
    content = tmp_path / "content"
    (content / "guides").mkdir(parents=True)
    (content / "checklists").mkdir()
    (content / "guides" / "a.md").write_text(
        "---\nid: a\ntitle: Alpha guide\ncategory: water\n---\n"
        "Read [[b]] then [[b|the other one]], [[plan:p]] and [[checklist:c]].\n",
        "utf-8",
    )
    (content / "guides" / "b.md").write_text(
        "---\nid: b\ntitle: Beta guide\ncategory: water\n---\nbody\n", "utf-8"
    )
    (content / "checklists" / "c.md").write_text("---\nid: c\ntitle: Go bag\n---\n- [ ] x\n")
    (content / "journeys.yaml").write_text("journeys:\n  - id: p\n    title: Plan P\n")
    monkeypatch.setattr(settings, "content_dir", str(content))
    text = next(c["text"] for c in rag._load_chunks() if c["source_id"] == "a")
    assert text == "Read Beta guide then the other one, Plan P and Go bag."


def test_cli_guide_prints_link_words(monkeypatch):
    from horizon.scripts import admin as cli

    out = cli._markdown_to_text(
        "Try [[water-slow-sand-filter]] or [[x|this]].",
        lambda kind, i: "Slow sand filter" if i == "water-slow-sand-filter" else None,
    )
    assert out == "Try Slow sand filter or this."
