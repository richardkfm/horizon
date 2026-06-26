"""Seed the database from repo content on first run.

On startup, if the journeys table is empty, horizon copies the bundled
``content/`` directory into ``settings.content_dir`` and loads
``journeys.yaml`` plus guide metadata into SQLite. This keeps horizon useful
out of the box while letting operators add their own content later.

NOTE: stub for v0.1 scaffold — implementation lands in the data-model step.
"""

from __future__ import annotations


def seed_if_empty() -> None:
    """Load bundled journeys/guides into the database if it is empty."""
    raise NotImplementedError("Seeding is implemented in the data-model step.")
