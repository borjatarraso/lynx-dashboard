"""Stable public API for the Lynx Dashboard.

Importing from this module gives you everything you need to integrate the
dashboard's catalog, recommender, and launcher into your own tooling —
without reaching into internal modules that may move between minor versions.

Quick tour
----------

>>> from lynx_dashboard import api
>>> api.__api_version__
'1.0'

>>> # Catalog
>>> [a.command for a in api.APPS]
['lynx-fundamental', 'lynx-compare', 'lynx-portfolio']
>>> len(api.AGENTS)
11
>>> api.find("fundamental").command
'lynx-fundamental'

>>> # Recommender (network optional)
>>> rec = api.recommend("XOM", offline=True)
>>> rec.has_match and rec.primary.registry_name
'lynx-investor-energy'

>>> # Launcher (dry run)
>>> req = api.make_launch_request(api.find("energy"), ticker="XOM", mode="console")
>>> cmd = api.build_command(req)
>>> "-p" in cmd and "XOM" in cmd
True

>>> # JSON-serializable views for scripting / integrations
>>> catalog = api.catalog_as_dicts()
>>> "lynx-fundamental" in {x["command"] for x in catalog}
True

Guarantees
----------

Anything exported from ``lynx_dashboard.api`` is stable within the major
version advertised by ``__api_version__``. Additions are backward-compatible;
breaking changes bump the major. Use this module — not internal imports —
if you want the dashboard's logic in your own scripts or apps.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from lynx_dashboard import (
    APP_NAME,
    APP_SHORT_NAME,
    APP_TAGLINE,
    DESCRIPTION,
    LICENSE_NAME,
    LICENSE_TEXT,
    PACKAGE_NAME,
    PROG_NAME,
    SUITE_LABEL,
    SUITE_NAME,
    SUITE_VERSION,
    __version__,
    get_about_text,
    get_logo_ascii,
)
from lynx_dashboard.launcher import (
    LaunchRequest,
    LaunchResult,
    build_command,
    format_command,
    launch_blocking,
    launch_detached,
    mode_to_flag,
    resolve_executable,
)
from lynx_dashboard.recommender import (
    CompanyProfile,
    Recommendation,
    recommend_for_profile,
    recommend_for_query,
)
from lynx_dashboard.registry import (
    AGENTS,
    ALL_LAUNCHABLES,
    APPS,
    Launchable,
    LaunchableKind,
    agents_for_mode,
    apps_for_mode,
    by_keybinding,
    by_name,
    by_registry_name,
)


__api_version__ = "1.0"

__all__ = [
    # Metadata
    "__api_version__",
    "__version__",
    "APP_NAME",
    "APP_SHORT_NAME",
    "APP_TAGLINE",
    "DESCRIPTION",
    "LICENSE_NAME",
    "LICENSE_TEXT",
    "PACKAGE_NAME",
    "PROG_NAME",
    "SUITE_LABEL",
    "SUITE_NAME",
    "SUITE_VERSION",
    "get_about_text",
    "get_logo_ascii",
    # Catalog
    "ALL_LAUNCHABLES",
    "APPS",
    "AGENTS",
    "Launchable",
    "LaunchableKind",
    "agents_for_mode",
    "apps_for_mode",
    "by_keybinding",
    "by_name",
    "by_registry_name",
    "find",
    # Recommender
    "CompanyProfile",
    "Recommendation",
    "recommend_for_profile",
    "recommend_for_query",
    "recommend",
    # Launcher
    "LaunchRequest",
    "LaunchResult",
    "build_command",
    "format_command",
    "launch_blocking",
    "launch_detached",
    "make_launch_request",
    "mode_to_flag",
    "resolve_executable",
    # JSON-serializable helpers
    "launchable_as_dict",
    "catalog_as_dicts",
    "recommendation_as_dict",
]


# ---------------------------------------------------------------------------
# Convenience shortcuts
# ---------------------------------------------------------------------------

def find(query: str) -> Optional[Launchable]:
    """Look up a launchable by name, short name, command, package, or key.

    Thin alias for :func:`lynx_dashboard.registry.by_name` that reads
    more naturally in calling code.

    >>> find("energy").command
    'lynx-energy'
    >>> find("1").name
    'Energy'
    """
    return by_name(query)


def recommend(
    query: str,
    *,
    offline: bool = False,
) -> Recommendation:
    """Recommend agents for a company *query* (ticker / ISIN / name).

    ``offline=True`` skips network calls (tests, airplane-mode demos).

    >>> rec = recommend("AAPL", offline=True)
    >>> rec.primary.registry_name
    'lynx-investor-information-technology'
    """
    return recommend_for_query(query, use_network=not offline)


def make_launch_request(
    target: Launchable,
    *,
    mode: str = "console",
    ticker: Optional[str] = None,
    run_mode: str = "production",
    refresh: bool = False,
    extra_args: Iterable[str] = (),
) -> LaunchRequest:
    """Build a :class:`LaunchRequest` with keyword defaults.

    Saves callers from having to remember the positional order.

    >>> req = make_launch_request(find("fundamental"), mode="tui", ticker="AAPL")
    >>> req.ticker, req.mode
    ('AAPL', 'tui')
    """
    return LaunchRequest(
        target=target,
        mode=mode,
        ticker=ticker,
        run_mode=run_mode,
        refresh=refresh,
        extra_args=tuple(extra_args),
    )


# ---------------------------------------------------------------------------
# JSON-serializable views
# ---------------------------------------------------------------------------

def launchable_as_dict(item: Launchable) -> Dict[str, Any]:
    """JSON-safe dict view of a :class:`Launchable`.

    Keys are stable within the major API version.
    """
    return {
        "name": item.name,
        "short_name": item.short_name,
        "kind": item.kind,
        "command": item.command,
        "package": item.package,
        "tagline": item.tagline,
        "description": item.description,
        "category": item.category,
        "modes": sorted(item.modes),
        "keybinding": item.keybinding,
        "registry_name": item.registry_name,
        "example_tickers": list(item.example_tickers),
        "color": item.color,
        "details": item.details,
        "data_sources": list(item.data_sources),
        "specialization": item.specialization,
    }


def catalog_as_dicts() -> List[Dict[str, Any]]:
    """Every launchable in registry order, as JSON-safe dicts."""
    return [launchable_as_dict(item) for item in ALL_LAUNCHABLES]


def recommendation_as_dict(rec: Recommendation) -> Dict[str, Any]:
    """JSON-safe dict view of a :class:`Recommendation`."""
    primary = rec.primary
    return {
        "query": rec.query,
        "profile": {
            "ticker": rec.profile.ticker,
            "name": rec.profile.name,
            "sector": rec.profile.sector,
            "industry": rec.profile.industry,
            "description": rec.profile.description,
            "source": rec.profile.source,
        },
        "primary": launchable_as_dict(primary) if primary is not None else None,
        "alternates": [launchable_as_dict(alt) for alt in rec.alternates],
        "reason": rec.reason,
        "has_match": rec.has_match,
    }
