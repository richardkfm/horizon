# Installing horizon

Three ways to get a node running, from easiest to most hands-on. Once it's up,
[operating.md](operating.md) covers configuration, the admin token, the CLI,
the optional local AI, and content packs.

horizon runs on Debian/Arch, Proxmox LXC, Raspberry Pi, and mini-PCs. Clients
connect with a browser over the local network.

## Docker (recommended)

```bash
git clone https://github.com/richardkfm/horizon && cd horizon
docker compose up -d
```

Then open **http://&lt;host-ip&gt;:8080** from any device on the local network.
On first run horizon seeds its bundled content and builds the search index.

`config.yaml` ships in the repo with safe defaults and is bind-mounted into the
container, so editing it always takes effect — no copy step needed. After
changing it, apply with `docker compose up -d --force-recreate`.

This default install is small and stays fully offline — **no model runtime is
pulled**. The "Ask a question" assistant falls back to local guide search until
you give it a model. Enabling the optional local AI and finding the admin token
are covered in [operating.md](operating.md).

## No git, no Docker? Use the curl installer

```bash
curl -fsSL https://raw.githubusercontent.com/richardkfm/horizon/main/scripts/get-horizon.sh | bash
cd horizon
```

The script only downloads and extracts a source tarball over HTTPS — no root,
no GitHub account, and it runs nothing else automatically, so it carries the
same trust as `git clone` would. Prefer not to pipe curl into bash at all?
Download it, read it, then run it:

```bash
curl -fsSL https://raw.githubusercontent.com/richardkfm/horizon/main/scripts/get-horizon.sh -o get-horizon.sh
less get-horizon.sh   # read it before running anything
bash get-horizon.sh
cd horizon
```

Either way you now have a local `horizon/` checkout — continue with
[Docker](#docker-recommended) or [Bare-metal](#bare-metal) (skip their
`git clone` step, you already have the source).

## Bare-metal

```bash
git clone https://github.com/richardkfm/horizon && cd horizon   # or the curl installer above
```

```bash
# System deps for PDF/print mode (Debian/Ubuntu example):
sudo apt install libpango-1.0-0 libpangocairo-1.0-0 libcairo2 \
                 libgdk-pixbuf-2.0-0 libffi-dev shared-mime-info

python -m venv .venv && source .venv/bin/activate
pip install -e .                 # lean, offline-first install
# pip install -e .[ai]           # optional: vector search for the AI assistant

uvicorn horizon.main:app --host 0.0.0.0 --port 8080
```

### Run it as a service (systemd)

For an unattended box the installer sets up a service account, virtualenv,
data dir, and systemd unit:

```bash
sudo ./packaging/install.sh
sudo systemctl enable --now horizon
```

## Makefile shortcuts

Common tasks are wrapped in a `Makefile` (`make help`): `make dev`,
`make run`, `make test`, `make lint`, `make build`, `make docker`.
