"""Test configuration: redirect horizon's data paths to a throwaway temp dir.

horizon defaults ``data_dir`` to ``/data`` (the path baked into the Docker
image). The test suite must not depend on that absolute path existing or being
writable — on a fresh laptop or a CI runner it is neither. So, *before* any
``horizon`` import triggers settings loading and the database directory's
creation, we generate a config file under a temporary directory and point
horizon at it via ``HORIZON_CONFIG``.

This keeps tests hermetic (each run gets a clean SQLite db, content copy, and
vector-store path) and lets ``pytest`` run anywhere without write access to
``/data``.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
import yaml

_tmp = Path(tempfile.mkdtemp(prefix="horizon-test-"))
_config = {
    "data_dir": str(_tmp),
    "database": str(_tmp / "horizon.db"),
    "content_dir": str(_tmp / "content"),
    "vectordb": {"path": str(_tmp / "chroma")},
    "content_packs": {"dir": str(_tmp / "packs")},
}
_config_path = _tmp / "config.yaml"
_config_path.write_text(yaml.safe_dump(_config), encoding="utf-8")

# Set before horizon is imported anywhere in the test session.
os.environ.setdefault("HORIZON_CONFIG", str(_config_path))


@pytest.fixture(scope="session")
def fixture_zim(tmp_path_factory) -> Path:
    """Build a tiny synthetic ZIM: a home page (with a script to be stripped),
    a searchable article, a redirect to it, and a non-HTML asset -- enough to
    exercise resolve_entry, redirect-following, search, and mimetype branching
    across both test_zim_reader.py and test_web_reference.py.
    """
    from libzim.writer import Creator, Hint, Item, StringProvider

    class _StringItem(Item):
        def __init__(self, path: str, title: str, content: str, mimetype: str = "text/html"):
            super().__init__()
            self._path = path
            self._title = title
            self._content = content
            self._mimetype = mimetype

        def get_path(self) -> str:
            return self._path

        def get_title(self) -> str:
            return self._title

        def get_mimetype(self) -> str:
            return self._mimetype

        def get_contentprovider(self) -> StringProvider:
            return StringProvider(self._content)

        def get_hints(self) -> dict:
            return {Hint.FRONT_ARTICLE: True}

    zim_path = tmp_path_factory.mktemp("zim") / "fixture.zim"
    with Creator(str(zim_path)).config_indexing(True, "eng") as creator:
        creator.set_mainpath("Home")
        creator.add_item(
            _StringItem(
                "Home",
                "Home Page",
                '<html><body><h1>Home</h1><a href="Camping">Camping</a>'
                "<script>window.zimTrackerPixel();</script></body></html>",
            )
        )
        creator.add_item(
            _StringItem(
                "Camping",
                "Camping basics",
                "<html><body><h1>Camping basics</h1><p>How to pick a tent site.</p></body></html>",
            )
        )
        creator.add_redirection("Old_Camping_Name", "Camping (old name)", "Camping", {})
        creator.add_item(_StringItem("logo.png", "logo", "not-really-a-png", mimetype="image/png"))
        creator.add_metadata("Title", "Fixture Pack")
        creator.add_metadata("Description", "A tiny test pack")
        creator.add_metadata("Language", "eng")
    return zim_path
