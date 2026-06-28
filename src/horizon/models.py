"""Data models for guides and tracks.

A *guide* is the primary unit: a Markdown how-to that a visitor browses and
reads directly. A *track* (modelled as ``Journey`` for API/contract stability)
is an optional, curated *ordered* sequence of guides for a multi-step goal
(e.g. "provide safe drinking water for a group" = test → choose treatment →
build a filter). Tracks express sequence by ordering their guides; there is no
prerequisite graph.
"""

from enum import StrEnum

from sqlmodel import Field, Relationship, SQLModel

# NOTE: This module intentionally omits ``from __future__ import annotations``.
# With stringified annotations, SQLModel 0.0.39 forwards the literal text
# ``"list[Journey]"`` to SQLAlchemy's ``relationship()``, which then fails to
# resolve it ("seems to be using a generic class"). Keeping real annotations
# (with quoted forward references) lets the link relationships configure.


class Category(StrEnum):
    water = "water"
    food = "food"
    energy = "energy"
    shelter = "shelter"
    health = "health"
    cooperation = "cooperation"
    survival = "survival"
    culture = "culture"
    language = "language"
    crafts = "crafts"
    emergencies = "emergencies"
    cooking = "cooking"
    calculations = "calculations"


class JourneyGuideLink(SQLModel, table=True):
    """Ordered link between a track (``Journey``) and a guide it includes.

    ``position`` orders the guides within a track so a track reads as a path
    (step 1, step 2, …) rather than an unordered set.
    """

    journey_id: str = Field(foreign_key="journey.id", primary_key=True)
    guide_id: str = Field(foreign_key="guide.id", primary_key=True)
    position: int = 0


class Guide(SQLModel, table=True):
    """A Markdown guide — the primary unit a visitor browses and reads.

    Body is stored on disk under ``content_dir/guides``; ``difficulty`` and
    ``estimated_time`` come from the file's front matter so the guide page
    carries its own context without an enclosing journey.
    """

    id: str = Field(primary_key=True)
    title: str
    category: Category
    summary: str = ""
    difficulty: int = 1  # 1 (easy) .. 5 (hard)
    estimated_time: str = ""  # human-readable, e.g. "2 days"
    path: str  # relative path to the Markdown file under the guides directory

    journeys: list["Journey"] = Relationship(back_populates="guides", link_model=JourneyGuideLink)


class Journey(SQLModel, table=True):
    """A curated, ordered track of guides for a multi-step goal.

    Kept named ``Journey`` (table and ``/api/journeys`` endpoints) for API
    contract stability; presented to visitors as a "step-by-step plan".
    """

    id: str = Field(primary_key=True)
    title: str
    description: str = ""
    category: Category
    difficulty: int = 1  # 1 (easy) .. 5 (hard)
    estimated_time: str = ""  # human-readable, e.g. "2 days"

    guides: list["Guide"] = Relationship(back_populates="journeys", link_model=JourneyGuideLink)
