"""Content-pack service + CLI tests.

The network is never touched: downloads run against a fake httpx client, and the
on-disk/catalog logic is exercised against a temp directory. ``hello world`` is
11 bytes; its sha256 is the constant below.
"""

from __future__ import annotations

import time

import httpx
import pytest

from horizon.config import settings
from horizon.scripts import content as cli
from horizon.services import packs

HELLO = b"hello world"
HELLO_SHA = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"

CATALOG = f"""
packs:
  - id: demo
    title: Demo Pack
    description: A tiny test pack.
    category: reference
    format: txt
    url: https://example.test/demo.txt
    size_bytes: 11
    sha256: "{HELLO_SHA}"
"""


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Point horizon at a temp content dir (with our catalog) and packs dir."""
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "packs.yaml").write_text(CATALOG, encoding="utf-8")
    monkeypatch.setattr(settings, "content_dir", str(content_dir))
    monkeypatch.setattr(settings.content_packs, "dir", str(tmp_path / "packs"))
    return tmp_path


class _FakeStream:
    def __init__(self, data: bytes):
        self._data = data
        self.headers = {"content-length": str(len(data))}

    def raise_for_status(self) -> None:
        pass

    def iter_bytes(self, size: int):
        for i in range(0, len(self._data), size):
            yield self._data[i : i + size]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeClient:
    def __init__(self, data: bytes):
        self._data = data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def stream(self, method: str, url: str):
        return _FakeStream(self._data)


def _patch_download(monkeypatch, data: bytes = HELLO):
    monkeypatch.setattr(httpx, "Client", lambda *a, **k: _FakeClient(data))


# --- catalog + on-disk state ------------------------------------------------


def test_load_catalog(env):
    specs = packs.load_catalog()
    assert [s.id for s in specs] == ["demo"]
    assert packs.get_spec("demo").title == "Demo Pack"
    assert packs.get_spec("missing") is None


def test_install_from_file_records_manifest(env, tmp_path):
    src = tmp_path / "demo.txt"
    src.write_bytes(HELLO)
    manifest = packs.install_from_file(packs.get_spec("demo"), src, move=False)
    assert manifest["id"] == "demo"
    assert manifest["size_bytes"] == 11
    assert packs.is_installed("demo")
    assert packs.read_manifest("demo")["sha256"] == HELLO_SHA


def test_install_rejects_bad_checksum(env, tmp_path):
    src = tmp_path / "demo.txt"
    src.write_bytes(b"corrupted")
    with pytest.raises(packs.PackError):
        packs.install_from_file(packs.get_spec("demo"), src, move=False)
    assert not packs.is_installed("demo")


def test_pack_status_merges_catalog_and_disk(env, tmp_path):
    rows = {r["id"]: r for r in packs.pack_status()}
    assert rows["demo"]["installed"] is False

    src = tmp_path / "demo.txt"
    src.write_bytes(HELLO)
    packs.install_from_file(packs.get_spec("demo"), src, move=False)

    rows = {r["id"]: r for r in packs.pack_status()}
    assert rows["demo"]["installed"] is True
    assert rows["demo"]["installed_size"] == 11


def test_remove_pack(env, tmp_path):
    src = tmp_path / "demo.txt"
    src.write_bytes(HELLO)
    packs.install_from_file(packs.get_spec("demo"), src, move=False)
    assert packs.remove_pack("demo") is True
    assert not packs.is_installed("demo")
    assert packs.remove_pack("demo") is False  # already gone


def test_verify_file_skips_when_no_checksum(env, tmp_path):
    f = tmp_path / "x"
    f.write_bytes(b"anything")
    assert packs.verify_file(f, "") is True


# --- download (faked network) ----------------------------------------------


def test_download_pack_installs(env, monkeypatch):
    _patch_download(monkeypatch)
    manifest = packs.download_pack("demo")
    assert manifest["size_bytes"] == 11
    assert packs.is_installed("demo")


def test_download_pack_unknown(env):
    with pytest.raises(packs.PackError):
        packs.download_pack("nope")


def test_download_pack_bad_checksum_does_not_install(env, monkeypatch):
    _patch_download(monkeypatch, data=b"corrupted")
    with pytest.raises(packs.PackError):
        packs.download_pack("demo")
    assert not packs.is_installed("demo")


def test_download_manager_runs_to_completion(env, monkeypatch):
    _patch_download(monkeypatch)
    manager = packs.DownloadManager()
    manager.start("demo")
    deadline = time.time() + 5
    while time.time() < deadline:
        job = manager.status("demo")
        if job and job["phase"] in ("done", "error"):
            break
        time.sleep(0.05)
    assert manager.status("demo")["phase"] == "done"
    assert packs.is_installed("demo")


# --- CLI --------------------------------------------------------------------


def test_cli_list(env, capsys):
    assert cli.main(["list"]) == 0
    out = capsys.readouterr().out
    assert "demo" in out
    assert "available" in out


def test_cli_download_and_remove(env, monkeypatch, capsys):
    _patch_download(monkeypatch)
    assert cli.main(["download", "demo"]) == 0
    assert packs.is_installed("demo")
    capsys.readouterr()
    # A second download without --force is a no-op.
    assert cli.main(["download", "demo"]) == 0
    assert "already installed" in capsys.readouterr().out
    assert cli.main(["remove", "demo"]) == 0


def test_cli_download_unknown_pack(env, capsys):
    assert cli.main(["download", "ghost"]) == 2
    assert "Unknown pack" in capsys.readouterr().err
