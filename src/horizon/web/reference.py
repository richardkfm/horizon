"""Reference library: an in-browser reader for installed ZIM content packs.

A content pack (``services/packs.py``) is a large optional download such as an
offline Wikipedia or WikEM snapshot. Downloading it used to be a dead end —
horizon had no way to actually read the result short of pointing an external
Kiwix viewer at the file. This router serves already-installed ``.zim`` packs
directly: a landing/search page per pack and an article view, with in-article
links and assets rewritten to stay under ``/reference/<pack_id>/...`` so
browsing works with no client-side JS and no third-party script execution
(``services/zim_reader.rewrite_article_html`` strips ``<script>`` tags).

Only *installed* ZIM-format packs are ever listed or resolvable here — this
router never touches the network or triggers a download.
"""

from __future__ import annotations

import base64
import hashlib
import re
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from horizon import __version__
from horizon.config import assistant_enabled, low_power_enabled
from horizon.services import packs as packs_service
from horizon.web.assets import static_url

router = APIRouter(prefix="/reference", tags=["reference"])

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals["low_power_enabled"] = low_power_enabled
templates.env.globals["assistant_enabled"] = assistant_enabled
templates.env.globals["static_url"] = static_url
templates.env.globals["version"] = __version__
templates.env.globals["reference_library_enabled"] = packs_service.has_installed_zim_pack
templates.env.globals["map_viewer_enabled"] = packs_service.has_installed_map_pack


# Raw (non-article) entries are served as inert resources: never sniffed into
# something executable, and -- if navigated to directly, e.g. an SVG -- unable to
# run script or load anything but same-origin images.
_RAW_ENTRY_CSP = "default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; sandbox"

_INLINE_SCRIPT_RE = re.compile(
    r"<script(?P<attrs>[^>]*)>(?P<body>.*?)</script\s*>", re.IGNORECASE | re.DOTALL
)


def _article_csp(page_html: str) -> str:
    """A Content-Security-Policy for a rendered reference article page.

    The article body has already been sanitised (no scripts, no handlers), so
    every inline ``<script>`` left in the page is horizon's own chrome from
    ``base.html`` (theme/text-size setup). Those are allowed by hash; any other
    inline script, and every script from anywhere but this node, is refused, as
    are plugins, frames, ``<base>`` hijacking, and remote images/fonts/media.
    ``'unsafe-eval'`` is only there for the vendored Alpine.js, which evaluates
    its own ``x-*`` attributes -- attributes the sanitiser never lets through
    from article markup.
    """
    hashes = []
    for match in _INLINE_SCRIPT_RE.finditer(page_html):
        if "src=" in match.group("attrs").lower():
            continue
        digest = hashlib.sha256(match.group("body").encode("utf-8")).digest()
        hashes.append(f"'sha256-{base64.b64encode(digest).decode('ascii')}'")
    script_src = " ".join(["'self'", "'unsafe-eval'", *sorted(set(hashes))])
    return (
        "default-src 'self'; "
        f"script-src {script_src}; "
        "object-src 'none'; frame-src 'none'; child-src 'none'; base-uri 'none'; "
        "form-action 'self'; img-src 'self' data:; media-src 'self'; "
        "font-src 'self' data:; style-src 'self' 'unsafe-inline'; connect-src 'self'"
    )


def _installed_zim_packs() -> list[dict]:
    """Installed, ZIM-format catalog rows -- the only packs this reader shows."""
    return [
        row for row in packs_service.pack_status() if row["installed"] and row["format"] == "zim"
    ]


def _zim_path_or_404(pack_id: str) -> tuple[dict, Path]:
    """Look up an installed ZIM pack's row and on-disk file, or raise 404."""
    row = next((r for r in _installed_zim_packs() if r["id"] == pack_id), None)
    path = packs_service.pack_file_path(pack_id)
    if row is None or path is None or not path.is_file():
        raise HTTPException(status_code=404, detail=f"Reference pack not installed: {pack_id}")
    return row, path


@router.get("", response_class=HTMLResponse)
def reference_index(request: Request) -> HTMLResponse:
    """List installed reference (ZIM) packs."""
    from horizon.services import zim_reader

    rows = []
    for row in _installed_zim_packs():
        path = packs_service.pack_file_path(row["id"])
        if path is None or not path.is_file():
            continue
        try:
            info = zim_reader.pack_info(path)
        except zim_reader.ZimUnavailableError:
            continue
        rows.append({"id": row["id"], "title": info.title, "description": info.description})

    return templates.TemplateResponse(request, "reference_index.html", {"packs": rows})


@router.get("/{pack_id}", response_class=HTMLResponse)
def pack_landing(
    request: Request, pack_id: str, q: Annotated[str | None, Query()] = None
) -> HTMLResponse:
    """A pack's landing page: title, article count, search, random article."""
    from horizon.services import zim_reader

    _, path = _zim_path_or_404(pack_id)
    info = zim_reader.pack_info(path)
    query = (q or "").strip()
    hits = zim_reader.search(path, query) if query else []

    return templates.TemplateResponse(
        request,
        "reference_pack.html",
        {
            "pack_id": pack_id,
            "info": info,
            "query": query,
            "hits": hits,
        },
    )


@router.get("/{pack_id}/random")
def pack_random(pack_id: str) -> RedirectResponse:
    """Redirect to a random article -- a low-effort way to browse an unfamiliar pack."""
    from horizon.services import zim_reader

    _, path = _zim_path_or_404(pack_id)
    entry_path = zim_reader.random_entry_path(path)
    return RedirectResponse(url=f"/reference/{pack_id}/{entry_path}", status_code=303)


@router.get("/{pack_id}/{entry_path:path}")
def pack_article(request: Request, pack_id: str, entry_path: str) -> Response:
    """Serve one ZIM entry: a rewritten HTML article, or a raw in-article asset
    (image/CSS/font) by mimetype. Both live under the same path scheme because
    ZIM entry paths don't otherwise distinguish "page" from "asset".
    """
    from horizon.services import zim_reader

    row, path = _zim_path_or_404(pack_id)
    entry = zim_reader.resolve_entry(path, entry_path)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Not found in {pack_id}: {entry_path}")

    mimetype = zim_reader.safe_mimetype(entry.mimetype)
    if mimetype != "text/html":
        headers = {
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": _RAW_ENTRY_CSP,
        }
        if zim_reader.is_active_mimetype(mimetype):
            # SVG/XHTML/XML can carry script: still usable as an <img> source,
            # but opened directly it is sandboxed by the CSP above.
            headers["Cross-Origin-Resource-Policy"] = "same-origin"
        return Response(content=entry.content, media_type=mimetype, headers=headers)

    body_html = zim_reader.rewrite_article_html(
        entry.content.decode("utf-8", errors="replace"),
        pack_id=pack_id,
        entry_path=entry.path,
    )
    response = templates.TemplateResponse(
        request,
        "reference_article.html",
        {
            "pack_id": pack_id,
            "pack_title": row["title"],
            "article_title": entry.title,
            "body_html": body_html,
        },
    )
    response.headers["Content-Security-Policy"] = _article_csp(
        bytes(response.body).decode("utf-8", errors="replace")
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
