"""Optional moral-core ethics hook tests.

The hook must be opt-in and must always fail open: a disabled, unreachable, or
misbehaving moral-core never alters or blocks horizon's own answer beyond the
documented decisions.
"""

from __future__ import annotations

import httpx
import pytest

from horizon.config import settings
from horizon.services import ethics

DRAFT = "Boil the water for one minute. [water-slow-sand-filter]"


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(settings.ethics, "enabled", True)


def test_disabled_passes_through(monkeypatch):
    monkeypatch.setattr(settings.ethics, "enabled", False)
    assert ethics.refine_answer(DRAFT) == DRAFT


def test_approve_returns_draft(enabled, monkeypatch):
    monkeypatch.setattr(ethics, "_evaluate", lambda a, c: {"decision": "approve"})
    assert ethics.refine_answer(DRAFT) == DRAFT


def test_adjust_returns_refined(enabled, monkeypatch):
    monkeypatch.setattr(
        ethics, "_evaluate", lambda a, c: {"decision": "adjust", "answer": "Refined."}
    )
    assert ethics.refine_answer(DRAFT) == "Refined."


def test_adjust_without_answer_falls_back_to_draft(enabled, monkeypatch):
    monkeypatch.setattr(ethics, "_evaluate", lambda a, c: {"decision": "adjust", "answer": ""})
    assert ethics.refine_answer(DRAFT) == DRAFT


def test_block_returns_refusal_with_reason(enabled, monkeypatch):
    monkeypatch.setattr(ethics, "_evaluate", lambda a, c: {"decision": "block", "reason": "unsafe"})
    out = ethics.refine_answer(DRAFT)
    assert out.startswith(ethics._BLOCK_PREFIX)
    assert "unsafe" in out


def test_unreachable_fails_open(enabled, monkeypatch):
    def boom(a, c):
        raise httpx.ConnectError("no route")

    monkeypatch.setattr(ethics, "_evaluate", boom)
    assert ethics.refine_answer(DRAFT) == DRAFT


def test_garbage_response_fails_open(enabled, monkeypatch):
    def boom(a, c):
        raise ValueError("not a dict")

    monkeypatch.setattr(ethics, "_evaluate", boom)
    assert ethics.refine_answer(DRAFT) == DRAFT
