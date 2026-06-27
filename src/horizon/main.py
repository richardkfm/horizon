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
from horizon.db import init_db
from horizon.web import admin as admin_routes
from horizon.web import routes as web_routes

logger = logging.getLogger("horizon")

STATIC_DIR = Path(__file__).parent / "web" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise DB, seed content, and build the index on startup."""
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

# Static assets (CSS + vendored JS).
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Server-rendered pages.
app.include_router(web_routes.router)
app.include_router(admin_routes.router)

# Knowledge + AI APIs (stable integration surface).
app.include_router(journeys.router)
app.include_router(guides.router)
app.include_router(recommend.router)
app.include_router(ai.router)


@app.get("/healthz", tags=["meta"])
def healthz() -> dict:
    """Liveness probe."""
    return {"status": "ok", "version": __version__}
