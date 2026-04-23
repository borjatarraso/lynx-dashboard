"""Unit tests for the GUI launcher helpers (no display required)."""

from __future__ import annotations

import os

import pytest

from lynx_dashboard.gui.app import (
    _TERMINAL_CANDIDATES,
    _build_keep_open_script,
    _display_key,
    _logo_path,
    _resolve_terminal,
    _strip_rich_markup,
)


def test_terminal_candidates_nonempty():
    """The candidate list must cover at least the big-three DE terminals."""
    names = {name for name, _prefix in _TERMINAL_CANDIDATES}
    assert "xterm" in names
    assert "gnome-terminal" in names
    assert "konsole" in names


def test_resolve_terminal_returns_none_or_valid_tuple():
    result = _resolve_terminal()
    if result is None:
        return
    path, prefix = result
    assert isinstance(path, str) and path
    assert isinstance(prefix, tuple)


def test_resolve_terminal_respects_override(monkeypatch, tmp_path):
    # Create a fake executable and point LYNX_TERMINAL at it.
    fake = tmp_path / "fake-terminal"
    fake.write_text("#!/bin/sh\nexit 0\n")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}" + os.environ.get("PATH", ""))
    monkeypatch.setenv("LYNX_TERMINAL", "fake-terminal")
    resolved = _resolve_terminal()
    assert resolved is not None
    path, prefix = resolved
    assert path.endswith("fake-terminal")
    assert prefix == ()


def test_display_key_handles_minus_and_none():
    assert _display_key(None) == ""
    assert _display_key("") == ""
    assert _display_key("f") == "f"
    assert _display_key("minus") == "-"


def test_strip_rich_markup():
    assert _strip_rich_markup("[bold green]hi[/]") == "hi"
    assert _strip_rich_markup("plain") == "plain"
    assert _strip_rich_markup("[bold]a[/] [italic]b[/]") == "a b"


def test_keep_open_script_includes_command_exit_code_and_read():
    """The keep-open wrapper is the difference between 'terminal blinks and
    vanishes' and 'user sees what actually happened' — lock the shape in."""
    script = _build_keep_open_script(("lynx-fundamental", "-p", "-tui"))
    assert "lynx-fundamental -p -tui" in script
    assert "__lynx_ec=$?" in script
    assert "command exited with code" in script
    assert "read -r" in script


def test_keep_open_script_quotes_spaces_in_argv():
    """Arguments with spaces (multi-ticker compare input) must survive."""
    script = _build_keep_open_script(("lynx-compare", "-p", "AAPL MSFT"))
    # shlex.join should quote the multi-word ticker argument.
    assert "'AAPL MSFT'" in script or '"AAPL MSFT"' in script


def test_png_logos_shipped():
    """The dashboard must ship the PNG logos; GUI relies on them."""
    for name in (
        "logo_sm_green.png",
        "logo_md_green.png",
        "logo_lg_green.png",
    ):
        path = _logo_path(name)
        assert path is not None, f"{name} not found in img/"
        assert path.is_file() and path.stat().st_size > 0
