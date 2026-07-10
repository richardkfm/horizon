"""Tests for the MBTiles reader service (services/mbtiles.py).

Uses the ``fixture_mbtiles`` fixture (conftest.py): a tiny synthetic
``.mbtiles`` SQLite file with one gzipped tile -- no binary fixture checked
into the repo, fully reproducible, and fast (no real rendered tileset).
"""

from __future__ import annotations

import gzip

import pytest

from horizon.services import mbtiles


def test_pack_info_reads_metadata(fixture_mbtiles):
    info = mbtiles.pack_info(fixture_mbtiles)
    assert info.name == "Fixture Map"
    assert info.format == "pbf"
    assert info.bounds == (-1.0, -1.0, 1.0, 1.0)
    assert info.center == (0.0, 0.0, 1.0)
    assert info.minzoom == 0
    assert info.maxzoom == 0


def test_get_tile_returns_bytes_for_present_tile(fixture_mbtiles):
    data = mbtiles.get_tile(fixture_mbtiles, 0, 0, 0)
    assert data is not None
    assert gzip.decompress(data) == b"not-really-a-vector-tile"


def test_get_tile_returns_none_for_missing_tile(fixture_mbtiles):
    assert mbtiles.get_tile(fixture_mbtiles, 5, 5, 5) is None


def test_is_gzipped(fixture_mbtiles):
    data = mbtiles.get_tile(fixture_mbtiles, 0, 0, 0)
    assert mbtiles.is_gzipped(data)
    assert not mbtiles.is_gzipped(b"not gzipped")


def test_pack_info_missing_file_raises(tmp_path):
    with pytest.raises(mbtiles.MBTilesUnavailableError):
        mbtiles.pack_info(tmp_path / "missing.mbtiles")


def test_pack_info_defaults_name_to_stem_when_metadata_missing(tmp_path):
    import sqlite3

    path = tmp_path / "bare.mbtiles"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE metadata (name TEXT, value TEXT)")
    conn.execute(
        "CREATE TABLE tiles (zoom_level INTEGER, tile_column INTEGER, "
        "tile_row INTEGER, tile_data BLOB)"
    )
    conn.commit()
    conn.close()

    info = mbtiles.pack_info(path)
    assert info.name == "bare"
    assert info.bounds is None
    assert info.center is None
    assert info.minzoom == 0
    assert info.maxzoom == 14
