"""Optional ethics refinement via an external moral-core service.

This is a pure, opt-in refinement. It is DISABLED by default
(``settings.ethics.enabled``). horizon must never hard-depend on moral-core: if
the hook is disabled or the endpoint is unreachable, draft answers pass through
unchanged, relying on horizon's built-in md skills and system prompt.

NOTE: stub for v0.1 scaffold — implemented in the optional-integrations step.
"""

from __future__ import annotations

from horizon.config import settings


def refine_answer(answer: str, context: dict | None = None) -> str:
    """Optionally refine a draft answer via moral-core; fail open to the input."""
    if not settings.ethics.enabled:
        return answer
    raise NotImplementedError("Implemented in the optional-integrations step.")
