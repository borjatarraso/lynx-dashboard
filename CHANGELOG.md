# Changelog

## 3.1 — 2026-04-23

**New**

- `lynx_dashboard.api` — stable versioned public API (`__api_version__ = "1.0"`)
  exposing catalog, recommender, launcher, and JSON-safe view helpers for
  third-party integrations. See `docs/API.md`.
- `--json` flag for `--list`, `--info`, and `--recommend` — machine-readable
  output for scripting.
- Persistent recent-queries history at `$XDG_CONFIG_HOME/lynx-dashboard/`,
  surfaced as clickable pills in the GUI Recommend dialog. `--clear-history`
  wipes it. `LYNX_DASHBOARD_HISTORY` overrides the path for tests and
  session-scoped use.
- `--debug` / `--verbose` flag and `LYNX_DEBUG=1` env var disable the
  stdout/stderr silencers around yfinance and the core resolver, so you can
  see what the resolution pipeline is actually doing.
- "Copy command" button in Info dialogs — puts the exact shell command on
  the clipboard for sharing or running elsewhere.
- Recommender resolution pipeline extended: name-based fallback (when a
  symbol returns a name but no sector) and base-symbol fallback (strip
  `.MI` etc. and search alternates). Guarded against junior-market
  suffixes (`.V`, `.CN`) to avoid cross-exchange misclassification.
- `docs/API.md`, `docs/DEVELOPMENT.md`, `docs/TROUBLESHOOTING.md`.

**Bug fixes**

- Subprocess pipe leak in `_spawn_in_terminal`: stdout / stderr FDs are
  now drained via `communicate()` before trying the next terminal
  candidate.
- `_silence_stdio` uses `ExitStack` so the `/dev/null` file handle is
  always closed even on exception. Respects `LYNX_DEBUG=1` to become a
  no-op for diagnostics.
- Splash `_ease_out_cubic` / `_status_at` now clamp NaN and ±Inf to
  [0, 1] instead of crashing the animation.
- GUI `_flash_status` tracks its pending `after()` id and cancels it on
  quit / re-flash so stale callbacks don't fire against a destroyed
  interpreter.
- `_refresh_status` guards against `tk.TclError` when the window is
  already being torn down.

**Tests**

- 116 tests passing (up from 76). New coverage: API surface, JSON
  output, history persistence, CLI debug flag, NaN/Inf easing, clear-
  history flow, silence-stdio env-var behavior.

## 3.0 — 2026-04-23

Initial release.

- Unified launcher for every app and agent in the Lince Investor Suite.
- Four interface modes: console, interactive REPL, Textual TUI, Tkinter GUI.
- **Animated splash screen** across all modes with fade-in/out, ease-out-
  cubic progress bar, cycling status messages, and click/keypress skip.
  `--no-splash` and `LYNX_NO_SPLASH=1` disable it.
- **Info dialogs** — every app and every agent has an ⓘ Info button in the
  GUI, an `i` keybinding in the TUI, an `info <name>` command in the REPL,
  and a `--info NAME` CLI flag. Shows details, data sources, and (for
  agents) what specializes them.
- **Recommend dialog** with clickable example-ticker pills for every
  sector, reachable from a prominent button beneath the hero, Ctrl+R in
  the GUI, `r` in the TUI, and `recommend` in the REPL.
- **PNG logo** shipped in `img/` and rendered in the GUI hero + About
  dialog, matching the rest of the suite. ASCII fallback on pre-8.6 Tk.
- **Cross-mode launch** from the GUI to TUI/console/interactive opens a
  new terminal emulator (gnome-terminal, konsole, xterm, alacritty,
  kitty, wezterm, foot, urxvt; override via `LYNX_TERMINAL`). Child is
  wrapped in a shell that keeps the terminal open so errors are visible.
- **Unified 3×3 grid** aligns the three core-app buttons with the three
  columns of sector-agent buttons; columns use `uniform="launch-col"`
  so widths match across sections.
- **Readable hover** — ttk `style.map` locks the `active`/`pressed`
  states so buttons never go white-on-white.
- **Centered modals** — GUI uses explicit geometry centering; TUI uses
  `align: center middle`.
- Company → agent recommender powered by
  `lynx_investor_core.sector_registry`. yfinance optional; offline hint
  table covers large caps when no network is available.
- Mode-inherited launching: TUI suspends the Textual app while the child
  takes over the terminal; GUI detaches GUI children, spawns TUI/console
  children in a new terminal window with a keep-open wrapper.
- Keybindings share vocabulary with the rest of the suite (`a` = about,
  `q` = quit, PgUp/PgDn, etc.).
- Easter egg (ASCII art + market quips + konami sequence in TUI,
  hidden "lynx" keystroke trigger in the GUI — not advertised in menus).
- Pass-through of production (`-p`) / testing (`-t`) run modes to launched
  children.
- `--recommend`, `--info`, `--launch`, and `--list` are mutually
  exclusive at the CLI level so combinations don't silently drop flags.

### Bug fixes
- GUI shortcut keys (`f`, `c`, `p`, `1`-`9`, `0`, `-`) no longer hijack
  typing when focus is in an Entry / Text / Combobox widget.
- Launcher sibling-script resolution finds the correct agent script
  (`lynx-investor/lynx-investor-<sector>/lynx-investor-<sector>.py`)
  when the installed CLI isn't on `$PATH`.
- Offline recommender no longer leaks free-text into the profile's
  ticker slot; permits real `BRK-B` / `OCO.V` style symbols.
