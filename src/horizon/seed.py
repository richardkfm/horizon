"""Sync bundled content into the database and content directory on startup.

On every startup, horizon brings ``settings.content_dir`` and the metadata
database up to date with the bundled ``content/`` directory: new guides,
checklists, and step-by-step plans are added, and a shipped plan's guide
order is refreshed to match ``journeys.yaml``. Nothing an operator has added
or hand-edited is ever overwritten — see ``_sync_bundled_path`` — though a
database row whose file has been deleted is dropped on the next sync.
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
import tempfile
from pathlib import Path

import yaml
from sqlmodel import Session, delete, func, select

from horizon.config import settings
from horizon.db import engine
from horizon.models import (
    Category,
    Checklist,
    Guide,
    Journey,
    JourneyGuideLink,
)
from horizon.services.frontmatter import coerce_difficulty, split_front_matter

logger = logging.getLogger("horizon")

# Records the hash of each bundled file at the point it was last written into
# content_dir, so later runs can tell "bundle changed, operator didn't touch
# it -> safe to refresh" apart from "operator edited this -> leave it alone".
_MANIFEST_NAME = ".bundle_manifest.json"

# Manifest value for a file whose provenance was lost (the manifest itself was
# corrupt) and that differs from the bundle: never a real sha256, so the file
# is treated as operator-edited on every later sync and never overwritten.
_OPERATOR_OWNED = "operator-owned"


def seed_if_empty() -> None:
    """Sync bundled content into the database, adding or refreshing as needed.

    Safe to call on every startup. Guides and checklists are added if new and
    have their metadata (title, category, summary, ...) refreshed to match
    whatever is currently on disk — including any operator edits, since we
    always read the live file, never a cached copy. A row whose file has been
    deleted from the content directory is removed; a file that exists but
    cannot be parsed (bad YAML, an unknown category, ...) is skipped with a
    warning and its existing row, if any, is kept rather than vanishing.

    Step-by-step plans are rebuilt from ``journeys.yaml`` every run: shipped,
    curated content rather than operator data, so a plan's guide order always
    matches the file, a plan removed from the file is removed from the
    database, and a plan that resolves to fewer than two guides (a missing
    guide file, or a leftover from before plans required at least two) is
    dropped rather than shown as a single-guide dead end.

    The whole sync runs in one transaction: if anything fails, nothing is
    committed and the database keeps its previous, working content.
    """
    content_dir = _ensure_content_dir()
    with Session(engine) as session:
        try:
            stats = _sync_content(session, content_dir)
            session.commit()
        except Exception:
            session.rollback()
            raise

    logger.info(
        "Synced content into %s: %d guide(s) (%d new, %d removed), %d checklist(s) "
        "(%d new, %d removed), %d plan(s) added, %d updated, %d dropped (fewer than "
        "2 guides), %d removed",
        settings.database,
        stats["guides"],
        stats["new_guides"],
        stats["removed_guides"],
        stats["checklists"],
        stats["new_checklists"],
        stats["removed_checklists"],
        stats["plans_added"],
        stats["plans_updated"],
        stats["plans_dropped"],
        stats["plans_removed"],
    )


def _sync_content(session: Session, content_dir: Path) -> dict[str, int]:
    """Bring the database in line with ``content_dir`` inside ``session``.

    Does not commit: callers own the transaction so a failure part-way through
    can be rolled back as a whole.
    """
    failed_guides: set[str] = set()
    failed_checklists: set[str] = set()
    guides = _load_guides(content_dir / "guides", failed=failed_guides)
    checklists = _load_checklists(content_dir / "checklists", failed=failed_checklists)
    try:
        journeys, guide_links = _load_journeys(content_dir / "journeys.yaml")
        journeys_ok = True
    except Exception as exc:  # noqa: BLE001 - a broken plans file must not block boot
        logger.warning("Could not read journeys.yaml; keeping the existing plans: %s", exc)
        journeys, guide_links, journeys_ok = [], [], False

    n_new_guides = _upsert_guides(session, guides)
    n_new_checklists = _upsert_checklists(session, checklists)
    removed_guides = _remove_stale_guides(session, {g.id for g in guides}, failed_guides)
    removed_checklists = _remove_stale_checklists(
        session, {c.id for c in checklists}, failed_checklists
    )
    session.flush()

    added = updated = dropped = removed_plans = 0
    if journeys_ok:
        guide_ids = set(session.exec(select(Guide.id)).all())
        added, updated, dropped = _sync_journeys(session, journeys, guide_links, guide_ids)
        removed_plans = _remove_stale_journeys(session, {j.id for j in journeys})
        session.flush()

    return {
        "guides": len(guides),
        "new_guides": n_new_guides,
        "removed_guides": removed_guides,
        "checklists": len(checklists),
        "new_checklists": n_new_checklists,
        "removed_checklists": removed_checklists,
        "plans_added": added,
        "plans_updated": updated,
        "plans_dropped": dropped,
        "plans_removed": removed_plans,
    }


def _remove_stale_guides(session: Session, keep_ids: set[str], failed_paths: set[str]) -> int:
    """Delete guide rows whose file is gone (and their plan links).

    A row whose file is still on disk but failed to parse this run is kept, so a
    typo in one guide's front matter doesn't make it disappear from the site.
    """
    removed = 0
    for guide in session.exec(select(Guide)).all():
        if guide.id in keep_ids or guide.path in failed_paths:
            continue
        # Bulk SQL delete (runs immediately), so when the guide itself is
        # deleted its many-to-many collection is already empty and SQLAlchemy
        # doesn't try to delete the same association rows a second time.
        session.exec(delete(JourneyGuideLink).where(JourneyGuideLink.guide_id == guide.id))
        session.delete(guide)
        removed += 1
        logger.info("Removed guide %s: its file is no longer in the content directory", guide.id)
    return removed


def _remove_stale_checklists(session: Session, keep_ids: set[str], failed_paths: set[str]) -> int:
    """Delete checklist rows whose file is gone (see :func:`_remove_stale_guides`)."""
    removed = 0
    for checklist in session.exec(select(Checklist)).all():
        if checklist.id in keep_ids or checklist.path in failed_paths:
            continue
        session.delete(checklist)
        removed += 1
        logger.info(
            "Removed checklist %s: its file is no longer in the content directory", checklist.id
        )
    return removed


def _remove_stale_journeys(session: Session, keep_ids: set[str]) -> int:
    """Delete plans (and their links) that are no longer listed in ``journeys.yaml``."""
    removed = 0
    for journey in session.exec(select(Journey)).all():
        if journey.id in keep_ids:
            continue
        session.exec(delete(JourneyGuideLink).where(JourneyGuideLink.journey_id == journey.id))
        session.delete(journey)
        removed += 1
        logger.info("Removed plan %s: it is no longer listed in journeys.yaml", journey.id)
    return removed


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


def _counts(session: Session) -> dict[str, int]:
    return {
        "journeys": session.exec(select(func.count()).select_from(Journey)).one(),
        "guides": session.exec(select(func.count()).select_from(Guide)).one(),
        "checklists": session.exec(select(func.count()).select_from(Checklist)).one(),
    }


def reseed() -> dict:
    """Wipe the content tables and reload them from the content directory.

    Unlike :func:`seed_if_empty`'s incremental sync, this rebuilds every row —
    it is the "re-seed from the panel" repair: an operator who has edited or
    corrupted their content directory (or whose metadata has drifted from the
    files on disk) can rebuild the SQLite metadata without a restart or the
    command line.

    Atomic: the wipe and the reload run in a single transaction, so if loading
    fails part-way the transaction is rolled back and the previous content is
    still there — a failed repair can never leave the node with an empty
    database (which used to crash the next boot).

    Returns a small before/after summary so the caller can show what changed.
    Only metadata is touched (journeys, guides, checklists, and the edge
    table); the Markdown files on disk and the vector index are left alone —
    callers reindex separately so the heavy embedding step stays opt-in and
    low-power-aware.
    """
    # Copy in any bundled content that is missing first (plain file I/O, outside
    # the database transaction).
    content_dir = _ensure_content_dir()

    with Session(engine) as session:
        before = _counts(session)
        try:
            # Clear edges first, then the nodes. Bulk deletes bypass the
            # identity map, so drop anything cached before re-adding rows.
            session.exec(delete(JourneyGuideLink))
            session.exec(delete(Guide))
            session.exec(delete(Checklist))
            session.exec(delete(Journey))
            session.expunge_all()
            _sync_content(session, content_dir)
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("Re-seed failed; the previous content was kept unchanged.")
            raise
        after = _counts(session)

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
    bundled file under ``journeys.yaml``, ``packs.yaml``, ``guides/``,
    ``checklists/``, and ``md_skills/`` is synced individually via
    :func:`_sync_bundled_path`: a
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
    manifest, trusted = _read_manifest(manifest_path)
    if not trusted:
        logger.warning(
            "The bundle manifest %s is unreadable; treating any content file that "
            "differs from the bundled version as an operator edit and leaving it alone.",
            manifest_path,
        )

    def sync(bundled_file: Path, target_file: Path, rel: str) -> None:
        try:
            _sync_bundled_path(bundled_file, target_file, rel, manifest, trusted=trusted)
        except OSError as exc:
            logger.warning("Could not sync bundled file %s: %s", rel, exc)

    sync(bundled / "journeys.yaml", target / "journeys.yaml", "journeys.yaml")
    if (bundled / "packs.yaml").is_file():
        sync(bundled / "packs.yaml", target / "packs.yaml", "packs.yaml")
    for sub in ("guides", "checklists", "md_skills"):
        _sync_bundled_tree(bundled / sub, target / sub, sub, manifest, trusted=trusted)

    try:
        _save_manifest(manifest_path, manifest)
    except OSError as exc:
        logger.warning("Could not save the bundle manifest %s: %s", manifest_path, exc)
    return target


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_manifest(path: Path) -> tuple[dict[str, str], bool]:
    """Load the manifest, reporting whether it can be trusted.

    Returns ``(manifest, trusted)``. A *missing* manifest is trusted-but-empty
    (a fresh install, or one that predates this tracking). A manifest that
    exists but can't be read or parsed is *untrusted*: we've lost the record of
    what horizon wrote, so a differing file might be an operator's edit and
    must not be overwritten.
    """
    if not path.exists():
        return {}, True
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}, False
    if not isinstance(data, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in data.items()
    ):
        return {}, False
    return data, True


def _load_manifest(path: Path) -> dict[str, str]:
    """Load the record of each bundled file's hash as of its last sync.

    Tolerant of a missing or corrupt manifest — returns ``{}`` rather than
    crashing startup. :func:`_ensure_content_dir` uses :func:`_read_manifest`
    instead, which also says whether a corrupt manifest was found.
    """
    return _read_manifest(path)[0]


def _save_manifest(path: Path, manifest: dict[str, str]) -> None:
    """Write the manifest atomically (temp file + ``os.replace``).

    A crash or full disk mid-write must never leave a truncated manifest
    behind, since an unreadable manifest makes every file look operator-owned.
    """
    data = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=".bundle_manifest.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def _sync_bundled_tree(
    bundled_dir: Path,
    target_dir: Path,
    rel_prefix: str,
    manifest: dict[str, str],
    *,
    trusted: bool = True,
) -> None:
    """Sync every file under a bundled subdirectory (e.g. ``guides/``), recursively."""
    if not bundled_dir.is_dir():
        return
    for bundled_file in sorted(bundled_dir.rglob("*")):
        if not bundled_file.is_file():
            continue
        rel = f"{rel_prefix}/{bundled_file.relative_to(bundled_dir).as_posix()}"
        target_file = target_dir / bundled_file.relative_to(bundled_dir)
        try:
            _sync_bundled_path(bundled_file, target_file, rel, manifest, trusted=trusted)
        except OSError as exc:
            logger.warning("Could not sync bundled file %s: %s", rel, exc)


def _sync_bundled_path(
    bundled_file: Path,
    target_file: Path,
    rel: str,
    manifest: dict[str, str],
    *,
    trusted: bool = True,
) -> None:
    """Bring one file in content_dir up to date with its bundled version.

    - Missing target: always copied in.
    - Existing target with no manifest record (an install that pre-dates this
      tracking, the overwhelmingly common case): refreshed to the bundled
      version in this same pass — an *install* that pre-dates tracking is not
      the same thing as a *file* an operator has hand-edited, and treating it
      as "unknown, leave it and just record a baseline" used to mean a later
      release's content fixes (e.g. an added diagram) needed two restarts to
      actually reach an already-provisioned install: the first only recorded
      the pre-existing content as the baseline, the second then saw it as
      "unchanged since last sync" and finally applied the update.
    - Existing target whose hash still matches what we last wrote (``manifest``)
      but the bundle has since changed: refreshed, since the operator hasn't
      touched it since our last sync.
    - Existing target whose hash no longer matches the manifest: the operator
      edited it since the last sync, so it is left alone entirely.
    - ``trusted=False`` (the manifest file existed but was corrupt): there is
      no reliable history, so an existing target that differs from the bundle
      is recorded as operator-owned and left alone, now and on later runs.
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
    if target_hash == bundled_hash:
        manifest[rel] = bundled_hash  # Identical already; just record it.
        return
    if recorded is not None and target_hash != recorded:
        return  # Operator edited it since the last sync; leave it alone.
    if recorded is None and not trusted:
        # History lost: assume the difference is an operator edit. The sentinel
        # never matches a real hash, so later runs keep leaving it alone.
        manifest[rel] = _OPERATOR_OWNED
        return

    target_file.write_bytes(bundled_bytes)
    manifest[rel] = bundled_hash


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
    """Split a content file's YAML front matter from its Markdown body.

    Lenient (bad metadata reads as ``{}``); kept for callers that only need a
    best-effort read. Seeding itself uses :func:`_read_meta`, which is strict.
    """
    return split_front_matter(text)


def _read_meta(md_path: Path) -> dict:
    """Read a content file's front matter strictly (raises on unusable metadata)."""
    meta, _body = split_front_matter(md_path.read_text(encoding="utf-8"), strict=True)
    return meta


def _text(value: object, default: str = "") -> str:
    """Front-matter text field as a plain string (``None`` -> ``default``)."""
    if value is None:
        return default
    return value if isinstance(value, str) else str(value)


def _category(value: object) -> Category | None:
    try:
        return Category(value)
    except (ValueError, TypeError):
        return None


def _load_guides(guides_dir: Path, *, failed: set[str] | None = None) -> list[Guide]:
    """Read guide metadata from the Markdown files' front matter.

    One bad file never blocks the rest: a file that can't be read or parsed,
    has an unknown category, or repeats an earlier file's id is skipped with a
    warning. Files skipped for being unusable are added to ``failed`` (by file
    name) so the caller can keep their previous rows instead of deleting them.
    """
    guides: list[Guide] = []
    if not guides_dir.is_dir():
        return guides
    failed = failed if failed is not None else set()
    seen: dict[str, str] = {}
    for md_path in sorted(guides_dir.glob("*.md")):
        try:
            meta = _read_meta(md_path)
            guide_id = _text(meta.get("id")) or md_path.stem
            category = _category(meta.get("category"))
            if category is None:
                raise ValueError(f"missing or invalid category {meta.get('category')!r}")
            guide = Guide(
                id=guide_id,
                title=_text(meta.get("title"), guide_id) or guide_id,
                category=category,
                summary=_text(meta.get("summary")),
                difficulty=coerce_difficulty(meta.get("difficulty", 1)),
                estimated_time=_text(meta.get("estimated_time")),
                path=md_path.name,
            )
        except Exception as exc:  # noqa: BLE001 - one bad file must not block boot
            logger.warning("Skipping guide %s: %s", md_path.name, exc)
            failed.add(md_path.name)
            continue
        if guide_id in seen:
            logger.warning(
                "Skipping guide %s: id %r is already used by %s",
                md_path.name,
                guide_id,
                seen[guide_id],
            )
            continue
        seen[guide_id] = md_path.name
        guides.append(guide)
    return guides


def _load_checklists(checklists_dir: Path, *, failed: set[str] | None = None) -> list[Checklist]:
    """Read checklist metadata from the Markdown files' front matter.

    Mirrors :func:`_load_guides`: checklists are auto-discovered by scanning the
    directory, so dropping in a new ``*.md`` file is enough to publish it. The
    ``category`` front-matter key is optional (a checklist may span topics); when
    present it must be a known :class:`~horizon.models.Category`. Unusable files
    are skipped with a warning, never raised.
    """
    checklists: list[Checklist] = []
    if not checklists_dir.is_dir():
        return checklists
    failed = failed if failed is not None else set()
    seen: dict[str, str] = {}
    for md_path in sorted(checklists_dir.glob("*.md")):
        try:
            meta = _read_meta(md_path)
            checklist_id = _text(meta.get("id")) or md_path.stem
            raw_category = meta.get("category")
            category = _category(raw_category) if raw_category is not None else None
            if raw_category is not None and category is None:
                raise ValueError(f"invalid category {raw_category!r}")
            checklist = Checklist(
                id=checklist_id,
                title=_text(meta.get("title"), checklist_id) or checklist_id,
                category=category,
                summary=_text(meta.get("summary")),
                path=md_path.name,
            )
        except Exception as exc:  # noqa: BLE001 - one bad file must not block boot
            logger.warning("Skipping checklist %s: %s", md_path.name, exc)
            failed.add(md_path.name)
            continue
        if checklist_id in seen:
            logger.warning(
                "Skipping checklist %s: id %r is already used by %s",
                md_path.name,
                checklist_id,
                seen[checklist_id],
            )
            continue
        seen[checklist_id] = md_path.name
        checklists.append(checklist)
    return checklists


def _load_journeys(
    yaml_path: Path,
) -> tuple[list[Journey], list[JourneyGuideLink]]:
    """Parse ``journeys.yaml`` into track (Journey) rows and ordered guide links.

    A track's ``guides`` list is ordered; each link records its ``position`` so
    the track reads as a path. Tracks have no prerequisites — the order is the
    path.
    """
    if not yaml_path.is_file():
        return [], []
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("journeys.yaml must be a mapping with a 'journeys' list")
    entries = data.get("journeys") or []
    if not isinstance(entries, list):
        raise ValueError("journeys.yaml: 'journeys' must be a list")

    journeys: list[Journey] = []
    guide_links: list[JourneyGuideLink] = []
    seen_journeys: set[str] = set()

    for entry in entries:
        if not isinstance(entry, dict) or not _text(entry.get("id")):
            logger.warning("Skipping malformed plan entry in journeys.yaml: %r", entry)
            continue
        journey_id = _text(entry["id"])
        if journey_id in seen_journeys:
            logger.warning("Skipping plan %s: duplicate id in journeys.yaml", journey_id)
            continue
        category = _category(entry.get("category"))
        if category is None:
            logger.warning(
                "Skipping journey %s: missing or invalid category %r",
                journey_id,
                entry.get("category"),
            )
            continue
        seen_journeys.add(journey_id)
        journeys.append(
            Journey(
                id=journey_id,
                title=_text(entry.get("title"), journey_id) or journey_id,
                description=_text(entry.get("description")).strip(),
                category=category,
                difficulty=coerce_difficulty(entry.get("difficulty", 1)),
                estimated_time=_text(entry.get("estimated_time")),
            )
        )
        raw_guides = entry.get("guides") or []
        if not isinstance(raw_guides, list):
            logger.warning("Plan %s: 'guides' must be a list; ignoring it", journey_id)
            raw_guides = []
        seen_guides: set[str] = set()
        for raw_guide_id in raw_guides:
            guide_id = _text(raw_guide_id)
            if not guide_id:
                continue
            if guide_id in seen_guides:
                logger.warning(
                    "Plan %s lists guide %s more than once; keeping the first",
                    journey_id,
                    guide_id,
                )
                continue
            guide_links.append(
                JourneyGuideLink(
                    journey_id=journey_id, guide_id=guide_id, position=len(seen_guides)
                )
            )
            seen_guides.add(guide_id)

    return journeys, guide_links
