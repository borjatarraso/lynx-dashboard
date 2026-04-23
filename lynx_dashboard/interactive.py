"""Interactive REPL for the Lynx Dashboard.

Mirrors the UX vocabulary of every other suite REPL — ``help`` lists commands,
``about`` shows the license, ``quit`` / ``q`` exits, arrow keys walk history.
Launchables can be reached by name, shortcut key, or full command.
"""

from __future__ import annotations

try:
    import readline as _readline  # noqa: F401 — arrow-key history on POSIX
except ImportError:
    pass

from rich.console import Console
from rich.panel import Panel

from lynx_investor_core.about import render_about_compact

from lynx_dashboard import get_about_text
from lynx_dashboard.display import (
    render_agents_panel,
    render_apps_panel,
    render_banner,
    render_keybindings,
    render_recommendation,
)
from lynx_dashboard.easter import pick_easter_egg
from lynx_dashboard.launcher import LaunchRequest, build_command, format_command, launch_blocking
from lynx_dashboard.recommender import recommend_for_query
from lynx_dashboard.registry import ALL_LAUNCHABLES, AGENTS, APPS, Launchable, by_name

console = Console()


MENU = """
[bold cyan]Launch:[/]
  [bold]f | fundamental[/]          Launch Lynx Fundamental
  [bold]c | compare[/]              Launch Lynx Compare
  [bold]p | portfolio[/]            Launch Lynx Portfolio
  [bold]1-9, 0, -[/]                Launch a sector agent (see 'agents')
  [bold]launch[/] <name> [ticker]   Launch any app/agent by name

[bold cyan]Discover:[/]
  [bold]apps[/]                     Show the three core apps
  [bold]agents[/]                   Show the 11 sector-specialized agents
  [bold]list[/]                     Show everything
  [bold]info[/] <name>              Detailed info for an app or agent
  [bold]recommend[/] <ticker>       Recommend an agent for a company
  [bold]keys | keybindings[/]       Show all keybindings

[bold cyan]Modes:[/]
  [bold]mode[/]                     Show current launch mode
  [bold]mode[/] <interactive|tui|gui|console>   Change launch mode
  [bold]run-mode[/] <production|testing>        Toggle production/testing flag

[bold cyan]Other:[/]
  [bold]about[/]                    Show about / license
  [bold]help, ?[/]                  Show this menu
  [bold]quit, q[/]                  Exit
"""


def run_interactive(default_mode: str = "interactive", run_mode: str = "production") -> None:
    render_banner(console)
    console.print(Panel(MENU, border_style="cyan", title="[bold]Interactive Mode[/]"))
    state = {"mode": default_mode, "run_mode": run_mode}

    while True:
        try:
            prompt = (
                f"\n[bold cyan]lynx-dashboard[/] [dim]({state['mode']}/{state['run_mode']})[/] "
            )
            console.print(prompt, end="")
            raw = input().strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye![/]")
            break
        if not raw:
            continue

        parts = raw.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd in ("quit", "exit", "q"):
            console.print("[dim]Goodbye![/]")
            return
        if cmd in ("help", "?"):
            console.print(MENU)
            continue
        if cmd == "keys" or cmd == "keybindings":
            console.print(render_keybindings())
            continue
        if cmd == "apps":
            console.print(render_apps_panel())
            continue
        if cmd == "agents":
            console.print(render_agents_panel())
            continue
        if cmd == "list":
            console.print(render_apps_panel())
            console.print(render_agents_panel())
            continue
        if cmd == "about":
            render_about_compact(console, get_about_text())
            continue
        if cmd == "info":
            if not arg:
                console.print("[yellow]Usage: info <name>  (e.g. info energy, info fundamental)[/]")
                continue
            target = by_name(arg)
            if target is None:
                console.print(f"[red]No launchable matches '{arg}'.[/]")
                continue
            _render_info(target)
            continue
        # The "lynx" code word is a hidden trigger for the easter egg. It is
        # intentionally NOT advertised in the menu.
        if cmd == "lynx":
            console.print(Panel(pick_easter_egg(), border_style="green", title="[bold green]A wild lynx appears![/]"))
            continue
        if cmd == "mode":
            if not arg:
                console.print(f"[dim]Current mode:[/] [bold]{state['mode']}[/]")
                continue
            if arg in ("interactive", "tui", "gui", "console"):
                state["mode"] = arg
                console.print(f"[green]Launch mode set to {arg}.[/]")
            else:
                console.print(
                    "[yellow]Mode must be one of: interactive, tui, gui, console.[/]"
                )
            continue
        if cmd == "run-mode":
            if not arg:
                console.print(f"[dim]Current run mode:[/] [bold]{state['run_mode']}[/]")
                continue
            if arg in ("production", "testing"):
                state["run_mode"] = arg
                console.print(f"[green]Run mode set to {arg}.[/]")
            else:
                console.print("[yellow]Run mode must be 'production' or 'testing'.[/]")
            continue
        if cmd == "recommend":
            if not arg:
                console.print("[yellow]Usage: recommend <TICKER|NAME|ISIN>[/]")
                continue
            rec = recommend_for_query(arg)
            console.print(render_recommendation(rec))
            if rec.has_match:
                ticker = rec.profile.ticker or rec.query or ""
                prompt_text = (
                    f"[bold cyan]Launch[/] [bold]{rec.primary.name}[/] "
                    + (f"for [bold]{ticker}[/] " if ticker else "")
                    + "now? [Y/n]"
                )
                try:
                    console.print(prompt_text, end=" ")
                    answer = input().strip().lower()
                except (EOFError, KeyboardInterrupt):
                    continue
                if answer in ("", "y", "yes"):
                    _do_launch(rec.primary, state, ticker or None)
                else:
                    console.print(
                        f"[dim]Skipped. Run [bold]launch {rec.primary.command}"
                        + (f" {ticker}" if ticker else "")
                        + "[/][dim] anytime to jump in.[/]"
                    )
            continue
        if cmd == "launch":
            if not arg:
                console.print("[yellow]Usage: launch <name> [ticker][/]")
                continue
            launch_parts = arg.split(maxsplit=1)
            target = by_name(launch_parts[0])
            if target is None:
                console.print(f"[red]No launchable matches '{launch_parts[0]}'.[/]")
                continue
            ticker = launch_parts[1] if len(launch_parts) > 1 else None
            _do_launch(target, state, ticker)
            continue

        # Shortcut keys — 'f', 'c', 'p', '1'..'9', '0', 'minus' / '-'
        if len(cmd) <= 4:
            key = "minus" if cmd == "-" else cmd
            target = next((t for t in ALL_LAUNCHABLES if t.keybinding and t.keybinding == key), None)
            if target is not None:
                ticker = arg or None
                _do_launch(target, state, ticker)
                continue

        # Otherwise try fuzzy lookup by name.
        target = by_name(cmd)
        if target is not None:
            _do_launch(target, state, arg or None)
            continue

        console.print(f"[red]Unknown command:[/] {cmd}   [dim](try 'help')[/]")


def _render_info(item: Launchable) -> None:
    """Print the detailed info block for a launchable."""
    parts: list[str] = [
        f"[bold blue]{item.name}[/]  [italic {item.color}]— {item.tagline}[/]",
        "",
        "[bold magenta]What it does[/]",
        item.details or item.description,
    ]
    if item.data_sources:
        parts.extend(["", "[bold magenta]Data sources[/]"])
        for source in item.data_sources:
            parts.append(f"  • {source}")
    if item.specialization:
        parts.extend(["", "[bold magenta]What makes it specialized[/]", item.specialization])
    parts.extend(
        [
            "",
            "[bold magenta]At a glance[/]",
            f"  Command:    [bold]{item.command}[/]",
            f"  Package:    {item.package}",
            f"  Keybinding: [bold]{(item.keybinding if item.keybinding != 'minus' else '-') or '—'}[/]",
            f"  Modes:      {', '.join(sorted(item.modes)) if item.modes else '—'}",
        ]
    )
    if item.example_tickers:
        parts.append(f"  Try with:   {', '.join(item.example_tickers)}")
    console.print(Panel("\n".join(parts), border_style=item.color, title=f"[bold]Info — {item.name}[/]"))


def _do_launch(target, state: dict, ticker) -> None:
    request = LaunchRequest(
        target=target,
        mode=state["mode"],
        ticker=ticker,
        run_mode=state["run_mode"],
    )
    cmd_str = format_command(build_command(request))
    console.print(f"[dim]$ {cmd_str}[/]")
    result = launch_blocking(request)
    if not result.launched:
        console.print(f"[red]{result.message}[/]")
    else:
        console.print(f"[green]Back in dashboard. {result.message}[/]")
