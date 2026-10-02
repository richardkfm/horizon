"""Retrieval-augmented generation index over guides + md skills (Chroma).

On startup horizon indexes every guide and md skill into an embedded Chroma
collection. Retrieval pulls the most relevant chunks for a question so the AI
assistant can ground and cite its answers in local content.

Offline-first and resilient by design:

* Building the index needs the optional ``chromadb`` extra and the embedding
  model (Ollama). If either is unavailable, :func:`reindex_content` logs and
  returns — it never raises, so it can't crash startup.
* The index is only rebuilt when the content (or the embedding model) has
  changed since the last successful build: a fingerprint of the chunk set is
  stored next to the index, so a routine reboot doesn't re-embed every chunk.
  At startup the build runs in a background thread
  (:func:`start_background_reindex`) so the node serves pages immediately.
* :func:`retrieve` tries the vector index first, then transparently falls back
  to a pure keyword search over the same on-disk chunks. That fallback needs no
  external service, so retrieval (and citations) keep working fully offline and
  the logic stays unit-testable. In low-power mode the vector path (which calls
  the embedding model) is skipped entirely. ``retrieve`` never raises.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import logging
import os
import re
import threading
from pathlib import Path

import yaml

from horizon.config import low_power_enabled, settings
from horizon.services.frontmatter import split_front_matter
from horizon.services.plaintext import wiki_links_to_text

logger = logging.getLogger("horizon")


def _import_chromadb():
    """Import chromadb lazily with telemetry disabled.

    chromadb is the optional ``ai`` extra; importing it here (not at module load)
    keeps horizon bootable without it. We also pin off Chroma's anonymous usage
    telemetry so the node makes no outbound calls, honouring offline-first even
    on bare-metal installs where the Docker env var isn't set.
    """
    os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")
    import chromadb

    return chromadb


# Collection holding one entry per content chunk.
_COLLECTION = "horizon_content"

# Chunk guides/skills by paragraph, packing paragraphs up to this size. Small
# enough to stay focused on weak hardware, large enough to keep a step intact.
_MAX_CHUNK_CHARS = 1200

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Fingerprint of the last successful index build, stored next to the index.
_FINGERPRINT_FILE = "horizon_index_fingerprint.json"

# Serialises index builds: the startup background thread and an admin/CLI
# rebuild must never write the Chroma collection at the same time.
_INDEX_LOCK = threading.Lock()
_background_thread: threading.Thread | None = None

# Source kinds. Guides are citable local content; md skills only steer tone and
# values, so they are retrieved as context but never surfaced as citations.
_KIND_GUIDE = "guide"
_KIND_SKILL = "md_skill"


# --- Content loading & chunking (pure, no external services) ----------------


def _parse_front_matter(text: str) -> tuple[dict, str]:
    """Split a leading ``---`` YAML front-matter block from the Markdown body.

    Lenient: unusable metadata reads as ``{}`` so one bad file never breaks
    retrieval for the rest.
    """
    return split_front_matter(text)


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


def _other_titles(content_dir: Path) -> dict[str, dict[str, str]]:
    """Plan and checklist titles, for turning ``[[plan:id]]`` links into words."""
    titles: dict[str, dict[str, str]] = {"plan": {}, "checklist": {}}
    try:
        data = yaml.safe_load((content_dir / "journeys.yaml").read_text(encoding="utf-8"))
        for entry in (data or {}).get("journeys") or []:
            if isinstance(entry, dict) and entry.get("id"):
                titles["plan"][str(entry["id"])] = str(entry.get("title") or entry["id"])
    except Exception:  # noqa: BLE001 - titles are a nicety; ids are the fallback
        pass
    checklists = content_dir / "checklists"
    if checklists.is_dir():
        for md_path in sorted(checklists.glob("*.md")):
            try:
                meta, _ = _parse_front_matter(md_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError):
                continue
            checklist_id = str(meta.get("id") or md_path.stem)
            titles["checklist"][checklist_id] = str(meta.get("title") or checklist_id)
    return titles


def _load_chunks() -> list[dict]:
    """Read guides + md skills from disk into chunk records.

    Each record: ``id`` (unique), ``source_id`` (guide/skill id), ``kind``,
    ``title``, and ``text``. Pure: touches only the local content directory.
    Wiki links (``[[guide-id]]``, ``[[plan:id|text]]``, ...) are replaced by
    their words (custom text, else the target's title, else its id) so the
    model and keyword search see readable prose, not link syntax.
    """
    content_dir = Path(settings.content_dir)
    docs: list[tuple[str, str, str, str]] = []  # (kind, source_id, title, body)
    for kind, subdir in ((_KIND_GUIDE, "guides"), (_KIND_SKILL, "md_skills")):
        directory = content_dir / subdir
        if not directory.is_dir():
            continue
        for md_path in sorted(directory.glob("*.md")):
            try:
                meta, body = _parse_front_matter(md_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError) as exc:
                logger.warning("Skipping %s for search: %s", md_path.name, exc)
                continue
            source_id = str(meta.get("id") or md_path.stem)
            title = str(meta.get("title") or source_id)
            docs.append((kind, source_id, title, body))

    resolve = None
    if any("[[" in body for *_rest, body in docs):
        titles = _other_titles(content_dir)
        titles["guide"] = {sid: title for kind, sid, title, _ in docs if kind == _KIND_GUIDE}

        def resolve(link_kind: str, target: str) -> str | None:
            return titles.get(link_kind, {}).get(target)

    chunks: list[dict] = []
    for kind, source_id, title, body in docs:
        if resolve is not None:
            body = wiki_links_to_text(body, resolve)
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


def chromadb_available() -> bool:
    """True when the optional ``ai`` extra (chromadb) is installed. Cheap: no import."""
    try:
        return importlib.util.find_spec("chromadb") is not None
    except (ImportError, ValueError):
        return False


def _fingerprint(chunks: list[dict]) -> str:
    """Hash of everything that determines the index contents."""
    digest = hashlib.sha256()
    digest.update(f"{settings.llm.provider}\0{settings.llm.embedding_model}\0".encode())
    for chunk in chunks:
        for key in ("id", "source_id", "kind", "title", "text"):
            digest.update(str(chunk[key]).encode("utf-8", errors="replace"))
            digest.update(b"\0")
    return digest.hexdigest()


def _fingerprint_path() -> Path:
    return Path(settings.vectordb.path) / _FINGERPRINT_FILE


def _read_fingerprint() -> dict:
    try:
        data = json.loads(_fingerprint_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_fingerprint(fingerprint: str, count: int) -> None:
    path = _fingerprint_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        payload = {
            "fingerprint": fingerprint,
            "embedding_model": settings.llm.embedding_model,
            "chunks": count,
        }
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(tmp, path)
    except OSError as exc:
        logger.warning("Could not record the search-index fingerprint: %s", exc)


def _index_is_current(chromadb, fingerprint: str, count: int) -> bool:
    """True when the stored fingerprint matches and the collection holds ``count`` chunks."""
    recorded = _read_fingerprint()
    if recorded.get("fingerprint") != fingerprint:
        return False
    try:
        client = chromadb.PersistentClient(path=settings.vectordb.path)
        return client.get_collection(_COLLECTION).count() == count
    except Exception:  # noqa: BLE001 - absent/unreadable collection => rebuild
        return False


def reindex_content(*, force: bool = False) -> None:
    """(Re)build the vector index from guides and md skills on disk.

    Synchronous (the admin repair and the CLI call it and wait). Skips work
    when it can't or needn't run: without the optional ``chromadb`` extra it
    returns before embedding anything, and unless ``force`` is set it returns
    early when the stored fingerprint shows the content and embedding model are
    unchanged since the last successful build.

    Resilient: any failure (no embedding model, no write access, a malformed
    model response) is logged and swallowed so callers never see an exception.
    Retrieval then falls back to keyword search until the index can be built.
    """
    try:
        with _INDEX_LOCK:
            _reindex_locked(force=force)
    except Exception as exc:  # noqa: BLE001 - never raise to startup/admin callers
        logger.warning("Vector index build failed; using keyword fallback: %s", exc)


def _reindex_locked(*, force: bool) -> None:
    if not chromadb_available():
        logger.info(
            "Vector index not built: the optional 'ai' extra is not installed, so "
            "chromadb is unavailable; AI retrieval will use keyword fallback. "
            "Install it with `pip install 'horizon[ai]'` to enable vector search."
        )
        return

    try:
        chunks = _load_chunks()
    except Exception as exc:  # noqa: BLE001 - never crash startup on content I/O
        logger.warning("Could not read content for indexing: %s", exc)
        return

    if not chunks:
        logger.info("No content found to index.")
        return

    try:
        chromadb = _import_chromadb()
    except Exception as exc:  # noqa: BLE001 - a broken install behaves like a missing one
        logger.warning(
            "Vector index not built: chromadb could not be imported (%s); AI retrieval "
            "will use keyword fallback.",
            exc,
        )
        return

    fingerprint = _fingerprint(chunks)
    if not force and _index_is_current(chromadb, fingerprint, len(chunks)):
        logger.info("Search index is up to date (%d chunks); skipping rebuild.", len(chunks))
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
    if len(embeddings) != len(chunks):
        logger.warning(
            "Vector index not built: the embedding model returned %d vectors for %d "
            "chunks; AI retrieval will use keyword fallback.",
            len(embeddings),
            len(chunks),
        )
        return

    try:
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
        _write_fingerprint(fingerprint, len(chunks))
        logger.info("Indexed %d content chunks into Chroma.", len(chunks))
    except Exception as exc:  # noqa: BLE001 - degrade to keyword retrieval
        logger.warning("Vector index build failed; using keyword fallback: %s", exc)


def start_background_reindex() -> threading.Thread | None:
    """Run :func:`reindex_content` in a daemon thread so startup isn't blocked.

    Returns the thread, or ``None`` when there is nothing to do (no chromadb)
    or a background build is already running.
    """
    global _background_thread
    if not chromadb_available():
        logger.info(
            "Vector search is not installed (optional 'ai' extra); the assistant "
            "uses offline keyword search."
        )
        return None
    if _background_thread is not None and _background_thread.is_alive():
        return None
    thread = threading.Thread(target=reindex_content, name="horizon-reindex", daemon=True)
    _background_thread = thread
    thread.start()
    return thread


def index_stats() -> dict:
    """Describe the vector index versus the content on disk, cheaply.

    Used by the admin health view to tell an operator whether the search index
    is present and current. Deliberately needs **no** embedding model: it only
    counts on-disk chunks and reads the existing Chroma collection's size, so it
    is safe to run on every page load and in low-power mode.

    Returns ``chromadb_installed`` (is the optional ``ai`` extra present),
    ``index_built`` (does the collection exist), ``indexed_chunks`` (its size, or
    ``None``), and ``disk_chunks`` (chunks the current content would produce).
    """
    try:
        disk_chunks: int | None = len(_load_chunks())
    except Exception:  # noqa: BLE001 - report rather than crash the health view
        disk_chunks = None

    try:
        chromadb = _import_chromadb()
    except ImportError:
        return {
            "chromadb_installed": False,
            "index_built": False,
            "indexed_chunks": None,
            "disk_chunks": disk_chunks,
        }

    try:
        client = chromadb.PersistentClient(path=settings.vectordb.path)
        collection = client.get_collection(_COLLECTION)
        indexed = collection.count()
        return {
            "chromadb_installed": True,
            "index_built": True,
            "indexed_chunks": indexed,
            "disk_chunks": disk_chunks,
        }
    except Exception:  # noqa: BLE001 - collection absent or store unreadable
        return {
            "chromadb_installed": True,
            "index_built": False,
            "indexed_chunks": None,
            "disk_chunks": disk_chunks,
        }


# --- Retrieval --------------------------------------------------------------


def retrieve(query: str, top_k: int | None = None) -> list[dict]:
    """Return the most relevant content chunks for a query, with source ids.

    Prefers the Chroma vector index; falls back to keyword search when the index
    or embedding model is unavailable, and always in low-power mode (vector
    search embeds the query, i.e. runs the model). Never raises: on any failure
    it returns what keyword search finds, or ``[]``. Returned records mirror
    :func:`_load_chunks` records (``source_id``, ``kind``, ``title``, ``text``).
    """
    k = top_k or settings.rag.top_k
    if not query or not query.strip():
        return []
    if not low_power_enabled():
        try:
            results = _retrieve_vector(query, k)
        except Exception as exc:  # noqa: BLE001 - degrade to keyword retrieval
            logger.warning("Vector retrieval failed; using keyword fallback: %s", exc)
            results = None
        if results is not None:
            return results
    try:
        return _retrieve_keyword(query, k)
    except Exception as exc:  # noqa: BLE001 - retrieval must never fail the caller
        logger.warning("Keyword retrieval failed: %s", exc)
        return []


def _retrieve_vector(query: str, top_k: int) -> list[dict] | None:
    """Query the Chroma index; return ``None`` (not ``[]``) to signal fallback."""
    if not chromadb_available():
        # Optional 'ai' extra not installed: don't spend a model call on
        # embedding a query there is no index to search with.
        return None

    from horizon.services.llm import LLMUnavailable, embed

    try:
        chromadb = _import_chromadb()
    except Exception:  # noqa: BLE001 - broken/missing extra => keyword retrieval
        return None

    try:
        client = chromadb.PersistentClient(path=settings.vectordb.path)
        try:
            collection = client.get_collection(_COLLECTION)
        except Exception:  # noqa: BLE001 - index not built yet
            return None
    except Exception as exc:  # noqa: BLE001 - degrade to keyword retrieval
        logger.warning("Vector retrieval failed; using keyword fallback: %s", exc)
        return None

    try:
        query_vec = embed([query])[0]
    except (LLMUnavailable, IndexError):
        return None

    try:
        res = collection.query(query_embeddings=[query_vec], n_results=top_k)
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
    except Exception as exc:  # noqa: BLE001 - degrade to keyword retrieval
        logger.warning("Vector retrieval failed; using keyword fallback: %s", exc)
        return None


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
