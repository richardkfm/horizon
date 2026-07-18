# Backlog — design/UX polish & missing guides

A prioritized working list for what comes after v0.7: first the design/UX
rough edges still standing, then the guide topics the library is missing.
[ROADMAP.md](../ROADMAP.md) stays the high-level milestone story; this file
holds the granular items to pick from.

Ground rules for executing anything here (they're the repo's existing rules,
restated so nobody re-derives them):

- UX items follow `CLAUDE.md` → *UX & frontend standards* and are verified
  per *Verifying UI changes*: Playwright at a phone viewport (375×812),
  zero horizontal overflow asserted, screenshots eyeballed.
- Content items follow `CLAUDE.md` → *Content principles* and *Adding
  content*; every new guide keeps
  `tests/test_web_ui.py::test_every_category_has_a_seeded_guide` green and
  gets a `CHANGELOG.md` entry.
- Out of scope for everything below: new JS frameworks, CDN/network assets,
  accounts or telemetry-based personalisation (localStorage only).

---

## Part 1 — Design & UX

### P0 — parity gaps (newest features visibly behind the rest)

- [ ] **Bring the reference library up to the card treatment.**
  `reference_index.html` and `reference_pack.html` still render plain
  `<ul class="link-list">` while guides/journeys/checklists moved to the
  responsive `.card-grid` in v0.7. Reuse the existing card markup/classes
  from `guides.html` / `checklists.html` — no new CSS system.
- [ ] **Same pass for the maps index.** `maps_index.html` lists packs as a
  bare link list; the viewer itself (`maps_pack.html`) shipped, but its
  front door didn't get the v0.7 "card grids instead of link lists" fix.

### P1 — interaction feedback & accessibility

- [ ] **Consistent htmx loading states.** Only `assistant.html` and the
  admin partials (`admin/_health_body.html`, `admin/_pack_row.html`) use
  `hx-indicator`/`hx-disabled-elt` today. Audit every other htmx
  interaction (guide search first) and give each a visible pending state —
  on weak hardware a slow request with no feedback reads as broken.
- [ ] **Explicit empty states everywhere.** `.empty` treatment exists in
  `guides.html` and `journey_detail.html` (and minimal copy in
  reference/maps); add a friendly "nothing here yet" state to
  `checklists.html`, `recommend.html`, and the assistant's
  `partials/_answer.html` instead of default blankness.
- [ ] **Extend page-level ARIA to reference & maps.** `base.html` provides
  the shell landmarks, but the newest pages (`reference_*.html`,
  `maps_*.html`) carry no `aria-*` of their own. Apply the established
  pattern: labelled landmarks, `aria-live` on regions htmx swaps.
- [ ] **One real assistive-technology pass.** The v0.6 accessibility work
  was structural/automated plus a keyboard walkthrough; ROADMAP.md itself
  flags that NVDA/JAWS/VoiceOver testing hasn't happened. Walk the core
  flow (home → guide → plan → assistant) with a real screen reader and
  file what it finds as new items here.

### P2 — polish, once P0/P1 land

- [ ] **Verify the retrofitted grids on a phone.** Touch-target size and
  overflow at 375×812 on the new reference/maps card grids — matching CSS
  classes is not verification.
- [ ] **"Part of a plan" breadcrumb on guide pages.** A reader landing on a
  guide from search/recommend can't see it belongs to a step-by-step plan;
  surface a small "part of *Off-grid power*" link on the guide detail page.
- [ ] **Keep low-power-critical widgets on plain JS.** The nav/theme/a11y
  toggles in `base.html` are deliberately plain JS (not Alpine) so they
  work in low-power mode. Hold that line for new widgets, and leave a
  comment saying so where it applies, so nobody "helpfully" converts them.

---

## Part 2 — Missing guides

Current shape of the library: 94 guides across 15 categories. Thinnest:
language (3), mobility (3), calculations (4), cooking (4). No journey or
checklist covers `language` yet.

Editorial decisions already made (don't relitigate):

- Keeping animals for **eggs, milk, and wool is in scope**, framed strictly
  around non-lethal use with an explicit "Note" callout that horizon
  doesn't cover slaughter. Working/draft animals for transport: same basis.
- **Leatherworking is out**, even from reclaimed hide — too close to the
  animal-product line the project stays clear of.
- As ever: nothing that requires killing an animal, no weapons/war prep,
  clean energy over combustion wherever a clean option can do the job.

### language (highest priority — thinnest, no journey, no checklist)

- [ ] *Learn essential numbers, measurements, and quantities* — practical
  vocabulary distinct from the existing phrases guide.
- [ ] *Communicate without a shared language: sign, gesture, and
  pictograms* — includes basic sign/deaf-inclusive communication.
- [ ] *Document and preserve a local or minority language* — pairs with
  culture's storytelling/preservation guide.
- [ ] Once the category reaches ~5–6 guides, add a
  `language-and-communication` journey (the one category without one).

### mobility

- [ ] *Move people and goods with a working animal* — harnessing, care,
  load limits; non-lethal working use only, never food.
- [ ] *Move by water: rafts and small boats* for communities near water.

### calculations

- [ ] *Track a household or co-op's stores and inventory* — simple
  bookkeeping; pairs with the `share-and-barter` checklist.
- [ ] *Calculate water flow, consumption, and storage needs* — water is a
  headline category with no rate math anywhere.
- [ ] *Work out a fair trade or barter value* — bridges calculations and
  cooperation's resource-sharing content.

### cooking

- [ ] *Cook with a solar oven* — no solar cooking guide exists anywhere;
  strongest clean-energy fit. Cross-link from energy.
- [ ] *Cook with foraged and wild food* — pairs with survival's wild-food
  identification guide.
- [ ] *Ferment beyond pickles: vinegar and lacto-ferments* — deepens the
  existing drying/fermenting/pickling guide.

### water

- [ ] *Reuse greywater around the home* — distinct from survival's
  waste/hygiene guide; real-sustainability angle.
- [ ] *Conserve and ration water day to day* — the ordinary-times version
  of what only the drought emergency guide touches today.

### energy (clean-energy angle throughout)

- [ ] *Build a small biogas digester* — organic waste to cooking fuel;
  renewable, directly displaces combustion generators.
- [ ] *Use human and pedal power* — treadle tools, bike generators; the
  cheap low-tech complement to solar/wind.
- [ ] Solar-oven build detail can live here if the cooking guide above
  stays usage-focused — decide when writing, don't duplicate.

### food

- [ ] *Keep poultry for eggs* — no-kill framing with explicit Note callout.
- [ ] *Keep a dairy animal* — same framing.
- [ ] *Keep bees and support pollinators.*
- [ ] *Root-cellar and cold-store food* — distinct from seed-saving and
  from cooking's preservation guide.
- [ ] *Compost kitchen and garden waste* — deepens the soil-restoration
  guide.

### shelter

- [ ] *Retrofit and weatherize an existing home* — every current shelter
  guide assumes new-build; most readers have an existing structure.
- [ ] *Basic water and sanitation plumbing for a shelter.*
- [ ] *Pest- and rodent-proof a home or store.*

### crafts

- [ ] *Make soap and candles.*
- [ ] *Basic pottery* and *woodworking joinery* (likely two guides).
- [ ] *Natural-fibre textile crafts* — felting/weaving/knitting with plant
  fibre and wool from kept animals; no hide or leather work.

### cooperation

- [ ] *Onboard new members and plan succession* for a group or co-op.
- [ ] *Share child-rearing and elder-care as a group commons* — extends
  resource-sharing into care work.

### culture

- [ ] *Make art with natural pigments* — the visual-craft/morale
  counterpart to the music/dance/games guides.
- [ ] *Run a children's play and learning curriculum* — complements
  language's literacy guide and culture's storytelling.

### Checklists to add

Eight categories have no checklist today. Most list-shaped first:

- [ ] **shelter** — a build/retrofit checklist.
- [ ] **survival** — a wilderness kit, distinct from the emergencies go-bag.
- [ ] **technology** — mesh/radio setup checklist.
- Lower priority (more guide-shaped than list-shaped): culture, language,
  cooking, calculations, mobility — add only if a natural task list falls
  out of a specific guide above.
