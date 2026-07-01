# CLAUDE.md

Guidance for AI agents and developers working in this repository.

## What horizon is

horizon is an **offline-first "autonomy & rebuilding" node**: a self-contained
server offering a library of visual step-by-step *guides* (the primary unit you
browse and read), a few curated, ordered *step-by-step plans* ("journeys" in the
code) that thread guides together, and a *local AI assistant* (RAG over local
content) for water, food, energy, shelter, health, and cooperative governance.
It targets constrained,
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
- **Metadata store:** SQLite via SQLModel (`db.py`, `models.py`) — guides,
  plans (`Journey`), and the ordered guide-link edges between them.
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
  journeys.yaml     seed step-by-step plans (ordered guide lists)
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

- **Guide (the primary unit):** `content/guides/<id>.md` with front matter
  (`id`, `title`, `category`, `summary`, `difficulty` 1–5, `estimated_time`);
  images under `content/guides/images/`. Auto-discovered by scanning the dir — a
  new file seeds and indexes itself, no plan required. A guide stands on its own —
  it does not need a plan to be browsable or useful.
- **Figure:** write a paragraph containing *only* an image and `services.markdown`
  wraps it in a captioned `<figure>` (alt text = caption). Prefer monochrome
  **SVG** line art so it stays legible on screen, paper, and e-ink; the stylesheet
  sits figures on a light card for contrast in any theme. Images are served at
  `/guides/images` (mounted in `main.py`).
- **Checklist:** `content/checklists/<id>.md` with front matter (`id`, `title`,
  `summary`, optional `category`); body is a Markdown task list (`- [ ] item`)
  rendered as tick-able checkboxes. Auto-discovered like guides; standalone (no
  plan links); tick state is localStorage-only. Backed by the `Checklist`
  model and `seed._load_checklists`.
- **Step-by-step plan ("journey"):** an entry in `content/journeys.yaml` (`id`,
  `title`, `description`, `category`, `difficulty` 1–5, `estimated_time`,
  `guides[]`). `guides` is an **ordered** list — the order *is* the path; there
  are no prerequisites. Only add a plan where guides form a genuine "do this,
  then this" progression; most guides need no plan.
- **md skill:** `content/md_skills/<id>.md` — indexed alongside guides to steer
  the assistant's values and style.
- **Callouts:** start a blockquote with a recognised bold label — `Pick this if` /
  `Avoid if` / `Spec` / `Decision` / `Risk` / `Do now` / `Tip` / `Note` (with
  synonyms; see `services.markdown._CALLOUT_LABELS`). `Do now` is the most urgent,
  for immediate life-safety actions.
- **Importing external content:** `horizon-content import wikihow <url>` /
  `import book <path>` on the CLI, or the **Import content** wizard under
  `/admin/import` in the web UI, convert a how-to page or a book into guide
  Markdown and write it under `<content_dir>/guides` — never into the repo's
  bundled `content/`, since imported text (WikiHow is CC BY-NC-SA; a book may be
  copyrighted) must never get committed into the PolyForm Noncommercial-licensed
  seed bundle.
  The conversion logic in `services/importer.py` stays pure (no network); the
  one seam that fetches a URL, downloads step images, or writes guide files is
  `services/import_content.py`, called by both the CLI (`scripts/content.py`)
  and the admin web route (`web/admin.py`) so they share the same code instead
  of duplicating it — mirroring the pure/impure split in `services/packs.py`.
  The web wizard writes synchronously (unlike the packs wizard's background
  job) since a page-plus-images import is quick, then re-seeds and re-indexes
  immediately so the new guide is live without a restart.

Categories are fixed: `water`, `food`, `energy`, `shelter`, `health`,
`cooperation`, `survival`, `culture`, `language`, `crafts`, `emergencies`,
`cooking`, `calculations` (see `models.Category`). Adding a category is a small code change (the `Category`
enum, plus a `CATEGORY_EXAMPLES` line in `web/routes.py` and an SVG icon in
`landing.html`); routes, API, seeding, and the admin dashboard auto-discover it.
Restart to re-seed and re-index.

## Conventions

- Python ≥ 3.11, full type hints, `from __future__ import annotations`.
- ruff for lint + format (config in `pyproject.toml`).
- Unimplemented scaffold functions raise `NotImplementedError` with a note naming
  the step that fills them in; startup tolerates these.
- Don't add runtime cloud calls. Don't import sibling projects. Don't move value
  judgements out of `content/md_skills/`.
- **Guides are the primary unit; plans are an optional curated layer.** Never
  wrap a single guide in its own plan ("journey") just to give it a node — that
  was the old design and it bought an interstitial click and empty prerequisite
  dead-ends for no benefit. A plan must thread *several* guides into a real
  ordered path. Browsing (home tiles, categories, recommend) points at guides;
  plans are a small, hand-picked set on top.

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
  pointers current; fix in-page anchors if a heading changes. **On every
  release bump, also update the status badge and the "Status:" line to match
  `pyproject.toml`'s `version`** — this has drifted before (stuck at v0.2.0
  through the v0.3 and v0.4 releases).
- **`ROADMAP.md`** — keep the path towards the next milestone (currently v0.5)
  honest; move shipped items into "Where we are" and the changelog.
- When you establish a new standard or learn a durable lesson, write it into this
  file so the next agent inherits it.
- **`config.yaml` is tracked in the repo** (safe, all-disabled defaults) and
  `docker-compose.yml` bind-mounts it **unconditionally**. This used to be
  gitignored with the mount commented out by default, which meant the
  documented "copy config.example.yaml to config.yaml and edit it" step
  silently did nothing — a real-world report ("set admin.token, rebuilt, still
  can't log in") traced back to exactly this. Don't reintroduce that gap:
  keep `config.yaml` tracked and the mount line uncommented, so editing it
  always takes effect after `docker compose up -d --force-recreate`.
- **`init_db()` only creates missing tables (`SQLModel.metadata.create_all`),
  never adds missing columns to an existing table.** A release that adds a
  column to `Guide`/`Journey` (e.g. the v0.3 `difficulty`/`estimated_time`
  move) will crash every page touching that table for anyone upgrading an
  existing `horizon-data` volume in place, with
  `sqlite3.OperationalError: no such column: ...`. There is no migration step
  yet — flag this in review for any model change that adds/renames a column,
  and consider adding a lightweight startup migration (no Alembic needed:
  inspect existing columns and `ALTER TABLE ... ADD COLUMN` for any that are
  missing) before the next schema change ships.
