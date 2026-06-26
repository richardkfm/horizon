"""Guides API: fetch guide metadata and rendered content."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/guides", tags=["guides"])


@router.get("/{guide_id}")
def get_guide(guide_id: str, format: str = "html") -> dict:
    """Return guide metadata plus rendered HTML (or raw Markdown).

    Args:
        format: ``html`` (rendered) or ``markdown`` (raw source).
    """
    raise NotImplementedError("Implemented in the Knowledge API step.")
