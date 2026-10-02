"""Shared YAML front-matter parsing for guides, checklists, and md skills.

Every content file is Markdown with an optional leading YAML block::

    ---
    id: water-boiling
    title: Boil water safely
    ---
    # Body...

The block is delimited by a ``---`` line at the very start of the file and the
next line consisting of only ``---``. Matching whole *lines* (rather than
splitting on the first ``---`` substring anywhere) matters: a title such as
``Part One --- Beginnings`` or a summary that is itself ``---`` must never be
mistaken for the closing delimiter.

Pure (no I/O, no database), so seeding, retrieval, diagnostics, and the admin
library all share one parser instead of four subtly different ones.
"""

from __future__ import annotations

import re

import yaml

# Opening ``---`` on the first line, then the shortest run of lines up to a line
# that is exactly ``---`` (trailing whitespace tolerated). ``\A`` anchors the
# opening fence to the start of the text; ``^``/``$`` (MULTILINE) anchor the
# closing one to a whole line.
_FRONT_MATTER_RE = re.compile(
    r"\A---[ \t]*\r?\n(?P<meta>.*?)^---[ \t]*(?:\r?\n|\Z)",
    re.DOTALL | re.MULTILINE,
)


class FrontMatterError(ValueError):
    """A file's front matter is present but unusable (bad YAML, not a mapping)."""


def _match(text: str) -> re.Match[str] | None:
    return _FRONT_MATTER_RE.match(text.lstrip("﻿"))


def split_front_matter(text: str, *, strict: bool = False) -> tuple[dict, str]:
    """Split ``text`` into ``(meta, body)``.

    Text without a front-matter block returns ``({}, text)``. When the block is
    present but is not valid YAML, or does not parse to a mapping (e.g. a YAML
    list), ``strict=True`` raises :class:`FrontMatterError`; otherwise the
    metadata is treated as empty and the body is still returned, so read-only
    callers (search, the health view) degrade instead of crashing.
    """
    match = _match(text)
    if match is None:
        return {}, text
    body = text.lstrip("﻿")[match.end() :].lstrip("\r\n")
    try:
        meta = yaml.safe_load(match.group("meta"))
    except yaml.YAMLError as exc:
        if strict:
            raise FrontMatterError(f"invalid YAML front matter: {exc}") from exc
        return {}, body
    if meta is None:
        meta = {}
    if not isinstance(meta, dict):
        if strict:
            raise FrontMatterError(
                f"front matter must be a mapping of keys to values, not {type(meta).__name__}"
            )
        return {}, body
    return meta, body


def strip_front_matter(text: str) -> str:
    """Return only the Markdown body (never raises, whatever the metadata holds)."""
    match = _match(text)
    if match is None:
        return text
    return text.lstrip("﻿")[match.end() :].lstrip("\r\n")


def coerce_difficulty(value: object, *, default: int = 3) -> int:
    """Turn a front-matter ``difficulty`` into an int clamped to 1-5.

    Content is hand-written, so tolerate ``"2"``, ``2.0``, or ``easy``: anything
    non-numeric becomes ``default``, and out-of-range numbers are clamped rather
    than rejected.
    """
    if isinstance(value, bool):
        return default
    try:
        number = int(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return default
    return max(1, min(5, number))
