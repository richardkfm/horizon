"""Arrow-key-navigable menu for ``horizon-admin``.

The subcommands in ``admin.py`` are the full surface, but they require an
operator to already know the command names and flags. This module is the
friendly front door: ``horizon-admin`` with no arguments (or ``horizon-admin
menu``) drops into a menu you drive with the arrow keys (or ``j``/``k``) and
Enter, that walks a first-time operator to every subcommand without them
typing anything but a search term or a goal.

Built on the standard library's ``curses`` only — no new dependency, and it
already works everywhere horizon targets: a Raspberry Pi over SSH, a serial
console, a plain terminal. When the terminal isn't interactive (piped output,
no ``curses``, e.g. Windows) it falls back to a numbered ``input()`` prompt
menu instead of crashing, the same "degrade, don't break" rule the web UI
follows for optional integrations.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from types import SimpleNamespace

from horizon.scripts import admin

_Handler = Callable[[], None]


# --- selection widget ---------------------------------------------------


def _select(title: str, options: list[str], subtitle: str = "", banner: str = "") -> int | None:
    """Show a menu and return the chosen index, or ``None`` on cancel.

    ``banner`` (the ASCII logo) is only ever passed for the top-level main
    menu -- submenus stay banner-free so the option list gets the vertical
    space on a small terminal.
    """
    if not options:
        return None
    if sys.stdout.isatty() and sys.stdin.isatty():
        try:
            import curses
        except ImportError:
            pass
        else:
            try:
                return curses.wrapper(_select_curses, title, options, subtitle, banner)
            except curses.error:
                pass  # terminal too small / unsupported -- fall back to plain
    return _select_plain(title, options, subtitle, banner)


def _select_curses(
    stdscr, title: str, options: list[str], subtitle: str, banner: str
) -> int | None:
    import curses

    curses.curs_set(0)
    stdscr.keypad(True)
    idx = 0
    top = 0
    footer = "Up/Down or j/k: move   Enter: select   q: back"
    banner_lines = banner.splitlines() if banner else []
    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        row = 0
        # Only draw the logo if it (plus the title, options, and footer) actually
        # fits -- a small terminal (or SSH session resized narrow) drops it rather
        # than clipping the menu the operator actually needs.
        needed = len(banner_lines) + len(options) + 5
        if banner_lines and h >= needed:
            for line in banner_lines:
                stdscr.addstr(row, 0, line[: max(w - 1, 0)], curses.A_DIM)
                row += 1
            row += 1
        stdscr.addstr(row, 0, title[: max(w - 1, 0)], curses.A_BOLD)
        row += 1
        if subtitle:
            stdscr.addstr(row, 0, subtitle[: max(w - 1, 0)])
            row += 1
        row += 1
        list_top = row
        visible = max(1, h - list_top - 2)
        if idx < top:
            top = idx
        if idx >= top + visible:
            top = idx - visible + 1
        for i in range(top, min(len(options), top + visible)):
            marker = "> " if i == idx else "  "
            attr = curses.A_REVERSE if i == idx else curses.A_NORMAL
            stdscr.addstr(list_top + (i - top), 0, (marker + options[i])[: max(w - 1, 0)], attr)
        stdscr.addstr(min(h - 1, list_top + visible + 1), 0, footer[: max(w - 1, 0)], curses.A_DIM)
        stdscr.refresh()
        key = stdscr.getch()
        if key in (curses.KEY_UP, ord("k")):
            idx = (idx - 1) % len(options)
        elif key in (curses.KEY_DOWN, ord("j")):
            idx = (idx + 1) % len(options)
        elif key in (curses.KEY_ENTER, 10, 13):
            return idx
        elif key in (27, ord("q")):
            return None
        elif key == curses.KEY_RESIZE:
            continue


def _select_plain(
    title: str, options: list[str], subtitle: str = "", banner: str = ""
) -> int | None:
    if banner:
        print(banner)
    print()
    print(title)
    if subtitle:
        print(subtitle)
    for i, opt in enumerate(options, start=1):
        print(f"  {i}. {opt}")
    while True:
        try:
            raw = input("Choose a number (Enter/q to go back): ").strip()
        except EOFError:
            return None
        if raw.lower() in ("q", "quit", ""):
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw) - 1
        print("  Not a valid choice.")


def _prompt(message: str) -> str:
    try:
        return input(message).strip()
    except EOFError:
        return ""


def _pause() -> None:
    print()
    try:
        input("Press Enter to go back... ")
    except EOFError:
        pass


# --- actions --------------------------------------------------------------


def _do_status() -> None:
    admin.cmd_status(SimpleNamespace(json=False, no_logo=True))
    _pause()


def _do_doctor() -> None:
    admin.cmd_doctor(SimpleNamespace(json=False, no_logo=True))
    _pause()


def _do_check() -> None:
    idx = _select(
        "Check content health",
        ["Files, links and search index", "Also probe the local model runtime"],
    )
    if idx is None:
        return
    admin.cmd_check(SimpleNamespace(check_model=idx == 1, json=False, no_logo=True))
    _pause()


def _do_reindex() -> None:
    admin.cmd_reindex(SimpleNamespace())
    _pause()


def _do_seed() -> None:
    idx = _select(
        "Seed the database",
        ["Seed if empty (safe)", "Force re-seed from disk (overwrites edits)"],
    )
    if idx is None:
        return
    admin.cmd_seed(SimpleNamespace(force=idx == 1))
    _pause()


def _do_config() -> None:
    admin.cmd_config(SimpleNamespace(json=False))
    _pause()


def _category_choices() -> list[str]:
    from horizon.models import Category

    return [c.value for c in Category]


def _browse_journeys() -> None:
    from sqlmodel import Session, select

    from horizon.db import engine
    from horizon.models import Category, Journey

    while True:
        categories = ["All categories", *_category_choices()]
        cidx = _select("Step-by-step plans", categories)
        if cidx is None:
            return
        category = None if cidx == 0 else categories[cidx]

        with Session(engine) as session:
            statement = select(Journey)
            if category:
                statement = statement.where(Journey.category == Category(category))
            statement = statement.order_by(Journey.category, Journey.difficulty, Journey.id)
            journeys = session.exec(statement).all()
            rows = [
                (j.id, f"{j.title}  ({j.estimated_time or j.category.value})") for j in journeys
            ]

        if not rows:
            print("\nNo plans in that category yet.")
            _pause()
            continue

        while True:
            jidx = _select(
                "Step-by-step plans", [label for _id, label in rows], subtitle=category or ""
            )
            if jidx is None:
                break
            admin.cmd_journey(SimpleNamespace(id=rows[jidx][0], json=False))
            _pause()


def _browse_guides() -> None:
    from sqlmodel import Session, select

    from horizon.db import engine
    from horizon.models import Category, Guide

    while True:
        categories = ["All categories", "Search by keyword", *_category_choices()]
        cidx = _select("How-to guides", categories)
        if cidx is None:
            return

        category = None
        search = None
        if cidx == 1:
            search = _prompt("Search term: ")
            if not search:
                continue
        elif cidx > 1:
            category = categories[cidx]

        with Session(engine) as session:
            statement = select(Guide)
            if category:
                statement = statement.where(Guide.category == Category(category))
            statement = statement.order_by(Guide.category, Guide.id)
            guides = session.exec(statement).all()

        needle = (search or "").lower()
        rows = [
            (g.id, f"{g.title}  ({g.category.value})")
            for g in guides
            if not needle or needle in g.title.lower() or needle in (g.summary or "").lower()
        ]

        if not rows:
            print("\nNo matching guides.")
            _pause()
            continue

        while True:
            gidx = _select(
                "How-to guides", [label for _id, label in rows], subtitle=category or search or ""
            )
            if gidx is None:
                break
            admin.cmd_guide(SimpleNamespace(id=rows[gidx][0], raw=False))
            _pause()


def _do_recommend() -> None:
    goal = _prompt("What's your goal? (e.g. safe drinking water): ")
    if not goal:
        return
    admin.cmd_recommend(
        SimpleNamespace(goal=[goal], people=None, climate=None, resource=None, json=False)
    )
    _pause()


def _do_ask() -> None:
    question = _prompt("Ask the assistant: ")
    if not question:
        return
    admin.cmd_ask(SimpleNamespace(question=[question], no_jargon=False, json=False))
    _pause()


def _browse_packs() -> None:
    from horizon.services.packs import installed_packs, load_catalog

    while True:
        idx = _select(
            "Content packs", ["List installed & available", "Download a pack", "Remove a pack"]
        )
        if idx is None:
            return
        if idx == 0:
            admin.cmd_packs_list(SimpleNamespace())
            _pause()
        elif idx == 1:
            catalog = load_catalog()
            if not catalog:
                print("\nNo packs in the catalog.")
                _pause()
                continue
            labels = [f"{s.title}  ({s.id})" for s in catalog]
            pidx = _select("Download a pack (fetches over the network)", labels)
            if pidx is None:
                continue
            confirm = _prompt(f"Download {catalog[pidx].title!r} now? [y/N]: ")
            if confirm.lower().startswith("y"):
                admin.cmd_packs_download(SimpleNamespace(name=catalog[pidx].id, force=False))
                _pause()
        elif idx == 2:
            installed = installed_packs()
            if not installed:
                print("\nNo packs installed.")
                _pause()
                continue
            labels = [f"{p['id']}" for p in installed]
            pidx = _select("Remove a pack", labels)
            if pidx is None:
                continue
            confirm = _prompt(f"Remove {installed[pidx]['id']!r}? [y/N]: ")
            if confirm.lower().startswith("y"):
                admin.cmd_packs_remove(SimpleNamespace(name=installed[pidx]["id"]))
                _pause()


_MAIN_MENU: list[tuple[str, _Handler]] = [
    ("Where to start (recommend for a goal)", _do_recommend),
    ("Browse step-by-step plans", _browse_journeys),
    ("Browse how-to guides", _browse_guides),
    ("Ask the local assistant a question", _do_ask),
    ("Content packs (list / download / remove)", _browse_packs),
    ("Status: runtime + content overview", _do_status),
    ("Doctor: health-check integrations", _do_doctor),
    ("Check: content-health diagnostics", _do_check),
    ("Reindex the assistant's search", _do_reindex),
    ("Seed the database from bundled content", _do_seed),
    ("Show effective configuration", _do_config),
]


def run_menu() -> int:
    """Run the interactive main menu until the operator quits. Always exits 0."""
    banner = admin._banner().strip("\n")
    options = [label for label, _handler in _MAIN_MENU] + ["Quit"]
    while True:
        idx = _select("horizon-admin -- main menu", options, banner=banner)
        if idx is None or options[idx] == "Quit":
            return 0
        _MAIN_MENU[idx][1]()
