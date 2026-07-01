#!/usr/bin/env bash
# Bare-metal installer for horizon (Debian/Ubuntu/Arch, Raspberry Pi, LXC).
#
# Creates an unprivileged service account, a virtualenv under PREFIX, a writable
# data directory, and (optionally) a systemd service. horizon runs fully offline
# afterwards; a local model runtime (e.g. Ollama) is optional and configured
# separately in config.yaml.
#
# Usage:
#   sudo ./packaging/install.sh              # install to /opt/horizon, set up systemd
#   sudo PREFIX=/srv/horizon ./packaging/install.sh
#   ./packaging/install.sh --no-service      # venv only, no systemd (e.g. for dev)
set -euo pipefail

PREFIX="${PREFIX:-/opt/horizon}"
DATA_DIR="${DATA_DIR:-/var/lib/horizon}"
SERVICE_USER="${SERVICE_USER:-horizon}"
WANT_SERVICE=1
[ "${1:-}" = "--no-service" ] && WANT_SERVICE=0

SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> horizon installer"
echo "    source:  $SRC_DIR"
echo "    prefix:  $PREFIX"
echo "    data:    $DATA_DIR"

# --- prerequisites ---------------------------------------------------------
if ! command -v python3 >/dev/null 2>&1; then
  echo "error: python3 is required" >&2
  exit 1
fi
PYVER="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
case "$PYVER" in
  3.1[1-9]|3.[2-9][0-9]) : ;;
  *) echo "error: Python >= 3.11 required (found $PYVER)" >&2; exit 1 ;;
esac

echo "==> Note: PDF/print mode needs system libraries (WeasyPrint):"
echo "    Debian/Ubuntu: apt install libpango-1.0-0 libpangocairo-1.0-0 libcairo2 \\"
echo "                   libgdk-pixbuf-2.0-0 libffi-dev shared-mime-info"
echo "    Arch:          pacman -S pango cairo gdk-pixbuf2 libffi"

# --- service account -------------------------------------------------------
if [ "$WANT_SERVICE" -eq 1 ] && ! id "$SERVICE_USER" >/dev/null 2>&1; then
  echo "==> Creating service user '$SERVICE_USER'"
  useradd --system --home "$DATA_DIR" --shell /usr/sbin/nologin "$SERVICE_USER" || \
    useradd --system --home-dir "$DATA_DIR" --shell /bin/false "$SERVICE_USER"
fi

# --- copy source + build venv ---------------------------------------------
echo "==> Installing source into $PREFIX"
mkdir -p "$PREFIX"
if [ "$SRC_DIR" != "$PREFIX" ]; then
  cp -a "$SRC_DIR/." "$PREFIX/"
fi

echo "==> Creating virtualenv and installing horizon"
python3 -m venv "$PREFIX/.venv"
"$PREFIX/.venv/bin/pip" install --upgrade pip >/dev/null
"$PREFIX/.venv/bin/pip" install "$PREFIX"

# --- config + data ---------------------------------------------------------
if [ ! -f "$PREFIX/config.yaml" ]; then
  echo "==> Writing config.yaml (data_dir -> $DATA_DIR)"
  sed -e "s#^data_dir:.*#data_dir: $DATA_DIR#" \
      -e "s#^database:.*#database: $DATA_DIR/horizon.db#" \
      -e "s#^content_dir:.*#content_dir: $DATA_DIR/content#" \
      "$PREFIX/config.example.yaml" > "$PREFIX/config.yaml"
  # content_packs.dir is nested; rewrite its value too.
  sed -i "s#^\(\s*dir:\)\s*/data/packs#\1 $DATA_DIR/packs#" "$PREFIX/config.yaml"
fi

mkdir -p "$DATA_DIR"
if [ "$WANT_SERVICE" -eq 1 ]; then
  chown -R "$SERVICE_USER:$SERVICE_USER" "$DATA_DIR" "$PREFIX"
fi

# --- systemd service -------------------------------------------------------
if [ "$WANT_SERVICE" -eq 1 ] && command -v systemctl >/dev/null 2>&1; then
  echo "==> Installing systemd service"
  install -m 0644 "$PREFIX/packaging/horizon.service" /etc/systemd/system/horizon.service
  systemctl daemon-reload
  echo "    Enable with: sudo systemctl enable --now horizon"
else
  echo "==> Skipping systemd setup"
  echo "    Run manually: $PREFIX/.venv/bin/uvicorn horizon.main:app --host 0.0.0.0 --port 8080"
fi

echo "==> Done. horizon is installed."
echo "    The admin area is on by default: if you don't set admin.token in"
echo "    config.yaml (or HORIZON_ADMIN_TOKEN), a random token is generated on"
echo "    first run and saved to <data_dir>/admin_token. Open http://<host-ip>:8080"
