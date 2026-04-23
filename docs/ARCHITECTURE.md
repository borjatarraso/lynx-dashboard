# Architecture

The dashboard is a *launcher*, not an analyzer. It deliberately owns very
little state — nearly everything it knows comes from
`lynx_investor_core` and from each target app's own CLI.

```
                    ┌────────────────────────────────────┐
                    │  lynx_dashboard.cli (argparse)     │
                    └───────┬───────────────────┬────────┘
                            │                   │
              ┌─────────────▼──┐          ┌─────▼────────────┐
              │ UI-mode runner │          │ direct operations│
              │  • console     │          │  • --recommend   │
              │  • interactive │          │  • --launch      │
              │  • tui         │          │  • --list        │
              │  • gui         │          │  • --about       │
              └──────┬─────────┘          └─────┬────────────┘
                     │                          │
                     ▼                          ▼
              ┌──────────────┐          ┌──────────────────┐
              │ registry.py  │◄─────────┤ recommender.py   │
              │ (all apps/   │          │ (yfinance +      │
              │  agents,     │          │  core.sector_    │
              │  metadata)   │          │  registry)       │
              └──────┬───────┘          └──────────────────┘
                     │
                     ▼
              ┌──────────────┐
              │ launcher.py  │───► subprocess.run(...)
              │ (build argv, │        │
              │  suspend TUI,│        ▼
              │  detach GUI) │   lynx-fundamental / lynx-compare / ...
              └──────────────┘   lynx-energy / lynx-finance / ...
```

## Single source of truth

The GICS → agent mapping lives in
`lynx_investor_core.sector_registry.AGENT_REGISTRY`. The dashboard's
`registry.py` carries only display metadata (name, tagline, keybinding,
color) and links each agent back to its registry entry by name. This means
the dashboard never disagrees with the agents about which sector belongs
where: both read the same `AGENT_REGISTRY`.

## Mode inheritance

| Dashboard mode | How a child is launched                                     |
|----------------|-------------------------------------------------------------|
| console        | `subprocess.run` attached to the terminal                   |
| interactive    | `subprocess.run` attached to the terminal                   |
| tui            | `App.suspend()` then `subprocess.run`; screen restores on return |
| gui            | `launch_detached` so the child runs in its own window       |

The launch mode can be overridden from the dashboard at runtime (`m` cycles
it in TUI; the GUI exposes radio buttons under `View`).

## Executable resolution

`launcher.resolve_executable` tries three paths, in order:

1. `shutil.which(command)` — the installed CLI.
2. `python -m <package>` — when the package imports but no CLI script is on PATH.
3. `python <sibling-dir>/<command>.py` — for a working copy of the suite
   checked out next to the dashboard.

The sibling-dir fallback is what makes the dashboard work inside this
monorepo even before `pip install -e` has been run on each sub-package.

## No shared runtime state

Each child is its own process with its own `data/` and `data_test/`
directories, its own argparse, its own cache. The dashboard does not
maintain a Python-level handle on any running child, which is why there
is no "attach to running session" feature and no IPC layer.
