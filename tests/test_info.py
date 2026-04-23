"""Info renderer + --info CLI integration tests."""

from __future__ import annotations

import io
from contextlib import redirect_stdout

from lynx_dashboard.cli import run_cli
from lynx_dashboard.display import render_info
from lynx_dashboard.registry import AGENTS, APPS


def _run(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = run_cli(argv)
    return rc, buf.getvalue()


def test_render_info_agent_includes_specialization():
    agent = next(a for a in AGENTS if a.command == "lynx-energy")
    panel = render_info(agent)
    # Panel renderables stringify to a rendered ANSI block. Check that the
    # three canonical sections survive into the output.
    text = panel.renderable if isinstance(panel.renderable, str) else ""
    assert "What it does" in text
    assert "What makes it specialized" in text
    assert "Reserves" in text or "reserves" in text


def test_render_info_app_has_no_specialization_section():
    fundamental = next(a for a in APPS if a.command == "lynx-fundamental")
    panel = render_info(fundamental)
    text = panel.renderable if isinstance(panel.renderable, str) else ""
    assert "What it does" in text
    assert "What makes it specialized" not in text


def test_cli_info_known_agent():
    rc, out = _run(["--info", "energy"])
    assert rc == 0
    assert "Energy" in out
    assert "Reserves" in out or "reserves" in out
    assert "lynx-energy" in out


def test_cli_info_known_app_by_command():
    rc, out = _run(["--info", "lynx-fundamental"])
    assert rc == 0
    assert "Lynx Fundamental" in out
    assert "Piotroski" in out or "DCF" in out


def test_cli_info_unknown_returns_error():
    rc, _ = _run(["--info", "bogus-name-xyz"])
    assert rc != 0
