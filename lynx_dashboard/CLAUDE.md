# CLAUDE.md — `lynx_dashboard` package

Scoped guidance for the application package. This is the only source-bearing
module in the repo; everything the dashboard does at runtime lives here. For
project-wide context see the [root CLAUDE.md](../CLAUDE.md).

## Responsibility

Catalog the Lince Investor Suite, recommend the right agent for a query, and
launch any app/agent in the interface mode the user chose. The package holds
only **display metadata and launch logic** — the authoritative GICS → agent
mapping lives in `lynx_investor_core.sector_registry.AGENT_REGISTRY`, and all
real analysis happens in the child processes it spawns.

## Logical modules (within this package)

The files group into five logical layers. The dependency direction is strictly
downward — lower layers never import higher ones.

| Layer | Files | Responsibility |
|-------|-------|----------------|
| **Catalog** (leaf) | `registry.py`, `history.py`, `easter.py`, `icons.py`, `__init__.py` | Frozen catalog of apps/agents + display helpers; recent-query store; egg content; icon generation; package/branding metadata. No internal imports. |
| **Resolution** | `launcher.py`, `recommender.py`, `plugin_loader.py` | Build launch argv + spawn children; resolve a query to a company profile and rank agents; bridge `lynx_investor_core.plugins` entry points into the catalog. Depend only on `registry`. |
| **Console UI** | `display.py`, `interactive.py`, `splash.py` | Rich console renderers; the REPL; animated splash. |
| **Dispatch** | `cli.py`, `__main__.py` | Argparse entry point that dispatches to a mode runner or a direct operation; process exit code propagation. Imports almost everything. |
| **Frontends** | `tui/app.py`, `gui/app.py` | Textual TUI (`DashboardApp`) and Tkinter GUI (`run_gui`). |
| **Public API** | `api.py` | Version-locked façade (`__api_version__ = "1.0"`) over catalog, recommender, launcher, and JSON serialization. |

These layers are kept inside one installable package on purpose: `api.py` is a
documented, version-locked import surface, so the files are **not** split into
separate top-level packages. Treat the table above as the module map.

## Public interface

- **Stable, for third parties:** `lynx_dashboard.api` — see
  [../docs/API.md](../docs/API.md). Everything in `api.__all__` and the
  `launchable_as_dict` / `recommendation_as_dict` JSON keys are contract.
- **Process entry points:** `cli.run_cli()` (returns an exit code),
  `__main__.main()`, and the `lynx-dashboard` console script.
- **Catalog:** `registry.APPS`, `registry.AGENTS`, `registry.ALL_LAUNCHABLES`,
  `Launchable`, and lookups `by_name` / `by_keybinding` / `by_registry_name` /
  `apps_for_mode` / `agents_for_mode`, plus translation-aware `display_*`
  helpers.
- **Recommender:** `recommend_for_query()` → `Recommendation`.
- **Launcher:** `build_command()`, `format_command()`, `launch_blocking()`,
  `launch_detached()`, `resolve_executable()`, `mode_to_flag()`.

## Module-local conventions

- **Registry is frozen dataclasses** — safe to import at module load. All
  modes default to `_ALL_MODES` unless a `Launchable` overrides them. Agents
  must set a unique `keybinding` and a `registry_name` that matches
  `AGENT_REGISTRY`; consistency tests enforce both.
- **`display_*` helpers are translation-aware** and fall back to English when
  locale data is missing — render through them, don't read raw fields.
- **Recommender pipeline** (`_fetch_yf_profile_uncached`) is a linear,
  `@lru_cache`-backed cascade: ticker → core resolver → Yahoo search → name
  fallback → suffix strip → offline hints. Ranking weights sector (100) over
  industry (50) over description (10). Junior-market suffixes
  (`.V`, `.CN`, `.NE`, `.NEO`, `.BO`) are blocked from base-symbol stripping.
- **Launcher builds argv in stages** (exe → run-mode flag → UI flag →
  `--refresh` → ticker → extra args). TUI launches wrap the call in
  `App.suspend()`; GUI launches detach with stdio to `/dev/null`. Each child
  owns its own `data/` — no shared runtime state, no IPC.
- **Splash** is skipped by `--no-splash`, `LYNX_NO_SPLASH=1`, or `CI=1`.
- **Tests are hermetic:** pass `dry_run=True` to avoid spawning; set
  `LYNX_DASHBOARD_HISTORY` to redirect the history file.

See [../docs/DEVELOPMENT.md](../docs/DEVELOPMENT.md) for step-by-step recipes
(adding a launchable, a recommender step, or a launch mode).
</content>
