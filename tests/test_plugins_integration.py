"""Integration tests for the plugin-system bridge in the dashboard."""

from __future__ import annotations

import sys
import types

import pytest

from lynx_dashboard import plugin_loader
from lynx_dashboard.plugin_loader import (
    discovered_launchables,
    discovered_plugins,
    launch_plugin,
    launchable_from_plugin,
    reset_cache,
)
from lynx_dashboard.registry import AGENTS as HARDCODED_AGENTS, APPS as HARDCODED_APPS


# ---------------------------------------------------------------------------
# Helpers: fabricate fake entry points the same way the core plugins tests do
# ---------------------------------------------------------------------------


class _FakeEntryPoint:
    def __init__(self, loader, name="fake", group="lynx_investor_suite.agents"):
        self.name = name
        self.group = group
        self._loader = loader

    def load(self):
        return self._loader


class _FakeEntryPoints:
    def __init__(self, eps):
        self._eps = list(eps)

    def select(self, group=None):
        if group is None:
            return list(self._eps)
        return [e for e in self._eps if getattr(e, "group", None) == group]


def _inject_entry_points(monkeypatch, eps):
    import importlib.metadata as md

    fake = _FakeEntryPoints(eps)
    monkeypatch.setattr(md, "entry_points", lambda: fake)
    # Clear the dashboard's cached discovery so the fake sees light of day.
    reset_cache()


def _make_sector_agent(**overrides):
    from lynx_investor_core.plugins import SectorAgent

    defaults = dict(
        name="lynx-investor-energy",
        short_name="energy",
        sector="Energy",
        tagline="Oil, gas, pipelines, LNG, energy services",
        prog_name="lynx-energy",
        version="5.2",
        package_module="lynx_energy",
        entry_point_module="lynx_energy.__main__",
        entry_point_function="main",
        icon="\u26fd",
    )
    defaults.update(overrides)
    return SectorAgent(**defaults)


# ---------------------------------------------------------------------------
# discovered_plugins() / discovered_launchables()
# ---------------------------------------------------------------------------


def test_discovery_returns_known_agents(monkeypatch):
    """Discovery via injected entry points returns the expected SectorAgents."""
    agent = _make_sector_agent()
    _inject_entry_points(monkeypatch, [_FakeEntryPoint(lambda: agent)])

    plugins = discovered_plugins(refresh=True)

    assert len(plugins) == 1
    assert plugins[0].name == "lynx-investor-energy"
    assert plugins[0].short_name == "energy"
    assert plugins[0].version == "5.2"


def test_discovery_caches_result(monkeypatch):
    """Repeat calls without refresh=True should reuse the cached list."""
    agent = _make_sector_agent()
    _inject_entry_points(monkeypatch, [_FakeEntryPoint(lambda: agent)])

    first = discovered_plugins(refresh=True)
    # Replace entry points but expect the cache to win.
    _inject_entry_points(monkeypatch, [])  # this calls reset_cache()
    # Manually re-seed the cache since reset cleared it:
    discovered_plugins(refresh=True)
    cached = discovered_plugins()  # no refresh
    assert cached == discovered_plugins()


def test_discovery_falls_back_to_hardcoded_when_empty(monkeypatch):
    """When no plugins are installed, discovered_launchables falls back."""
    _inject_entry_points(monkeypatch, [])

    result = discovered_launchables(refresh=True)

    assert result == HARDCODED_APPS + HARDCODED_AGENTS


def test_discovered_launchables_projects_plugins(monkeypatch):
    """When plugins are installed, they drive the launchable list."""
    agent = _make_sector_agent()
    _inject_entry_points(monkeypatch, [_FakeEntryPoint(lambda: agent)])

    result = discovered_launchables(refresh=True)

    assert len(result) == 1
    only = result[0]
    assert only.command == "lynx-energy"
    assert only.package == "lynx_energy"
    # Sector (category) and registry_name should come from the plugin.
    assert only.registry_name == "lynx-investor-energy"


def test_discovered_launchable_merges_hardcoded_ui_metadata(monkeypatch):
    """Merged Launchable preserves hard-coded UI flavour (keybinding, details)."""
    agent = _make_sector_agent()  # package_module="lynx_energy" → hardcoded match
    _inject_entry_points(monkeypatch, [_FakeEntryPoint(lambda: agent)])

    merged = discovered_launchables(refresh=True)[0]

    # The hard-coded Energy entry has keybinding="1" and details/data_sources.
    assert merged.keybinding == "1"
    assert merged.details, "merged entry lost hard-coded details"
    assert merged.data_sources, "merged entry lost hard-coded data_sources"


def test_launchable_from_plugin_without_hardcoded_defaults_sensibly():
    """A third-party plugin with no hard-coded twin still produces a Launchable."""
    agent = _make_sector_agent(
        name="lynx-investor-spacetech",
        short_name="spacetech",
        sector="Space Tech",
        tagline="Launch vehicles and satellites",
        prog_name="lynx-spacetech",
        package_module="lynx_spacetech",
        entry_point_module="lynx_spacetech.__main__",
    )

    launchable = launchable_from_plugin(agent, hardcoded=None)

    assert launchable.command == "lynx-spacetech"
    assert launchable.package == "lynx_spacetech"
    assert launchable.registry_name == "lynx-investor-spacetech"
    assert "console" in launchable.modes and "gui" in launchable.modes


# ---------------------------------------------------------------------------
# launch_plugin()
# ---------------------------------------------------------------------------


def test_launch_resolves_entry_function(monkeypatch):
    """launch_plugin resolves to the plugin's main() and forwards argv."""
    captured = {}

    def fake_main(argv):
        captured["argv"] = list(argv)
        return 0

    fake_module = types.ModuleType("plugin_integ_fake")
    fake_module.main = fake_main  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "plugin_integ_fake", fake_module)

    agent = _make_sector_agent(
        name="lynx-investor-fake",
        short_name="fake",
        entry_point_module="plugin_integ_fake",
        entry_point_function="main",
        package_module="lynx_fake",
    )
    _inject_entry_points(monkeypatch, [_FakeEntryPoint(lambda: agent)])

    rc = launch_plugin("fake", ["-p", "AAPL"])

    assert rc == 0
    assert captured["argv"] == ["-p", "AAPL"]


def test_launch_plugin_raises_when_unknown(monkeypatch):
    _inject_entry_points(monkeypatch, [])  # nothing installed
    with pytest.raises(LookupError):
        launch_plugin("doesnotexist", [])


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_between_tests():
    """Every test starts with a clean discovery cache."""
    reset_cache()
    yield
    reset_cache()
