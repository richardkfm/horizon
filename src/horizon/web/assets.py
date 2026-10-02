"""Cache-busting for the vendored static assets.

Browsers cache ``/static/app.css`` aggressively, but the HTML that links it is
fetched fresh every load. After a deploy that meant a new template could be
served with the *old* stylesheet still applied from cache — the header looking
broken until a hard refresh. We append a short version token to every static
URL; the token changes whenever an asset's contents change, so a new build
yields a new URL the browser has never cached, while unchanged deploys keep the
URL stable (and the cache warm).

The token is computed once at import from each file's size + mtime, mixed with
the app version. No network, no build step — it works fully offline.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import parse_qs

from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from horizon import __version__

STATIC_DIR = Path(__file__).parent / "static"


def _compute_version() -> str:
    digest = hashlib.sha1(__version__.encode())
    try:
        for path in sorted(STATIC_DIR.rglob("*")):
            if path.is_file():
                stat = path.stat()
                digest.update(path.name.encode())
                digest.update(str(stat.st_size).encode())
                digest.update(str(int(stat.st_mtime)).encode())
    except OSError:
        # If the static dir can't be read, fall back to the version alone; the
        # URLs stay valid, they just won't bust on content change.
        pass
    return digest.hexdigest()[:8]


STATIC_VERSION = _compute_version()


def static_url(path: str) -> str:
    """Return a ``/static/<path>`` URL with a cache-busting version suffix."""
    return f"/static/{path}?v={STATIC_VERSION}"


# Cache lifetimes for static responses. A versioned URL (``?v=<token>`` from
# ``static_url``) never changes content, so browsers may keep it for a year
# without revalidating; an unversioned one (guide images, a hand-typed URL)
# gets a short lifetime so an edit shows up within minutes.
IMMUTABLE_CACHE = "public, max-age=31536000, immutable"
SHORT_CACHE = "public, max-age=600"


class CachedStaticFiles(StaticFiles):
    """``StaticFiles`` that adds ``Cache-Control`` based on the cache-buster.

    Saves a request (and a Pi's CPU) per asset per page view: with the
    long-lived header a returning visitor's browser doesn't even ask.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        if response.status_code in (200, 304):
            query = parse_qs(scope.get("query_string", b"").decode("latin-1"))
            response.headers["Cache-Control"] = IMMUTABLE_CACHE if query.get("v") else SHORT_CACHE
        return response
