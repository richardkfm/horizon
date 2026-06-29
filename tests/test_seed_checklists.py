"""Unit tests for checklist content discovery in the seeder."""

from __future__ import annotations

from pathlib import Path

from horizon.models import Category
from horizon.seed import _load_checklists


def test_load_checklists_discovers_files(tmp_path: Path):
    d = tmp_path / "checklists"
    d.mkdir()
    (d / "go-bag.md").write_text(
        "---\nid: go-bag\ntitle: Go-bag\nsummary: A grab-and-go kit.\n"
        "category: emergencies\n---\n\n- [ ] Water\n",
        encoding="utf-8",
    )
    checklists = _load_checklists(d)
    assert len(checklists) == 1
    c = checklists[0]
    assert c.id == "go-bag"
    assert c.title == "Go-bag"
    assert c.category == Category.emergencies
    assert c.path == "go-bag.md"


def test_load_checklists_category_is_optional(tmp_path: Path):
    d = tmp_path / "checklists"
    d.mkdir()
    (d / "misc.md").write_text("---\nid: misc\ntitle: Misc\n---\n\n- [ ] Thing\n", encoding="utf-8")
    (c,) = _load_checklists(d)
    assert c.category is None


def test_load_checklists_skips_invalid_category(tmp_path: Path):
    d = tmp_path / "checklists"
    d.mkdir()
    (d / "bad.md").write_text(
        "---\nid: bad\ntitle: Bad\ncategory: nonsense\n---\n", encoding="utf-8"
    )
    assert _load_checklists(d) == []


def test_load_checklists_missing_dir_returns_empty(tmp_path: Path):
    assert _load_checklists(tmp_path / "nope") == []
