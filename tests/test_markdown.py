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
