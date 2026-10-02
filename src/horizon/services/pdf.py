"""Render guides to A4-friendly PDF for print mode (via WeasyPrint).

Pure, offline rendering: a guide's HTML is paired with the shared print
stylesheet (``web/static/print.css``) plus a small PDF-only colophon (the guide
title in the page header, "horizon · <title> · printed <date>" and a page
number in the footer) to produce a minimal, high-contrast A4 document.
WeasyPrint pulls in system libraries (cairo/pango), so this module is imported
lazily by the PDF route — the rest of the app boots and serves the UI even
where those libraries are absent.

Two safety properties matter because guide Markdown can come from imports:

* **No network, no arbitrary files.** WeasyPrint's default fetcher would make
  a live HTTP request for a remote image and happily embed any local file a
  ``<a rel="attachment" href="file:///...">`` points at. :class:`_LocalFetcher`
  only serves files under ``<content_dir>/guides`` (guide images) and horizon's
  own static directory, plus inline ``data:`` URLs, and refuses everything else.
* **Cheap repeats.** Rendering is the expensive part on weak hardware, so
  finished PDFs are kept in a small in-memory LRU cache keyed by the document
  (or a caller-supplied key such as guide id + source mtime) and the date.
"""

from __future__ import annotations

import hashlib
import html as html_lib
import mimetypes
import re
import threading
import urllib.request
from collections import OrderedDict
from datetime import date
from functools import lru_cache
from pathlib import Path
from urllib.parse import unquote, urlsplit

from weasyprint import CSS, HTML

from horizon.config import settings

_STATIC_DIR = Path(__file__).resolve().parent.parent / "web" / "static"
_PRINT_CSS = _STATIC_DIR / "print.css"

# Rendered PDFs kept in memory. Guides are small (tens to a few hundred KB as
# PDF), so a handful of entries bounds memory on a Raspberry Pi.
_CACHE_SIZE = 16
_cache: OrderedDict[str, bytes] = OrderedDict()
_cache_lock = threading.Lock()

_TITLE_RE = re.compile(r"<title[^>]*>(?P<title>.*?)</title\s*>", re.IGNORECASE | re.DOTALL)
_TITLE_SUFFIX = " — horizon"


class PDFResourceRefused(ValueError):
    """A PDF tried to load something outside the allowed local directories."""


def _allowed_roots() -> list[Path]:
    return [(Path(settings.content_dir) / "guides").resolve(), _STATIC_DIR.resolve()]


def _base_url() -> str:
    """Base URL so a guide's relative ``images/...`` paths resolve to its files."""
    return (Path(settings.content_dir) / "guides").resolve().as_uri() + "/"


def _resolve_local(url: str) -> Path:
    """Map an allowed ``file:`` URL to a real file, or raise :class:`PDFResourceRefused`."""
    parts = urlsplit(url)
    if parts.scheme.lower() != "file" or parts.netloc not in ("", "localhost"):
        raise PDFResourceRefused(f"PDF resource refused (not a local file): {url[:200]}")
    try:
        path = Path(urllib.request.url2pathname(unquote(parts.path))).resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        raise PDFResourceRefused(f"PDF resource refused (bad path): {url[:200]}") from exc
    if not any(path.is_relative_to(root) for root in _allowed_roots()) or not path.is_file():
        raise PDFResourceRefused(f"PDF resource refused (outside guide content): {url[:200]}")
    return path


def _fetch(url: str) -> tuple[bytes, str, str]:
    """Return ``(data, mime_type, url)`` for an allowed resource; raise otherwise."""
    scheme = urlsplit(url).scheme.lower()
    if scheme == "data":
        # Inline data needs no network or filesystem; let the stdlib decode it.
        with urllib.request.urlopen(url) as resp:  # noqa: S310 - data: scheme only
            return resp.read(), resp.headers.get_content_type(), url
    path = _resolve_local(url)
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return path.read_bytes(), mime_type, url


def _make_url_fetcher():
    """Build a WeasyPrint URL fetcher restricted to :func:`_fetch`.

    WeasyPrint >= 66-ish takes a ``URLFetcher`` subclass; older releases take a
    plain callable returning a dict. Support both so the ``weasyprint>=61``
    floor in ``pyproject.toml`` keeps working.
    """
    try:
        from weasyprint.urls import URLFetcher, URLFetcherResponse
    except ImportError:

        def legacy_fetcher(url: str) -> dict:
            data, mime_type, final_url = _fetch(url)
            return {"string": data, "mime_type": mime_type, "redirected_url": final_url}

        return legacy_fetcher

    class _LocalFetcher(URLFetcher):
        def fetch(self, url, headers=None):  # noqa: ANN001 - WeasyPrint's signature
            data, mime_type, final_url = _fetch(url)
            return URLFetcherResponse(final_url, data, {"Content-Type": mime_type})

    return _LocalFetcher(allowed_protocols=("file", "data"), allow_redirects=False)


@lru_cache(maxsize=1)
def _stylesheet() -> CSS:
    """Return the shared print stylesheet, parsed once and reused."""
    return CSS(filename=str(_PRINT_CSS), url_fetcher=_make_url_fetcher())


def _css_string(text: str) -> str:
    """Quote ``text`` as a CSS string literal."""
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    escaped = re.sub(r"[\r\n\f]+", " ", escaped)
    return f'"{escaped}"'


def _colophon_css(title: str, printed: str) -> str:
    """PDF-only page furniture: running title header, colophon + page footer."""
    label = _css_string(title)
    footer = _css_string(f"horizon · {title} · printed {printed}")
    return f"""
@page {{
  margin-top: 2.2cm;
  margin-bottom: 2.2cm;
  @top-center {{
    content: {label};
    font-size: 8.5pt;
    color: #444;
  }}
  @bottom-left {{
    content: {footer};
    font-size: 8pt;
    color: #444;
  }}
  @bottom-right {{
    content: counter(page) " / " counter(pages);
    font-size: 8pt;
    color: #444;
  }}
}}
@page :first {{
  @top-center {{ content: none; }}
}}
"""


def _title_of(document: str) -> str:
    match = _TITLE_RE.search(document)
    if not match:
        return "guide"
    title = html_lib.unescape(re.sub(r"<[^>]+>", "", match.group("title"))).strip()
    title = title.removesuffix(_TITLE_SUFFIX.strip()).strip()
    return title or "guide"


def render_pdf(
    html: str,
    *,
    title: str | None = None,
    cache_key: str | None = None,
    printed_on: date | None = None,
) -> bytes:
    """Render a standalone HTML document to a minimal, high-contrast, A4 PDF.

    ``title`` labels the page header/footer (default: the document's
    ``<title>`` without the " — horizon" suffix). ``cache_key`` (e.g.
    ``f"{guide_id}:{source_mtime}"``) identifies the content for the render
    cache; without one the document's own hash is used, which is just as
    correct. Only local guide files and horizon's static assets are ever
    loaded while rendering — never the network.
    """
    printed = (printed_on or date.today()).isoformat()
    label = title if title is not None else _title_of(html)
    identity = cache_key if cache_key is not None else hashlib.sha256(html.encode()).hexdigest()
    key = hashlib.sha256(f"{identity}\0{label}\0{printed}".encode()).hexdigest()

    with _cache_lock:
        cached = _cache.get(key)
        if cached is not None:
            _cache.move_to_end(key)
            return cached

    fetcher = _make_url_fetcher()
    pdf = HTML(string=html, base_url=_base_url(), url_fetcher=fetcher).write_pdf(
        stylesheets=[_stylesheet(), CSS(string=_colophon_css(label, printed))]
    )

    with _cache_lock:
        _cache[key] = pdf
        _cache.move_to_end(key)
        while len(_cache) > _CACHE_SIZE:
            _cache.popitem(last=False)
    return pdf


def clear_cache() -> None:
    """Drop every cached PDF (e.g. after a re-seed)."""
    with _cache_lock:
        _cache.clear()
