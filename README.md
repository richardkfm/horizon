<div align="center">

# horizon

<img width="480" alt="horizon" src="https://github.com/user-attachments/assets/f61ff046-3a4b-4fec-a99c-004e312b9034" />

**An offline-first autonomy node for basic human skills.**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-261230.svg)](https://github.com/astral-sh/ruff)
[![Offline-first](https://img.shields.io/badge/offline--first-%E2%9C%93-success.svg)](#)
[![Status: v0.2.0](https://img.shields.io/badge/status-v0.2.0-blue.svg)](#roadmap--changelog)

</div>

horizon is a small, self-contained server you run on your own hardware (a
Raspberry Pi, mini-PC, or LXC/VM). It gives a household or neighbourhood a
curated **skill tree** of practical "journeys", **visual step-by-step guides**,
and a **local AI assistant** across water, food, energy, shelter, health,
cooperative governance, survival basics, culture (music, dance, games),
essential language, crafts & repair, emergencies, plant-based cooking, and
practical calculations — all working **fully offline** after setup, with no
cloud dependency at runtime.

horizon is about everyday autonomy and relearning basic human skills. Most of us are one dead
Wi-Fi signal away from being stuck — a single camping trip is enough to show how
much practical know-how we've quietly outsourced to the internet. horizon puts
those basic human skills back within reach: living well off-grid, sustainably
and without coercion.

> **Status:** v0.2.0. The v0.1 scaffold (data model, APIs, content layout) is
> complete, with a design system, light/dark theming, an expanded content
> library, and a UX layer for non-technical neighbours now on top of it (see
> [Roadmap & changelog](#roadmap--changelog) and [ROADMAP.md](ROADMAP.md)).

**Contents:** [Features](#features) · [Quickstart](#quickstart-docker-recommended) · [Bare-metal](#bare-metal-run) · [Adding content](#adding-guides-journeys--md-skills) · [API](#api-reference) · [Integrations](#optional-integrations) · [Configuration](#configuration) · [CLI](#command-line-horizon-admin) · [Content packs](#content-packs) · [Roadmap & changelog](#roadmap--changelog)

## Features

- **Skill tree ("journeys").** Capabilities modelled as a graph of journeys with
  prerequisite edges (e.g. *water testing → slow sand filtration → storage*).
- **Thirteen skill categories.** Water, food, energy, shelter, health,
  cooperation, survival basics, culture (music, dance, games), essential
  language, crafts & repair, emergencies (natural disasters — floods,
  earthquakes, drought, wildfire, storms, radiological — plus blackouts, extreme
  heat/cold, air raids, conflict, pandemics), plant-based cooking (vegan), and
  practical calculations (energy sizing, areas/volumes, loads) — each with
  built-in journeys and guides, no download required.
- **Visual guides + print mode.** Markdown guides with images, rendered to HTML
  for the web and to a minimal, high-contrast **A4 PDF** for printing.
- **Find your starting point.** Describe a goal in plain words and horizon
  recommends journeys and guides to begin with, matched locally — no internet.
- **Local AI assistant (RAG).** Answers grounded in *your* local guides and
  "md skills", always citing the guides/journeys used — runs against a local
  model, never the cloud. The assistant tells you its live state up front and
  can be turned off by the operator.
- **Made for non-technical neighbours.** Plain-language navigation, "Start here"
  journeys with a visible prerequisite path, guide search, a phone-friendly
  responsive layout, and plain-language answers by default.
- **Comfortable to look at, day or night.** A calm "paper & ink" design with
  light and dark themes (remembered on-device, defaulting to your system
  setting). All styling is vendored — no external fonts or CDNs — and print and
  low-power/e-ink modes keep their high-contrast palettes.
- **Built-in values.** Sustainability, non-authoritarian cooperation, fairness,
  and anti-exploitation are baked into the assistant via md skills.
- **Simple, stable APIs.** Other projects (e.g. `neighbourgood`) can link to
  journeys/guides without horizon knowing anything about them.
- **Full command-line interface.** `horizon-admin` browses plans, guides,
  recommendations, and assistant answers and handles operator upkeep
  (status, health checks, reindex, seed, content packs) — so a headless node can
  run with the web UI switched off (`web.enabled: false`).

## Quickstart (Docker, recommended)

```bash
git clone https://github.com/richardkfm/horizon && cd horizon

# (optional) customise configuration
cp config.example.yaml config.yaml

docker compose up -d
```

Then open **http://&lt;host-ip&gt;:8080** from any device on the local network.
On first run horizon seeds its bundled content and builds the search index.

This default install is small and stays fully offline — **no model runtime is
pulled**. The "Ask a question" assistant falls back to local guide search until
you give it a model. The local AI is entirely optional; enable it whichever way
suits you:

```bash
# A) Point horizon at a model server you already run (e.g. llama.cpp).
#    In config.yaml:
#      llm:
#        provider: openai-compatible
#        endpoint: http://<your-host>:8081/v1
#    No extra container is pulled.

# B) Or run the bundled Ollama container (opt-in `ai` profile; ~3GB image):
docker compose --profile ai up -d
docker compose exec ollama ollama pull llama3.2:3b
docker compose exec ollama ollama pull nomic-embed-text
```

The default image stays lean: it ships **without** the heavy vector-search
stack (chromadb + onnxruntime/tokenizers/…), so it builds fast and the
assistant retrieves with keyword search. To bake in vector search, build with
the `ai` extra: `docker compose build --build-arg INSTALL_EXTRAS=ai` (or
`docker build --build-arg INSTALL_EXTRAS=ai .`).

## Bare-metal run

```bash
# System deps for PDF/print mode (Debian/Ubuntu example):
sudo apt install libpango-1.0-0 libpangocairo-1.0-0 libcairo2 \
                 libgdk-pixbuf-2.0-0 libffi-dev shared-mime-info

python -m venv .venv && source .venv/bin/activate
pip install -e .                 # lean, offline-first install

# Optional: vector search for the AI assistant. This pulls a large dependency
# tree (chromadb + onnxruntime/tokenizers/…); without it, retrieval falls back
# to keyword search and everything still works offline.
# pip install -e .[ai]

# A local model runtime must be reachable (see config.yaml `llm.endpoint`):
# install Ollama separately and `ollama pull llama3.2:3b nomic-embed-text`

uvicorn horizon.main:app --host 0.0.0.0 --port 8080
```

horizon also runs on Debian/Arch, Proxmox LXC, Raspberry Pi, and mini-PCs.
Clients connect by browser over the local network; an optional Wi-Fi access
point is documented as a future step.

### Install as a service (systemd)

For an unattended bare-metal box, the installer sets up a service account, a
virtualenv under `/opt/horizon`, a writable data dir under `/var/lib/horizon`,
and a systemd unit:

```bash
sudo ./packaging/install.sh
sudo systemctl enable --now horizon
journalctl -u horizon -f
```

Common tasks are also wrapped in a `Makefile` (`make help`): `make dev`,
`make run`, `make test`, `make lint`, `make build`, `make docker`.

## Adding guides, journeys & md skills

Content lives under `content/` in the repo (copied into the data directory on
first run):

- **Guides** — `content/guides/<id>.md`, with YAML front matter:

  ```markdown
  ---
  id: water-rainwater-harvesting
  title: Harvest and store rainwater
  category: water
  summary: Collect roof runoff and store it safely.
  ---
  # ...steps, materials, risks, images...
  ```

  Put images in `content/guides/images/`.

- **Journeys** — add an entry to `content/journeys.yaml` with `id`, `title`,
  `description`, `category`, `difficulty`, `estimated_time`, `prerequisites`
  (other journey ids), and `guides` (guide ids).

- **md skills** — `content/md_skills/<id>.md`: values, answer style, and domain
  checklists that steer the assistant. These are indexed alongside guides.

Restart horizon to re-seed and re-index.

## API reference

Read-only **Knowledge API**:

| Method & path | Purpose |
| --- | --- |
| `GET /api/journeys` | List journeys (basic metadata); `?category=` to filter. |
| `GET /api/journeys/{id}` | Full journey: prerequisites + linked guides. |
| `GET /api/guides/{id}` | Guide metadata + rendered HTML (`?format=markdown` for source). |
| `POST /api/recommend` | Suggest journeys/guides for a goal + context. |

`POST /api/recommend` example:

```json
{ "goal": "community_garden", "people": 10, "climate": "temperate" }
```

**AI API**:

| Method & path | Purpose |
| --- | --- |
| `POST /api/ai/answer` | Locally-retrieved, cited answer to a question. |

```json
// request
{ "question": "How do I make river water safe to drink?", "context": {} }
// response
{ "answer": "...", "citations": ["water-slow-sand-filter", "checklist-water-safety"] }
```

Interactive API docs are served at `/docs`.

## Optional integrations

horizon is **fully usable standalone**. Integrations are opt-in and horizon never
hard-depends on them.

- **neighbourgood** (or any app) can call the read-only Knowledge API to link
  tasks/events to horizon's journeys and guides. horizon stores no users or
  social graph.
- **moral-core** ethics hook: set in `config.yaml` (off by default):

  ```yaml
  ethics:
    enabled: true
    endpoint: http://moral-core.local/api/evaluate
  ```

  When enabled, draft answers are sent for approve/adjust/block refinement. If
  moral-core is unreachable or disabled, horizon uses its built-in md skills.

The admin area (**Admin → Integrations**) shows the live status of the local
model runtime, the ethics hook, and installed content packs at a glance.

## Configuration

Copy `config.example.yaml` → `config.yaml`. Key settings: `server.port`,
`data_dir`/`database`, `llm.*` (provider, endpoint, models), `vectordb.*`,
`rag.top_k`, `ai.no_jargon_default` (plain-language answers, default `true`),
`assistant.enabled` (the chat assistant, default `true`), `power.low_power`
(solar/battery mode), `ethics.*`, and `content_packs.dir`.

**Local model runtime (optional).** horizon supports two providers; the assistant
falls back to local guide search until one is reachable:

- **Ollama (default)** — easiest to run and maintain. With Docker, start the
  bundled runtime with the `ai` profile (`docker compose --profile ai up -d`) and
  pull a model. This is the recommended path for most users.
- **llama.cpp / OpenAI-compatible** — if you already run a `llama-server` (or any
  OpenAI-style endpoint), point horizon at it instead of pulling a container:

  ```yaml
  llm:
    provider: openai-compatible
    endpoint: http://192.168.1.10:8081/v1   # your server's OpenAI-compatible base URL
    model: local-model                      # whatever your server serves
    embedding_model: nomic-embed-text        # only if it exposes an embeddings route
  ```

`web.enabled` (default `true`) controls the server-rendered web UI; turn it off
to run a headless node with only the JSON API and the `horizon-admin` CLI.

A few settings also honour environment overrides, so a script can flip them
without editing `config.yaml`: `HORIZON_LOW_POWER`, `HORIZON_ASSISTANT_ENABLED`,
and `HORIZON_ADMIN_TOKEN` are read at request time; `HORIZON_WEB_ENABLED` is read
at startup.

## Command line (`horizon-admin`)

For a node with no browser, `horizon-admin` is a full operator **and** reader
interface — everything runs offline (only `packs download` touches the network):

```bash
horizon-admin status                 # runtime + content overview (with logo)
horizon-admin doctor                 # health-check every optional integration
horizon-admin seed                   # load bundled content into an empty db
horizon-admin reindex                # rebuild the vector index after edits
horizon-admin config                 # effective settings (admin token redacted)

horizon-admin journeys               # browse step-by-step plans
horizon-admin journey <id>           # one plan: prerequisites -> here -> next + guides
horizon-admin guides --search water  # browse / search how-to guides
horizon-admin guide <id>             # read a guide as terminal text (--raw for Markdown)
horizon-admin recommend safe water   # suggest where to start for a goal
horizon-admin ask "how do I store rainwater"   # cited assistant answer (offline fallback)

horizon-admin packs list             # manage offline content packs
```

Most commands accept `--json` for scripting. Run with `web.enabled: false`
(or `HORIZON_WEB_ENABLED=0`) to serve only the JSON API and drive the node
entirely from this CLI.

**Access:** the CLI is not gated by the admin token (that token guards the
network-exposed web admin area). Like `psql` or `systemctl`, it trusts the OS
user — anyone who can run it can already read the database and `config.yaml`
directly. Control access with shell login and file permissions; `horizon-admin
config` redacts the token so it is never printed.

## Content packs

Larger offline resources (Wikipedia, medical ZIMs, maps) are optional downloads
fetched while online and then used offline. The catalog of available packs lives
in `content/packs.yaml` (copied to your data dir on first run, so it is editable
and known offline). Downloads are checksum-verified when the catalog provides a
`sha256`, and stored under `content_packs.dir`.

```bash
horizon-content list                     # available + installed packs
horizon-content download wikipedia-en-mini
horizon-content remove wikipedia-en-mini
```

The same operations are also available under `horizon-admin packs …` and as a
web wizard under **Admin → Content packs**, which downloads in the background and
shows live progress.

## Roadmap & changelog

v0.1 was built in vertical slices, with the local model **last** so horizon is
useful before any LLM is involved: data model + seed → Knowledge API → web UI →
guide rendering + print/PDF → recommendations → RAG + AI assistant → content
packs + admin → optional integrations → packaging. That scaffold is complete,
and a UX layer for non-technical neighbours (plain-language navigation, the
journey skill-path, guide search, and a verified responsive layout) now sits on
top of it.

The design pass (a cohesive "paper & ink" system with **dark/light theming**)
has shipped. The path from here stays lean and open (no accounts, no profiles,
no tracking): a deeper "what to pick" content library, and the admin tools to
keep a node healthy (a check & repair diagnostics feed, and re-seeding from the
panel) — see **[ROADMAP.md](ROADMAP.md)** for the plan towards v0.5.

Notable changes are recorded in **[CHANGELOG.md](CHANGELOG.md)**.

## License

[AGPL-3.0-or-later](LICENSE).
