---
ep_version: 1
project: lynx-dashboard
title: Lynx Dashboard
status: ACTIVE
last_touched: 2026-09-08
last_touched_text: 8 September 2026
section: sub
category: investments
generated: 2026-09-08
ep_locked: false   # set true and this file is never regenerated
---

# Lynx Dashboard

> Dashboard / launcher for all sub-projects + agents

🟢 **ACTIVE** · last touched **8 September 2026** (last commit to project files)

---

## What this is

Unified launcher and command center for the **Lince Investor Suite**.

`lynx-dashboard` is the single entry point you run when you don't know yet which app or agent you need. It showcases every app and every sector-specialized agent, suggests the right agent for any company you type in, and launches any of them in the same interface mode you used to enter the dashboard.

Plus 11 sector-specialized agents covering the entire GICS universe: energy, financials, information technology, healthcare, basic materials, consumer discretionary, consumer staples, industrials, utilities, communication services, and real estate.

Every UI mode opens with a branded splash — ~1.8 s in the GUI, ~1.5 s in the TUI, ~1.4 s in the console. The splash is skippable: click (or press any key) in the GUI, any key in the TUI. Disable it globally with `--no-splash` or `LYNX_NO_SPLASH=1`. CI environments (`CI=1`) get no splash by default.

The dashboard remembers your last 12 recommendations. They show up as clickable pills in the Recommend dialog next to the "Try:" sample pills. Stored at `$XDG_CONFIG_HOME/lynx-dashboard/history.json` (or `~/.config/lynx-dashboard/history.json`).

Wrap it in `jq` to cherry-pick fields:

Stable, versioned public API — see [docs/API.md](docs/API.md).

rec = api.recommend("Oroco") if rec.has_match: req = api.make_launch_request(rec.primary, ticker=rec.profile.ticker, mode="tui") print("Will run:", api.format_command(api.build_command(req))) ```

Bypasses the stdout/stderr silencers around yfinance and the core resolver so you can see what the resolution pipeline is actually doing.

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for known rough edges.

The dashboard runs in four interface modes, mirroring the rest of the suite:

- **Console** (default) — prints a pretty catalog and exits.
- **Interactive** (`-i`) — REPL with `launch`, `recommend`, `list`, `about`, `help`.
- **TUI** (`-tui`) — Textual dashboard with tabs, tables, keybindings.
- **GUI** (`-x`) — Tkinter window with category frames and a File menu.

In each mode, launching a child uses the same mode by default. From TUI, Textual's `App.suspend()` releases the terminal so the child's TUI takes over; when the child exits you land back in the dashboard. From GUI, the child opens in its own window and the dashboard stays interactive.

Type a ticker, ISIN, or company name and the dashboard:

1. Fetches the Yahoo Finance profile (`pip install lynx-dashboard[recommender]`).
2. Feeds it to `lynx_investor_core.sector_registry.suggest_agent`, which
   owns the single-source-of-truth GICS → agent mapping.
3. Shows a top pick plus any runner-ups.

An offline hint table ships with the package so the recommender still works without a network for common large-caps. Pass `--offline` to skip yfinance entirely.

See `docs/KEYBINDINGS.md` for the full list.

The dashboard is deliberately thin. It never reaches into another app's internals — it shells out to each target the way a human would. The single source of truth for the GICS → agent mapping lives in `lynx_investor_core.sector_registry`; `lynx_dashboard.recommender` is a small wrapper that fetches a profile and asks core which agent matches.

Key modules:

## Start here

- [`README.md`](README.md) — what the project is, in its own words
- [`CLAUDE.md`](CLAUDE.md) — working agreement for a session in this repo
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — module map and how the pieces fit
- [`ROADMAP.md`](ROADMAP.md) — where this is heading

## Run it

```bash
cd ~/claude/lince-investor/lynx-dashboard
./run                                 # project runner
lynx-dashboard                        # console entry point
python3 -m lynx_dashboard             # runnable package
```

## The rest of it

**Directories**

- `data/` — 2 entries
- `docs/` — 6 entries
- `img/` — 7 entries
- `lynx_dashboard/` — 18 entries
- `lynx_dashboard.egg-info/` — 6 entries
- `tests/` — 14 entries

**Other documentation**

- [`CHANGELOG.md`](CHANGELOG.md)
- [`DESIGN.md`](DESIGN.md)

**`docs/`** holds 6 files.

**Build / config**: `Dockerfile`, `pyproject.toml`

---

## Ownership

<img src="https://www.cortex-university.com/static/brand/lince-logo.png" alt="Lince" width="96" height="96" align="left" style="margin-right:16px" />

**Lynx Dashboard is proudly part of Lince.**

| Company ID | Headquarters |
|---|---|
| 3015071-2 | Helsinki, Finland |

Part of the LINCE company · © All rights reserved


<sub>Standard entry-point card (`index.ep.md`, format v1) — generated 2026-09-08 by Lynx Factory. Regenerating overwrites this file unless `ep_locked: true`.</sub>
