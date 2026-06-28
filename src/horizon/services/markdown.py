"""Render guide Markdown to HTML for the web UI.

Pure, offline rendering with ``markdown-it-py`` — no network, no LLM. Guides on
disk carry YAML front matter (``id``/``title``/``category``/``summary``); the
helpers here strip that block before rendering so only the body becomes HTML.

On top of CommonMark + GFM tables, guides can use **callouts** for the
"which should I pick?" content added in v0.3. A callout is just a normal
blockquote whose first line is a recognised **bold label** — e.g.::

    > **Pick this if:** your water is cloudy or from a river.

    > **Spec:** 60 cm sand bed, ~0.1 m/h flow.

The renderer tags such blockquotes with a ``callout callout-<kind>`` class so
the stylesheet can give them a distinct, scannable look (and print/e-ink keep
high contrast). Crucially this degrades gracefully: anywhere the class is not
styled — another renderer, a plain Markdown view — the callout is still a valid
blockquote with a bold label, so no meaning is lost and nothing breaks offline.
"""

from __future__ import annotations

from functools import lru_cache

from markdown_it import MarkdownIt
from markdown_it.token import Token

# Recognised callout labels → kind (the CSS modifier). Matched case-insensitively
# against the bold label that opens a blockquote, with any trailing colon
# stripped. Synonyms map to the same kind so guide authors can write naturally.
_CALLOUT_LABELS: dict[str, str] = {
    "pick this if": "pick",
    "choose this if": "pick",
    "good for": "pick",
    "avoid if": "avoid",
    "skip if": "avoid",
    "not for": "avoid",
    "spec": "spec",
    "specs": "spec",
    "at a glance": "spec",
    "decide": "decision",
    "decision": "decision",
    "rule of thumb": "decision",
    "risk": "risk",
    "warning": "risk",
    "caution": "risk",
    "tip": "tip",
    "note": "note",
}


def _callout_kind(label: str) -> str | None:
    """Map a blockquote's opening bold label to a callout kind, if recognised."""
    return _CALLOUT_LABELS.get(label.strip().rstrip(":").strip().lower())


def _tag_callouts(state) -> None:  # noqa: ANN001 - markdown-it core rule state
    """Core rule: class-tag blockquotes that open with a recognised bold label.

    Walks the block token stream and, for every ``blockquote_open`` whose first
    child paragraph starts with a ``strong`` run (a ``**Label**``), adds a
    ``callout callout-<kind>`` class when the label is one we know. Leaves every
    other blockquote untouched, so ordinary quotes render as before.
    """
    tokens: list[Token] = state.tokens
    for i, token in enumerate(tokens):
        if token.type != "blockquote_open":
            continue
        # blockquote_open → paragraph_open → inline (the first line's content).
        if i + 2 >= len(tokens):
            continue
        if tokens[i + 1].type != "paragraph_open":
            continue
        inline = tokens[i + 2]
        if inline.type != "inline" or not inline.children:
            continue
        # Skip a leading empty text child (markdown-it emits one before strong).
        children = [c for c in inline.children if not (c.type == "text" and not c.content)]
        # The line must open with a bold run: strong_open, text, strong_close.
        if len(children) < 3 or children[0].type != "strong_open":
            continue
        if children[1].type != "text":
            continue
        kind = _callout_kind(children[1].content)
        if kind is None:
            continue
        existing = token.attrGet("class")
        classes = f"{existing} callout callout-{kind}" if existing else f"callout callout-{kind}"
        token.attrSet("class", classes)


@lru_cache(maxsize=1)
def _parser() -> MarkdownIt:
    """Return a shared CommonMark parser with GFM tables and callouts enabled."""
    md = MarkdownIt("commonmark").enable("table")
    md.core.ruler.push("horizon_callouts", _tag_callouts)
    return md


def strip_front_matter(text: str) -> str:
    """Drop a leading ``---`` YAML front-matter block, returning the body.

    Mirrors the split in ``seed._split_front_matter`` but keeps this service free
    of any database/seed import so it stays pure and unit-testable.
    """
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            return parts[2].lstrip("\n")
    return text


def render_markdown(text: str) -> str:
    """Render Markdown to an HTML fragment, ignoring any front matter."""
    return _parser().render(strip_front_matter(text))
