"""Recommendation API: suggest journeys/guides for a goal + simple context."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from horizon.services.recommend import recommend_journeys

router = APIRouter(prefix="/api", tags=["recommend"])


class RecommendRequest(BaseModel):
    goal: str
    people: int | None = None
    climate: str | None = None
    resources: list[str] | None = None


class RecommendResponse(BaseModel):
    journeys: list[dict]
    guides: list[dict]


@router.post("/recommend", response_model=RecommendResponse)
def recommend(req: RecommendRequest) -> RecommendResponse:
    """Suggest journeys + guides for a goal. Pure logic — no LLM required."""
    result = recommend_journeys(
        req.goal,
        people=req.people,
        climate=req.climate,
        resources=req.resources,
    )
    return RecommendResponse(**result)
