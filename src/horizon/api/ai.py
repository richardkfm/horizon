"""AI API: answer questions using local RAG over guides + md skills.

Answers are generated with a fixed system prompt (horizon's purpose and values)
plus retrieved guides and md skills, and always cite the guide/journey ids used.
If the optional ethics hook is enabled, draft answers are refined via moral-core;
otherwise horizon relies solely on its built-in md skills.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/ai", tags=["ai"])


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
    raise NotImplementedError("Implemented in the RAG + AI assistant step.")
