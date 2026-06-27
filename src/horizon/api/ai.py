"""AI API: answer questions using local RAG over guides + md skills.

Answers are generated with a fixed system prompt (horizon's purpose and values)
plus retrieved guides and md skills, and always cite the guide ids used. If the
optional ethics hook is enabled, draft answers are refined via moral-core;
otherwise horizon relies solely on its built-in md skills.

The endpoint is offline-first: retrieval always works (keyword fallback), and if
the local model is unavailable the answer degrades to a deterministic pointer to
the most relevant local guides — it never returns an error for that case.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from horizon.config import settings
from horizon.services.llm import LLMUnavailable, generate
from horizon.services.rag import retrieve

logger = logging.getLogger("horizon")

router = APIRouter(prefix="/api/ai", tags=["ai"])

# Base instructions; horizon's values/answer-style md skills are appended at
# runtime so value judgements stay in content, not code (see CLAUDE.md).
_BASE_SYSTEM = (
    "You are horizon's local assistant for practical autonomy and rebuilding: "
    "water, food, energy, shelter, health, and cooperative governance. You run "
    "fully offline on constrained hardware. Answer ONLY from the provided local "
    "context (guides and notes). If the context does not cover the question, say "
    "so plainly rather than inventing details. Be practical and step-by-step, "
    "warn about safety-critical risks up front, and cite the guide ids you used."
)

# md skills that should always steer answers, regardless of what retrieval found.
_STEERING_SKILLS = ("values", "answer-style")


class AnswerRequest(BaseModel):
    question: str
    context: dict | None = None
    no_jargon: bool | None = None


class AnswerResponse(BaseModel):
    answer: str
    citations: list[str]  # guide_ids / journey_ids backing the answer


@router.post("/answer", response_model=AnswerResponse)
def answer(req: AnswerRequest) -> AnswerResponse:
    """Answer a question with locally-retrieved, cited content."""
    question = (req.question or "").strip()
    if not question:
        return AnswerResponse(
            answer="Please ask a question about water, food, energy, shelter, "
            "health, or cooperation.",
            citations=[],
        )

    chunks = retrieve(question)
    citations = _citations(chunks)

    no_jargon = req.no_jargon if req.no_jargon is not None else settings.ai.no_jargon_default
    system = _system_prompt()
    prompt = _build_prompt(question, chunks)

    try:
        draft = generate(system, prompt, no_jargon=no_jargon)
    except LLMUnavailable:
        logger.info("LLM unavailable; returning local-content fallback answer.")
        draft = _fallback_answer(chunks)

    final = _refine(draft, req.context)
    return AnswerResponse(answer=final, citations=citations)


def _citations(chunks: list[dict]) -> list[str]:
    """Unique guide source ids from retrieved chunks, in retrieval order."""
    seen: set[str] = set()
    citations: list[str] = []
    for chunk in chunks:
        if chunk["kind"] != "guide":
            continue
        source_id = chunk["source_id"]
        if source_id not in seen:
            seen.add(source_id)
            citations.append(source_id)
    return citations


def _build_prompt(question: str, chunks: list[dict]) -> str:
    """Assemble the user prompt: retrieved context followed by the question."""
    if chunks:
        blocks = [f"[{chunk['source_id']}] {chunk['title']}\n{chunk['text']}" for chunk in chunks]
        context = "\n\n---\n\n".join(blocks)
    else:
        context = "(no local content matched this question)"
    return (
        "Local context from horizon's guides and notes:\n\n"
        f"{context}\n\n"
        f"Question: {question}\n\n"
        "Answer using only the context above. Cite the guide ids (in square "
        "brackets) you relied on."
    )


@lru_cache(maxsize=1)
def _system_prompt() -> str:
    """Base prompt plus the values/answer-style md skills (cached)."""
    parts = [_BASE_SYSTEM]
    skills_dir = Path(settings.content_dir) / "md_skills"
    for skill_id in _STEERING_SKILLS:
        body = _read_skill_body(skills_dir / f"{skill_id}.md")
        if body:
            parts.append(body)
    return "\n\n".join(parts)


def _read_skill_body(path: Path) -> str | None:
    """Return an md skill's body (front matter stripped), or ``None`` if absent."""
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        segments = text.split("---", 2)
        if len(segments) == 3:
            return segments[2].lstrip("\n")
    return text


def _fallback_answer(chunks: list[dict]) -> str:
    """Deterministic answer when the model is unavailable: point to local guides."""
    guides = [c for c in chunks if c["kind"] == "guide"]
    if not guides:
        return (
            "The local AI model isn't running right now, and I couldn't find a "
            "local guide matching your question. Try browsing the journeys, or "
            "rephrase your question."
        )
    seen: set[str] = set()
    lines: list[str] = []
    for guide in guides:
        if guide["source_id"] in seen:
            continue
        seen.add(guide["source_id"])
        lines.append(f"- {guide['title']} [{guide['source_id']}]")
    listing = "\n".join(lines)
    return (
        "The local AI model isn't running right now, so I can't write a full "
        "answer. Based on your question, these local guides are most relevant:\n\n"
        f"{listing}\n\n"
        "Open them for complete step-by-step instructions."
    )


def _refine(draft: str, context: dict | None) -> str:
    """Optionally refine via the moral-core ethics hook; always fail open.

    horizon must never hard-depend on moral-core: if the hook is disabled,
    unreachable, or not yet implemented, the draft passes through unchanged.
    """
    from horizon.services.ethics import refine_answer

    try:
        return refine_answer(draft, context=context)
    except Exception as exc:  # noqa: BLE001 - fail open to horizon's own answer
        logger.warning("Ethics refinement unavailable; using draft answer: %s", exc)
        return draft
