# CLAUDE.md

Guidance for AI agents and developers working in this repository.

## What horizon is

horizon is an **offline-first "autonomy & rebuilding" node**: a self-contained
server offering a skill tree of practical *journeys*, visual step-by-step
*guides*, and a *local AI assistant* (RAG over local content) for water, food,
energy, shelter, health, and cooperative governance. It targets constrained,
self-hosted hardware (Raspberry Pi, mini-PC, Proxmox LXC, Debian/Arch) and must
be useful out of the box, fully offline.

## Non-negotiable principles

Hold these when making any change:

1. **Offline-first.** No cloud or external network dependency at runtime. Network
   is used only during setup and optional content-pack downloads. The app must
   import, boot, and serve the UI with **no external services running**; Ollama
   and Chroma are only exercised by the AI assistant path.
2. **No hard dependency on sibling projects.** `neighbourgood` and `moral-core`
   are *optional consumers/refiners*, never imports. The `moral-core` ethics hook
   is opt-in (`ethics.enabled`, default `false`) and must **fail open** to
   horizon's built-in md skills if disabled or unreachable.
3. **Values are content, not code.** Sustainability, non-authoritarian
   cooperation, fairness, and anti-exploitation live in `content/md_skills/` and
   the AI system prompt. Don't bury value judgements in business logic.
4. **Built for weak hardware.** Prefer simple, low-resource designs. Keep it
   runnable bare-metal, not only in Docker.
5. **Keep core logic pure.** The Knowledge API and recommendation logic must work
   and be unit-testable **without** the LLM/vector DB. Isolate external systems
   in `src/horizon/services/`.

## Architecture

- **Web framework:** FastAPI + Uvicorn (`src/horizon/main.py`).
- **UI:** server-rendered Jinja2 + HTMX + Alpine.js (vendored locally, no build
  step), with a print/low-power friendly stylesheet (`web/static/print.css`).
- **Metadata store:** SQLite via SQLModel (`db.py`, `models.py`) — journeys,
  guides, prerequisite/guide-link edges.
- **Content:** Markdown guides + md skills on disk under `content/` (seeded into
  `settings.content_dir` on first run).
- **Vector index:** embedded Chroma over guides + md skills (`services/rag.py`).
- **LLM:** Ollama by default (generation + embeddings), or a llama.cpp
  OpenAI-compatible endpoint (`services/llm.py`).
- **PDF/print:** WeasyPrint (`services/pdf.py`).
- **Startup lifespan** (`main.py`): `init_db()` → `seed_if_empty()` →
  `reindex_content()`. Steps not yet implemented are skipped gracefully.

## Directory map

```
content/            seed content shipped in the repo
  guides/           Markdown guides (+ images/)
  md_skills/        values, answer-style, domain checklists
  journeys.yaml     seed skill-tree nodes + edges
src/horizon/
  main.py           FastAPI app: routers, static, lifespan
  config.py         typed settings loaded from config.yaml
  db.py, models.py  SQLModel engine + Journey/Guide models
  seed.py           load bundled content into SQLite
  api/              Knowledge API (journeys, guides, recommend) + AI API
  services/         markdown, pdf, rag, llm, recommend, ethics (external deps)
  web/              routes.py + templates/ + static/
  scripts/          horizon-content CLI (content packs)
tests/              pytest
config.example.yaml docker-compose.yml  Dockerfile  pyproject.toml
```

## Dev commands

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]

uvicorn horizon.main:app --reload    # run locally
pytest                               # tests
ruff check . && ruff format .        # lint / format
docker compose config                # validate compose
docker compose up                    # full stack (app + ollama)
```

## API contract (keep stable)

These are horizon's integration surface; preserve backward compatibility:

- `GET /api/journeys`, `GET /api/journeys/{id}`
- `GET /api/guides/{id}`
- `POST /api/recommend` — `{goal, people?, climate?, resources?}`
- `POST /api/ai/answer` — `{question, context?}` → `{answer, citations[]}`

`citations` are guide/journey ids. Always cite local content in AI answers.

## Adding content

- **Guide:** `content/guides/<id>.md` with front matter (`id`, `title`,
  `category`, `summary`); images under `content/guides/images/`.
- **Journey:** an entry in `content/journeys.yaml` (`id`, `title`, `description`,
  `category`, `difficulty` 1–5, `estimated_time`, `prerequisites[]`, `guides[]`).
- **md skill:** `content/md_skills/<id>.md` — indexed alongside guides to steer
  the assistant's values and style.

Categories are fixed: `water`, `food`, `energy`, `shelter`, `health`,
`cooperation` (see `models.Category`). Restart to re-seed and re-index.

## Conventions

- Python ≥ 3.11, full type hints, `from __future__ import annotations`.
- ruff for lint + format (config in `pyproject.toml`).
- Unimplemented scaffold functions raise `NotImplementedError` with a note naming
  the step that fills them in; startup tolerates these.
- Don't add runtime cloud calls. Don't import sibling projects. Don't move value
  judgements out of `content/md_skills/`.
