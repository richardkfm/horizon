"""Journeys API: list journeys and fetch full journey detail."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from horizon.db import get_session
from horizon.models import Category, Guide, Journey, JourneyPrerequisite

router = APIRouter(prefix="/api/journeys", tags=["journeys"])

SessionDep = Annotated[Session, Depends(get_session)]


def _journey_summary(journey: Journey) -> dict:
    """Basic metadata shared by list and nested (prerequisite) views."""
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
    }


@router.get("")
def list_journeys(
    session: SessionDep,
    category: str | None = None,
) -> list[dict]:
    """Return journeys with basic metadata, optionally filtered by category."""
    statement = select(Journey)
    if category is not None:
        if category not in set(Category):
            raise HTTPException(status_code=400, detail=f"Unknown category: {category}")
        statement = statement.where(Journey.category == Category(category))
    statement = statement.order_by(Journey.category, Journey.difficulty, Journey.id)
    journeys = session.exec(statement).all()
    return [_journey_summary(j) for j in journeys]


@router.get("/{journey_id}")
def get_journey(
    journey_id: str,
    session: SessionDep,
) -> dict:
    """Return full journey data, including prerequisites and linked guides."""
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
    return data
