"""Launch a target app / agent from the dashboard.

The dashboard never reaches into another app's internals; it launches each
target as a subprocess exactly the way a human would from the shell. This
keeps the data-isolation contract of the suite intact (each agent manages its
own ``data/`` and ``data_test/`` directories, its own cache, and its own
argument parser) and it means there is no long-lived Python process that
could accidentally share state between agents.

The one subtlety is mode inheritance. When the dashboard runs inside a TUI
(Textual) or GUI (Tkinter) main loop, we want the launched app to replace
the dashboard visually while it runs, and then return control cleanly when
the user quits the child. See :func:`launch_blocking` for how each mode is
handled.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from lynx_dashboard.registry import Launchable

__all__ = [
    "LaunchRequest",
    "LaunchResult",
    "build_command",
    "resolve_executable",
    "launch_blocking",
    "launch_detached",
    "mode_to_flag",
]


# Map dashboard mode → CLI flag understood by every suite app.
_MODE_FLAG: dict = {
    "console": None,          # no flag — default behaviour
    "interactive": "-i",
    "tui": "-tui",
    "gui": "-x",
    "search": "-s",
}


def mode_to_flag(mode: str) -> Optional[str]:
    return _MODE_FLAG.get(mode)


@dataclass(frozen=True)
class LaunchRequest:
    target: Launchable
    mode: str                             # console / interactive / tui / gui
    ticker: Optional[str] = None
    run_mode: str = "production"          # production / testing
    extra_args: Tuple[str, ...] = ()
    refresh: bool = False


@dataclass(frozen=True)
class LaunchResult:
    command: Tuple[str, ...]
    returncode: int
    launched: bool                        # False if executable missing / dry-run
    message: str = ""


# ---------------------------------------------------------------------------
# Command construction
# ---------------------------------------------------------------------------

def build_command(request: LaunchRequest) -> Tuple[str, ...]:
    """Build the argv tuple the launcher will execute for *request*."""
    exe = resolve_executable(request.target)
    cmd: List[str] = list(exe)

    # Run mode is required by every suite agent.
    if request.run_mode == "testing":
        cmd.append("-t")
    else:
        cmd.append("-p")

    # UI mode flag.
    flag = mode_to_flag(request.mode)
    if flag:
        cmd.append(flag)

    if request.refresh:
        cmd.append("--refresh")

    # Ticker (or comparison pair). Many apps accept a positional identifier;
    # passing a blank string is a no-op on most, so we guard against it.
    if request.ticker:
        # lynx-compare takes TWO positional tickers separated by space. We
        # pass them as separate argv entries.
        parts = [p for p in request.ticker.split() if p]
        cmd.extend(parts)

    if request.extra_args:
        cmd.extend(request.extra_args)

    return tuple(cmd)


def resolve_executable(target: Launchable) -> List[str]:
    """Return the argv prefix needed to launch *target*.

    Resolution order:

    1. If the installed CLI (``target.command``) is on ``$PATH``, use it.
    2. If the Python package (``target.package``) imports, use
       ``python -m target.package``.
    3. If there's a sibling ``<target.command>.py`` script next to this
       checkout, fall back to ``python <that script>``.
    4. Last-resort fallback: just return the command name so the user gets a
       legible "command not found" error (with the hint shown alongside it).
    """
    # 1. Installed CLI entry point
    path = shutil.which(target.command)
    if path:
        return [path]

    # 2. Module launch
    if _module_importable(target.package):
        return [sys.executable, "-m", target.package]

    # 3. Sibling script
    sibling = _sibling_script(target.command)
    if sibling is not None:
        return [sys.executable, str(sibling)]

    # 4. Hopeful last resort — subprocess will fail with a clean message.
    return [target.command]


def _module_importable(package_name: str) -> bool:
    import importlib.util
    try:
        return importlib.util.find_spec(package_name) is not None
    except (ImportError, ValueError):
        return False


def _sibling_script(command: str) -> Optional[Path]:
    """Find the entry script for *command* in the expected checkout layout.

    Core apps live at ``.../lynx-<name>/lynx-<name>.py`` — directory and
    script name match the CLI name. Agents, however, have a longer directory
    and script name than their CLI command: ``lynx-energy`` is launched by
    ``.../lynx-investor/lynx-investor-energy/lynx-investor-energy.py``. We
    probe all three conventions in order, so whichever exists wins.
    """
    here = Path(__file__).resolve().parent.parent        # .../lynx-dashboard
    suite_root = here.parent                              # .../ (contains all lynx-* dirs)
    agent_dir = _guess_agent_dir(command)
    candidates = [
        # 1. Core-app convention: matching directory and script name.
        suite_root / command / f"{command}.py",
        # 2. Agent convention: lynx-investor/lynx-investor-<sector>/lynx-investor-<sector>.py.
        suite_root / "lynx-investor" / agent_dir / f"{agent_dir}.py",
        # 3. Fallback: agent directory but with the CLI-command script name
        # (in case someone renames things). Harmless if it doesn't exist.
        suite_root / "lynx-investor" / agent_dir / f"{command}.py",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


_COMMAND_TO_AGENT_DIR: dict = {
    "lynx-energy": "lynx-investor-energy",
    "lynx-finance": "lynx-investor-financials",
    "lynx-tech": "lynx-investor-information-technology",
    "lynx-health": "lynx-investor-healthcare",
    "lynx-mining": "lynx-investor-basic-materials",
    "lynx-discretionary": "lynx-investor-consumer-discretionary",
    "lynx-staples": "lynx-investor-consumer-staples",
    "lynx-industrials": "lynx-investor-industrials",
    "lynx-utilities": "lynx-investor-utilities",
    "lynx-comm": "lynx-investor-communication-services",
    "lynx-realestate": "lynx-investor-real-estate",
}


def _guess_agent_dir(command: str) -> str:
    return _COMMAND_TO_AGENT_DIR.get(command, command)


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def launch_blocking(request: LaunchRequest, *, dry_run: bool = False) -> LaunchResult:
    """Launch *request* and block until the child exits.

    The dashboard's mode dictates how we run the child:

    * **tui** — if we're called from inside a running Textual ``App``, the
      caller is expected to wrap us in ``app.suspend()`` (see
      ``tui/app.py``). From this function's perspective we just run the
      child attached to the same TTY.
    * **gui / console / interactive** — run attached to the controlling
      terminal; the child inherits stdin/stdout/stderr.

    Use :func:`launch_detached` instead when you want a GUI child to pop up
    in its own window while the dashboard keeps running.
    """
    cmd = build_command(request)
    if dry_run:
        return LaunchResult(cmd, 0, False, "dry-run (no subprocess spawned)")
    try:
        completed = subprocess.run(list(cmd))
    except FileNotFoundError as exc:
        return LaunchResult(
            cmd, 127, False,
            f"Executable not found: {exc.filename or cmd[0]}. "
            f"Is '{request.target.command}' installed (pip install {request.target.command})?",
        )
    except KeyboardInterrupt:
        return LaunchResult(cmd, 130, True, "Cancelled by user.")
    msg = f"{request.target.command} exited with code {completed.returncode}."
    return LaunchResult(cmd, completed.returncode, True, msg)


def launch_detached(request: LaunchRequest, *, dry_run: bool = False) -> LaunchResult:
    """Spawn *request* as a detached subprocess (fire-and-forget).

    Used by the GUI dashboard to pop a Tkinter child in its own window while
    the dashboard stays interactive. On POSIX we fork a new session so
    closing the dashboard won't SIGHUP the child.
    """
    cmd = build_command(request)
    if dry_run:
        return LaunchResult(cmd, 0, False, "dry-run (no subprocess spawned)")
    try:
        kwargs: dict = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if os.name == "posix":
            kwargs["start_new_session"] = True
        subprocess.Popen(list(cmd), **kwargs)
    except FileNotFoundError as exc:
        return LaunchResult(
            cmd, 127, False,
            f"Executable not found: {exc.filename or cmd[0]}.",
        )
    return LaunchResult(cmd, 0, True, "Launched in background.")


def format_command(cmd: Tuple[str, ...]) -> str:
    """Shell-quote *cmd* for display in the UI."""
    return " ".join(shlex.quote(c) for c in cmd)
