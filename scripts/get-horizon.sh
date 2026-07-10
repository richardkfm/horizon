#!/usr/bin/env bash
# horizon curl installer — fetches the horizon source with curl/tar (no git,
# no Docker, no GitHub account required) so packaging/install.sh has
# something to install from.
#
# This script ONLY downloads and extracts a source tarball. It does not
# install anything, does not need root, and does not run any further code —
# so piping it into bash carries the same trust as `git clone` would, no
# more. The actual install step (packaging/install.sh) is separate and
# always run explicitly by you, so there's something concrete to read before
# anything touches your system.
#
# If you'd rather not pipe curl into bash at all, download and read this
# script first, then run it locally:
#   curl -fsSL https://raw.githubusercontent.com/richardkfm/horizon/main/scripts/get-horizon.sh -o get-horizon.sh
#   less get-horizon.sh
#   bash get-horizon.sh
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/richardkfm/horizon/main/scripts/get-horizon.sh | bash
#   curl -fsSL .../get-horizon.sh | HORIZON_REF=v0.7.0 bash
#
# Env vars:
#   HORIZON_REF   branch, tag, or commit to fetch (default: main)
#   HORIZON_DIR   where to extract the source (default: ./horizon)
set -euo pipefail

REPO="richardkfm/horizon"
REF="${HORIZON_REF:-main}"
DEST="${HORIZON_DIR:-$PWD/horizon}"

echo "==> horizon curl installer"
echo "    repo: $REPO@$REF"
echo "    dest: $DEST"

if ! command -v tar >/dev/null 2>&1; then
  echo "error: tar is required" >&2
  exit 1
fi

if command -v curl >/dev/null 2>&1; then
  FETCH="curl -fsSL"
elif command -v wget >/dev/null 2>&1; then
  FETCH="wget -qO-"
else
  echo "error: curl or wget is required" >&2
  exit 1
fi

if [ -e "$DEST" ]; then
  echo "error: $DEST already exists — remove it or set HORIZON_DIR to a new path" >&2
  exit 1
fi

TARBALL_URL="https://github.com/$REPO/archive/$REF.tar.gz"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "==> Downloading $TARBALL_URL"
$FETCH "$TARBALL_URL" > "$TMP/horizon.tar.gz"

echo "==> Extracting to $DEST"
mkdir -p "$DEST"
tar -xzf "$TMP/horizon.tar.gz" -C "$DEST" --strip-components=1

echo "==> Done. Source is at $DEST"
echo ""
echo "Nothing has been installed and nothing ran as root. To finish, read and"
echo "run the installer yourself:"
echo ""
echo "    cd $DEST && sudo ./packaging/install.sh          # venv + systemd service"
echo "    cd $DEST && ./packaging/install.sh --no-service  # venv only, no root needed"
