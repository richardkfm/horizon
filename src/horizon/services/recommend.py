"""Recommendation logic.

Given a goal and simple context (people, climate, resources), rank guides (the
primary unit a visitor reads) and the curated tracks that match. This is
deliberately pure (no LLM, no vector DB) so ``/api/recommend`` and the scenario
page work on minimal hardware and are easy to unit-test. Matching is a
lightweight keyword overlap over the seeded guide and track metadata in SQLite.
"""

from __future__ import annotations

import re

from sqlmodel import Session, select

from horizon.db import engine
from horizon.models import Guide, Journey

# Common words that carry no topical signal. Verbs like "build"/"grow"/"provide"
# are intentionally kept — they overlap with journey titles.
_STOPWORDS = {
    "a",
    "an",
    "the",
    "to",
    "for",
    "of",
    "and",
    "or",
    "in",
    "on",
    "with",
    "my",
    "our",
    "we",
    "i",
    "how",
    "do",
    "i'd",
    "is",
    "it",
    "that",
    "this",
    "at",
    "as",
    "by",
    "be",
    "can",
    "need",
    "want",
    "some",
    "any",
    "about",
    # Generic quantity / scale / framing words that appear across many journeys
    # and categories, so they add noise rather than topical signal.
    "group",
    "groups",
    "people",
    "person",
    "small",
    "large",
    "basic",
    "basics",
    "common",
    "simple",
    "make",
    "set",
    "up",
    "get",
    "good",
    "well",
    "use",
    "using",
    "run",
    "help",
    "handle",
    "situation",
    "situations",
    "thing",
    "things",
    "way",
    "ways",
}

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Scoring weights: a category-name hit is the strongest signal.
_CATEGORY_WEIGHT = 3
_TITLE_WEIGHT = 2
_TEXT_WEIGHT = 1

_TOP_N = 5


def _tokenize(text: str) -> set[str]:
    """Lowercase, split into word tokens, drop stopwords and 1-char tokens."""
    return {
        tok for tok in _TOKEN_RE.findall(text.lower()) if len(tok) > 1 and tok not in _STOPWORDS
    }


def _score(query: set[str], *, title: str, text: str, category: str) -> int:
    """Weighted keyword overlap between the query and an item's fields."""
    if not query:
        return 0
    score = 0
    if category in query:
        score += _CATEGORY_WEIGHT
    score += _TITLE_WEIGHT * len(query & _tokenize(title))
    score += _TEXT_WEIGHT * len(query & _tokenize(text))
    return score


def _journey_summary(journey: Journey) -> dict:
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


def recommend_journeys(
    goal: str,
    *,
    people: int | None = None,
    climate: str | None = None,
    resources: list[str] | None = None,
) -> dict:
    """Return suggested guides + tracks for the given goal and context.

    Guides are the primary unit (what a visitor reads), so they are ranked
    directly; matching tracks ("journeys") are surfaced alongside as multi-step
    paths. ``climate`` and ``resources`` are folded into the keyword query as
    extra signals; ``people`` is informational only (no field encodes group
    size). An empty goal yields empty results.
    """
    parts = [goal or ""]
    if climate:
        parts.append(climate)
    if resources:
        parts.extend(resources)
    query = _tokenize(" ".join(parts))

    if not query:
        return {"journeys": [], "guides": []}

    with Session(engine) as session:
        journeys = session.exec(select(Journey)).all()
        guides = session.exec(select(Guide)).all()

        # Rank guides directly — they are the thing a visitor opens and reads.
        scored_guides = [
            (g, s)
            for g in guides
            if (
                s := _score(
                    query,
                    title=g.title,
                    text=g.summary,
                    category=g.category.value,
                )
            )
            > 0
        ]
        scored_guides.sort(key=lambda pair: (-pair[1], pair[0].difficulty, pair[0].id))
        top_guides = [g for g, _ in scored_guides[:_TOP_N]]

        # Surface curated tracks that match, as multi-step paths to follow.
        scored_journeys = [
            (j, s)
            for j in journeys
            if (
                s := _score(
                    query,
                    title=j.title,
                    text=j.description,
                    category=j.category.value,
                )
            )
            > 0
        ]
        scored_journeys.sort(key=lambda pair: (-pair[1], pair[0].difficulty, pair[0].id))
        top_journeys = [j for j, _ in scored_journeys[:_TOP_N]]

        return {
            "journeys": [_journey_summary(j) for j in top_journeys],
            "guides": [_guide_summary(g) for g in top_guides],
        }
