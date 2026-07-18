"""Optional offline content packs (Wikipedia, medical ZIMs, maps, ...).

Content packs are large optional downloads fetched while the internet is
available and then used fully offline. They are never required: horizon's
journeys, guides, md skills, and assistant all work without any pack installed.

This module is split so the parts that matter for correctness stay pure and
unit-testable with no network:

* catalog loading (:func:`load_catalog`) reads a shipped YAML list of available
  packs, so the catalog is known offline;
* the on-disk state (:func:`installed_packs`, manifests, :func:`verify_file`,
  :func:`install_from_file`, :func:`remove_pack`) only touches the local packs
  directory;
* only :func:`download_pack` reaches the network, and it funnels through
  ``install_from_file`` once the bytes are on disk.

A small threaded :class:`DownloadManager` lets the admin web wizard kick off a
download and poll its progress without blocking the request; the CLI uses the
synchronous :func:`download_pack` directly.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import threading
import time
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel

from horizon.config import settings

logger = logging.getLogger("horizon")

# Name of the per-pack manifest written into <packs_dir>/<id>/.
_MANIFEST = "manifest.json"

# Streaming download chunk size: small enough for weak hardware, big enough to
# avoid excessive Python overhead on multi-GB files.
_CHUNK = 1 << 20  # 1 MiB

# Progress callbacks receive (downloaded_bytes, total_bytes_or_None, phase).
ProgressCb = Callable[[int, "int | None", str], None]


class PackSpec(BaseModel):
    """A pack as described in the shipped catalog (an *available* pack)."""

    id: str
    title: str
    description: str = ""
    category: str = "reference"
    format: str = ""
    url: str = ""
    size_bytes: int | None = None
    sha256: str = ""


# --- Catalog (pure) ---------------------------------------------------------


def _catalog_path() -> Path | None:
    """Locate the pack catalog: the operator's copy first, then the bundled one.

    Prefer ``<content_dir>/packs.yaml`` (writable, operator-editable, created by
    the first-run content seed) and fall back to the catalog shipped in the repo
    so the catalog is available even before any seed has run.
    """
    live = Path(settings.content_dir) / "packs.yaml"
    if live.is_file():
        return live
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "content" / "packs.yaml"
        if candidate.is_file():
            return candidate
    return None


def load_catalog() -> list[PackSpec]:
    """Return the available packs from the catalog (empty if none is found)."""
    path = _catalog_path()
    if path is None:
        logger.warning("No content-pack catalog (packs.yaml) found.")
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    specs: list[PackSpec] = []
    for entry in data.get("packs", []):
        try:
            specs.append(PackSpec.model_validate(entry))
        except Exception as exc:  # noqa: BLE001 - skip a malformed entry, keep the rest
            logger.warning("Skipping malformed pack entry %r: %s", entry, exc)
    return specs


def get_spec(pack_id: str) -> PackSpec | None:
    """Return the catalog spec for ``pack_id``, or ``None`` if unknown."""
    for spec in load_catalog():
        if spec.id == pack_id:
            return spec
    return None


def human_size(num: int | None) -> str:
    """Format a byte count compactly (``?`` when unknown)."""
    if not num:
        return "?"
    size = float(num)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


# --- On-disk state (pure) ---------------------------------------------------


def packs_dir() -> Path:
    """The directory holding installed packs (from ``content_packs.dir``)."""
    return Path(settings.content_packs.dir)


def _pack_dir(pack_id: str) -> Path:
    return packs_dir() / pack_id


def _manifest_path(pack_id: str) -> Path:
    return _pack_dir(pack_id) / _MANIFEST


def is_installed(pack_id: str) -> bool:
    """True when ``pack_id`` has a complete manifest on disk."""
    return _manifest_path(pack_id).is_file()


def read_manifest(pack_id: str) -> dict | None:
    """Return the installed pack's manifest, or ``None`` if not installed."""
    path = _manifest_path(pack_id)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read manifest for %s: %s", pack_id, exc)
        return None


def installed_packs() -> list[dict]:
    """Return manifests for every installed pack, sorted by id."""
    root = packs_dir()
    if not root.is_dir():
        return []
    manifests: list[dict] = []
    for child in sorted(root.iterdir()):
        if child.is_dir() and (manifest := read_manifest(child.name)) is not None:
            manifests.append(manifest)
    return manifests


def pack_file_path(pack_id: str) -> Path | None:
    """Absolute path to an installed pack's payload file, or ``None`` if not
    installed. Resolves the manifest's ``"file"`` key against the pack's dir.
    """
    manifest = read_manifest(pack_id)
    if manifest is None or "file" not in manifest:
        return None
    return _pack_dir(pack_id) / manifest["file"]


def has_installed_zim_pack() -> bool:
    """True if at least one installed pack is a ZIM (i.e. the reference-library
    reader has something to show). Used to conditionally show that nav item.
    """
    return any(m.get("format") == "zim" for m in installed_packs())


def pack_mbtiles_path(pack_id: str) -> Path | None:
    """Absolute path to a maps pack's dropped-in ``.mbtiles`` file, or ``None``.

    A ``maps-*`` pack downloads raw ``.osm.pbf`` source data (see the comment
    block in ``content/packs.yaml``); to actually view it, an operator renders
    it once, off the node, with Planetiler and copies the resulting
    ``.mbtiles`` file into this pack's own directory alongside the ``.pbf``
    (see ``docs/operating.md``). The exact filename doesn't matter -- this
    looks for the first ``*.mbtiles`` file in the pack's directory.
    """
    directory = _pack_dir(pack_id)
    if not directory.is_dir():
        return None
    matches = sorted(directory.glob("*.mbtiles"))
    return matches[0] if matches else None


def has_installed_map_pack() -> bool:
    """True if at least one installed maps pack has a rendered ``.mbtiles``
    companion (i.e. the map viewer has something to show). Used to
    conditionally show that nav item.
    """
    return any(
        m.get("category") == "maps" and pack_mbtiles_path(m["id"]) is not None
        for m in installed_packs()
    )


def pack_status() -> list[dict]:
    """Merge the catalog with on-disk state for display.

    Each row carries the catalog fields plus ``installed`` and (when installed)
    the manifest's ``installed_size`` and ``installed_at``. Installed packs that
    are no longer in the catalog are still listed so operators can remove them.
    """
    rows: list[dict] = []
    seen: set[str] = set()
    for spec in load_catalog():
        seen.add(spec.id)
        manifest = read_manifest(spec.id)
        row = spec.model_dump()
        row["installed"] = manifest is not None
        row["in_catalog"] = True
        if manifest is not None:
            row["installed_size"] = manifest.get("size_bytes")
            row["installed_at"] = manifest.get("installed_at")
        rows.append(row)
    for manifest in installed_packs():
        if manifest["id"] in seen:
            continue
        rows.append(
            {
                "id": manifest["id"],
                "title": manifest.get("title", manifest["id"]),
                "description": "Installed pack not in the current catalog.",
                "category": manifest.get("category", ""),
                "format": manifest.get("format", ""),
                "url": "",
                "size_bytes": manifest.get("size_bytes"),
                "sha256": manifest.get("sha256", ""),
                "installed": True,
                "in_catalog": False,
                "installed_size": manifest.get("size_bytes"),
                "installed_at": manifest.get("installed_at"),
            }
        )
    return rows


def _filename_for(spec: PackSpec) -> str:
    """Best-effort download filename from the URL (falls back to ``<id>.dat``)."""
    name = Path(urlparse(spec.url).path).name
    return name or f"{spec.id}.dat"


def verify_file(path: Path, sha256: str) -> bool:
    """Return True if ``path`` matches ``sha256``. Empty checksum ⇒ skip (True)."""
    if not sha256:
        return True
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(_CHUNK), b""):
            digest.update(block)
    return digest.hexdigest() == sha256.strip().lower()


class PackError(RuntimeError):
    """A content-pack operation failed (bad checksum, unknown pack, I/O)."""


def install_from_file(spec: PackSpec, source: Path, *, move: bool = True) -> dict:
    """Place an already-downloaded pack file under the packs dir and record it.

    Verifies the checksum (when the spec carries one), installs the file into
    ``<packs_dir>/<id>/`` and writes a manifest. Pure local I/O: this is the
    seam the network downloader and the tests share. Returns the manifest.
    """
    source = Path(source)
    if not source.is_file():
        raise PackError(f"Source file does not exist: {source}")
    if not verify_file(source, spec.sha256):
        raise PackError(f"Checksum mismatch for pack {spec.id!r}; refusing to install.")

    dest_dir = _pack_dir(spec.id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = _filename_for(spec)
    dest_file = dest_dir / filename

    if move:
        # os.replace is atomic within a filesystem; fall back to copy across devices.
        try:
            source.replace(dest_file)
        except OSError:
            shutil.copy2(source, dest_file)
            source.unlink(missing_ok=True)
    else:
        shutil.copy2(source, dest_file)

    manifest = {
        "id": spec.id,
        "title": spec.title,
        "category": spec.category,
        "format": spec.format,
        "file": filename,
        "size_bytes": dest_file.stat().st_size,
        "sha256": spec.sha256,
        "installed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    _manifest_path(spec.id).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    logger.info("Installed content pack %s into %s", spec.id, dest_dir)
    return manifest


def remove_pack(pack_id: str) -> bool:
    """Delete an installed pack's directory. Returns True if anything was removed."""
    directory = _pack_dir(pack_id)
    if not directory.is_dir():
        return False
    shutil.rmtree(directory)
    logger.info("Removed content pack %s", pack_id)
    return True


# --- Download (network) -----------------------------------------------------


def download_pack(pack_id: str, *, progress_cb: ProgressCb | None = None) -> dict:
    """Download, verify, and install a pack from the catalog. Returns its manifest.

    Network is used only here, and only while the operator chooses to download.
    The stream is written to a ``.part`` file next to the final location and
    only promoted via :func:`install_from_file` once complete and verified, so a
    partial or corrupt download never looks installed.
    """
    spec = get_spec(pack_id)
    if spec is None:
        raise PackError(f"Unknown pack: {pack_id!r}")
    if not spec.url:
        raise PackError(f"Pack {pack_id!r} has no download URL.")

    dest_dir = _pack_dir(spec.id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    part = dest_dir / f"{_filename_for(spec)}.part"

    import httpx

    def report(done: int, total: int | None, phase: str) -> None:
        if progress_cb is not None:
            progress_cb(done, total, phase)

    try:
        # trust_env=True (default): pack downloads are external internet traffic,
        # so they should honour any configured HTTP(S) proxy.
        timeout = httpx.Timeout(60.0, connect=10.0)
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            with client.stream("GET", spec.url) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("content-length") or 0) or spec.size_bytes
                downloaded = 0
                report(0, total, "downloading")
                with part.open("wb") as fh:
                    for chunk in resp.iter_bytes(_CHUNK):
                        fh.write(chunk)
                        downloaded += len(chunk)
                        report(downloaded, total, "downloading")
    except httpx.HTTPError as exc:
        part.unlink(missing_ok=True)
        raise PackError(f"Download failed for {pack_id!r}: {exc}") from exc

    report(part.stat().st_size, part.stat().st_size, "verifying")
    manifest = install_from_file(spec, part, move=True)
    report(manifest["size_bytes"], manifest["size_bytes"], "done")
    return manifest


# --- Background download manager (for the admin web wizard) -----------------


class DownloadManager:
    """Tracks background pack downloads so the web UI can poll their progress.

    One download per pack at a time. State lives in memory only — restarting
    horizon clears in-flight jobs, but a completed pack is recorded on disk via
    its manifest, so nothing important is lost.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, dict] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

    def status(self, pack_id: str) -> dict | None:
        """Return a copy of the current job state for ``pack_id`` (or ``None``)."""
        with self._lock:
            job = self._jobs.get(pack_id)
            return dict(job) if job is not None else None

    def is_active(self, pack_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(pack_id)
            return job is not None and job["phase"] in ("queued", "downloading", "verifying")

    def start(self, pack_id: str) -> dict:
        """Start a background download (no-op if one is already running)."""
        with self._lock:
            existing = self._jobs.get(pack_id)
            if existing is not None and existing["phase"] in (
                "queued",
                "downloading",
                "verifying",
            ):
                return dict(existing)
            self._jobs[pack_id] = {
                "pack_id": pack_id,
                "phase": "queued",
                "downloaded": 0,
                "total": None,
                "error": None,
            }
            thread = threading.Thread(target=self._run, args=(pack_id,), daemon=True)
            self._threads[pack_id] = thread
            thread.start()
            return dict(self._jobs[pack_id])

    def _update(self, pack_id: str, **fields: object) -> None:
        with self._lock:
            job = self._jobs.get(pack_id)
            if job is not None:
                job.update(fields)

    def _run(self, pack_id: str) -> None:
        def progress(done: int, total: int | None, phase: str) -> None:
            self._update(pack_id, downloaded=done, total=total, phase=phase)

        try:
            download_pack(pack_id, progress_cb=progress)
            self._update(pack_id, phase="done", error=None)
        except Exception as exc:  # noqa: BLE001 - surface failure to the poller
            logger.warning("Background download of %s failed: %s", pack_id, exc)
            self._update(pack_id, phase="error", error=str(exc))


# Shared manager used by the admin routes.
download_manager = DownloadManager()
