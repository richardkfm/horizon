"""Simple token-based admin area.

A self-hosted operator logs in with a shared token (from ``config.yaml`` or the
``HORIZON_ADMIN_TOKEN`` env var) and sees a read-only content dashboard. Access
is carried by an httponly cookie holding an HMAC of the token — the raw token is
never stored in the cookie. With no token configured the area is disabled.

Kept deliberately small: no users table, no sessions store, no new dependencies.
The heavier content-management features land in the later content-packs slice.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from collections import Counter
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, func, select

from horizon import __version__
from horizon.config import settings
from horizon.db import get_session
from horizon.models import (
    Category,
    Guide,
    Journey,
    JourneyGuideLink,
    JourneyPrerequisite,
)

router = APIRouter(tags=["admin"])

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

SessionDep = Annotated[Session, Depends(get_session)]

COOKIE_NAME = "horizon_admin"
_COOKIE_MESSAGE = b"horizon-admin-v1"


def _effective_token() -> str:
    """Resolve the admin token: env var overrides config; blank ⇒ disabled."""
    return os.environ.get("HORIZON_ADMIN_TOKEN") or settings.admin.token


def admin_enabled() -> bool:
    """True when an admin token is configured."""
    return bool(_effective_token())


def _expected_cookie() -> str:
    """HMAC of the effective token — the value stored in the auth cookie."""
    token = _effective_token().encode("utf-8")
    return hmac.new(token, _COOKIE_MESSAGE, hashlib.sha256).hexdigest()


def is_authed(request: Request) -> bool:
    """True when the request carries a valid admin cookie."""
    if not admin_enabled():
        return False
    presented = request.cookies.get(COOKIE_NAME, "")
    return hmac.compare_digest(presented, _expected_cookie())


@router.get("/admin/login", response_class=HTMLResponse)
def login_form(request: Request) -> HTMLResponse:
    """Show the admin login form (or a disabled notice)."""
    return templates.TemplateResponse(
        request,
        "admin/login.html",
        {"enabled": admin_enabled(), "error": None},
    )


@router.post("/admin/login")
def login_submit(request: Request, token: Annotated[str, Form()] = ""):
    """Verify the submitted token and set the auth cookie on success."""
    if not admin_enabled():
        return templates.TemplateResponse(
            request,
            "admin/login.html",
            {"enabled": False, "error": None},
            status_code=403,
        )

    if not hmac.compare_digest(token, _effective_token()):
        return templates.TemplateResponse(
            request,
            "admin/login.html",
            {"enabled": True, "error": "Incorrect token."},
            status_code=401,
        )

    response = RedirectResponse("/admin", status_code=303)
    response.set_cookie(
        COOKIE_NAME,
        _expected_cookie(),
        httponly=True,
        samesite="strict",
        max_age=60 * 60 * 12,
    )
    return response


@router.post("/admin/logout")
def logout() -> RedirectResponse:
    """Clear the auth cookie and return home."""
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response


@router.get("/admin", response_class=HTMLResponse)
def dashboard(request: Request, session: SessionDep):
    """Read-only content overview, gated behind the admin cookie."""
    if not is_authed(request):
        return RedirectResponse("/admin/login", status_code=303)

    journey_rows = session.exec(
        select(Journey.category, func.count()).group_by(Journey.category)
    ).all()
    guide_rows = session.exec(select(Guide.category, func.count()).group_by(Guide.category)).all()
    journey_counts = Counter({cat.value: n for cat, n in journey_rows})
    guide_counts = Counter({cat.value: n for cat, n in guide_rows})

    per_category = [
        {
            "category": c.value,
            "journeys": journey_counts.get(c.value, 0),
            "guides": guide_counts.get(c.value, 0),
        }
        for c in Category
    ]

    stats = {
        "journeys_total": sum(journey_counts.values()),
        "guides_total": sum(guide_counts.values()),
        "guide_links": len(session.exec(select(JourneyGuideLink)).all()),
        "prerequisites": len(session.exec(select(JourneyPrerequisite)).all()),
    }

    runtime = {
        "version": __version__,
        "content_dir": settings.content_dir,
        "database": settings.database,
    }

    return templates.TemplateResponse(
        request,
        "admin/dashboard.html",
        {
            "per_category": per_category,
            "stats": stats,
            "runtime": runtime,
        },
    )
