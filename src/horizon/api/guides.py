"""Guides API: fetch guide metadata and rendered content."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from horizon.config import settings
from horizon.db import get_session
from horizon.models import Guide

router = APIRouter(prefix="/api/guides", tags=["guides"])

SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/{guide_id}")
def get_guide(
    guide_id: str,
    session: SessionDep,
    format: str = "html",
) -> dict:
    """Return guide metadata plus rendered HTML (or raw Markdown).

    Args:
        format: ``html`` (rendered) or ``markdown`` (raw source).

    The Markdown source is always returned; for ``html`` the body is rendered
    to an HTML fragment as well.
    """
    if format not in {"html", "markdown"}:
        raise HTTPException(status_code=400, detail=f"Unknown format: {format}")

    guide = session.get(Guide, guide_id)
    if guide is None:
        raise HTTPException(status_code=404, detail=f"Guide not found: {guide_id}")

    body = _read_body(guide)

    data: dict = {
        "id": guide.id,
        "title": guide.title,
        "category": guide.category.value,
        "summary": guide.summary,
        "markdown": body,
    }
    if format == "html":
        data["html"] = _render_html(body)
    return data


def _read_body(guide: Guide) -> str:
    """Read a guide's Markdown body from the content directory."""
    md_path = Path(settings.content_dir) / "guides" / guide.path
    if not md_path.is_file():
        raise HTTPException(status_code=404, detail=f"Guide file missing on disk: {guide.path}")
    return md_path.read_text(encoding="utf-8")


def _render_html(body: str) -> str:
    """Render a guide's Markdown body to an HTML fragment."""
    from horizon.services.markdown import render_markdown

    return render_markdown(body)
