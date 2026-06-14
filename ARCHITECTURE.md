# Architecture

A one-page tour of how Lynx Dashboard fits together. For the detailed
dataflow, mode-inheritance table, and executable-resolution rules see
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## The shape of the thing

Lynx Dashboard is a **launcher, not an analyzer**. It catalogs the Lince
Investor Suite, recommends an agent for a query, and spawns the chosen
target as its own process. It deliberately owns almost no state — the GICS →
agent mapping comes from `lynx_investor_core.sector_registry.AGENT_REGISTRY`,
and all real analysis happens in the children it launches.

## Logical modules

All code lives in the single installable package `lynx_dashboard`. Inside it
the files form five logical layers, with dependencies pointing strictly
downward (a lower layer never imports a higher one):

```
        ┌──────────────────────────────────────────────┐
        │ Frontends      tui/app.py · gui/app.py        │
        │ Dispatch       cli.py · __main__.py           │   Public API
        ├──────────────────────────────────────────────┤   api.py
        │ Console UI     display.py · interactive.py    │   (façade over
        │                splash.py                      │    every layer,
        ├──────────────────────────────────────────────┤    version-locked)
        │ Resolution     launcher.py · recommender.py   │
        │                plugin_loader.py               │
        ├──────────────────────────────────────────────┤
        │ Catalog (leaf) registry.py · history.py       │
        │                easter.py · icons.py · __init__ │
        └──────────────────────────────────────────────┘
```

- **Catalog** — frozen dataclasses describing every app/agent plus display
  metadata; recent-query store; egg content; icon generation; branding. No
  internal imports.
- **Resolution** — turn a query into a company profile and rank agents
  (`recommender`); build argv and spawn children (`launcher`); discover
  entry-point plugins (`plugin_loader`). Depend only on the catalog.
- **Console UI** — Rich renderers, the REPL, and the splash animation.
- **Dispatch** — argparse entry point that routes to a mode runner or a
  direct operation (`--recommend`, `--info`, `--launch`, `--list`).
- **Frontends** — the Textual TUI (`DashboardApp`) and Tkinter GUI
  (`run_gui`).
- **Public API** — `api.py` re-exports a stable, documented surface across
  every layer for third-party integrations.

These layers stay inside one package on purpose: `lynx_dashboard.api` is a
version-locked public import surface, so the modules are not separated into
distinct top-level packages.

## Dataflow

```
query / keypress
      │
      ▼
  cli.py / tui / gui  ──►  recommender ──►  registry (rank agents)
      │                                         │
      ▼                                         ▼
  launcher.build_command  ──►  subprocess.run(...)  ──►  child app/agent
```

## Mode inheritance

The dashboard launches each child in a way that matches the mode it was
opened in: console/interactive attach to the terminal; TUI suspends
(`App.suspend()`) then runs; GUI launches detached in its own window. The
mode can be overridden at runtime. Full table in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#mode-inheritance).

## External dependencies

- `lynx-investor-core` — suite metadata, the sector/agent registry, About
  and logo helpers, and the plugin entry-point system.
- `rich` — console rendering. `textual` — the TUI. Tkinter (stdlib) — the GUI.
- `argcomplete` — shell completion. `yfinance` (optional) — recommender
  profile lookups. `Pillow` (optional) — PNG icon generation.

## No shared runtime state

Each child is its own process with its own `data/`, argparse, and cache. The
dashboard keeps no handle on a running child — hence no "attach to session"
feature and no IPC layer.
</content>
