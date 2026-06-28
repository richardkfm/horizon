"""Tests for the content-health diagnostics service and its repairs.

These exercise the pure check logic (no LLM / vector DB needed) plus the
re-seed repair, mirroring CLAUDE.md's rule that core logic stays unit-testable
without external systems.
"""

from __future__ import annotations

from pathlib import Path

from sqlmodel import Session, select

from horizon.config import settings
from horizon.db import engine, init_db
from horizon.models import Guide, Journey, JourneyGuideLink
from horizon.seed import reseed, seed_if_empty
from horizon.services import diagnostics


def _ensure_seeded() -> None:
    init_db()
    seed_if_empty()


def _check(report: dict, check_id: str) -> dict:
    return next(c for c in report["checks"] if c["id"] == check_id)


def test_healthy_node_passes_all_checks():
    _ensure_seeded()
    report = diagnostics.run_checks()
    # A freshly seeded node has no hard failures.
    assert report["healthy"] is True
    assert report["counts"]["fail"] == 0
    # Core structural checks resolve cleanly.
    for cid in ("database", "guide_links", "guide_files", "duplicates"):
        assert _check(report, cid)["status"] == "ok"


def test_broken_guide_link_is_flagged():
    _ensure_seeded()
    with Session(engine) as session:
        journey_id = session.exec(select(Journey.id)).first()
        session.add(JourneyGuideLink(journey_id=journey_id, guide_id="does-not-exist"))
        session.commit()
    try:
        report = diagnostics.run_checks()
        links = _check(report, "guide_links")
        assert links["status"] == "warn"
        assert any("does-not-exist" in d for d in links["details"])
    finally:
        with Session(engine) as session:
            edge = session.get(JourneyGuideLink, (journey_id, "does-not-exist"))
            if edge:
                session.delete(edge)
                session.commit()


def test_missing_guide_file_is_a_hard_failure():
    _ensure_seeded()
    with Session(engine) as session:
        ghost = Guide(
            id="ghost-guide",
            title="Ghost",
            category=session.exec(select(Guide)).first().category,
            summary="x",
            path="ghost-guide-does-not-exist.md",
        )
        session.add(ghost)
        session.commit()
    try:
        report = diagnostics.run_checks()
        files = _check(report, "guide_files")
        assert files["status"] == "fail"
        assert report["healthy"] is False
        assert any("ghost-guide" in d for d in files["details"])
    finally:
        with Session(engine) as session:
            g = session.get(Guide, "ghost-guide")
            if g:
                session.delete(g)
                session.commit()


def test_missing_guide_image_is_flagged(tmp_path):
    _ensure_seeded()
    guides_dir = Path(settings.content_dir) / "guides"
    guides_dir.mkdir(parents=True, exist_ok=True)
    md = guides_dir / "img-test.md"
    md.write_text(
        "---\nid: img-test\ntitle: Img\ncategory: water\nsummary: s\n---\n\n"
        "![a diagram](images/missing-diagram.png)\n",
        encoding="utf-8",
    )
    with Session(engine) as session:
        from horizon.models import Category

        session.add(
            Guide(
                id="img-test", title="Img", category=Category.water, summary="s", path="img-test.md"
            )
        )
        session.commit()
    try:
        report = diagnostics.run_checks()
        images = _check(report, "guide_images")
        assert images["status"] == "warn"
        assert any("missing-diagram.png" in d for d in images["details"])
    finally:
        md.unlink(missing_ok=True)
        with Session(engine) as session:
            g = session.get(Guide, "img-test")
            if g:
                session.delete(g)
                session.commit()


def test_reseed_repair_restores_deleted_content():
    _ensure_seeded()
    with Session(engine) as session:
        before = len(session.exec(select(Journey)).all())
        assert before > 0
        # Wipe a journey and confirm the repair brings the set back.
        for link in session.exec(select(JourneyGuideLink)).all():
            session.delete(link)
        for j in session.exec(select(Journey)).all():
            session.delete(j)
        session.commit()
        assert len(session.exec(select(Journey)).all()) == 0

    summary = reseed()
    assert summary["after"]["journeys"] == before
    with Session(engine) as session:
        assert len(session.exec(select(Journey)).all()) == before


def test_run_repair_unknown_action():
    result = diagnostics.run_repair("nonsense")
    assert result["ok"] is False
