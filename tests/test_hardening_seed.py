"""Hardening regressions: front matter, seeding, re-seed atomicity, boot resilience.

Each test pins a failure mode that used to take the node down or lose data:
a ``---`` inside front matter, one malformed content file blocking boot, a
re-seed that could leave the database empty, stale rows for deleted content,
and a corrupt bundle manifest overwriting operator edits.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

import horizon.seed as seed_module
from horizon.config import settings
from horizon.models import Checklist, Guide, Journey, JourneyGuideLink
from horizon.services.frontmatter import (
    FrontMatterError,
    coerce_difficulty,
    split_front_matter,
    strip_front_matter,
)
from horizon.services.importer import ParsedChapter, render_book_guide, split_book_into_chapters

# --- shared front-matter parser ------------------------------------------------


def test_front_matter_tolerates_triple_dash_inside_values():
    text = (
        "---\nid: g\ntitle: Part One --- Beginnings\nsummary: Well---yes\n---\n# Body\n---\nmore\n"
    )
    meta, body = split_front_matter(text)
    assert meta == {"id": "g", "title": "Part One --- Beginnings", "summary": "Well---yes"}
    assert body == "# Body\n---\nmore\n"


def test_front_matter_closing_fence_must_be_a_whole_line():
    text = "---\nid: g\nsummary: '---'\n---\nbody\n"
    meta, body = split_front_matter(text)
    assert meta["summary"] == "---"
    assert body == "body\n"


def test_front_matter_absent_or_empty():
    assert split_front_matter("# Just markdown\n") == ({}, "# Just markdown\n")
    assert split_front_matter("---\n---\nbody") == ({}, "body")
    assert strip_front_matter("---\nid: x\n---\n\nbody") == "body"


def test_front_matter_strict_rejects_bad_yaml_and_non_mapping():
    with pytest.raises(FrontMatterError):
        split_front_matter("---\ntitle: a: b: c\n---\nbody", strict=True)
    with pytest.raises(FrontMatterError):
        split_front_matter("---\n- a\n- b\n---\nbody", strict=True)
    # Lenient mode degrades to empty metadata but keeps the body.
    assert split_front_matter("---\n- a\n---\nbody") == ({}, "body")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(2, 2), ("4", 4), (2.7, 2), ("easy", 3), (None, 3), (0, 1), (99, 5), (-3, 1), (True, 3)],
)
def test_coerce_difficulty(raw, expected):
    assert coerce_difficulty(raw) == expected


# --- importer never emits front matter that breaks parsing ---------------------


def test_book_chapter_starting_with_rule_gets_a_real_summary():
    (chapter, *_rest) = split_book_into_chapters("# One\n\n---\n\nbody one\n\n# Two\n\nbody two")
    md = render_book_guide(chapter, guide_id="b", source="b.txt")
    meta, body = split_front_matter(md, strict=True)
    assert meta["summary"] == "body one"
    assert meta["title"] == "One"
    assert body.startswith("# One")


def test_book_title_with_triple_dash_round_trips():
    chapter = ParsedChapter(
        title="Part One --- Beginnings", body="---\n\n***\n\nWell---I think so."
    )
    md = render_book_guide(chapter, guide_id="b", source="b.txt")
    meta, _ = split_front_matter(md, strict=True)
    assert meta["title"] == "Part One --- Beginnings"
    assert meta["summary"] == "Well---I think so."


def test_book_chapter_without_words_falls_back_to_title():
    chapter = ParsedChapter(title="Interlude", body="---")
    meta, _ = split_front_matter(render_book_guide(chapter, guide_id="b", source="b"), strict=True)
    assert meta["summary"] == "Interlude"


# --- isolated content dir + database for seeding tests -------------------------

_GUIDE = "---\nid: {id}\ntitle: {title}\ncategory: water\nsummary: s\n---\nbody\n"
_JOURNEYS = (
    "journeys:\n"
    "  - id: plan-a\n"
    "    title: Plan A\n"
    "    category: water\n"
    "    guides: [g1, g2]\n"
    "  - id: plan-b\n"
    "    title: Plan B\n"
    "    category: water\n"
    "    guides: [g1, g2, g1]\n"
)


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """A temp content dir (also used as the bundle) and a temp SQLite database."""
    content = tmp_path / "content"
    for sub in ("guides", "checklists", "md_skills"):
        (content / sub).mkdir(parents=True)
    (content / "guides" / "g1.md").write_text(_GUIDE.format(id="g1", title="G1"), "utf-8")
    (content / "guides" / "g2.md").write_text(_GUIDE.format(id="g2", title="G2"), "utf-8")
    (content / "checklists" / "c1.md").write_text("---\nid: c1\ntitle: C1\n---\n- [ ] x\n", "utf-8")
    (content / "journeys.yaml").write_text(_JOURNEYS, "utf-8")

    bundle = tmp_path / "bundle"
    (bundle / "guides").mkdir(parents=True)
    (bundle / "journeys.yaml").write_text("journeys: []\n", "utf-8")

    monkeypatch.setattr(settings, "content_dir", str(content))
    monkeypatch.setenv("HORIZON_BUNDLED_CONTENT", str(bundle))
    # The bundle's journeys.yaml would replace ours on first sync; mark ours as
    # an operator edit so the sync leaves it alone.
    (content / ".bundle_manifest.json").write_text(
        json.dumps({"journeys.yaml": "operator-owned"}), "utf-8"
    )

    engine = create_engine(f"sqlite:///{tmp_path / 'h.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(seed_module, "engine", engine)
    return content, engine


def _ids(engine, model) -> set[str]:
    with Session(engine) as session:
        return set(session.exec(select(model.id)).all())


def test_bad_content_files_are_skipped_not_fatal(isolated):
    content, engine = isolated
    guides = content / "guides"
    (guides / "bad-int.md").write_text(
        "---\nid: bad-int\ntitle: X\ncategory: water\ndifficulty: easy\n---\nbody", "utf-8"
    )
    (guides / "bad-yaml.md").write_text("---\nid: x2\ntitle: X: y: z\n---\nbody", "utf-8")
    (guides / "a-list.md").write_text("---\n- a\n- b\n---\nbody", "utf-8")
    (guides / "bad-cat.md").write_text("---\nid: x4\ncategory: [water]\n---\nbody", "utf-8")
    (guides / "zz-dup.md").write_text(_GUIDE.format(id="g1", title="Dup"), "utf-8")
    (content / "checklists" / "bad.md").write_text("---\n[unclosed\n---\n- [ ] x", "utf-8")

    seed_module.seed_if_empty()

    assert _ids(engine, Guide) == {"g1", "g2", "bad-int"}
    with Session(engine) as session:
        assert session.get(Guide, "bad-int").difficulty == 3
        assert session.get(Guide, "g1").title == "G1"  # the duplicate didn't win
    assert _ids(engine, Checklist) == {"c1"}


def test_plan_with_repeated_guide_is_deduplicated(isolated):
    _content, engine = isolated
    seed_module.seed_if_empty()
    with Session(engine) as session:
        links = session.exec(
            select(JourneyGuideLink)
            .where(JourneyGuideLink.journey_id == "plan-b")
            .order_by(JourneyGuideLink.position)
        ).all()
    assert [(link.guide_id, link.position) for link in links] == [("g1", 0), ("g2", 1)]


def test_stale_rows_are_removed_on_reseed(isolated):
    content, engine = isolated
    seed_module.seed_if_empty()
    assert _ids(engine, Journey) == {"plan-a", "plan-b"}

    (content / "guides" / "g2.md").unlink()
    (content / "checklists" / "c1.md").unlink()
    (content / "journeys.yaml").write_text(_JOURNEYS.split("  - id: plan-b")[0], "utf-8")
    seed_module.seed_if_empty()

    assert _ids(engine, Guide) == {"g1"}
    assert _ids(engine, Checklist) == set()
    # plan-a now resolves to one guide (dropped); plan-b left the file (removed).
    assert _ids(engine, Journey) == set()
    with Session(engine) as session:
        assert session.exec(select(JourneyGuideLink)).all() == []


def test_unparseable_file_keeps_its_previous_row(isolated):
    content, engine = isolated
    seed_module.seed_if_empty()
    (content / "guides" / "g2.md").write_text("---\ntitle: [broken\n---\nbody", "utf-8")
    seed_module.seed_if_empty()
    assert "g2" in _ids(engine, Guide)


def test_reseed_is_atomic(isolated, monkeypatch):
    _content, engine = isolated
    seed_module.seed_if_empty()
    before = _ids(engine, Guide)
    assert before

    def boom(session, content_dir):
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(seed_module, "_sync_content", boom)
    with pytest.raises(RuntimeError):
        seed_module.reseed()

    # The delete was rolled back with the failed reload: nothing was lost.
    assert _ids(engine, Guide) == before
    assert _ids(engine, Journey) == {"plan-a", "plan-b"}


def test_reseed_rebuilds_rows(isolated):
    _content, engine = isolated
    seed_module.seed_if_empty()
    summary = seed_module.reseed()
    assert summary["before"]["guides"] == summary["after"]["guides"] == 2
    assert summary["after"]["checklists"] == 1


def test_broken_journeys_yaml_keeps_existing_plans(isolated):
    content, engine = isolated
    seed_module.seed_if_empty()
    (content / "journeys.yaml").write_text("journeys: [unclosed\n", "utf-8")
    seed_module.seed_if_empty()
    assert _ids(engine, Journey) == {"plan-a", "plan-b"}


# --- bundle manifest -----------------------------------------------------------


def test_corrupt_manifest_never_overwrites_operator_edits(tmp_path, monkeypatch):
    content = tmp_path / "content"
    bundle = tmp_path / "bundle"
    (bundle / "guides").mkdir(parents=True)
    (bundle / "journeys.yaml").write_text("journeys: []\n", "utf-8")
    (bundle / "guides" / "a.md").write_text("v1", "utf-8")
    monkeypatch.setattr(settings, "content_dir", str(content))
    monkeypatch.setenv("HORIZON_BUNDLED_CONTENT", str(bundle))

    seed_module._ensure_content_dir()
    target = content / "guides" / "a.md"
    target.write_text("operator edit", "utf-8")
    (content / ".bundle_manifest.json").write_text("{truncated", "utf-8")
    (bundle / "guides" / "a.md").write_text("v2", "utf-8")

    seed_module._ensure_content_dir()
    assert target.read_text("utf-8") == "operator edit"
    # ...and the rewritten manifest keeps protecting it on later runs.
    seed_module._ensure_content_dir()
    assert target.read_text("utf-8") == "operator edit"
    manifest = json.loads((content / ".bundle_manifest.json").read_text("utf-8"))
    assert manifest["guides/a.md"] == "operator-owned"


def test_manifest_is_written_atomically(tmp_path):
    path = tmp_path / ".bundle_manifest.json"
    seed_module._save_manifest(path, {"a": "1"})
    assert json.loads(path.read_text("utf-8")) == {"a": "1"}
    assert [p.name for p in tmp_path.iterdir()] == [path.name]  # no temp files left


def test_read_manifest_reports_trust(tmp_path):
    assert seed_module._read_manifest(tmp_path / "missing.json") == ({}, True)
    bad = tmp_path / "bad.json"
    bad.write_text("[1, 2]", "utf-8")
    assert seed_module._read_manifest(bad) == ({}, False)


# --- boot resilience -------------------------------------------------------------


def test_app_boots_with_a_malformed_guide(monkeypatch):
    guides = Path(settings.content_dir) / "guides"
    bad = guides / "zz-hardening-bad.md"
    guides.mkdir(parents=True, exist_ok=True)
    bad.write_text("---\nid: zz\ncategory: water\ndifficulty: easy\ntitle: [x\n---\nbody", "utf-8")
    try:
        from horizon.main import app

        with TestClient(app) as client:
            assert client.get("/healthz").status_code == 200
            assert client.get("/guides").status_code == 200
    finally:
        bad.unlink()


def test_app_boots_when_a_startup_step_raises(monkeypatch):
    from horizon.main import app

    def boom() -> None:
        raise RuntimeError("seed exploded")

    monkeypatch.setattr(seed_module, "seed_if_empty", boom)
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
