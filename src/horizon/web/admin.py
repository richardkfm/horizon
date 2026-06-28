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
from horizon.config import assistant_enabled, low_power_enabled, settings, web_enabled
from horizon.db import get_session
from horizon.models import (
    Category,
    Guide,
    Journey,
    JourneyGuideLink,
    JourneyPrerequisite,
)
from horizon.services import packs as packs_service
from horizon.web.assets import static_url

router = APIRouter(tags=["admin"])

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.filters["filesize"] = packs_service.human_size
templates.env.globals["low_power_enabled"] = low_power_enabled
templates.env.globals["assistant_enabled"] = assistant_enabled
templates.env.globals["static_url"] = static_url

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


def _redirect_if_unauthed(request: Request) -> RedirectResponse | None:
    """Return a redirect to the login page when the request is not authed."""
    if not is_authed(request):
        return RedirectResponse("/admin/login", status_code=303)
    return None


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
    if (redirect := _redirect_if_unauthed(request)) is not None:
        return redirect

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


# --- Library browser --------------------------------------------------------
#
# A complete, previewable view of every guide, journey, and md skill on the
# node, so an operator can see what is there and what is thin — the dashboard
# only shows category counts. Reads the same SQLite metadata as the public UI
# plus md skills straight off disk (they have no public page).


def _skill_files() -> list[dict]:
    """List md skills on disk with their front-matter id/title.

    md skills steer the assistant's values/style and are not stored in SQLite,
    so we read them directly from the content directory. Keyed by file *stem*
    (a stable slug) for the preview route, since ids may repeat the filename.
    """
    from horizon.seed import _split_front_matter

    skills_dir = Path(settings.content_dir) / "md_skills"
    skills: list[dict] = []
    if not skills_dir.is_dir():
        return skills
    for md_path in sorted(skills_dir.glob("*.md")):
        meta, body = _split_front_matter(md_path.read_text(encoding="utf-8"))
        skills.append(
            {
                "slug": md_path.stem,
                "id": meta.get("id") or md_path.stem,
                "title": meta.get("title") or md_path.stem,
                "thin": len(body.strip()) < 200,
            }
        )
    return skills


@router.get("/admin/library", response_class=HTMLResponse)
def library(request: Request, session: SessionDep):
    """Browse the whole library: every guide, journey, and md skill on the node."""
    if (redirect := _redirect_if_unauthed(request)) is not None:
        return redirect

    # How many journeys link each guide, so we can flag guides nothing points to.
    link_counts: Counter[str] = Counter(session.exec(select(JourneyGuideLink.guide_id)).all())

    guides = []
    for g in session.exec(select(Guide).order_by(Guide.category, Guide.id)).all():
        used = link_counts.get(g.id, 0)
        flags = []
        if not g.summary.strip():
            flags.append("no summary")
        if used == 0:
            flags.append("no journey links")
        guides.append(
            {
                "id": g.id,
                "title": g.title,
                "category": g.category.value,
                "summary": g.summary,
                "journeys": used,
                "flags": flags,
            }
        )

    guide_link_counts: Counter[str] = Counter(
        session.exec(select(JourneyGuideLink.journey_id)).all()
    )
    prereq_counts: Counter[str] = Counter(
        session.exec(select(JourneyPrerequisite.journey_id)).all()
    )

    journeys = []
    for j in session.exec(
        select(Journey).order_by(Journey.category, Journey.difficulty, Journey.id)
    ).all():
        n_guides = guide_link_counts.get(j.id, 0)
        flags = []
        if n_guides == 0:
            flags.append("no guides")
        if not j.description.strip():
            flags.append("no description")
        journeys.append(
            {
                "id": j.id,
                "title": j.title,
                "category": j.category.value,
                "difficulty": j.difficulty,
                "guides": n_guides,
                "prerequisites": prereq_counts.get(j.id, 0),
                "flags": flags,
            }
        )

    skills = _skill_files()

    totals = {
        "guides": len(guides),
        "journeys": len(journeys),
        "skills": len(skills),
        "thin": sum(1 for g in guides if g["flags"])
        + sum(1 for j in journeys if j["flags"])
        + sum(1 for s in skills if s["thin"]),
    }

    return templates.TemplateResponse(
        request,
        "admin/library.html",
        {"guides": guides, "journeys": journeys, "skills": skills, "totals": totals},
    )


@router.get("/admin/library/guides/{guide_id}", response_class=HTMLResponse)
def library_guide(guide_id: str, request: Request, session: SessionDep):
    """Preview a single guide (rendered Markdown) inside the admin panel."""
    if (redirect := _redirect_if_unauthed(request)) is not None:
        return redirect
    from horizon.api.guides import _read_body
    from horizon.services.markdown import render_markdown

    guide = session.get(Guide, guide_id)
    if guide is None:
        return HTMLResponse("Guide not found", status_code=404)
    return templates.TemplateResponse(
        request,
        "admin/library_item.html",
        {
            "kind": "Guide",
            "title": guide.title,
            "meta": {"id": guide.id, "category": guide.category.value, "summary": guide.summary},
            "public_url": f"/guides/{guide.id}",
            "body_html": render_markdown(_read_body(guide)),
        },
    )


@router.get("/admin/library/skills/{slug}", response_class=HTMLResponse)
def library_skill(slug: str, request: Request):
    """Preview a single md skill (rendered Markdown) inside the admin panel."""
    if (redirect := _redirect_if_unauthed(request)) is not None:
        return redirect
    from horizon.services.markdown import render_markdown

    md_path = Path(settings.content_dir) / "md_skills" / f"{slug}.md"
    if not md_path.is_file():
        return HTMLResponse("Skill not found", status_code=404)
    text = md_path.read_text(encoding="utf-8")
    from horizon.seed import _split_front_matter

    meta, _ = _split_front_matter(text)
    return templates.TemplateResponse(
        request,
        "admin/library_item.html",
        {
            "kind": "md skill",
            "title": meta.get("title") or slug,
            "meta": {"id": meta.get("id") or slug, "file": md_path.name},
            "public_url": None,
            "body_html": render_markdown(text),
        },
    )


@router.get("/admin/library/journeys/{journey_id}", response_class=HTMLResponse)
def library_journey(journey_id: str, request: Request, session: SessionDep):
    """Preview a single journey: its metadata, prerequisites, and linked guides."""
    if (redirect := _redirect_if_unauthed(request)) is not None:
        return redirect

    journey = session.get(Journey, journey_id)
    if journey is None:
        return HTMLResponse("Journey not found", status_code=404)

    prereq_ids = session.exec(
        select(JourneyPrerequisite.prerequisite_id).where(
            JourneyPrerequisite.journey_id == journey_id
        )
    ).all()
    prerequisites = [
        {"id": p.id, "title": p.title}
        for pid in prereq_ids
        if (p := session.get(Journey, pid)) is not None
    ]
    return templates.TemplateResponse(
        request,
        "admin/library_journey.html",
        {
            "journey": {
                "id": journey.id,
                "title": journey.title,
                "category": journey.category.value,
                "difficulty": journey.difficulty,
                "estimated_time": journey.estimated_time,
                "description": journey.description,
            },
            "prerequisites": prerequisites,
            "guides": [{"id": g.id, "title": g.title} for g in journey.guides],
            "public_url": f"/journeys/{journey.id}",
        },
    )


# --- Check & repair (health) ------------------------------------------------
#
# The operator's maintenance surface: a plain-language health view of what's
# wrong (broken links, missing files/images, a stale or absent search index,
# orphaned or duplicate content, the model runtime) plus the two one-click
# repairs that fix most of it — rebuild the index and re-seed from disk. All the
# logic lives in services/diagnostics.py; these routes only render and dispatch.


def _render_health(request: Request, *, check_model: bool, result: dict | None = None):
    """Render the health page (or just its body for an HTMX repair swap)."""
    from horizon.services.diagnostics import run_checks
    from horizon.services.eventlog import recent_events

    report = run_checks(check_model=check_model)
    context = {
        "report": report,
        "events": recent_events(limit=40),
        "low_power": low_power_enabled(),
        "checked_model": check_model,
        "result": result,
    }
    # HTMX repair posts swap only the live region; full loads render the page.
    template = "admin/_health_body.html" if "HX-Request" in request.headers else "admin/health.html"
    return templates.TemplateResponse(request, template, context)


@router.get("/admin/health", response_class=HTMLResponse)
def health_page(request: Request):
    """Diagnostics + repair view. Probes the model only when explicitly asked."""
    if (redirect := _redirect_if_unauthed(request)) is not None:
        return redirect
    # Probing the model runtime costs energy, so it is opt-in via ?check_model=1
    # and never done in low-power mode (where horizon ignores the model anyway).
    check_model = (
        request.query_params.get("check_model") in {"1", "true", "yes", "on"}
        and not low_power_enabled()
    )
    return _render_health(request, check_model=check_model)


@router.post("/admin/health/repair", response_class=HTMLResponse)
def health_repair(request: Request, action: Annotated[str, Form()] = ""):
    """Run a one-click repair, then re-render the health view with the outcome."""
    if (redirect := _redirect_if_unauthed(request)) is not None:
        return redirect
    from horizon.services.diagnostics import run_repair

    result = run_repair(action)
    # Without JS the form posts normally; redirect (PRG) so a refresh can't
    # re-run the repair. With HTMX we return the refreshed body fragment, which
    # carries the before/after result banner.
    if "HX-Request" not in request.headers:
        return RedirectResponse("/admin/health", status_code=303)
    return _render_health(request, check_model=False, result=result)


# --- Content packs wizard ---------------------------------------------------


def _pack_row(pack_id: str) -> dict | None:
    """Build the display row for one pack: catalog/disk state plus any live job."""
    for row in packs_service.pack_status():
        if row["id"] == pack_id:
            row["job"] = packs_service.download_manager.status(pack_id)
            return row
    return None


@router.get("/admin/packs", response_class=HTMLResponse)
def packs_page(request: Request):
    """Content-pack wizard: install/remove optional offline resources."""
    if (redirect := _redirect_if_unauthed(request)) is not None:
        return redirect
    rows = packs_service.pack_status()
    for row in rows:
        row["job"] = packs_service.download_manager.status(row["id"])
    return templates.TemplateResponse(
        request,
        "admin/packs.html",
        {"packs": rows, "packs_dir": settings.content_packs.dir},
    )


@router.post("/admin/packs/{pack_id}/download", response_class=HTMLResponse)
def packs_download(pack_id: str, request: Request):
    """Kick off a background download and return the pack's row fragment."""
    if (redirect := _redirect_if_unauthed(request)) is not None:
        return redirect
    if packs_service.get_spec(pack_id) is not None:
        packs_service.download_manager.start(pack_id)
    return _pack_row_fragment(request, pack_id)


@router.get("/admin/packs/{pack_id}/row", response_class=HTMLResponse)
def packs_row(pack_id: str, request: Request):
    """Return a single pack's row fragment (polled while a download runs)."""
    if (redirect := _redirect_if_unauthed(request)) is not None:
        return redirect
    return _pack_row_fragment(request, pack_id)


@router.post("/admin/packs/{pack_id}/remove", response_class=HTMLResponse)
def packs_remove(pack_id: str, request: Request):
    """Remove an installed pack and return its refreshed row fragment."""
    if (redirect := _redirect_if_unauthed(request)) is not None:
        return redirect
    packs_service.remove_pack(pack_id)
    return _pack_row_fragment(request, pack_id)


def _pack_row_fragment(request: Request, pack_id: str) -> HTMLResponse:
    row = _pack_row(pack_id)
    if row is None:
        return HTMLResponse("", status_code=404)
    return templates.TemplateResponse(request, "admin/_pack_row.html", {"pack": row})


# --- Optional integrations status ------------------------------------------


@router.get("/admin/integrations", response_class=HTMLResponse)
def integrations_page(request: Request):
    """Show the status of horizon's optional, opt-in integrations."""
    if (redirect := _redirect_if_unauthed(request)) is not None:
        return redirect

    from horizon.services import llm

    low_power = low_power_enabled()
    # When low-power mode is on, horizon never reaches for the model, so don't
    # probe it (the network call itself costs energy and time on a weak supply).
    llm_reachable = False if low_power else llm.available()
    installed = len(packs_service.installed_packs())
    available = len(packs_service.load_catalog())

    integrations = [
        {
            "name": "Web UI",
            "detail": "config web.enabled · env HORIZON_WEB_ENABLED",
            "state": "on" if web_enabled() else "off",
            "ok": web_enabled(),
            "note": (
                "This browser interface. It is optional: with the horizon-admin "
                "CLI an operator can run a node with the UI off, leaving only the "
                "JSON API and the command line. (You are seeing this page, so it "
                "is on.)"
            ),
        },
        {
            "name": "Chat assistant",
            "detail": "config assistant.enabled · env HORIZON_ASSISTANT_ENABLED",
            "state": "on" if assistant_enabled() else "off",
            "ok": assistant_enabled(),
            "note": (
                "The optional question box offered in the main menu. When off, the "
                "Ask a question link and page are hidden; journeys, guides, and "
                "recommendations are unaffected."
            ),
        },
        {
            "name": "Low-power mode",
            "detail": "config power.low_power · env HORIZON_LOW_POWER",
            "state": "on" if low_power else "off",
            "ok": low_power,
            "note": (
                "For solar / battery nodes. When on, horizon skips building the "
                "vector index and pauses the local model; the assistant answers "
                "from local guides via keyword search."
            ),
        },
        {
            "name": "Local model runtime",
            "detail": f"{settings.llm.provider} · {settings.llm.endpoint}",
            "state": "paused (low power)"
            if low_power
            else ("reachable" if llm_reachable else "unreachable"),
            "ok": llm_reachable,
            "note": (
                "Generates and embeds answers. When unreachable — or paused in "
                "low-power mode — the assistant falls back to keyword retrieval "
                "and points at local guides."
            ),
        },
        {
            "name": "moral-core ethics hook",
            "detail": settings.ethics.endpoint,
            "state": "enabled" if settings.ethics.enabled else "disabled",
            "ok": settings.ethics.enabled,
            "note": (
                "Optional answer refinement. Off by default; horizon always "
                "fails open to its own md-skill values if it is unreachable."
            ),
        },
        {
            "name": "Content packs",
            "detail": settings.content_packs.dir,
            "state": f"{installed} of {available} installed",
            "ok": installed > 0,
            "note": "Large optional offline resources (Wikipedia, medical, maps).",
        },
    ]
    return templates.TemplateResponse(
        request,
        "admin/integrations.html",
        {"integrations": integrations},
    )
