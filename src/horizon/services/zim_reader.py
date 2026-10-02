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
from html.parser import HTMLParser
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


_BODY_RE = re.compile(r"<body\b[^>]*>(?P<inner>.*)</body\s*>", re.IGNORECASE | re.DOTALL)


# --- HTML sanitising + rewriting (pure string transform, no ZIM access) -----
#
# ZIM archives are third-party content, so their HTML is treated as untrusted:
# it is re-serialised through a small allowlist (stdlib ``HTMLParser``, no new
# dependency) rather than patched with regexes. Only known-harmless tags and
# attributes survive; every ``on*`` handler, ``javascript:``/``vbscript:`` URL,
# non-image ``data:`` URL, and embedding element (script, iframe, object,
# embed, frame, ...) is dropped. Attributes that horizon's own vendored JS acts
# on (htmx ``hx-*``/``data-hx-*``, Alpine ``x-*``/``@*``/``:*``) are not on the
# allowlist either, so article markup can't drive the page's own scripts.

# Elements dropped together with everything inside them.
_DROP_WITH_CONTENT = frozenset(
    {
        "script",
        "iframe",
        "object",
        "embed",
        "frame",
        "frameset",
        "applet",
        "noscript",
        "noembed",
        "noframes",
        "template",
        "head",
        "title",
        "svg",
        "math",
        "textarea",
        "select",
        "xmp",
        "plaintext",
    }
)

# Elements kept (with allowlisted attributes). Anything else (html, body, form,
# input, button, link, meta, base, unknown custom tags, ...) is unwrapped: the
# tag is dropped but its text content is kept.
_ALLOWED_TAGS = frozenset(
    {
        "a", "abbr", "address", "article", "aside", "audio", "b", "bdi", "bdo",
        "big", "blockquote", "br", "caption", "center", "cite", "code", "col",
        "colgroup", "dd", "del", "details", "dfn", "div", "dl", "dt", "em",
        "figcaption", "figure", "font", "footer", "h1", "h2", "h3", "h4", "h5",
        "h6", "header", "hr", "i", "img", "ins", "kbd", "li", "main", "mark",
        "nav", "ol", "p", "picture", "pre", "q", "rp", "rt", "ruby", "s", "samp",
        "section", "small", "source", "span", "strike", "strong", "style", "sub",
        "summary", "sup", "table", "tbody", "td", "tfoot", "th", "thead", "time",
        "tr", "track", "tt", "u", "ul", "var", "video", "wbr",
    }
)  # fmt: skip

_VOID_TAGS = frozenset({"br", "col", "hr", "img", "source", "track", "wbr"})

_ALLOWED_ATTRS = frozenset(
    {
        "abbr", "align", "alt", "bgcolor", "border", "cellpadding", "cellspacing",
        "cite", "class", "color", "colspan", "controls", "datetime", "dir",
        "face", "headers", "height", "href", "id", "kind", "label", "lang",
        "loop", "media", "muted", "name", "nowrap", "open", "poster", "preload",
        "reversed", "role", "rowspan", "scope", "size", "sizes", "span", "src",
        "srclang", "srcset", "start", "style", "title", "type", "valign", "value",
        "width",
    }
)  # fmt: skip

_URL_ATTRS = frozenset({"href", "src", "poster", "cite"})

# Strip whitespace/control characters browsers ignore inside a URL scheme
# ("java\tscript:" is still javascript:).
_URL_JUNK_RE = re.compile(r"[\x00-\x20\x7f]+")
_STYLE_DANGER_RE = re.compile(
    r"expression\s*\(|javascript:|vbscript:|behavior\s*:|-moz-binding|@import", re.I
)


def _scheme_of(value: str) -> str:
    cleaned = _URL_JUNK_RE.sub("", html.unescape(value)).lower()
    head = cleaned.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    return head.split(":", 1)[0] if ":" in head else ""


def _url_allowed(value: str, *, image: bool) -> bool:
    """False for script-capable URLs; ``data:`` only for images."""
    scheme = _scheme_of(value)
    if scheme in ("javascript", "vbscript", "livescript", "mocha", "file", "filesystem", "blob"):
        return False
    if scheme == "data":
        cleaned = _URL_JUNK_RE.sub("", value).lower()
        return image and cleaned.startswith("data:image/")
    return True


def _is_in_zim_link(value: str) -> bool:
    """True for a link that should be rewritten to a horizon /reference/... URL."""
    if value.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
        return False
    scheme = urlsplit(value).scheme
    return scheme in ("", "zim")


def _rewrite_target(value: str, *, pack_id: str, entry_path: str) -> str:
    resolved = urljoin(entry_path, value)
    resolved = resolved.lstrip("/")
    return f"/reference/{pack_id}/{resolved}"


def _rewrite_srcset(value: str, *, pack_id: str, entry_path: str) -> str | None:
    parts = []
    for candidate in value.split(","):
        candidate = candidate.strip()
        if not candidate:
            continue
        bits = candidate.split(None, 1)
        url = bits[0]
        descriptor = f" {bits[1]}" if len(bits) > 1 else ""
        if not _url_allowed(url, image=True):
            continue
        if _is_in_zim_link(url):
            url = _rewrite_target(url, pack_id=pack_id, entry_path=entry_path)
        parts.append(f"{url}{descriptor}")
    return ", ".join(parts) if parts else None


class _Sanitizer(HTMLParser):
    """Re-serialise untrusted HTML through the allowlists above."""

    def __init__(self, *, pack_id: str, entry_path: str) -> None:
        super().__init__(convert_charrefs=True)
        self._pack_id = pack_id
        self._entry_path = entry_path
        self._out: list[str] = []
        self._drop_stack: list[str] = []  # open drop-with-content elements
        self._open: list[str] = []  # open allowed elements, to keep output balanced
        self._in_style = False

    # -- helpers --------------------------------------------------------------

    def _clean_attrs(self, tag: str, attrs: list[tuple[str, str | None]]) -> str:
        kept: list[str] = []
        external = False
        image_ctx = tag in ("img", "source", "video", "picture")
        for raw_name, raw_value in attrs:
            name = raw_name.lower()
            value = raw_value or ""
            if name not in _ALLOWED_ATTRS or name.startswith("on"):
                continue
            if name == "style" and _STYLE_DANGER_RE.search(value):
                continue
            if name == "srcset":
                rewritten = _rewrite_srcset(
                    value, pack_id=self._pack_id, entry_path=self._entry_path
                )
                if rewritten is None:
                    continue
                value = rewritten
            elif name in _URL_ATTRS:
                if not _url_allowed(value, image=image_ctx or name == "poster"):
                    continue
                if name == "href" and tag == "a" and value.startswith(("http://", "https://")):
                    external = True
                elif _is_in_zim_link(value):
                    value = _rewrite_target(
                        value, pack_id=self._pack_id, entry_path=self._entry_path
                    )
            kept.append(f' {name}="{html.escape(value, quote=True)}"')
        if external:
            # Offline content can't guarantee an external link resolves, so mark
            # it clearly rather than let a visitor click into a silent dead end.
            kept.append(' target="_blank" rel="noopener"')
        return "".join(kept)

    # -- HTMLParser hooks -------------------------------------------------------

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if self._drop_stack:
            if tag in _DROP_WITH_CONTENT and tag not in _VOID_TAGS:
                self._drop_stack.append(tag)
            return
        if tag in _DROP_WITH_CONTENT:
            self._drop_stack.append(tag)
            return
        if tag not in _ALLOWED_TAGS:
            return
        if tag == "style":
            self._in_style = True
            self._open.append(tag)
            self._out.append("<style>")
            return
        self._out.append(f"<{tag}{self._clean_attrs(tag, attrs)}>")
        if tag not in _VOID_TAGS:
            self._open.append(tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if self._drop_stack or tag in _DROP_WITH_CONTENT or tag not in _ALLOWED_TAGS:
            return
        if tag in _VOID_TAGS:
            self._out.append(f"<{tag}{self._clean_attrs(tag, attrs)}>")
        else:
            self._out.append(f"<{tag}{self._clean_attrs(tag, attrs)}></{tag}>")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._drop_stack:
            if tag == self._drop_stack[-1]:
                self._drop_stack.pop()
            elif tag in self._drop_stack:
                del self._drop_stack[self._drop_stack.index(tag) :]
            return
        if tag not in _ALLOWED_TAGS or tag in _VOID_TAGS or tag not in self._open:
            # A stray closing tag must not close horizon's own wrapper elements.
            return
        while self._open:
            closing = self._open.pop()
            if closing == "style":
                self._in_style = False
            self._out.append(f"</{closing}>")
            if closing == tag:
                break

    def handle_data(self, data: str) -> None:
        if self._drop_stack:
            return
        if self._in_style:
            # Raw CSS (HTMLParser treats <style> as CDATA, so this text can't
            # contain a closing tag). Neutralise anything that could break out
            # of the element or pull in remote styles.
            css = re.sub(r"</?\s*style", "", data, flags=re.I)
            self._out.append(_STYLE_DANGER_RE.sub("/* removed */", css))
            return
        self._out.append(html.escape(data, quote=False))

    def result(self) -> str:
        self.close()
        # Close anything the article left open so it can't swallow the page.
        while self._open:
            self._out.append(f"</{self._open.pop()}>")
        return "".join(self._out)


def sanitize_article_html(html_text: str, *, pack_id: str, entry_path: str) -> str:
    """Allowlist-sanitise untrusted article HTML and rewrite in-archive URLs."""
    parser = _Sanitizer(pack_id=pack_id, entry_path=entry_path)
    parser.feed(html_text)
    return parser.result()


def rewrite_article_html(html_text: str, *, pack_id: str, entry_path: str) -> str:
    """Sanitise an article and rewrite in-article links/assets to horizon's
    ``/reference/<pack_id>/...`` URLs. Pure str -> str; safe to unit-test
    without a ZIM file.

    horizon never executes third-party JS from downloaded content: the HTML is
    re-serialised through :func:`sanitize_article_html`'s allowlist, which
    drops scripts and other embedding elements, every event-handler attribute,
    and script-capable URLs (see the module notes above).

    ZIM entries are usually *complete* HTML documents. Embedding one whole into
    the article template used to nest ``<html>/<head>/<body>`` inside horizon's
    page, and browsers hoist the head's ``<link rel="stylesheet">`` tags — so a
    pack's own MediaWiki skin CSS (rules on bare ``body``, ``h1``, ``a``, ...)
    restyled all of horizon's chrome and broke the dark theme. Keep only the
    ``<body>`` content: the article renders under horizon's own ``.zim-article``
    styling instead of the pack's site-wide skin. Inline ``<style>`` blocks in
    the body (e.g. MediaWiki TemplateStyles) are kept — they target the
    article's own classes, not the page. A fragment without ``<body>`` passes
    through whole (sanitised).
    """
    body = _BODY_RE.search(html_text)
    if body:
        html_text = body.group("inner")
    return sanitize_article_html(html_text, pack_id=pack_id, entry_path=entry_path)


# Mimetypes a browser may execute script in when navigated to directly.
_ACTIVE_MIMETYPES = (
    "image/svg+xml",
    "application/xhtml+xml",
    "application/xml",
    "text/xml",
    "text/xsl",
    "application/xslt+xml",
)
_MIMETYPE_RE = re.compile(r"^[a-z0-9][a-z0-9!#$&^_.+-]*/[a-z0-9][a-z0-9!#$&^_.+-]*$")


def safe_mimetype(mimetype: str) -> str:
    """Normalise a ZIM entry's mimetype for a ``Content-Type`` header."""
    base = (mimetype or "").split(";", 1)[0].strip().lower()
    return base if _MIMETYPE_RE.match(base) else "application/octet-stream"


def is_active_mimetype(mimetype: str) -> bool:
    """True for document types that can run script when opened directly (SVG, XHTML, XML)."""
    return safe_mimetype(mimetype) in _ACTIVE_MIMETYPES
