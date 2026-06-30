"""``horizon-content import`` CLI tests.

The network is faked (a tiny ``httpx.Client`` stand-in returning fixed HTML or
image bytes), mirroring the pattern in ``test_packs.py``. These exercise the
write-to-disk + argument-handling glue around ``horizon.services.importer``,
which is unit-tested directly (and without any network) in
``test_importer.py``.
"""

from __future__ import annotations

import httpx
import pytest

from horizon.config import settings
from horizon.scripts import content as cli

WIKIHOW_HTML = """
<h1>How to Build a Story Circle</h1>
<p>Gathering around a fire to tell stories builds community.</p>
<h2>Steps</h2>
<ol>
<li><b>Pick a spot.</b> Choose a safe, flat clearing.
<img src="https://example.test/spot.jpg" alt="A clear fire spot"></li>
<li><b>Invite people.</b> Tell neighbours the time and place.</li>
</ol>
"""

BOOK_TEXT = """Chapter 1: Greetings
Greetings here are never rushed.

Chapter 2: Festivals
Every household brings a dish to share.
"""


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "content_dir", str(tmp_path / "content"))
    return tmp_path


class _FakeResponse:
    def __init__(self, text: str = "", content: bytes = b""):
        self.text = text
        self.content = content or text.encode("utf-8")

    def raise_for_status(self) -> None:
        pass


class _FakeClient:
    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, url: str):
        if url.endswith(".jpg"):
            return _FakeResponse(content=b"\xff\xd8fakejpeg")
        return _FakeResponse(text=WIKIHOW_HTML)


def _patch_http(monkeypatch):
    monkeypatch.setattr(httpx, "Client", _FakeClient)


def _run(args: list[str]) -> int:
    parser = cli.build_parser()
    ns = parser.parse_args(args)
    return ns.func(ns)


# --- wikihow import ------------------------------------------------------------


def test_import_wikihow_writes_guide(env, monkeypatch, capsys):
    _patch_http(monkeypatch)
    rc = _run(
        [
            "import",
            "wikihow",
            "https://www.wikihow.com/Build-a-Story-Circle",
            "--category",
            "culture",
        ]
    )
    assert rc == 0

    out_path = env / "content" / "guides" / "how-to-build-a-story-circle.md"
    assert out_path.is_file()
    text = out_path.read_text(encoding="utf-8")
    assert "category: culture" in text
    assert "# How to Build a Story Circle" in text
    assert "![A clear fire spot]" in text

    image_path = env / "content" / "guides" / "images"
    assert any(image_path.iterdir())


def test_import_wikihow_custom_id_and_category(env, monkeypatch):
    _patch_http(monkeypatch)
    rc = _run(
        [
            "import",
            "wikihow",
            "https://www.wikihow.com/Build-a-Story-Circle",
            "--id",
            "culture-story-circle",
            "--category",
            "cooperation",
            "--no-images",
        ]
    )
    assert rc == 0
    out_path = env / "content" / "guides" / "culture-story-circle.md"
    assert out_path.is_file()
    assert "category: cooperation" in out_path.read_text(encoding="utf-8")
    assert not (env / "content" / "guides" / "images").exists()


def test_import_wikihow_refuses_to_overwrite_without_force(env, monkeypatch, capsys):
    _patch_http(monkeypatch)
    args = [
        "import",
        "wikihow",
        "https://www.wikihow.com/X",
        "--id",
        "dup",
        "--category",
        "culture",
        "--no-images",
    ]
    _run(args)
    rc = _run(args)
    assert rc == 1
    assert "already exists" in capsys.readouterr().err


def test_import_wikihow_force_overwrites(env, monkeypatch):
    _patch_http(monkeypatch)
    args = [
        "import",
        "wikihow",
        "https://www.wikihow.com/X",
        "--id",
        "dup",
        "--category",
        "culture",
        "--no-images",
    ]
    _run(args)
    rc = _run([*args, "--force"])
    assert rc == 0


def test_import_wikihow_requires_category(env, monkeypatch, capsys):
    """WikiHow spans every topic, so there is no sensible default category."""
    _patch_http(monkeypatch)
    with pytest.raises(SystemExit) as exc_info:
        cli.build_parser().parse_args(["import", "wikihow", "https://www.wikihow.com/X"])
    assert exc_info.value.code == 2
    assert "--category" in capsys.readouterr().err


def test_import_wikihow_reseed_loads_into_db(env, monkeypatch):
    """``--reseed`` reloads the database from disk, picking up the new guide.

    Uses its own throwaway SQLite engine (swapped into both ``horizon.db`` and
    ``horizon.seed``, which imported its own reference at module load time) so
    this destructive reseed cannot wipe the shared test-session database that
    other tests rely on being fully populated.
    """
    _patch_http(monkeypatch)
    (env / "content").mkdir(exist_ok=True)
    (env / "content" / "journeys.yaml").write_text("journeys: []\n", encoding="utf-8")

    from sqlmodel import create_engine

    import horizon.db as db_module
    import horizon.seed as seed_module

    test_engine = create_engine(f"sqlite:///{env}/isolated.db")
    monkeypatch.setattr(db_module, "engine", test_engine)
    monkeypatch.setattr(seed_module, "engine", test_engine)

    rc = _run(
        [
            "import",
            "wikihow",
            "https://www.wikihow.com/Build-a-Story-Circle",
            "--id",
            "culture-story-circle",
            "--category",
            "culture",
            "--no-images",
            "--reseed",
        ]
    )
    assert rc == 0

    from sqlmodel import Session

    from horizon.models import Guide

    with Session(test_engine) as session:
        guide = session.get(Guide, "culture-story-circle")
        assert guide is not None
        assert guide.category.value == "culture"


# --- book import -----------------------------------------------------------------


def test_import_book_splits_chapters(env, tmp_path):
    book = tmp_path / "valley-customs.txt"
    book.write_text(BOOK_TEXT, encoding="utf-8")

    rc = _run(["import", "book", str(book), "--id-prefix", "culture-valley-customs"])
    assert rc == 0

    guides_dir = env / "content" / "guides"
    written = sorted(p.name for p in guides_dir.glob("culture-valley-customs-*.md"))
    assert written == [
        "culture-valley-customs-01-greetings.md",
        "culture-valley-customs-02-festivals.md",
    ]
    assert "Greetings here are never rushed." in (guides_dir / written[0]).read_text(
        encoding="utf-8"
    )


def test_import_book_missing_file(env, tmp_path, capsys):
    rc = _run(["import", "book", str(tmp_path / "missing.txt")])
    assert rc == 2
    assert "No such file" in capsys.readouterr().err


def test_import_book_skips_existing_without_force(env, tmp_path, capsys):
    book = tmp_path / "book.txt"
    book.write_text(BOOK_TEXT, encoding="utf-8")
    _run(["import", "book", str(book), "--id-prefix", "x"])
    rc = _run(["import", "book", str(book), "--id-prefix", "x"])
    assert rc == 1
    assert "skipping" in capsys.readouterr().err
