"""Server-rendered page routes for the horizon home UI.

Pages: landing, journeys (skill tree), journey detail, and the guide viewer
(+ in-browser print via ``print.css``). These are thin, DB-direct views over the
same data the Knowledge API exposes — no HTTP self-calls and no LLM/vector
dependency, so the UI works fully offline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from horizon.api.guides import _read_body
from horizon.api.journeys import _guide_summary, _journey_summary
from horizon.db import get_session
from horizon.models import Category, Guide, Journey, JourneyPrerequisite
from horizon.services.markdown import render_markdown

router = APIRouter(tags=["web"])

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

SessionDep = Annotated[Session, Depends(get_session)]

CATEGORIES = [c.value for c in Category]


@router.get("/", response_class=HTMLResponse)
def landing(request: Request) -> HTMLResponse:
    """Landing view: the six categories and what horizon is for."""
    return templates.TemplateResponse(request, "landing.html", {"categories": CATEGORIES})


@router.get("/journeys", response_class=HTMLResponse)
def journeys_page(
    request: Request,
    session: SessionDep,
    category: str | None = None,
) -> HTMLResponse:
    """List journeys, optionally filtered by category."""
    if category is not None and category not in set(Category):
        raise HTTPException(status_code=400, detail=f"Unknown category: {category}")

    statement = select(Journey)
    if category is not None:
        statement = statement.where(Journey.category == Category(category))
    statement = statement.order_by(Journey.category, Journey.difficulty, Journey.id)
    journeys = [_journey_summary(j) for j in session.exec(statement).all()]

    return templates.TemplateResponse(
        request,
        "journeys.html",
        {
            "journeys": journeys,
            "categories": CATEGORIES,
            "selected_category": category,
        },
    )


@router.get("/journeys/{journey_id}", response_class=HTMLResponse)
def journey_detail_page(
    journey_id: str,
    request: Request,
    session: SessionDep,
) -> HTMLResponse:
    """Show a journey with its prerequisites and linked guides."""
    journey = session.get(Journey, journey_id)
    if journey is None:
        raise HTTPException(status_code=404, detail=f"Journey not found: {journey_id}")

    prereq_ids = session.exec(
        select(JourneyPrerequisite.prerequisite_id).where(
            JourneyPrerequisite.journey_id == journey_id
        )
    ).all()
    prerequisites = [
        _journey_summary(p) for pid in prereq_ids if (p := session.get(Journey, pid)) is not None
    ]

    data = _journey_summary(journey)
    data["prerequisites"] = prerequisites
    data["guides"] = [_guide_summary(g) for g in journey.guides]

    return templates.TemplateResponse(request, "journey_detail.html", {"journey": data})


@router.get("/guides/{guide_id}", response_class=HTMLResponse)
def guide_page(
    guide_id: str,
    request: Request,
    session: SessionDep,
) -> HTMLResponse:
    """Render a guide's Markdown for reading and printing."""
    guide = session.get(Guide, guide_id)
    if guide is None:
        raise HTTPException(status_code=404, detail=f"Guide not found: {guide_id}")

    body_html = render_markdown(_read_body(guide))

    return templates.TemplateResponse(
        request,
        "guide.html",
        {
            "guide": _guide_summary(guide),
            "body_html": body_html,
        },
    )
