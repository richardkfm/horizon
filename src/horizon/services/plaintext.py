"""Plain-text helpers for content shown outside the HTML renderer.

Guides cross-link with a wiki-style syntax — ``[[guide-id]]``,
``[[guide-id|custom text]]``, ``[[plan:id]]``, ``[[checklist:id]]`` — which the
web renderer turns into links. Plain-text consumers (the ``horizon-admin
guide`` terminal view, the chunks fed to the assistant's model) have no links,
so they show the link's *words* instead: the custom text when given, otherwise
the target's title when the caller can resolve it, otherwise the id.

Pure: title lookup is injected by the caller, so this needs no database or
filesystem and is trivially unit-testable.
"""

from __future__ import annotations

import re
from collections.abc import Callable

# ``[[kind:id|text]]`` with ``kind:`` and ``|text`` optional. Ids are slugs, so
# no ``]``/``|`` inside; the text may hold anything but ``]``.
WIKI_LINK_RE = re.compile(
    r"\[\[\s*(?:(?P<kind>guide|plan|journey|checklist)\s*:\s*)?"
    r"(?P<id>[^\]|\n]+?)\s*(?:\|\s*(?P<text>[^\]\n]*?)\s*)?\]\]",
    re.IGNORECASE,
)

# (kind, id) -> title, or None when unknown. ``kind`` is "guide", "plan" or
# "checklist".
TitleResolver = Callable[[str, str], "str | None"]


def _kind(raw: str | None) -> str:
    kind = (raw or "guide").lower()
    return "plan" if kind == "journey" else kind


def wiki_links_to_text(text: str, resolve_title: TitleResolver | None = None) -> str:
    """Replace every wiki link in ``text`` with readable words."""
    if "[[" not in text:
        return text

    def replace(match: re.Match[str]) -> str:
        custom = match.group("text")
        if custom:
            return custom
        target = match.group("id").strip()
        if resolve_title is not None:
            try:
                title = resolve_title(_kind(match.group("kind")), target)
            except Exception:  # noqa: BLE001 - a lookup failure just falls back to the id
                title = None
            if title:
                return title
        return target

    return WIKI_LINK_RE.sub(replace, text)


def wiki_link_targets(text: str) -> list[tuple[str, str]]:
    """``(kind, id)`` for every wiki link in ``text``, in order."""
    return [(_kind(m.group("kind")), m.group("id").strip()) for m in WIKI_LINK_RE.finditer(text)]
