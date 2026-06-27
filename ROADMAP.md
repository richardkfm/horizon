# horizon roadmap — towards v0.5

This roadmap builds on the experience horizon offers **today**: a browsable skill
tree of journeys, visual guides with print/PDF, a goal-based recommender, and an
offline local assistant — now with plain-language navigation, "Start here"
journeys, a visible prerequisite chain, a self-describing assistant, guide
search, and a phone-friendly responsive layout.

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

## Where we are — v0.1.x (shipped)

- Skill tree of journeys + guides, prerequisite/"what comes next" chain, and
  "Start here" entry points.
- Visual guides → HTML + high-contrast A4 PDF; print and low-power/e-ink modes.
- Goal-based recommendations and a guide search.
- Offline local AI assistant (RAG over local content), always cited, that
  degrades gracefully and tells the visitor its live state up front.
- Admin area: content dashboard, content-pack wizard, integrations status, and
  an assistant on/off toggle.
- Plain-language UI, accessible tap targets, and a verified responsive layout.
- A cohesive "paper & ink" design system (colour/type/space/radius/shadow
  tokens) with light and dark themes, remembered on-device and defaulting to the
  system setting — print and low-power/e-ink keep their high-contrast palettes.

The gaps we'll close next: the design system still needs the nicer skill-tree
visuals and a consistent pass over the admin panel; the content tells you *how*
but not always *which to pick*; and an admin can't yet diagnose or repair a node
without a terminal.

---

## v0.2 — Look & feel (make it cool, make it comfortable)

A focused design pass so horizon is a pleasure to use and easy on the eyes —
without adding weight or breaking offline/low-power/print.

- **Dark mode & light mode.** *(Shipped.)* A theme toggle that defaults to the
  device's `prefers-color-scheme` and remembers the choice on-device (a single
  display preference in `localStorage` — not an account). Built on CSS custom
  properties; print and low-power/e-ink keep their high-contrast palettes.
  *Users:* read comfortably day or night. *Admins:* nothing to configure.
- **Visual redesign.** *(Largely shipped.)* A cohesive design system — colour
  tokens, typography, spacing, cards, and iconography — applied across the
  pages. Still to do: nicer journey/skill-tree visuals that build on the
  prerequisite chain we already render. *Users:* the node feels trustworthy and
  modern.
- **Usability polish.** Consistent components, clear focus/hover states,
  restrained motion, and a tidy mobile layout. *Users:* obvious what to tap and
  where they are.
- **Still offline & frugal.** No external fonts/CDNs; everything vendored; must
  render acceptably in print and on weak/e-ink hardware.

**v0.2 done when:** horizon looks polished, switches cleanly between dark and
light, and still prints and runs on a Raspberry Pi without regressions —
verified at a real phone width.

---

## v0.3 — A deeper "what to pick" library

Today's guides tell you *how*. This milestone deepens the content so it also
helps you *decide* — the part people most often get wrong off-grid.

- **Decision guides.** "Which to choose" reference material: selection criteria,
  trade-offs, and worked examples (e.g. *which water filter for which source*,
  *how big a solar + battery setup*, *which crops for which season*).
- **Richer guide format.** Support comparison tables, decision steps, and spec
  callouts in guides — rendering responsively (the wide-table scroll already
  works) and in print/PDF. *Users:* fewer dead-ends and costly wrong choices.
- **Browse the full library in admin.** A complete, previewable view of every
  guide, journey, and md skill on the node, so an admin can see what's there and
  what's thin. *Admins:* know the library at a glance.
- **Values stay in content.** Any new steering lives in `content/md_skills/`,
  not in business logic.

**v0.3 done when:** a visitor can answer "which one should I pick?" from local
content alone, and an admin can see the whole library from the panel.

---

## v0.4 — A maintainable node (admin tooling)

Give the operator the handful of tools they need to keep a node healthy —
without SSH, restarts, or guesswork.

- **Check & repair feed (diagnostics).** A health view that surfaces real
  problems: broken prerequisite/guide links, missing guide images, content not
  in the search/RAG index, an unreachable model runtime, orphaned or duplicate
  content, and a readable recent-events/log feed for debugging. *Admins:* see
  what's wrong, in plain language, in one place.
- **One-click repair.** Fix what the checks find: rebuild the search/vector
  index, refresh links, clear caches — low-power-aware so it won't hammer a weak
  supply. *Admins:* resolve issues from the browser.
- **Re-seed from the panel.** Re-seed bundled content and re-index on demand
  (today this needs a restart), with a clear before/after summary. *Admins:*
  recover or refresh a node safely without the command line.

**v0.4 done when:** an admin can diagnose, repair, and re-seed a node entirely
from the admin panel, and the feed tells them honestly whether the node is
healthy.

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
