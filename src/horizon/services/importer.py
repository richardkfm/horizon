"""Convert external sources (a how-to article, a public-domain book) into guides.

horizon's guide format is just Markdown with YAML front matter (see
``CLAUDE.md`` → *Adding content*). This module turns two common external
sources into that same format, so imported material is a guide like any
other:

* :func:`parse_html_article` + :func:`render_wikihow_guide` — a WikiHow-shaped
  how-to page (an ``<h1>`` title, intro paragraphs, then one or more
  ``<h2>``/``<h3>`` sections each holding an ``<ol>`` of steps). The same
  parser works for most "intro + numbered steps" how-to pages, not only
  wikihow.com.
* :func:`split_book_into_chapters` + :func:`render_book_guide` — a plain-text
  or Markdown book (e.g. a public-domain folklore or customs collection),
  split into one guide per detected chapter.

Everything here is pure (no network, no filesystem) so it is unit-testable
offline, matching the "keep core logic pure" rule in ``CLAUDE.md``: fetching a
URL or downloading an image is the caller's job (``horizon-content import``),
this module only turns already-fetched text into guide Markdown.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from html.parser import HTMLParser

import yaml

# --- shared helpers -----------------------------------------------------------

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    """Turn arbitrary text into a ``guide-id``-safe slug."""
    slug = _SLUG_RE.sub("-", text.strip().lower()).strip("-")
    return slug or "guide"


def reading_time(word_count: int, *, words_per_minute: int = 200) -> str:
    """A rough "N min read" estimate, never below one minute."""
    minutes = max(1, round(word_count / words_per_minute))
    return f"~{minutes} min read"


def _front_matter(
    *,
    guide_id: str,
    title: str,
    category: str,
    summary: str,
    difficulty: int,
    estimated_time: str,
) -> str:
    data = {
        "id": guide_id,
        "title": title,
        "category": category,
        "summary": summary,
        "difficulty": difficulty,
        "estimated_time": estimated_time,
    }
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True).strip()


def _source_note(source: str, imported_on: date | None) -> str:
    """An attribution + licence-reminder callout (renders as a "Note" card)."""
    day = (imported_on or date.today()).isoformat()
    return (
        f"> **Note:** Imported from {source} on {day}. Check that source's "
        "licence before sharing or redistributing this content further."
    )


# --- WikiHow / how-to article import ------------------------------------------


@dataclass
class ParsedStep:
    text: str
    images: list[tuple[str, str]] = field(default_factory=list)  # (src, alt)


@dataclass
class ParsedSection:
    heading: str | None
    steps: list[ParsedStep] = field(default_factory=list)


@dataclass
class ParsedArticle:
    title: str
    intro: list[str] = field(default_factory=list)
    sections: list[ParsedSection] = field(default_factory=list)


_SKIP_TAGS = {"script", "style", "nav", "footer", "header", "aside", "noscript", "form", "svg"}
_VOID_TAGS = {"img", "br", "hr", "input", "meta", "link"}
_HEADING_TAGS = {"h1", "h2", "h3"}
_TOP_LEVEL_TAGS = _HEADING_TAGS | {"p", "ol"}


class _Node:
    __slots__ = ("tag", "attrs", "children")

    def __init__(self, tag: str, attrs: list[tuple[str, str | None]] | None = None):
        self.tag = tag
        self.attrs: dict[str, str] = {k: (v or "") for k, v in (attrs or [])}
        self.children: list[_Node | str] = []


class _TreeBuilder(HTMLParser):
    """A minimal HTML → tree builder: just enough structure to find articles."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("#root")
        self._stack = [self.root]
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        node = _Node(tag, attrs)
        self._stack[-1].children.append(node)
        if tag not in _VOID_TAGS:
            self._stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._skip_depth or tag in _SKIP_TAGS:
            return
        self._stack[-1].children.append(_Node(tag, attrs))

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        for i in range(len(self._stack) - 1, 0, -1):
            if self._stack[i].tag == tag:
                del self._stack[i:]
                break

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        self._stack[-1].children.append(data)


def _collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _text_of(node: _Node) -> str:
    parts: list[str] = []

    def walk(n: _Node | str) -> None:
        if isinstance(n, str):
            parts.append(n)
            return
        for child in n.children:
            walk(child)

    walk(node)
    return _collapse_ws("".join(parts))


def _find_first(node: _Node, tag: str) -> _Node | None:
    for child in node.children:
        if isinstance(child, _Node):
            if child.tag == tag:
                return child
            found = _find_first(child, tag)
            if found is not None:
                return found
    return None


def _flatten_top_level(node: _Node, out: list[_Node]) -> None:
    """Collect h1/h2/h3/p/ol nodes in document order, wherever nested.

    Descends into generic wrapper elements (``div``, ``section``, ``article``,
    ...) to find them, but does not descend *into* a ``p`` or ``ol`` once
    found, so nested list items or stray text inside them are not picked up
    as separate top-level events.
    """
    for child in node.children:
        if not isinstance(child, _Node):
            continue
        if child.tag in _TOP_LEVEL_TAGS:
            out.append(child)
            continue
        _flatten_top_level(child, out)


def _li_to_step(li: _Node) -> ParsedStep:
    parts: list[str] = []
    images: list[tuple[str, str]] = []

    def walk(n: _Node | str) -> None:
        if isinstance(n, str):
            parts.append(n)
            return
        if n.tag == "img":
            src = n.attrs.get("src") or n.attrs.get("data-src") or ""
            if src:
                images.append((src, n.attrs.get("alt", "")))
            return
        if n.tag in ("ol", "ul"):
            return  # skip nested sub-lists; keep step text flat and simple
        if n.tag in ("b", "strong"):
            parts.append("**")
            for c in n.children:
                walk(c)
            parts.append("**")
            return
        if n.tag in ("i", "em"):
            parts.append("*")
            for c in n.children:
                walk(c)
            parts.append("*")
            return
        for c in n.children:
            walk(c)

    for c in li.children:
        walk(c)
    return ParsedStep(text=_collapse_ws("".join(parts)), images=images)


def parse_html_article(html: str, *, title: str | None = None) -> ParsedArticle:
    """Parse an "intro + numbered steps" how-to page into a :class:`ParsedArticle`."""
    builder = _TreeBuilder()
    builder.feed(html)
    tree = builder.root

    h1 = _find_first(tree, "h1")
    article_title = title or (_text_of(h1) if h1 is not None else "")

    flat: list[_Node] = []
    _flatten_top_level(tree, flat)

    intro: list[str] = []
    sections: list[ParsedSection] = []
    current: ParsedSection | None = None
    started = False

    for node in flat:
        if node.tag == "h1":
            continue
        if node.tag in ("h2", "h3"):
            current = ParsedSection(heading=_text_of(node))
            sections.append(current)
            started = True
        elif node.tag == "p":
            text = _text_of(node)
            if not text:
                continue
            if not started:
                intro.append(text)
            # paragraphs inside a section (outside an <ol>) are dropped to
            # keep the output to "summary + numbered steps"; real step text
            # lives in the <ol> that follows.
        elif node.tag == "ol":
            started = True
            if current is None:
                current = ParsedSection(heading=None)
                sections.append(current)
            for li in node.children:
                if isinstance(li, _Node) and li.tag == "li":
                    step = _li_to_step(li)
                    if step.text or step.images:
                        current.steps.append(step)

    return ParsedArticle(title=article_title, intro=intro, sections=sections)


def render_wikihow_guide(
    article: ParsedArticle,
    *,
    guide_id: str,
    source: str,
    category: str = "culture",
    difficulty: int = 2,
    estimated_time: str = "",
    image_map: dict[str, str] | None = None,
    imported_on: date | None = None,
) -> str:
    """Render a parsed how-to article as guide Markdown (front matter + body)."""
    image_map = image_map or {}
    title = article.title or guide_id.replace("-", " ").title()
    summary = article.intro[0] if article.intro else f"Imported from {source}."

    body_lines = [f"# {title}", ""]
    body_lines.extend(p for para in article.intro for p in (para, ""))

    word_count = sum(len(p.split()) for p in article.intro)

    for section in article.sections:
        if section.heading:
            body_lines.append(f"## {section.heading}")
            body_lines.append("")
        for i, step in enumerate(section.steps, start=1):
            body_lines.append(f"{i}. {step.text}")
            word_count += len(step.text.split())
            for src, alt in step.images:
                local = image_map.get(src)
                if not local:
                    continue
                caption = _collapse_ws(alt) or f"Step {i}"
                body_lines.append("")
                body_lines.append(f"   ![{caption}]({local})")
            body_lines.append("")

    body_lines.append(_source_note(source, imported_on))
    body = "\n".join(body_lines).strip() + "\n"

    front = _front_matter(
        guide_id=guide_id,
        title=title,
        category=category,
        summary=summary,
        difficulty=difficulty,
        estimated_time=estimated_time or reading_time(word_count),
    )
    return f"---\n{front}\n---\n\n{body}"


def collect_image_sources(article: ParsedArticle) -> list[str]:
    """All distinct image URLs referenced by an article's steps, in order."""
    seen: list[str] = []
    for section in article.sections:
        for step in section.steps:
            for src, _alt in step.images:
                if src not in seen:
                    seen.append(src)
    return seen


# --- Book / long-form text import ---------------------------------------------


@dataclass
class ParsedChapter:
    title: str
    body: str


_MD_HEADING_RE = re.compile(r"^#{1,2}\s+(.+?)\s*$")
_CHAPTER_RE = re.compile(
    r"^(?:chapter|part|book)\s+([ivxlcdm\d]+)\b\s*[:.\-–—]?\s*(.*)$",
    re.IGNORECASE,
)
_CHAPTER_PREFIX_RE = re.compile(
    r"^(?:chapter|part|book)\s+[ivxlcdm\d]+\b\s*[:.\-–—]?\s*", re.IGNORECASE
)


def chapter_slug_suffix(title: str) -> str:
    """Slugify a chapter title for a guide-id suffix, dropping a leading "Chapter N".

    The numbered-index prefix (``-01-``, ``-02-``, ...) already encodes the
    chapter's position, so repeating "chapter-1-" in the slug would just be
    noise; the title's actual subject (e.g. "Greetings") is more useful.
    """
    remainder = _CHAPTER_PREFIX_RE.sub("", title).strip()
    return slugify(remainder or title)


def split_book_into_chapters(text: str) -> list[ParsedChapter]:
    """Split a plain-text or Markdown book into chapters.

    Recognises Markdown ``#``/``##`` headings and plain-text "Chapter N" /
    "Part N" / "Book N" lines. Falls back to a single chapter holding the
    whole text when fewer than two heading-like lines are found.
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    breaks: list[tuple[int, str]] = []  # (line index, chapter title)
    for i, raw in enumerate(lines):
        line = raw.strip()
        if not line:
            continue
        md = _MD_HEADING_RE.match(line)
        if md:
            breaks.append((i, md.group(1).strip()))
            continue
        ch = _CHAPTER_RE.match(line)
        if ch:
            label = f"Chapter {ch.group(1)}"
            extra = ch.group(2).strip()
            breaks.append((i, f"{label}: {extra}" if extra else label))

    if len(breaks) < 2:
        title = "Untitled"
        for raw in lines:
            if raw.strip():
                title = raw.strip().lstrip("#").strip()
                break
        body = _collapse_blank_lines("\n".join(lines))
        return [ParsedChapter(title=title, body=body)] if body.strip() else []

    chapters: list[ParsedChapter] = []
    for idx, (start, chapter_title) in enumerate(breaks):
        end = breaks[idx + 1][0] if idx + 1 < len(breaks) else len(lines)
        chunk = lines[start + 1 : end]
        body = _collapse_blank_lines("\n".join(chunk))
        if body.strip():
            chapters.append(ParsedChapter(title=chapter_title, body=body))
    return chapters


def _collapse_blank_lines(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def render_book_guide(
    chapter: ParsedChapter,
    *,
    guide_id: str,
    source: str,
    category: str = "culture",
    difficulty: int = 1,
    estimated_time: str = "",
    imported_on: date | None = None,
) -> str:
    """Render one book chapter as guide Markdown (front matter + body)."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", chapter.body) if p.strip()]
    word_count = sum(len(p.split()) for p in paragraphs)
    summary_source = paragraphs[0] if paragraphs else chapter.title
    summary = _collapse_ws(summary_source)[:240]

    body_lines = [f"# {chapter.title}", "", *[p for para in paragraphs for p in (para, "")]]
    body_lines.append(_source_note(source, imported_on))
    body = "\n".join(body_lines).strip() + "\n"

    front = _front_matter(
        guide_id=guide_id,
        title=chapter.title,
        category=category,
        summary=summary,
        difficulty=difficulty,
        estimated_time=estimated_time or reading_time(word_count),
    )
    return f"---\n{front}\n---\n\n{body}"
