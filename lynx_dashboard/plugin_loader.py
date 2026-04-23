"""Bridge between :mod:`lynx_investor_core.plugins` and the dashboard registry.

The dashboard has always kept a rich hard-coded list of launchables in
:mod:`lynx_dashboard.registry`. That list owns the UI-only metadata —
keybindings, colours, description text, data-source notes — that the
plugin system doesn't (and shouldn't) care about.

This module sources the **authoritative set of installed agents** from
the plugin system's entry points and merges each discovered
:class:`SectorAgent` back against the hard-coded :class:`Launchable`
for the same package (when one exists) so the dashboard keeps its
existing UX. Agents that are installed but not present in the
hard-coded list still show up in the launcher table with sensible
defaults.

Discovery is lazy and cached. Import cost of :mod:`lynx_dashboard`
stays unchanged because nothing here runs until the launcher is
actually opened.

Dev-environment note
--------------------

Entry points are registered at install time. If ``pip install -e .``
has not been re-run after the plugin was added, ``discover()`` will
return an empty list — in that case :func:`discovered_launchables`
falls back to the hard-coded registry so the dashboard still works.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from lynx_dashboard.registry import (
    AGENTS as _HARDCODED_AGENTS,
    APPS as _HARDCODED_APPS,
    Launchable,
    LaunchableKind,
)

__all__ = [
    "discovered_plugins",
    "discovered_launchables",
    "launchable_from_plugin",
    "launch_plugin",
]


# ---------------------------------------------------------------------------
# Plugin discovery (cached)
# ---------------------------------------------------------------------------

# Cache the discovery result so the dashboard doesn't re-walk entry points on
# every UI refresh. ``None`` = not yet probed. Call :func:`reset_cache` in
# tests to force re-discovery.
_DISCOVERY_CACHE: Optional[list] = None


def discovered_plugins(*, refresh: bool = False):
    """Return the raw list of installed :class:`SectorAgent` plugins.

    The result is cached after the first call. Pass ``refresh=True`` to
    force re-discovery (useful in long-running processes if a plugin
    is installed after startup).
    """
    global _DISCOVERY_CACHE
    if _DISCOVERY_CACHE is None or refresh:
        # Lazy import keeps ``lynx_dashboard`` import-time cheap.
        from lynx_investor_core import plugins as core_plugins
        try:
            _DISCOVERY_CACHE = list(core_plugins.discover())
        except Exception:
            # Discovery must never break the dashboard.
            _DISCOVERY_CACHE = []
    return list(_DISCOVERY_CACHE)


def reset_cache() -> None:
    """Clear the discovery cache — primarily for tests."""
    global _DISCOVERY_CACHE
    _DISCOVERY_CACHE = None


# ---------------------------------------------------------------------------
# Plugin → Launchable projection
# ---------------------------------------------------------------------------

# Index the hard-coded launchables by package name for cheap lookup.
def _build_hardcoded_index() -> dict:
    index = {}
    for item in _HARDCODED_APPS + _HARDCODED_AGENTS:
        index[item.package] = item
    return index


def launchable_from_plugin(
    plugin,
    *,
    hardcoded: Optional[Launchable] = None,
) -> Launchable:
    """Project a :class:`SectorAgent` into a :class:`Launchable`.

    Merges with ``hardcoded`` (the matching entry from the registry
    module, if any) so UI-only fields — keybinding, colour, description,
    details, modes — survive. Plugin-sourced fields (name, sector,
    version, CLI command) always win because the plugin is the source
    of truth for what is actually installed.
    """
    if hardcoded is None:
        modes = frozenset({"console", "interactive", "tui", "gui"})
        return Launchable(
            name=plugin.sector or plugin.name,
            short_name=plugin.short_name,
            kind=LaunchableKind.AGENT,
            command=plugin.prog_name,
            package=plugin.package_module,
            tagline=plugin.tagline,
            description=plugin.tagline,
            category=plugin.sector,
            modes=modes,
            registry_name=plugin.name,
        )

    # Merge: keep hard-coded UI flavour, overwrite the identity fields
    # with the authoritative plugin data so the launcher shows the
    # installed version etc.
    return Launchable(
        name=hardcoded.name,
        short_name=hardcoded.short_name,
        kind=hardcoded.kind,
        command=plugin.prog_name or hardcoded.command,
        package=plugin.package_module or hardcoded.package,
        tagline=plugin.tagline or hardcoded.tagline,
        description=hardcoded.description,
        category=hardcoded.category,
        modes=hardcoded.modes,
        keybinding=hardcoded.keybinding,
        registry_name=plugin.name or hardcoded.registry_name,
        example_tickers=hardcoded.example_tickers,
        color=hardcoded.color,
        details=hardcoded.details,
        data_sources=hardcoded.data_sources,
        specialization=hardcoded.specialization,
    )


def discovered_launchables(
    *, refresh: bool = False
) -> Tuple[Launchable, ...]:
    """Return the active launchable set for the dashboard.

    * If any plugins are discovered, return the merged plugin-sourced
      list (preserving hard-coded UI metadata where available).
    * If discovery is empty, fall back to the hard-coded registry so
      the dashboard still works in a dev checkout that hasn't been
      reinstalled.
    """
    plugins = discovered_plugins(refresh=refresh)
    if not plugins:
        return _HARDCODED_APPS + _HARDCODED_AGENTS

    index = _build_hardcoded_index()
    projected: List[Launchable] = []
    for plugin in plugins:
        hardcoded = index.get(plugin.package_module)
        projected.append(launchable_from_plugin(plugin, hardcoded=hardcoded))
    return tuple(projected)


# ---------------------------------------------------------------------------
# Launch bridge
# ---------------------------------------------------------------------------


def launch_plugin(short_or_name: str, argv: Sequence[str]) -> int:
    """Look up a plugin by name/short-name and launch it.

    Thin wrapper around :func:`lynx_investor_core.plugins.get_by_name`
    and :func:`lynx_investor_core.plugins.launch`. Returns the child's
    exit code, or raises :class:`LookupError` if the plugin isn't
    installed.
    """
    from lynx_investor_core import plugins as core_plugins

    agent = core_plugins.get_by_name(short_or_name)
    if agent is None:
        raise LookupError(
            f"No Lynx plugin registered under name/short-name "
            f"{short_or_name!r}. Run 'pip install -e .' against the "
            f"plugin package and try again."
        )
    return core_plugins.launch(agent, list(argv))
