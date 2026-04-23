# Lynx Dashboard — Public API

Everything you need to integrate the dashboard's catalog, recommender, and
launcher into your own tooling.

```python
from lynx_dashboard import api
```

`api.__api_version__` advertises the stability contract (currently `"1.0"`).
Anything exported from this module is backward-compatible within a major
version. Additions bump the minor; renames / removals bump the major.

## At a glance

| Capability | Import | One-liner |
|---|---|---|
| Catalog browsing | `api.APPS`, `api.AGENTS` | `[a.command for a in api.APPS]` |
| Fuzzy lookup | `api.find(q)` | `api.find("energy").command → "lynx-energy"` |
| Company → agent | `api.recommend(q)` | `api.recommend("XOM").primary.registry_name` |
| Build launch argv | `api.make_launch_request`, `api.build_command` | see below |
| Run a child | `api.launch_blocking`, `api.launch_detached` | see below |
| JSON-safe views | `api.launchable_as_dict`, `api.catalog_as_dicts`, `api.recommendation_as_dict` | round-trip through `json` |
| About / branding | `api.get_about_text`, `api.get_logo_ascii` | — |

## Catalog

### `api.APPS: Tuple[Launchable, ...]`
The three core apps: `lynx-fundamental`, `lynx-compare`, `lynx-portfolio`.

### `api.AGENTS: Tuple[Launchable, ...]`
The 11 sector-specialized agents covering every GICS bucket.

### `api.ALL_LAUNCHABLES: Tuple[Launchable, ...]`
`APPS + AGENTS`.

### `api.find(query) -> Optional[Launchable]`
Lookup by name, short name, command, package, or keybinding.

```python
api.find("fundamental").command   # 'lynx-fundamental'
api.find("1").name                # 'Energy'
api.find("bogus") is None         # True
```

### `api.by_keybinding(key) -> Optional[Launchable]`
Lookup by the registered keyboard shortcut.

### `api.by_registry_name(name) -> Optional[Launchable]`
Lookup by the canonical name from `lynx_investor_core.sector_registry`.

### `Launchable` dataclass fields
```
name, short_name, kind, command, package,
tagline, description, category,
modes, keybinding, registry_name,
example_tickers, color,
details, data_sources, specialization,
```

All fields are hashable/frozen. `kind` is either `"app"` or `"agent"`.

## Recommender

### `api.recommend(query, *, offline=False) -> Recommendation`
Resolve *query* to a company profile and recommend one or more agents.

Resolution pipeline (each step runs until one produces a profile with usable
sector data):

1. Direct-ticker fast path (`yfinance.Ticker(query)`).
2. Core resolver (`lynx_investor_core.ticker.resolve_identifier`) — handles
   ISIN, name search, and 30+ exchange-suffix probes.
3. Yahoo symbol search for abbreviated queries (`F3`, `TCS`, etc.).
4. Name-based fallback (if the original symbol had a name but no sector,
   search for the name).
5. Base-symbol fallback (strip `.MI` etc. and try alternate listings — guarded
   against junior-market suffixes `.V`, `.CN`, `.NE`, `.NEO`, `.BO` so dead
   TSXV symbols don't get misclassified as unrelated US listings).
6. Offline hint table (hand-curated large-caps + description patterns) when
   no network or yfinance is missing.

Ranking within results prefers sector matches (score 100) > industry matches
(50) > description-pattern matches (10). Ties break on registry order.

```python
rec = api.recommend("Oroco")
if rec.has_match:
    print(rec.primary.name, "for", rec.profile.ticker)
```

### `Recommendation` fields
- `query: str` — what the caller passed in.
- `profile: CompanyProfile` — resolved ticker + sector + name + industry + description.
- `primary: Optional[Launchable]` — top-ranked agent.
- `alternates: List[Launchable]` — runner-ups in score order.
- `reason: str` — human-readable explanation.
- `has_match: bool` — `True` iff `primary is not None`.

## Launcher

### `api.make_launch_request(target, *, mode="console", ticker=None, run_mode="production", refresh=False, extra_args=())`

Builds a `LaunchRequest`. Modes: `console`, `interactive`, `tui`, `gui`, `search`.

### `api.build_command(request) -> Tuple[str, ...]`
Returns the argv the launcher will spawn. Pure function — does not touch the filesystem or network.

### `api.launch_blocking(request, *, dry_run=False) -> LaunchResult`
Spawns the child attached to the current stdin/stdout/stderr and blocks until
it exits. Use from CLI / interactive / console dashboards.

### `api.launch_detached(request, *, dry_run=False) -> LaunchResult`
Spawns the child in its own session with stdio redirected to `/dev/null`.
Use from GUI → GUI transitions so the dashboard keeps responding.

### `api.format_command(argv) -> str`
Shell-quoted display form of an argv tuple, suitable for copy-paste.

### `api.resolve_executable(target) -> List[str]`
Returns the argv prefix the launcher will use (installed CLI, `python -m`, or
sibling script).

## JSON-safe views

For scripting and integrations.

```python
import json
from lynx_dashboard import api

print(json.dumps(api.catalog_as_dicts(), indent=2))

rec = api.recommend("XOM", offline=True)
print(json.dumps(api.recommendation_as_dict(rec), indent=2))

print(json.dumps(api.launchable_as_dict(api.find("energy")), indent=2))
```

These are also reachable from the CLI:

```
lynx-dashboard --list --json
lynx-dashboard --recommend XOM --json
lynx-dashboard --info energy --json
```

## About / branding

```python
about = api.get_about_text()
logo  = api.get_logo_ascii()
```

`about` is the same dict the About dialog renders: name, version, author,
license, description, logo_ascii, etc.

## Example: wire the recommender into your own CLI

```python
#!/usr/bin/env python3
"""Classify every ticker in `holdings.txt` and emit an agent-assignment CSV."""
import csv, sys
from lynx_dashboard import api

with open("holdings.csv") as src, sys.stdout as out:
    writer = csv.writer(out)
    writer.writerow(["ticker", "sector", "agent", "command"])
    for ticker in src.read().splitlines():
        rec = api.recommend(ticker.strip(), offline=False)
        writer.writerow([
            ticker,
            rec.profile.sector or "",
            rec.primary.name if rec.primary else "",
            rec.primary.command if rec.primary else "",
        ])
```

## Example: discover, classify, launch — programmatically

```python
from lynx_dashboard import api

rec = api.recommend("F3 Uranium")
if rec.has_match:
    req = api.make_launch_request(
        rec.primary, mode="console", ticker=rec.profile.ticker,
    )
    print("Will run:", api.format_command(api.build_command(req)))
    # api.launch_blocking(req)   # actually execute
```

## Stability guarantees

| What's stable | What isn't |
|---|---|
| Names exported from `lynx_dashboard.api` | Anything in `lynx_dashboard.gui.*` / `lynx_dashboard.tui.*` |
| Dict keys returned by `*_as_dict` helpers | Console output formatting (Rich styling, panel titles) |
| CLI `--json` output shape | Non-JSON CLI output formatting |
| `CompanyProfile` / `Recommendation` / `Launchable` field names | `LaunchResult.message` wording |
| `__api_version__` semver discipline | — |

If a script only imports from `lynx_dashboard.api`, it will keep working as
long as the `__api_version__` major doesn't change.
