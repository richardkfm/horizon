"""Render guide Markdown to HTML for the web UI.

Pure, offline rendering with ``markdown-it-py`` — no network, no LLM. Guides on
disk carry YAML front matter (``id``/``title``/``category``/``summary``); the
helpers here strip that block before rendering so only the body becomes HTML.
"""

from __future__ import annotations

from functools import lru_cache

from markdown_it import MarkdownIt


@lru_cache(maxsize=1)
def _parser() -> MarkdownIt:
    """Return a shared CommonMark parser with GFM tables enabled."""
    return MarkdownIt("commonmark").enable("table")


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
