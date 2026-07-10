"""Map viewer: an in-browser basemap for installed ``maps-*`` content packs.

A ``maps-*`` pack (``services/packs.py``) downloads raw OpenStreetMap
``.osm.pbf`` data -- source material, not something a browser can render, so
downloading one used to be a dead end. This router serves an already-rendered
``.mbtiles`` file that an operator has dropped into the pack's directory (see
``services.packs.pack_mbtiles_path`` and ``docs/operating.md`` for the
one-time Planetiler rendering step): a landing page listing installed maps, a
per-pack viewer, and a vector-tile endpoint, displayed with the vendored
MapLibre GL JS (no CDN, no network at runtime).

Only installed maps packs with a dropped-in ``.mbtiles`` are ever listed or
resolvable here -- this router never touches the network and never renders
anything itself.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from horizon import __version__
from horizon.config import assistant_enabled, low_power_enabled
from horizon.services import packs as packs_service
from horizon.web.assets import static_url

router = APIRouter(prefix="/maps", tags=["maps"])

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals["low_power_enabled"] = low_power_enabled
templates.env.globals["assistant_enabled"] = assistant_enabled
templates.env.globals["static_url"] = static_url
templates.env.globals["version"] = __version__
templates.env.globals["reference_library_enabled"] = packs_service.has_installed_zim_pack
templates.env.globals["map_viewer_enabled"] = packs_service.has_installed_map_pack


def _installed_map_packs() -> list[dict]:
    """Installed maps-category rows that have a rendered ``.mbtiles`` companion."""
    return [
        row
        for row in packs_service.pack_status()
        if row["installed"]
        and row["category"] == "maps"
        and packs_service.pack_mbtiles_path(row["id"]) is not None
    ]


def _mbtiles_path_or_404(pack_id: str) -> Path:
    path = packs_service.pack_mbtiles_path(pack_id)
    if path is None or not path.is_file():
        raise HTTPException(
            status_code=404, detail=f"No rendered map available for pack: {pack_id}"
        )
    return path


@router.get("", response_class=HTMLResponse)
def maps_index(request: Request) -> HTMLResponse:
    """List installed, rendered map packs."""
    from horizon.services import mbtiles

    rows = []
    for row in _installed_map_packs():
        path = packs_service.pack_mbtiles_path(row["id"])
        try:
            info = mbtiles.pack_info(path)
        except mbtiles.MBTilesUnavailableError:
            continue
        rows.append({"id": row["id"], "title": row["title"], "map_name": info.name})

    return templates.TemplateResponse(request, "maps_index.html", {"packs": rows})


@router.get("/{pack_id}", response_class=HTMLResponse)
def map_viewer(request: Request, pack_id: str) -> HTMLResponse:
    """A pack's viewer page: a full-size MapLibre map over its rendered tiles."""
    from horizon.services import mbtiles

    row = next((r for r in _installed_map_packs() if r["id"] == pack_id), None)
    path = _mbtiles_path_or_404(pack_id)
    info = mbtiles.pack_info(path)

    return templates.TemplateResponse(
        request,
        "maps_pack.html",
        {
            "pack_id": pack_id,
            "title": row["title"] if row else info.name,
            "info": info,
        },
    )


@router.get("/{pack_id}/tiles/{z}/{x}/{y}.pbf")
def map_tile(pack_id: str, z: int, x: int, y: int) -> Response:
    """Serve one vector tile straight out of the pack's ``.mbtiles`` (SQLite)."""
    from horizon.services import mbtiles

    path = _mbtiles_path_or_404(pack_id)
    data = mbtiles.get_tile(path, z, x, y)
    if data is None:
        # A missing tile within the rendered bounds is normal (open ocean, a
        # zoom level beyond what was rendered) -- 204 lets MapLibre skip it
        # quietly instead of treating it as a load failure.
        return Response(status_code=204)
    headers = {"Content-Encoding": "gzip"} if mbtiles.is_gzipped(data) else {}
    return Response(content=data, media_type="application/x-protobuf", headers=headers)
