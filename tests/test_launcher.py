"""Launcher command-construction tests (no subprocess spawned)."""

from __future__ import annotations

from lynx_dashboard.launcher import (
    LaunchRequest,
    build_command,
    mode_to_flag,
    resolve_executable,
    launch_blocking,
)
from lynx_dashboard.registry import APPS, by_name


def _fundamental():
    target = by_name("fundamental")
    assert target is not None
    return target


def test_mode_to_flag_covers_all_modes():
    assert mode_to_flag("console") is None
    assert mode_to_flag("interactive") == "-i"
    assert mode_to_flag("tui") == "-tui"
    assert mode_to_flag("gui") == "-x"
    assert mode_to_flag("search") == "-s"
    assert mode_to_flag("bogus") is None


def test_resolve_executable_always_returns_something():
    for app in APPS:
        resolved = resolve_executable(app)
        assert resolved, f"no resolution for {app.command}"
        # Every entry should be a non-empty list of strings.
        assert all(isinstance(x, str) and x for x in resolved)


def test_build_command_basic_production_console():
    target = _fundamental()
    cmd = build_command(LaunchRequest(target=target, mode="console", run_mode="production"))
    assert "-p" in cmd
    assert "-t" not in cmd
    assert cmd[-1] != "-i"  # no UI flag in console mode


def test_build_command_tui_with_ticker():
    target = _fundamental()
    cmd = build_command(LaunchRequest(target=target, mode="tui", ticker="AAPL", run_mode="production"))
    assert "-p" in cmd
    assert "-tui" in cmd
    assert "AAPL" in cmd


def test_launch_intent_threads_ticker_into_command():
    """When the Recommend dialog passes a ticker into _launch, the subprocess
    argv must include it so the agent auto-runs analysis on that company."""
    target = by_name("energy")
    assert target is not None
    # Simulates what `self._launch(target, ticker="OCO.V")` builds.
    cmd = build_command(LaunchRequest(
        target=target, mode="tui", run_mode="production", ticker="OCO.V",
    ))
    assert "lynx-energy" in " ".join(cmd)
    assert "OCO.V" in cmd
    assert "-p" in cmd
    assert "-tui" in cmd


def test_launch_intent_without_ticker_still_works():
    target = by_name("fundamental")
    assert target is not None
    cmd = build_command(LaunchRequest(
        target=target, mode="console", run_mode="production", ticker=None,
    ))
    assert "lynx-fundamental" in " ".join(cmd)
    # No ticker argument should have been appended.
    assert all(not arg.startswith("OCO") for arg in cmd)


def test_build_command_testing_and_refresh():
    target = _fundamental()
    cmd = build_command(LaunchRequest(
        target=target, mode="interactive", run_mode="testing", refresh=True,
    ))
    assert "-t" in cmd
    assert "-p" not in cmd
    assert "-i" in cmd
    assert "--refresh" in cmd


def test_build_command_compare_two_tickers():
    target = by_name("compare")
    assert target is not None
    cmd = build_command(LaunchRequest(target=target, mode="console", ticker="AAPL MSFT"))
    # Both tickers must appear as separate argv entries for lynx-compare's positional parser.
    assert "AAPL" in cmd
    assert "MSFT" in cmd


def test_launch_blocking_dry_run_does_not_spawn():
    target = _fundamental()
    result = launch_blocking(
        LaunchRequest(target=target, mode="console"),
        dry_run=True,
    )
    assert not result.launched
    assert result.returncode == 0


def test_sibling_script_resolves_agent_checkout_layout(tmp_path, monkeypatch):
    """Agent scripts live at lynx-investor/lynx-investor-<sector>/lynx-investor-<sector>.py.
    The previous resolver looked for lynx-energy.py in that directory, which
    never existed. Lock the correct path in."""
    import lynx_dashboard.launcher as launcher_module

    fake_root = tmp_path / "suite"
    agent_dir = fake_root / "lynx-investor" / "lynx-investor-energy"
    agent_dir.mkdir(parents=True)
    script = agent_dir / "lynx-investor-energy.py"
    script.write_text("# fake\n")

    # Fake dashboard package root under tmp_path so the resolver walks up
    # from the faked __file__ into *our* tmp suite layout.
    fake_package = fake_root / "lynx-dashboard" / "lynx_dashboard"
    fake_package.mkdir(parents=True)
    fake_launcher_file = fake_package / "launcher.py"
    fake_launcher_file.write_text("")

    monkeypatch.setattr(launcher_module, "__file__", str(fake_launcher_file))
    resolved = launcher_module._sibling_script("lynx-energy")
    assert resolved == script


def test_sibling_script_resolves_core_app_layout(tmp_path, monkeypatch):
    """Core apps live at <root>/lynx-<name>/lynx-<name>.py — unchanged."""
    import lynx_dashboard.launcher as launcher_module

    fake_root = tmp_path / "suite"
    app_dir = fake_root / "lynx-fundamental"
    app_dir.mkdir(parents=True)
    script = app_dir / "lynx-fundamental.py"
    script.write_text("# fake\n")

    fake_package = fake_root / "lynx-dashboard" / "lynx_dashboard"
    fake_package.mkdir(parents=True)
    fake_launcher_file = fake_package / "launcher.py"
    fake_launcher_file.write_text("")

    monkeypatch.setattr(launcher_module, "__file__", str(fake_launcher_file))
    resolved = launcher_module._sibling_script("lynx-fundamental")
    assert resolved == script
