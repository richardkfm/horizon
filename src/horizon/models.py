"""Data models for journeys and guides.

A *journey* is a node in the skill tree (e.g. "provide safe drinking water for
20 people"). Journeys have prerequisite edges to other journeys and link to one
or more *guides* (Markdown step-by-step instructions).
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


class JourneyPrerequisite(SQLModel, table=True):
    """Edge in the skill-tree graph: ``journey_id`` requires ``prerequisite_id``."""

    journey_id: str = Field(foreign_key="journey.id", primary_key=True)
    prerequisite_id: str = Field(foreign_key="journey.id", primary_key=True)


class JourneyGuideLink(SQLModel, table=True):
    """Many-to-many link between journeys and the guides they reference."""

    journey_id: str = Field(foreign_key="journey.id", primary_key=True)
    guide_id: str = Field(foreign_key="guide.id", primary_key=True)


class Guide(SQLModel, table=True):
    """A Markdown guide. Body is stored on disk under ``content_dir/guides``."""

    id: str = Field(primary_key=True)
    title: str
    category: Category
    summary: str = ""
    path: str  # relative path to the Markdown file under the guides directory

    journeys: list["Journey"] = Relationship(back_populates="guides", link_model=JourneyGuideLink)


class Checklist(SQLModel, table=True):
    """A printable, checkable list. Body is stored on disk under ``content_dir/checklists``.

    Standalone content (no journey links): a checklist is a self-contained,
    print/e-ink-friendly list of things to gather or do, mirroring the supply and
    go-bag lists in survival handbooks. Check state lives client-side only.
    """

    id: str = Field(primary_key=True)
    title: str
    category: Category | None = None
    summary: str = ""
    path: str  # relative path to the Markdown file under the checklists directory


class Journey(SQLModel, table=True):
    """A node in the skill tree."""

    id: str = Field(primary_key=True)
    title: str
    description: str = ""
    category: Category
    difficulty: int = 1  # 1 (easy) .. 5 (hard)
    estimated_time: str = ""  # human-readable, e.g. "2 days"

    guides: list["Guide"] = Relationship(back_populates="journeys", link_model=JourneyGuideLink)
