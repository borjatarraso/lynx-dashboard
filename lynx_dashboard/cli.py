"""Command-line interface for lynx-dashboard.

The dashboard is a launcher, not an analyzer, so its CLI looks different from
the rest of the suite: it doesn't force ``-p``/``-t`` (instead accepts them
as pass-through flags) and it has a native ``--recommend`` / ``--launch``
flow so users can stay in the dashboard if they want, or skip straight into
an agent if they don't.
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from rich.console import Console

from lynx_dashboard import (
    APP_NAME,
    APP_TAGLINE,
    SUITE_LABEL,
    __version__,
    get_about_text,
)
from lynx_dashboard.display import render_dashboard, render_info, render_recommendation
from lynx_dashboard.launcher import (
    LaunchRequest,
    build_command,
    format_command,
    launch_blocking,
)
from lynx_dashboard.recommender import recommend_for_query
from lynx_dashboard.registry import ALL_LAUNCHABLES, by_name


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lynx-dashboard",
        description=(
            f"{APP_NAME} — {APP_TAGLINE}.\n"
            "Unified launcher for every app and sector-specialized agent in\n"
            "the Lince Investor Suite. Pick an interface (console / interactive\n"
            "/ TUI / GUI) and the dashboard will launch target apps in that same\n"
            "mode, so transitions feel native."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  lynx-dashboard                       Print apps+agents to the console\n"
            "  lynx-dashboard -i                    Interactive REPL launcher\n"
            "  lynx-dashboard -tui                  Textual dashboard (recommended)\n"
            "  lynx-dashboard -x                    Tkinter dashboard\n"
            "  lynx-dashboard --recommend XOM       Which agent fits XOM?\n"
            "  lynx-dashboard --launch fundamental  Start lynx-fundamental now\n"
            "  lynx-dashboard --launch energy XOM   Start lynx-energy on XOM\n"
            "  lynx-dashboard --list                Machine-readable catalog\n"
            "  lynx-dashboard --about               About / license\n"
        ),
    )

    # Interface mode — mutually exclusive; console is the default.
    ui = parser.add_mutually_exclusive_group()
    ui.add_argument(
        "-i", "--interactive-mode",
        action="store_true", dest="interactive",
        help="Launch the interactive REPL dashboard",
    )
    ui.add_argument(
        "-tui", "--textual-ui",
        action="store_true", dest="tui",
        help="Launch the Textual TUI dashboard",
    )
    ui.add_argument(
        "-x", "--gui",
        action="store_true", dest="gui",
        help="Launch the Tkinter graphical dashboard",
    )
    ui.add_argument(
        "-c", "--console",
        action="store_true", dest="console",
        help="Print the dashboard to the console and exit (default)",
    )

    # Run mode — pass-through when launching.
    parser.add_argument(
        "-p", "--production-mode",
        action="store_const", const="production", dest="run_mode",
        default="production",
        help="Run launched apps in production mode (default)",
    )
    parser.add_argument(
        "-t", "--testing-mode",
        action="store_const", const="testing", dest="run_mode",
        help="Run launched apps in testing mode (isolated data_test/)",
    )

    # Direct operations that short-circuit the UI loop.
    # These four run-once actions are mutually exclusive — combining them is
    # nonsense (which one wins?) and the old implicit precedence silently
    # ignored whichever came second.
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument(
        "--recommend", metavar="TICKER",
        help="Recommend an agent for TICKER / company name and exit",
    )
    actions.add_argument(
        "--info", metavar="NAME",
        help="Show detailed info for an app/agent (e.g. 'energy', 'fundamental') and exit",
    )
    actions.add_argument(
        "--launch", metavar="NAME", nargs="+",
        help="Launch app/agent NAME (optionally followed by ticker args)",
    )
    actions.add_argument(
        "--list", action="store_true",
        help="Print every launchable as a machine-readable table and exit",
    )
    parser.add_argument(
        "--offline", action="store_true",
        help="Skip network calls in the recommender (uses offline ticker hints)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print the command that would run without actually launching it",
    )
    parser.add_argument(
        "--no-splash", action="store_true",
        help="Skip the opening splash animation (also: LYNX_NO_SPLASH=1)",
    )
    parser.add_argument(
        "--json", action="store_true", dest="as_json",
        help="Emit machine-readable JSON for --list / --recommend / --info",
    )
    parser.add_argument(
        "--debug", "--verbose", action="store_true", dest="debug",
        help="Enable verbose logging (also: LYNX_DEBUG=1)",
    )
    parser.add_argument(
        "--clear-history", action="store_true",
        help="Erase the recent-queries history and exit",
    )

    parser.add_argument(
        "--version", action="version",
        version=f"{APP_NAME} v{__version__} — part of {SUITE_LABEL}",
    )
    parser.add_argument("--about", action="store_true", help="Show about / license and exit")
    # Shared --language flag (us / es / it / de / fr / fa).
    try:
        from lynx_investor_core.translations import add_language_argument
        add_language_argument(parser)
    except ImportError:
        pass

    return parser


# ---------------------------------------------------------------------------
# Sub-commands (non-UI short-circuits)
# ---------------------------------------------------------------------------

def _print_about(console: Console) -> None:
    from lynx_investor_core.about import render_about_cli
    render_about_cli(console, get_about_text())


def _print_list(console: Console, *, as_json: bool = False) -> None:
    if as_json:
        import json
        from lynx_dashboard.api import catalog_as_dicts
        print(json.dumps(catalog_as_dicts(), indent=2))
        return
    console.print("# kind\tkey\tcommand\tname\ttagline")
    for item in ALL_LAUNCHABLES:
        console.print(
            f"{item.kind}\t{item.keybinding or '-'}\t{item.command}\t"
            f"{item.name}\t{item.tagline}"
        )


def _do_info(console: Console, args: argparse.Namespace) -> int:
    from lynx_dashboard.registry import by_name
    target = by_name(args.info)
    if target is None:
        if args.as_json:
            import json
            print(json.dumps({"error": f"No launchable matches {args.info!r}"}, indent=2))
        else:
            console.print(
                f"[red]No launchable matches '{args.info}'. Use --list to see all.[/]"
            )
        return 2
    if args.as_json:
        import json
        from lynx_dashboard.api import launchable_as_dict
        print(json.dumps(launchable_as_dict(target), indent=2))
        return 0
    console.print(render_info(target))
    return 0


def _do_recommend(console: Console, args: argparse.Namespace) -> int:
    query = (args.recommend or "").strip()
    if not query:
        console.print(
            "[bold red]Error:[/] --recommend needs a non-empty ticker / "
            "company name (e.g. --recommend AAPL)."
        )
        return 2
    rec = recommend_for_query(query, use_network=not args.offline)
    _record_recommendation(query, rec)
    if args.as_json:
        import json
        from lynx_dashboard.api import recommendation_as_dict
        print(json.dumps(recommendation_as_dict(rec), indent=2))
        return 0 if rec.has_match else 1
    console.print(render_recommendation(rec))
    return 0 if rec.has_match else 1


def _record_recommendation(query: str, rec) -> None:
    """Persist a query to the history store. Silent on any failure —
    history is a convenience, never a correctness feature."""
    try:
        from lynx_dashboard.history import HistoryEntry, HistoryStore
        HistoryStore().record(HistoryEntry(
            query=query,
            ticker=rec.profile.ticker or "",
            sector=rec.profile.sector or "",
            primary=rec.primary.registry_name if rec.primary else "",
        ))
    except Exception:
        pass


def _do_launch(console: Console, args: argparse.Namespace) -> int:
    if not args.launch:
        console.print("[red]--launch requires at least a target name.[/]")
        return 2
    target_query = args.launch[0]
    ticker_args = args.launch[1:]
    target = by_name(target_query)
    if target is None:
        console.print(f"[red]No launchable matches '{target_query}'. Use --list to see all.[/]")
        return 2
    mode = _selected_ui_mode(args) or "console"
    request = LaunchRequest(
        target=target,
        mode=mode,
        ticker=" ".join(ticker_args) if ticker_args else None,
        run_mode=args.run_mode,
    )
    if args.dry_run:
        console.print(format_command(build_command(request)))
        return 0
    console.print(f"[dim]$ {format_command(build_command(request))}[/]")
    result = launch_blocking(request)
    if not result.launched:
        console.print(f"[red]{result.message}[/]")
        return result.returncode or 1
    console.print(f"[green]{result.message}[/]")
    return result.returncode


def _selected_ui_mode(args: argparse.Namespace) -> str:
    if getattr(args, "tui", False):
        return "tui"
    if getattr(args, "gui", False):
        return "gui"
    if getattr(args, "interactive", False):
        return "interactive"
    if getattr(args, "console", False):
        return "console"
    return ""


# ---------------------------------------------------------------------------
# UI loop dispatch
# ---------------------------------------------------------------------------

def _run_tui(args: argparse.Namespace) -> int:
    try:
        from lynx_dashboard.tui.app import DashboardApp
    except ImportError as exc:
        print(f"Textual is required for the TUI dashboard: {exc}", file=sys.stderr)
        return 1
    app = DashboardApp(
        run_mode=args.run_mode,
        offline=args.offline,
        dry_run=args.dry_run,
        show_splash=not _splash_suppressed(args),
    )
    app.run()
    return 0


def _run_gui(args: argparse.Namespace) -> int:
    try:
        from lynx_dashboard.gui.app import run_gui
    except ImportError as exc:
        print(f"Tkinter is required for the GUI dashboard: {exc}", file=sys.stderr)
        return 1
    run_gui(
        run_mode=args.run_mode,
        offline=args.offline,
        dry_run=args.dry_run,
        show_splash=not _splash_suppressed(args),
    )
    return 0


def _run_interactive(args: argparse.Namespace) -> int:
    from lynx_dashboard.interactive import run_interactive
    if not _splash_suppressed(args):
        from lynx_dashboard.splash import run_console_splash
        run_console_splash()
    run_interactive(default_mode="interactive", run_mode=args.run_mode)
    return 0


def _run_console(args: argparse.Namespace) -> int:
    console = Console()
    if not _splash_suppressed(args):
        from lynx_dashboard.splash import run_console_splash
        run_console_splash()
    render_dashboard(console)
    return 0


def _splash_suppressed(args: argparse.Namespace) -> bool:
    from lynx_dashboard.splash import splash_disabled
    return splash_disabled(cli_flag=getattr(args, "no_splash", False))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_cli(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()

    try:
        import argcomplete
        argcomplete.autocomplete(parser)
    except ImportError:
        pass  # argcomplete optional at runtime

    args = parser.parse_args(argv)
    try:
        from lynx_investor_core.translations import apply_args as _apply_lang
        _apply_lang(args)
    except ImportError:
        pass

    # --debug / --verbose is a synonym for LYNX_DEBUG=1 — flips off the
    # stdout/stderr silencers in the recommender so yfinance/Rich output is
    # visible for diagnostics.
    if getattr(args, "debug", False):
        import os as _os
        _os.environ.setdefault("LYNX_DEBUG", "1")

    console = Console()

    if args.clear_history:
        return _do_clear_history(console)
    if args.about:
        _print_about(console)
        return 0
    if args.list:
        _print_list(console, as_json=args.as_json)
        return 0
    if args.info:
        return _do_info(console, args)
    if args.recommend is not None:
        return _do_recommend(console, args)
    if args.launch:
        return _do_launch(console, args)
    if args.tui:
        return _run_tui(args)
    if args.gui:
        return _run_gui(args)
    if args.interactive:
        return _run_interactive(args)
    return _run_console(args)


def _do_clear_history(console: Console) -> int:
    from lynx_dashboard.history import HistoryStore
    store = HistoryStore()
    before = len(store.load())
    store.clear()
    console.print(
        f"[green]Cleared {before} entr{'y' if before == 1 else 'ies'} from history."
        if before else "[dim]History was already empty.[/]"
    )
    return 0
