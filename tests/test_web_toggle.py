"""The web UI can be turned off, leaving the JSON API (and the CLI) in place.

``horizon.main`` decides whether to mount the server-rendered UI when the module
is imported, so each case is exercised in a fresh subprocess with a different
``HORIZON_WEB_ENABLED`` value. The subprocess inherits ``HORIZON_CONFIG`` (set by
``conftest.py``) so it uses the same hermetic temp data dir.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap

_PROBE = textwrap.dedent(
    """
    import json
    from fastapi.testclient import TestClient
    from horizon.db import init_db
    from horizon.seed import seed_if_empty

    init_db()
    seed_if_empty()

    from horizon.main import app

    with TestClient(app) as client:
        paths = sorted(app.openapi()["paths"].keys())
        root = client.get("/")
        ctype = root.headers.get("content-type", "")
        print(json.dumps({
            "paths": paths,
            "root_status": root.status_code,
            "root_json": root.json() if ctype.startswith("application/json") else None,
            "root_is_html": ctype.startswith("text/html"),
            "journeys_api": client.get("/api/journeys").status_code,
            "healthz": client.get("/healthz").status_code,
        }))
    """
)


def _probe(web_enabled: str | None) -> dict:
    env = dict(os.environ)
    if web_enabled is None:
        env.pop("HORIZON_WEB_ENABLED", None)
    else:
        env["HORIZON_WEB_ENABLED"] = web_enabled
    result = subprocess.run(
        [sys.executable, "-c", _PROBE],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_web_enabled_by_default():
    data = _probe(None)
    # HTML UI mounted: landing page renders HTML and web routes are present.
    assert data["root_status"] == 200
    assert data["root_is_html"] is True
    assert "/journeys" in data["paths"]
    assert "/guides" in data["paths"]
    # The JSON API and health probe are up regardless.
    assert data["journeys_api"] == 200
    assert data["healthz"] == 200


def test_web_can_be_disabled():
    data = _probe("0")
    # The browser UI routes are gone...
    assert "/journeys" not in data["paths"]
    assert "/guides" not in data["paths"]
    # ...root returns a friendly JSON notice instead of the HTML landing page...
    assert data["root_json"] is not None
    assert data["root_json"]["web_ui"] == "disabled"
    # ...but the JSON API and health probe still work.
    assert data["journeys_api"] == 200
    assert data["healthz"] == 200


def test_web_enabled_truthy_value():
    data = _probe("yes")
    assert data["root_is_html"] is True
    assert "/journeys" in data["paths"]
