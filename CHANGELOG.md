# Changelog

All notable changes to horizon are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/).
horizon is pre-1.0, so minor versions may include breaking changes; the
documented HTTP API contract (`/api/journeys`, `/api/guides`, `/api/recommend`,
`/api/ai/answer`) is kept stable.

Updating this changelog and the README is part of every user-facing change
(see `CLAUDE.md` → *Documentation discipline*).

## [Unreleased]

### Added
- **Light & dark themes.** A header theme toggle defaults to the device's
  `prefers-color-scheme` and remembers the choice on-device (a single
  `localStorage` display preference — no account). The page sets the theme
  before paint to avoid a flash. Print and low-power/e-ink keep their fixed
  high-contrast palettes regardless of the chosen theme.
- **Visual redesign — a cohesive "paper & ink" design system.** App styling is
  now driven by design tokens (colour, type, spacing, radius, shadow): a calm
  "horizon" blue accent, a system-serif display face for headings (no external
  fonts — still fully offline), softly shadowed cards, clearer focus rings, and
  restrained hover motion that respects `prefers-reduced-motion`. The recommend
  and assistant forms read as cards. No markup contract changed; every existing
  class name is preserved.
- **Five new built-in content categories** — `survival` (fire, finding water,
  navigation, knots, foraging, trapping & fishing), `culture` (simple
  instruments, group songs, circle dances, no-gear games, storytelling),
  `language` (core phrases, teaching literacy, communicating across barriers),
  `crafts` (cordage, mending textiles, tool repair), and `emergencies` —
  civilian-protection guidance for blackouts, extreme heat and cold, air raids
  and drone attacks, armed conflict, and pandemics. Each ships with seed journeys
  and step-by-step guides, plus md skills steering the assistant on survival
  safety, culture/language inclusion, and emergency safety. They appear on the
  home page, in the journeys/guides browser, the API, recommendations, and the
  admin dashboard — all offline, no download required. `GET
  /api/journeys?category=…` now accepts these five new category values.
- **Expanded food, shelter, and survival content** — more food guides (year-round
  vegetable garden, fruit trees and berries, seed saving), more ways to build a
  home (quick emergency shelter, earth building, timber-frame cabin), and finding
  food in nature (trapping and fishing) added to the existing categories.
- **Two more built-in categories** — `cooking` (plant-based / vegan only: one-pot
  meals, balancing plant proteins, baking bread without modern equipment, and
  preserving by drying/fermenting/pickling) and `calculations` (practical
  numeracy: sizing an energy system, area and volume, estimating material and
  supply quantities, and weights/loads in building). Each ships seed journeys and
  guides plus an md skill (plant-based cooking style; calculation answer safety).
  `GET /api/journeys?category=…` now also accepts `cooking` and `calculations`.
- **Energy production content** — new guides for generating power from a small
  wind turbine, storing and managing power in a battery bank, and heating water
  with the sun, added to the existing `energy` category.
- **`horizon-admin` CLI** — a full headless operator + reader interface for a
  node with no browser. Maintenance: `status` (runtime + content overview with
  an ASCII banner), `doctor` (health-check every optional integration, non-zero
  exit only on a hard failure), `seed`, `reindex`, `config` (effective settings,
  admin token redacted), and `packs list/download/remove`. Content reading:
  `journeys` / `journey <id>` (with an ASCII prerequisite→next flow), `guides` /
  `guide <id>` (Markdown rendered as terminal text, `--raw` for source),
  `recommend <goal>`, and `ask <question>` (cited, offline keyword-fallback
  answer). Most commands take `--json` for scripting.
- **Web UI on/off switch** — new `web.enabled` setting (default `true`,
  overridable at startup via `HORIZON_WEB_ENABLED`). When off, horizon mounts
  only the JSON API and `/healthz` (root returns a short JSON notice) so a
  headless node can be run from the `horizon-admin` CLI alone; the documented
  HTTP API contract is unaffected. Its state shows on **Admin → Integrations**.
- **Journey skill-path navigation.** Entry-point journeys (no prerequisites)
  carry a **Start here** badge in the list and detail header; journey detail
  pages show a prerequisite chain (*Before this → here → Then*) and a *What
  comes next* section built from reverse prerequisite edges.
- **Self-describing assistant.** The assistant page resolves its live state on
  load and tells the visitor up front whether it will give a written answer, is
  paused for low power, is model-off (guides-only), or has been turned off.
- **Operator toggle for the assistant** — new `assistant.enabled` setting
  (default `true`, overridable at runtime via `HORIZON_ASSISTANT_ENABLED`). When
  off, the *Ask a question* link and page are hidden and the answer endpoint
  returns a notice; journeys, guides, and recommendations are unaffected. Its
  state is shown on **Admin → Integrations**.
- **Guide search** — plain substring search over guide title/summary on the
  guides page, composing with the category filter; in-process and fully offline.
- **Category examples & icons** on the home page — each category tile gains a
  vendored inline-SVG icon and a one-line plain-language example.
- **Responsive layout** — a mobile breakpoint and comfortable (~44px) touch
  targets; wide tables scroll within their own box instead of widening the page.
- **Project docs** — this changelog and a `ROADMAP.md` towards v0.5.

### Changed
- **Plain-language navigation.** Header links are now task-oriented (*Where to
  start*, *Step-by-step plans*, *How-to guides*, *Ask a question*); the Admin
  link is removed from the public header and reachable via a discreet *Operator
  login* link in the footer.
- **Plain-language answers by default** — `ai.no_jargon_default` now defaults to
  `true`, reflected in the assistant's checkbox. This also changes the default
  for `POST /api/ai/answer` when a caller omits `no_jargon` (response shape is
  unchanged). Operators can opt out per request or in `config.yaml`.
- **Recommend form** — the do-nothing *People* input is removed from the web
  form (the API still accepts `people` for contract compatibility); optional
  fields are labelled plainly, with example phrasings and a helpful empty state
  that offers topic chips instead of a dead end.

### Fixed
- The home **Describe your goal** call-to-action rendered as broken green blocks
  with invisible text: `.btn` is now `inline-block` so a link-button in flowing
  text stays one rectangle, and `.cta a` no longer paints the button text
  green-on-green. (Affected all viewports.)

## [0.1.0] — 2026-06-26

Initial scaffold built in vertical slices, useful before any LLM is involved.

### Added
- SQLModel data model (journeys, guides, prerequisite/guide-link edges) and seed
  content under `content/` (guides, md skills, `journeys.yaml`).
- Read-only **Knowledge API**: `GET /api/journeys`, `GET /api/journeys/{id}`,
  `GET /api/guides/{id}`, `POST /api/recommend`.
- Server-rendered web UI (Jinja2 + HTMX + Alpine, vendored locally): landing,
  journeys, journey detail, guide viewer, recommend, assistant.
- Guide rendering to HTML and a high-contrast A4 **PDF** (WeasyPrint), with a
  print/low-power stylesheet.
- Pure, LLM-free recommendation logic over seeded metadata.
- **Local AI assistant** (`POST /api/ai/answer`): RAG over guides + md skills
  with keyword fallback, always citing local content, degrading gracefully when
  the model is unavailable.
- Optional **moral-core ethics hook** (`ethics.*`, off by default, fails open).
- **Content packs**: CLI (`horizon-content`) and an admin web wizard with
  background downloads and checksum verification.
- Token-gated **admin** area: content dashboard, content-pack wizard, and
  integrations status.
- **Low-power mode** for solar/battery nodes (`power.low_power` /
  `HORIZON_LOW_POWER`): skips the vector index and pauses the model, with an
  e-ink-friendly stylesheet.
- Packaging: Docker/compose, systemd installer, and a `Makefile`.

[Unreleased]: https://github.com/richardkfm/horizon/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/richardkfm/horizon/releases/tag/v0.1.0
