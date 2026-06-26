# horizon
<img width="844" height="676" alt="grafik" src="https://github.com/user-attachments/assets/f61ff046-3a4b-4fec-a99c-004e312b9034" />

**An offline-first autonomy node for basic human skills.**

horizon is a small, self-contained server you run on your own hardware (a
Raspberry Pi, mini-PC, or LXC/VM). It gives a household or neighbourhood a
curated **skill tree** of practical "journeys", **visual step-by-step guides**,
and a **local AI assistant** for water, food, energy, shelter, health, and
cooperative governance — all working **fully offline** after setup, with no
cloud dependency at runtime.

horizon is for autonomy and rebuilding, not just emergencies: living well
off-grid and distributing basic human skills, sustainably and without
coercion.

> **Status:** v0.1 scaffold. The structure, APIs, and content layout are in
> place; feature logic is being filled in step by step (see
> [Roadmap](#roadmap)).

## Features

- **Skill tree ("journeys").** Capabilities modelled as a graph of journeys with
  prerequisite edges (e.g. *water testing → slow sand filtration → storage*).
- **Visual guides + print mode.** Markdown guides with images, rendered to HTML
  for the web and to a minimal, high-contrast **A4 PDF** for printing.
- **Local AI assistant (RAG).** Answers grounded in *your* local guides and
  "md skills", always citing the guides/journeys used — runs against a local
  model, never the cloud.
- **Built-in values.** Sustainability, non-authoritarian cooperation, fairness,
  and anti-exploitation are baked into the assistant via md skills.
- **Simple, stable APIs.** Other projects (e.g. `neighbourgood`) can link to
  journeys/guides without horizon knowing anything about them.

## Quickstart (Docker, recommended)

```bash
git clone https://github.com/richardkfm/horizon && cd horizon

# (optional) customise configuration
cp config.example.yaml config.yaml

docker compose up -d

# Pull a small local model + an embedding model into Ollama (one-time, online):
docker compose exec ollama ollama pull llama3.2:3b
docker compose exec ollama ollama pull nomic-embed-text
```

Then open **http://&lt;host-ip&gt;:8080** from any device on the local network.
On first run horizon seeds its bundled content and builds the search index.

## Bare-metal run

```bash
# System deps for PDF/print mode (Debian/Ubuntu example):
sudo apt install libpango-1.0-0 libpangocairo-1.0-0 libcairo2 \
                 libgdk-pixbuf-2.0-0 libffi-dev shared-mime-info

python -m venv .venv && source .venv/bin/activate
pip install -e .

# A local model runtime must be reachable (see config.yaml `llm.endpoint`):
# install Ollama separately and `ollama pull llama3.2:3b nomic-embed-text`

uvicorn horizon.main:app --host 0.0.0.0 --port 8080
```

horizon also runs on Debian/Arch, Proxmox LXC, Raspberry Pi, and mini-PCs.
Clients connect by browser over the local network; an optional Wi-Fi access
point is documented as a future step.

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

## Configuration

Copy `config.example.yaml` → `config.yaml`. Key settings: `server.port`,
`data_dir`/`database`, `llm.*` (provider, endpoint, models), `vectordb.*`,
`rag.top_k`, `ai.no_jargon_default`, `ethics.*`, `content_packs.dir`.

## Content packs

Larger offline resources (Wikipedia, medical ZIMs, maps) are optional downloads
fetched while online and then used offline:

```bash
horizon-content list
horizon-content download wikipedia
```

A web wizard on the admin page will wrap the same operations.

## Roadmap

v0.1 is being built in vertical slices, with the local model **last** so horizon
is useful before any LLM is involved: data model + seed → Knowledge API → web UI
→ guide rendering + print/PDF → recommendations → RAG + AI assistant → content
packs + admin → optional integrations → packaging.

## License

[AGPL-3.0-or-later](LICENSE).
