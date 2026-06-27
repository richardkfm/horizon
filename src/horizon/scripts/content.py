"""``horizon-content`` CLI: manage optional offline content packs.

Content packs (offline Wikipedia, medical ZIMs, maps, ...) are large optional
downloads fetched while internet is available, then used fully offline. The same
operations are wrapped by a wizard on the admin page; this CLI is the headless
equivalent for servers without a browser to hand.
"""

from __future__ import annotations

import argparse
import sys

from horizon.services.packs import (
    PackError,
    download_pack,
    get_spec,
    human_size,
    pack_status,
    read_manifest,
    remove_pack,
)


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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
