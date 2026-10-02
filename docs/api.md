# API reference

horizon exposes a small, stable HTTP surface so other projects (e.g.
`neighbourgood`) can link to plans and guides without horizon knowing anything
about them. These endpoints are horizon's integration contract and are kept
backward-compatible; see [`CHANGELOG.md`](../CHANGELOG.md) for any change that
affects them.

Interactive API docs (Swagger UI) are served at `/docs` when the app is
running.

## Knowledge API (read-only)

| Method & path | Purpose |
| --- | --- |
| `GET /api/journeys` | List the curated step-by-step plans; `?category=` to filter (unknown category → 400). |
| `GET /api/journeys/{id}` | Full plan: its guides **in order** (`prerequisites` is always `[]`). |
| `GET /api/guides/{id}` | Guide metadata + Markdown source, plus rendered HTML unless `?format=markdown`. |
| `POST /api/recommend` | Suggest guides (and the plans that fit) for a goal + context. |

A plan needs at least two guides to be a plan, so single-guide entries are
never listed and return 404 on detail — guides are the primary unit and stand
on their own.

### Cross-references in guide Markdown

A guide's `markdown` may contain wiki-style cross-references:
`[[guide-id]]`, `[[guide-id|custom text]]`, `[[plan:journey-id]]`, and
`[[checklist:checklist-id]]` (`journey:` is accepted as a synonym for
`plan:`). A consumer that shows the Markdown should treat them as links (to
`GET /api/guides/{id}`, `GET /api/journeys/{id}`, or horizon's
`/checklists/{id}` page) or strip them to their words — the custom text if
given, otherwise the target's title or id. In the `html` field they are
rendered as `<a class="xref">` links to the conventional page URL
(`/guides/{id}`, `/journeys/{id}`, `/checklists/{id}`), labelled with the
custom text or, failing that, the id; the API does not look up titles. Raw
HTML in guide Markdown is never passed through: the `html` field shows it
escaped, as text.

`POST /api/recommend` example (`goal` is required; `people`, `climate`, and
`resources` are optional):

```json
{ "goal": "community_garden", "people": 10, "climate": "temperate" }
```

The response is `{ "journeys": [...], "guides": [...] }`, matched locally with
no LLM involved. Each list holds at most five items, best match first, and
drops anything scoring under 40% of the best match — so a precise goal can
return just one or two strong results rather than five loose ones. Common
question words and filler ("how do I keep my family safe", "what should we
know about …") are ignored when matching.

## AI API

| Method & path | Purpose |
| --- | --- |
| `POST /api/ai/answer` | Locally-retrieved, cited answer to a question. |

```json
// request — `context` and `no_jargon` are optional
{ "question": "How do I make river water safe to drink?", "context": {}, "no_jargon": true }
// response
{ "answer": "...", "citations": ["water-slow-sand-filter", "water-choosing-treatment"] }
```

`citations` are the ids of the local **guides** the answer drew on, in
retrieval order, without duplicates — it always cites its sources. md skills
steer the answer but are never cited, and plans are not cited directly. `no_jargon` overrides the
`ai.no_jargon_default` config setting for a single request; omit it to use the
node's default (plain language).

The endpoint is offline-first and never errors because a model is missing (or
returns something malformed): with no usable model runtime, retrieval falls
back to keyword search and the answer degrades to a short, plain-language
pointer at the most relevant local guides, listed by **title** (one `- Title`
line each; the ids are in `citations`). When nothing matches, it suggests
browsing the step-by-step plans or asking in different words. In low-power
mode the answer takes the same shape (explaining that the node is saving
energy) and the model is never called, not even for embeddings.

## Errors, compression, and caching

- **Errors under `/api/*` are JSON**, as FastAPI produces them:
  `{"detail": "..."}` for 400/404, and the standard validation body for 422.
  The same goes for `/healthz`, `/docs`, `/redoc`, `/openapi.json`, and any
  request carrying an `HX-Request` header. Every *other* path — the
  browser-facing pages — returns a friendly HTML error page with the same
  status code (404, 400, 405, 422, and 5xx, including an unexpected crash).
  An unexpected crash on an API path still returns the plain-text
  `Internal Server Error` 500 it always did. With `web.enabled: false` every
  error is JSON (or that plain-text 500).
- **gzip:** responses over 1 KB, JSON included, are gzip-compressed when the
  client sends `Accept-Encoding: gzip`. Standard HTTP clients decompress
  transparently; nothing changes for a client that doesn't ask for it.

## Optional integrations

horizon is **fully usable standalone**. Integrations are opt-in and horizon
never hard-depends on them.

- **neighbourgood** (or any app) can call the read-only Knowledge API to link
  tasks/events to horizon's journeys and guides. horizon stores no users or
  social graph.
- **moral-core** ethics hook: set in `config.yaml` (off by default):

  ```yaml
  ethics:
    enabled: true
    endpoint: http://moral-core.local/api/evaluate
  ```

  When enabled, draft answers are sent for approve/adjust/block refinement. If
  moral-core is unreachable or disabled, horizon uses its built-in md skills.

The admin area (**Admin → Integrations**) shows the live status of the local
model runtime, the ethics hook, and installed content packs at a glance.
