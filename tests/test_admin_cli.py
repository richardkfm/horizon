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
