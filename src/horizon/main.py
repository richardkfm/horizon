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

from fastapi import FastAPI, Request
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from horizon import __version__
from horizon.api import ai, guides, journeys, recommend
from horizon.config import web_enabled
from horizon.db import init_db

logger = logging.getLogger("horizon")

STATIC_DIR = Path(__file__).parent / "web" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise DB, seed content, and build the index on startup.

    Each step is isolated: a failure in one (a corrupt content file, an
    unwritable index directory, ...) is logged and boot continues, so the node
    always comes up and serves whatever it can. The vector index is built in a
    background thread so pages are served immediately.
    """

    from collections.abc import Callable

    def step(name: str, fn: Callable[[], object]) -> None:
        try:
            fn()
        except NotImplementedError:
            logger.info("Startup step %r not yet implemented; skipping.", name)
        except Exception:  # noqa: BLE001 - never let one step stop the node booting
            logger.exception("Startup step %r failed; continuing to boot.", name)

    # Capture recent log events in memory first, so the admin health feed shows
    # the seed/index lifespan steps and any later repairs.
    def install_events() -> None:
        from horizon.services.eventlog import install as install_event_log

        install_event_log()

    def admin_token() -> None:
        if web_enabled():
            from horizon.web.admin import ensure_token_ready

            ensure_token_ready()

    def seed() -> None:
        from horizon.seed import seed_if_empty

        seed_if_empty()

    def index() -> None:
        from horizon.config import low_power_enabled

        if low_power_enabled():
            # Building embeddings for the whole corpus is the heaviest startup
            # cost; in low-power mode we skip it and let retrieval use the
            # keyword fallback.
            logger.info(
                "Low-power mode: skipping vector index build; AI retrieval uses "
                "keyword search and the assistant answers from local content."
            )
            return
        from horizon.services.rag import start_background_reindex

        start_background_reindex()

    step("event log", install_events)
    step("admin token", admin_token)
    step("database", init_db)
    step("content seed", seed)
    step("search index", index)
    yield


app = FastAPI(title="horizon", version=__version__, lifespan=lifespan)

# Compress HTML, CSS, and JS on the wire: a page plus its stylesheet shrinks
# roughly 4-5x, which matters on a slow mesh/Wi-Fi link to a Pi. Level 5 keeps
# the CPU cost low on weak hardware for most of the size win; responses that
# are already encoded (gzipped map tiles) are passed through untouched.
app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=5)

# The server-rendered web UI is optional: a headless operator can run a node
# with just the JSON API and the ``horizon-admin`` CLI by setting
# ``web.enabled: false`` (or ``HORIZON_WEB_ENABLED=0``). The API and health
# probe below are always mounted so integrations and probes never depend on it.
if web_enabled():
    from horizon.web import admin as admin_routes
    from horizon.web import maps as maps_routes
    from horizon.web import reference as reference_routes
    from horizon.web import routes as web_routes
    from horizon.web.assets import SHORT_CACHE, CachedStaticFiles

    # Static assets (CSS + vendored JS). Versioned URLs are cached for a year.
    app.mount("/static", CachedStaticFiles(directory=str(STATIC_DIR)), name="static")
    # Guide illustrations live alongside the Markdown under the content directory
    # so content packs can ship their own figures. ``check_dir=False`` because the
    # content directory is materialised during the seeding lifespan step, after
    # this mount is created; the dir exists by the time any request is served.
    from horizon.config import settings

    guide_images = Path(settings.content_dir) / "guides" / "images"
    app.mount(
        "/guides/images",
        CachedStaticFiles(directory=str(guide_images), check_dir=False),
        name="guide-images",
    )

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon() -> Response:
        """Serve the SVG mark for browsers/tools that ask for /favicon.ico."""
        return FileResponse(
            STATIC_DIR / "favicon.svg",
            media_type="image/svg+xml",
            headers={"Cache-Control": SHORT_CACHE},
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


def _wants_json_error(request: Request) -> bool:
    """API callers, probes, and htmx fragment requests keep the JSON errors.

    The JSON API is a stable contract (``{"detail": ...}`` bodies), so only
    browser page requests get the friendly HTML error page.
    """
    path = request.url.path
    return (
        not web_enabled()
        or path.startswith("/api/")
        or path in ("/api", "/healthz", "/docs", "/redoc", "/openapi.json")
        or "HX-Request" in request.headers
    )


def _error_page(request: Request, status_code: int, headers: dict | None = None) -> Response:
    """Render the friendly, plain-language error page with the real status."""
    from horizon.web.routes import templates

    return templates.TemplateResponse(
        request,
        "error.html",
        {"status_code": status_code, "path": request.url.path},
        status_code=status_code,
        headers=headers,
    )


@app.exception_handler(StarletteHTTPException)
async def _http_error(request: Request, exc: StarletteHTTPException) -> Response:
    if _wants_json_error(request) or exc.status_code < 400:
        return await http_exception_handler(request, exc)
    return _error_page(request, exc.status_code, getattr(exc, "headers", None))


@app.exception_handler(RequestValidationError)
async def _validation_error(request: Request, exc: RequestValidationError) -> Response:
    if _wants_json_error(request):
        return await request_validation_exception_handler(request, exc)
    return _error_page(request, 422)


@app.exception_handler(Exception)
async def _server_error(request: Request, exc: Exception) -> Response:
    """Unexpected crashes: the friendly page for visitors, plain text for the API.

    Starlette still logs the traceback and re-raises after this returns. The
    API keeps the exact ``Internal Server Error`` text body it always had, and
    if the error page itself can't render, fall back to that too.
    """
    if not _wants_json_error(request):
        try:
            return _error_page(request, 500)
        except Exception:  # noqa: BLE001 - never fail while reporting a failure
            pass
    return PlainTextResponse("Internal Server Error", status_code=500)


@app.get("/healthz", tags=["meta"])
def healthz() -> dict:
    """Liveness probe."""
    return {"status": "ok", "version": __version__}
