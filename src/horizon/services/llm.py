"""Local LLM client (Ollama by default; llama.cpp OpenAI-compatible optional).

Used for both answer generation and embeddings. All calls go to a local-network
endpoint, so we deliberately bypass any ambient HTTP proxy (``trust_env=False``)
to keep the path offline-first. horizon degrades gracefully: every entry point
raises :class:`LLMUnavailable` when the runtime cannot be reached, and callers
(RAG indexing, the AI API) catch it and fall back rather than failing the app.
"""

from __future__ import annotations

import httpx

from horizon.config import settings

# Generation can be slow on weak hardware; embeddings are quick. Connect fast so
# an absent runtime fails promptly instead of hanging requests (and tests).
_GENERATE_TIMEOUT = httpx.Timeout(120.0, connect=5.0)
_EMBED_TIMEOUT = httpx.Timeout(60.0, connect=5.0)

_NO_JARGON_NOTE = (
    "\n\nPlain-language mode is ON: avoid technical jargon. When a technical term "
    "is unavoidable, explain it in simple words a beginner can follow."
)


class LLMUnavailable(RuntimeError):
    """The local model runtime is unreachable or returned an unusable response."""


# A runtime that answers 200 with something other than the JSON we expect (a
# proxy error page, a different API version, a truncated body) surfaces as one
# of these while decoding; treat it exactly like an unreachable runtime.
_BAD_RESPONSE_ERRORS = (ValueError, KeyError, IndexError, TypeError, AttributeError)


def _check_vectors(vectors: object, expected: int) -> list[list[float]]:
    """Validate an embedding response: ``expected`` non-empty numeric vectors."""
    if not isinstance(vectors, list) or len(vectors) != expected:
        raise ValueError(f"expected {expected} embedding(s), got {type(vectors).__name__}")
    for vec in vectors:
        if not isinstance(vec, list) or not vec:
            raise ValueError("embedding is not a non-empty list")
        if not all(isinstance(x, int | float) and not isinstance(x, bool) for x in vec):
            raise ValueError("embedding holds non-numeric values")
    return vectors


def generate(system: str, prompt: str, *, no_jargon: bool = False) -> str:
    """Generate a completion from the local model.

    Raises :class:`LLMUnavailable` if the runtime cannot be reached so callers
    can fall back to local content instead of surfacing an error.
    """
    if no_jargon:
        system = system + _NO_JARGON_NOTE
    try:
        if settings.llm.provider == "openai-compatible":
            return _generate_openai(system, prompt)
        return _generate_ollama(system, prompt)
    except (httpx.HTTPError, httpx.InvalidURL) as exc:
        raise LLMUnavailable(f"LLM generation failed: {exc}") from exc
    except _BAD_RESPONSE_ERRORS as exc:
        raise LLMUnavailable(f"LLM returned an unexpected response: {exc!r}") from exc


def embed(texts: list[str]) -> list[list[float]]:
    """Return embedding vectors for the given texts (one per input, in order)."""
    if not texts:
        return []
    try:
        if settings.llm.provider == "openai-compatible":
            vectors = _embed_openai(texts)
        else:
            vectors = _embed_ollama(texts)
        return _check_vectors(vectors, len(texts))
    except (httpx.HTTPError, httpx.InvalidURL) as exc:
        raise LLMUnavailable(f"Embedding request failed: {exc}") from exc
    except _BAD_RESPONSE_ERRORS as exc:
        raise LLMUnavailable(f"Embedding model returned an unexpected response: {exc!r}") from exc


def available() -> bool:
    """Quick, side-effect-free check that the local model runtime is reachable.

    Used by the admin integrations view. Never raises: any error (including an
    absent runtime) returns ``False`` so the rest of the app keeps working.
    """
    # Ollama lists pulled models at /api/tags; the OpenAI-compatible servers
    # expose /v1/models. Both are cheap and need no model loaded.
    path = "/v1/models" if settings.llm.provider == "openai-compatible" else "/api/tags"
    try:
        with _client(httpx.Timeout(5.0, connect=3.0)) as client:
            resp = client.get(f"{_endpoint()}{path}")
            return resp.status_code < 500
    except Exception:  # noqa: BLE001 - e.g. httpx.HTTPError, or a malformed endpoint URL
        return False


def _endpoint() -> str:
    return settings.llm.endpoint.rstrip("/")


def _client(timeout: httpx.Timeout) -> httpx.Client:
    # trust_env=False: never route local model calls through an ambient proxy.
    return httpx.Client(trust_env=False, timeout=timeout)


# --- Ollama (default) -------------------------------------------------------


def _generate_ollama(system: str, prompt: str) -> str:
    payload = {
        "model": settings.llm.model,
        "system": system,
        "prompt": prompt,
        "stream": False,
    }
    with _client(_GENERATE_TIMEOUT) as client:
        resp = client.post(f"{_endpoint()}/api/generate", json=payload)
        resp.raise_for_status()
        text = resp.json()["response"]
        if not isinstance(text, str):
            raise TypeError("'response' is not a string")
        return text.strip()


def _embed_ollama(texts: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    with _client(_EMBED_TIMEOUT) as client:
        for text in texts:
            resp = client.post(
                f"{_endpoint()}/api/embeddings",
                json={"model": settings.llm.embedding_model, "prompt": text},
            )
            resp.raise_for_status()
            vectors.append(resp.json()["embedding"])
    return vectors


# --- OpenAI-compatible (e.g. llama.cpp server) ------------------------------


def _generate_openai(system: str, prompt: str) -> str:
    payload = {
        "model": settings.llm.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
    }
    with _client(_GENERATE_TIMEOUT) as client:
        resp = client.post(f"{_endpoint()}/v1/chat/completions", json=payload)
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"] or ""
        if not isinstance(text, str):
            raise TypeError("message content is not a string")
        return text.strip()


def _embed_openai(texts: list[str]) -> list[list[float]]:
    payload = {"model": settings.llm.embedding_model, "input": texts}
    with _client(_EMBED_TIMEOUT) as client:
        resp = client.post(f"{_endpoint()}/v1/embeddings", json=payload)
        resp.raise_for_status()
        data = sorted(resp.json()["data"], key=lambda row: row["index"])
        return [row["embedding"] for row in data]
