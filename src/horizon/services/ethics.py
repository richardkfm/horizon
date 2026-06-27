"""Optional ethics refinement via an external moral-core service.

This is a pure, opt-in refinement. It is DISABLED by default
(``settings.ethics.enabled``). horizon must never hard-depend on moral-core: if
the hook is disabled, unreachable, or returns anything unexpected, the draft
answer passes through unchanged, relying on horizon's built-in md skills and
system prompt. In other words it **fails open** — a broken or missing moral-core
can never break or censor horizon's own answers.

Contract with moral-core (kept deliberately small):

    POST <endpoint>
      { "answer": "<draft>", "context": { ... } }
    -> { "decision": "approve" | "adjust" | "block",
         "answer": "<refined answer>",   # used when decision == "adjust"
         "reason": "<short note>" }       # optional, shown when blocked

* ``approve`` (or any unknown decision): return the draft unchanged.
* ``adjust``: return moral-core's refined ``answer`` (falling back to the draft
  if it sent nothing usable).
* ``block``: replace the answer with a brief, non-authoritarian refusal that
  cites moral-core's reason, rather than silently dropping the question.

The call targets a local-network service, so like the LLM client it bypasses any
ambient HTTP proxy (``trust_env=False``) to stay offline-first.
"""

from __future__ import annotations

import logging

import httpx

from horizon.config import settings

logger = logging.getLogger("horizon")

# moral-core sits on the local network; keep the hook snappy so a slow or absent
# service never noticeably delays an answer (we fail open on timeout).
_TIMEOUT = httpx.Timeout(8.0, connect=3.0)

_BLOCK_PREFIX = "This answer was withheld by the ethics policy"


def refine_answer(answer: str, context: dict | None = None) -> str:
    """Optionally refine a draft answer via moral-core; fail open to the input.

    Returns the (possibly refined) answer. Never raises for an unreachable or
    misbehaving moral-core: any error degrades to the original ``answer``.
    """
    if not settings.ethics.enabled:
        return answer

    try:
        decision = _evaluate(answer, context)
    except httpx.HTTPError as exc:
        logger.warning("moral-core unreachable; using horizon's own answer: %s", exc)
        return answer
    except Exception as exc:  # noqa: BLE001 - any unexpected payload fails open
        logger.warning("moral-core returned an unusable response; failing open: %s", exc)
        return answer

    verdict = str(decision.get("decision", "approve")).lower()
    if verdict == "adjust":
        refined = (decision.get("answer") or "").strip()
        return refined or answer
    if verdict == "block":
        reason = (decision.get("reason") or "").strip()
        suffix = f": {reason}" if reason else "."
        return f"{_BLOCK_PREFIX}{suffix}"
    # approve / anything unrecognised: pass the draft through untouched.
    return answer


def _evaluate(answer: str, context: dict | None) -> dict:
    """POST the draft to moral-core and return the parsed JSON decision."""
    payload = {"answer": answer, "context": context or {}}
    # trust_env=False: keep this on the local network, never via an ambient proxy.
    with httpx.Client(trust_env=False, timeout=_TIMEOUT) as client:
        resp = client.post(settings.ethics.endpoint, json=payload)
        resp.raise_for_status()
        data = resp.json()
    if not isinstance(data, dict):
        raise ValueError("moral-core response was not a JSON object")
    return data
