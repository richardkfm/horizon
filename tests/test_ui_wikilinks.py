"""Content check: every ``[[...]]`` cross-reference in the shipped content resolves.

Scans the bundled guides, checklists, and plan descriptions (not code spans or
fenced blocks, where ``[[`` is left alone by the renderer) and asserts each
target id exists, so a renamed guide can't silently leave plain-text "links"
behind.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from horizon.services.markdown import _WIKILINK

CONTENT = Path(__file__).resolve().parent.parent / "content"

# Any [[...]] at all, so a malformed reference fails loudly too.
_ANY_WIKILINK = re.compile(r"\[\[([^\]\n]*)\]\]")
_FENCE = re.compile(r"^(```|~~~).*?^\1", re.MULTILINE | re.DOTALL)
_CODE_SPAN = re.compile(r"(`+)(?!`).*?(?<!`)\1(?!`)", re.DOTALL)


def _front_matter_id(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        meta = yaml.safe_load(text.split("---", 2)[1]) or {}
        if meta.get("id"):
            return str(meta["id"])
    return path.stem


def _known_ids() -> dict[str, set[str]]:
    journeys = yaml.safe_load((CONTENT / "journeys.yaml").read_text(encoding="utf-8"))
    return {
        "guide": {_front_matter_id(p) for p in (CONTENT / "guides").glob("*.md")},
        "checklist": {_front_matter_id(p) for p in (CONTENT / "checklists").glob("*.md")},
        "plan": {j["id"] for j in journeys.get("journeys", [])},
    }


def _sources() -> list[tuple[str, str]]:
    sources = [
        (str(p.relative_to(CONTENT)), p.read_text(encoding="utf-8"))
        for folder in ("guides", "checklists")
        for p in sorted((CONTENT / folder).glob("*.md"))
    ]
    journeys = yaml.safe_load((CONTENT / "journeys.yaml").read_text(encoding="utf-8"))
    for j in journeys.get("journeys", []):
        sources.append((f"journeys.yaml:{j['id']}", j.get("description") or ""))
    return sources


def _strip_code(text: str) -> str:
    return _CODE_SPAN.sub("", _FENCE.sub("", text))


def test_every_wikilink_resolves():
    known = _known_ids()
    problems: list[str] = []
    for name, text in _sources():
        for match in _ANY_WIKILINK.finditer(_strip_code(text)):
            ref = match.group(0)
            parsed = _WIKILINK.fullmatch(ref)
            if parsed is None:
                problems.append(f"{name}: malformed {ref}")
                continue
            kind = {"journey": "plan", None: "guide"}.get(parsed.group(1), parsed.group(1))
            if parsed.group(2) not in known[kind]:
                problems.append(f"{name}: unknown {kind} in {ref}")
    assert not problems, "\n".join(problems)


def test_known_ids_are_found():
    # Guard against the scan silently finding nothing (e.g. a moved folder).
    known = _known_ids()
    assert "survival-knots" in known["guide"]
    assert "go-bag" in known["checklist"]
    assert "safe-drinking-water" in known["plan"]
