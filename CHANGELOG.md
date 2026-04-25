# Changelog

## 6.0.0 — 2026-04-26

**Major release synchronising the entire Lince Investor Suite.**

### What's new across the Suite

- **lynx-fund** — brand-new mutual / index fund analysis tool, rejecting
  ETFs and stocks at the resolver level. Surfaces share classes, loads,
  12b-1 fees, manager tenure, persistence, capital-gains tax drag, and
  20-rule passive-investor checklist with tailored tips.
- **lynx-compare-fund** — head-to-head comparison for two mutual / index
  funds. Adds a Boglehead-style Passive-Investor Verdict, plus warnings
  for active-vs-passive, UCITS, soft- / hard-close, and distribution-
  policy mismatches.
- **lynx-theme** — visual theme editor for the entire Suite (GUI + TUI
  only). Edit colours, fonts, alignment, bold / italic / underline /
  blink / marquee for 15 styled areas with live preview. Three built-in
  read-only reference themes (`lynx-mocha`, `lynx-latte`,
  `lynx-high-contrast`). Sets the default theme persisted to
  `$XDG_CONFIG_HOME/lynx-theme/default.json`.
- **i18n** — every Suite CLI now accepts `--language=us|es|it|de|fr|fa`
  and persists the user's choice to `$XDG_CONFIG_HOME/lynx/language.json`.
  GUI apps mount a small bottom-right language toggle (left-click
  cycles, right-click opens a chooser); TUI apps bind `g` to cycle.
  Honours `LYNX_LANG` for ad-hoc shells.
- **Author signature footer** — every txt / html / pdf export now ends
  with the Suite-wide author block: *Borja Tarraso
  &lt;borja.tarraso@member.fsf.org&gt;*. Provided by the new
  `lynx_investor_core.author_footer` module.

### Dashboard

- Two new APP launchables (Lynx Fund, Lynx Compare Fund, Lynx Theme),
  raising the catalogue to **8 apps + 11 sector agents = 19
  launchables**.
- Per-app launch dialect (`run_mode_dialect`, `ui_mode_flags`,
  `accepts_identifier`) so the launcher emits argv each app
  understands; lynx-theme + lynx-portfolio launch correctly from every
  mode.
- `--recommend` now rejects empty queries instead of silently passing.

### Bug fixes

- `__main__.py` of every fund / compare-fund / etf / compare-etf entry
  point now propagates `run_cli`'s return code so non-zero exits are
  visible to shell scripts and CI pipelines.
- Stale-install hygiene: pyproject editable installs now overwrite
  cached site-packages copies cleanly.
- Cosmetic clean-up: remaining "ETF" labels in fund / compare-fund
  GUI / TUI / interactive prompts → "Fund".
- Validation: empty positional ticker, missing second comparison
  ticker, and `--recommend ""` now exit non-zero with a clear message.


## 5.5.2 — 2026-04-24

**New**

- **Domain icons for every app and agent** — a 40×40 flat-design PNG is
  rendered per-entry (candlestick chart for Fundamental, balance scale
  for Compare, briefcase for Portfolio, pie chart for ETF, twin pies +
  beam for Compare ETF, lightning bolt for Energy, Greek-temple bank
  for Financials, microchip for IT, medical cross for Healthcare,
  faceted gemstone for Basic Materials, shopping bag for Consumer
  Discretionary, shopping cart for Staples, gear for Industrials, water
  drop for Utilities, signal tower for Communication Services, house
  with chimney for Real Estate). Rendered at 4× resolution and
  downsampled with a Lanczos filter so strokes stay crisp. Icons are
  generated on first GUI launch via `lynx_dashboard.icons` (Pillow
  optional) and cached under `img/icons/`. Each icon sits in the card's
  top-right corner (rowspan=2 next to the name + tagline) in its
  Launchable's house colour, so the card height stays the same as the
  pre-icon version — Launch/Info buttons keep their original compact
  heights.
- **Recommend button moved into the hero row.** Previously a
  full-width "Recommend an Agent for a Company" bar lived on its own
  line below the hero; it now sits compactly between the Lynx
  Dashboard titles and the Quit button, at its natural width. Trimmed
  card paddings (title/tagline/button vertical pads) and the grid
  spacing so the dashboard fits the default 1200×900 window with no
  vertical scrollbar. The scrollbar still appears on demand when the
  window is smaller than the content.
- **TUI now shows every app and every agent with a domain glyph** in a
  new "Icon" column (📊 ⚖ 💼 🧺 ⚖ ⚡ 🏦 💻 ➕ ⛏ 🛍 🛒 ⚙ 💧 📡 🏠).
- **TUI launch keybindings extended** — `e` launches Lynx ETF and
  `Shift+E` launches Lynx Compare ETF. Previously those two new core
  apps could only be reached through the row cursor.
- **TUI splash screen centred.** Previously rendered top-left due to
  `content-align` not positioning a `Vertical` container; now wraps
  the splash box in an outer container with `align: center middle` and
  switches the inner labels to `text-align: center`.

**New core apps (carried over from the v5.5.2 release cut)**

- **Two new core apps** onboarded into the registry:
  - **Lynx ETF** (`lynx-etf`, keybinding `e`, cyan) — ETF-specialist analysis.
    Rejects stocks, mutual funds, and index funds at the resolver level. Covers
    expense ratio, AUM, top holdings, sector/geography allocation, performance
    windows (1M–10Y + CAGR), Sharpe/Sortino, volatility, max drawdown, and
    tracking error. Produces a 0-100 scored verdict.
  - **Lynx Compare ETF** (`lynx-compare-etf`, keybinding `E`, magenta) —
    head-to-head ETF comparison with per-section winners across Costs, Income,
    Size & Liquidity, Performance, Diversification, Risk, and Tracking. Warns
    on asset-class, domicile, replication, or size-tier mismatches. Computes
    approximate holdings overlap.
- `--list --json` now includes both new apps (total 16 launchables).
- Ships full four-mode support (console / interactive / TUI / GUI) for both
  new tools, plus a REST API server for `lynx-compare-etf`.

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
