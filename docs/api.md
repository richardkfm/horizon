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
| `GET /api/journeys` | List the curated step-by-step plans; `?category=` to filter. |
| `GET /api/journeys/{id}` | Full plan: its guides **in order** (`prerequisites` is always `[]`). |
| `GET /api/guides/{id}` | Guide metadata + rendered HTML (`?format=markdown` for source). |
| `POST /api/recommend` | Suggest guides (and the plans that fit) for a goal + context. |

`POST /api/recommend` example:

```json
{ "goal": "community_garden", "people": 10, "climate": "temperate" }
```

## AI API

| Method & path | Purpose |
| --- | --- |
| `POST /api/ai/answer` | Locally-retrieved, cited answer to a question. |

```json
// request
{ "question": "How do I make river water safe to drink?", "context": {} }
// response
{ "answer": "...", "citations": ["water-slow-sand-filter", "checklist-water-safety"] }
```

`citations` are guide/journey ids — the assistant always cites the local
content it drew on.

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
