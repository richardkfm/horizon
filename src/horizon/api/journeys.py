"""Journeys API: list journeys and fetch full journey detail."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from horizon.db import get_session
from horizon.models import Category, Guide, Journey, JourneyGuideLink

router = APIRouter(prefix="/api/journeys", tags=["journeys"])

SessionDep = Annotated[Session, Depends(get_session)]


def _journey_summary(journey: Journey) -> dict:
    """Basic track metadata shared by the list and detail views."""
    return {
        "id": journey.id,
        "title": journey.title,
        "description": journey.description,
        "category": journey.category.value,
        "difficulty": journey.difficulty,
        "estimated_time": journey.estimated_time,
    }


def _guide_summary(guide: Guide) -> dict:
    return {
        "id": guide.id,
        "title": guide.title,
        "category": guide.category.value,
        "summary": guide.summary,
        "difficulty": guide.difficulty,
        "estimated_time": guide.estimated_time,
    }


def ordered_guides(session: Session, journey_id: str) -> list[Guide]:
    """Return a track's guides in their stored ``position`` order."""
    rows = session.exec(
        select(Guide)
        .join(JourneyGuideLink, JourneyGuideLink.guide_id == Guide.id)
        .where(JourneyGuideLink.journey_id == journey_id)
        .order_by(JourneyGuideLink.position)
    ).all()
    return list(rows)


def _guide_counts(session: Session) -> dict[str, int]:
    """Number of linked guides per journey id."""
    counts: dict[str, int] = {}
    for jid in session.exec(select(JourneyGuideLink.journey_id)).all():
        counts[jid] = counts.get(jid, 0) + 1
    return counts


@router.get("")
def list_journeys(
    session: SessionDep,
    category: str | None = None,
) -> list[dict]:
    """Return journeys with basic metadata, optionally filtered by category.

    A journey needs at least two linked guides to be a real step-by-step plan
    (CLAUDE.md: a single guide never needs one) — seeding already enforces
    this, but the list is filtered here too as a defensive backstop against
    any journey that predates that rule.
    """
    statement = select(Journey)
    if category is not None:
        if category not in set(Category):
            raise HTTPException(status_code=400, detail=f"Unknown category: {category}")
        statement = statement.where(Journey.category == Category(category))
    statement = statement.order_by(Journey.category, Journey.difficulty, Journey.id)
    journeys = session.exec(statement).all()
    counts = _guide_counts(session)
    return [_journey_summary(j) for j in journeys if counts.get(j.id, 0) >= 2]


@router.get("/{journey_id}")
def get_journey(
    journey_id: str,
    session: SessionDep,
) -> dict:
    """Return full track data: its ordered guides.

    ``prerequisites`` is retained as an always-empty list for backward
    compatibility with the documented response shape; tracks no longer use a
    prerequisite graph (the guide order is the path). A journey with fewer
    than two guides is reported not found — see ``list_journeys``.
    """
    journey = session.get(Journey, journey_id)
    if journey is None:
        raise HTTPException(status_code=404, detail=f"Journey not found: {journey_id}")

    guides = [_guide_summary(g) for g in ordered_guides(session, journey_id)]
    if len(guides) < 2:
        raise HTTPException(status_code=404, detail=f"Journey not found: {journey_id}")

    data = _journey_summary(journey)
    data["prerequisites"] = []
    data["guides"] = guides
    return data
