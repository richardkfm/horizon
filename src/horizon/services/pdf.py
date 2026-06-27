"""Render guides to A4-friendly PDF for print mode (via WeasyPrint).

Pure, offline rendering: a guide's HTML is paired with the shared print
stylesheet (``web/static/print.css``) to produce a minimal, high-contrast A4
document. WeasyPrint pulls in system libraries (cairo/pango), so this module is
imported lazily by the PDF route — the rest of the app boots and serves the UI
even where those libraries are absent.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from weasyprint import CSS, HTML

_PRINT_CSS = Path(__file__).resolve().parent.parent / "web" / "static" / "print.css"


@lru_cache(maxsize=1)
def _stylesheet() -> CSS:
    """Return the shared print stylesheet, parsed once and reused."""
    return CSS(filename=str(_PRINT_CSS))


def render_pdf(html: str) -> bytes:
    """Render a standalone HTML document to a minimal, high-contrast, A4 PDF."""
    return HTML(string=html).write_pdf(stylesheets=[_stylesheet()])
