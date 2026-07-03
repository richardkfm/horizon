"""Read Kiwix ZIM content packs (offline Wikipedia, WikEM, ...) for display.

Content packs downloaded via ``services/packs.py`` are self-contained ZIM
archives on disk. This module is the pure, offline read side: given a path to
an already-downloaded ``.zim`` file, open it, resolve an article by path,
rewrite its HTML so in-article links/assets work under horizon's own
``/reference/<pack_id>/...`` URLs, and search the archive's built-in index.
No network, no database — everything here is a local file read, so it stays
importable and testable without a running FastAPI app or a real multi-hundred
-megabyte archive (see ``tests/test_zim_reader.py``, which builds tiny
synthetic ZIMs with ``libzim.writer`` for the read-path tests).

``libzim`` ships small prebuilt wheels (no system library required, including
on aarch64/Raspberry Pi), so it is a plain top-level import here, the same way
``services/pdf.py`` imports WeasyPrint at module level — callers that want to
defer loading it import *this module* lazily at the call site instead (see
``web/reference.py``), mirroring how routes.py lazily imports ``services.pdf``.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from libzim.reader import Archive
from libzim.search import Query, Searcher

# Cap redirect-following so a corrupt or cyclic ZIM can't hang a request.
_MAX_REDIRECTS = 5


class ZimUnavailableError(RuntimeError):
    """A ZIM archive could not be opened or read (missing, corrupt, ...)."""


@dataclass(frozen=True)
class ZimEntry:
    """A resolved, unrewritten ZIM entry: raw content as stored in the archive."""

    path: str
    title: str
    content: bytes
    mimetype: str


@dataclass(frozen=True)
class ZimSearchHit:
    path: str
    title: str


@dataclass(frozen=True)
class ZimPackInfo:
    title: str
    description: str
    language: str
    article_count: int
    main_path: str


def _open(zim_path: Path) -> Archive:
    try:
        return Archive(zim_path)
    except (RuntimeError, OSError) as exc:
        raise ZimUnavailableError(f"Could not open ZIM archive: {zim_path}") from exc


def _metadata_str(archive: Archive, name: str, default: str = "") -> str:
    try:
        return archive.get_metadata(name).decode("utf-8", errors="replace")
    except (RuntimeError, KeyError):
        return default


def pack_info(zim_path: Path) -> ZimPackInfo:
    """Return display metadata for a ZIM pack's landing page."""
    archive = _open(zim_path)
    return ZimPackInfo(
        title=_metadata_str(archive, "Title", default=zim_path.stem),
        description=_metadata_str(archive, "Description"),
        language=_metadata_str(archive, "Language"),
        article_count=archive.article_count,
        main_path=archive.main_entry.path,
    )


def resolve_entry(zim_path: Path, entry_path: str) -> ZimEntry | None:
    """Return the entry at ``entry_path``, following redirects. ``None`` if missing."""
    archive = _open(zim_path)
    try:
        entry = archive.get_entry_by_path(entry_path)
    except KeyError:
        return None

    for _ in range(_MAX_REDIRECTS):
        if not entry.is_redirect:
            break
        entry = entry.get_redirect_entry()
    else:
        raise ZimUnavailableError(f"Redirect loop resolving {entry_path!r} in {zim_path}")

    item = entry.get_item()
    return ZimEntry(
        path=entry.path,
        title=entry.title,
        content=bytes(item.content),
        mimetype=item.mimetype,
    )


def random_entry_path(zim_path: Path) -> str:
    """Return the path of a random article, for a "surprise me" link."""
    archive = _open(zim_path)
    return archive.get_random_entry().path


def search(zim_path: Path, query: str, *, limit: int = 20) -> list[ZimSearchHit]:
    """Full-text search the archive's built-in index. No network, no ranking model."""
    query = query.strip()
    if not query:
        return []
    archive = _open(zim_path)
    results = Searcher(archive).search(Query().set_query(query))
    hits = []
    for path in results.getResults(0, limit):
        entry = archive.get_entry_by_path(path)
        hits.append(ZimSearchHit(path=path, title=entry.title))
    return hits


# --- HTML rewriting (pure string transform, no ZIM access) ------------------

_TAG_ATTR_RE = re.compile(
    r"""(?P<tag><(?:a|img|link|source)\b[^>]*?\s)(?P<attr>href|src|srcset)=(?P<quote>["'])(?P<value>.*?)(?P=quote)""",
    re.IGNORECASE | re.DOTALL,
)
_SCRIPT_RE = re.compile(r"<script\b.*?</script\s*>", re.IGNORECASE | re.DOTALL)
_BODY_RE = re.compile(r"<body\b[^>]*>(?P<inner>.*)</body\s*>", re.IGNORECASE | re.DOTALL)


def _is_in_zim_link(value: str) -> bool:
    """True for a link that should be rewritten to a horizon /reference/... URL."""
    if value.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
        return False
    scheme = urlsplit(value).scheme
    return scheme in ("", "zim")


def _rewrite_srcset(value: str, *, pack_id: str, entry_path: str) -> str:
    parts = []
    for candidate in value.split(","):
        candidate = candidate.strip()
        if not candidate:
            continue
        bits = candidate.split(None, 1)
        url = bits[0]
        descriptor = f" {bits[1]}" if len(bits) > 1 else ""
        if _is_in_zim_link(url):
            url = _rewrite_target(url, pack_id=pack_id, entry_path=entry_path)
        parts.append(f"{url}{descriptor}")
    return ", ".join(parts)


def _rewrite_target(value: str, *, pack_id: str, entry_path: str) -> str:
    resolved = urljoin(entry_path, value)
    resolved = resolved.lstrip("/")
    return f"/reference/{pack_id}/{resolved}"


def rewrite_article_html(html_text: str, *, pack_id: str, entry_path: str) -> str:
    """Rewrite in-article links/assets to horizon's ``/reference/<pack_id>/...``
    URLs and strip ``<script>`` tags (horizon never executes third-party JS from
    downloaded content). Pure str -> str; safe to unit-test without a ZIM file.

    ZIM entries are usually *complete* HTML documents. Embedding one whole into
    the article template used to nest ``<html>/<head>/<body>`` inside horizon's
    page, and browsers hoist the head's ``<link rel="stylesheet">`` tags — so a
    pack's own MediaWiki skin CSS (rules on bare ``body``, ``h1``, ``a``, ...)
    restyled all of horizon's chrome and broke the dark theme. Keep only the
    ``<body>`` content: the article renders under horizon's own ``.zim-article``
    styling instead of the pack's site-wide skin. Inline ``<style>`` blocks in
    the body (e.g. MediaWiki TemplateStyles) are kept — they target the
    article's own classes, not the page. A fragment without ``<body>`` passes
    through whole.
    """
    body = _BODY_RE.search(html_text)
    if body:
        html_text = body.group("inner")
    html_text = _SCRIPT_RE.sub("", html_text)

    def _replace(m: re.Match[str]) -> str:
        tag, attr, quote, raw_value = m.group("tag", "attr", "quote", "value")
        # The captured value is still HTML-entity-escaped as it appeared in the
        # source (e.g. "&amp;" for "&" in a query string); unescape once before
        # resolving/rewriting, then escape exactly once on the way back out.
        value = html.unescape(raw_value)
        is_external = attr == "href" and value.startswith(("http://", "https://"))

        if attr == "srcset":
            new_value = _rewrite_srcset(value, pack_id=pack_id, entry_path=entry_path)
        elif _is_in_zim_link(value):
            new_value = _rewrite_target(value, pack_id=pack_id, entry_path=entry_path)
        else:
            new_value = value

        escaped = html.escape(new_value, quote=True)
        if is_external:
            # Offline content can't guarantee an external link resolves, so mark
            # it clearly rather than let a visitor click into a silent dead end.
            return f'{tag}{attr}={quote}{escaped}{quote} target="_blank" rel="noopener"'
        return f"{tag}{attr}={quote}{escaped}{quote}"

    return _TAG_ATTR_RE.sub(_replace, html_text)
