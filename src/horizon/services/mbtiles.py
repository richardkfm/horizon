"""Read MBTiles vector-tile basemaps for the map viewer (``web/maps.py``).

A ``maps-*`` content pack (``services/packs.py``) downloads raw OpenStreetMap
``.osm.pbf`` data -- source material, not something a browser can render.
horizon does not render it: that's a CPU/RAM-heavy batch job that does not fit
weak/Pi-class hardware. Instead an operator renders it *once*, off the node,
with `Planetiler <https://github.com/onthegomap/planetiler>`_ and drops the
resulting ``.mbtiles`` file into the installed pack's own directory (see
``docs/operating.md``); ``services.packs.pack_mbtiles_path`` finds it.

MBTiles is just a SQLite database
(https://github.com/mapbox/mbtiles-spec/blob/master/1.3/spec.md), so this
module is stdlib ``sqlite3`` only -- no new dependency, and importable/testable
without a real multi-hundred-megabyte tileset (tests build a tiny synthetic
``.mbtiles``). Tile rows are stored TMS-style (Y flipped from the XYZ scheme
every web map client -- MapLibre included -- requests); :func:`get_tile` flips
once at this read boundary so callers never have to think about it.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

# Planetiler (and most encoders) gzip each vector tile blob before storing it;
# detect that by its magic bytes rather than trusting the "format" metadata key,
# which describes the tile content type (pbf), not its compression.
_GZIP_MAGIC = b"\x1f\x8b"


class MBTilesUnavailableError(RuntimeError):
    """An ``.mbtiles`` file could not be opened or read (missing, corrupt, ...)."""


@dataclass(frozen=True)
class MBTilesInfo:
    """Display metadata for a map viewer landing page."""

    name: str
    format: str
    bounds: tuple[float, float, float, float] | None
    center: tuple[float, float, float] | None
    minzoom: int
    maxzoom: int


def _connect(path: Path) -> sqlite3.Connection:
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.execute("SELECT 1 FROM metadata LIMIT 1")
        return conn
    except sqlite3.Error as exc:
        raise MBTilesUnavailableError(f"Could not open MBTiles file: {path}") from exc


def _metadata(conn: sqlite3.Connection) -> dict[str, str]:
    return dict(conn.execute("SELECT name, value FROM metadata").fetchall())


def _floats(raw: str | None, count: int) -> tuple[float, ...] | None:
    if not raw:
        return None
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) != count:
        return None
    try:
        return tuple(float(p) for p in parts)
    except ValueError:
        return None


def pack_info(path: Path) -> MBTilesInfo:
    """Return the tileset's name, zoom range, and bounds/center for display."""
    conn = _connect(path)
    try:
        meta = _metadata(conn)
        return MBTilesInfo(
            name=meta.get("name", path.stem),
            format=meta.get("format", "pbf"),
            bounds=_floats(meta.get("bounds"), 4),
            center=_floats(meta.get("center"), 3),
            minzoom=int(meta.get("minzoom", 0)),
            maxzoom=int(meta.get("maxzoom", 14)),
        )
    finally:
        conn.close()


def get_tile(path: Path, z: int, x: int, y: int) -> bytes | None:
    """Return raw tile bytes at XYZ (slippy-map) coordinates, or ``None`` if absent."""
    conn = _connect(path)
    try:
        tms_y = (2**z - 1) - y
        row = conn.execute(
            "SELECT tile_data FROM tiles WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?",
            (z, x, tms_y),
        ).fetchone()
        return bytes(row[0]) if row else None
    finally:
        conn.close()


def is_gzipped(tile_data: bytes) -> bool:
    """True if a tile blob is gzip-compressed (needs a ``Content-Encoding`` header)."""
    return tile_data[:2] == _GZIP_MAGIC
