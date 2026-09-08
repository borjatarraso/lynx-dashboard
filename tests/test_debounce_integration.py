"""Verify the dashboard GUI / TUI debounce rapid duplicate clicks.

The user reported that clicking "Launch Portfolio" twice in quick
succession spawned two detached subprocesses. Every action callback
that fires expensive work (subprocess, modal, network) is now gated
by a per-key cooldown. These tests lock that behaviour in:

* The dashboard GUI's ``_launch`` only spawns once per cooldown window.
* The dashboard TUI's ``_launch`` ditto, on the synchronous path.

We don't need a real Tk display — we stub out the launcher and the
``_launch`` body's mode dispatch, then call ``_launch`` directly twice
and assert the second call is dropped.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from lynx_investor_core.debounce import ClickDebouncer
from lynx_dashboard.registry import APPS


def _portfolio_target():
    """Return the lynx-portfolio Launchable (the user's repro target)."""
    for item in APPS:
        if item.command == "lynx-portfolio":
            return item
    pytest.fail("lynx-portfolio not in APPS — registry change?")


# ---------------------------------------------------------------------------
# Dashboard GUI
# ---------------------------------------------------------------------------

class TestDashboardGUILaunchDebounce:
    def test_rapid_double_click_only_spawns_once(self, monkeypatch):
        """Clicking _launch twice in <1500 ms must spawn the child once."""
        from lynx_dashboard.gui import app as gui_app

        spawn_calls = []

        def fake_launch_detached(request):
            spawn_calls.append(request)
            return SimpleNamespace(launched=True, message="ok")

        monkeypatch.setattr(gui_app, "launch_detached", fake_launch_detached)
        monkeypatch.setattr(
            gui_app, "build_command", lambda r: ("lynx-portfolio", "-x"),
        )
        monkeypatch.setattr(
            gui_app, "format_command", lambda c: "lynx-portfolio -x",
        )

        # Hand-craft a minimal stand-in for DashboardGUI: just the
        # attributes _launch reads. We bypass the full Tk init because
        # CI has no DISPLAY.
        instance = SimpleNamespace(
            _launch_mode=SimpleNamespace(get=lambda: "gui"),
            _run_mode=SimpleNamespace(get=lambda: "production"),
            _dry_run=False,
            _click_gate=ClickDebouncer(cooldown_ms=1500),
            _show_message=MagicMock(),
            _flash_status=MagicMock(),
        )
        target = _portfolio_target()
        # Double-click: two calls back-to-back from the user.
        gui_app.DashboardGUI._launch(instance, target)
        gui_app.DashboardGUI._launch(instance, target)
        gui_app.DashboardGUI._launch(instance, target)

        assert len(spawn_calls) == 1, (
            "Triple-clicking Launch should spawn exactly one subprocess; "
            f"got {len(spawn_calls)}."
        )

    def test_open_recommend_only_runs_once_per_cooldown(self, monkeypatch):
        from lynx_dashboard.gui import app as gui_app

        modal_opens = []

        def fake_modal(self, *args, **kwargs):
            modal_opens.append(args)
            # Return something Toplevel-shaped that swallows further calls.
            stub = MagicMock()
            stub.destroy = MagicMock()
            return stub

        monkeypatch.setattr(gui_app.DashboardGUI, "_modal", fake_modal)
        # Stub the rest of _open_recommend's work so we don't need Tk.
        monkeypatch.setattr(gui_app.DashboardGUI, "_dialog_buttons",
                            lambda *a, **kw: None)
        # Once the gate denies, the rest of the body never runs, so we
        # only need to make sure the gate is consulted first.
        instance = SimpleNamespace(
            _click_gate=ClickDebouncer(cooldown_ms=600),
            _modal=lambda *a, **kw: fake_modal(instance, *a, **kw),
            _dialog_buttons=lambda *a, **kw: None,
        )
        # Patch out the deeper widget-building so the no-Tk env survives;
        # but on the second call the gate should short-circuit before any
        # of that runs.
        with pytest.raises(Exception):
            # First call goes through the gate, then will hit Tk-less
            # ttk widget construction and blow up. That's fine — the
            # contract we care about is that the gate is consulted.
            gui_app.DashboardGUI._open_recommend(instance)
        # Second call: gate must reject without raising.
        gui_app.DashboardGUI._open_recommend(instance)
        # No second crash means the gate denied early.


# ---------------------------------------------------------------------------
# Dashboard TUI
# ---------------------------------------------------------------------------

class TestDashboardTUILaunchDebounce:
    def test_rapid_double_call_only_launches_once(self, monkeypatch):
        from lynx_dashboard.tui import app as tui_app

        launch_calls = []

        def fake_launch_blocking(request):
            launch_calls.append(request)
            return SimpleNamespace(launched=True, returncode=0, message="")

        monkeypatch.setattr(tui_app, "launch_blocking", fake_launch_blocking)
        monkeypatch.setattr(
            tui_app, "build_command", lambda r: ("lynx-portfolio",),
        )
        monkeypatch.setattr(
            tui_app, "format_command", lambda c: "lynx-portfolio",
        )

        # Strip out the suspend()-context-manager + notify so we don't
        # need a running Textual app for the test.
        from contextlib import contextmanager

        @contextmanager
        def fake_suspend():
            yield

        instance = SimpleNamespace(
            _launch_mode="tui",
            _run_mode="production",
            _dry_run=False,
            _click_gate=ClickDebouncer(cooldown_ms=1500),
            notify=MagicMock(),
            suspend=fake_suspend,
        )

        target = _portfolio_target()
        tui_app.DashboardApp._launch(instance, target)
        tui_app.DashboardApp._launch(instance, target)
        tui_app.DashboardApp._launch(instance, target)

        assert len(launch_calls) == 1, (
            "Triple-press of the launch action should run launch_blocking once."
        )
