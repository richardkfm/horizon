"""An in-memory ring buffer of recent log events, for the admin health feed.

The "check & repair" panel (Admin → Health) needs a readable recent-events feed
so an operator can see what the node has been doing — a seed, a reindex, an
embedding model falling back to keyword search — without SSHing in to tail a log
file. We attach a small, bounded :class:`logging.Handler` to horizon's ``horizon``
logger that keeps the last few hundred records in memory.

Deliberately tiny and offline-first: no log file to rotate, no external service,
no new dependency, and a fixed memory ceiling so it is safe on weak hardware. It
is *not* an audit log — the buffer is lost on restart, which is fine for a
live "what just happened" view.
"""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime
from threading import Lock

# Keep the last N records. A few hundred is plenty for a live feed and bounds the
# memory cost on a Raspberry Pi.
_CAPACITY = 300

_LOGGER_NAME = "horizon"


class RingBufferHandler(logging.Handler):
    """A logging handler that retains the most recent records in memory."""

    def __init__(self, capacity: int = _CAPACITY) -> None:
        super().__init__()
        self._records: deque[dict] = deque(maxlen=capacity)
        self._lock = Lock()

    def emit(self, record: logging.LogRecord) -> None:
        # Format defensively: a broken format string must never take down the
        # caller that was only trying to log.
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001 - never raise from a log handler
            message = record.msg if isinstance(record.msg, str) else repr(record.msg)
        entry = {
            "time": datetime.fromtimestamp(record.created),
            "level": record.levelname,
            "levelno": record.levelno,
            "message": message,
        }
        with self._lock:
            self._records.append(entry)

    def events(self, limit: int | None = None) -> list[dict]:
        """Return retained events, newest first (optionally capped to ``limit``)."""
        with self._lock:
            items = list(self._records)
        items.reverse()
        if limit is not None:
            items = items[:limit]
        return items


# Module-level singleton so every part of horizon shares one buffer.
_handler: RingBufferHandler | None = None


def install() -> RingBufferHandler:
    """Attach the ring-buffer handler to the ``horizon`` logger (idempotent).

    Called once at app startup (before seeding/indexing) so the feed captures the
    lifespan events too. Safe to call repeatedly — it only attaches once.
    """
    global _handler
    if _handler is None:
        _handler = RingBufferHandler()
        _handler.setLevel(logging.INFO)
    logger = logging.getLogger(_LOGGER_NAME)
    if _handler not in logger.handlers:
        logger.addHandler(_handler)
        # Ensure INFO records reach the handler even if no basicConfig ran; don't
        # clobber a lower level an operator may have set.
        if logger.level == logging.NOTSET or logger.level > logging.INFO:
            logger.setLevel(logging.INFO)
    return _handler


def recent_events(limit: int = 50) -> list[dict]:
    """Return the most recent log events (newest first) for the health feed."""
    if _handler is None:
        return []
    return _handler.events(limit=limit)
