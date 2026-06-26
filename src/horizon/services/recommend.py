"""Journey recommendation logic.

Given a goal and simple context (people, climate, resources), rank journeys and
collect their guides. This is deliberately pure (no LLM) so /api/recommend and
the scenario wizard work on minimal hardware and are easy to unit-test.

NOTE: stub for v0.1 scaffold — implemented in the recommendation step.
"""

from __future__ import annotations


def recommend_journeys(
    goal: str,
    *,
    people: int | None = None,
    climate: str | None = None,
    resources: list[str] | None = None,
) -> dict:
    """Return suggested journeys + guides for the given goal and context."""
    raise NotImplementedError("Implemented in the recommendation step.")
