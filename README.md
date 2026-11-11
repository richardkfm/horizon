<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/logo-dark.svg">
  <img src="docs/images/logo-light.svg" alt="horizon" width="320">
</picture>

**An offline-first autonomy node for basic human skills.**

[![Status: v0.9.5](https://img.shields.io/badge/status-v0.9.5-blue.svg)](CHANGELOG.md)
[![License: PolyForm Noncommercial 1.0.0](https://img.shields.io/badge/License-PolyForm%20Noncommercial%201.0.0-blue.svg)](LICENSE)

</div>

horizon is a small server you run on your own hardware — a Raspberry Pi,
mini-PC, or VM. It gives a household or neighbourhood **visual how-to guides**,
**step-by-step plans**, and a **local AI assistant**. Fully offline after setup.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/morning-dark.svg">
  <img src="docs/images/morning-light.svg" alt="An animated ASCII morning: the sun shines over a cottage with solar panels, a sunflower, a sapling and a small wind turbine, while birds cross the sky." width="100%">
</picture>

## What you get

- **Visual guides** across 15 topics, drawn with ASCII diagrams that work on any screen or paper.
- **Step-by-step plans** that thread guides into a path.
- **Print-ready** A4 PDFs and tick-able checklists.
- **Offline extras:** a Wikipedia reference library and a map viewer.
- **Local AI assistant** that cites your guides. No cloud. Optional.
- **Made for neighbours:** plain language, phone-friendly, accessible.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/topics-dark.svg">
  <img src="docs/images/topics-light.svg" alt="The fifteen topics, each with its own small ASCII emblem: water, food, energy, shelter, health, cooperation, survival, culture, language, crafts, emergencies, cooking, calculations, technology and mobility." width="100%">
</picture>

→ [All features](docs/features.md)

## Screenshots

![The home page: one sentence, a search field, the ASCII morning scene, and the fifteen topics as a contents list](docs/screenshots/home.png)

![A guide in dark mode: italic standfirst, a ruled row of facts, a Risk note in the margin, and an amber ASCII diagram](docs/screenshots/guide-dark.png)

![Three phone screens: the guide list, a first-aid guide in dark mode, and a step-by-step plan](docs/screenshots/phones.png)

## Quickstart

```bash
git clone https://github.com/richardkfm/horizon
cd horizon
docker compose up -d
```

Open **http://&lt;host-ip&gt;:8080** on any device in your network.
No Docker or git? → [Install guide](docs/install.md).

## Configuration

Edit `config.yaml` — it ships with safe, offline defaults.

<img width="800" height="682" alt="The horizon admin CLI menu" src="https://github.com/user-attachments/assets/d0f8e3d1-67a2-45fc-b538-8b8f472f029c" />

Admin token, CLI, local AI, content packs → [Operating guide](docs/operating.md).

---

[Install](docs/install.md) · [Features](docs/features.md) ·
[Operating](docs/operating.md) · [Authoring content](docs/authoring-content.md) ·
[API](docs/api.md) · [Changelog](CHANGELOG.md) · [Roadmap](ROADMAP.md)

**Status:** v0.9.5 · [PolyForm Noncommercial 1.0.0](LICENSE): free for
noncommercial use; commercial use needs a separate agreement.
