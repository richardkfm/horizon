# horizon roadmap

This roadmap builds on the experience horizon offers **today**: a browsable
library of visual guides (with print/PDF) you open straight to, a few curated
step-by-step plans that thread guides together in order, a goal-based
recommender, and an offline local assistant — with plain-language
navigation, a self-describing assistant, guide search, decision guides that
help you *choose*, a richer guide format (comparison tables and callouts), an
admin library that shows the whole node at a glance, a **check & repair**
panel that lets an operator diagnose, repair, and re-seed a node entirely from
the browser (v0.4), printable checklists, guide figures/ASCII diagrams, more
medical and safety guides, an `horizon-content import` command for turning
outside material into local guides (v0.5), the design system applied
consistently everywhere plus an accessibility & responsive pass (v0.6), and —
as of v0.7 — an in-browser **reference library** for downloaded offline
content packs, a solarpunk landing hero, and a broad content expansion across
survival, health, food, and emergencies. horizon is now a cohesive,
comfortable, maintainable node ready to hand to a neighbour.

The focus stays **lean and simple**: deepen the content so it actually helps
you *choose*, and give the admin the few tools they need to keep a node
healthy. No user accounts, no profiles, no tracking — horizon stays an open,
offline library anyone can walk up to.

Everything here holds horizon's non-negotiables: offline-first, no cloud at
runtime, runnable on weak hardware, values live in content, and the core stays
pure and testable.

Milestones are vertical and shippable: each one is useful on its own. What
comes after v0.7 isn't decided yet — see the principles below and expect this
file to grow a new milestone as real neighbourhood deployments surface the
next gap. A granular working list of candidate items (design/UX polish and
missing guide topics) lives in [docs/BACKLOG.md](docs/BACKLOG.md).

---

## Where we are — v0.7.0 (shipped)

- **A reference library for downloaded ZIM content packs.** Previously a
  downloaded pack (offline Wikipedia, WikEM) was a dead end with no way to
  actually read it short of an external Kiwix viewer. `/reference` now lists
  installed packs, each with full-text search and a "Random article" link,
  and renders articles inline — no client-side JS, third-party `<script>`
  tags always stripped server-side.
- **A solarpunk landing hero.** A hand-drawn, gently animated ASCII scene
  (cottage, solar roof, garden, wind turbine) opens the front page, paired
  with new "sun" and "leaf" accent tokens used sparingly across both themes;
  everything flattens to plain ink in low-power, high-contrast, and print
  modes, and the animation is skipped for `prefers-reduced-motion` readers.
- **A broad content expansion** — around twenty new guides across survival
  (map/compass and GPS navigation, campsite setup, sanitation, signaling for
  rescue), health (bites/stings, mass-casualty triage, power-dependent
  medical care, psychological first aid), food (plant-problem diagnosis,
  reforestation), and emergencies (car-free households, vehicle stranding) —
  threaded into two new step-by-step plans and cross-linked from existing
  guides. Guides and checklists also gained a "Read further" footer (next
  guide in a plan, plus a few more on the same topic) so a reader doesn't
  have to detour back through the plan page.
- **Smaller UX fixes**: guides/checklists indexes are now responsive card
  grids instead of a long link list, the home page's topic tiles go
  two-per-row on phones, and the header nav fits on one line at laptop width.
- **Documentation and packaging refreshed** for this tagged release (version
  bump, README status badge, changelog).

The gap we'll close next: the reference library has no built-in map viewer
yet, so the maps content packs are still raw `.osm.pbf` extracts rather than
something you can browse in the UI — that's the natural next step once a
lightweight offline map renderer is chosen.

## Where we are — v0.6.0 (shipped)

- **The design system applied consistently everywhere.** The admin panel
  (dashboard, check & repair, library, content packs, integrations) already
  shared the "paper & ink" tokens and dark/light theming; this release audits
  every page and fixes the handful of layout rules that assumed one line and
  would overflow under a wider setting (see below), rather than adding a new
  visual language.
- **An accessibility & responsive pass.** A "Skip to content" link (first tab
  stop, jumps to `<main>`); labelled navigation landmarks so screen readers can
  tell the main nav, the admin nav, and topic filters apart; a dedicated
  **tablet breakpoint** (641–1024px) that keeps touch-sized tap targets on
  tablets, not just phones; and an on-device **text size / high-contrast**
  setting — independent of theme and of low-power mode, remembered locally,
  reachable from a small panel next to the theme toggle. Verified with
  Playwright at phone/tablet/desktop widths, in both themes, at every
  text-size and contrast combination, with zero horizontal overflow — which
  caught real bugs: several flex rows (guide print/PDF actions, the admin
  dashboard header and nav, the header icon row) only fit on one line at
  normal text size and needed to wrap once the new setting scales the UI up.
- **Documentation and packaging refreshed** for this tagged release (version
  bump, README status badge, changelog).

The gap we'll close next: this pass was a structural/automated review (focus
order, ARIA landmarks, labels, contrast, zero-overflow at every text-size
combination) plus a manual keyboard walkthrough — it has not yet been tested
with real assistive technology (NVDA, JAWS, VoiceOver). That's the next thing
to verify before calling the accessibility work done.

## Where we are — v0.5.0 (shipped)

- **Printable checklists.** A new standalone content type at `/checklists`:
  tick-able, print/e-ink-friendly lists (go-bag, water/food stores, first-aid kit,
  tools, and a mutual-aid "goods to share and barter" list), auto-discovered from
  `content/checklists/` and saved on-device only.
- **Guide figures and ASCII diagrams.** A pure-Markdown figure convention — a
  lone-image paragraph becomes a captioned `<figure>` — with monochrome SVG line
  art that stays crisp in print and e-ink; guide images are now served from the
  content directory. A fenced ` ```ascii ` block plus an italic caption gets the
  same treatment with no image file needed, illustrating ten previously-bare
  guides.
- **More how-to content.** Quick medical-help guides (bleeding, burns, choking/CPR,
  cold and heat injuries, fractures), a "put out a fire safely" guide, and a "make
  your own hand tools" guide, plus a `health-safety` answer-style skill and a new
  `Do now` callout for immediate life-safety actions. A new crafts step-by-step
  plan threads cordage, tool-making, sharpening/repair, and mending together.
- **Importing outside content (`horizon-content import`).** Headless subcommands
  convert a WikiHow how-to page or a local book into regular, offline guides
  written into the operator's content directory (never the git-tracked seed
  bundle), with a source/licence note appended automatically.

## Where we are — v0.4.0 (shipped)

- **A maintainable node — check & repair.** A new **Admin → Check & repair**
  panel (and the headless `horizon-admin check`) gives an operator a
  plain-language health view of the node: broken prerequisite/guide links,
  guides with no file on disk, missing guide images, orphaned or duplicated
  content, whether the search index is present and current, and — opt-in — the
  model runtime. Each problem is listed with the specific offending items.
- **One-click repairs, low-power-aware.** Rebuild the search index and re-seed
  the content metadata from disk straight from the browser, with a clear
  before/after summary; the energy-hungry index build is paused under low-power
  mode rather than hammering a weak supply. Repairs run over HTMX with a live
  result banner and degrade to a plain form post with no JavaScript. The CLI
  gains `horizon-admin seed --force` as the headless re-seed.
- **A recent-events feed.** A small in-memory ring buffer shows what the node
  has been doing (seeding, indexing, repairs, embedding fall-backs) on the
  health page, so an operator can debug without tailing a log file.

## Where we are — v0.3.0 (shipped)

- **Decision guides ("which to pick").** Local content that helps a visitor
  *choose*, not only *do*: which water treatment for which source, how big a
  solar + battery system (with a worked example and sizing table), which crops
  for which season/climate, and which shelter for which situation. Each leads a
  "Start here" decision journey that the matching build journey now builds on, so
  a track reads decide → build.
- **Richer guide format.** Comparison tables (responsive scroll) plus **callouts**
  — labelled blockquotes (`Pick this if` / `Avoid if` / `Spec` / `Decide` /
  `Risk` / `Tip` / `Note`) rendered as scannable boxes that degrade gracefully to
  a bold label everywhere the styling is absent, including print and e-ink.
- **Browse the whole library in admin.** Admin → Library lists and previews every
  guide, journey, and md skill on the node (md skills included, despite having no
  public page) and flags thin content so an operator knows the library at a glance.
- **Values stay in content.** A new `choosing-well` md skill steers the assistant
  to help people decide honestly — situation first, trade-offs visible, safety
  first, criteria not brands.

## Where we are — v0.2.0 (shipped)

- Skill tree of journeys + guides, prerequisite/"what comes next" chain, and
  "Start here" entry points.
- Thirteen built-in skill categories: water, food, energy, shelter, health,
  cooperation, survival basics, culture (music, dance, games), essential
  language, crafts & repair, emergencies (natural disasters — floods,
  earthquakes, drought, wildfire, storms, radiological — plus blackouts, extreme
  heat/cold, air raids, conflict, pandemics), plant-based cooking (vegan), and
  practical calculations (energy sizing, areas/volumes, loads) — each seeded with
  journeys and guides offline.
- Visual guides → HTML + high-contrast A4 PDF; print and low-power/e-ink modes.
- Goal-based recommendations and a guide search.
- Offline local AI assistant (RAG over local content), always cited, that
  degrades gracefully and tells the visitor its live state up front.
- Admin area: content dashboard, content-pack wizard, integrations status, and
  an assistant on/off toggle.
- `horizon-admin` CLI: headless status/doctor/reindex/seed/config and pack
  management, plus reading journeys, guides, recommendations, and assistant
  answers from the terminal. An optional `web.enabled` switch lets a node run
  with the browser UI off, on the API + CLI alone.
- Plain-language UI, accessible tap targets, and a verified responsive layout.
- A cohesive "paper & ink" design system (colour/type/space/radius/shadow
  tokens) with light and dark themes, remembered on-device and defaulting to the
  system setting — print and low-power/e-ink keep their high-contrast palettes.
- A skill-tree view of the plans: journeys grouped into per-topic tracks with
  shared category icons, entry points first, and a "Builds on …" connector that
  surfaces the prerequisite path on each card.
- Brand and mobile polish: a vendored logo mark + favicon, a softer wordmark,
  and a collapsible phone-width header — verified at 375×812 with zero
  horizontal overflow.
- A lean, robust install: `chromadb` is now the optional `ai` extra (the default
  `pip install` and Docker image are small and fast), the wheel ships the web
  assets and locates bundled content across install layouts, static assets are
  cache-busted, and a malformed `config.yaml` no longer crash-loops the node.

The gap we'll close next: the design system isn't yet applied consistently
across every page and the admin panel, and there's no dedicated accessibility &
responsive pass (keyboard/screen-reader review, a tablet breakpoint, a
larger-text/high-contrast option) — the work that turns a maintainable node into
a release a neighbourhood can rely on.

---

## Principles for every milestone

- **Lean and open.** No accounts, no profiles, no telemetry. horizon is a
  walk-up library, not a sign-up product.
- **Offline & frugal.** No cloud at runtime; vendored assets; must degrade
  gracefully under low-power mode and on a Raspberry Pi.
- **Values stay in content.** New guidance lives in `content/md_skills/`, not
  business logic.
- **Verify, don't assume.** UI changes are checked at a real phone width before
  they ship (see `CLAUDE.md` → *Verifying UI changes*).

This roadmap is a direction, not a contract — milestones may reorder as we learn
from real neighbourhood deployments.
