"""Retrieval-augmented generation index over guides + md skills (Chroma).

On startup horizon indexes every guide and md skill into an embedded Chroma
collection. Retrieval pulls the most relevant chunks for a question so the AI
assistant can ground and cite its answers in local content.

Offline-first and resilient by design:

* Building the index needs the embedding model (Ollama). If it is unavailable,
  :func:`reindex_content` logs and returns — it never crashes startup.
* :func:`retrieve` tries the vector index first, then transparently falls back
  to a pure keyword search over the same on-disk chunks. That fallback needs no
  external service, so retrieval (and citations) keep working fully offline and
  the logic stays unit-testable.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml

from horizon.config import settings

logger = logging.getLogger("horizon")

# Collection holding one entry per content chunk.
_COLLECTION = "horizon_content"

# Chunk guides/skills by paragraph, packing paragraphs up to this size. Small
# enough to stay focused on weak hardware, large enough to keep a step intact.
_MAX_CHUNK_CHARS = 1200

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Source kinds. Guides are citable local content; md skills only steer tone and
# values, so they are retrieved as context but never surfaced as citations.
_KIND_GUIDE = "guide"
_KIND_SKILL = "md_skill"


# --- Content loading & chunking (pure, no external services) ----------------


def _parse_front_matter(text: str) -> tuple[dict, str]:
    """Split a leading ``---`` YAML front-matter block from the Markdown body."""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            return yaml.safe_load(parts[1]) or {}, parts[2].lstrip("\n")
    return {}, text


def _chunk_text(body: str) -> list[str]:
    """Group paragraphs into chunks no larger than ``_MAX_CHUNK_CHARS``."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if current and len(current) + len(para) + 2 > _MAX_CHUNK_CHARS:
            chunks.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current:
        chunks.append(current)
    return chunks


def _load_chunks() -> list[dict]:
    """Read guides + md skills from disk into chunk records.

    Each record: ``id`` (unique), ``source_id`` (guide/skill id), ``kind``,
    ``title``, and ``text``. Pure: touches only the local content directory.
    """
    content_dir = Path(settings.content_dir)
    chunks: list[dict] = []
    for kind, subdir in ((_KIND_GUIDE, "guides"), (_KIND_SKILL, "md_skills")):
        directory = content_dir / subdir
        if not directory.is_dir():
            continue
        for md_path in sorted(directory.glob("*.md")):
            meta, body = _parse_front_matter(md_path.read_text(encoding="utf-8"))
            source_id = meta.get("id") or md_path.stem
            title = meta.get("title", source_id)
            for i, text in enumerate(_chunk_text(body)):
                chunks.append(
                    {
                        "id": f"{kind}:{source_id}#{i}",
                        "source_id": source_id,
                        "kind": kind,
                        "title": title,
                        "text": text,
                    }
                )
    return chunks


# --- Index build ------------------------------------------------------------


def reindex_content() -> None:
    """(Re)build the vector index from guides and md skills on disk.

    Resilient: any failure (no embedding model, no write access) is logged and
    swallowed so startup always completes. Retrieval then falls back to keyword
    search until the index can be built.
    """
    try:
        chunks = _load_chunks()
    except Exception as exc:  # noqa: BLE001 - never crash startup on content I/O
        logger.warning("Could not read content for indexing: %s", exc)
        return

    if not chunks:
        logger.info("No content found to index.")
        return

    from horizon.services.llm import LLMUnavailable, embed

    try:
        embeddings = embed([c["text"] for c in chunks])
    except LLMUnavailable as exc:
        logger.warning(
            "Vector index not built (embedding model unavailable); AI retrieval "
            "will use keyword fallback: %s",
            exc,
        )
        return

    try:
        import chromadb

        client = chromadb.PersistentClient(path=settings.vectordb.path)
        # Rebuild from scratch so the index always mirrors current content.
        try:
            client.delete_collection(_COLLECTION)
        except Exception:  # noqa: BLE001 - collection may not exist yet
            pass
        collection = client.create_collection(_COLLECTION)
        collection.add(
            ids=[c["id"] for c in chunks],
            embeddings=embeddings,
            documents=[c["text"] for c in chunks],
            metadatas=[
                {"source_id": c["source_id"], "kind": c["kind"], "title": c["title"]}
                for c in chunks
            ],
        )
        logger.info("Indexed %d content chunks into Chroma.", len(chunks))
    except Exception as exc:  # noqa: BLE001 - degrade to keyword retrieval
        logger.warning("Vector index build failed; using keyword fallback: %s", exc)


# --- Retrieval --------------------------------------------------------------


def retrieve(query: str, top_k: int | None = None) -> list[dict]:
    """Return the most relevant content chunks for a query, with source ids.

    Prefers the Chroma vector index; falls back to keyword search when the index
    or embedding model is unavailable. Returned records mirror :func:`_load_chunks`
    records (``source_id``, ``kind``, ``title``, ``text``).
    """
    k = top_k or settings.rag.top_k
    if not query or not query.strip():
        return []
    results = _retrieve_vector(query, k)
    if results is not None:
        return results
    return _retrieve_keyword(query, k)


def _retrieve_vector(query: str, top_k: int) -> list[dict] | None:
    """Query the Chroma index; return ``None`` (not ``[]``) to signal fallback."""
    from horizon.services.llm import LLMUnavailable, embed

    try:
        query_vec = embed([query])[0]
    except LLMUnavailable:
        return None

    try:
        import chromadb

        client = chromadb.PersistentClient(path=settings.vectordb.path)
        try:
            collection = client.get_collection(_COLLECTION)
        except Exception:  # noqa: BLE001 - index not built yet
            return None
        res = collection.query(query_embeddings=[query_vec], n_results=top_k)
    except Exception as exc:  # noqa: BLE001 - degrade to keyword retrieval
        logger.warning("Vector retrieval failed; using keyword fallback: %s", exc)
        return None

    ids = res["ids"][0]
    documents = res["documents"][0]
    metadatas = res["metadatas"][0]
    return [
        {
            "id": cid,
            "source_id": meta["source_id"],
            "kind": meta["kind"],
            "title": meta["title"],
            "text": doc,
        }
        for cid, doc, meta in zip(ids, documents, metadatas, strict=False)
    ]


def _tokenize(text: str) -> set[str]:
    return {tok for tok in _TOKEN_RE.findall(text.lower()) if len(tok) > 1}


def _retrieve_keyword(query: str, top_k: int) -> list[dict]:
    """Pure keyword-overlap retrieval over on-disk chunks (no external service)."""
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []
    scored: list[tuple[int, dict]] = []
    for chunk in _load_chunks():
        title_hits = len(query_tokens & _tokenize(chunk["title"]))
        body_hits = len(query_tokens & _tokenize(chunk["text"]))
        # Title matches weigh double; body matches add breadth.
        score = 2 * title_hits + body_hits
        if score > 0:
            scored.append((score, chunk))
    scored.sort(key=lambda pair: (-pair[0], pair[1]["id"]))
    return [chunk for _, chunk in scored[:top_k]]
