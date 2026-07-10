"""``horizon-admin`` CLI: headless operator tooling for a horizon node.

A self-hosted operator running horizon on a Raspberry Pi or an LXC container
rarely has a browser pointed at the box. The token-gated admin web area
(**Admin → …**) is the graphical surface; this command is its headless
equivalent — the things you reach for over SSH:

* ``status``   — runtime + content overview (what the dashboard shows);
* ``doctor``   — health checks of every optional integration (the integrations
  page), with a non-zero exit when something the operator asked for is broken;
* ``check``    — content-health diagnostics (broken links, missing files/images,
  a stale search index, orphaned or duplicate content) — Admin → Check & repair;
* ``reindex``  — rebuild the vector index after editing content;
* ``seed``     — load the bundled content into an empty database (``--force``
  re-seeds a populated one from disk);
* ``packs``    — list / download / remove offline content packs;
* ``config``   — print the effective, secret-free configuration.

Every command stays offline-first: only ``packs download`` reaches the network,
and only while the operator asks it to. Nothing here imports a sibling project
or buries a value judgement in logic — it just drives horizon's own services.

Access model: this CLI is deliberately **not** gated by the admin token. That
token guards the *web* admin area, which is reachable over the network; the CLI
runs locally, so its security boundary is shell/filesystem access. Anyone who
can run ``horizon-admin`` can already read ``config.yaml`` (where the token lives
in plaintext) and the SQLite database directly, so an app-level prompt would add
friction without adding protection — the same trust model as ``psql`` or
``systemctl``. Restrict access with OS login + file permissions, not a password
here. (``config`` still redacts the token so it is never printed.)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Any

from horizon import __version__
from horizon.config import (
    assistant_enabled,
    low_power_enabled,
    settings,
    web_enabled,
)

# --- Branding ---------------------------------------------------------------

# A sun cresting a horizon line over a block wordmark. Pure ASCII so it renders
# on a serial console, an e-ink terminal, or a plain SSH session with no fancy
# font or colour support — the same audiences horizon itself targets.
_LOGO = r"""
                         .--.
                     .-'      '-.
       \   |   /   .'   sunrise   '.
        '. | .'   /                  \
     -=== (   ) ===----------------------------  the horizon
        .' | '.   \                  /
       /   |   \   '.              .'
                     '-.        .-'
                         '--''--'
   _   _  ___  ____  ___ _____  ___  _   _
  | | | |/ _ \|  _ \|_ _|__  / / _ \| \ | |
  | |_| | | | | |_) || |  / /| | | | |  \| |
  |  _  | |_| |  _ < | | / /_| |_| | |\  |
  |_| |_|\___/|_| \_\___/____|\___/|_| \_|

  offline-first autonomy & rebuilding node · admin cli v{version}
"""


def _banner() -> str:
    return _LOGO.format(version=__version__)


# --- Small output helpers ---------------------------------------------------

# Status glyphs are plain words so the output is greppable and prints cleanly on
# terminals without colour or unicode.
_OK = "ok"
_WARN = "warn"
_OFF = "off"
_FAIL = "fail"


def _emit(payload: Any, *, as_json: bool) -> None:
    """Print a structured payload as JSON, or rely on the caller's plain text."""
    if as_json:
        print(json.dumps(payload, indent=2, default=str))


def _content_stats() -> dict:
    """Counts of journeys, guides, and skill-tree edges from the database."""
    from sqlmodel import Session, func, select

    from horizon.db import engine
    from horizon.models import (
        Category,
        Guide,
        Journey,
        JourneyGuideLink,
    )

    with Session(engine) as session:
        journey_rows = session.exec(
            select(Journey.category, func.count()).group_by(Journey.category)
        ).all()
        guide_rows = session.exec(
            select(Guide.category, func.count()).group_by(Guide.category)
        ).all()
        journeys = {cat.value: n for cat, n in journey_rows}
        guides = {cat.value: n for cat, n in guide_rows}
        per_category = [
            {
                "category": c.value,
                "journeys": journeys.get(c.value, 0),
                "guides": guides.get(c.value, 0),
            }
            for c in Category
        ]
        return {
            "journeys_total": sum(journeys.values()),
            "guides_total": sum(guides.values()),
            "guide_links": len(session.exec(select(JourneyGuideLink)).all()),
            "per_category": per_category,
        }


# --- status -----------------------------------------------------------------


def cmd_status(args: argparse.Namespace) -> int:
    """Print a runtime + content overview (the dashboard, headless)."""
    from horizon.services import packs

    try:
        stats = _content_stats()
        db_ok = True
    except Exception as exc:  # noqa: BLE001 - report rather than crash
        stats = {"error": str(exc)}
        db_ok = False

    installed = packs.installed_packs()
    available = packs.load_catalog()

    overview = {
        "version": __version__,
        "data_dir": settings.data_dir,
        "database": settings.database,
        "content_dir": settings.content_dir,
        "vectordb_path": settings.vectordb.path,
        "packs_dir": settings.content_packs.dir,
        "database_ok": db_ok,
        "content": stats,
        "packs": {"installed": len(installed), "available": len(available)},
    }

    if args.json:
        _emit(overview, as_json=True)
        return 0 if db_ok else 1

    if not args.no_logo:
        print(_banner())

    print(f"horizon {overview['version']}")
    print(f"  data dir      {overview['data_dir']}")
    print(f"  database      {overview['database']}")
    print(f"  content dir   {overview['content_dir']}")
    print(f"  vector store  {overview['vectordb_path']}")
    print(f"  packs dir     {overview['packs_dir']}")
    print()

    if not db_ok:
        print(f"  database: UNREADABLE — {stats['error']}", file=sys.stderr)
        return 1

    print(
        f"  content: {stats['journeys_total']} plans, "
        f"{stats['guides_total']} guides, "
        f"{stats['guide_links']} guide links"
    )
    width = max((len(r["category"]) for r in stats["per_category"]), default=8)
    for row in stats["per_category"]:
        print(
            f"    {row['category']:<{width}}  "
            f"{row['journeys']:>3} journeys  {row['guides']:>3} guides"
        )
    print()
    print(
        f"  content packs: {overview['packs']['installed']} installed "
        f"of {overview['packs']['available']} in the catalog"
    )
    return 0


# --- doctor -----------------------------------------------------------------


def _doctor_checks() -> list[dict]:
    """Build the integration health rows (mirrors Admin → Integrations).

    Each row: ``name``, ``status`` (one of ok/warn/off/fail), and ``detail``.
    Optional integrations being off is reported as ``off`` (informational), not
    a failure — horizon is designed to run with all of them disabled.
    """
    from horizon.web.admin import admin_enabled

    rows: list[dict] = []

    # Database — the one hard requirement: the metadata store must be readable.
    try:
        stats = _content_stats()
        if stats["journeys_total"] == 0:
            rows.append(
                {
                    "name": "Database",
                    "status": _WARN,
                    "detail": f"{settings.database} (no journeys — run `horizon-admin seed`)",
                }
            )
        else:
            rows.append(
                {
                    "name": "Database",
                    "status": _OK,
                    "detail": f"{settings.database} ({stats['journeys_total']} journeys, "
                    f"{stats['guides_total']} guides)",
                }
            )
    except Exception as exc:  # noqa: BLE001
        rows.append({"name": "Database", "status": _FAIL, "detail": str(exc)})

    # Content directory on disk.
    from pathlib import Path

    content_dir = Path(settings.content_dir)
    guides_dir = content_dir / "guides"
    n_guide_files = len(list(guides_dir.glob("*.md"))) if guides_dir.is_dir() else 0
    if n_guide_files:
        rows.append(
            {
                "name": "Content files",
                "status": _OK,
                "detail": f"{content_dir} ({n_guide_files} guide files)",
            }
        )
    else:
        rows.append(
            {
                "name": "Content files",
                "status": _WARN,
                "detail": f"{content_dir} (no guide markdown found — seed not run yet?)",
            }
        )

    low_power = low_power_enabled()

    # Chat assistant (optional, on by default).
    rows.append(
        {
            "name": "Chat assistant",
            "status": _OK if assistant_enabled() else _OFF,
            "detail": "config assistant.enabled · env HORIZON_ASSISTANT_ENABLED",
        }
    )

    # Low-power mode (optional, off by default).
    rows.append(
        {
            "name": "Low-power mode",
            "status": _OK if low_power else _OFF,
            "detail": "config power.low_power · env HORIZON_LOW_POWER",
        }
    )

    # Local model runtime. When low-power mode is on, horizon never reaches for
    # the model, so we don't probe it (the network call costs energy on a weak
    # supply) — report it as paused rather than unreachable.
    if low_power:
        rows.append(
            {
                "name": "Local model runtime",
                "status": _OFF,
                "detail": f"paused for low power "
                f"({settings.llm.provider} · {settings.llm.endpoint})",
            }
        )
    else:
        from horizon.services import llm

        reachable = llm.available()
        rows.append(
            {
                "name": "Local model runtime",
                "status": _OK if reachable else _WARN,
                "detail": f"{settings.llm.provider} · {settings.llm.endpoint} "
                + (
                    "(reachable)"
                    if reachable
                    else "(unreachable — assistant falls back to keyword search)"
                ),
            }
        )

    # moral-core ethics hook (optional, off by default, always fails open).
    rows.append(
        {
            "name": "moral-core ethics hook",
            "status": _OK if settings.ethics.enabled else _OFF,
            "detail": settings.ethics.endpoint,
        }
    )

    # Web UI (optional now that the CLI is a full interface; on by default).
    rows.append(
        {
            "name": "Web UI",
            "status": _OK if web_enabled() else _OFF,
            "detail": "config web.enabled · env HORIZON_WEB_ENABLED"
            + ("" if web_enabled() else " (off — JSON API + CLI only)"),
        }
    )

    # Admin web area (token-gated; on by default via an auto-generated token
    # when admin.token / HORIZON_ADMIN_TOKEN aren't set).
    rows.append(
        {
            "name": "Admin web area",
            "status": _OK if (web_enabled() and admin_enabled()) else _OFF,
            "detail": "config admin.token · env HORIZON_ADMIN_TOKEN"
            + ("" if web_enabled() else " (web UI off)"),
        }
    )

    # Content packs.
    from horizon.services import packs

    installed = len(packs.installed_packs())
    available = len(packs.load_catalog())
    rows.append(
        {
            "name": "Content packs",
            "status": _OK if installed else _OFF,
            "detail": f"{installed} of {available} installed · {settings.content_packs.dir}",
        }
    )

    return rows


def cmd_doctor(args: argparse.Namespace) -> int:
    """Run integration health checks. Exit non-zero only on a hard failure."""
    rows = _doctor_checks()

    if args.json:
        _emit({"checks": rows}, as_json=True)
    else:
        if not args.no_logo:
            print(_banner())
        width = max(len(r["name"]) for r in rows)
        for row in rows:
            print(f"  [{row['status']:^4}] {row['name']:<{width}}  {row['detail']}")
        print()

    failed = [r for r in rows if r["status"] == _FAIL]
    if failed:
        if not args.json:
            print(
                f"{len(failed)} check(s) failed. horizon needs a readable database to run.",
                file=sys.stderr,
            )
        return 1
    if not args.json:
        print("No hard failures. Items marked 'off' are optional and disabled by choice.")
    return 0


# --- reindex ----------------------------------------------------------------


def cmd_reindex(args: argparse.Namespace) -> int:
    """Rebuild the vector index from guides + md skills on disk."""
    # Surface the service's own progress logs so the operator sees what happened
    # (e.g. "embedding model unavailable; keyword fallback").
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        stream=sys.stderr,
    )
    from horizon.services.rag import reindex_content

    print("Rebuilding the vector index from local content...")
    reindex_content()
    print(
        "Done. If the embedding model was unavailable the index was skipped and "
        "the assistant will use offline keyword search until you reindex with the "
        "model running."
    )
    return 0


# --- seed -------------------------------------------------------------------


def cmd_seed(args: argparse.Namespace) -> int:
    """Create tables and load bundled content (``--force`` re-seeds a populated db)."""
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    from horizon.db import init_db

    init_db()

    if args.force:
        # Re-seed from disk even when populated — the headless twin of the admin
        # panel's "Re-seed content" repair.
        from horizon.seed import reseed

        summary = reseed()
        print(
            f"Re-seeded the database from content on disk: "
            f"{summary['after']['journeys']} journeys, {summary['after']['guides']} guides."
        )
        return 0

    from horizon.seed import seed_if_empty

    before = _content_stats()["journeys_total"]
    seed_if_empty()
    after = _content_stats()["journeys_total"]

    if after > before:
        print(f"Seeded the database: {after} journeys now present.")
    else:
        print(
            f"Database already populated ({after} journeys); nothing to seed. "
            f"Use `horizon-admin seed --force` to re-seed from disk."
        )
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """Run content-health diagnostics (the headless Admin → Check & repair).

    Exit non-zero on a hard failure (a ``fail`` check), like ``doctor``; warnings
    are reported but do not fail the command.
    """
    from horizon.services.diagnostics import run_checks

    report = run_checks(check_model=args.check_model)

    if args.json:
        _emit(report, as_json=True)
        return 1 if not report["healthy"] else 0

    if not args.no_logo:
        print(_banner())

    width = max(len(c["name"]) for c in report["checks"])
    for c in report["checks"]:
        print(f"  [{c['status']:^4}] {c['name']:<{width}}  {c['summary']}")
        for detail in c["details"]:
            print(f"           - {detail}")
    print()
    counts = report["counts"]
    print(
        f"  {counts['ok']} ok, {counts['warn']} warn, {counts['fail']} fail, {counts['off']} off."
    )
    if not report["healthy"]:
        print(
            "  Some checks failed. Try `horizon-admin seed --force` and `horizon-admin reindex`.",
            file=sys.stderr,
        )
        return 1
    if report["problems"]:
        print("  No hard failures, but some items are worth a look (see 'warn' above).")
    else:
        print("  This node looks healthy.")
    return 0


# --- packs ------------------------------------------------------------------


def cmd_packs_list(args: argparse.Namespace) -> int:
    """List installed and available content packs."""
    from horizon.services.packs import human_size, pack_status

    rows = pack_status()
    if not rows:
        print("No content packs in the catalog.")
        return 0
    width = max(len(r["id"]) for r in rows)
    print(f"{'PACK':<{width}}  STATUS      SIZE       TITLE")
    for row in rows:
        status = "installed" if row["installed"] else "available"
        size = human_size(row.get("installed_size") or row.get("size_bytes"))
        print(f"{row['id']:<{width}}  {status:<10}  {size:<9}  {row['title']}")
    return 0


def cmd_packs_download(args: argparse.Namespace) -> int:
    """Download and install a content pack by name (the only networked command)."""
    from horizon.services.packs import (
        PackError,
        download_pack,
        get_spec,
        human_size,
        read_manifest,
    )

    spec = get_spec(args.name)
    if spec is None:
        print(
            f"Unknown pack: {args.name!r}. Run `horizon-admin packs list`.",
            file=sys.stderr,
        )
        return 2
    if read_manifest(args.name) is not None and not args.force:
        print(f"Pack {args.name!r} is already installed. Use --force to re-download.")
        return 0

    print(f"Downloading {spec.title} ({human_size(spec.size_bytes)}) from {spec.url}")

    def progress(done: int, total: int | None, phase: str) -> None:
        if phase == "downloading" and total:
            pct = 100 * done / total
            print(f"\r  {pct:5.1f}%  {human_size(done)} / {human_size(total)}", end="", flush=True)
        elif phase == "verifying":
            print("\r  verifying checksum...", end="", flush=True)

    try:
        manifest = download_pack(args.name, progress_cb=progress)
    except PackError as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        return 1
    print(f"\nInstalled {manifest['id']} ({human_size(manifest['size_bytes'])}).")
    return 0


def cmd_packs_remove(args: argparse.Namespace) -> int:
    """Remove an installed content pack."""
    from horizon.services.packs import remove_pack

    if remove_pack(args.name):
        print(f"Removed {args.name}.")
        return 0
    print(f"Pack {args.name!r} is not installed.", file=sys.stderr)
    return 1


# --- config -----------------------------------------------------------------

# Keys whose values must never be printed — the admin token is a shared secret.
_SECRET_KEYS = {"token"}


def _redact(value: Any, key: str = "") -> Any:
    """Recursively blank out secret-bearing keys for safe display."""
    if isinstance(value, dict):
        return {k: _redact(v, k) for k, v in value.items()}
    if key in _SECRET_KEYS and value:
        return "***set (hidden)***"
    return value


def cmd_config(args: argparse.Namespace) -> int:
    """Print the effective configuration, with secrets redacted."""
    from horizon.web.admin import admin_enabled

    data = _redact(settings.model_dump())
    # Reflect the live env overrides so the operator sees the *effective* state,
    # not just what config.yaml says.
    data["_effective"] = {
        "web_enabled": web_enabled(),
        "low_power": low_power_enabled(),
        "assistant_enabled": assistant_enabled(),
        "admin_enabled": admin_enabled(),
        "config_path": os.environ.get("HORIZON_CONFIG", "config.yaml"),
    }

    if args.json:
        _emit(data, as_json=True)
        return 0

    import yaml

    print(yaml.safe_dump(data, sort_keys=False, default_flow_style=False).rstrip())
    return 0


# --- Content browsing (text + simple ASCII graphics) ------------------------
#
# These make horizon usable straight from a terminal — no browser, no network.
# Everything renders in plain ASCII so it is legible over a serial console or on
# an e-ink screen, the same low-power audiences the web UI is built for.


def _term_width(cap: int = 100) -> int:
    """Usable line width: the terminal's, clamped so long lines stay readable."""
    import shutil

    return min(shutil.get_terminal_size((80, 24)).columns, cap)


def _wrap(text: str, indent: str = "  ") -> str:
    """Wrap a paragraph to the terminal width with a hanging indent."""
    import textwrap

    text = " ".join((text or "").split())
    if not text:
        return ""
    return textwrap.fill(
        text,
        width=_term_width(),
        initial_indent=indent,
        subsequent_indent=indent,
    )


def _heading(text: str) -> str:
    """An underlined section heading."""
    return f"{text}\n{'=' * max(len(text), 8)}"


def _difficulty_bar(level: int) -> str:
    """Render a 1–5 difficulty as an ASCII meter, e.g. ``[##---] 2/5``."""
    level = max(1, min(5, int(level)))
    return f"[{'#' * level}{'-' * (5 - level)}] {level}/5"


def _validate_category(category: str | None) -> int | None:
    """Return 2 (and print) if ``category`` is set but unknown, else ``None``."""
    from horizon.models import Category

    if category is not None and category not in set(Category):
        valid = ", ".join(c.value for c in Category)
        print(f"Unknown category: {category!r}. Choose one of: {valid}.", file=sys.stderr)
        return 2
    return None


def cmd_journeys(args: argparse.Namespace) -> int:
    """List step-by-step plans (journeys), grouped by category."""
    if (rc := _validate_category(args.category)) is not None:
        return rc

    from sqlmodel import Session, select

    from horizon.db import engine
    from horizon.models import Category, Journey

    with Session(engine) as session:
        statement = select(Journey)
        if args.category:
            statement = statement.where(Journey.category == Category(args.category))
        statement = statement.order_by(Journey.category, Journey.difficulty, Journey.id)
        journeys = session.exec(statement).all()
        rows = [
            {
                "id": j.id,
                "title": j.title,
                "category": j.category.value,
                "difficulty": j.difficulty,
                "estimated_time": j.estimated_time,
            }
            for j in journeys
        ]

    if args.json:
        _emit({"journeys": rows}, as_json=True)
        return 0

    if not rows:
        print("No plans found. Run `horizon-admin seed` to load bundled content.")
        return 0

    current = None
    for row in rows:
        if row["category"] != current:
            current = row["category"]
            print()
            print(_heading(current.upper()))
        print(f"  - {row['title']}  ({row['id']})")
        meta = f"      {_difficulty_bar(row['difficulty'])}"
        if row["estimated_time"]:
            meta += f" - {row['estimated_time']}"
        print(meta)
    print()
    print("  See a plan in full:  horizon-admin journey <id>")
    return 0


def cmd_journey(args: argparse.Namespace) -> int:
    """Show one plan in full: its metadata and its ordered guides."""
    from sqlmodel import Session

    from horizon.api.journeys import ordered_guides
    from horizon.db import engine
    from horizon.models import Journey

    with Session(engine) as session:
        journey = session.get(Journey, args.id)
        if journey is None:
            print(f"Plan not found: {args.id!r}. Try `horizon-admin journeys`.", file=sys.stderr)
            return 1

        data = {
            "id": journey.id,
            "title": journey.title,
            "description": journey.description,
            "category": journey.category.value,
            "difficulty": journey.difficulty,
            "estimated_time": journey.estimated_time,
            "guides": [{"id": g.id, "title": g.title} for g in ordered_guides(session, journey.id)],
        }

    if args.json:
        _emit(data, as_json=True)
        return 0

    print(_heading(data["title"]))
    print(f"  id          {data['id']}")
    print(f"  category    {data['category']}")
    print(f"  difficulty  {_difficulty_bar(data['difficulty'])}")
    if data["estimated_time"]:
        print(f"  time        {data['estimated_time']}")
    if data["description"]:
        print()
        print(_wrap(data["description"]))

    print()
    if data["guides"]:
        print("  Guides, in order")
        for i, g in enumerate(data["guides"], start=1):
            print(f"    {i}. {g['title']}  ({g['id']})")
        print()
        print("  Read a guide:  horizon-admin guide <id>")
    else:
        print("  (No guides linked to this plan yet.)")
    return 0


def cmd_guides(args: argparse.Namespace) -> int:
    """List how-to guides, optionally filtered by category and a search term."""
    if (rc := _validate_category(args.category)) is not None:
        return rc

    from sqlmodel import Session, select

    from horizon.db import engine
    from horizon.models import Category, Guide

    with Session(engine) as session:
        statement = select(Guide)
        if args.category:
            statement = statement.where(Guide.category == Category(args.category))
        statement = statement.order_by(Guide.category, Guide.id)
        guides = session.exec(statement).all()

    needle = (args.search or "").strip().lower()
    rows = [
        {"id": g.id, "title": g.title, "category": g.category.value, "summary": g.summary}
        for g in guides
        if not needle or needle in g.title.lower() or needle in (g.summary or "").lower()
    ]

    if args.json:
        _emit({"guides": rows}, as_json=True)
        return 0

    if not rows:
        print("No matching guides.")
        return 0

    current = None
    for row in rows:
        if row["category"] != current:
            current = row["category"]
            print()
            print(_heading(current.upper()))
        print(f"  - {row['title']}  ({row['id']})")
        if row["summary"]:
            print(_wrap(row["summary"], indent="      "))
    print()
    print("  Read a guide:  horizon-admin guide <id>")
    return 0


def _markdown_to_text(body: str) -> str:
    """Lightly format Markdown for a terminal: headings stand out, body intact.

    Conservative on purpose — lists, tables, and code blocks are passed through
    untouched so nothing is mangled; only ATX headings get visual emphasis. The
    one other special case is a ` ```ascii ` diagram fence (see
    ``services.markdown._wrap_ascii_diagrams``): the fence markers are dropped
    (the art is the point, not the code-block noise around it) and a trailing
    ``*caption*`` line is unwrapped, so the diagrams that already read fine in
    raw Markdown stand out clearly in the CLI too.
    """
    out: list[str] = []
    lines = body.splitlines()
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.lstrip()
        if stripped.strip().lower() == "```ascii":
            i += 1
            diagram: list[str] = []
            while i < n and lines[i].strip() != "```":
                diagram.append(lines[i])
                i += 1
            i += 1  # skip the closing fence
            out += ["", *diagram]
            j = i
            while j < n and not lines[j].strip():
                j += 1
            caption_line = lines[j].strip() if j < n else ""
            if (
                len(caption_line) > 1
                and caption_line.startswith("*")
                and caption_line.endswith("*")
            ):
                out += ["", f"  ({caption_line.strip('*').strip()})"]
                i = j + 1
            continue
        if stripped.startswith("# "):
            title = stripped[2:].strip()
            out += ["", title.upper(), "=" * max(len(title), 8)]
        elif stripped.startswith("## "):
            title = stripped[3:].strip()
            out += ["", title, "-" * max(len(title), 8)]
        elif stripped.startswith("### "):
            out += ["", f">> {stripped[4:].strip()}"]
        else:
            out.append(line)
        i += 1
    return "\n".join(out).strip("\n")


def cmd_guide(args: argparse.Namespace) -> int:
    """Print a guide rendered as readable terminal text (``--raw`` for Markdown)."""
    from pathlib import Path

    from sqlmodel import Session

    from horizon.db import engine
    from horizon.models import Guide

    with Session(engine) as session:
        guide = session.get(Guide, args.id)
        if guide is None:
            print(f"Guide not found: {args.id!r}. Try `horizon-admin guides`.", file=sys.stderr)
            return 1
        title = guide.title
        category = guide.category.value
        path = Path(settings.content_dir) / "guides" / guide.path

    if not path.is_file():
        print(f"Guide file missing on disk: {path}", file=sys.stderr)
        return 1

    # Strip the YAML front matter; the metadata is shown in the header instead.
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            text = parts[2].lstrip("\n")

    if args.raw:
        print(text)
        return 0

    print(_heading(title))
    print(f"  category: {category} · id: {args.id}")
    print()
    print(_markdown_to_text(text))
    return 0


def cmd_recommend(args: argparse.Namespace) -> int:
    """Suggest journeys + guides for a free-text goal (offline keyword matching)."""
    from horizon.services.recommend import recommend_journeys

    goal = " ".join(args.goal).strip()
    if not goal:
        print("Tell me your goal, e.g. `horizon-admin recommend safe drinking water`.")
        return 2

    result = recommend_journeys(
        goal,
        people=args.people,
        climate=args.climate,
        resources=args.resource or None,
    )

    if args.json:
        _emit(result, as_json=True)
        return 0

    print(_heading(f'Where to start: "{goal}"'))
    journeys = result.get("journeys", [])
    guides = result.get("guides", [])
    if not journeys and not guides:
        print("  No close matches. Browse everything with `horizon-admin journeys`.")
        return 0

    if journeys:
        print()
        print("  Suggested plans")
        for j in journeys:
            print(f"    - {j['title']}  ({j['id']})  {_difficulty_bar(j['difficulty'])}")
    if guides:
        print()
        print("  Related guides")
        for g in guides:
            print(f"    - {g['title']}  ({g['id']})")
    print()
    print("  Open one:  horizon-admin journey <id>   /   horizon-admin guide <id>")
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    """Ask the local assistant a question (cited, offline-capable answer)."""
    from horizon.api.ai import AnswerRequest, answer

    question = " ".join(args.question).strip()
    if not question:
        print("Ask a question, e.g. `horizon-admin ask how do I store rainwater`.")
        return 2

    result = answer(AnswerRequest(question=question, no_jargon=args.no_jargon))

    if args.json:
        _emit({"answer": result.answer, "citations": result.citations}, as_json=True)
        return 0

    print(_heading("Answer"))
    print()
    print(_markdown_to_text(result.answer))
    if result.citations:
        print()
        print("  Sources (local guides)")
        from sqlmodel import Session

        from horizon.db import engine
        from horizon.models import Guide

        with Session(engine) as session:
            for cid in result.citations:
                guide = session.get(Guide, cid)
                label = f"{guide.title}  ({cid})" if guide is not None else cid
                print(f"    - {label}")
    return 0


# --- Parser -----------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="horizon-admin",
        description="Headless operator tooling for a horizon node.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"horizon-admin {__version__}",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="Runtime + content overview.")
    p_status.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    p_status.add_argument("--no-logo", action="store_true", help="Skip the ASCII banner.")
    p_status.set_defaults(func=cmd_status)

    p_doctor = sub.add_parser("doctor", help="Health-check optional integrations.")
    p_doctor.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    p_doctor.add_argument("--no-logo", action="store_true", help="Skip the ASCII banner.")
    p_doctor.set_defaults(func=cmd_doctor)

    p_reindex = sub.add_parser("reindex", help="Rebuild the vector index from content.")
    p_reindex.set_defaults(func=cmd_reindex)

    p_seed = sub.add_parser("seed", help="Seed the database from bundled content if empty.")
    p_seed.add_argument(
        "--force",
        action="store_true",
        help="Re-seed from disk even if the database is already populated.",
    )
    p_seed.set_defaults(func=cmd_seed)

    p_check = sub.add_parser("check", help="Content-health diagnostics (links, files, index).")
    p_check.add_argument(
        "--check-model",
        action="store_true",
        help="Also probe the local model runtime (a network call that costs energy).",
    )
    p_check.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    p_check.add_argument("--no-logo", action="store_true", help="Skip the ASCII banner.")
    p_check.set_defaults(func=cmd_check)

    p_config = sub.add_parser("config", help="Print the effective configuration (no secrets).")
    p_config.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    p_config.set_defaults(func=cmd_config)

    p_journeys = sub.add_parser("journeys", help="List step-by-step plans (journeys).")
    p_journeys.add_argument("--category", help="Filter by category (water, food, ...).")
    p_journeys.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    p_journeys.set_defaults(func=cmd_journeys)

    p_journey = sub.add_parser("journey", help="Show one plan in full (ordered guides).")
    p_journey.add_argument("id", help="Journey identifier.")
    p_journey.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    p_journey.set_defaults(func=cmd_journey)

    p_guides = sub.add_parser("guides", help="List how-to guides.")
    p_guides.add_argument("--category", help="Filter by category (water, food, ...).")
    p_guides.add_argument("--search", help="Filter by a word in the title or summary.")
    p_guides.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    p_guides.set_defaults(func=cmd_guides)

    p_guide = sub.add_parser("guide", help="Print a guide as readable terminal text.")
    p_guide.add_argument("id", help="Guide identifier.")
    p_guide.add_argument("--raw", action="store_true", help="Print the raw Markdown source.")
    p_guide.set_defaults(func=cmd_guide)

    p_rec = sub.add_parser("recommend", help="Suggest where to start for a goal.")
    p_rec.add_argument("goal", nargs="+", help="Free-text goal, e.g. safe drinking water.")
    p_rec.add_argument("--people", type=int, help="Group size (informational).")
    p_rec.add_argument("--climate", help="Climate hint folded into matching.")
    p_rec.add_argument("--resource", action="append", help="A resource on hand (repeatable).")
    p_rec.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    p_rec.set_defaults(func=cmd_recommend)

    p_ask = sub.add_parser("ask", help="Ask the local assistant a question.")
    p_ask.add_argument("question", nargs="+", help="Your question.")
    p_ask.add_argument("--no-jargon", action="store_true", help="Force plain-language wording.")
    p_ask.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    p_ask.set_defaults(func=cmd_ask)

    p_packs = sub.add_parser("packs", help="Manage offline content packs.")
    packs_sub = p_packs.add_subparsers(dest="packs_command", required=True)

    pl = packs_sub.add_parser("list", help="List installed/available packs.")
    pl.set_defaults(func=cmd_packs_list)

    pd = packs_sub.add_parser("download", help="Download and install a pack.")
    pd.add_argument("name", help="Pack identifier (e.g. wikipedia-en-mini).")
    pd.add_argument("--force", action="store_true", help="Re-download even if already installed.")
    pd.set_defaults(func=cmd_packs_download)

    pr = packs_sub.add_parser("remove", help="Remove an installed pack.")
    pr.add_argument("name", help="Pack identifier to remove.")
    pr.set_defaults(func=cmd_packs_remove)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
