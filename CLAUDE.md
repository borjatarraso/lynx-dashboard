# CLAUDE.md — lynx-dashboard

Project-level guidance for agents working in this repo. Keep it terse; the
deep detail lives in the linked files.

## What this is

Lynx Dashboard is the unified launcher and command center for the Lince
Investor Suite. It is a **launcher, not an analyzer**: it catalogs every
suite app and sector-specialized agent, recommends the right agent for a
ticker/company query, and launches any target in one of four interface
modes (console, interactive REPL, Textual TUI, Tkinter GUI). It owns very
little state — most of what it knows comes from `lynx_investor_core` and
from each target app's own CLI.

## Top-level layout

```
lynx-dashboard/
├── lynx_dashboard/      # the application package (see lynx_dashboard/CLAUDE.md)
│   ├── tui/             # Textual TUI frontend
│   └── gui/             # Tkinter GUI frontend
├── docs/                # reference docs (ARCHITECTURE, API, DEVELOPMENT, …)
├── tests/              # pytest suite (hermetic; no network, no real subprocess)
├── img/                 # ASCII + PNG logos
├── lynx-dashboard.py    # thin script entry point
├── pyproject.toml       # packaging + pytest config
├── ARCHITECTURE.md      # one-page architecture tour → docs/ARCHITECTURE.md for detail
├── DESIGN.md            # design principles and the rationale behind them
└── ROADMAP.md           # status, versioning/stability policy, possible directions
```

All application code lives in the single installable package
`lynx_dashboard`. The logical module boundaries inside it (catalog,
resolution, rendering, frontends, public API) are described in
[lynx_dashboard/CLAUDE.md](lynx_dashboard/CLAUDE.md) and
[ARCHITECTURE.md](ARCHITECTURE.md). They are kept inside one package on
purpose — `lynx_dashboard.api` is a version-locked public import surface, so
the modules are not split into separate top-level packages.

## Build / test commands

Run from source (the suite lives in sibling directories of this repo):

```bash
PYTHONPATH=.:../lynx-investor-core python lynx-dashboard.py --help
```

Run the tests (hermetic — no network, no real subprocesses):

```bash
PYTHONPATH=.:../lynx-investor-core python -m pytest tests/ -q
```

After `pip install -e .` the `lynx-dashboard` console script is on `$PATH`.
`pyproject.toml` pins `testpaths = ["tests"]` and `addopts = "-v --tb=short"`.

## Conventions a new agent should follow

- **Prefer editing existing files over creating new ones.** Comments explain
  *why*, not *what*.
- **Catalog edits go through the registry.** Add apps/agents to
  `registry.APPS` / `registry.AGENTS`; agents must set `registry_name` to
  match `lynx_investor_core.sector_registry.AGENT_REGISTRY` (consistency
  tests enforce the 1:1 mapping and unique keybindings).
- **The public API is load-bearing.** Anything in `lynx_dashboard.api.__all__`
  and the `*_as_dict` JSON keys are contract; adding bumps minor, renaming or
  removing bumps major. `tests/test_api.py` locks every stable name.
- **Tests stay hermetic.** No network and no spawned subprocesses
  (`dry_run=True`); history writes to temp dirs via `LYNX_DASHBOARD_HISTORY`.
  Every new feature gets at least one regression test.
- **Error handling only at system boundaries**; trust internal callers.
- **Don't change behavior, rename public APIs, or refactor unrelated code**
  unless that is the explicit task.

## Where to read more

- [lynx_dashboard/CLAUDE.md](lynx_dashboard/CLAUDE.md) — the application
  package: its logical modules, public interface, and local conventions.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — dataflow, mode inheritance,
  executable resolution.
- [docs/API.md](docs/API.md) — the stable `lynx_dashboard.api` surface.
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) — how to add a launchable, a
  recommender step, or a launch mode.
</content>
</invoke>

<!-- LYNX-EP-NOTE:BEGIN -->

## Entry-point card — keep it current

This project carries `index.ep.md` (and `index.ep.html`), the standard card
that answers what this is, where to look first, and how to run it. Every
project in `~/devel/` has one in the same shape, so jumping between them
does not mean re-learning where to look.

**When work here changes any of the following, refresh the card:**

- what the project is or does (title, one-line purpose, description)
- the file someone should open first
- the command that starts it
- the top-level layout or where the documentation lives

Refresh it with:

```bash
python3 ~/devel/lynx_factory/web/tools/gen_ep_index.py --only <this-project>
```

That regenerates from this repo's own README/CLAUDE.md plus the Lynx Factory
ledger — it does not invent anything, so fixing the card usually means fixing
the README first. The README's ownership footer is refreshed by the same
command.

To hand-write a card and stop it being regenerated, set `ep_locked: true` in
its front matter.

<!-- LYNX-EP-NOTE:END -->
