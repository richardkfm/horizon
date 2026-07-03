"""Tests for the ZIM reader service (services/zim_reader.py).

The rewrite tests are pure string-in/string-out and need no ZIM file at all.
The archive-reading tests use the ``fixture_zim`` fixture (conftest.py): a
tiny synthetic ZIM built with ``libzim.writer`` -- no binary fixture checked
into the repo, fully reproducible, and fast (a handful of short articles, not
a real Wikipedia dump). Shared with test_web_reference.py.
"""

from __future__ import annotations

import pytest

from horizon.services import zim_reader

# --- HTML rewriting (no ZIM file needed) -------------------------------------


def test_rewrite_relative_href():
    out = zim_reader.rewrite_article_html(
        '<a href="Other_Article">link</a>', pack_id="demo", entry_path="Home"
    )
    assert 'href="/reference/demo/Other_Article"' in out


def test_rewrite_relative_href_with_parent_segments():
    out = zim_reader.rewrite_article_html(
        '<a href="../A/Other_Article">link</a>', pack_id="demo", entry_path="A/Home"
    )
    assert 'href="/reference/demo/A/Other_Article"' in out


def test_rewrite_relative_src():
    out = zim_reader.rewrite_article_html(
        '<img src="images/pic.png">', pack_id="demo", entry_path="Home"
    )
    assert 'src="/reference/demo/images/pic.png"' in out


def test_rewrite_srcset():
    out = zim_reader.rewrite_article_html(
        '<img srcset="a.png 1x, b.png 2x">', pack_id="demo", entry_path="Home"
    )
    assert "/reference/demo/a.png 1x" in out
    assert "/reference/demo/b.png 2x" in out


def test_absolute_http_link_left_alone_but_marked_external():
    out = zim_reader.rewrite_article_html(
        '<a href="https://example.com/page">ext</a>', pack_id="demo", entry_path="Home"
    )
    assert 'href="https://example.com/page"' in out
    assert 'target="_blank"' in out
    assert 'rel="noopener"' in out


def test_anchor_and_mailto_left_alone():
    out = zim_reader.rewrite_article_html(
        '<a href="#section">jump</a> <a href="mailto:a@b.test">mail</a>',
        pack_id="demo",
        entry_path="Home",
    )
    assert 'href="#section"' in out
    assert 'href="mailto:a@b.test"' in out
    assert "/reference/" not in out


def test_script_tags_stripped():
    out = zim_reader.rewrite_article_html(
        "<p>ok</p><script>alert(1)</script><p>after</p>",
        pack_id="demo",
        entry_path="Home",
    )
    assert "<script" not in out
    assert "alert" not in out
    assert "<p>ok</p>" in out
    assert "<p>after</p>" in out


def test_entity_escaped_query_string_not_double_escaped():
    out = zim_reader.rewrite_article_html(
        '<a href="Article?x=1&amp;y=2">link</a>', pack_id="demo", entry_path="Home"
    )
    assert "&amp;amp;" not in out
    assert "&amp;" in out


def test_style_tags_kept():
    out = zim_reader.rewrite_article_html(
        "<style>.x{color:red}</style><p>ok</p>", pack_id="demo", entry_path="Home"
    )
    assert "<style>" in out


def test_full_document_reduced_to_body_content():
    """A complete HTML document keeps only its <body> content, so the pack's
    own skin stylesheets (head <link> tags) never leak onto horizon's page."""
    doc = (
        "<!DOCTYPE html><html><head><title>T</title>"
        '<link href="_mw_/skin.css" rel="stylesheet">'
        '</head><body class="mediawiki"><h1>Title</h1><p>text</p></body></html>'
    )
    out = zim_reader.rewrite_article_html(doc, pack_id="demo", entry_path="Home")
    assert "<h1>Title</h1><p>text</p>" in out
    assert "<link" not in out
    assert "<head" not in out
    assert "<html" not in out
    assert "<body" not in out


def test_fragment_without_body_passes_through():
    out = zim_reader.rewrite_article_html(
        "<h2>Section</h2><p>fragment</p>", pack_id="demo", entry_path="Home"
    )
    assert "<h2>Section</h2><p>fragment</p>" in out


# --- Archive reading (fixture_zim from conftest.py) --------------------------


def test_pack_info(fixture_zim):
    info = zim_reader.pack_info(fixture_zim)
    assert info.title == "Fixture Pack"
    assert info.description == "A tiny test pack"
    assert info.article_count >= 2


def test_resolve_entry_known_path(fixture_zim):
    entry = zim_reader.resolve_entry(fixture_zim, "Camping")
    assert entry is not None
    assert entry.title == "Camping basics"
    assert b"tent site" in entry.content
    assert entry.mimetype == "text/html"


def test_resolve_entry_unknown_path(fixture_zim):
    assert zim_reader.resolve_entry(fixture_zim, "Does_Not_Exist") is None


def test_resolve_entry_follows_redirect(fixture_zim):
    entry = zim_reader.resolve_entry(fixture_zim, "Old_Camping_Name")
    assert entry is not None
    assert entry.path == "Camping"
    assert entry.title == "Camping basics"


def test_resolve_entry_non_html_asset(fixture_zim):
    entry = zim_reader.resolve_entry(fixture_zim, "logo.png")
    assert entry is not None
    assert entry.mimetype == "image/png"
    assert entry.content == b"not-really-a-png"


def test_random_entry_path_returns_a_real_entry(fixture_zim):
    path = zim_reader.random_entry_path(fixture_zim)
    assert zim_reader.resolve_entry(fixture_zim, path) is not None


def test_search_finds_matching_article(fixture_zim):
    hits = zim_reader.search(fixture_zim, "tent")
    assert any(h.path == "Camping" for h in hits)


def test_search_empty_query_returns_nothing(fixture_zim):
    assert zim_reader.search(fixture_zim, "   ") == []


def test_open_missing_file_raises_zim_unavailable(tmp_path):
    with pytest.raises(zim_reader.ZimUnavailableError):
        zim_reader.pack_info(tmp_path / "nope.zim")
