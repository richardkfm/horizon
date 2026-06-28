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
