"""Unit tests for the pure Markdown rendering service."""

from __future__ import annotations

from horizon.services.markdown import render_markdown, strip_front_matter


def test_strip_front_matter_removes_leading_block():
    text = "---\nid: x\ntitle: X\n---\n\n# Heading\n\nBody."
    body = strip_front_matter(text)
    assert body.startswith("# Heading")
    assert "id: x" not in body


def test_strip_front_matter_passthrough_without_block():
    text = "# Heading\n\nNo front matter here."
    assert strip_front_matter(text) == text


def test_render_markdown_basic_elements():
    html = render_markdown("# Title\n\n- one\n- two\n")
    assert "<h1>Title</h1>" in html
    assert "<ul>" in html and "<li>one</li>" in html


def test_render_markdown_ignores_front_matter():
    html = render_markdown("---\nid: g\n---\n\n# Real Title\n")
    assert "<h1>Real Title</h1>" in html
    assert "id: g" not in html


def test_render_markdown_tables_enabled():
    table = "| a | b |\n| - | - |\n| 1 | 2 |\n"
    html = render_markdown(table)
    assert "<table>" in html
    assert "<td>1</td>" in html


def test_callout_blockquote_gets_class():
    html = render_markdown("> **Pick this if:** the water is cloudy.")
    assert 'class="callout callout-pick"' in html
    # The bold label survives so the callout reads correctly even unstyled.
    assert "<strong>Pick this if:</strong>" in html


def test_callout_label_synonyms_map_to_kind():
    assert 'callout-avoid"' in render_markdown("> **Skip if:** the source is clean.")
    assert 'callout-spec"' in render_markdown("> **At a glance:** 60 cm sand bed.")
    assert 'callout-risk"' in render_markdown("> **Warning:** never skip testing.")


def test_callout_matching_is_case_insensitive():
    assert 'callout-tip"' in render_markdown("> **tip:** wash the sand first.")


def test_plain_blockquote_is_not_a_callout():
    html = render_markdown("> Just a quote, no label.")
    assert "callout" not in html
    assert "<blockquote>" in html


def test_unknown_label_stays_plain_blockquote():
    html = render_markdown("> **Heads up:** an unrecognised label.")
    assert "callout" not in html


def test_do_now_callout_gets_now_kind():
    html = render_markdown("> **Do now:** get out and stay out.")
    assert 'class="callout callout-now"' in html
    assert "<strong>Do now:</strong>" in html
    # "Act now" / "Right now" are synonyms for the same urgent kind.
    assert 'callout-now"' in render_markdown("> **Act now:** move to cover.")


def test_lone_image_paragraph_becomes_figure():
    html = render_markdown("![Fig. 1: a simple shower](images/shower.svg)")
    assert "<figure" in html and 'class="guide-figure"' in html
    assert '<img src="images/shower.svg"' in html
    assert "<figcaption>Fig. 1: a simple shower</figcaption>" in html


def test_inline_image_is_not_wrapped_in_figure():
    html = render_markdown("See this ![x](a.png) inline image.")
    assert "<figure" not in html
    assert "<p>" in html and '<img src="a.png"' in html


def test_figcaption_is_escaped():
    html = render_markdown("![a <b> & c](x.svg)")
    assert "<figcaption>a &lt;b&gt; &amp; c</figcaption>" in html


def test_task_list_renders_checkboxes():
    html = render_markdown("- [ ] water\n- [x] torch\n")
    assert 'class="task-list"' in html
    # Exactly one class, not duplicated per item.
    assert html.count("task-list") == 1
    assert '<li class="task-item"><input type="checkbox" class="task-check"> water' in html
    assert '<li class="task-item"><input type="checkbox" class="task-check" checked> torch' in html


def test_task_marker_accepts_upper_x():
    html = render_markdown("- [X] done\n")
    assert 'class="task-check" checked>' in html


def test_plain_list_is_not_a_task_list():
    html = render_markdown("- one\n- two\n")
    assert "task-list" not in html
    assert "checkbox" not in html
