# Adding guides, checklists, plans & md skills

Content lives under `content/` in the repo (copied into the data directory on
first run). Guides are the primary unit — a new file seeds and indexes itself,
no plan required.

## Guides

`content/guides/<id>.md`, with YAML front matter:

```markdown
---
id: water-rainwater-harvesting
title: Harvest and store rainwater
category: water
summary: Collect roof runoff and store it safely.
difficulty: 2
estimated_time: "1 day"
---
# ...steps, materials, risks, images...
```

Put images in `content/guides/images/` (served at `/guides/images`). Bodies are
CommonMark with GFM tables.

### Callouts

To draw attention to a choice, start a blockquote with a recognised **bold
label** and horizon renders it as a callout:

```markdown
> **Pick this if:** your water is cloudy or from a river.
> **Avoid if:** it could carry chemicals or salt.
> **Spec:** 60 cm sand bed, ~0.1 m/h flow.
> **Do now:** get out, stay out, and call for help.
```

Labels map to `pick` / `avoid` / `spec` / `decision` / `risk` / `do now` /
`tip` / `note` (with synonyms); an unrecognised label stays an ordinary
blockquote.

### Figures

Prefer an **ASCII diagram**: a fenced ` ```ascii ` code block followed by an
`*italic caption*` line renders as a captioned `<figure>` card. No image file to
draw, ship, or keep in sync — it reads correctly as-is with no rendering at all
(raw Markdown, a CLI, `cat`), and it costs nothing on constrained hardware. This
is the default for guide diagrams; the ten line-art diagrams already in
`content/guides/` (cordage twisting, square lashing, fire-hardening, and so on)
all use it:

````markdown
```ascii
+---+
| A |
+---+
```

*Fig. 1: a labelled box*
````

For a figure that genuinely needs a real image (a photo, or line art too
detailed for monospace text), write a paragraph that is *only* an image; horizon
wraps it in a captioned `<figure>` using the alt text as the caption. Put the
file under `content/guides/images/` and prefer simple monochrome **SVG** line
art so it stays crisp in print/e-ink:

```markdown
![Fig. 1: a labelled diagram](images/example-diagram.svg)
```

## Checklists

`content/checklists/<id>.md`, with the same front matter as a guide (`category`
optional). Write items as a Markdown task list and horizon renders real,
tick-able checkboxes (ticks saved on-device only) that print as empty squares:

```markdown
---
id: go-bag
title: Go-bag (grab-and-go kit)
summary: A packed bag by the door so you can leave within minutes.
---
- [ ] Water bottle and purification tablets
- [ ] Torch and spare batteries
```

Like guides, checklists are auto-discovered — drop in a file to publish one.

## Step-by-step plans

Add an entry to `content/journeys.yaml` with `id`, `title`, `description`,
`category`, `difficulty`, `estimated_time`, and `guides` (an **ordered** list of
guide ids). A plan is only worth adding where guides form a genuine "do this,
then this" path; the guide order is the path (there are no prerequisites).
Guides need no plan to be useful.

## md skills

`content/md_skills/<id>.md`: values, answer style, and domain checklists that
steer the assistant. These are indexed alongside guides.

---

Restart horizon to load the change: every startup syncs the database and
content directory with what's on disk (adds anything new, refreshes a plan's
guide order, drops any plan left with fewer than two guides) without touching
anything you've hand-edited, then re-indexes for the assistant.

## Importing external content (WikiHow, books)

`horizon-content import` turns outside material into a guide in the same
format, written under `<content_dir>/guides` (never the repo's bundled
`content/`, so third-party text never gets committed). The same conversion is
also available with no terminal, as a web wizard under **Admin → Import
content**: paste a page URL or upload a book file, pick a category, and it
writes the guide and re-seeds/re-indexes immediately.

```bash
# A WikiHow-shaped how-to page: title, intro, numbered steps, step images.
# WikiHow spans every topic, so --category is required, not guessed.
horizon-content import wikihow https://www.wikihow.com/Some-Article \
  --category crafts --reseed

# A local text/Markdown book, split into one guide per detected chapter.
# Defaults to category: culture (override with --category for other subjects).
horizon-content import book ./folklore-of-the-valley.txt \
  --id-prefix culture-valley-folklore --reseed
```

Both estimate a reading time from word count, download step images locally so
the guide still renders fully offline, and end the guide with a "Note" callout
recording the source and a reminder to check its licence (WikiHow text is
CC BY-NC-SA; a book may be copyrighted) before sharing the content further.
Network is only touched during the import itself — once written, an imported
guide is no different from a hand-authored one. Without `--reseed`, run
`horizon-admin seed --force` and `horizon-admin reindex` afterwards. See
`horizon-content import wikihow --help` / `import book --help` for all options.
