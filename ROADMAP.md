# Roadmap

Status, the stability policy the project commits to today, and a few possible
directions. The "possible directions" are **not commitments** — they are seams
that already exist in the code and could be extended.

## Current status

- **Version 6.0.0**, classified `Development Status :: 5 - Production/Stable`
  in `pyproject.toml`.
- Four interface modes ship and work end-to-end: console, interactive REPL,
  Textual TUI, Tkinter GUI.
- The public API is at `__api_version__ = "1.0"`.
- Test suite is hermetic and green (see `tests/`).
- Recent work (per `CHANGELOG.md`) has focused on suite-wide theming and on
  translating the dashboard menus, hero, dialogs, and status bar.

## Stability policy (committed)

- `lynx_dashboard.api.__all__` and the `launchable_as_dict` /
  `recommendation_as_dict` JSON keys are contract. Adding an export is a
  minor-version bump; renaming or removing one is a major-version bump.
- `tests/test_api.py` locks every stable name; a contract change must update
  that test in the same commit so the intent is reviewable.
- The CLI flags and `--json` output shape documented in `README.md` and
  `docs/API.md` are part of the same contract.

## Possible directions (not committed)

Each item below extends machinery that already exists; none is promised.

- **Wider plugin coverage.** `plugin_loader.py` already bridges
  `lynx_investor_core.plugins` entry points into the catalog; more suite apps
  could be surfaced as discovered plugins rather than hard-coded entries.
- **Broader localization.** The registry's `display_*` helpers are already
  translation-aware with English fallback; additional locales can be added
  without touching call sites.
- **More recommender resolution steps.** `_fetch_yf_profile_uncached` is a
  linear cascade designed for insertion (see `docs/DEVELOPMENT.md`); custom
  ISIN/symbol overrides are a natural addition.
- **Additional launch modes.** Adding a mode is a documented four-step change
  (`launcher._MODE_FLAG`, `registry._ALL_MODES`, `cli._run_*`, and the
  frontends).

## Non-goals

These are deliberate boundaries, not gaps (see [DESIGN.md](DESIGN.md)):

- No in-process analysis — the dashboard launches the analyzers, it does not
  replace them.
- No "attach to a running child" / IPC layer — children are isolated
  processes by design.
</content>
