"""Guards against the packaging regression that crash-looped the Docker image.

A real (non-editable) ``pip install`` ships only Python modules unless data files
are declared. Two things must hold or the installed app dies at startup:

* the server-rendered UI assets (``web/static`` + ``web/templates``) are declared
  as package data, so they land in the wheel; and
* the bundled seed ``content/`` is locatable even when the package is installed
  away from the source tree (e.g. ``site-packages`` in the container), via the
  ``HORIZON_BUNDLED_CONTENT`` override.

Editable installs (how CI runs) always have these files on disk, so these tests
assert the *declarations* and *resolution logic* rather than re-building a wheel.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from horizon import seed
from horizon.main import STATIC_DIR
from horizon.web.routes import TEMPLATES_DIR

_PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_pyproject_declares_web_package_data():
    data = tomllib.loads((_PROJECT_ROOT / "pyproject.toml").read_text())
    pkg_data = data["tool"]["setuptools"]["package-data"]
    patterns = pkg_data["horizon.web"]
    # Both asset trees must be covered, including their nested files.
    assert any(p.startswith("static/") for p in patterns)
    assert any(p.startswith("templates/") for p in patterns)
    assert any("**" in p for p in patterns)


def test_web_assets_exist_where_the_app_loads_them():
    # The app mounts these by filesystem path; if they are absent it raises at
    # startup (the original crash). Spot-check a top-level and a nested file.
    assert (STATIC_DIR / "app.css").is_file()
    assert (TEMPLATES_DIR / "landing.html").is_file()
    assert (TEMPLATES_DIR / "admin" / "login.html").is_file()


def test_bundled_content_dir_honours_env_override(tmp_path, monkeypatch):
    bundled = tmp_path / "mycontent"
    bundled.mkdir()
    (bundled / "journeys.yaml").write_text("[]", encoding="utf-8")
    monkeypatch.setenv("HORIZON_BUNDLED_CONTENT", str(bundled))
    assert seed._bundled_content_dir() == bundled


def test_bundled_content_dir_found_without_env(monkeypatch):
    # With no override, resolution still finds the repo's content/ (editable /
    # source layout) by walking up from the module.
    monkeypatch.delenv("HORIZON_BUNDLED_CONTENT", raising=False)
    found = seed._bundled_content_dir()
    assert (found / "journeys.yaml").is_file()
