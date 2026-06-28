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
