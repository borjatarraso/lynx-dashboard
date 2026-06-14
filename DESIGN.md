# Design

The principles behind Lynx Dashboard and the rationale for each. These are
descriptive — they record decisions already made in the code, not aspirations.

## 1. Launcher, not analyzer

The dashboard catalogs and launches; it does not analyze companies itself.
Every analytical answer comes from a child app/agent run as its own process.

*Why:* keeps the dashboard small and stateless, and guarantees the answer a
user sees is identical to running the target app directly — there is no second
implementation to drift.

## 2. Single source of truth for the catalog

The GICS → agent mapping lives in
`lynx_investor_core.sector_registry.AGENT_REGISTRY`. The local `registry.py`
carries only display metadata (name, tagline, keybinding, color) and links
each agent back by `registry_name`. Consistency tests enforce the 1:1 mapping
and unique keybindings.

*Why:* the dashboard can never disagree with the agents about which sector
belongs where, because both read the same registry.

## 3. Stateless child processes, no IPC

Each launched target is an independent process with its own `data/`, argparse,
and cache. The dashboard keeps no Python-level handle on it.

*Why:* process isolation is simpler and safer than an IPC/attach layer, and it
matches how users run the apps standalone. The cost — no "attach to running
session" — is accepted deliberately.

## 4. Mode inheritance

A child is launched in a way that matches the dashboard's current mode:
terminal-attached for console/interactive, `App.suspend()` for TUI,
detached for GUI. The mode is overridable at runtime.

*Why:* the user's interface expectation should carry through the launch
without an extra prompt.

## 5. Three-stage executable resolution

`launcher.resolve_executable` tries `shutil.which`, then `python -m <package>`,
then a sibling-directory script.

*Why:* the same code works for an installed CLI, an importable-but-unscripted
package, and a monorepo checkout that has not been `pip install -e`'d yet.

## 6. A stable, version-locked public API

`api.py` is a thin façade (`__api_version__ = "1.0"`) over the internal layers.
Everything in `api.__all__` and the `*_as_dict` JSON keys is contract: adding
is a minor bump, renaming/removing is a major bump, and `tests/test_api.py`
locks every name.

*Why:* third-party integrations import `lynx_dashboard.api`, so the internal
files can be reorganized freely as long as the façade holds — which is also why
the logical modules are kept inside one package rather than split into separate
top-level packages.

## 7. Resilient recommender, graceful offline

The recommender is a linear, cached cascade (ticker → core resolver → Yahoo
search → name fallback → suffix strip → offline hints) that ranks agents by
sector (100) over industry (50) over description (10). `--offline` skips
yfinance entirely; a missing optional dependency degrades, it does not crash.

*Why:* a launcher must stay usable without a network and must not let a fuzzy
description match outrank a real sector match.

## 8. Hermetic tests

Tests never touch the network and never spawn real subprocesses (`dry_run=True`);
history is redirected with `LYNX_DASHBOARD_HISTORY`. Every feature carries at
least one regression test.

*Why:* the suite must be fast, deterministic, and safe to run anywhere — CI
included.
</content>
