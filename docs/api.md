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
| `GET /api/guides/{id}` | Guide metadata + rendered HTML (`?format=markdown` for source). |
| `POST /api/recommend` | Suggest guides (and the plans that fit) for a goal + context. |

A plan needs at least two guides to be a plan, so single-guide entries are
never listed and return 404 on detail — guides are the primary unit and stand
on their own.

`POST /api/recommend` example (`goal` is required; `people`, `climate`, and
`resources` are optional):

```json
{ "goal": "community_garden", "people": 10, "climate": "temperate" }
```

The response is `{ "journeys": [...], "guides": [...] }`, matched locally with
no LLM involved.

## AI API

| Method & path | Purpose |
| --- | --- |
| `POST /api/ai/answer` | Locally-retrieved, cited answer to a question. |

```json
// request — `context` and `no_jargon` are optional
{ "question": "How do I make river water safe to drink?", "context": {}, "no_jargon": true }
// response
{ "answer": "...", "citations": ["water-slow-sand-filter", "checklist-water-safety"] }
```

`citations` are the ids of the local content the assistant drew on (guides,
plans, or md skills) — it always cites its sources. `no_jargon` overrides the
`ai.no_jargon_default` config setting for a single request; omit it to use the
node's default (plain language).

The endpoint is offline-first and never errors because a model is missing: with
no model runtime reachable, retrieval falls back to keyword search and the
answer degrades to a cited pointer at the most relevant local guides.

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
