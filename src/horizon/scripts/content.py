"""``horizon-content`` CLI: manage optional offline content packs and imports.

Content packs (offline Wikipedia, medical ZIMs, maps, ...) are large optional
downloads fetched while internet is available, then used fully offline. The same
operations are wrapped by a wizard on the admin page; this CLI is the headless
equivalent for servers without a browser to hand.

``import`` follows the same online-during-setup, offline-after pattern for
smaller, one-off sources: a WikiHow-shaped how-to page or a local book file is
fetched/read once, while the operator is online, and converted into a regular
guide (Markdown + front matter) under ``<content_dir>/guides``. From that point
it is indistinguishable from any other guide — see ``horizon.services.importer``
for the (pure, offline-testable) conversion logic.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

from horizon.services.packs import (
    PackError,
    download_pack,
    get_spec,
    human_size,
    pack_status,
    read_manifest,
    remove_pack,
)

_IMPORT_USER_AGENT = "horizon-content-importer/1 (offline self-hosted import tool)"


def cmd_list(args: argparse.Namespace) -> int:
    """List installed and available content packs."""
    rows = pack_status()
    if not rows:
        print("No content packs in the catalog.")
        return 0
    width = max(len(r["id"]) for r in rows)
    print(f"{'PACK':<{width}}  STATUS      SIZE       TITLE")
    for row in rows:
        status = "installed" if row["installed"] else "available"
        size = human_size(row.get("installed_size") or row.get("size_bytes"))
        print(f"{row['id']:<{width}}  {status:<10}  {size:<9}  {row['title']}")
    return 0


def cmd_download(args: argparse.Namespace) -> int:
    """Download and install a content pack by name."""
    spec = get_spec(args.name)
    if spec is None:
        print(f"Unknown pack: {args.name!r}. Run `horizon-content list`.", file=sys.stderr)
        return 2
    if read_manifest(args.name) is not None and not args.force:
        print(f"Pack {args.name!r} is already installed. Use --force to re-download.")
        return 0

    print(f"Downloading {spec.title} ({human_size(spec.size_bytes)}) from {spec.url}")

    def progress(done: int, total: int | None, phase: str) -> None:
        if phase == "downloading" and total:
            pct = 100 * done / total
            print(f"\r  {pct:5.1f}%  {human_size(done)} / {human_size(total)}", end="", flush=True)
        elif phase == "verifying":
            print("\r  verifying checksum...", end="", flush=True)

    try:
        manifest = download_pack(args.name, progress_cb=progress)
    except PackError as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        return 1
    print(f"\nInstalled {manifest['id']} ({human_size(manifest['size_bytes'])}).")
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    """Remove an installed content pack."""
    if remove_pack(args.name):
        print(f"Removed {args.name}.")
        return 0
    print(f"Pack {args.name!r} is not installed.", file=sys.stderr)
    return 1


# --- import (wikihow / book -> guide) ----------------------------------------


def _guides_dest(args: argparse.Namespace) -> Path:
    if args.dest:
        return Path(args.dest)
    from horizon.config import settings

    return Path(settings.content_dir) / "guides"


def _fetch_text(url: str) -> str:
    import httpx

    with httpx.Client(
        timeout=30, follow_redirects=True, headers={"User-Agent": _IMPORT_USER_AGENT}
    ) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text


_CHAPTER_PREFIX_RE = re.compile(
    r"^(?:chapter|part|book)\s+[ivxlcdm\d]+\b\s*[:.\-–—]?\s*", re.IGNORECASE
)


def _chapter_slug_suffix(title: str) -> str:
    """Slugify a chapter title for a guide-id suffix, dropping a leading "Chapter N".

    The numbered-index prefix (``-01-``, ``-02-``, ...) already encodes the
    chapter's position, so repeating "chapter-1-" in the slug would just be
    noise; the title's actual subject (e.g. "Greetings") is more useful.
    """
    from horizon.services.importer import slugify

    remainder = _CHAPTER_PREFIX_RE.sub("", title).strip()
    return slugify(remainder or title)


def _guess_ext(url: str) -> str:
    suffix = Path(urlparse(url).path).suffix.split("?")[0]
    return suffix if suffix and len(suffix) <= 5 else ".jpg"


def _download_images(urls: list[str], dest_dir: Path, prefix: str) -> dict[str, str]:
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
        timeout=20, follow_redirects=True, headers={"User-Agent": _IMPORT_USER_AGENT}
    ) as client:
        for i, url in enumerate(urls, start=1):
            filename = f"{prefix}-{i}{_guess_ext(url)}"
            try:
                response = client.get(url)
                response.raise_for_status()
            except Exception as exc:  # noqa: BLE001 - one bad image shouldn't abort the import
                print(f"  warning: could not download image {url}: {exc}", file=sys.stderr)
                continue
            (dest_dir / filename).write_bytes(response.content)
            image_map[url] = f"images/{filename}"
    return image_map


def _maybe_reseed(args: argparse.Namespace, *, guides_now: str) -> None:
    if not args.reseed:
        print(
            "Run `horizon-admin seed --force` (or restart) to load it, then "
            "`horizon-admin reindex` so the assistant can cite it."
        )
        return
    from horizon.db import init_db
    from horizon.seed import reseed

    init_db()
    summary = reseed()
    print(
        f"Re-seeded: {summary['after']['guides']} guides now in the database "
        f"({guides_now}). Run `horizon-admin reindex` so the assistant can cite the new content."
    )


def cmd_import_wikihow(args: argparse.Namespace) -> int:
    """Fetch a WikiHow-shaped how-to page and save it as a guide."""
    from horizon.services import importer

    try:
        html = _fetch_text(args.url)
    except Exception as exc:  # noqa: BLE001 - report rather than crash
        print(f"Error fetching {args.url}: {exc}", file=sys.stderr)
        return 1

    article = importer.parse_html_article(html)
    if not article.title and not article.sections:
        print(
            "Could not find an article title or any numbered steps on that page "
            "— it may not be a how-to article, or its markup is unusual.",
            file=sys.stderr,
        )
        return 1

    guide_id = args.id or importer.slugify(article.title or args.url)
    dest = _guides_dest(args)
    dest.mkdir(parents=True, exist_ok=True)
    out_path = dest / f"{guide_id}.md"
    if out_path.exists() and not args.force:
        print(
            f"Guide {guide_id!r} already exists at {out_path}. "
            "Pass --id for a different id or --force to overwrite.",
            file=sys.stderr,
        )
        return 1

    image_map: dict[str, str] = {}
    if not args.no_images:
        sources = importer.collect_image_sources(article)
        image_map = _download_images(sources, dest / "images", guide_id)

    content = importer.render_wikihow_guide(
        article,
        guide_id=guide_id,
        source=args.url,
        category=args.category,
        difficulty=args.difficulty,
        estimated_time=args.estimated_time,
        image_map=image_map,
    )
    out_path.write_text(content, encoding="utf-8")
    print(f"Wrote {out_path} (id: {guide_id}, category: {args.category}).")
    _maybe_reseed(args, guides_now=guide_id)
    return 0


def cmd_import_book(args: argparse.Namespace) -> int:
    """Split a local text/Markdown book into one guide per chapter."""
    from horizon.services import importer

    path = Path(args.path)
    if not path.is_file():
        print(f"No such file: {path}", file=sys.stderr)
        return 2

    text = path.read_text(encoding="utf-8", errors="replace")
    chapters = importer.split_book_into_chapters(text)
    if not chapters:
        print("No content found to import.", file=sys.stderr)
        return 1

    prefix = args.id_prefix or importer.slugify(path.stem)
    dest = _guides_dest(args)
    dest.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    for i, chapter in enumerate(chapters, start=1):
        if len(chapters) == 1:
            guide_id = prefix
        else:
            suffix = _chapter_slug_suffix(chapter.title)
            guide_id = f"{prefix}-{i:02d}-{suffix}" if suffix else f"{prefix}-{i:02d}"

        out_path = dest / f"{guide_id}.md"
        if out_path.exists() and not args.force:
            print(
                f"  skipping {guide_id!r}: already exists at {out_path} (use --force to overwrite)",
                file=sys.stderr,
            )
            continue

        content = importer.render_book_guide(
            chapter,
            guide_id=guide_id,
            source=str(path),
            category=args.category,
            difficulty=args.difficulty,
            estimated_time=args.estimated_time,
        )
        out_path.write_text(content, encoding="utf-8")
        written.append(guide_id)

    if not written:
        print("No guides were written.", file=sys.stderr)
        return 1

    print(f"Wrote {len(written)} guide(s) to {dest}: {', '.join(written)}")
    _maybe_reseed(args, guides_now=", ".join(written))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="horizon-content", description="Manage horizon offline content packs."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List installed/available packs.")
    p_list.set_defaults(func=cmd_list)

    p_dl = sub.add_parser("download", help="Download and install a pack.")
    p_dl.add_argument("name", help="Pack identifier (e.g. wikipedia-en-mini).")
    p_dl.add_argument("--force", action="store_true", help="Re-download even if already installed.")
    p_dl.set_defaults(func=cmd_download)

    p_rm = sub.add_parser("remove", help="Remove an installed pack.")
    p_rm.add_argument("name", help="Pack identifier to remove.")
    p_rm.set_defaults(func=cmd_remove)

    from horizon.models import Category

    categories = [c.value for c in Category]

    p_import = sub.add_parser("import", help="Import a how-to page or a local book as guide(s).")
    import_sub = p_import.add_subparsers(dest="import_command", required=True)

    p_wikihow = import_sub.add_parser("wikihow", help="Fetch a how-to page and save it as a guide.")
    p_wikihow.add_argument("url", help="URL of a wikihow-style how-to article.")
    p_wikihow.add_argument("--id", help="Guide id (default: slug of the article title).")
    p_wikihow.add_argument(
        "--category",
        default="culture",
        choices=categories,
        help="Guide category (default: culture).",
    )
    p_wikihow.add_argument(
        "--difficulty",
        type=int,
        default=2,
        choices=range(1, 6),
        help="Difficulty 1-5 (default: 2).",
    )
    p_wikihow.add_argument(
        "--estimated-time", default="", help="Override the auto-estimated reading time."
    )
    p_wikihow.add_argument(
        "--dest", help="Directory to write the guide into (default: <content_dir>/guides)."
    )
    p_wikihow.add_argument("--no-images", action="store_true", help="Skip downloading step images.")
    p_wikihow.add_argument(
        "--force", action="store_true", help="Overwrite an existing guide with the same id."
    )
    p_wikihow.add_argument(
        "--reseed",
        action="store_true",
        help="Reload the database from disk immediately after writing.",
    )
    p_wikihow.set_defaults(func=cmd_import_wikihow)

    p_book = import_sub.add_parser(
        "book", help="Split a local text/Markdown book into chapter guides."
    )
    p_book.add_argument("path", help="Path to a local .txt or .md book file.")
    p_book.add_argument("--id-prefix", help="Guide id prefix (default: slug of the file name).")
    p_book.add_argument(
        "--category",
        default="culture",
        choices=categories,
        help="Guide category (default: culture).",
    )
    p_book.add_argument(
        "--difficulty",
        type=int,
        default=1,
        choices=range(1, 6),
        help="Difficulty 1-5 (default: 1).",
    )
    p_book.add_argument(
        "--estimated-time", default="", help="Override the auto-estimated reading time."
    )
    p_book.add_argument(
        "--dest", help="Directory to write guides into (default: <content_dir>/guides)."
    )
    p_book.add_argument(
        "--force", action="store_true", help="Overwrite existing guides with the same id."
    )
    p_book.add_argument(
        "--reseed",
        action="store_true",
        help="Reload the database from disk immediately after writing.",
    )
    p_book.set_defaults(func=cmd_import_book)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
