"""ASCII topic emblems — the small three-line mark each topic is drawn with.

They replace the old inline-SVG category icons and the index-card tabs: the
same monospace craft as the guides' ASCII diagrams, so a topic looks like
something drawn in the guide itself rather than a stock icon. Each emblem is
at most three lines of at most eight columns, inked in the topic's own colour
(``[data-cat]`` / ``--cat`` in ``app.css``) and always ``aria-hidden`` — the
topic's name sits next to it in plain text.

Adding a category means adding its emblem here (``tests/test_ui_pages.py``
fails on a category without one).
"""

from __future__ import annotations

TOPIC_EMBLEMS: dict[str, str] = {
    "water": "  .\n / \\\n \\_/",
    "food": "\\|/\n |\n_|_",
    "energy": "\\ | /\n- o -\n/ | \\",
    "shelter": " /\\\n/  \\\n|[]|",
    "health": "  |\n--+--\n  |",
    "cooperation": " o o\no   o\n o o",
    "survival": "  N\nW-+-E\n  S",
    "culture": " __\n|  |\no  o",
    "language": ".---.\n| ab|\n'-v-'",
    "crafts": "\\ /\n X\n/ \\",
    "emergencies": "  /\\\n /! \\\n/____\\",
    "cooking": " ) )\n.---.\n'---'",
    "calculations": "1 2 3\n-----\n  = 6",
    "technology": "((o))\n  |\n /_\\",
    "mobility": "   __o\n _`\\<,_\n(_)/ (_)",
}

# A neutral fallback for anything unexpected (never shown for a real category).
_FALLBACK = " .-.\n( o )\n '-'"


def topic_emblem(category: str) -> str:
    """The ASCII emblem for ``category`` (a plain-text, multi-line string)."""
    return TOPIC_EMBLEMS.get(category, _FALLBACK)
