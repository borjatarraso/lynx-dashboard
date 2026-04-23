# Development

How the pieces fit and how to change them safely.

## Layout

```
lynx-dashboard/
├── lynx_dashboard/               # package
│   ├── __init__.py               # version, about metadata
│   ├── __main__.py               # `python -m lynx_dashboard`
│   ├── api.py                    # stable public API (import-safe)
│   ├── cli.py                    # argparse, mode dispatch
│   ├── registry.py               # catalog of apps + agents
│   ├── recommender.py            # query → company profile → agent
│   ├── launcher.py               # argv construction + subprocess launch
│   ├── display.py                # Rich-based console renderers
│   ├── interactive.py            # REPL
│   ├── history.py                # persistent recent-queries store
│   ├── splash.py                 # animated splash (GUI + TUI + console)
│   ├── easter.py                 # hidden egg content
│   ├── tui/app.py                # Textual TUI dashboard
│   └── gui/app.py                # Tkinter GUI dashboard
├── img/                          # ASCII + PNG logos
├── docs/                         # this folder
├── tests/                        # pytest suite (116 tests)
├── lynx-dashboard.py             # thin script entry point
├── lynx-dashboard                # symlink for bare-name invocation
├── requirements.txt
└── pyproject.toml
```

## Running from source

```bash
cd lynx-dashboard
PYTHONPATH=.:../lynx-investor-core python lynx-dashboard.py --help
```

After `pip install -e .` the `lynx-dashboard` entry point is on `$PATH`.

## Running the tests

```bash
PYTHONPATH=.:../lynx-investor-core python -m pytest tests/ -q
```

Tests are hermetic: no network, no subprocesses are actually spawned
(everything goes through `dry_run=True`), and history is written to
temp directories via the `LYNX_DASHBOARD_HISTORY` env var override.
`LYNX_DEBUG=1` is explicitly scrubbed in tests that depend on the
default silencer behavior, so the CLI debug test can't cross-contaminate.

## Debugging

Set `LYNX_DEBUG=1` or pass `--debug`/`--verbose` to see what the
recommender's resolution pipeline is actually doing. yfinance and Rich
diagnostic output flow through to your terminal instead of being swallowed.

```bash
LYNX_DEBUG=1 lynx-dashboard --recommend "F3 Uranium" --offline
```

## Adding a launchable

1. Add an entry to `registry.APPS` or `registry.AGENTS`. All fields with
   sensible defaults: only `name`, `short_name`, `kind`, `command`,
   `package`, `tagline`, `description`, `category` are required.
2. Pick a unique `keybinding` — the registry's consistency test will fail
   if you collide with an existing key.
3. For agents, set `registry_name` to match an entry in
   `lynx_investor_core.sector_registry.AGENT_REGISTRY`. The consistency
   tests enforce 1:1 mapping.
4. Fill in `details` (multi-paragraph), `data_sources` (tuple of strings),
   and — for agents — `specialization`. The Info dialog / `--info` CLI /
   TUI Info modal all read these directly.

## Adding a resolution step to the recommender

`recommender._fetch_yf_profile_uncached` is a linear pipeline. Each step:

1. Yields zero or more candidate symbols.
2. Each candidate goes through `_try_symbol` which calls
   `_profile_for_symbol`.
3. `_profile_for_symbol` returns `None` if the Yahoo entry has no
   sector / industry / description signal.
4. First candidate with a usable profile wins.

To add a step (say, a custom-curated ISIN → symbol mapping):

```python
# In _fetch_yf_profile_uncached, between existing steps:
if is_isin(query):
    mapped = ISIN_OVERRIDES.get(query.upper())
    if mapped:
        p = _try_symbol(mapped)
        if p is not None:
            return p
```

## Adding a launch mode

1. Add the flag to `launcher._MODE_FLAG` (or document `None` if no flag).
2. Add the mode name to `registry._ALL_MODES` if every launchable supports
   it; otherwise add it to each `Launchable.modes` individually.
3. Teach the mode runners in `cli._run_*` how to dispatch to it.
4. Teach the GUI / TUI / REPL UI to surface the mode.

## Updating the public API

- Anything exported from `lynx_dashboard.api.__all__` is load-bearing.
- Adding a new export is a minor-version bump.
- Renaming or removing an export is a major-version bump.
- `launchable_as_dict` / `recommendation_as_dict` keys are part of the
  JSON-output contract — don't change without bumping major.

Tests in `tests/test_api.py` lock every stable name in place. If you need
to change one, update the test in the same commit so the intent is
reviewable.

## Style notes

- Prefer editing existing files over creating new ones.
- Comments explain *why*, not *what*. Identifier names cover the *what*.
- No backwards-compatibility shims for unused or deleted code.
- Error handling only at system boundaries; trust internal callers.
- Every new feature gets at least one regression test.
