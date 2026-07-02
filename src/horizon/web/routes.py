"""Server-rendered page routes for the horizon home UI.

Pages: landing, journeys (skill tree), journey detail, the guide viewer
(+ in-browser print via ``print.css``), and the AI assistant. Most pages are
thin, DB-direct views over the same data the Knowledge API exposes — no HTTP
self-calls. Only the assistant touches the LLM/vector path, and it degrades
gracefully (keyword retrieval + a local-content fallback) so the UI still works
fully offline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from horizon import __version__
from horizon.api.ai import AnswerRequest
from horizon.api.ai import answer as ai_answer
from horizon.api.guides import _read_body
from horizon.api.journeys import _guide_summary, _journey_summary, ordered_guides
from horizon.config import assistant_enabled, low_power_enabled, settings
from horizon.db import get_session
from horizon.models import Category, Checklist, Guide, Journey, JourneyGuideLink
from horizon.services import packs as packs_service
from horizon.services.markdown import render_markdown
from horizon.services.recommend import recommend_journeys
from horizon.web.assets import static_url

router = APIRouter(tags=["web"])

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
# Read live (honours the HORIZON_LOW_POWER env override) so every page reflects
# the current power mode without restarting.
templates.env.globals["low_power_enabled"] = low_power_enabled
templates.env.globals["assistant_enabled"] = assistant_enabled
templates.env.globals["static_url"] = static_url
templates.env.globals["version"] = __version__
# Only show the "Reference library" nav item once an operator has actually
# downloaded a ZIM pack -- a per-request on-disk check, cheap enough given
# horizon's low request volume; no caching layer added for this.
templates.env.globals["reference_library_enabled"] = packs_service.has_installed_zim_pack

SessionDep = Annotated[Session, Depends(get_session)]

CATEGORIES = [c.value for c in Category]

# One-line, plain-language example per category so a visitor scanning the home
# page can recognise their problem without knowing horizon's taxonomy.
CATEGORY_EXAMPLES = {
    "water": "Make river or rain water safe to drink",
    "food": "Grow staple crops and store a harvest",
    "energy": "Set up a small solar and battery system",
    "shelter": "Keep a simple shelter warm and dry",
    "health": "First aid and staying healthy off-grid",
    "cooperation": "Make fair group decisions together",
    "survival": "Make fire, find water, and find your way",
    "culture": "Music, dance, and games with no gear",
    "language": "Learn and teach essential words",
    "crafts": "Make rope, mend clothes, and fix tools",
    "emergencies": "Stay safe in blackouts, disasters, and conflict",
    "cooking": "Cook and bake simple plant-based meals",
    "calculations": "Size a system, a room, or a load",
}


def _category_cards() -> list[dict]:
    """Category name plus its plain-language example, for the home page tiles."""
    return [{"name": c, "example": CATEGORY_EXAMPLES.get(c, "")} for c in CATEGORIES]


@router.get("/", response_class=HTMLResponse)
def landing(request: Request) -> HTMLResponse:
    """Landing view: the skill categories and what horizon is for."""
    return templates.TemplateResponse(request, "landing.html", {"categories": _category_cards()})


@router.get("/journeys", response_class=HTMLResponse)
def journeys_page(
    request: Request,
    session: SessionDep,
    category: str | None = None,
) -> HTMLResponse:
    """List the curated step-by-step plans (tracks), optionally by category.

    Each track previews its ordered guides so a visitor sees the path at a
    glance and can jump straight to any guide. A track needs at least two
    linked guides to be a real plan (CLAUDE.md: a single guide never needs one
    wrapped around it) — seeding already enforces this, but it is filtered out
    here too as a defensive backstop.
    """
    if category is not None and category not in set(Category):
        raise HTTPException(status_code=400, detail=f"Unknown category: {category}")

    statement = select(Journey)
    if category is not None:
        statement = statement.where(Journey.category == Category(category))
    statement = statement.order_by(Journey.category, Journey.difficulty, Journey.id)

    tracks = []
    for journey in session.exec(statement).all():
        guides = [_guide_summary(g) for g in ordered_guides(session, journey.id)]
        if len(guides) < 2:
            continue
        data = _journey_summary(journey)
        data["guides"] = guides
        tracks.append(data)

    # Only show category filters that actually have a track, so the chips never
    # lead to an empty page.
    track_categories = sorted({t["category"] for t in tracks}, key=CATEGORIES.index)

    return templates.TemplateResponse(
        request,
        "journeys.html",
        {
            "tracks": tracks,
            "categories": track_categories,
            "selected_category": category,
        },
    )


@router.get("/journeys/{journey_id}", response_class=HTMLResponse)
def journey_detail_page(
    journey_id: str,
    request: Request,
    session: SessionDep,
) -> HTMLResponse:
    """Show a track as an ordered list of guides linking straight to each guide."""
    journey = session.get(Journey, journey_id)
    if journey is None:
        raise HTTPException(status_code=404, detail=f"Journey not found: {journey_id}")

    guides = [_guide_summary(g) for g in ordered_guides(session, journey_id)]
    if len(guides) < 2:
        raise HTTPException(status_code=404, detail=f"Journey not found: {journey_id}")

    data = _journey_summary(journey)
    data["guides"] = guides

    return templates.TemplateResponse(request, "journey_detail.html", {"journey": data})


@router.get("/guides", response_class=HTMLResponse)
def guides_page(
    request: Request,
    session: SessionDep,
    category: str | None = None,
    q: str | None = None,
) -> HTMLResponse:
    """Browse all guides, optionally filtered by category and a search term."""
    if category is not None and category not in set(Category):
        raise HTTPException(status_code=400, detail=f"Unknown category: {category}")

    statement = select(Guide)
    if category is not None:
        statement = statement.where(Guide.category == Category(category))
    statement = statement.order_by(Guide.category, Guide.id)
    guides = [_guide_summary(g) for g in session.exec(statement).all()]

    # Plain substring search over title and summary so visitors can find a guide
    # by name without learning the categories. Kept in-process (no LLM/index) so
    # it works fully offline and on minimal hardware.
    query = (q or "").strip()
    if query:
        needle = query.lower()
        guides = [
            g
            for g in guides
            if needle in g["title"].lower() or needle in (g["summary"] or "").lower()
        ]

    return templates.TemplateResponse(
        request,
        "guides.html",
        {
            "guides": guides,
            "categories": CATEGORIES,
            "selected_category": category,
            "query": query,
        },
    )


@router.get("/guides/{guide_id}.pdf")
def guide_pdf(guide_id: str, session: SessionDep) -> Response:
    """Render a guide as a downloadable, A4 print-friendly PDF (WeasyPrint).

    WeasyPrint is imported lazily so the rest of the UI still boots and serves
    where its system libraries are unavailable; in that case this route fails
    rather than the whole app.
    """
    guide = session.get(Guide, guide_id)
    if guide is None:
        raise HTTPException(status_code=404, detail=f"Guide not found: {guide_id}")

    from horizon.services.pdf import render_pdf

    document = templates.env.get_template("guide_pdf.html").render(
        guide=_guide_summary(guide),
        body_html=render_markdown(_read_body(guide)),
    )
    pdf_bytes = render_pdf(document)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{guide_id}.pdf"'},
    )


@router.get("/guides/{guide_id}", response_class=HTMLResponse)
def guide_page(
    guide_id: str,
    request: Request,
    session: SessionDep,
) -> HTMLResponse:
    """Render a guide's Markdown for reading and printing."""
    guide = session.get(Guide, guide_id)
    if guide is None:
        raise HTTPException(status_code=404, detail=f"Guide not found: {guide_id}")

    body_html = render_markdown(_read_body(guide))

    # Curated tracks this guide is part of, so a reader can pick up the wider
    # step-by-step plan it belongs to.
    track_ids = session.exec(
        select(JourneyGuideLink.journey_id).where(JourneyGuideLink.guide_id == guide_id)
    ).all()
    in_tracks = [
        _journey_summary(j) for jid in track_ids if (j := session.get(Journey, jid)) is not None
    ]

    return templates.TemplateResponse(
        request,
        "guide.html",
        {
            "guide": _guide_summary(guide),
            "body_html": body_html,
            "in_tracks": in_tracks,
        },
    )


def _checklist_summary(checklist: Checklist) -> dict:
    """Plain dict for a checklist (mirrors ``_guide_summary``)."""
    return {
        "id": checklist.id,
        "title": checklist.title,
        "category": checklist.category.value if checklist.category else None,
        "summary": checklist.summary,
    }


def _read_checklist_body(checklist: Checklist) -> str:
    """Read a checklist's Markdown body from the content directory."""
    md_path = Path(settings.content_dir) / "checklists" / checklist.path
    if not md_path.is_file():
        raise HTTPException(
            status_code=404, detail=f"Checklist file missing on disk: {checklist.path}"
        )
    return md_path.read_text(encoding="utf-8")


@router.get("/checklists", response_class=HTMLResponse)
def checklists_page(request: Request, session: SessionDep) -> HTMLResponse:
    """List all checklists — printable lists of things to gather, pack, or do."""
    statement = select(Checklist).order_by(Checklist.title, Checklist.id)
    checklists = [_checklist_summary(c) for c in session.exec(statement).all()]
    return templates.TemplateResponse(
        request,
        "checklists.html",
        {"checklists": checklists},
    )


@router.get("/checklists/{checklist_id}", response_class=HTMLResponse)
def checklist_page(
    checklist_id: str,
    request: Request,
    session: SessionDep,
) -> HTMLResponse:
    """Render a single checklist with tick-able, printable items."""
    checklist = session.get(Checklist, checklist_id)
    if checklist is None:
        raise HTTPException(status_code=404, detail=f"Checklist not found: {checklist_id}")

    body_html = render_markdown(_read_checklist_body(checklist))

    return templates.TemplateResponse(
        request,
        "checklist.html",
        {
            "checklist": _checklist_summary(checklist),
            "body_html": body_html,
        },
    )


@router.get("/recommend", response_class=HTMLResponse)
def recommend_page(
    request: Request,
    goal: str | None = None,
    people: int | None = None,
    climate: str | None = None,
    resources: str | None = None,
) -> HTMLResponse:
    """Scenario helper: suggest journeys/guides for a goal and simple context."""
    resource_list = [r.strip() for r in (resources or "").split(",") if r.strip()]

    results = None
    if goal and goal.strip():
        results = recommend_journeys(
            goal,
            people=people,
            climate=climate,
            resources=resource_list or None,
        )

    return templates.TemplateResponse(
        request,
        "recommend.html",
        {
            "results": results,
            "categories": CATEGORIES,
            "form": {
                "goal": goal or "",
                "climate": climate or "",
                "resources": resources or "",
            },
        },
    )


@router.get("/assistant", response_class=HTMLResponse)
def assistant_page(request: Request) -> HTMLResponse:
    """The local AI assistant: ask a question, get a cited, locally-grounded answer.

    Resolve the assistant's live state up front so the page can set expectations
    *before* the visitor types: full written answers, energy-saving low-power
    mode, or model-off (guides-only). ``model_off`` is only reached when not in
    low-power mode, where probing the runtime would waste energy.
    """
    if not assistant_enabled():
        state = "disabled"
    elif low_power_enabled():
        state = "low_power"
    else:
        from horizon.services import llm

        state = "ready" if llm.available() else "model_off"

    return templates.TemplateResponse(
        request,
        "assistant.html",
        {"state": state, "no_jargon_default": settings.ai.no_jargon_default},
    )


@router.post("/assistant/answer", response_class=HTMLResponse)
def assistant_answer(
    request: Request,
    session: SessionDep,
    question: Annotated[str, Form()] = "",
    no_jargon: Annotated[bool, Form()] = False,
) -> HTMLResponse:
    """Answer a question and render it as an HTMX fragment with cited guides.

    Reuses the AI API's answer logic directly (no HTTP self-call) and resolves
    citation ids to guide titles for display.
    """
    if not assistant_enabled():
        return templates.TemplateResponse(
            request,
            "partials/_answer.html",
            {
                "answer_html": render_markdown(
                    "The assistant has been turned off by the operator. "
                    "Browse the [step-by-step plans](/journeys) and "
                    "[how-to guides](/guides) instead."
                ),
                "citations": [],
            },
        )

    result = ai_answer(AnswerRequest(question=question, no_jargon=no_jargon))

    citations = [
        {"id": guide.id, "title": guide.title}
        for cid in result.citations
        if (guide := session.get(Guide, cid)) is not None
    ]

    return templates.TemplateResponse(
        request,
        "partials/_answer.html",
        {
            "answer_html": render_markdown(result.answer),
            "citations": citations,
        },
    )
