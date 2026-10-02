"""horizon — offline-first autonomy & rebuilding node."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    # Single source of truth: the version in pyproject.toml, as installed.
    __version__ = version("horizon")
except PackageNotFoundError:  # running from a source checkout without install
    __version__ = "0.9.0"
