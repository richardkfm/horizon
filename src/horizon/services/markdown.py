"""Render guide Markdown to HTML for the web UI.

Pure, offline rendering with ``markdown-it-py`` — no network, no LLM. Guides on
disk carry YAML front matter (``id``/``title``/``category``/``summary``); the
helpers here strip that block before rendering so only the body becomes HTML.

On top of CommonMark + GFM tables, guides can use **callouts** for the
"which should I pick?" content added in v0.3. A callout is just a normal
blockquote whose first line is a recognised **bold label** — e.g.::

    > **Pick this if:** your water is cloudy or from a river.

    > **Spec:** 60 cm sand bed, ~0.1 m/h flow.

    > **Do now:** get out, stay out, and call for help.

The renderer tags such blockquotes with a ``callout callout-<kind>`` class so
the stylesheet can give them a distinct, scannable look (and print/e-ink keep
high contrast). Crucially this degrades gracefully: anywhere the class is not
styled — another renderer, a plain Markdown view — the callout is still a valid
blockquote with a bold label, so no meaning is lost and nothing breaks offline.

Three more guide conventions are handled here, all pure-Markdown and graceful:

* **Figures.** A paragraph that contains nothing but a single image is wrapped in
  ``<figure>``/``<figcaption>``, using the image's *alt text* as the caption
  (write it like ``![Fig. 1: a simple solar shower](images/shower.svg)``). Line
  drawings render the same on screen, on paper, and on e-ink.
* **ASCII diagrams.** A fenced code block tagged ``ascii`` followed by an
  ``*italic caption*`` paragraph is wrapped the same way, e.g.::

      ```ascii
      +-----------+
      |   sand    |
      +-----------+
      ```

      *Fig. 1: filter cross-section*

  Plain monospace line art needs no image file, renders identically in a
  browser, a printed page, and a plain-text/CLI view of the guide source, and
  is trivial to keep in version control. The fence always gets the figure
  card treatment; the ``<figcaption>`` is only added when an italic caption
  paragraph follows it.
* **Checklists.** GFM task-list items (``- [ ] item`` / ``- [x] item``) become
  real ``<input type="checkbox">`` boxes inside a ``task-list``. The check state
  is purely client-side (localStorage); with no styling/JS it still reads as a
  plain checklist and prints as empty squares.
"""

from __future__ import annotations

import re
from functools import lru_cache
from html import escape

from markdown_it import MarkdownIt
from markdown_it.token import Token

# Recognised callout labels → kind (the CSS modifier). Matched case-insensitively
# against the bold label that opens a blockquote, with any trailing colon
# stripped. Synonyms map to the same kind so guide authors can write naturally.
_CALLOUT_LABELS: dict[str, str] = {
    "pick this if": "pick",
    "choose this if": "pick",
    "good for": "pick",
    "avoid if": "avoid",
    "skip if": "avoid",
    "not for": "avoid",
    "spec": "spec",
    "specs": "spec",
    "at a glance": "spec",
    "decide": "decision",
    "decision": "decision",
    "rule of thumb": "decision",
    "risk": "risk",
    "warning": "risk",
    "caution": "risk",
    "do now": "now",
    "act now": "now",
    "right now": "now",
    "tip": "tip",
    "note": "note",
}


def _add_class(existing: str | None, name: str) -> str:
    """Append a CSS class to an attribute value, preserving existing classes.

    Idempotent: a class already present is not added again, so a rule that fires
    once per list item still leaves the list with a single ``task-list`` class.
    """
    classes = (existing or "").split()
    if name not in classes:
        classes.append(name)
    return " ".join(classes)


# A task-list marker opening a list item's text: ``[ ]`` / ``[x]`` / ``[X]``
# followed by whitespace. Mirrors GFM so guide authors write checklists naturally.
_TASK_MARKER = re.compile(r"\[([ xX])\]\s+")


def _callout_kind(label: str) -> str | None:
    """Map a blockquote's opening bold label to a callout kind, if recognised."""
    return _CALLOUT_LABELS.get(label.strip().rstrip(":").strip().lower())


def _tag_callouts(state) -> None:  # noqa: ANN001 - markdown-it core rule state
    """Core rule: class-tag blockquotes that open with a recognised bold label.

    Walks the block token stream and, for every ``blockquote_open`` whose first
    child paragraph starts with a ``strong`` run (a ``**Label**``), adds a
    ``callout callout-<kind>`` class when the label is one we know. Leaves every
    other blockquote untouched, so ordinary quotes render as before.
    """
    tokens: list[Token] = state.tokens
    for i, token in enumerate(tokens):
        if token.type != "blockquote_open":
            continue
        # blockquote_open → paragraph_open → inline (the first line's content).
        if i + 2 >= len(tokens):
            continue
        if tokens[i + 1].type != "paragraph_open":
            continue
        inline = tokens[i + 2]
        if inline.type != "inline" or not inline.children:
            continue
        # Skip a leading empty text child (markdown-it emits one before strong).
        children = [c for c in inline.children if not (c.type == "text" and not c.content)]
        # The line must open with a bold run: strong_open, text, strong_close.
        if len(children) < 3 or children[0].type != "strong_open":
            continue
        if children[1].type != "text":
            continue
        kind = _callout_kind(children[1].content)
        if kind is None:
            continue
        existing = token.attrGet("class")
        classes = f"{existing} callout callout-{kind}" if existing else f"callout callout-{kind}"
        token.attrSet("class", classes)


def _wrap_figures(state) -> None:  # noqa: ANN001 - markdown-it core rule state
    """Core rule: wrap a lone-image paragraph in ``<figure>`` + ``<figcaption>``.

    A paragraph whose only meaningful content is a single image becomes a figure,
    with the image's alt text used as a visible caption. Any other paragraph —
    including one with text alongside an image — is left untouched, so inline
    images keep working as before.
    """
    out: list[Token] = []
    tokens: list[Token] = state.tokens
    n = len(tokens)
    i = 0
    while i < n:
        token = tokens[i]
        if (
            token.type == "paragraph_open"
            and i + 2 < n
            and tokens[i + 1].type == "inline"
            and tokens[i + 2].type == "paragraph_close"
        ):
            inline = tokens[i + 1]
            kids = [
                c
                for c in (inline.children or [])
                if not (c.type == "text" and not c.content.strip())
            ]
            if len(kids) == 1 and kids[0].type == "image":
                image = kids[0]
                caption = (image.content or image.attrGet("alt") or "").strip()
                inline.children = [image]  # drop stray empty text nodes
                token.tag = "figure"
                token.attrSet("class", _add_class(token.attrGet("class"), "guide-figure"))
                close = tokens[i + 2]
                close.tag = "figure"
                out.append(token)
                out.append(inline)
                if caption:
                    cap = Token("html_block", "", 0)
                    cap.content = f"<figcaption>{escape(caption)}</figcaption>\n"
                    out.append(cap)
                out.append(close)
                i += 3
                continue
        out.append(token)
        i += 1
    state.tokens = out


def _wrap_ascii_diagrams(state) -> None:  # noqa: ANN001 - markdown-it core rule state
    """Core rule: wrap a fenced ` ```ascii ` block in ``<figure>`` + ``<figcaption>``.

    Mirrors ``_wrap_figures`` for plain-text line art: write a diagram as a
    fenced code block tagged ``ascii`` followed by an ``*italic caption*``
    paragraph, e.g.::

        ```ascii
        +-----------+
        |   sand    |
        +-----------+
        ```

        *Fig. 1: filter cross-section*

    and it gets the same captioned card as an image figure. The fence itself is
    untouched HTML-escaped text, so it still reads correctly with no styling at
    all — raw Markdown in a CLI, a plain ``cat``, or any other renderer. Every
    ``ascii`` fence gets the figure card; the caption is only added when an
    italic paragraph immediately follows it.
    """
    out: list[Token] = []
    tokens: list[Token] = state.tokens
    n = len(tokens)
    i = 0
    while i < n:
        token = tokens[i]
        if token.type == "fence" and (token.info or "").strip().lower() == "ascii":
            caption = None
            consumed = 1
            if (
                i + 3 < n
                and tokens[i + 1].type == "paragraph_open"
                and tokens[i + 2].type == "inline"
                and tokens[i + 3].type == "paragraph_close"
            ):
                # Only a *wholly italic* paragraph counts as this fence's caption,
                # so an ordinary paragraph that merely follows the diagram is
                # never swallowed by mistake.
                children = tokens[i + 2].children or []
                if (
                    len(children) >= 2
                    and children[0].type == "em_open"
                    and children[-1].type == "em_close"
                ):
                    text = "".join(c.content for c in children[1:-1]).strip()
                    if text:
                        caption = text
                        consumed = 4
            open_tok = Token("html_block", "", 0)
            open_tok.content = '<figure class="guide-figure guide-ascii">\n'
            out.append(open_tok)
            out.append(token)
            if caption:
                cap = Token("html_block", "", 0)
                cap.content = f"<figcaption>{escape(caption)}</figcaption>\n"
                out.append(cap)
            close_tok = Token("html_block", "", 0)
            close_tok.content = "</figure>\n"
            out.append(close_tok)
            i += consumed
            continue
        out.append(token)
        i += 1
    state.tokens = out


def _render_task_lists(state) -> None:  # noqa: ANN001 - markdown-it core rule state
    """Core rule: turn ``- [ ]``/``- [x]`` list items into real checkboxes.

    Each matching item gets a leading ``<input type="checkbox">`` (checked for
    ``[x]``), its ``list_item`` is tagged ``task-item``, and the enclosing list is
    tagged ``task-list`` so the stylesheet can drop the bullet. The checkbox is
    not disabled: the checklist pages persist its state locally (localStorage).
    """
    tokens: list[Token] = state.tokens
    list_stack: list[Token] = []
    for i, token in enumerate(tokens):
        if token.type in ("bullet_list_open", "ordered_list_open"):
            list_stack.append(token)
        elif token.type in ("bullet_list_close", "ordered_list_close"):
            if list_stack:
                list_stack.pop()
        elif (
            token.type == "inline"
            and i >= 2
            and tokens[i - 1].type == "paragraph_open"
            and tokens[i - 2].type == "list_item_open"
        ):
            child = token.children[0] if token.children else None
            if child is None or child.type != "text":
                continue
            match = _TASK_MARKER.match(child.content)
            if match is None:
                continue
            checked = match.group(1).lower() == "x"
            child.content = child.content[match.end() :]
            box = Token("html_inline", "", 0)
            attr = " checked" if checked else ""
            box.content = f'<input type="checkbox" class="task-check"{attr}> '
            token.children.insert(0, box)
            item = tokens[i - 2]
            item.attrSet("class", _add_class(item.attrGet("class"), "task-item"))
            if list_stack:
                lst = list_stack[-1]
                lst.attrSet("class", _add_class(lst.attrGet("class"), "task-list"))


@lru_cache(maxsize=1)
def _parser() -> MarkdownIt:
    """Return a shared CommonMark parser with GFM tables and horizon rules."""
    md = MarkdownIt("commonmark").enable("table")
    md.core.ruler.push("horizon_callouts", _tag_callouts)
    md.core.ruler.push("horizon_figures", _wrap_figures)
    md.core.ruler.push("horizon_ascii_diagrams", _wrap_ascii_diagrams)
    md.core.ruler.push("horizon_task_lists", _render_task_lists)
    return md


def strip_front_matter(text: str) -> str:
    """Drop a leading ``---`` YAML front-matter block, returning the body.

    Mirrors the split in ``seed._split_front_matter`` but keeps this service free
    of any database/seed import so it stays pure and unit-testable.
    """
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            return parts[2].lstrip("\n")
    return text


def render_markdown(text: str) -> str:
    """Render Markdown to an HTML fragment, ignoring any front matter."""
    return _parser().render(strip_front_matter(text))
