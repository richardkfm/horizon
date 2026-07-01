"""Tests for horizon's upgrade-safe content sync (``seed.py``).

Covers two things that used to silently go stale on an already-provisioned
install (e.g. a long-lived Docker volume): the bundled-file sync into
``content_dir`` (``_sync_bundled_path`` / ``_sync_bundled_tree``) and the
incremental database sync (``seed_if_empty``) that adds new guides/checklists,
refreshes a plan's guide order, and drops any plan resolving to fewer than two
guides. See CLAUDE.md: "plans are an optional curated layer... never wrap a
single guide in its own plan".
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from horizon.config import settings
from horizon.models import Category, Checklist, Guide, Journey, JourneyGuideLink
from horizon.seed import (
    _load_manifest,
    _sync_bundled_path,
    _sync_bundled_tree,
    _sync_journeys,
    _upsert_checklists,
    _upsert_guides,
    seed_if_empty,
)

# --- bundled-file sync (pure filesystem, no DB) ------------------------------


def test_sync_bundled_path_copies_missing_file(tmp_path):
    bundled = tmp_path / "bundled.md"
    bundled.write_text("v1", encoding="utf-8")
    target = tmp_path / "target.md"
    manifest: dict[str, str] = {}

    _sync_bundled_path(bundled, target, "target.md", manifest)

    assert target.read_text(encoding="utf-8") == "v1"
    assert "target.md" in manifest


def test_sync_bundled_path_refreshes_untouched_file(tmp_path):
    bundled = tmp_path / "bundled.md"
    bundled.write_text("v1", encoding="utf-8")
    target = tmp_path / "target.md"
    manifest: dict[str, str] = {}
    _sync_bundled_path(bundled, target, "f", manifest)  # first sync

    bundled.write_text("v2 with new content", encoding="utf-8")
    _sync_bundled_path(bundled, target, "f", manifest)  # bundle updated upstream

    assert target.read_text(encoding="utf-8") == "v2 with new content"


def test_sync_bundled_path_preserves_operator_edit(tmp_path):
    bundled = tmp_path / "bundled.md"
    bundled.write_text("v1", encoding="utf-8")
    target = tmp_path / "target.md"
    manifest: dict[str, str] = {}
    _sync_bundled_path(bundled, target, "f", manifest)  # first sync

    target.write_text("operator's own edit", encoding="utf-8")
    bundled.write_text("v2 with new content", encoding="utf-8")
    _sync_bundled_path(bundled, target, "f", manifest)  # bundle updated upstream

    assert target.read_text(encoding="utf-8") == "operator's own edit"


def test_sync_bundled_path_unknown_provenance_is_left_alone(tmp_path):
    """A target file with no manifest history (e.g. pre-dates this tracking)
    is never guessed at — it is left as-is and just becomes the new baseline.
    """
    bundled = tmp_path / "bundled.md"
    bundled.write_text("v2", encoding="utf-8")
    target = tmp_path / "target.md"
    target.write_text("whatever was there before", encoding="utf-8")
    manifest: dict[str, str] = {}

    _sync_bundled_path(bundled, target, "f", manifest)

    assert target.read_text(encoding="utf-8") == "whatever was there before"
    assert manifest["f"] is not None  # baseline recorded for next time


def test_sync_bundled_tree_handles_nested_dirs(tmp_path):
    bundled_dir = tmp_path / "bundled"
    (bundled_dir / "images").mkdir(parents=True)
    (bundled_dir / "a.md").write_text("a", encoding="utf-8")
    (bundled_dir / "images" / "pic.svg").write_text("<svg/>", encoding="utf-8")

    target_dir = tmp_path / "target"
    manifest: dict[str, str] = {}
    _sync_bundled_tree(bundled_dir, target_dir, "guides", manifest)

    assert (target_dir / "a.md").read_text(encoding="utf-8") == "a"
    assert (target_dir / "images" / "pic.svg").read_text(encoding="utf-8") == "<svg/>"
    assert "guides/a.md" in manifest
    assert "guides/images/pic.svg" in manifest


def test_load_manifest_tolerates_missing_or_corrupt(tmp_path):
    assert _load_manifest(tmp_path / "nope.json") == {}
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    assert _load_manifest(bad) == {}


# --- database sync ------------------------------------------------------------


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_upsert_guides_adds_new_and_refreshes_existing(db_session):
    existing = Guide(id="g1", title="Old title", category=Category.water, path="g1.md")
    db_session.add(existing)
    db_session.commit()

    guides = [
        Guide(id="g1", title="New title", category=Category.water, summary="updated", path="g1.md"),
        Guide(id="g2", title="Second", category=Category.water, path="g2.md"),
    ]
    added = _upsert_guides(db_session, guides)
    db_session.commit()

    assert added == 1
    assert db_session.get(Guide, "g1").title == "New title"
    assert db_session.get(Guide, "g1").summary == "updated"
    assert db_session.get(Guide, "g2") is not None


def test_upsert_checklists_adds_new_and_refreshes_existing(db_session):
    checklists = [Checklist(id="c1", title="Checklist one", path="c1.md")]
    added = _upsert_checklists(db_session, checklists)
    db_session.commit()
    assert added == 1
    assert db_session.get(Checklist, "c1") is not None


def test_sync_journeys_drops_plan_with_fewer_than_two_guides(db_session):
    journeys = [Journey(id="j1", title="Thin plan", category=Category.water)]
    links = [JourneyGuideLink(journey_id="j1", guide_id="g1", position=0)]

    added, updated, dropped = _sync_journeys(db_session, journeys, links, guide_ids={"g1"})
    db_session.commit()

    assert (added, updated, dropped) == (0, 0, 1)
    assert db_session.get(Journey, "j1") is None


def test_sync_journeys_removes_previously_seeded_thin_plan(db_session):
    """A journey seeded by old code before the "needs >= 2 guides" rule
    existed is cleaned up on the next sync, not left as a dead end.
    """
    db_session.add(Guide(id="g1", title="G1", category=Category.water, path="g1.md"))
    db_session.add(Journey(id="j1", title="Thin plan", category=Category.water))
    db_session.add(JourneyGuideLink(journey_id="j1", guide_id="g1", position=0))
    db_session.commit()

    journeys = [Journey(id="j1", title="Thin plan", category=Category.water)]
    links = [JourneyGuideLink(journey_id="j1", guide_id="g1", position=0)]
    _sync_journeys(db_session, journeys, links, guide_ids={"g1"})
    db_session.commit()

    assert db_session.get(Journey, "j1") is None
    assert (
        db_session.exec(select(JourneyGuideLink).where(JourneyGuideLink.journey_id == "j1")).first()
        is None
    )


def test_sync_journeys_adds_and_refreshes_guide_order(db_session):
    for gid in ("g1", "g2", "g3"):
        db_session.add(Guide(id=gid, title=gid, category=Category.water, path=f"{gid}.md"))
    db_session.commit()

    journeys = [Journey(id="j1", title="Plan", category=Category.water)]
    links = [
        JourneyGuideLink(journey_id="j1", guide_id="g1", position=0),
        JourneyGuideLink(journey_id="j1", guide_id="g2", position=1),
    ]
    added, updated, dropped = _sync_journeys(
        db_session, journeys, links, guide_ids={"g1", "g2", "g3"}
    )
    db_session.commit()
    assert (added, updated, dropped) == (1, 0, 0)

    # A later sync adds a third guide and reorders — the existing plan is
    # updated in place, not duplicated.
    journeys = [Journey(id="j1", title="Plan", category=Category.water)]
    links = [
        JourneyGuideLink(journey_id="j1", guide_id="g3", position=0),
        JourneyGuideLink(journey_id="j1", guide_id="g1", position=1),
        JourneyGuideLink(journey_id="j1", guide_id="g2", position=2),
    ]
    added, updated, dropped = _sync_journeys(
        db_session, journeys, links, guide_ids={"g1", "g2", "g3"}
    )
    db_session.commit()
    assert (added, updated, dropped) == (0, 1, 0)

    ordered = db_session.exec(
        select(JourneyGuideLink)
        .where(JourneyGuideLink.journey_id == "j1")
        .order_by(JourneyGuideLink.position)
    ).all()
    assert [link.guide_id for link in ordered] == ["g3", "g1", "g2"]


# --- end-to-end: seed_if_empty is safe to call repeatedly, upgrade scenario --


def test_seed_if_empty_upgrades_a_legacy_stale_install(tmp_path, monkeypatch):
    """Simulates an already-provisioned install being started up against a
    newer bundled content tree.

    Before this fix, ``journeys.yaml`` was already force-copied to
    content_dir on every boot (so it matches the current bundle here too —
    the realistic case for an operator who never hand-edits it), but the
    *database* was never refreshed after the first seed: it still has a
    leftover single-guide plan from before plans required >= 2 guides, and no
    checklist rows at all (checklists didn't exist yet when it was seeded).
    """
    guide_a_md = "---\nid: water-a\ntitle: A\ncategory: water\nsummary: s\n---\nbody\n"
    guide_b_md = "---\nid: water-b\ntitle: B\ncategory: water\nsummary: s\n---\nbody\n"
    journeys_yaml = (
        "journeys:\n"
        "  - id: legacy-plan\n"
        "    title: Legacy plan, now multi-step\n"
        "    category: water\n"
        "    guides:\n"
        "      - water-a\n"
        "      - water-b\n"
    )

    content_dir = tmp_path / "content"
    (content_dir / "guides").mkdir(parents=True)
    (content_dir / "checklists").mkdir()
    (content_dir / "md_skills").mkdir()
    (content_dir / "guides" / "water-a.md").write_text(guide_a_md, encoding="utf-8")
    (content_dir / "guides" / "water-b.md").write_text(guide_b_md, encoding="utf-8")
    (content_dir / "journeys.yaml").write_text(journeys_yaml, encoding="utf-8")
    monkeypatch.setattr(settings, "content_dir", str(content_dir))

    bundled = tmp_path / "bundled"
    (bundled / "guides").mkdir(parents=True)
    (bundled / "checklists").mkdir()
    (bundled / "md_skills").mkdir()
    (bundled / "guides" / "water-a.md").write_text(guide_a_md, encoding="utf-8")
    (bundled / "guides" / "water-b.md").write_text(guide_b_md, encoding="utf-8")
    (bundled / "checklists" / "new-checklist.md").write_text(
        "---\nid: new-checklist\ntitle: New\n---\n- [ ] item\n", encoding="utf-8"
    )
    (bundled / "journeys.yaml").write_text(journeys_yaml, encoding="utf-8")
    monkeypatch.setenv("HORIZON_BUNDLED_CONTENT", str(bundled))

    engine = create_engine(f"sqlite:///{tmp_path / 'isolated.db'}")
    SQLModel.metadata.create_all(engine)

    import horizon.seed as seed_module

    monkeypatch.setattr(seed_module, "engine", engine)

    # Legacy DB state: seeded long ago, before the >= 2-guide rule and
    # checklists existed.
    with Session(engine) as session:
        session.add(Guide(id="water-a", title="A", category=Category.water, path="water-a.md"))
        session.add(
            Journey(id="legacy-plan", title="Legacy single-guide plan", category=Category.water)
        )
        session.add(JourneyGuideLink(journey_id="legacy-plan", guide_id="water-a", position=0))
        session.commit()

    seed_if_empty()

    with Session(engine) as session:
        journey = session.get(Journey, "legacy-plan")
        assert journey is not None
        assert journey.title == "Legacy plan, now multi-step"
        links = session.exec(
            select(JourneyGuideLink).where(JourneyGuideLink.journey_id == "legacy-plan")
        ).all()
        assert {link.guide_id for link in links} == {"water-a", "water-b"}
        assert session.exec(select(Checklist)).all() != []
        assert session.get(Guide, "water-b") is not None

    assert (Path(content_dir) / "checklists" / "new-checklist.md").is_file()
