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

## UX & frontend standards

horizon's primary user is a **non-technical neighbour who just browses the web**.
Hold these when touching templates, copy, or `web/static/`:

1. **Plain language over jargon.** Name things by the task, not horizon's
   taxonomy (nav says *Step-by-step plans* / *How-to guides* / *Where to start* /
   *Ask a question*, not "Journeys/Guides/Recommend/Assistant"). Plain-language
   answers are the default (`ai.no_jargon_default: true`).
2. **Don't expose operator surfaces to visitors.** Admin/operator entry points
   stay out of the public header (a discreet footer link is fine). Public pages
   assume zero technical knowledge.
3. **Set expectations before action, not after.** If a feature can degrade
   (assistant model-off / low-power / disabled), say so *up front* on the page —
   never let the user discover it only after they act. Resolve the live state in
   the route and render it.
4. **Graceful degradation must be visible and friendly.** Mirror the backend's
   fail-open behaviour in the UI with a clear, non-alarming explanation and a
   useful fallback (e.g. point at local guides).
5. **Offline-first frontend.** No external fonts, CDNs, or network assets. Vendor
   JS/CSS locally; use inline SVG for icons. Everything must work with no
   internet and render acceptably in print and low-power/e-ink modes.
6. **Accessible & responsive by default.** No horizontal page overflow at phone
   width; ~44px touch targets on small screens; wide tables scroll inside their
   own box (`.table-scroll` for markup we control; the on-screen scroll is undone
   in `print.css`). Keep `aria-*`/labels on interactive elements.
7. **Personalisation stays local and private.** Prefer on-device state
   (localStorage) and config over accounts or servers; no telemetry.

## Verifying UI changes

"Responsive/working by construction" is not verification — **render it**. The
environment ships Chromium at `/opt/pw-browsers` with Playwright preconfigured
(`pip install playwright`; do **not** run `playwright install`). For a UI change:

- Launch the app (`uvicorn horizon.main:app …`, set `HORIZON_ADMIN_TOKEN` if you
  need the admin views) and drive it with Playwright at a phone viewport
  (e.g. 375×812).
- Assert **zero horizontal page overflow**
  (`document.body.scrollWidth - documentElement.clientWidth <= 0`) on each page,
  and screenshot the key pages to eyeball layout.
- This is how the broken landing CTA (an inline `.btn` splitting across lines,
  plus green-on-green text) was caught — automated overflow checks plus a human
  look at the screenshot. Do both.

## Documentation discipline

Update docs **as part of every user-facing change**, in the same change set:

- **`CHANGELOG.md`** — add entries under `## [Unreleased]` using Keep a Changelog
  sections (Added / Changed / Fixed). Call out anything that affects the
  documented HTTP API contract (e.g. a changed default), even when the response
  shape is unchanged.
- **`README.md`** — keep Features, Configuration, and the Roadmap/changelog
  pointers current; fix in-page anchors if a heading changes.
- **`ROADMAP.md`** — keep the path towards the next milestone (currently v0.5)
  honest; move shipped items into "Where we are" and the changelog.
- When you establish a new standard or learn a durable lesson, write it into this
  file so the next agent inherits it.
