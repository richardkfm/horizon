"""``horizon-content`` CLI: manage optional offline content packs.

Content packs (offline Wikipedia, medical ZIMs, maps, etc.) are large optional
downloads fetched while internet is available, then used fully offline. This is
a scaffold stub; the download/verify/install logic lands in the content-packs
step. A web wizard on the admin page will wrap the same operations.
"""

from __future__ import annotations

import argparse


def cmd_list(args: argparse.Namespace) -> int:
    """List installed and available content packs."""
    raise NotImplementedError("Implemented in the content-packs step.")


def cmd_download(args: argparse.Namespace) -> int:
    """Download and install a content pack by name."""
    raise NotImplementedError("Implemented in the content-packs step.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="horizon-content", description="Manage horizon offline content packs."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List installed/available packs.")
    p_list.set_defaults(func=cmd_list)

    p_dl = sub.add_parser("download", help="Download and install a pack.")
    p_dl.add_argument("name", help="Pack identifier (e.g. wikipedia, medical, maps).")
    p_dl.set_defaults(func=cmd_download)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
