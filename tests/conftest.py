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
