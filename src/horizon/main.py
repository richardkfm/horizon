"""horizon FastAPI application entry point.

Wires together the server-rendered web UI and the Knowledge/AI APIs. On startup
it initialises the database, seeds bundled content if empty, and (in later steps)
builds the vector index. The app must import and serve the landing page with no
external services running; Ollama/Chroma are only exercised by the AI assistant.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from horizon import __version__
from horizon.api import ai, guides, journeys, recommend
from horizon.config import web_enabled
from horizon.db import init_db

logger = logging.getLogger("horizon")

STATIC_DIR = Path(__file__).parent / "web" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise DB, seed content, and build the index on startup."""
    # Capture recent log events in memory first, so the admin health feed shows
    # the seed/index lifespan steps and any later repairs.
    from horizon.services.eventlog import install as install_event_log

    install_event_log()
    if web_enabled():
        from horizon.web.admin import ensure_token_ready

        ensure_token_ready()
    init_db()
    # Seeding and indexing are implemented in later steps; keep startup resilient
    # so the app boots even before that logic exists.
    try:
        from horizon.seed import seed_if_empty

        seed_if_empty()
    except NotImplementedError:
        logger.info("Content seeding not yet implemented; skipping.")
    from horizon.config import low_power_enabled

    if low_power_enabled():
        # Building embeddings for the whole corpus is the heaviest startup cost;
        # in low-power mode we skip it and let retrieval use the keyword fallback.
        logger.info(
            "Low-power mode: skipping vector index build; AI retrieval uses "
            "keyword search and the assistant answers from local content."
        )
    else:
        try:
            from horizon.services.rag import reindex_content

            reindex_content()
        except NotImplementedError:
            logger.info("Vector indexing not yet implemented; skipping.")
    yield


app = FastAPI(title="horizon", version=__version__, lifespan=lifespan)

# The server-rendered web UI is optional: a headless operator can run a node
# with just the JSON API and the ``horizon-admin`` CLI by setting
# ``web.enabled: false`` (or ``HORIZON_WEB_ENABLED=0``). The API and health
# probe below are always mounted so integrations and probes never depend on it.
if web_enabled():
    from horizon.web import admin as admin_routes
    from horizon.web import maps as maps_routes
    from horizon.web import reference as reference_routes
    from horizon.web import routes as web_routes

    # Static assets (CSS + vendored JS).
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    # Guide illustrations live alongside the Markdown under the content directory
    # so content packs can ship their own figures. ``check_dir=False`` because the
    # content directory is materialised during the seeding lifespan step, after
    # this mount is created; the dir exists by the time any request is served.
    from horizon.config import settings

    guide_images = Path(settings.content_dir) / "guides" / "images"
    app.mount(
        "/guides/images",
        StaticFiles(directory=str(guide_images), check_dir=False),
        name="guide-images",
    )
    # Server-rendered pages.
    app.include_router(web_routes.router)
    app.include_router(admin_routes.router)
    app.include_router(reference_routes.router)
    app.include_router(maps_routes.router)
else:
    logger.info(
        "Web UI disabled (web.enabled is off): serving the JSON API only. "
        "Manage this node with the horizon-admin CLI."
    )

    @app.get("/", tags=["meta"])
    def web_disabled_notice() -> dict:
        """Friendly root response when the browser UI is turned off."""
        return {
            "status": "ok",
            "web_ui": "disabled",
            "detail": "The web UI is turned off. Use the JSON API under /api or the "
            "horizon-admin CLI to manage this node.",
            "api_docs": "/docs",
        }


# Knowledge + AI APIs (stable integration surface).
app.include_router(journeys.router)
app.include_router(guides.router)
app.include_router(recommend.router)
app.include_router(ai.router)


@app.get("/healthz", tags=["meta"])
def healthz() -> dict:
    """Liveness probe."""
    return {"status": "ok", "version": __version__}
