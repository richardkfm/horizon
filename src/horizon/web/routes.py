"""Server-rendered page routes for the horizon home UI.

Pages: landing, journeys (skill tree), guide viewer (+ print/PDF), AI assistant,
and an admin/content page. For the v0.1 scaffold only the landing page renders;
the rest are wired up in the Web UI step.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["web"])

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

CATEGORIES = ["water", "food", "energy", "shelter", "health", "cooperation"]


@router.get("/", response_class=HTMLResponse)
def landing(request: Request) -> HTMLResponse:
    """Landing view: the six categories and what horizon is for."""
    return templates.TemplateResponse(
        request, "landing.html", {"categories": CATEGORIES}
    )
