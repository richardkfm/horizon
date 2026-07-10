"""``horizon-admin`` CLI tests.

The CLI is the headless equivalent of the admin web area; these tests exercise
each subcommand against the hermetic temp data dir set up in ``conftest.py``.
The network is never touched (no ``packs download`` here), and the local model
runtime is stubbed so ``doctor`` does not depend on a running Ollama.
"""

from __future__ import annotations

import json

import pytest

from horizon.db import init_db
from horizon.scripts import admin as cli
from horizon.seed import seed_if_empty
from horizon.services import llm


@pytest.fixture
def seeded():
    """Ensure the database is initialised and seeded for content-dependent commands."""
    init_db()
    seed_if_empty()


@pytest.fixture(autouse=True)
def offline_llm(monkeypatch):
    """Pretend the local model runtime is unreachable so doctor stays offline."""
    monkeypatch.setattr(llm, "available", lambda: False)


def test_banner_includes_wordmark_and_version():
    banner = cli._banner()
    assert "HORIZON" not in banner  # it is ASCII-art, not literal text...
    assert "autonomy & rebuilding node" in banner
    assert cli.__version__ in banner


def test_banner_wordmark_glyph_columns_are_aligned():
    # The block-letter wordmark is figlet-style ASCII art: the glyph columns in
    # each row must line up with the rows above/below it, or "HORIZON" reads as
    # a garbled mess instead of letters (this broke once before -- the rows had
    # drifted to different lengths). Verify each row's underscores/pipes/slashes
    # fall in the same columns as a known-correct reference render.
    lines = cli._LOGO.splitlines()
    glyph_lines = [ln for ln in lines if set(ln) <= set(" _|\\/<>()") and ln.strip()]
    reference = [
        "   _   _  ___  ____  ___ ________  _   _",
        "  | | | |/ _ \\|  _ \\|_ _|__  / _ \\| \\ | |",
        "  | |_| | | | | |_) || |  / / | | |  \\| |",
        "  |  _  | |_| |  _ < | | / /| |_| | |\\  |",
        "  |_| |_|\\___/|_| \\_\\___/____\\___/|_| \\_|",
    ]
    assert glyph_lines == reference


def test_status_human_output(seeded, capsys):
    assert cli.main(["status", "--no-logo"]) == 0
    out = capsys.readouterr().out
    assert "horizon" in out
    assert "journeys" in out
    assert "content packs" in out


def test_status_json(seeded, capsys):
    assert cli.main(["status", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["version"] == cli.__version__
    assert payload["database_ok"] is True
    assert payload["content"]["journeys_total"] > 0
    assert "per_category" in payload["content"]


def test_doctor_reports_offline_model_without_failing(seeded, capsys):
    # An unreachable model is a warning, not a hard failure: exit code stays 0.
    assert cli.main(["doctor", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    names = {row["name"]: row["status"] for row in payload["checks"]}
    assert names["Database"] == "ok"
    assert names["Local model runtime"] == "warn"


def test_seed_is_idempotent(capsys):
    assert cli.main(["seed"]) == 0
    first = capsys.readouterr().out
    assert "journeys" in first
    assert cli.main(["seed"]) == 0
    second = capsys.readouterr().out
    assert "already populated" in second


def test_config_redacts_admin_token(monkeypatch, capsys):
    monkeypatch.setenv("HORIZON_ADMIN_TOKEN", "super-secret")
    assert cli.main(["config", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["admin"]["token"] in ("", "***set (hidden)***")
    assert "super-secret" not in json.dumps(payload)
    assert payload["_effective"]["admin_enabled"] is True


def test_packs_list_empty(capsys):
    assert cli.main(["packs", "list"]) == 0
    # The hermetic temp content dir ships no packs.yaml, so the catalog is empty.
    out = capsys.readouterr().out
    assert "content packs" in out.lower() or "PACK" in out


def test_check_reports_healthy_node(seeded, capsys):
    # A freshly seeded node has no hard failures: exit code 0.
    assert cli.main(["check", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["healthy"] is True
    ids = {c["id"] for c in payload["checks"]}
    assert {"database", "guide_files", "search_index"} <= ids


def test_check_human_output(seeded, capsys):
    assert cli.main(["check", "--no-logo"]) == 0
    out = capsys.readouterr().out
    assert "Database" in out
    assert "ok" in out


def test_seed_force_reseeds_populated_db(seeded, capsys):
    assert cli.main(["seed", "--force"]) == 0
    out = capsys.readouterr().out
    assert "Re-seeded" in out


def test_guide_renders_ascii_diagrams_without_fence_noise(seeded, capsys):
    # The ASCII diagram convention (CLAUDE.md) exists precisely so guides read
    # correctly in a CLI with no rendering at all; `horizon-admin guide` should
    # show the art, not the ```ascii fence markers or literal caption asterisks.
    assert cli.main(["guide", "crafts-make-tools"]) == 0
    out = capsys.readouterr().out
    assert "```ascii" not in out
    assert "```" not in out
    assert "stone blade, ground to an edge" in out
    assert "(Fig. 1: hafting a stone blade" in out
    assert "(Fig. 2: fire-hardening a point" in out


def test_markdown_to_text_unwraps_ascii_fence_and_caption():
    body = "before\n\n```ascii\n+---+\n| A |\n+---+\n```\n\n*Fig. 1: a box*\n\nafter\n"
    out = cli._markdown_to_text(body)
    assert "```" not in out
    assert "+---+" in out
    assert "| A |" in out
    assert "(Fig. 1: a box)" in out
    assert "before" in out and "after" in out
