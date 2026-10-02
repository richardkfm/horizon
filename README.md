<div align="center">
  
<img width="480" alt="horizon" src="https://github.com/user-attachments/assets/f61ff046-3a4b-4fec-a99c-004e312b9034" />


# horizon
**An offline-first autonomy node for basic human skills.**

[![License: PolyForm Noncommercial 1.0.0](https://img.shields.io/badge/License-PolyForm%20Noncommercial%201.0.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-261230.svg)](https://github.com/astral-sh/ruff)
[![Offline-first](https://img.shields.io/badge/offline--first-%E2%9C%93-success.svg)](#)
[![Status: v0.9.3](https://img.shields.io/badge/status-v0.9.3-blue.svg)](CHANGELOG.md)

</div>

horizon is a small server you run on your own hardware — a Raspberry Pi,
mini-PC, or VM. It gives a household or neighbourhood **visual how-to guides**,
**step-by-step plans**, and a **local AI assistant**. Fully offline after setup.

Most of us are one dead Wi-Fi signal away from being stuck. horizon puts basic
human skills back within reach: living well, sustainably, and without coercion.

<img width="800" height="752" alt="horizon-full" src="https://github.com/user-attachments/assets/f9cc8906-a041-479b-88a8-86ef27c5febd" />

## What you get

- **Visual guides** across 15 topics — water, food, energy, health, and more.
- **Step-by-step plans** that thread guides into a path.
- **Print-ready** A4 PDFs and tick-able checklists.
- **Offline extras:** a Wikipedia reference library and a map viewer.
- **Local AI assistant** that cites your guides. No cloud. Optional.
- **Made for neighbours:** plain language, phone-friendly, accessible.

→ [All features](docs/features.md)

## Screenshots

A guide with an ASCII diagram, dark theme:

![A horizon guide page in dark mode, showing the reverse-wrap cordage technique with a captioned amber ASCII diagram](docs/screenshots/guide-ascii-diagram.png)

The admin **Content packs** page, for downloading offline extras:

![The horizon admin Content packs page in light mode, listing downloadable offline packs with size and status](docs/screenshots/admin-content-packs.png)

## Quickstart

```bash
git clone https://github.com/richardkfm/horizon
cd horizon
docker compose up -d
```

Open **http://&lt;host-ip&gt;:8080** on any device in your network.

No Docker or git? Bare-metal, curl installer, systemd →
[Install guide](docs/install.md).

## Configuration

Edit `config.yaml` — it ships with safe, offline defaults.

<img width="800" height="682" alt="horizon_cli_new3" src="https://github.com/user-attachments/assets/d0f8e3d1-67a2-45fc-b538-8b8f472f029c" />

Admin token, CLI, local AI, content packs →
[Operating guide](docs/operating.md).

## Documentation

- [Install](docs/install.md) — Docker, bare-metal, curl, systemd
- [Features](docs/features.md) — the full tour
- [Operating](docs/operating.md) — config, CLI, AI, packs
- [Authoring content](docs/authoring-content.md) — guides, plans, imports
- [API](docs/api.md) — Knowledge API and AI API

## Status

**Status:** v0.9.3 — see [CHANGELOG](CHANGELOG.md) and [ROADMAP](ROADMAP.md).

## License

[PolyForm Noncommercial 1.0.0](LICENSE) — free for noncommercial use.
Commercial use needs a separate agreement.
