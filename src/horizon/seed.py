"""Sync bundled content into the database and content directory on startup.

On every startup, horizon brings ``settings.content_dir`` and the metadata
database up to date with the bundled ``content/`` directory: new guides,
checklists, and step-by-step plans are added, and a shipped plan's guide
order is refreshed to match ``journeys.yaml``. Nothing an operator has added
or hand-edited is ever removed or overwritten — see ``_sync_bundled_path``.
This keeps horizon useful out of the box on first run *and* keeps an
upgraded, already-provisioned install (e.g. a long-lived Docker volume) from
being stuck showing whatever content happened to exist the first time it was
seeded.

The seed is pure metadata work: it touches only SQLite and the local content
directory, with no network or LLM involvement, so the app is useful before any
of the AI machinery exists.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path

import yaml
from sqlmodel import Session, select

from horizon.config import settings
from horizon.db import engine
from horizon.models import (
    Category,
    Checklist,
    Guide,
    Journey,
    JourneyGuideLink,
)

logger = logging.getLogger("horizon")

# Records the hash of each bundled file at the point it was last written into
# content_dir, so later runs can tell "bundle changed, operator didn't touch
# it -> safe to refresh" apart from "operator edited this -> leave it alone".
_MANIFEST_NAME = ".bundle_manifest.json"


def seed_if_empty() -> None:
    """Sync bundled content into the database, adding or refreshing as needed.

    Safe to call on every startup. Guides and checklists are added if new and
    have their metadata (title, category, summary, ...) refreshed to match
    whatever is currently on disk — including any operator edits, since we
    always read the live file, never a cached copy. Existing content is never
    deleted here.

    Step-by-step plans are rebuilt from ``journeys.yaml`` every run: shipped,
    curated content rather than operator data, so a plan's guide order always
    matches the file, and a plan that resolves to fewer than two guides (a
    missing guide file, or a leftover from before plans required at least two)
    is dropped rather than shown as a single-guide dead end.
    """
    content_dir = _ensure_content_dir()
    guides = _load_guides(content_dir / "guides")
    checklists = _load_checklists(content_dir / "checklists")
    journeys, guide_links = _load_journeys(content_dir / "journeys.yaml")

    with Session(engine) as session:
        n_new_guides = _upsert_guides(session, guides)
        n_new_checklists = _upsert_checklists(session, checklists)
        session.commit()

        guide_ids = set(session.exec(select(Guide.id)).all())
        added, updated, dropped = _sync_journeys(session, journeys, guide_links, guide_ids)
        session.commit()

    logger.info(
        "Synced content into %s: %d guide(s) (%d new), %d checklist(s) (%d new), "
        "%d plan(s) added, %d updated, %d dropped (fewer than 2 guides)",
        settings.database,
        len(guides),
        n_new_guides,
        len(checklists),
        n_new_checklists,
        added,
        updated,
        dropped,
    )


def _upsert_guides(session: Session, guides: list[Guide]) -> int:
    """Add new guides and refresh existing ones' metadata. Returns count added."""
    added = 0
    for guide in guides:
        existing = session.get(Guide, guide.id)
        if existing is None:
            session.add(guide)
            added += 1
        else:
            existing.title = guide.title
            existing.category = guide.category
            existing.summary = guide.summary
            existing.difficulty = guide.difficulty
            existing.estimated_time = guide.estimated_time
            existing.path = guide.path
    return added


def _upsert_checklists(session: Session, checklists: list[Checklist]) -> int:
    """Add new checklists and refresh existing ones' metadata. Returns count added."""
    added = 0
    for checklist in checklists:
        existing = session.get(Checklist, checklist.id)
        if existing is None:
            session.add(checklist)
            added += 1
        else:
            existing.title = checklist.title
            existing.category = checklist.category
            existing.summary = checklist.summary
            existing.path = checklist.path
    return added


def _sync_journeys(
    session: Session,
    journeys: list[Journey],
    guide_links: list[JourneyGuideLink],
    guide_ids: set[str],
) -> tuple[int, int, int]:
    """Upsert plans from ``journeys.yaml`` and refresh their guide order.

    Only links whose guide actually exists are counted; a plan resolving to
    fewer than two guides is removed (or never inserted) rather than kept as a
    single-guide dead end (CLAUDE.md: plans are a curated multi-guide layer, a
    single guide never needs one). Returns ``(added, updated, dropped)`` counts.
    """
    links_by_journey: dict[str, list[JourneyGuideLink]] = {}
    for link in guide_links:
        if link.guide_id in guide_ids:
            links_by_journey.setdefault(link.journey_id, []).append(link)
        else:
            logger.warning(
                "Skipping guide link %s -> %s: guide not found", link.journey_id, link.guide_id
            )

    added = updated = dropped = 0
    for journey in journeys:
        links = links_by_journey.get(journey.id, [])

        if len(links) < 2:
            dropped += 1
            logger.warning(
                "Skipping plan %s: only %d guide(s) resolve (a plan needs at least 2)",
                journey.id,
                len(links),
            )
            # Delete the link rows before the parent: deleting a loaded Journey
            # with its guide links still attached makes SQLAlchemy also try to
            # clear the (already-deleted) association rows itself, which just
            # emits a harmless-but-noisy "0 rows matched" warning.
            for link in session.exec(
                select(JourneyGuideLink).where(JourneyGuideLink.journey_id == journey.id)
            ).all():
                session.delete(link)
            existing = session.get(Journey, journey.id)
            if existing is not None:
                session.delete(existing)
            continue

        existing = session.get(Journey, journey.id)
        if existing is None:
            session.add(journey)
            added += 1
        else:
            existing.title = journey.title
            existing.description = journey.description
            existing.category = journey.category
            existing.difficulty = journey.difficulty
            existing.estimated_time = journey.estimated_time
            updated += 1

        for link in session.exec(
            select(JourneyGuideLink).where(JourneyGuideLink.journey_id == journey.id)
        ).all():
            session.delete(link)
        session.add_all(links)

    return added, updated, dropped


def reseed() -> dict:
    """Wipe the content tables and reload bundled content from disk.

    Unlike :func:`seed_if_empty`, this runs even when the database is already
    populated — it is the "re-seed from the panel" repair: an operator who has
    edited or corrupted their content directory (or whose metadata has drifted
    from the files on disk) can rebuild the SQLite metadata from the content
    directory without a restart or the command line.

    Returns a small before/after summary so the caller can show what changed.
    Only metadata is touched (journeys, guides, and the edge tables); the
    Markdown files on disk and the vector index are left alone — callers reindex
    separately so the heavy embedding step stays opt-in and low-power-aware.
    """
    with Session(engine) as session:
        before = {
            "journeys": len(session.exec(select(Journey)).all()),
            "guides": len(session.exec(select(Guide)).all()),
            "checklists": len(session.exec(select(Checklist)).all()),
        }

        # Clear edges first so foreign keys resolve, then the nodes.
        for link in session.exec(select(JourneyGuideLink)).all():
            session.delete(link)
        for guide in session.exec(select(Guide)).all():
            session.delete(guide)
        for checklist in session.exec(select(Checklist)).all():
            session.delete(checklist)
        for journey in session.exec(select(Journey)).all():
            session.delete(journey)
        session.commit()

    # The tables are now empty, so the sync below re-adds everything from the
    # content directory (copying bundled content in if it is missing).
    seed_if_empty()

    with Session(engine) as session:
        after = {
            "journeys": len(session.exec(select(Journey)).all()),
            "guides": len(session.exec(select(Guide)).all()),
            "checklists": len(session.exec(select(Checklist)).all()),
        }
    logger.info(
        "Re-seeded content: journeys %d -> %d, guides %d -> %d, checklists %d -> %d",
        before["journeys"],
        after["journeys"],
        before["guides"],
        after["guides"],
        before["checklists"],
        after["checklists"],
    )
    return {"before": before, "after": after}


def _ensure_content_dir() -> Path:
    """Return the live content directory, syncing it up from the bundle.

    horizon ships seed content inside the repo. On first boot this copies it
    into ``settings.content_dir`` so operators have a writable copy to edit and
    add to. On every later boot (an upgrade of an existing install), each
    bundled file under ``journeys.yaml``, ``guides/``, ``checklists/``, and
    ``md_skills/`` is synced individually via :func:`_sync_bundled_path`: a
    missing file is added, and a file that is unchanged since horizon last
    wrote it is refreshed to the new bundled version — but a file an operator
    has edited is left alone. Without this, a content_dir created before a
    later release's checklist, plan, or guide update would silently keep
    stale content forever, since seeding used to run only once.
    """
    target = Path(settings.content_dir)
    bundled = _bundled_content_dir()
    target.mkdir(parents=True, exist_ok=True)

    manifest_path = target / _MANIFEST_NAME
    manifest = _load_manifest(manifest_path)

    _sync_bundled_path(
        bundled / "journeys.yaml", target / "journeys.yaml", "journeys.yaml", manifest
    )
    for sub in ("guides", "checklists", "md_skills"):
        _sync_bundled_tree(bundled / sub, target / sub, sub, manifest)

    _save_manifest(manifest_path, manifest)
    return target


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_manifest(path: Path) -> dict[str, str]:
    """Load the record of each bundled file's hash as of its last sync.

    Tolerant of a missing or corrupt manifest (e.g. an install that predates
    this tracking, or a hand-edited file) — treated as "no history", so every
    file is handled as first-seen rather than crashing startup.
    """
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_manifest(path: Path, manifest: dict[str, str]) -> None:
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sync_bundled_tree(
    bundled_dir: Path, target_dir: Path, rel_prefix: str, manifest: dict[str, str]
) -> None:
    """Sync every file under a bundled subdirectory (e.g. ``guides/``), recursively."""
    if not bundled_dir.is_dir():
        return
    for bundled_file in sorted(bundled_dir.rglob("*")):
        if not bundled_file.is_file():
            continue
        rel = f"{rel_prefix}/{bundled_file.relative_to(bundled_dir).as_posix()}"
        target_file = target_dir / bundled_file.relative_to(bundled_dir)
        _sync_bundled_path(bundled_file, target_file, rel, manifest)


def _sync_bundled_path(
    bundled_file: Path, target_file: Path, rel: str, manifest: dict[str, str]
) -> None:
    """Bring one file in content_dir up to date with its bundled version.

    - Missing target: always copied in.
    - Existing target whose hash still matches what we last wrote (``manifest``)
      but the bundle has since changed: refreshed, since the operator hasn't
      touched it — this is what lets a later release's content improvements
      (e.g. an added diagram) reach an already-provisioned install.
    - Existing target with no manifest record: left alone, but its current hash
      is recorded as the new baseline (unknown provenance — could be an
      operator's own file — so we don't guess).
    - Existing target whose hash no longer matches the manifest: the operator
      edited it since the last sync, so it is left alone entirely.
    """
    bundled_bytes = bundled_file.read_bytes()
    bundled_hash = _hash_bytes(bundled_bytes)

    if not target_file.is_file():
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_bytes(bundled_bytes)
        manifest[rel] = bundled_hash
        return

    recorded = manifest.get(rel)
    if recorded == bundled_hash:
        return  # Already in sync; nothing changed upstream.

    target_hash = _hash_bytes(target_file.read_bytes())
    if recorded is None:
        manifest[rel] = target_hash
        return
    if target_hash == recorded:
        target_file.write_bytes(bundled_bytes)
        manifest[rel] = bundled_hash
    # else: target_hash differs from the last-synced hash -> operator edit,
    # leave the file and the manifest record as they are.


def _bundled_content_dir() -> Path:
    """Locate the ``content/`` directory shipped with horizon.

    Resilient across install layouts, checked in order:

    1. ``HORIZON_BUNDLED_CONTENT`` env var (the Docker image sets this).
    2. ``content/`` next to the installed package (if shipped as package data).
    3. Walking up the source tree — editable installs and running from the repo.
    4. ``content/`` under the current working directory — covers a regular
       ``pip install`` whose process runs from the project root (e.g. the Docker
       image's ``WORKDIR /app`` with ``COPY content ./content``).

    Without this, a non-editable install (the Docker build) would never find the
    repo-root ``content/`` by walking up from ``site-packages`` and would crash
    first-run seeding.
    """
    here = Path(__file__).resolve()
    candidates: list[Path] = []
    env = os.environ.get("HORIZON_BUNDLED_CONTENT")
    if env:
        candidates.append(Path(env))
    candidates.append(here.parent / "content")
    candidates.extend(parent / "content" for parent in here.parents)
    candidates.append(Path.cwd() / "content")

    for candidate in candidates:
        if (candidate / "journeys.yaml").is_file():
            return candidate
    raise FileNotFoundError(
        "Could not locate bundled content/ directory (journeys.yaml not found). "
        "Set HORIZON_BUNDLED_CONTENT to the directory holding journeys.yaml."
    )


def _split_front_matter(text: str) -> tuple[dict, str]:
    """Split a guide's YAML front matter from its Markdown body."""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            meta = yaml.safe_load(parts[1]) or {}
            return meta, parts[2].lstrip("\n")
    return {}, text


def _load_guides(guides_dir: Path) -> list[Guide]:
    """Read guide metadata from the Markdown files' front matter."""
    guides: list[Guide] = []
    if not guides_dir.is_dir():
        return guides
    for md_path in sorted(guides_dir.glob("*.md")):
        meta, _body = _split_front_matter(md_path.read_text(encoding="utf-8"))
        guide_id = meta.get("id") or md_path.stem
        category = meta.get("category")
        if category not in set(Category):
            logger.warning(
                "Skipping guide %s: missing or invalid category %r",
                md_path.name,
                category,
            )
            continue
        guides.append(
            Guide(
                id=guide_id,
                title=meta.get("title", guide_id),
                category=Category(category),
                summary=meta.get("summary", ""),
                difficulty=int(meta.get("difficulty", 1)),
                estimated_time=meta.get("estimated_time", ""),
                path=md_path.name,
            )
        )
    return guides


def _load_checklists(checklists_dir: Path) -> list[Checklist]:
    """Read checklist metadata from the Markdown files' front matter.

    Mirrors :func:`_load_guides`: checklists are auto-discovered by scanning the
    directory, so dropping in a new ``*.md`` file is enough to publish it. The
    ``category`` front-matter key is optional (a checklist may span topics); when
    present it must be a known :class:`~horizon.models.Category`.
    """
    checklists: list[Checklist] = []
    if not checklists_dir.is_dir():
        return checklists
    for md_path in sorted(checklists_dir.glob("*.md")):
        meta, _body = _split_front_matter(md_path.read_text(encoding="utf-8"))
        checklist_id = meta.get("id") or md_path.stem
        category = meta.get("category")
        if category is not None and category not in set(Category):
            logger.warning(
                "Skipping checklist %s: invalid category %r",
                md_path.name,
                category,
            )
            continue
        checklists.append(
            Checklist(
                id=checklist_id,
                title=meta.get("title", checklist_id),
                category=Category(category) if category is not None else None,
                summary=meta.get("summary", ""),
                path=md_path.name,
            )
        )
    return checklists


def _load_journeys(
    yaml_path: Path,
) -> tuple[list[Journey], list[JourneyGuideLink]]:
    """Parse ``journeys.yaml`` into track (Journey) rows and ordered guide links.

    A track's ``guides`` list is ordered; each link records its ``position`` so
    the track reads as a path. Tracks have no prerequisites — the order is the
    path.
    """
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    entries = data.get("journeys", [])

    journeys: list[Journey] = []
    guide_links: list[JourneyGuideLink] = []

    for entry in entries:
        journey_id = entry["id"]
        category = entry.get("category")
        if category not in set(Category):
            logger.warning(
                "Skipping journey %s: missing or invalid category %r",
                journey_id,
                category,
            )
            continue
        journeys.append(
            Journey(
                id=journey_id,
                title=entry.get("title", journey_id),
                description=(entry.get("description") or "").strip(),
                category=Category(category),
                difficulty=int(entry.get("difficulty", 1)),
                estimated_time=entry.get("estimated_time", ""),
            )
        )
        for position, guide_id in enumerate(entry.get("guides") or []):
            guide_links.append(
                JourneyGuideLink(journey_id=journey_id, guide_id=guide_id, position=position)
            )

    return journeys, guide_links
