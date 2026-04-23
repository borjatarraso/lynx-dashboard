"""Public API surface tests.

Any change that would break these tests is an API break and must bump
``lynx_dashboard.api.__api_version__``.
"""

from __future__ import annotations

import json

import pytest

from lynx_dashboard import api


# ---------------------------------------------------------------------------
# Metadata & exports
# ---------------------------------------------------------------------------

def test_api_version_is_semver_shaped():
    assert api.__api_version__.count(".") >= 1
    major, *_ = api.__api_version__.split(".")
    int(major)  # raises if not numeric


def test_api_reexports_core_types():
    """A known-stable checklist. Drop a name and you're breaking clients."""
    for name in (
        "APPS", "AGENTS", "ALL_LAUNCHABLES",
        "Launchable", "LaunchableKind",
        "by_name", "by_keybinding", "by_registry_name",
        "agents_for_mode", "apps_for_mode",
        "CompanyProfile", "Recommendation",
        "recommend", "recommend_for_query", "recommend_for_profile",
        "LaunchRequest", "LaunchResult",
        "build_command", "format_command",
        "launch_blocking", "launch_detached",
        "make_launch_request", "resolve_executable", "mode_to_flag",
        "launchable_as_dict", "catalog_as_dicts", "recommendation_as_dict",
        "get_about_text", "get_logo_ascii", "find",
    ):
        assert hasattr(api, name), f"api.{name} must be exported"


def test_find_is_thin_alias_for_by_name():
    assert api.find("energy") is api.by_name("energy")
    assert api.find("bogus-xxx") is None


# ---------------------------------------------------------------------------
# Launchable → dict
# ---------------------------------------------------------------------------

def test_launchable_as_dict_shape_is_stable():
    item = api.find("fundamental")
    assert item is not None
    payload = api.launchable_as_dict(item)
    for key in (
        "name", "short_name", "kind", "command", "package", "tagline",
        "description", "category", "modes", "keybinding", "registry_name",
        "example_tickers", "color", "details", "data_sources",
        "specialization",
    ):
        assert key in payload, f"{key} missing from launchable dict"
    # JSON-serializable (= no non-primitive values leaked through).
    json.dumps(payload)


def test_catalog_as_dicts_covers_every_launchable():
    catalog = api.catalog_as_dicts()
    assert len(catalog) == len(api.ALL_LAUNCHABLES)
    commands = {x["command"] for x in catalog}
    assert commands == {item.command for item in api.ALL_LAUNCHABLES}
    json.dumps(catalog)  # fully serializable


def test_modes_serialize_sorted_list():
    """frozenset doesn't JSON-serialize; the API must sort into a list."""
    payload = api.launchable_as_dict(api.find("fundamental"))
    assert isinstance(payload["modes"], list)
    assert payload["modes"] == sorted(payload["modes"])


# ---------------------------------------------------------------------------
# Recommend
# ---------------------------------------------------------------------------

def test_recommend_offline_shortcut():
    rec = api.recommend("XOM", offline=True)
    assert rec.has_match
    assert rec.primary.registry_name == "lynx-investor-energy"


def test_recommendation_as_dict_shape():
    rec = api.recommend("AAPL", offline=True)
    payload = api.recommendation_as_dict(rec)
    for key in ("query", "profile", "primary", "alternates", "reason", "has_match"):
        assert key in payload
    assert payload["has_match"] is True
    assert payload["primary"]["registry_name"] == "lynx-investor-information-technology"
    json.dumps(payload)


def test_recommendation_as_dict_no_match():
    rec = api.recommend("totally-unknown-xyz", offline=True)
    payload = api.recommendation_as_dict(rec)
    assert payload["has_match"] is False
    assert payload["primary"] is None
    assert payload["alternates"] == []


# ---------------------------------------------------------------------------
# Launch request helpers
# ---------------------------------------------------------------------------

def test_make_launch_request_threads_ticker():
    target = api.find("energy")
    req = api.make_launch_request(target, mode="tui", ticker="XOM")
    cmd = api.build_command(req)
    assert "lynx-energy" in " ".join(cmd)
    assert "-p" in cmd
    assert "-tui" in cmd
    assert "XOM" in cmd


def test_make_launch_request_defaults():
    target = api.find("fundamental")
    req = api.make_launch_request(target)
    # Mode defaults to console (no UI flag), run_mode defaults to production.
    cmd = api.build_command(req)
    assert "-p" in cmd
    assert "-tui" not in cmd and "-i" not in cmd and "-x" not in cmd


@pytest.mark.parametrize("mode,expected", [
    ("console", None),
    ("interactive", "-i"),
    ("tui", "-tui"),
    ("gui", "-x"),
])
def test_mode_to_flag(mode, expected):
    assert api.mode_to_flag(mode) == expected
