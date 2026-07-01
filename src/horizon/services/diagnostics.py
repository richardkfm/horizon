"""Content-health diagnostics and one-click repairs for the admin panel.

This is the engine behind **Admin → Health** (and the ``horizon-admin check``
command): it surfaces the real problems an operator needs to know about — broken
skill-tree links, missing guide files or images, content that has drifted out of
the search index, orphaned or duplicated content, and (optionally) an unreachable
model runtime — and offers the two repairs that fix most of them: rebuild the
search index, and re-seed the metadata from the content on disk.

Kept here in ``services/`` and deliberately **pure** in the CLAUDE.md sense: the
checks read only SQLite and the local content directory, so they are fully
unit-testable with no LLM or vector DB. The single network-ish probe (is the
local model reachable) is opt-in via ``check_model`` and skipped in low-power
mode, where horizon never reaches for the model anyway.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from sqlmodel import Session, select

from horizon.config import low_power_enabled, settings
from horizon.db import engine
from horizon.models import (
    Checklist,
    Guide,
    Journey,
    JourneyGuideLink,
)
from horizon.seed import _split_front_matter

logger = logging.getLogger("horizon")

# Check statuses. Plain words so they read the same in the panel, the CLI, and a
# JSON payload. ``off`` is informational (an optional capability is disabled by
# choice), never a problem.
OK = "ok"
WARN = "warn"
FAIL = "fail"
OFF = "off"

# Markdown image reference: ``![alt](src "optional title")``. We only need the src.
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(\s*([^)\s]+)")


def _check(id: str, name: str, status: str, summary: str, details: list[str] | None = None) -> dict:
    return {"id": id, "name": name, "status": status, "summary": summary, "details": details or []}


# --- Individual checks ------------------------------------------------------


def _check_database(session: Session) -> dict:
    """The one hard requirement: a readable metadata store with content in it."""
    try:
        n_journeys = len(session.exec(select(Journey)).all())
        n_guides = len(session.exec(select(Guide)).all())
        n_checklists = len(session.exec(select(Checklist)).all())
    except Exception as exc:  # noqa: BLE001 - report rather than crash
        return _check("database", "Database", FAIL, f"Unreadable: {exc}")
    if n_journeys == 0:
        return _check(
            "database",
            "Database",
            WARN,
            "No journeys in the database — re-seed to load the bundled content.",
        )
    return _check(
        "database",
        "Database",
        OK,
        f"{n_journeys} journeys, {n_guides} guides, and {n_checklists} checklists.",
    )


def _check_guide_links(session: Session) -> dict:
    """Track→guide links whose track or guide is missing."""
    journey_ids = set(session.exec(select(Journey.id)).all())
    guide_ids = set(session.exec(select(Guide.id)).all())
    broken = [
        f"{jid} → {gid}"
        for jid, gid in session.exec(
            select(JourneyGuideLink.journey_id, JourneyGuideLink.guide_id)
        ).all()
        if jid not in journey_ids or gid not in guide_ids
    ]
    if broken:
        return _check(
            "guide_links",
            "Guide links",
            WARN,
            f"{len(broken)} journey→guide link(s) point to missing content.",
            broken,
        )
    return _check("guide_links", "Guide links", OK, "All guide links resolve.")


def _check_guide_files(session: Session) -> dict:
    """Guides whose Markdown file is missing on disk (the reader 404s)."""
    guides_dir = Path(settings.content_dir) / "guides"
    missing = [
        f"{g.id} ({g.path})"
        for g in session.exec(select(Guide)).all()
        if not (guides_dir / g.path).is_file()
    ]
    if missing:
        return _check(
            "guide_files",
            "Guide files",
            FAIL,
            f"{len(missing)} guide(s) have no Markdown file on disk.",
            missing,
        )
    return _check("guide_files", "Guide files", OK, "Every guide has its file on disk.")


def _check_guide_images(session: Session) -> dict:
    """Local images referenced by a guide that are not on disk (broken image)."""
    guides_dir = Path(settings.content_dir) / "guides"
    missing: list[str] = []
    for g in session.exec(select(Guide)).all():
        md_path = guides_dir / g.path
        if not md_path.is_file():
            continue  # absence of the file itself is reported by _check_guide_files
        text = md_path.read_text(encoding="utf-8")
        for src in _IMAGE_RE.findall(text):
            # Skip remote/data URLs — offline-first guides should not use them,
            # but if one does it is not a *missing local file*.
            if src.startswith(("http://", "https://", "data:", "//")):
                continue
            # Resolve relative to the guides directory (where guide files and
            # their images/ folder live); tolerate a leading slash.
            target = guides_dir / src.lstrip("/")
            if not target.is_file():
                missing.append(f"{g.id}: {src}")
    if missing:
        return _check(
            "guide_images",
            "Guide images",
            WARN,
            f"{len(missing)} image(s) referenced by a guide are missing.",
            missing,
        )
    return _check("guide_images", "Guide images", OK, "All referenced images are present.")


def _check_orphans(session: Session) -> dict:
    """Content that is present but unreachable, or broken.

    Two kinds: tracks with fewer than two guides (not a real multi-step plan —
    see CLAUDE.md: a single guide never needs a plan wrapped around it), and
    guide Markdown files on disk with no database row (an extra file that was
    never seeded). A guide that belongs to no track is *not* orphaned — it is
    browsed and read directly from the library (/guides/{id}).
    """
    items: list[str] = []

    guide_counts: dict[str, int] = {}
    for jid in session.exec(select(JourneyGuideLink.journey_id)).all():
        guide_counts[jid] = guide_counts.get(jid, 0) + 1
    for j in session.exec(select(Journey)).all():
        n = guide_counts.get(j.id, 0)
        if n < 2:
            items.append(f"plan with fewer than 2 guides ({n}): {j.id}")

    # Guide files on disk that were never loaded into the database.
    db_paths = {g.path for g in session.exec(select(Guide)).all()}
    guides_dir = Path(settings.content_dir) / "guides"
    if guides_dir.is_dir():
        for md_path in sorted(guides_dir.glob("*.md")):
            if md_path.name not in db_paths:
                items.append(f"guide file on disk not in the database: {md_path.name}")

    if items:
        return _check(
            "orphans",
            "Orphaned content",
            WARN,
            f"{len(items)} item(s) are present but unreachable.",
            items,
        )
    return _check("orphans", "Orphaned content", OK, "No orphaned content.")


def _check_duplicates() -> dict:
    """Duplicate ids declared on disk that silently collapse when seeded.

    SQLite primary keys prevent duplicate rows, so two guide files (or md skills)
    claiming the same ``id`` don't both load — one silently wins. This is a real,
    invisible content bug, so we scan the files directly to catch it.
    """
    content_dir = Path(settings.content_dir)
    items: list[str] = []
    for label, subdir in (("guide", "guides"), ("md skill", "md_skills")):
        directory = content_dir / subdir
        if not directory.is_dir():
            continue
        seen: dict[str, str] = {}
        for md_path in sorted(directory.glob("*.md")):
            meta, _ = _split_front_matter(md_path.read_text(encoding="utf-8"))
            content_id = meta.get("id") or md_path.stem
            if content_id in seen:
                items.append(
                    f"duplicate {label} id {content_id!r}: {seen[content_id]} and {md_path.name}"
                )
            else:
                seen[content_id] = md_path.name
    if items:
        return _check(
            "duplicates",
            "Duplicate ids",
            WARN,
            f"{len(items)} duplicate id(s) on disk — one file silently wins.",
            items,
        )
    return _check("duplicates", "Duplicate ids", OK, "No duplicate content ids.")


def _check_search_index() -> dict:
    """Whether the vector search index is present and current.

    Cheap and offline (no embedding model): compares on-disk content chunks to
    the existing Chroma collection's size. Vector search is the optional ``ai``
    extra; when it is absent the assistant still answers via keyword search, so
    that is reported as ``off`` (by design), not a failure.
    """
    if low_power_enabled():
        return _check(
            "search_index",
            "Search index",
            OFF,
            "Paused for low power — the assistant uses offline keyword search.",
        )

    from horizon.services.rag import index_stats

    stats = index_stats()
    disk = stats["disk_chunks"]
    indexed = stats["indexed_chunks"]

    if not stats["chromadb_installed"]:
        return _check(
            "search_index",
            "Search index",
            OFF,
            "Vector search not installed (the optional 'ai' extra) — the assistant "
            "uses offline keyword search.",
        )
    if not stats["index_built"] or indexed == 0:
        return _check(
            "search_index",
            "Search index",
            WARN,
            "No vector index yet — rebuild it so the assistant can use semantic "
            "search (it falls back to keyword search until then).",
        )
    if disk is not None and indexed != disk:
        return _check(
            "search_index",
            "Search index",
            WARN,
            f"Index is out of date: {indexed} chunks indexed, {disk} on disk — "
            "rebuild to match the current content.",
        )
    return _check("search_index", "Search index", OK, f"{indexed} content chunks indexed.")


def _check_model_runtime(check_model: bool) -> dict:
    """The local model runtime (only probed when asked, never in low power)."""
    detail = f"{settings.llm.provider} · {settings.llm.endpoint}"
    if low_power_enabled():
        return _check(
            "model_runtime", "Local model runtime", OFF, f"Paused for low power ({detail})."
        )
    if not check_model:
        return _check(
            "model_runtime",
            "Local model runtime",
            OFF,
            f"Not checked — probing the model costs energy. {detail}",
        )
    from horizon.services import llm

    if llm.available():
        return _check("model_runtime", "Local model runtime", OK, f"Reachable ({detail}).")
    return _check(
        "model_runtime",
        "Local model runtime",
        WARN,
        f"Unreachable — the assistant falls back to keyword search ({detail}).",
    )


# --- Report -----------------------------------------------------------------


def run_checks(check_model: bool = False) -> dict:
    """Run every health check and return a structured report.

    ``check_model`` opts into probing the local model runtime (a network call
    that costs energy); it is left off by default and ignored in low-power mode.
    The report carries the per-check rows plus rollup counts and a ``healthy``
    flag (true when nothing is a hard failure).
    """
    with Session(engine) as session:
        checks = [
            _check_database(session),
            _check_guide_links(session),
            _check_guide_files(session),
            _check_guide_images(session),
            _check_orphans(session),
            _check_duplicates(),
            _check_search_index(),
            _check_model_runtime(check_model),
        ]

    counts = {
        OK: sum(1 for c in checks if c["status"] == OK),
        WARN: sum(1 for c in checks if c["status"] == WARN),
        FAIL: sum(1 for c in checks if c["status"] == FAIL),
        OFF: sum(1 for c in checks if c["status"] == OFF),
    }
    return {
        "checks": checks,
        "counts": counts,
        "healthy": counts[FAIL] == 0,
        "problems": counts[FAIL] + counts[WARN],
    }


# --- Repairs ----------------------------------------------------------------


def run_repair(action: str) -> dict:
    """Perform a one-click repair and return a result row for the panel.

    Supported actions:

    * ``reindex`` — rebuild the vector search index from content on disk.
    * ``reseed``  — reload the SQLite metadata from the content directory, then
      rebuild the index so search reflects the refreshed content.

    Both are low-power-aware: the index rebuild is the energy-hungry step, so it
    is skipped (with a clear note) when the node is in low-power mode rather than
    hammering a weak supply. The result dict has ``ok``, a short ``title``, and a
    human ``message``.
    """
    if action == "reindex":
        return _repair_reindex()
    if action == "reseed":
        return _repair_reseed()
    return {
        "ok": False,
        "title": "Unknown repair",
        "message": f"Unknown repair action: {action!r}.",
    }


def _repair_reindex() -> dict:
    if low_power_enabled():
        return {
            "ok": False,
            "title": "Rebuild search index",
            "message": "Skipped: the node is in low-power mode, so the energy-hungry "
            "index build is paused. The assistant uses offline keyword search "
            "meanwhile. Turn off low-power mode to rebuild.",
        }
    from horizon.services.rag import index_stats, reindex_content

    reindex_content()
    stats = index_stats()
    indexed = stats["indexed_chunks"]
    if stats["index_built"] and indexed:
        message = f"Rebuilt the search index: {indexed} content chunks indexed."
    else:
        message = (
            "Index not built — the embedding model was unavailable or the optional "
            "'ai' extra is not installed. The assistant uses offline keyword search "
            "until the model is reachable and you rebuild."
        )
    return {"ok": True, "title": "Rebuild search index", "message": message}


def _repair_reseed() -> dict:
    from horizon.seed import reseed

    summary = reseed()
    before, after = summary["before"], summary["after"]
    parts = [
        f"journeys {before['journeys']} → {after['journeys']}",
        f"guides {before['guides']} → {after['guides']}",
    ]
    message = "Re-seeded content from disk (" + ", ".join(parts) + ")."

    if low_power_enabled():
        message += (
            " The search index was not rebuilt (low-power mode); turn off low-power "
            "mode and rebuild the index to refresh semantic search."
        )
    else:
        from horizon.services.rag import index_stats, reindex_content

        reindex_content()
        stats = index_stats()
        if stats["index_built"] and stats["indexed_chunks"]:
            message += f" Rebuilt the search index ({stats['indexed_chunks']} chunks)."
        else:
            message += " The search index was not rebuilt (embedding model unavailable)."

    return {"ok": True, "title": "Re-seed content", "message": message}
