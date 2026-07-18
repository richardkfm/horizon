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
- **A `curl`-based installer (`scripts/get-horizon.sh`) for boxes without
  `git` or Docker.** User feedback: some operators hit a wall installing
  horizon because their box has neither a `git` client nor Docker (and no
  GitHub account to set either up). The script does exactly one thing —
  download and extract a source tarball over HTTPS — and needs no root and
  runs nothing else on its own, so `curl ... | bash` carries the same trust
  as `git clone` would; the actual install step (`packaging/install.sh`,
  unchanged) is still a separate command you run and can read first. The
  original `git clone` + Docker/bare-metal paths are untouched, just
  reordered: the README's [Quickstart](README.md#quickstart) now leads with
  the curl installer, followed by [Docker](README.md#docker-recommended) and
  [bare-metal](README.md#bare-metal).
- **A built-in map viewer (`/maps`), closing the "download a map, find no
  viewer" dead end.** A `maps-*` content pack downloads raw OpenStreetMap
  `.osm.pbf` source data — useful, but not something a browser can render,
  and rendering it into tiles is a CPU/RAM-heavy batch job that doesn't fit
  weak/Pi-class hardware. Rather than render on the node, horizon reads an
  `.mbtiles` file (vector tiles) that the operator renders **once, off the
  node**, with [Planetiler](https://github.com/onthegomap/planetiler) — a
  single self-contained jar, no PostGIS/Mapnik install — and drops into the
  installed pack's own directory (`docs/operating.md` has the exact
  command). `.mbtiles` is just SQLite, so serving it (`services/mbtiles.py`)
  is a raw blob read; the map itself renders client-side with the newly
  vendored MapLibre GL JS, using a deliberately minimal style (roads, water,
  buildings, land cover — no text labels yet, so no glyph/sprite server is
  needed). The **Maps** nav item and an **Admin → Content packs** "View map"
  link only appear once a pack actually has a rendered basemap; until then
  the pack row explains the one-time rendering step instead of just sitting
  there installed and inert.

### Changed
- **Reference library and Maps index pages now use the same responsive card
  grid as guides/journeys/checklists.** The two newest features were still
  plain link lists (the pre-v0.7 pattern): `/reference` and `/maps` pack
  listings and the in-pack article search results on `/reference/{pack}` now
  render as `.card-grid` cards, and all three pages use the wider browsing
  shell. Map pack cards also show the pack's catalog description; an
  installed pack missing from the catalog shows no description on the public
  page instead of leaking the operator-facing "not in the current catalog"
  note (`pack_status()` rows gained an `in_catalog` flag for this — additive,
  no HTTP API impact). Verified at phone (375×812) and laptop widths with
  zero horizontal overflow.
- **Visual refresh — the solarpunk hero scene, glowing ASCII diagrams, and a
  wider browsing shell.** Three UI-only changes (no HTTP API or content-format
  impact):
  - The landing page's ASCII scene is now a full 60-column solarpunk morning —
    a cottage with a solar-panel roof, a sunflower, garden beds, a sapling, and
    a wind turbine, with a breathing sun, drifting birds, a spinning rotor, and
    a butterfly in the animated sky layer (still two stacked `<pre>` layers on
    one monospace grid; still plain text, still animated only outside
    low-power/reduced-motion, with the complete still scene as frame 0). In
    the dark theme the scene glows softly, like a village at dusk.
  - ASCII diagrams in guides (` ```ascii ` figures) now have a proper drawing
    surface instead of a fixed white card that glared in dark mode: an
    engineer's graph-paper notebook in the light theme (faint leaf-green grid
    drawn with CSS gradients, warm paper, soft ink) and an amber terminal at
    dusk in the dark theme (deep surface, glowing amber ink, faint scanlines).
    Driven entirely by new `--diagram-*` theme tokens, so high-contrast,
    low-power/e-ink, and print all still flatten diagrams to plain ink on
    paper, and captions now read as a small monospace figure label.
  - Browsing pages (home, guides, step-by-step plans, checklists) use a wider
    content shell that matches the header's width, so the hero and card grids
    fill a desktop screen instead of leaving dead gutters; reading pages keep
    the narrower measure that suits running text.

### Fixed
- **`docker compose build` tagged the image `horizon:0.5.0` regardless of the
  actual release.** `docker-compose.yml`'s `image:` pin had drifted two
  releases behind `pyproject.toml`'s version (last bumped for the v0.5.0
  release, never updated since), so `docker compose up` printed a stale
  version in its build output even on current `main`. Bumped the pin to
  `horizon:0.7.0` to match.

### Added
- **`horizon-admin menu`: an arrow-key-navigable interactive menu.** Running
  `horizon-admin` with no subcommand (or `horizon-admin menu` explicitly) now
  opens a menu covering every existing subcommand — browse plans/guides,
  recommend, ask the assistant, manage content packs, status/doctor/check,
  seed/reindex, config — driven with the arrow keys or `j`/`k` and `Enter`, so
  an operator doesn't need to already know the subcommand names. Built on the
  standard library's `curses` (no new dependency); falls back to a plain
  numbered `input()` prompt on a non-interactive terminal or where `curses`
  isn't available. New module: `horizon.scripts.menu`. The main-menu screen
  now also draws the `horizon-admin` ASCII banner (logo) as part of itself —
  in both the `curses` picker and the plain fallback — rather than printing it
  once before handing off to `curses`, where it could be wiped by the
  alternate-screen switch. On a terminal too short to fit the banner and the
  full option list, the banner is dropped so the menu itself never clips.

### Fixed
- **`horizon-admin`'s ASCII "HORIZON" wordmark rendered as a garbled mess on
  some terminals** (reported on Windows Terminal/PowerShell). The block-letter
  glyph rows in `admin._LOGO` had drifted to inconsistent widths (42/43/44/42/42
  characters) so the underscores/pipes/slashes that form each letter didn't
  actually line up in the same columns from row to row — on a strict monospace
  font this read as merely off, but on fonts/terminal themes with any glow,
  bloom, or ligature rendering it collapsed into noise. Replaced it with a
  verified, column-aligned render of the same wordmark (every glyph row is the
  same width) and added a regression test
  (`test_banner_wordmark_glyph_columns_are_aligned`).
- **`crafts-make-tools` still carried the pre-ASCII-convention test image.**
  The "make your own hand tools" guide was the original demo of the SVG figure
  convention; when the ASCII diagram convention shipped afterwards and was
  rolled out to ten other guides, this guide — the one that started it — was
  never converted, leaving a leftover `hafted-tool.svg`. Replaced it with an
  ASCII diagram matching the guide's existing one, and removed the now-unused
  SVG file. `CLAUDE.md` and `docs/authoring-content.md` previously didn't say
  ASCII is the default over an image; both now do, so this shouldn't happen
  again.
- **`horizon-admin guide` didn't render ASCII diagrams cleanly.** The CLI's
  Markdown-to-terminal-text pass left ` ```ascii ` fence markers and the
  literal `*caption*` asterisks in the output, so diagrams read as raw
  Markdown noise instead of the plain-text art they're meant to be.
  `_markdown_to_text` now strips the fence and unwraps the caption.
- **Uneven home-page category tiles.** The `technology`, `emergencies`, and
  `cooking` tile blurbs wrapped to one line more than every other category,
  making those cards visibly taller and breaking the grid's row alignment.
  Shortened all three (`CATEGORY_EXAMPLES` in `web/routes.py`) so every
  category tile wraps to the same two lines.
- **"More on `<category>`" read-further heading looked like guide content.**
  It reused the same h2 styling as in-guide section headings, sat with almost
  no gap above it, and gave a reader no visual cue that everything below was
  extra reading rather than more of the guide. It's now a small muted
  eyebrow-style label (`.read-further-more h2` in `app.css`) with more
  breathing room above it.

### Added
- **New `mobility` category**, with three guides — keep a bicycle running
  with basic maintenance and repairs, move heavy loads without a car
  (wheelbarrows, handcarts, bike trailers, and load technique), and build a
  cargo bike trailer (a buildable relative of the bakfiets that hitches to
  any bike) — threaded together in a new "Get around and haul loads without a
  car" step-by-step plan. Adds a new `Category` enum value, home-page tile,
  and nav icon.
- **Two more `technology` guides**: repair small electronics and solder
  (the general multimeter/soldering skill behind most technology repairs),
  and build a resilient mesh network (going beyond the local-network
  guide's overview into genuine multi-hop, self-healing mesh — Bluetooth
  mesh messaging on phones already owned, LoRa nodes placed for redundant
  paths, and open mesh routing firmware for Wi-Fi). The "Set up local tech
  infrastructure" plan now threads all six `technology` guides together.
- **A new `technology` category** (horizon's fourteenth) covering local
  radio, networking, and computing — a gap no existing category fit
  cleanly, and one that's deeply on-brand for a self-hosted, offline-first
  project. Ships with four guides (set up two-way radio for your community,
  build a local network without the internet, turn an old PC into a local
  server, maintain and repair computers), a `technology-safety` md skill
  (keeping radio/network content community-coordination framed rather than
  tactical, and legally aware), a dedicated category icon, and a
  step-by-step plan, "Set up local tech infrastructure".
- **Three new `cooperation` guides** — resolve conflict between people fairly,
  share resources and manage a group's commons, and build trust and
  agreements with neighbouring groups — filling out horizon's thinnest guide
  category (previously 2 guides) and giving it its first step-by-step plan,
  "Set up cooperative governance from scratch".
- **A `cooperation-consensus` md skill**, encoding the "consensus is the
  foundation" content principle for the assistant, matching the per-category
  skill pattern used by `emergencies`/`health`/`survival`/etc.
- **Two new `water` guides** — harvest and store rainwater, and find, dig, or
  protect a well or spring — closing a sourcing gap in a category that
  previously only covered testing, treating, and filtering. Threaded into the
  existing "Provide safe drinking water for a group" plan ahead of testing
  and treatment.
- **A new `crafts` guide**, spin fibre and weave simple cloth, covering
  fibre preparation, drop-spindle spinning, and basic weaving — distinct from
  the existing cordage guide's coarser rope-making technique. Threaded into
  the "Make and maintain your own tools" plan.
- **A new step-by-step plan for `emergencies`**, "Prepare for and get through
  a long blackout", threading blackout, extreme heat, extreme cold, fire
  safety, and no-car-household guides — the category's largest guide count
  (15) previously had zero curated plans.

### Fixed
- The `cooperation` category had no dedicated icon in the shared
  `category_icon` macro and silently fell back to the generic icon; it now
  has its own.

### Removed
- **Retired the `survival-trapping-fishing` guide** ("Catch fish and small
  game for food"). It taught snares, deadfalls, and killing/gutting catch for
  food, which conflicts with CLAUDE.md's "no killing of animals" content
  principle. Removed its reference from the "Core wilderness survival
  skills" plan and an incidental mention in the cordage guide.

## [0.7.0] — 2026-07-09

### Added
- **"Read further" footer on guides and checklists.** A guide that's a step
  in a plan now ends with a "Next in `<plan>`" link straight to the following
  guide (in the leaf-accent style introduced with the solarpunk hero), so a
  reader partway through a step-by-step plan doesn't have to detour back
  through the plan page to continue. Every guide — in a plan or not — also
  gets a small "More on `<category>`" list of a few other guides on the same
  topic; checklists get the same "more on" list keyed off their own category,
  since checklists stay standalone and have no plan to link onward to.
- **A solarpunk landing hero with a hand-drawn ASCII scene.** The front page
  opens with a two-layer ASCII vignette — a cottage with solar-panel roof, a
  garden, and a wind turbine in leaf-green ink, with the sun, turbine rotor,
  and two birds gently animating in amber on top. The animation is plain JS
  with no new dependencies, is skipped entirely in low-power mode and for
  `prefers-reduced-motion` readers (who get the complete still scene), and
  the scene is described to screen readers via a `role="img"` label.
- **Solarpunk accent tokens** (`--sun`, `--leaf` + soft tints) in both themes:
  a sunrise gradient hairline across the top of every page, a sun-to-leaf
  flourish under the landing section heading, a warm sun-glow/leaf-tint wash
  and asymmetric "leaf" corners on the hero card, and a leaf-green hover on
  the topic tiles. All decorative colour flattens to plain ink in low-power,
  high-contrast, and print modes.
- **Two new survival guides covering map and GPS use**, filling a gap where
  the only existing navigation guide was explicitly "without a compass or
  map": *Navigate with a map and compass* (`survival-map-and-compass`
  — orienting a map, taking and following a bearing, finding your position by
  resection) and *Use offline maps and GPS with no signal*
  (`survival-offline-maps-and-gps` — a phone's GPS receiver works from
  satellites alone with no signal, but only if the map area was downloaded
  beforehand; also covers printing a paper backup). Cross-linked with the
  existing "find direction without a compass" and "get through emergencies
  with no car" guides. The go-bag checklist gained a "printed local map and a
  compass" item to match.
- **New guide for car-free households facing emergencies**
  (`emergency-no-car-household`): evacuating on foot when transit may fail,
  storing supplies in a small apartment footprint instead of a car trunk or
  garage, and the specific risks of a heatwave or blackout with no vehicle to
  drive to a cooling centre — including checking on isolated neighbours.
  Cross-linked from "survive extreme heat without power" and "prepare for and
  live through a long blackout".
- **Eight new guides covering camping and disaster-response gaps, threaded
  into two step-by-step plans.** For camping/fieldcraft (survival category):
  "Choose and set up a safe campsite" (`survival-campsite-setup`, site
  selection, camp layout, wildlife-safe food storage), "Manage waste and
  hygiene without plumbing" (`survival-sanitation-hygiene`, latrines,
  greywater, handwashing), and "Signal for rescue if lost or stranded"
  (`survival-signaling-for-rescue`, ground signals, fire/smoke, mirror
  flashes). For health: "Treat bites, stings, and wildlife encounters"
  (`health-bites-stings-wildlife`), "Triage multiple casualties at once"
  (`health-mass-casualty-triage`), "Keep essential medical care going without
  power" (`health-power-dependent-care`, insulin/oxygen/dialysis/mobility
  during a blackout), and "Support someone through shock, trauma, or grief"
  (`health-psychological-first-aid`). And for emergencies: "Survive being
  stranded in a vehicle" (`emergency-vehicle-stranded`). The three new
  survival guides are added to the existing "Core wilderness survival
  skills" plan (before fire/water and after foraging/trapping respectively),
  and a new "Respond when several people are hurt at once" plan threads
  first-aid basics through triage, bleeding/fracture treatment, and
  psychological first aid. All eight are cross-linked from related existing
  guides (water field-testing, foraging, navigation, blackout, extreme cold,
  flood, first-aid basics).
- **Two new food guides closing gaps in plant identification and land
  management:** "Diagnose crop problems — deficiency, disease, pest, or
  invasive" (`food-diagnose-plant-problems`) teaches reading the pattern of a
  struggling plant to tell nutrient deficiency, disease, pest damage, and
  invasive spreaders apart; "Reforest and restore woodland"
  (`food-reforestation`) covers assisted natural regeneration vs. planting,
  mixed native species selection, and long-term woodland management at a
  scale beyond a single windbreak hedge. Both are cross-linked from the
  existing crop-choosing and soil/land-restoration guides, and the
  diagnosis guide is added to the "Grow and store your own food" plan.
- **Reference library: an in-browser reader for downloaded ZIM content packs**
  (offline Wikipedia, WikEM). Previously a downloaded pack was a dead end —
  there was no way to actually read it short of pointing an external Kiwix
  viewer at the file. `/reference` now lists installed ZIM packs; each has a
  landing page with full-text search (using the ZIM's own built-in index) and
  a "Random article" link, and articles render inline with in-article links
  and images rewritten to stay under `/reference/<pack_id>/...` — no
  client-side JS, and `<script>` tags from third-party content are always
  stripped server-side (`services/zim_reader.py`). A "Reference library" nav
  item appears only once at least one ZIM pack is installed. Adds `libzim` as
  a new dependency (small prebuilt wheels, including aarch64/Raspberry Pi, no
  system library required).

### Changed
- **`docs/operating.md` explains where to actually run `horizon-admin`.** The
  CLI section jumped straight into usage examples, silently assuming the
  reader already had `horizon-admin` on `PATH` — a real report was someone
  `cd`'d into the repo on a VPS and typing `horizon-admin` got "command not
  found", because it's a `pip`-installed console script, not a file in the
  repo. Added a "Getting the command to run" subsection covering all three
  install paths: `docker compose exec horizon horizon-admin …` for the
  Quickstart Docker path, activating `.venv` for a bare-metal install, and the
  full binary path under `/opt/horizon/venv/` for the systemd installer.
- **Slimmed the README and split its reference material into `docs/`.** The
  README had grown to cover the full API, content authoring, configuration, the
  CLI, and content packs inline. Those sections now live in dedicated files —
  [`docs/api.md`](docs/api.md) (HTTP API reference + optional integrations),
  [`docs/authoring-content.md`](docs/authoring-content.md) (guides, checklists,
  plans, md skills, importing), and [`docs/operating.md`](docs/operating.md)
  (configuration, local model runtime, `horizon-admin`, content packs) — leaving
  the README an overview (features, quickstart, bare-metal, a brief config
  summary) that links out to them. No documented behaviour or API changed; this
  is a docs reorganisation only.
- **Map content packs now offer a per-country option, not just whole
  continents.** The previous fix for broken map-pack URLs replaced a single
  ~1.1 GB pre-tiled world pack with 8 raw `.osm.pbf` continent extracts from
  Geofabrik — which fixed the dead links but made the *smallest* map download
  jump to several GB, and the four biggest (Africa, Asia, Europe, North
  America) run 7-34 GB each, since no free, no-account, pre-tiled provider
  exists to replace the old one. Those four continents now also list one pack
  per country/territory (still Geofabrik, one directory level down its own
  hierarchy — e.g. Germany at 4.5 GB instead of all of Europe's 31+ GB, or
  Luxembourg under 50 MB), verified live against Geofabrik's current file
  sizes. The whole-continent packs are kept, retitled to flag their size, for
  anyone who wants full continental coverage. `content/packs.yaml` documents
  how to add any other Geofabrik sub-region (state/city-level) to an
  operator's own copy of the catalog. Since the maps category is now ~155 entries, the
  admin **Content packs** page gained a client-side filter box.
- **Guides and Checklists indexes are now responsive card grids.** The old
  single-column link list made ~90 guides a very long, hard-to-scan page on a
  laptop; each entry is now a tappable card (category badge, title, summary)
  in a multi-column grid that stacks back to one column on phones.
- **The home page's topic tiles go two-per-row on phones** with compact
  padding — thirteen full-width tiles previously made the front page a very
  long scroll on a small screen.
- **The header navigation fits on one line at laptop width.** Nav links are
  slightly condensed, the header bar may run a little wider than the reading
  column, and the explicit "Home" item only shows in the collapsed phone
  menu — on wide screens the brand itself is the way home. Previously the
  last nav item ("Ask a question") wrapped onto its own second row.

- **License changed from AGPL-3.0-or-later to PolyForm Noncommercial
  1.0.0.** horizon is now source-available rather than open source: the code
  remains free to use, modify, and self-host for any noncommercial purpose
  (personal, educational, charitable, research, and government use), but
  commercial use requires a separate agreement with the copyright holder.
  Updated `LICENSE`, `pyproject.toml`, the README badge/license section, and
  the site footer accordingly.
- **The admin area is now on by default.** Previously a blank `admin.token`
  disabled it entirely; now, when neither `admin.token` nor
  `HORIZON_ADMIN_TOKEN` is set, horizon generates a random token on first run,
  persists it to `<data_dir>/admin_token`, and logs it once at startup so an
  operator can log in without editing `config.yaml`. Setting `admin.token` (or
  the env var) still works exactly as before and takes precedence.

### Added
- **Proper per-guide licence attribution for imported content, now that
  horizon's own licence is noncommercial-only.** `horizon-content import
  wikihow` now attributes WikiHow's own CC BY-NC-SA 3.0 licence by default
  (`services/importer.py`'s `render_wikihow_guide`/`_source_note`) instead of
  a generic "check the licence" caution — the resulting guide is marked as
  licensed under those original terms, distinct from the rest of the
  repository's own licence, satisfying CC BY-NC-SA's ShareAlike clause. This
  makes it possible to bundle imported WikiHow content into the repo's own
  seed content (`--dest content/guides`) where that wasn't safe before.
  `horizon-content import book` gained matching `--license-name`/
  `--license-url` flags for books with a verified compatible licence (public
  domain, CC-BY, etc.); see `CLAUDE.md` for the policy on when bundling
  imported content into `content/` is appropriate.
- **Two new guides:** *Restore worn-out land and rebuild soil*
  (`food-soil-and-land-restoration`) covering cover crops, swales, windbreaks,
  and other low-tech land-regeneration techniques, and *Set up fair,
  accountable governance for a group* (`cooperation-democratic-governance`)
  covering rotating/recallable roles, power-splitting, and federation for
  groups that outgrow whole-group consensus. The land-restoration guide is now
  the first step in the "Grow and store your own food" plan.
- **"Import content" wizard in the admin web UI** (`/admin/import`), so an
  operator can turn a WikiHow-shaped how-to page or an uploaded book file
  (.txt/.md) into guide(s) without a terminal — previously only available via
  the `horizon-content import wikihow`/`import book` CLI. Both now share the
  same fetch/write logic (`services/import_content.py`); the web wizard
  re-seeds and rebuilds the search index immediately after writing, so the new
  guide is live with no restart.
- **10 more ASCII diagrams across guides** (cordage twisting, square lashing,
  timber-frame cabin cross-section, battery series/parallel wiring, a wind
  turbine on its guyed mast, splinting, a succession garden bed layout,
  earthquake Drop-Cover-Hold-On, an earth-wall cross-section, direct pressure
  for bleeding, and fire-hardening a digging stick) — the same
  `` ```ascii `` + caption convention already used elsewhere.

### Changed
- **Landing page heading no longer repeats "horizon".** The header already
  shows the wordmark, so the intro `<h1>` now reads "Guides for everyday
  autonomy" instead of duplicating the brand name directly beneath it.
- **Footer spacing fixed.** `.footer-links` (GitHub / Operator login) had no
  layout rules at all, so the two links ran together with no gap and wrapped
  awkwardly on narrow screens; the footer row also had no extra padding
  separating it from the page above. Added a flex-wrap gap for the links and
  more breathing room around the footer row.
- **Landing page CTA spacing.** The "Describe your goal" button sat right
  under its question with almost no gap when wrapped to its own line; added
  margin above the button and below the whole `.cta` paragraph.
- **`<h2>` section headings now have top margin.** They previously had none,
  so a second section heading straight after another block (e.g. "Step-by-step
  plans that fit" right under the "Guides to read" list on `/recommend`) had
  no visual separation at all. `h2` now carries the same top spacing used
  elsewhere for section breaks.

### Fixed
- **Reference library articles no longer leak their pack's own CSS onto the
  whole page.** A ZIM entry is usually a complete HTML document; embedding it
  whole nested `<html>/<head>/<body>` inside horizon's page, and the browser
  hoisted the head's `<link rel="stylesheet">` tags, so a pack's MediaWiki
  skin restyled horizon's entire chrome and broke the dark theme on article
  pages. `rewrite_article_html` now keeps only the `<body>` content, and
  `.zim-article` gained native typography (wiki-style section rules, bordered
  tables, a muted per-article licence footer) — reference articles now follow
  horizon's light/dark/low-power themes correctly.
- **Content pack downloads were all broken.** `content/packs.yaml` pointed at
  stale URLs: Kiwix now embeds a build date in ZIM filenames and deletes older
  dates (`wikipedia_en_100_mini.zim` / `wikem_en_all_maxi.zim` both 404'd), and
  the maps pack's `data.maptiler.com` URL is gone now that MapTiler requires an
  account/API key for downloads. Repointed the Wikipedia and WikEM packs at
  their current dated Kiwix filenames (documented the date-rot caveat in
  `packs.yaml` for next time), and replaced the single broken world-map pack
  with per-continent OpenStreetMap extracts from Geofabrik (`maps-europe`,
  `maps-africa`, `maps-asia`, `maps-north-america`, `maps-south-america`,
  `maps-central-america`, `maps-australia-oceania`, `maps-antarctica`) — a
  free, no-account source, so an operator only downloads the region(s) they
  need. These are raw `.osm.pbf` OpenStreetMap extracts rather than
  pre-rendered tiles, since horizon has no built-in map viewer yet and no
  no-account pre-tiled basemap provider split by continent could be found.
- **`packs.yaml` was never kept in sync on already-provisioned installs**, so
  the URL fix above wouldn't reach any node that had already started once.
  `_ensure_content_dir()` (`seed.py`) used to `shutil.copytree` the whole
  bundled `content/` dir on first run, including `packs.yaml`; a later
  refactor to per-file syncing (so upgrades pick up new/changed guides,
  checklists, and plans) carried over `journeys.yaml` but dropped
  `packs.yaml` from the synced list, silently freezing an operator's pack
  catalog at whatever it was on first boot. `packs.yaml` is now synced the
  same way as `journeys.yaml`.
- **Admin dashboard/library/etc. pages showed a blank version in the
  footer** ("AGPL-3.0 · v" with nothing after it) because `web/admin.py` builds
  its own `Jinja2Templates` instance and never registered the `version`
  Jinja global that `web/routes.py` sets on its own instance. Registered it on
  the admin templates too.
- **Upgraded installs (e.g. a long-lived Docker volume) now pick up new
  seed content automatically instead of staying stuck at whatever was there
  the first time they were seeded.** Previously, seeding only ever ran once —
  a node that had already been seeded before checklists existed kept 0
  checklists forever, a step-by-step plan that used to be single-guide
  (before plans required at least two) stayed a single-guide dead end, and a
  later release's improvements to an existing guide (e.g. an added ASCII
  diagram) never reached content_dir, because guide/checklist files were only
  copied in if missing. Startup now syncs on every boot: new guides,
  checklists, and plans are added; a plan's guide order is refreshed from
  `journeys.yaml`; and each bundled file is individually brought up to date
  with the shipped version *unless the operator has edited it since horizon
  last wrote it* (tracked via a small per-file hash manifest in content_dir,
  so a file with no tracking history — the common case on the very first sync
  after upgrading to this fix — is refreshed in the same pass rather than
  needing a second restart). A plan that
  resolves to fewer than two guides is dropped rather than kept as a
  single-guide dead end, and `/journeys`, `/api/journeys`, and `/api/recommend`
  now also filter thin plans defensively as a backstop, so a stale database can
  never surface one even before its next sync. `services.diagnostics` reports
  the checklist count and flags any plan with fewer than two guides.

## [0.6.0] — 2026-07-01

### Added
- **Accessibility pass.** A "Skip to content" link (first tab stop, jumps
  keyboard users past the header to `<main>`); labelled `<nav>` landmarks
  (main navigation, admin navigation, category/topic filters) so screen
  readers can tell them apart; and an on-device **text size / high-contrast**
  display setting — a small panel off a new header button, independent of
  theme and of low-power mode, remembered locally (`localStorage`, no
  account). Text size scales the whole rem-based UI (Normal / A+ / A++);
  high contrast flattens muted greys and soft accent fills to full-strength
  ink and hard borders on top of whichever theme is active.
- **A tablet breakpoint.** A dedicated `641–1024px` media query keeps
  touch-sized (~44px) tap targets on tablets, not just phones, alongside the
  existing phone breakpoint.

### Changed
- **Design-system consistency audit.** Several flex rows that assumed a
  single line (the guide print/PDF actions, the admin dashboard header and
  nav, the header icon row) now wrap instead of overflowing the page once
  the new text-size setting scales the UI up — caught by re-running the
  phone/tablet/desktop overflow check from `CLAUDE.md` at every text-size and
  contrast combination, in both themes, across the public site and the admin
  panel.

## [0.5.0] — 2026-07-01

### Added
- **Import external content as guides (`horizon-content import`).** Two new
  headless subcommands turn outside material into regular guides:
  `horizon-content import wikihow <url>` fetches an "intro + numbered steps"
  how-to page and converts it to guide Markdown (steps, bold step leads, and
  step images downloaded locally so the guide still renders fully offline);
  `horizon-content import book <path>` splits a local text/Markdown book into
  one guide per detected chapter and defaults to category `culture`. WikiHow
  spans every topic, so `wikihow` has no default — `--category` is required
  there. Both write into `<content_dir>/guides` so they never touch the
  git-tracked seed content, and append a "Note" callout recording the source and
  a reminder to check its licence before redistributing. `--reseed` reloads the
  database immediately; otherwise the usual `horizon-admin seed --force` +
  `reindex` picks the new guide(s) up. The conversion logic
  (`horizon.services.importer`) is pure and network-free, unit-tested without
  any HTTP fetch.
- **New step-by-step plan: "Make and maintain your own tools."** Threads the
  four crafts guides into an ordered path — cordage, making hand tools,
  sharpening/repair, and mending textiles.
- **Two new checklists.** "Home emergency preparedness" (stocking the home
  itself, distinct from the go-bag, for blackouts, storms, floods, and a
  medical emergency) and "Off-grid power build" (tools, parts, and safety
  gear to pair with the off-grid-power plan).
- **Checklists (`/checklists`).** A new printable content type — a self-contained,
  tick-able list of things to gather, pack, or do. Ships a starter set: a go-bag,
  water store, food store, first-aid kit, tools and materials, and a
  cooperation-flavoured "goods to share and barter" list (framed as mutual aid, not
  profiteering). Checklists are auto-discovered from `content/checklists/*.md`
  (drop in a file to publish one), reachable from the header nav and the landing
  page, and print/e-ink friendly. Ticked items are saved **on the device only**
  (localStorage — no account, server, or telemetry) and degrade gracefully where
  JavaScript is off.
- **Guide figures.** A pure-Markdown figure convention: a paragraph containing only
  an image is rendered as a `<figure>` with the image's alt text as a visible
  caption. Line-drawing SVGs sit on a light card so they stay legible in any theme
  and in print/e-ink. Guide illustrations under `content/guides/images/` are now
  served (at `/guides/images`). Demonstrated on the new "make your own hand tools"
  guide.
- **New how-to guides.** Quick medical-help guides — *stop severe bleeding*,
  *treat burns and scalds*, *help someone choking or not breathing*, *treat
  hypothermia and frostbite*, *treat heat exhaustion and heat stroke*, *splint
  fractures and sprains* — plus *put out a fire safely* and *make your own hand
  tools*. A `health-safety` answer-style skill steers the assistant to treat these
  as first aid and defer to professional care.
- **"Do now" callout.** A new callout kind (`> **Do now:** …`) for immediate,
  life-safety actions, rendered with the most urgent styling and used by the
  medical and fire guides.
- **ASCII diagram convention.** A pure-Markdown alternative to image figures: a
  fenced ` ```ascii ` code block followed by an `*italic caption*` renders as the
  same captioned `<figure>` card as an image, but needs no image file and reads
  correctly as-is in a CLI, `cat`, or any plain Markdown viewer — and degrades to
  print without losing any meaning. Added monospace line-art diagrams to ten
  guides that had no illustration: the slow sand filter cross-section, the
  low-tech solar wiring order, where a shelter loses heat, a water-safety
  decision tree, a 500 m² staple-crop plot layout, the first-aid priority order,
  teepee and lean-to fire lays, a fish funnel trap, the shadow-stick navigation
  method, and the area/volume formula shapes. Six of these guides previously
  carried a "diagrams will be added" placeholder note, now removed.

### Fixed
- README status badge and the "Status:" line still said v0.2.0 after the
  v0.4.0 release; bumped to match `pyproject.toml`.
- `docker-compose.yml` pinned the `horizon` image to the stale `0.2.0` tag;
  bumped to `0.4.0`.
- **`config.yaml` is now tracked in the repo (with safe, all-disabled
  defaults) and bind-mounted unconditionally in `docker-compose.yml`.**
  Previously it was gitignored and the mount was commented out by default, so
  an operator following the documented "copy config.example.yaml to
  config.yaml and edit it" step would see no effect — the container only ever
  read the bundled `config.example.yaml`, regardless of `docker compose up
  --build`. New installs now work out of the box (`git clone && docker
  compose up -d`, no copy step), and editing `config.yaml` always takes
  effect after `docker compose up -d --force-recreate`.
- Upgrading an existing `horizon-data` volume across a release that adds
  columns to `Guide`/`Journey` (e.g. the `difficulty`/`estimated_time` move in
  v0.3) crashed every guide/journey page with `sqlite3.OperationalError: no
  such column`, because `init_db()` only creates missing tables, never adds
  missing columns to an existing one. *(Tracked for a follow-up migration
  fix — current workaround: delete `/data/horizon.db` and restart to reseed
  from `content/`.)*
- Existing deployments whose `content_dir` predated the multi-guide
  `journeys.yaml` rework or the checklists feature kept seeing single-guide
  plans and an empty checklists list forever, because `_ensure_content_dir()`
  treated *any* existing `journeys.yaml` as a fully up-to-date content
  directory and skipped copying bundled content entirely. It now always
  refreshes `journeys.yaml` (shipped, curated content) and fills in any
  guide/checklist/skill files missing from an existing `content_dir`, without
  touching files an operator has already edited. Trigger the admin panel's
  "reseed content" action (or delete the journeys/guides/checklists rows) to
  pick this up on an existing install.
- The site header and footer stretched to the full viewport width instead of
  lining up with the centred page content; they now share the same
  `max-width`/centred container as `.content`.
- The page `<title>` and homepage tagline used an em dash and described
  horizon as being "about rebuilding"; reworded to plain language matching
  `CLAUDE.md`'s description (a library of guides and a local AI assistant for
  water, food, energy, shelter, and health).

### Changed
- **Guides are now the primary thing you browse and read.** Clicking a topic
  from the home page (or a category) goes **straight to the how-to guide**,
  instead of an interstitial "journey" page that wrapped a single guide and an
  empty prerequisites list. Each guide now carries its own difficulty and
  estimated time (migrated into guide front matter) and links back to any plan
  it belongs to.
- **"Journeys" are now a small set of curated, ordered "step-by-step plans"
  (tracks).** A plan strings several guides together in the order you'd work
  through them (e.g. *Provide safe drinking water for a group*: test → choose
  treatment → build a filter). The 57 single-guide journeys are gone; guides
  outside a plan are still fully browsable from the library. Prerequisites
  (often empty, and an extra click) have been removed — a plan's guide order is
  the path.
- **`/recommend` leads with guides**, then surfaces the curated plans that fit.

### API
- `GET /api/journeys` now returns the curated plans (a handful), not one entry
  per guide. `GET /api/journeys/{id}` returns its guides **in order**; the
  `prerequisites` field is retained but is **always an empty list** (kept for
  response-shape compatibility). Guide summaries in this response, and the
  `GET /api/guides/{id}` response, now include `difficulty` and
  `estimated_time`. Endpoint paths and the rest of the response shapes are
  unchanged.

## [0.4.0] — 2026-06-28

The "**maintainable node**" release: an operator can now diagnose, repair, and
re-seed a node entirely from the admin panel (or the headless CLI) — no SSH,
restart, or guesswork.

### Added
- **Check & repair (Admin → Check & repair).** A new health view that surfaces
  the real problems on a node in plain language: broken prerequisite and
  journey→guide links, guides with no Markdown file on disk, missing local guide
  images, orphaned content (guides nothing links to, journeys with no guides,
  guide files never seeded), duplicate content ids that silently collapse on
  seeding, whether the search/RAG index is present and current, and — opt-in,
  since it costs energy — whether the local model runtime is reachable. Each
  check is a clear ok/warn/fail/off row with the specific offending items listed.
- **One-click repairs.** From the same page: **Rebuild search index** (re-embed
  the content so semantic search matches what's on disk) and **Re-seed content
  from disk** (rebuild the journeys/guides/links metadata from the Markdown,
  with a before/after summary, then rebuild the index). Both are
  **low-power-aware**: the energy-hungry index rebuild is paused under low-power
  mode with a clear note rather than hammering a weak supply. Repairs run over
  HTMX with a live result banner and degrade to a plain form post (PRG redirect)
  with no JavaScript.
- **A recent-events feed.** A small in-memory ring buffer captures horizon's log
  events (seeding, indexing, repairs, embedding fall-backs) and shows the latest
  on the health page, so an operator can see what the node has been doing without
  tailing a log file. Bounded and offline-first; lost on restart by design.
- **`horizon-admin check`.** The headless twin of the health view: runs the same
  content-health diagnostics from the terminal (`--check-model` to also probe the
  model, `--json` for scripting), exiting non-zero on a hard failure like
  `doctor`.
- **`horizon-admin seed --force`.** Re-seed a populated database from the content
  on disk (the CLI equivalent of the panel's re-seed repair); plain `seed` still
  only loads into an empty database.

### Changed
- The admin dashboard navigation now leads with **Check & repair** alongside
  Library, Content packs, and Integrations.

## [0.3.0] — 2026-06-28

The "**which should I pick?**" release: horizon now helps you *decide*, not only
*do*. New decision guides, a richer guide format for comparing options, and an
admin library that shows the whole node at a glance.

### Added
- **Decision guides ("which to pick").** A new kind of guide that helps a visitor
  *choose* before they build, answerable entirely from local content: which water
  treatment for which source and threat, how big a solar + battery system for your
  loads (with a worked example and sizing table), which crops for your season,
  climate, and goal, and which shelter for how long you need it and your climate.
  Each leads a new *entry-point* journey (a "Start here" decision step) that the
  matching build journey now builds on, so a track reads **decide → build**.
- **Richer guide format — callouts.** Guides can mark a labelled blockquote
  (`> **Pick this if:** …`, `> **Avoid if:** …`, `> **Spec:** …`, `Decide`,
  `Risk`, `Tip`, `Note`) and horizon renders it as a distinct, scannable callout.
  It is pure CommonMark under the hood, so it **degrades gracefully**: anywhere
  the styling is absent (plain Markdown, another renderer) the bold label still
  carries the meaning. Comparison tables already scroll responsively; callouts
  flatten to a high-contrast rule + bold label in print and low-power/e-ink.
- **Browse the whole library in admin.** A new **Admin → Library** page lists
  every guide, journey, and md skill on the node — previewable in the panel
  (rendered Markdown, including md skills, which have no public page) — and flags
  thin content (a guide with no summary or no journey links, a journey with no
  guides, a very short md skill) so an operator can see what's there and what
  needs filling out.
- **A "choosing well" md skill.** New `content/md_skills/choosing-well.md` steers
  the assistant to help people decide honestly — start from their situation, make
  trade-offs visible, put safety first, recommend criteria not brands — keeping
  the new steering in content, not business logic.

### Added (earlier, unreleased before 0.3.0)
- **A skill-tree view of the plans.** The *Step-by-step plans* page no longer
  renders one undifferentiated grid: journeys are now grouped into per-topic
  tracks, each with its category icon, a plain-language example, and a plan
  count. Within a track, entry points come first (still flagged *Start here*)
  and any journey that builds on another shows a "Builds on …" connector, so the
  prerequisite path is visible while browsing — not only on the detail page. The
  category icons are factored into a shared template macro reused by the home
  page, keeping the iconography consistent and fully offline (inline SVG, no
  external requests). Verified with Playwright at 375×812 and 1200×800 (zero
  horizontal overflow on every page).
- **A horizon logo mark and favicon.** The header now carries a small inline-SVG
  emblem (a sun rising over hills and water, echoing the project logo) beside the
  wordmark, and the site ships a vendored `favicon.svg` (`/static/favicon.svg`).
  Both are local assets — no external request — so the brand still works fully
  offline. The wordmark also moves to a soft rounded font stack that resolves to
  fonts already on the device.

### Changed
- **The mobile header collapses behind a menu button.** On phone-width screens
  the navigation links used to stack into several tall rows, eating roughly half
  the first screen. They now fold into a hamburger menu, so the header is a single
  compact row (~60px) until tapped open. The toggle is plain JS, so it works in
  low-power mode too; on desktop the nav stays inline as before. Verified with
  Playwright at 375×812 and 1200×800 (zero horizontal overflow on every page).
- **`chromadb` is now the optional `ai` extra, not a core dependency.** It pulled
  a large, mostly-unused tree (onnxruntime, tokenizers, huggingface-hub, grpcio,
  kubernetes, …) on every install and Docker build, even though horizon supplies
  its own embeddings (Ollama/llama.cpp) and never uses Chroma's bundled model.
  The default `pip install .` and Docker image are now lean and fast to build;
  vector search is opt-in via `pip install '.[ai]'` or
  `docker build --build-arg INSTALL_EXTRAS=ai`. Retrieval falls back to keyword
  search when it is absent, so the assistant still answers fully offline. Chroma's
  anonymous telemetry is also pinned off (`ANONYMIZED_TELEMETRY=false`) for
  offline-first deploys.
- **The Docker build caches pip downloads between builds.** The build now uses a
  BuildKit cache mount instead of `--no-cache-dir`, so a clean rebuild reuses
  already-downloaded wheels rather than re-fetching them from PyPI each time.

### Fixed
- **Static assets are cache-busted, so a deploy no longer serves a stale
  stylesheet.** `app.css`/JS are linked with a content-derived `?v=` token, so a
  new build yields a URL the browser hasn't cached. Previously a fresh template
  could render against the old, browser-cached CSS — the header looked broken
  until a manual hard refresh.
- **The Docker image no longer crash-loops on a missing `web/static` directory.**
  The server-rendered UI assets (`web/static`, `web/templates`) were not declared
  as package data, so a real `pip install .` (the Docker build) dropped them and
  the app died at startup mounting a non-existent directory — looping forever
  under `restart: unless-stopped`. They are now shipped in the wheel. The bundled
  seed `content/` is likewise located across install layouts (new
  `HORIZON_BUNDLED_CONTENT` override, set by the image) so first-run seeding works
  when horizon is installed away from the source tree. Verified by installing the
  built wheel into a clean environment and booting it.
- **A malformed `config.yaml` no longer crash-loops the node.** Settings are
  loaded at import time, so an invalid or badly-indented `config.yaml` used to
  raise during startup — under Docker's `restart: unless-stopped` that meant an
  endless restart loop serving nothing. horizon now logs a clear error naming the
  file and the problem and falls back to built-in defaults so the node still
  boots and serves its local content; fix the file and restart to apply settings.

## [0.2.0] — 2026-06-28

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
- **Natural-disaster guides** — the `emergencies` category gains civilian-safety
  guidance for floods, earthquakes, drought, nuclear/radiological emergencies,
  wildfires, and severe storms (high wind, hurricanes, tornadoes, lightning),
  each written for both urban and out-of-town/rural settings.
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
- **The bundled Ollama runtime is now opt-in.** `docker compose up` no longer
  starts (or pulls the ~3GB image for) the `ollama` service, and `horizon` no
  longer `depends_on` it — the default install is small and boots fully offline,
  with the assistant falling back to local guide search. Enable the local model
  either by pointing `llm.endpoint` at your own llama.cpp / OpenAI-compatible
  server, or by starting the bundled runtime with the `ai` profile
  (`docker compose --profile ai up -d`). README quickstart updated to match.
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

[Unreleased]: https://github.com/richardkfm/horizon/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/richardkfm/horizon/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/richardkfm/horizon/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/richardkfm/horizon/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/richardkfm/horizon/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/richardkfm/horizon/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/richardkfm/horizon/releases/tag/v0.1.0
