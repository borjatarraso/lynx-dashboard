"""CLI smoke tests (no external process spawned; dry-run only)."""

from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout

import pytest

from lynx_dashboard.cli import build_parser, run_cli


def _run(argv):
    buf_out, buf_err = io.StringIO(), io.StringIO()
    with redirect_stdout(buf_out), redirect_stderr(buf_err):
        rc = run_cli(argv)
    return rc, buf_out.getvalue(), buf_err.getvalue()


def test_help_parses():
    parser = build_parser()
    help_text = parser.format_help()
    assert "lynx-dashboard" in help_text
    assert "--recommend" in help_text
    assert "--launch" in help_text


def test_list_prints_every_launchable():
    rc, out, _ = _run(["--list"])
    assert rc == 0
    assert "lynx-fundamental" in out
    assert "lynx-compare" in out
    assert "lynx-portfolio" in out
    # all 11 sector commands
    for cmd in (
        "lynx-energy", "lynx-finance", "lynx-tech", "lynx-health",
        "lynx-mining", "lynx-discretionary", "lynx-staples",
        "lynx-industrials", "lynx-utilities", "lynx-comm", "lynx-realestate",
    ):
        assert cmd in out, f"{cmd} missing from --list"


def test_about_prints_license():
    rc, out, _ = _run(["--about"])
    assert rc == 0
    assert "BSD" in out
    assert "Lynx Dashboard" in out


def test_recommend_offline_hits_known_ticker():
    rc, out, _ = _run(["--recommend", "XOM", "--offline"])
    assert rc == 0
    assert "Energy" in out or "lynx-energy" in out


def test_recommend_offline_unknown_ticker_returns_nonzero():
    rc, _, _ = _run(["--recommend", "totally-unknown-xyz-123", "--offline"])
    assert rc != 0


def test_launch_dry_run_builds_command():
    rc, out, _ = _run(["--launch", "fundamental", "AAPL", "--dry-run", "-c"])
    assert rc == 0
    assert "lynx-fundamental" in out
    assert "AAPL" in out
    assert "-p" in out


def test_launch_dry_run_with_testing_mode():
    rc, out, _ = _run(["--launch", "energy", "XOM", "--dry-run", "-c", "-t"])
    assert rc == 0
    assert "-t" in out
    assert "-p" not in out


def test_launch_unknown_target_errors():
    rc, _, _ = _run(["--launch", "bogus-name-xyz", "--dry-run"])
    assert rc != 0


def test_recommend_and_launch_are_mutually_exclusive():
    """Combining two run-once actions used to silently drop one — argparse
    must now reject the combination outright."""
    with pytest.raises(SystemExit):
        _run(["--recommend", "XOM", "--launch", "fundamental"])


def test_info_and_list_are_mutually_exclusive():
    with pytest.raises(SystemExit):
        _run(["--info", "energy", "--list"])


def test_no_splash_flag_accepted():
    parser = build_parser()
    args = parser.parse_args(["--no-splash", "-c"])
    assert args.no_splash is True


def test_list_json_is_valid_and_non_empty():
    """--list --json produces a JSON array covering every launchable."""
    import json as _json
    rc, out, _ = _run(["--list", "--json"])
    assert rc == 0
    payload = _json.loads(out)
    assert isinstance(payload, list)
    # One row per app + agent (8 apps + 11 agents).
    assert len(payload) == 19
    commands = {x["command"] for x in payload}
    assert "lynx-fundamental" in commands
    assert "lynx-etf" in commands
    assert "lynx-compare-etf" in commands
    assert "lynx-fund" in commands
    assert "lynx-compare-fund" in commands
    assert "lynx-theme" in commands
    assert "lynx-energy" in commands


def test_recommend_json_offline_known_ticker():
    import json as _json
    rc, out, _ = _run(["--recommend", "XOM", "--offline", "--json"])
    assert rc == 0
    payload = _json.loads(out)
    assert payload["has_match"] is True
    assert payload["primary"]["registry_name"] == "lynx-investor-energy"
    assert payload["query"] == "XOM"


def test_recommend_json_offline_no_match():
    import json as _json
    rc, out, _ = _run(["--recommend", "xyz-unknown-123", "--offline", "--json"])
    assert rc != 0
    payload = _json.loads(out)
    assert payload["has_match"] is False
    assert payload["primary"] is None


def test_info_json_known_agent():
    import json as _json
    rc, out, _ = _run(["--info", "energy", "--json"])
    assert rc == 0
    payload = _json.loads(out)
    assert payload["command"] == "lynx-energy"
    assert payload["kind"] == "agent"
    assert "What makes it specialized" not in payload  # NOT rendered text
    assert "specialization" in payload


def test_info_json_unknown_emits_error_object():
    import json as _json
    rc, out, _ = _run(["--info", "bogus-xyz", "--json"])
    assert rc != 0
    payload = _json.loads(out)
    assert "error" in payload


def test_debug_flag_sets_env(monkeypatch):
    """--debug / --verbose must flip LYNX_DEBUG so the recommender's
    stdout silencers become no-ops."""
    # Explicitly clean the env both before and after so a stray LYNX_DEBUG
    # from a prior test doesn't mask a regression, and this test doesn't
    # bleed state into later tests.
    import os as _os
    monkeypatch.delenv("LYNX_DEBUG", raising=False)
    try:
        rc, _, _ = _run(["--list", "--debug"])
        assert rc == 0
        assert _os.environ.get("LYNX_DEBUG") == "1"
    finally:
        _os.environ.pop("LYNX_DEBUG", None)


def test_clear_history_runs(tmp_path, monkeypatch):
    """--clear-history must wipe the file without error."""
    monkeypatch.setenv("LYNX_DASHBOARD_HISTORY", str(tmp_path / "h.json"))
    # Write a fake history first.
    from lynx_dashboard.history import HistoryEntry, HistoryStore
    HistoryStore().record(HistoryEntry(query="AAPL"))
    rc, out, _ = _run(["--clear-history"])
    assert rc == 0
    assert HistoryStore().load() == []


def test_entrypoint_propagates_nonzero_exit_code(tmp_path):
    """Regression: the top-level scripts must call sys.exit(run_cli()) —
    otherwise non-zero return codes silently become 0 at the shell level.

    Reproduces `python -m lynx_dashboard --info bogus` and asserts the
    subprocess itself exits non-zero. The test before this existed only
    checked run_cli()'s return value, which hid the bug."""
    import os as _os
    import subprocess as _sp
    import sys as _sys

    root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    env = _os.environ.copy()
    env["PYTHONPATH"] = f"{root}:{_os.path.dirname(root)}/lynx-investor-core"

    # `python -m lynx_dashboard` with an unknown --info name must exit != 0.
    r = _sp.run(
        [_sys.executable, "-m", "lynx_dashboard", "--info", "definitely-not-a-name"],
        cwd=root,
        env=env,
        stdout=_sp.PIPE,
        stderr=_sp.PIPE,
        timeout=30,
    )
    assert r.returncode != 0, (
        f"entrypoint swallowed non-zero exit code. stdout={r.stdout!r} stderr={r.stderr!r}"
    )

    # And the direct script must too.
    r = _sp.run(
        [_sys.executable, "lynx-dashboard.py", "--info", "definitely-not-a-name"],
        cwd=root,
        env=env,
        stdout=_sp.PIPE,
        stderr=_sp.PIPE,
        timeout=30,
    )
    assert r.returncode != 0, (
        f"lynx-dashboard.py swallowed non-zero exit code. stdout={r.stdout!r} stderr={r.stderr!r}"
    )


@pytest.mark.parametrize("flag", ["-i", "-tui", "-x"])
def test_interactive_ui_modes_parse_without_error(flag):
    parser = build_parser()
    # Just verify the parser accepts these without raising.
    parser.parse_args([flag, "--dry-run"])
