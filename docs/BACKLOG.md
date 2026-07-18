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

- [x] **Bring the reference library up to the card treatment.**
  `reference_index.html` and `reference_pack.html` still render plain
  `<ul class="link-list">` while guides/journeys/checklists moved to the
  responsive `.card-grid` in v0.7. Reuse the existing card markup/classes
  from `guides.html` / `checklists.html` — no new CSS system.
- [x] **Same pass for the maps index.** `maps_index.html` lists packs as a
  bare link list; the viewer itself (`maps_pack.html`) shipped, but its
  front door didn't get the v0.7 "card grids instead of link lists" fix.

### P1 — interaction feedback & accessibility

- [x] **Consistent htmx loading states.** *(Audited: the app has exactly
  three htmx surfaces — the assistant form (`hx-indicator`), the admin
  repair forms (`hx-disabled-elt`), and the admin pack rows. Guide search
  is a plain GET form, not htmx. The one real gap was the pack rows'
  Remove/Download buttons, which now disable themselves while the request
  is in flight.)*
- [x] **Explicit empty states everywhere.** *(Audited: this was stale —
  `checklists.html` ("No checklists yet"), `recommend.html` (the
  no-match suggestions box), and `partials/_answer.html` ("No local
  guides matched this question") all already have explicit empty states,
  as do guides, journeys, reference, and maps. Nothing to add.)*
- [x] **Extend page-level ARIA to reference & maps.** *(The pack search
  form already had `role="search"` + hidden labels. Added: a visible
  results-count heading and `aria-label` on the search-results grid in
  `reference_pack.html`, and `role="region"` on the map viewer so its
  existing `aria-label` actually creates a landmark. The pages are
  full-page-load, not htmx swaps, so no `aria-live` is needed.)*
- [ ] **One real assistive-technology pass.** The v0.6 accessibility work
  was structural/automated plus a keyboard walkthrough; ROADMAP.md itself
  flags that NVDA/JAWS/VoiceOver testing hasn't happened. Walk the core
  flow (home → guide → plan → assistant) with a real screen reader and
  file what it finds as new items here.

### P2 — polish, once P0/P1 land

- [x] **Verify the retrofitted grids on a phone.** Touch-target size and
  overflow at 375×812 on the new reference/maps card grids — matching CSS
  classes is not verification. *(Done alongside the P0 work: Playwright at
  375×812 and 1280×800 with fixture packs, zero overflow, screenshots
  eyeballed; cards are full-width padded tap targets.)*
- [x] **"Part of a plan" breadcrumb on guide pages.** *(Audited: stale —
  `guide.html` already renders a "Part of this plan:" box above the
  article (`.guide-tracks`, fed by `in_tracks` in the route) plus "Next
  in {plan}" links in the Read-further footer. Nothing to add.)*
- [x] **Keep low-power-critical widgets on plain JS.** *(Audited: stale —
  `base.html` already carries "Plain JS so it works in low-power mode"
  comments on every such script (theme boot, nav toggle, a11y panel).
  The convention holds; nothing to add.)*

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

- [x] *Learn essential numbers, measurements, and quantities* — practical
  vocabulary distinct from the existing phrases guide.
  *(`language-numbers-and-measures`)*
- [x] *Communicate without a shared language: sign, gesture, and
  pictograms* — includes basic sign/deaf-inclusive communication.
  *(`language-signs-and-pictograms`, angled toward deaf inclusion, group
  hand signals, and posted pictograms so it doesn't duplicate
  `language-across-barriers`.)*
- [x] *Document and preserve a local or minority language* — pairs with
  culture's storytelling/preservation guide.
  *(`language-preserve-a-language`)*
- [x] Once the category reaches ~5–6 guides, add a
  `language-and-communication` journey (the one category without one).
  *(Added at 6 guides, threading all of them in order.)*

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
