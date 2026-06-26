"""Journeys API: list journeys and fetch full journey detail."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/journeys", tags=["journeys"])


@router.get("")
def list_journeys(category: str | None = None) -> list[dict]:
    """Return journeys with basic metadata, optionally filtered by category."""
    raise NotImplementedError("Implemented in the Knowledge API step.")


@router.get("/{journey_id}")
def get_journey(journey_id: str) -> dict:
    """Return full journey data, including prerequisites and linked guides."""
    raise NotImplementedError("Implemented in the Knowledge API step.")
