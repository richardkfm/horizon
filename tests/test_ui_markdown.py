"""Markdown renderer: cross-reference links, raw-HTML escaping, and helpers."""

from __future__ import annotations

from horizon.services.markdown import render_inline, render_markdown, split_title

TITLES = {
    ("guide", "survival-knots"): ("/guides/survival-knots", "Tie essential knots"),
    ("guide", "water-boil"): ("/guides/water-boil", "Boil water's germs, safely"),
    ("plan", "safe-drinking-water"): ("/journeys/safe-drinking-water", "Safe water"),
    ("checklist", "go-bag"): ("/checklists/go-bag", "Go-bag"),
}


def resolve(kind: str, target: str):
    return TITLES.get((kind, target))


def test_wikilink_uses_resolved_title():
    html = render_markdown("See [[survival-knots]].", resolve)
    assert '<a class="xref" href="/guides/survival-knots">Tie essential knots</a>' in html


def test_wikilink_custom_text():
    html = render_markdown("Learn [[survival-knots|a few knots, + lashings']].", resolve)
    assert ">a few knots, + lashings&#x27;</a>" in html


def test_wikilink_plan_and_checklist_urls():
    html = render_markdown("[[plan:safe-drinking-water]] and [[checklist:go-bag]]", resolve)
    assert 'href="/journeys/safe-drinking-water">Safe water</a>' in html
    assert 'href="/checklists/go-bag">Go-bag</a>' in html


def test_wikilink_title_is_escaped():
    html = render_markdown("[[water-boil]]", resolve)
    assert "Boil water&#x27;s germs, safely</a>" in html


def test_unknown_wikilink_is_plain_text():
    html = render_markdown("See [[no-such-guide]] and [[no-such|its text]].", resolve)
    assert "<a" not in html
    assert "See no-such-guide and its text." in html


def test_wikilink_without_resolver_uses_default_url():
    html = render_markdown("[[survival-knots]] [[plan:p1]] [[checklist:c1]]")
    assert 'href="/guides/survival-knots"' in html
    assert 'href="/journeys/p1"' in html
    assert 'href="/checklists/c1"' in html


def test_wikilink_left_alone_in_code():
    html = render_markdown("Write `[[survival-knots]]`.\n\n```\n[[survival-knots]]\n```\n", resolve)
    assert "<a" not in html
    assert html.count("[[survival-knots]]") == 2


def test_wikilink_in_table_cell():
    table = "| Need | Guide |\n| - | - |\n| Rope | [[survival-knots]] |\n"
    html = render_markdown(table, resolve)
    assert '<td><a class="xref" href="/guides/survival-knots">Tie essential knots</a></td>' in html


def test_wikilink_in_callout_blockquote():
    html = render_markdown("> **Tip:** practise with [[survival-knots]] first.", resolve)
    assert 'class="callout callout-tip"' in html
    assert 'href="/guides/survival-knots"' in html


def test_wikilink_in_list_and_task_items():
    html = render_markdown("- read [[survival-knots]]\n\n1. pack [[checklist:go-bag]]\n", resolve)
    assert '<li>read <a class="xref" href="/guides/survival-knots">' in html
    assert 'href="/checklists/go-bag">Go-bag</a>' in html
    tasks = render_markdown("- [ ] tie [[survival-knots]]\n", resolve)
    assert 'class="task-label"' in tasks and 'href="/guides/survival-knots"' in tasks


def test_render_inline_for_descriptions():
    html = render_inline("Start with [[survival-knots]].", resolve)
    assert not html.startswith("<p>")
    assert 'href="/guides/survival-knots"' in html


def test_raw_html_is_escaped():
    html = render_markdown(
        'Hi <script>alert(1)</script> <img src=x onerror="x()">\n\n<div>block</div>'
    )
    assert "<script>" not in html
    assert "<img" not in html
    assert "<div>" not in html
    assert "&lt;script&gt;" in html


def test_horizon_features_survive_html_off():
    md = (
        "> **Do now:** act.\n\n![Fig. 1: shower](images/s.svg)\n\n"
        "```ascii\n+--+\n```\n\n*cap*\n\n- [ ] item\n"
    )
    html = render_markdown(md)
    assert "callout-now" in html
    assert '<figure class="guide-figure">' in html and "<figcaption>Fig. 1: shower" in html
    assert 'class="guide-figure guide-ascii"' in html
    assert 'class="task-check"' in html


def test_callout_label_with_trailing_period():
    assert "callout-note" in render_markdown("> **Note.** something")
    assert "callout-now" in render_markdown("> **Do now.** get out")
    assert "callout-note" in render_markdown("> **Principle:** consent first")
    # A bold sentence that merely ends in a full stop is not a callout.
    assert "callout" not in render_markdown("> **Small is warm.** Keep it tight.")


def test_ascii_figure_carries_column_count():
    html = render_markdown("```ascii\nab\nabcdefgh\n```\n")
    assert 'data-cols="8"' in html
    assert 'style="--cols:8"' in html


def test_split_title():
    assert split_title("---\nid: a\n---\n\n# Hello\n\nBody") == ("Hello", "Body")
    assert split_title("No heading\n\n# Later") == (None, "No heading\n\n# Later")
