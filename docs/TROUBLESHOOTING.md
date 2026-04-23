# Troubleshooting

Known rough edges and how to work around them.

## The dashboard can't find a terminal to open TUI / interactive children

Seen in the GUI when "Launch children in TUI" is selected but clicking a
Launch card shows *"Couldn't open a terminal window"*.

The dashboard probes: `x-terminal-emulator`, `gnome-terminal`, `konsole`,
`xfce4-terminal`, `alacritty`, `kitty`, `wezterm`, `foot`, `xterm`, `urxvt`
— in that order. Install one of them, or force a specific one:

```bash
export LYNX_TERMINAL=alacritty
lynx-dashboard -x
```

The dialog also prints the equivalent command so you can copy-paste it into
whatever terminal you already have open.

## gnome-terminal opens a window that immediately vanishes

The dashboard wraps every cross-mode launch in a `sh -c '…; read'` so the
terminal stays open even if the child crashes. You should see either the
child's TUI or a `[lynx-dashboard] command exited with code N` line.

If you see neither, the failure is happening inside `gnome-terminal-server`
(a DBus / Wayland handshake glitch). Try another terminal:
```bash
LYNX_TERMINAL=xterm lynx-dashboard -x
```

## "NO MATCH" for an obvious company

Most often: Yahoo Finance doesn't have data for that exact symbol. Try:

1. The company name instead of the ticker (`Oroco` vs `OCO.V`).
2. The ISIN (e.g. `US0378331005` for Apple).
3. A different exchange suffix — `.TO` (TSX), `.V` (TSXV), `.L` (LSE),
   `.DE` (XETRA), `.PA` (Paris), `.AS` (Amsterdam), `.MI` (Milan),
   `.SW` (Switzerland), `.HK` (Hong Kong), `.T` (Tokyo), `.AX` (Australia),
   `.NS` / `.BO` (India), `.MX` (Mexico), `.SA` (Brazil).

Known categorical gap: delisted / post-bankruptcy tickers (e.g. `MULN`) and
Canadian junior miners that never listed on a non-Canadian exchange often
have no Yahoo profile at all. These will remain "no match" until Yahoo
publishes data for them.

## Recommender suggested a different agent than I expected

The priority is `sector > industry > description`. If you think Yahoo's
sector classification is wrong, run:

```bash
LYNX_DEBUG=1 lynx-dashboard --recommend "<query>"
```

to see what sector / industry yfinance is reporting. The dashboard
faithfully maps those to the matching agent via
`lynx_investor_core.sector_registry.AGENT_REGISTRY`.

Example: Procter & Gamble's long description mentions "e-commerce channels",
which hits consumer-discretionary's description pattern, but its Yahoo
sector is "Consumer Defensive" → the dashboard correctly ranks
consumer-staples first based on sector priority.

## Splash screen is annoying / slow

Three ways to skip it:

- One-off: `lynx-dashboard --no-splash`
- Permanent: `export LYNX_NO_SPLASH=1` in your shell rc.
- Click (GUI) or any key (TUI) to dismiss while it's showing.

CI environments with `CI=1` get no splash by default.

## Launch button says "Dry run" instead of actually launching

You passed `--dry-run` somewhere. It prints what would have been executed
and exits without spawning anything. Remove the flag.

## "Mode not supported" dialog for an app/agent

Currently every app and agent supports every mode, so this shouldn't
happen. If it does, it means the `Launchable.modes` frozenset was changed
for that entry without updating the UI. Open `registry.py`.

## `--debug` / `LYNX_DEBUG=1` doesn't show any extra output

The debug toggle disables the `_silence_stdio` wrapper around yfinance and
the core `resolve_identifier` function. If yfinance has nothing to say
(e.g. the direct-ticker path returns valid data immediately), there's
genuinely no extra output to show.

## Recent-queries pills don't appear in the Recommend dialog

The dashboard writes to `~/.config/lynx-dashboard/history.json`
(or `$XDG_CONFIG_HOME/lynx-dashboard/history.json`). To reset:

```bash
lynx-dashboard --clear-history
```

Or point the store somewhere else for a session:

```bash
LYNX_DASHBOARD_HISTORY=/tmp/my-history.json lynx-dashboard -x
```

## Textual TUI fails to start

`textual >= 0.60` is required. `pip install -r requirements.txt --upgrade`.

## Can't close a modal with Esc

Every modal honors `Escape`, but if focus is inside an Entry widget (GUI)
Tk sometimes swallows the Escape. Click outside the input first, or use
the explicit `Close` button.
