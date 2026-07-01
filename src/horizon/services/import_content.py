"""Network/filesystem orchestration for importing external content as guides.

Pairs with the pure conversion functions in :mod:`horizon.services.importer`
(parsing + Markdown rendering) the same way :mod:`horizon.services.packs`
pairs its pure catalog/on-disk logic with a network downloader: this module is
the one seam that touches the network or writes files, so both the
``horizon-content import`` CLI and the admin web import wizard call the same
functions instead of duplicating fetch logic.
"""

from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import urlparse

from horizon.config import settings
from horizon.services import importer

logger = logging.getLogger("horizon")

_USER_AGENT = "horizon-content-importer/1 (offline self-hosted import tool)"


class ContentImportError(RuntimeError):
    """An import failed in a way that is safe to show the operator directly."""


def default_guides_dir() -> Path:
    """Where imported guides land by default: ``<content_dir>/guides``."""
    return Path(settings.content_dir) / "guides"


def fetch_text(url: str) -> str:
    """Fetch a URL's body as text, wrapping any failure as :class:`ContentImportError`."""
    import httpx

    try:
        with httpx.Client(
            timeout=30, follow_redirects=True, headers={"User-Agent": _USER_AGENT}
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.text
    except Exception as exc:  # noqa: BLE001 - reported to the operator, not crashed on
        raise ContentImportError(f"Could not fetch {url}: {exc}") from exc


def _guess_ext(url: str) -> str:
    suffix = Path(urlparse(url).path).suffix.split("?")[0]
    return suffix if suffix and len(suffix) <= 5 else ".jpg"


def download_images(urls: list[str], dest_dir: Path, prefix: str) -> dict[str, str]:
    """Best-effort download of step images so the guide renders fully offline.

    A failed image is just dropped (with a warning) rather than left as a
    remote URL — a guide that hot-links an image would silently break once
    the node goes offline, the one situation horizon must never be in.
    """
    if not urls:
        return {}
    import httpx

    dest_dir.mkdir(parents=True, exist_ok=True)
    image_map: dict[str, str] = {}
    with httpx.Client(
        timeout=20, follow_redirects=True, headers={"User-Agent": _USER_AGENT}
    ) as client:
        for i, url in enumerate(urls, start=1):
            filename = f"{prefix}-{i}{_guess_ext(url)}"
            try:
                response = client.get(url)
                response.raise_for_status()
            except Exception as exc:  # noqa: BLE001 - one bad image shouldn't abort the import
                logger.warning("Could not download image %s: %s", url, exc)
                continue
            (dest_dir / filename).write_bytes(response.content)
            image_map[url] = f"images/{filename}"
    return image_map


def import_wikihow(
    url: str,
    *,
    category: str,
    difficulty: int = 2,
    estimated_time: str = "",
    guide_id: str | None = None,
    dest_dir: Path | None = None,
    download_images_flag: bool = True,
    force: bool = False,
) -> dict:
    """Fetch a WikiHow-shaped how-to page and write it as a guide.

    Returns ``{"guide_id": ..., "path": ...}``. Raises :class:`ContentImportError`
    on any recoverable failure (fetch, parse, or an existing guide id).
    """
    html = fetch_text(url)
    article = importer.parse_html_article(html)
    if not article.title and not article.sections:
        raise ContentImportError(
            "Could not find an article title or any numbered steps on that page "
            "— it may not be a how-to article, or its markup is unusual."
        )

    resolved_id = guide_id or importer.slugify(article.title or url)
    dest = dest_dir or default_guides_dir()
    dest.mkdir(parents=True, exist_ok=True)
    out_path = dest / f"{resolved_id}.md"
    if out_path.exists() and not force:
        raise ContentImportError(
            f"Guide '{resolved_id}' already exists at {out_path}. "
            "Choose a different id, or overwrite it."
        )

    image_map: dict[str, str] = {}
    if download_images_flag:
        sources = importer.collect_image_sources(article)
        image_map = download_images(sources, dest / "images", resolved_id)

    content = importer.render_wikihow_guide(
        article,
        guide_id=resolved_id,
        source=url,
        category=category,
        difficulty=difficulty,
        estimated_time=estimated_time,
        image_map=image_map,
    )
    out_path.write_text(content, encoding="utf-8")
    return {"guide_id": resolved_id, "path": out_path}


def import_book(
    text: str,
    *,
    source_name: str,
    category: str = "culture",
    difficulty: int = 1,
    estimated_time: str = "",
    id_prefix: str | None = None,
    dest_dir: Path | None = None,
    force: bool = False,
) -> dict:
    """Split book text into one guide per chapter.

    Returns ``{"written": [{"guide_id", "path"}, ...], "skipped": [guide_id, ...]}``.
    ``written`` may be empty (e.g. every chapter id already existed and
    ``force`` was off) — callers should check it rather than rely on an
    exception, since ``skipped`` still needs reporting in that case. Only
    raises :class:`ContentImportError` when no chapters could be found at all.
    """
    chapters = importer.split_book_into_chapters(text)
    if not chapters:
        raise ContentImportError("No content found to import.")

    prefix = id_prefix or importer.slugify(Path(source_name).stem)
    dest = dest_dir or default_guides_dir()
    dest.mkdir(parents=True, exist_ok=True)

    written: list[dict] = []
    skipped: list[str] = []
    for i, chapter in enumerate(chapters, start=1):
        if len(chapters) == 1:
            resolved_id = prefix
        else:
            suffix = importer.chapter_slug_suffix(chapter.title)
            resolved_id = f"{prefix}-{i:02d}-{suffix}" if suffix else f"{prefix}-{i:02d}"

        out_path = dest / f"{resolved_id}.md"
        if out_path.exists() and not force:
            skipped.append(resolved_id)
            continue

        content = importer.render_book_guide(
            chapter,
            guide_id=resolved_id,
            source=source_name,
            category=category,
            difficulty=difficulty,
            estimated_time=estimated_time,
        )
        out_path.write_text(content, encoding="utf-8")
        written.append({"guide_id": resolved_id, "path": out_path})

    return {"written": written, "skipped": skipped}
