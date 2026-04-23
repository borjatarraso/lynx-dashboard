"""Registry invariants."""

from __future__ import annotations

from lynx_investor_core.sector_registry import AGENT_REGISTRY

from lynx_dashboard.registry import (
    AGENTS,
    APPS,
    ALL_LAUNCHABLES,
    LaunchableKind,
    agents_for_mode,
    apps_for_mode,
    by_keybinding,
    by_name,
    by_registry_name,
)


def test_three_core_apps():
    assert len(APPS) == 3
    commands = {a.command for a in APPS}
    assert commands == {"lynx-fundamental", "lynx-compare", "lynx-portfolio"}


def test_eleven_sector_agents():
    assert len(AGENTS) == 11


def test_all_launchables_union():
    assert len(ALL_LAUNCHABLES) == len(APPS) + len(AGENTS)


def test_every_agent_has_a_registry_entry():
    """Every dashboard agent must match exactly one entry in core's registry."""
    core_names = {e.name for e in AGENT_REGISTRY}
    for agent in AGENTS:
        assert agent.registry_name is not None, f"{agent.name} missing registry_name"
        assert agent.registry_name in core_names, (
            f"{agent.registry_name} not found in lynx_investor_core.sector_registry"
        )


def test_every_core_registry_entry_has_an_agent():
    """And vice-versa: the dashboard must expose an agent for every sector."""
    dashboard_names = {a.registry_name for a in AGENTS}
    for entry in AGENT_REGISTRY:
        assert entry.name in dashboard_names, (
            f"No dashboard button for core agent {entry.name}"
        )


def test_keybindings_unique():
    seen = {}
    for item in ALL_LAUNCHABLES:
        if item.keybinding is None:
            continue
        assert item.keybinding not in seen, (
            f"Keybinding collision: '{item.keybinding}' on "
            f"{item.name} and {seen[item.keybinding].name}"
        )
        seen[item.keybinding] = item


def test_lookup_by_name():
    assert by_name("fundamental") is not None
    assert by_name("lynx-fundamental").command == "lynx-fundamental"
    assert by_name("Fundamental").command == "lynx-fundamental"
    assert by_name("bogus") is None
    assert by_name("") is None


def test_lookup_by_keybinding():
    target = by_keybinding("f")
    assert target is not None and target.command == "lynx-fundamental"
    assert by_keybinding("minus") is not None
    assert by_keybinding("") is None


def test_lookup_by_registry_name():
    target = by_registry_name("lynx-investor-energy")
    assert target is not None and target.command == "lynx-energy"


def test_apps_and_agents_kind_consistency():
    for app in APPS:
        assert app.is_app and not app.is_agent
        assert app.kind == LaunchableKind.APP
    for agent in AGENTS:
        assert agent.is_agent and not agent.is_app
        assert agent.kind == LaunchableKind.AGENT


def test_mode_filters_return_all_for_standard_modes():
    for mode in ("console", "interactive", "tui", "gui"):
        assert apps_for_mode(mode) == APPS
        assert agents_for_mode(mode) == AGENTS


def test_every_launchable_has_details():
    """Info dialogs rely on the `details` field being non-empty."""
    for item in ALL_LAUNCHABLES:
        assert item.details, f"{item.name} has no details"
        assert len(item.details) > 80, f"{item.name} details too short"


def test_every_launchable_has_data_sources():
    for item in ALL_LAUNCHABLES:
        assert item.data_sources, f"{item.name} missing data_sources"
        assert all(isinstance(s, str) and s for s in item.data_sources)


def test_every_agent_has_specialization():
    """Agents must explain what makes them specialized."""
    for agent in AGENTS:
        assert agent.specialization, f"{agent.name} missing specialization"


def test_apps_have_no_specialization():
    """Core apps are general-purpose; leaving specialization empty is intentional."""
    for app in APPS:
        assert app.specialization == "", f"{app.name} should not have specialization"
