"""Hardening regressions for content packs: path traversal, manifests, downloads."""

from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from horizon.config import settings
from horizon.main import app
from horizon.scripts import admin as admin_cli
from horizon.scripts import content as content_cli
from horizon.services import packs

TOKEN = "hardening-packs-token"


@pytest.fixture
def packs_root(tmp_path, monkeypatch):
    """Packs dir nested one level down, with a sentinel file beside it."""
    root = tmp_path / "root"
    pdir = root / "packs"
    pdir.mkdir(parents=True)
    (root / "KEEP.txt").write_text("x", "utf-8")
    monkeypatch.setattr(settings.content_packs, "dir", str(pdir))
    return pdir


@pytest.mark.parametrize(
    "pack_id", ["..", ".", "../x", "a/b", "/etc", "", "UPPER", "-lead", "a..b", "a\x00b"]
)
def test_invalid_pack_ids_are_rejected(packs_root, pack_id):
    assert not packs.is_valid_pack_id(pack_id)
    with pytest.raises(packs.PackError):
        packs._pack_dir(pack_id)
    assert packs.remove_pack(pack_id) is False
    assert packs.read_manifest(pack_id) is None
    assert packs.pack_file_path(pack_id) is None
    assert packs.pack_mbtiles_path(pack_id) is None
    assert (packs_root.parent / "KEEP.txt").exists()


def test_valid_pack_ids():
    for pack_id in ("wikipedia-en-mini", "maps-africa-algeria", "a", "a.b_c-1"):
        assert packs.is_valid_pack_id(pack_id)


def test_symlinked_pack_dir_is_not_removed(packs_root, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "precious.txt").write_text("x", "utf-8")
    (packs_root / "evil").symlink_to(outside, target_is_directory=True)
    assert packs.remove_pack("evil") is False
    assert (outside / "precious.txt").exists()


def test_admin_remove_dotdot_is_refused(packs_root, monkeypatch):
    monkeypatch.setenv("HORIZON_ADMIN_TOKEN", TOKEN)
    with TestClient(app) as client:
        client.post("/admin/login", data={"token": TOKEN})
        for raw in ("%2E%2E", "..%2F..", "%2e"):
            resp = client.post(f"/admin/packs/{raw}/remove")
            assert resp.status_code == 404
    assert packs_root.is_dir()
    assert (packs_root.parent / "KEEP.txt").exists()


def test_cli_remove_rejects_traversal(packs_root, capsys):
    class Args:
        name = ".."

    assert admin_cli.cmd_packs_remove(Args()) == 2
    assert content_cli.cmd_remove(Args()) == 2
    assert packs_root.is_dir()


def _write_manifest(packs_root, name: str, payload: object) -> None:
    (packs_root / name).mkdir()
    (packs_root / name / "manifest.json").write_text(json.dumps(payload), "utf-8")


def test_bad_manifests_are_skipped_not_fatal(packs_root, monkeypatch):
    _write_manifest(packs_root, "a-list", [])
    _write_manifest(packs_root, "no-id", {"title": "x"})
    _write_manifest(packs_root, "wrong-id", {"id": "something-else"})
    _write_manifest(packs_root, "good", {"id": "good", "title": "Good", "file": "f.zim"})
    _write_manifest(packs_root, "escape", {"id": "escape", "file": "../../KEEP.txt"})
    (packs_root / "broken").mkdir()
    (packs_root / "broken" / "manifest.json").write_text("{", "utf-8")

    assert [m["id"] for m in packs.installed_packs()] == ["escape", "good"]
    assert packs.pack_file_path("escape") is None
    assert packs.pack_file_path("good") == packs_root / "good" / "f.zim"
    assert {row["id"] for row in packs.pack_status()} >= {"good"}

    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert client.get("/guides").status_code == 200


def _spec() -> packs.PackSpec:
    return packs.PackSpec(id="t", title="t", url="https://example.test/f.zim", sha256="00" * 32)


def test_checksum_failure_deletes_part_file(packs_root):
    part = packs_root / "t" / "f.zim.part"
    part.parent.mkdir()
    part.write_bytes(b"x" * 100)
    with pytest.raises(packs.PackError, match="Checksum"):
        packs.install_from_file(_spec(), part)
    assert not part.exists()


class _FailingStream:
    headers = {"content-length": "100"}

    def raise_for_status(self) -> None:
        pass

    def iter_bytes(self, size: int):
        yield b"abc"
        raise OSError(28, "No space left on device")

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> bool:
        return False


class _FakeClient:
    def __init__(self, *a, **k) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> bool:
        return False

    def stream(self, method: str, url: str):
        return _FailingStream()


def test_download_os_error_deletes_part_file(packs_root, monkeypatch):
    monkeypatch.setattr(packs, "get_spec", lambda pack_id: _spec())
    monkeypatch.setattr(httpx, "Client", _FakeClient)
    with pytest.raises(packs.PackError, match="No space left"):
        packs.download_pack("t")
    assert list((packs_root / "t").glob("*.part")) == []


def test_catalog_skips_unsafe_ids(tmp_path, monkeypatch):
    content = tmp_path / "content"
    content.mkdir()
    (content / "packs.yaml").write_text(
        "packs:\n  - id: ../evil\n    title: Evil\n  - id: ok-pack\n    title: OK\n", "utf-8"
    )
    monkeypatch.setattr(settings, "content_dir", str(content))
    assert [s.id for s in packs.load_catalog()] == ["ok-pack"]
