# horizon roadmap — towards v0.5

This roadmap builds on the experience horizon offers **today**: a browsable skill
tree of journeys, visual guides with print/PDF, a goal-based recommender, and an
offline local assistant — now with plain-language navigation, "Start here"
journeys, a visible prerequisite chain, a self-describing assistant, guide
search, a phone-friendly responsive layout, decision guides that help you
*choose*, a richer guide format (comparison tables and callouts), an admin
library that shows the whole node at a glance, and — new in v0.4 — a
**check & repair** panel that lets an operator diagnose, repair, and re-seed a
node entirely from the browser.

The focus from here is **lean and simple**: make horizon look and feel great,
deepen the content so it actually helps you *choose*, and give the admin the few
tools they need to keep a node healthy. No user accounts, no profiles, no
tracking — horizon stays an open, offline library anyone can walk up to.

Everything here holds horizon's non-negotiables: offline-first, no cloud at
runtime, runnable on weak hardware, values live in content, and the core stays
pure and testable.

Milestones are vertical and shippable: each one is useful on its own, and v0.5
is a polished, well-maintained node a neighbourhood can rely on.

---

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

## v0.5 — Polish & release

Pull it together into a release a neighbourhood can rely on.

- The design system applied consistently across every page and the admin panel,
  dark/light included.
- An accessibility & responsive pass (keyboard/screen-reader review, tablet
  breakpoint, larger-text/high-contrast option alongside the low-power palette).
- Documentation and packaging refreshed for a tagged release.

**v0.5 done when:** horizon is cohesive end to end, comfortable on any device and
in any light, maintainable from the panel, and ready to hand to a neighbour.

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
