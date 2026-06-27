# horizon roadmap — towards v0.5

This roadmap builds on the experience horizon offers **today**: a browsable skill
tree of journeys, visual guides with print/PDF, a goal-based recommender, and an
offline local assistant — now with plain-language navigation, "Start here"
journeys, a visible prerequisite chain, a self-describing assistant, guide
search, and a phone-friendly responsive layout.

The question this roadmap answers is the one that matters most for adoption:

> **How does a non-technical neighbour get more out of horizon, and how does an
> admin tailor a node to the specifics of *their* house and *their*
> neighbourhood — without editing files or touching a terminal?**

Everything here holds horizon's non-negotiables: offline-first, no cloud at
runtime, runnable on weak hardware, values live in content, and the core stays
pure and testable. Personalisation is **local and private** (on-device, no
accounts, no telemetry).

Milestones are vertical and shippable: each one is useful on its own, and v0.5
is the point where a neighbourhood can stand up nodes, make them their own, and
share between them.

---

## Where we are — v0.1.x (shipped)

- Skill tree of journeys + guides, prerequisite/"what comes next" chain, and
  "Start here" entry points.
- Visual guides → HTML + high-contrast A4 PDF; print and low-power/e-ink modes.
- Goal-based recommendations and a guide search.
- Offline local AI assistant (RAG over local content), always cited, that
  degrades gracefully and now tells the visitor its live state up front.
- Admin area: content dashboard, content-pack wizard, integrations status, an
  assistant on/off toggle, and a read-only content overview.
- Plain-language UI, accessible tap targets, and a verified responsive layout.

The gap: horizon is **the same on every node**. An admin can't yet make it
reflect their own well, their own solar array, or their own climate without
editing files, and a user can't record what they've already done.

---

## v0.2 — "Know your place" (personal context, no accounts)

Make horizon aware of *this* household and *this* place, and let a user keep
track of where they are — all stored locally in the browser / on the node.

| Feature | How users benefit | How admins benefit |
| --- | --- | --- |
| **House / neighbourhood profile** — admin sets climate, growing zone, water source, power setup, household size, and units (metric/imperial) once. | Pages and the recommender speak in their terms and units; less guesswork. | One place to describe the deployment; the whole node adapts to it. |
| **Profile-aware recommendations** — the profile pre-fills and biases `/recommend` and is passed to the assistant as context. | Better-matched journeys without re-typing their situation every time. | Recommendations and answers fit the neighbourhood out of the box. |
| **Progress tracking (localStorage)** — mark journeys/guides as planned / in-progress / done; "you are here" on the skill tree; resume where you left off. | A clear sense of momentum and what to do next; nothing to log into. | Higher completion; no user database to run or secure. |
| **Skill-tree graph view** — a visual map of journeys and prerequisite edges, building on the chain we already render. | See the whole path at a glance, not one node at a time. | A compelling overview to show neighbours what the node offers. |
| **Units & measurement helpers** — metric/imperial toggle applied across guides and forms. | Numbers in the units they actually use. | Serve mixed-unit neighbourhoods from one content set. |

**v0.2 done when:** a household can describe itself once and see horizon adapt,
and a user can track and resume their journeys — with zero accounts and full
offline privacy.

---

## v0.3 — "Make it yours" (local authoring, the biggest lever)

Today content is files on disk and the admin area is read-only. v0.3 lets a
non-technical admin add and edit content **for their own house and
neighbourhood** from the browser, safely alongside the shipped content.

| Feature | How users benefit | How admins benefit |
| --- | --- | --- |
| **Web guide & journey editor** — create/edit/remove local guides and journeys in the admin UI, with live preview and the same Markdown the shipped guides use. | House-specific how-tos ("Our well", "Where the water shutoff is", "Our inverter") sit right next to the general guides. | Capture local knowledge without Git, YAML, or a terminal. |
| **Local content namespace** — custom content lives in a separate space that **survives re-seed and upgrades** and is never clobbered by shipped updates. | Their local guides don't vanish on the next update. | Upgrade horizon without losing local work. |
| **Notes & overrides on shipped guides** — attach local annotations, photos, and cautions to a bundled guide without forking it. | General guidance plus what's true for *this* place ("our soil is clay", "rainwater only April–Sept"). | Adapt shipped content to local reality without maintaining a fork. |
| **Custom skill-tree wiring** — add local journeys and connect prerequisites/guides in the UI. | Local journeys ("Maintain the community greenhouse") become first-class. | Model the neighbourhood's actual capabilities. |
| **Re-index on save** — content and search/RAG stay consistent after edits, with low-power-aware reindexing. | New local content is searchable and answerable immediately. | No restart, no manual reindex. |

**v0.3 done when:** an admin can stand up a node and make it unmistakably *their
neighbourhood's* — local guides, local journeys, local notes — entirely from the
browser, surviving upgrades.

---

## v0.4 — "Conversations & curation" (deeper assistant, content that improves)

Turn the assistant from a one-shot box into a helper that holds a conversation
and quietly tells admins where their content has gaps.

| Feature | How users benefit | How admins benefit |
| --- | --- | --- |
| **Multi-turn assistant** — follow-up questions with remembered context ("what about for a baby?"), still fully offline and always cited. | Talk to it like they expect to, not one isolated query at a time. | Fewer dead-ends; people get to a usable answer. |
| **"Explain simpler" / answer feedback** — one-tap simpler rewrite and a was-this-helpful signal stored locally. | Control over reading level; a quick way to flag bad answers. | See, on a local dashboard, which questions horizon answers poorly. |
| **Content-gap dashboard** — unanswered/low-confidence questions and missing-citation topics surfaced to the admin. | Indirectly: the guides they need get written. | Know exactly what local content to add next, grounded in real use. |
| **Profile & inventory as context** — household profile and a simple inventory of what's on hand feed answers and recommendations. | Advice that assumes what they actually have. | The node reasons about local resources, not generic ones. |
| **Seasonal / calendar awareness** — planting and maintenance timing tuned to the profile's climate/zone. | "What should I do this month?" answers correctly for their location. | A living, place-aware calendar with no manual upkeep. |

**v0.4 done when:** the assistant sustains a conversation, users can steer and
rate answers, and admins get a concrete, usage-driven list of content to add.

---

## v0.5 — "Neighbours together" (sharing, onboarding, reach)

Make a single tailored node easy to reach, easy to copy, and easy to share
between neighbours — the point of a *neighbourhood* tool.

| Feature | How users benefit | How admins benefit |
| --- | --- | --- |
| **Node-to-node content sharing** — export/import local content as a signed pack over the LAN (or a USB stick); pull a neighbour's "Our well" guide into your node. | Knowledge spreads street to street, still offline. | Seed a new node from an existing one; collaborate without the cloud. |
| **Printable binders** — render a whole journey or a category as a single ordered PDF ("emergency water binder"). | A paper fallback that works with no power at all. | Hand out binders at a neighbourhood meeting. |
| **Easy onboarding** — QR code to the node, guided first-run setup, and optional Wi-Fi access-point mode. | Join by scanning a code; no IP addresses. | Stand a node up and get neighbours on it in minutes. |
| **Internationalisation** — translatable UI strings and multi-language content. | horizon in their language. | Serve multilingual neighbourhoods from one node. |
| **Accessibility & reach pass** — larger-text/high-contrast mode, a tablet breakpoint, keyboard/screen-reader review. | Usable for older neighbours and a range of devices. | One node serves everyone, verified, not assumed. |

**v0.5 done when:** a neighbourhood can run several nodes, each tailored to its
house/street, share local content between them, onboard newcomers with a QR
code, and fall back to printed binders — all offline, on weak hardware.

---

## Principles for every milestone

- **Offline & private by default.** No cloud at runtime; personalisation stays
  on the device. No accounts unless a feature genuinely cannot work without one.
- **Admin-tailorable, neighbour-usable.** If a feature helps an admin fit the
  node to their place, the result must stay simple for a non-technical visitor.
- **Values stay in content.** New guidance and steering live in
  `content/md_skills/`, not business logic.
- **Weak-hardware first.** Every feature must degrade gracefully under low-power
  mode and on a Raspberry Pi.
- **Verify, don't assume.** UI changes are checked at a real phone width before
  they ship (see `CLAUDE.md` → *Verifying UI changes*).

This roadmap is a direction, not a contract — milestones may reorder as we learn
from real neighbourhood deployments.
