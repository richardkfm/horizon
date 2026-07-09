# Operating a horizon node

Configuration, the `horizon-admin` CLI, and content packs — everything an
operator needs after the [Quickstart](../README.md#quickstart-docker-recommended).

## Configuration

Edit `config.yaml` directly (tracked in the repo with safe defaults; see
`config.example.yaml` for the fully annotated reference). With Docker,
`config.yaml` is bind-mounted into the container, so editing it always takes
effect — after changing it, apply with `docker compose up -d --force-recreate`.

Key settings: `server.port`, `data_dir`/`database`, `llm.*` (provider,
endpoint, models), `vectordb.*`, `rag.top_k`, `ai.no_jargon_default`
(plain-language answers, default `true`), `assistant.enabled` (the chat
assistant, default `true`), `power.low_power` (solar/battery mode), `ethics.*`,
and `content_packs.dir`.

`web.enabled` (default `true`) controls the server-rendered web UI; turn it off
to run a headless node with only the JSON API and the `horizon-admin` CLI.

A few settings also honour environment overrides, so a script can flip them
without editing `config.yaml`: `HORIZON_LOW_POWER`, `HORIZON_ASSISTANT_ENABLED`,
and `HORIZON_ADMIN_TOKEN` are read at request time; `HORIZON_WEB_ENABLED` is
read at startup.

### Admin token

The admin area is on by default. If you don't set `admin.token` (or
`HORIZON_ADMIN_TOKEN`), horizon generates a random token on first run and saves
it to `<data_dir>/admin_token` (e.g. the `horizon-data` volume). Log in at
`/admin/login` with that token.

```bash
# Find the auto-generated token (Docker):
docker compose exec horizon cat /data/admin_token
# or check the startup logs:
docker compose logs app | grep -i admin

# Bare-metal/systemd install (data_dir defaults to /var/lib/horizon):
sudo cat /var/lib/horizon/admin_token
```

To set your own token instead, add it to `config.yaml`:

```yaml
admin:
  token: "your-strong-token-here"
```

then apply with `docker compose up -d --force-recreate` (or set the
`HORIZON_ADMIN_TOKEN` environment variable, which takes precedence over both
`config.yaml` and the auto-generated token).

### Local model runtime (optional)

The default install stays fully offline — **no model runtime is pulled**. The
"Ask a question" assistant falls back to local guide search until you give it a
model. horizon supports two providers:

- **Ollama (default)** — easiest to run and maintain. With Docker, start the
  bundled runtime with the `ai` profile and pull a model. Recommended for most
  users:

  ```bash
  docker compose --profile ai up -d          # opt-in `ai` profile; ~3GB image
  docker compose exec ollama ollama pull llama3.2:3b
  docker compose exec ollama ollama pull nomic-embed-text
  ```

- **llama.cpp / OpenAI-compatible** — if you already run a `llama-server` (or
  any OpenAI-style endpoint), point horizon at it instead of pulling a
  container:

  ```yaml
  llm:
    provider: openai-compatible
    endpoint: http://192.168.1.10:8081/v1   # your server's OpenAI-compatible base URL
    model: local-model                      # whatever your server serves
    embedding_model: nomic-embed-text        # only if it exposes an embeddings route
  ```

The default image also ships **without** the heavy vector-search stack
(chromadb + onnxruntime/tokenizers/…), so it builds fast and the assistant
retrieves with keyword search. To bake in vector search, build with the `ai`
extra: `docker compose build --build-arg INSTALL_EXTRAS=ai` (or
`docker build --build-arg INSTALL_EXTRAS=ai .`). Bare-metal: `pip install -e .[ai]`.

## Command line (`horizon-admin`)

For a node with no browser, `horizon-admin` is a full operator **and** reader
interface — everything runs offline (only `packs download` touches the network):

```bash
horizon-admin status                 # runtime + content overview (with logo)
horizon-admin doctor                 # health-check every optional integration
horizon-admin check                  # content-health diagnostics (links, files, index)
horizon-admin seed                   # load bundled content into an empty db
horizon-admin seed --force           # re-seed a populated db from content on disk
horizon-admin reindex                # rebuild the vector index after edits
horizon-admin config                 # effective settings (admin token redacted)

horizon-admin journeys               # browse the curated step-by-step plans
horizon-admin journey <id>           # one plan: its guides, in order
horizon-admin guides --search water  # browse / search how-to guides
horizon-admin guide <id>             # read a guide as terminal text (--raw for Markdown)
horizon-admin recommend safe water   # suggest where to start for a goal
horizon-admin ask "how do I store rainwater"   # cited assistant answer (offline fallback)

horizon-admin packs list             # manage offline content packs
```

Most commands accept `--json` for scripting. Run with `web.enabled: false`
(or `HORIZON_WEB_ENABLED=0`) to serve only the JSON API and drive the node
entirely from this CLI.

**Access:** the CLI is not gated by the admin token (that token guards the
network-exposed web admin area). Like `psql` or `systemctl`, it trusts the OS
user — anyone who can run it can already read the database and `config.yaml`
directly. Control access with shell login and file permissions; `horizon-admin
config` redacts the token so it is never printed.

## Content packs

Larger offline resources (Wikipedia, medical ZIMs, maps) are optional downloads
fetched while online and then used offline. The catalog of available packs lives
in `content/packs.yaml` (copied to your data dir on first run, so it is editable
and known offline). Downloads are checksum-verified when the catalog provides a
`sha256`, and stored under `content_packs.dir`.

```bash
horizon-content list                     # available + installed packs
horizon-content download wikipedia-en-mini
horizon-content remove wikipedia-en-mini
```

The same operations are also available under `horizon-admin packs …` and as a
web wizard under **Admin → Content packs**, which downloads in the background and
shows live progress.

Once a Wikipedia/WikEM-style ZIM pack is installed, read it right in the
browser at **Reference library** (linked from the main nav once a pack is
installed) — full-text search plus an article view, no external Kiwix viewer
needed. Maps packs (`.osm.pbf` raw OpenStreetMap extracts) don't have an
in-browser viewer yet; see the note in `content/packs.yaml`. Map packs come in
two sizes: for Africa, Asia, Europe, and North America there's a pack per
country (e.g. Germany at 4.5 GB) as well as the whole continent (e.g. all of
Europe at 31+ GB) — pick the country unless you actually need every country
on the continent. The other four continents are small enough to ship as a
single file. Either way, this is raw source data, not a ready-to-view basemap.
