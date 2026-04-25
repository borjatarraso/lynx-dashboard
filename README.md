# Lynx Dashboard

Unified launcher and command center for the **Lince Investor Suite**.

`lynx-dashboard` is the single entry point you run when you don't know yet
which app or agent you need. It showcases every app and every
sector-specialized agent, suggests the right agent for any company you type
in, and launches any of them in the same interface mode you used to enter
the dashboard.

## What's inside

| Core app          | What it does                                        |
|-------------------|-----------------------------------------------------|
| `lynx-fundamental`| Full-stack value-investing analysis for one company |
| `lynx-compare`    | Side-by-side comparison of two companies            |
| `lynx-portfolio`  | Portfolio tracker with encrypted vault              |

Plus 11 sector-specialized agents covering the entire GICS universe:
energy, financials, information technology, healthcare, basic materials,
consumer discretionary, consumer staples, industrials, utilities,
communication services, and real estate.

## Quick start

```bash
# Default — print the whole catalog to the console
lynx-dashboard

# Interactive REPL dashboard
lynx-dashboard -i

# Textual TUI dashboard (recommended)
lynx-dashboard -tui

# Tkinter graphical dashboard
lynx-dashboard -x

# Ask "which agent should I use for XOM?"
lynx-dashboard --recommend XOM

# Show detailed info for an app or agent
lynx-dashboard --info fundamental
lynx-dashboard --info energy

# Jump directly into the right agent for XOM
lynx-dashboard --launch energy XOM -tui

# Machine-readable catalog
lynx-dashboard --list

# Skip the opening splash animation
lynx-dashboard -x --no-splash           # or: export LYNX_NO_SPLASH=1
```

## Splash

Every UI mode opens with a branded splash — ~1.8 s in the GUI, ~1.5 s in the
TUI, ~1.4 s in the console. The splash is skippable: click (or press any key)
in the GUI, any key in the TUI. Disable it globally with `--no-splash` or
`LYNX_NO_SPLASH=1`. CI environments (`CI=1`) get no splash by default.

## Recent queries

The dashboard remembers your last 12 recommendations. They show up as
clickable pills in the Recommend dialog next to the "Try:" sample pills.
Stored at `$XDG_CONFIG_HOME/lynx-dashboard/history.json` (or
`~/.config/lynx-dashboard/history.json`).

```bash
lynx-dashboard --clear-history          # wipe the store
LYNX_DASHBOARD_HISTORY=/tmp/hist.json lynx-dashboard -x   # session-scoped
```

## JSON output for scripting

```bash
lynx-dashboard --list --json              # catalog
lynx-dashboard --info energy --json       # single launchable
lynx-dashboard --recommend XOM --json     # recommendation
```

Wrap it in `jq` to cherry-pick fields:

```bash
lynx-dashboard --list --json | jq '.[] | select(.kind=="agent") | .command'
```

## Python API

Stable, versioned public API — see [docs/API.md](docs/API.md).

```python
from lynx_dashboard import api

rec = api.recommend("Oroco")
if rec.has_match:
    req = api.make_launch_request(rec.primary, ticker=rec.profile.ticker, mode="tui")
    print("Will run:", api.format_command(api.build_command(req)))
```

## Debugging

```bash
LYNX_DEBUG=1 lynx-dashboard --recommend "F3 Uranium"
# or
lynx-dashboard --debug --recommend "F3 Uranium"
```

Bypasses the stdout/stderr silencers around yfinance and the core resolver
so you can see what the resolution pipeline is actually doing.

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for known rough edges.

## Modes

The dashboard runs in four interface modes, mirroring the rest of the suite:

- **Console** (default) — prints a pretty catalog and exits.
- **Interactive** (`-i`) — REPL with `launch`, `recommend`, `list`, `about`, `help`.
- **TUI** (`-tui`) — Textual dashboard with tabs, tables, keybindings.
- **GUI** (`-x`) — Tkinter window with category frames and a File menu.

In each mode, launching a child uses the same mode by default. From TUI,
Textual's `App.suspend()` releases the terminal so the child's TUI takes
over; when the child exits you land back in the dashboard. From GUI, the
child opens in its own window and the dashboard stays interactive.

## Company → agent recommender

Type a ticker, ISIN, or company name and the dashboard:

1. Fetches the Yahoo Finance profile (`pip install lynx-dashboard[recommender]`).
2. Feeds it to `lynx_investor_core.sector_registry.suggest_agent`, which
   owns the single-source-of-truth GICS → agent mapping.
3. Shows a top pick plus any runner-ups.

An offline hint table ships with the package so the recommender still
works without a network for common large-caps. Pass `--offline` to skip
yfinance entirely.

## Keybindings

| Key                  | Action                                       |
|----------------------|----------------------------------------------|
| `f` / `c` / `p`      | Launch Fundamental / Compare / Portfolio     |
| `1` … `9` `0` `-`    | Launch a sector agent (number shown in UI)   |
| `r`                  | Recommend an agent for a company             |
| `a`                  | About dialog                                 |
| `?` / `h` / `F1`     | Keybindings cheat-sheet                      |
| `m`                  | Cycle launch mode (tui → interactive → gui → console) |
| `t`                  | Toggle run mode (production ↔ testing)       |
| `e`                  | Easter egg                                   |
| `PgUp` / `PgDn`      | Scroll long output                           |
| `Esc`                | Close modal / return to dashboard            |
| `q` / `Ctrl+Q`       | Quit                                         |

See `docs/KEYBINDINGS.md` for the full list.

## Architecture

The dashboard is deliberately thin. It never reaches into another app's
internals — it shells out to each target the way a human would. The single
source of truth for the GICS → agent mapping lives in
`lynx_investor_core.sector_registry`; `lynx_dashboard.recommender` is a
small wrapper that fetches a profile and asks core which agent matches.

Key modules:

- `registry.py` — catalog of all apps/agents with metadata.
- `recommender.py` — company → agent lookup (yfinance + offline fallback).
- `launcher.py` — subprocess dispatch with mode inheritance.
- `cli.py` — argparse entry point.
- `display.py` — Rich-based console renderers.
- `interactive.py` — REPL.
- `tui/app.py` — Textual TUI.
- `gui/app.py` — Tkinter GUI.

## License

BSD 3-Clause. See `LICENSE`.

---

## Author and signature

This project is part of the **Lince Investor Suite**, authored and signed by

> **Borja Tarraso** &lt;[borja.tarraso@member.fsf.org](mailto:borja.tarraso@member.fsf.org)&gt;
> Licensed under BSD-3-Clause.

Every report and export emitted by Suite tools includes this same
signature in its footer. The shipped logo PNGs additionally carry the
author's signature via steganography for provenance — please do not
replace or re-encode the logo files.
