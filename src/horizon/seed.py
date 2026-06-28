"""Seed the database from repo content on first run.

On startup, if the journeys table is empty, horizon copies the bundled
``content/`` directory into ``settings.content_dir`` and loads
``journeys.yaml`` plus guide metadata into SQLite. This keeps horizon useful
out of the box while letting operators add their own content later.

The seed is pure metadata work: it touches only SQLite and the local content
directory, with no network or LLM involvement, so the app is useful before any
of the AI machinery exists.
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

import yaml
from sqlmodel import Session, select

from horizon.config import settings
from horizon.db import engine
from horizon.models import (
    Category,
    Guide,
    Journey,
    JourneyGuideLink,
    JourneyPrerequisite,
)

logger = logging.getLogger("horizon")


def seed_if_empty() -> None:
    """Load bundled journeys/guides into the database if it is empty.

    Idempotent: if any journeys already exist the call returns immediately, so
    it is safe to run on every startup.
    """
    with Session(engine) as session:
        if session.exec(select(Journey)).first() is not None:
            return

        content_dir = _ensure_content_dir()
        guides = _load_guides(content_dir / "guides")
        journeys, guide_links, prerequisites = _load_journeys(content_dir / "journeys.yaml")

        # Insert nodes first so the edge tables' foreign keys resolve.
        session.add_all(guides)
        session.add_all(journeys)
        session.commit()

        # Only link guides that actually exist on disk; skip dangling refs.
        guide_ids = {g.id for g in guides}
        journey_ids = {j.id for j in journeys}
        for link in guide_links:
            if link.guide_id in guide_ids and link.journey_id in journey_ids:
                session.add(link)
            else:
                logger.warning(
                    "Skipping guide link %s -> %s: missing node",
                    link.journey_id,
                    link.guide_id,
                )
        for edge in prerequisites:
            if edge.prerequisite_id in journey_ids and edge.journey_id in journey_ids:
                session.add(edge)
            else:
                logger.warning(
                    "Skipping prerequisite %s -> %s: missing journey",
                    edge.journey_id,
                    edge.prerequisite_id,
                )
        session.commit()

        logger.info(
            "Seeded %d journeys and %d guides into %s",
            len(journeys),
            len(guides),
            settings.database,
        )


def _ensure_content_dir() -> Path:
    """Return the live content directory, copying bundled content on first run.

    horizon ships seed content inside the repo. On first boot we copy it into
    ``settings.content_dir`` so operators have a writable copy to edit and add
    to. If that directory already holds content we use it as-is.
    """
    target = Path(settings.content_dir)
    if (target / "journeys.yaml").is_file():
        return target

    bundled = _bundled_content_dir()
    target.mkdir(parents=True, exist_ok=True)
    # copytree with dirs_exist_ok so a partially-populated target is tolerated.
    shutil.copytree(bundled, target, dirs_exist_ok=True)
    logger.info("Copied bundled content from %s to %s", bundled, target)
    return target


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
                path=md_path.name,
            )
        )
    return guides


def _load_journeys(
    yaml_path: Path,
) -> tuple[list[Journey], list[JourneyGuideLink], list[JourneyPrerequisite]]:
    """Parse ``journeys.yaml`` into Journey rows and edge rows."""
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    entries = data.get("journeys", [])

    journeys: list[Journey] = []
    guide_links: list[JourneyGuideLink] = []
    prerequisites: list[JourneyPrerequisite] = []

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
        for guide_id in entry.get("guides") or []:
            guide_links.append(JourneyGuideLink(journey_id=journey_id, guide_id=guide_id))
        for prereq_id in entry.get("prerequisites") or []:
            prerequisites.append(
                JourneyPrerequisite(journey_id=journey_id, prerequisite_id=prereq_id)
            )

    return journeys, guide_links, prerequisites
