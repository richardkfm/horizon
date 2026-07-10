"""Tests for the ``horizon-admin`` interactive arrow-key menu.

Pytest's captured stdin/stdout are never a tty, so these exercise the plain
numbered-prompt fallback (``menu._select_plain``) rather than the ``curses``
widget -- the same code path a piped or non-interactive terminal takes. The
curses picker itself is a thin, mostly-untestable wrapper around a well-known
stdlib API and is covered by manual verification instead.
"""

from __future__ import annotations

import pytest

from horizon.db import init_db
from horizon.scripts import admin as cli
from horizon.scripts import menu
from horizon.seed import seed_if_empty
from horizon.services import llm


@pytest.fixture
def seeded():
    init_db()
    seed_if_empty()


@pytest.fixture(autouse=True)
def offline_llm(monkeypatch):
    monkeypatch.setattr(llm, "available", lambda: False)


def _feed(monkeypatch, *answers: str):
    """Queue successive ``input()`` answers for the plain-menu fallback."""
    queue = list(answers)

    def fake_input(prompt: str = "") -> str:
        if not queue:
            raise EOFError
        return queue.pop(0)

    monkeypatch.setattr("builtins.input", fake_input)


def test_select_plain_returns_chosen_index(monkeypatch, capsys):
    _feed(monkeypatch, "2")
    assert menu._select_plain("Title", ["a", "b", "c"]) == 1
    out = capsys.readouterr().out
    assert "1. a" in out and "2. b" in out and "3. c" in out


def test_select_plain_reprompts_on_invalid_choice(monkeypatch, capsys):
    _feed(monkeypatch, "nope", "99", "1")
    assert menu._select_plain("Title", ["only"]) == 0
    assert "Not a valid choice." in capsys.readouterr().out


def test_select_plain_cancel_returns_none(monkeypatch):
    _feed(monkeypatch, "q")
    assert menu._select_plain("Title", ["a", "b"]) is None


def test_select_plain_empty_input_cancels(monkeypatch):
    _feed(monkeypatch, "")
    assert menu._select_plain("Title", ["a", "b"]) is None


def test_bare_invocation_launches_menu(monkeypatch, seeded, capsys):
    # `horizon-admin` with no subcommand at all is the friendly front door.
    _feed(monkeypatch, "q")  # quit immediately
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "main menu" in out
    assert "Quit" in out


def test_menu_subcommand_quits_cleanly(monkeypatch, seeded, capsys):
    _feed(monkeypatch, "q")
    assert cli.main(["menu"]) == 0
    assert "main menu" in capsys.readouterr().out


def test_menu_shows_the_logo_banner(monkeypatch, seeded, capsys):
    # The ASCII banner is drawn as part of the main-menu screen itself (not
    # printed once and left behind), so it should reappear each time the
    # operator lands back on the main menu, in both curses and plain mode.
    _feed(monkeypatch, "q")
    assert cli.main(["menu"]) == 0
    out = capsys.readouterr().out
    assert "offline-first autonomy & rebuilding node" in out
    assert "the horizon" in out


def test_menu_runs_status_action_and_returns(monkeypatch, seeded, capsys):
    # Choose "Status" (option 6), then Enter to dismiss the pause, then quit.
    status_index = [label for label, _h in menu._MAIN_MENU].index(
        "Status: runtime + content overview"
    )
    _feed(monkeypatch, str(status_index + 1), "", "q")
    assert cli.main(["menu"]) == 0
    out = capsys.readouterr().out
    assert "content:" in out
    assert "journeys" in out


def test_menu_browse_guides_search_and_view(monkeypatch, seeded, capsys):
    guides_index = [label for label, _h in menu._MAIN_MENU].index("Browse how-to guides")
    # Browse guides -> search by keyword -> "rainwater" -> first result -> back out.
    _feed(
        monkeypatch,
        str(guides_index + 1),
        "2",
        "rainwater",
        "1",
        "",
        "q",
        "q",
        "q",
    )
    assert cli.main(["menu"]) == 0
    out = capsys.readouterr().out
    assert "rainwater" in out.lower()


def test_menu_recommend_flow(monkeypatch, seeded, capsys):
    recommend_index = [label for label, _h in menu._MAIN_MENU].index(
        "Where to start (recommend for a goal)"
    )
    _feed(monkeypatch, str(recommend_index + 1), "safe drinking water", "", "q")
    assert cli.main(["menu"]) == 0
    out = capsys.readouterr().out
    assert "Where to start" in out


def test_menu_packs_list_action(monkeypatch, capsys):
    packs_index = [label for label, _h in menu._MAIN_MENU].index(
        "Content packs (list / download / remove)"
    )
    _feed(monkeypatch, str(packs_index + 1), "1", "", "q", "q")
    assert cli.main(["menu"]) == 0
    out = capsys.readouterr().out
    assert "content packs" in out.lower() or "PACK" in out
