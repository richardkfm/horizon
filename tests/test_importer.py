"""``horizon.services.importer`` tests: pure conversion, no network.

Mirrors the offline-testable shape of the rest of the suite — these exercise
HTML/text -> guide-Markdown conversion with small inline fixtures, never a
real network fetch (that lives in ``horizon-content import`` and is exercised
separately with a faked ``httpx.Client``).
"""

from __future__ import annotations

from horizon.services import importer, markdown

WIKIHOW_HTML = """
<html><head><script>tracking();</script></head>
<body>
<nav>Home | Categories</nav>
<div class="content">
<h1>How to Make a Friendship Bracelet</h1>
<div id="intro">
<p>Friendship bracelets are a fun craft passed between friends.</p>
<p>This covers a simple chevron pattern.</p>
</div>
<h2>Part 1: Gather Materials</h2>
<ol>
<li><b>Choose your colors.</b> Pick 4-6 floss colors you like.
<img src="https://example.test/colors.jpg" alt="Embroidery floss colors"></li>
<li><b>Cut the strings.</b> Cut each string about 60cm long.</li>
</ol>
<h2>Part 2: Tie the Knots</h2>
<ol>
<li><b>Tape it down.</b> Secure the bundle with tape.</li>
</ol>
</div>
<footer>copyright 2024</footer>
</body></html>
"""


def test_slugify():
    assert (
        importer.slugify("How to Make a Friendship Bracelet!")
        == "how-to-make-a-friendship-bracelet"
    )
    assert importer.slugify("  multiple   spaces  ") == "multiple-spaces"
    assert importer.slugify("") == "guide"


def test_parse_html_article_title_intro_sections():
    article = importer.parse_html_article(WIKIHOW_HTML)
    assert article.title == "How to Make a Friendship Bracelet"
    assert article.intro == [
        "Friendship bracelets are a fun craft passed between friends.",
        "This covers a simple chevron pattern.",
    ]
    assert [s.heading for s in article.sections] == [
        "Part 1: Gather Materials",
        "Part 2: Tie the Knots",
    ]
    assert len(article.sections[0].steps) == 2
    assert len(article.sections[1].steps) == 1


def test_parse_html_article_strips_script_and_nav():
    article = importer.parse_html_article(WIKIHOW_HTML)
    assert "tracking" not in article.intro[0]
    assert all("Home" not in p for p in article.intro)


def test_parse_html_article_step_bold_lead_and_images():
    article = importer.parse_html_article(WIKIHOW_HTML)
    first_step = article.sections[0].steps[0]
    assert first_step.text == "**Choose your colors.** Pick 4-6 floss colors you like."
    assert first_step.images == [("https://example.test/colors.jpg", "Embroidery floss colors")]

    second_step = article.sections[0].steps[1]
    assert second_step.images == []


def test_collect_image_sources_dedupes_in_order():
    html = """
    <h1>T</h1>
    <h2>S</h2>
    <ol>
    <li>One <img src="a.jpg"></li>
    <li>Two <img src="b.jpg"></li>
    <li>Three <img src="a.jpg"></li>
    </ol>
    """
    article = importer.parse_html_article(html)
    assert importer.collect_image_sources(article) == ["a.jpg", "b.jpg"]


def test_render_wikihow_guide_front_matter_and_body():
    article = importer.parse_html_article(WIKIHOW_HTML)
    md = importer.render_wikihow_guide(
        article,
        guide_id="culture-friendship-bracelet",
        source="https://www.wikihow.com/Make-a-Friendship-Bracelet",
        category="culture",
        difficulty=3,
        image_map={"https://example.test/colors.jpg": "images/culture-friendship-bracelet-1.jpg"},
    )
    assert md.startswith("---\n")
    front, _, body = md.partition("---\n\n")
    assert "id: culture-friendship-bracelet" in front
    assert "category: culture" in front
    assert "difficulty: 3" in front
    assert "# How to Make a Friendship Bracelet" in body
    assert "## Part 1: Gather Materials" in body
    assert "1. **Choose your colors.**" in body
    assert "![Embroidery floss colors](images/culture-friendship-bracelet-1.jpg)" in body
    # The second step's image has no entry in image_map, so it is dropped
    # rather than left as a remote (offline-breaking) URL.
    assert "example.test" not in body
    assert "> **Note:** Imported from https://www.wikihow.com/Make-a-Friendship-Bracelet" in body


def test_render_wikihow_guide_renders_figure_and_callout():
    article = importer.parse_html_article(WIKIHOW_HTML)
    md = importer.render_wikihow_guide(
        article,
        guide_id="x",
        source="https://example.test/a",
        image_map={"https://example.test/colors.jpg": "images/x-1.jpg"},
    )
    html = markdown.render_markdown(md)
    assert 'class="guide-figure"' in html
    assert "callout callout-note" in html


def test_render_wikihow_guide_defaults_estimated_time_from_word_count():
    article = importer.parse_html_article("<h1>T</h1><p>short.</p>")
    md = importer.render_wikihow_guide(article, guide_id="t", source="https://example.test/t")
    assert "estimated_time: ~1 min read" in md


# --- book splitting ------------------------------------------------------------


def test_split_book_markdown_headings():
    text = "# Intro\nhello\n\n# Customs\nworld\n"
    chapters = importer.split_book_into_chapters(text)
    assert [c.title for c in chapters] == ["Intro", "Customs"]
    assert chapters[0].body == "hello"
    assert chapters[1].body == "world"


def test_split_book_plain_chapter_headings():
    text = (
        "Chapter 1: Greetings\n"
        "In the valley, greetings are never rushed.\n\n"
        "Chapter 2 - Harvest Festivals\n"
        "The festival marks the end of the season.\n"
    )
    chapters = importer.split_book_into_chapters(text)
    assert chapters[0].title == "Chapter 1: Greetings"
    assert chapters[1].title == "Chapter 2: Harvest Festivals"
    assert "never rushed" in chapters[0].body
    assert "end of the season" in chapters[1].body


def test_split_book_without_headings_falls_back_to_one_chapter():
    text = "Just a short piece of writing with no chapter markers at all."
    chapters = importer.split_book_into_chapters(text)
    assert len(chapters) == 1
    assert chapters[0].body == text.strip()


def test_split_book_empty_text_returns_no_chapters():
    assert importer.split_book_into_chapters("   \n\n  ") == []


def test_render_book_guide_front_matter_and_summary():
    chapter = importer.ParsedChapter(
        title="Chapter 1: Greetings",
        body="In the valley, greetings are never rushed.\n\nA visitor who hurries is suspect.",
    )
    md = importer.render_book_guide(
        chapter,
        guide_id="culture-valley-customs-01-greetings",
        source="valley-customs.txt",
        category="culture",
    )
    assert "title: 'Chapter 1: Greetings'" in md or 'title: "Chapter 1: Greetings"' in md
    assert "summary: In the valley, greetings are never rushed." in md
    assert "# Chapter 1: Greetings" in md
    assert "A visitor who hurries is suspect." in md
    assert "> **Note:** Imported from valley-customs.txt" in md
