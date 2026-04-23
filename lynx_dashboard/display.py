"""Rich-based console renderers for the dashboard.

Used by the default console mode and reused from the interactive REPL.
"""

from __future__ import annotations

from typing import Iterable, Sequence

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from lynx_dashboard.recommender import Recommendation
from lynx_dashboard.registry import AGENTS, APPS, Launchable

__all__ = [
    "render_banner",
    "render_apps_panel",
    "render_agents_panel",
    "render_launchables_table",
    "render_recommendation",
    "render_keybindings",
    "render_dashboard",
    "render_info",
]


def render_info(item: Launchable) -> Panel:
    """Detailed info panel for a single launchable — used by --info and REPL."""
    parts = [
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
    keybinding = item.keybinding
    key_display = "-" if keybinding == "minus" else (keybinding or "—")
    parts.extend(
        [
            "",
            "[bold magenta]At a glance[/]",
            f"  Command:    [bold]{item.command}[/]",
            f"  Package:    {item.package}",
            f"  Keybinding: [bold]{key_display}[/]",
            f"  Modes:      {', '.join(sorted(item.modes)) if item.modes else '—'}",
        ]
    )
    if item.example_tickers:
        parts.append(f"  Try with:   {', '.join(item.example_tickers)}")
    return Panel(
        "\n".join(parts),
        border_style=item.color,
        title=f"[bold]Info — {item.name}[/]",
    )


def render_banner(console: Console) -> None:
    from lynx_dashboard import get_logo_ascii, APP_NAME, APP_TAGLINE, SUITE_LABEL
    logo = get_logo_ascii()
    if logo:
        console.print(Panel(f"[bold green]{logo}[/]", border_style="green", padding=(0, 2)))
    console.print(Panel(
        f"[bold blue]{APP_NAME}[/]\n"
        f"[dim]{APP_TAGLINE}[/]\n"
        f"[dim]Part of {SUITE_LABEL}[/]",
        border_style="blue",
        padding=(0, 2),
    ))


def _launchable_row(item: Launchable) -> Sequence[str]:
    key = item.keybinding or "-"
    return (
        f"[bold]{key}[/]",
        f"[bold {item.color}]{item.name}[/]",
        item.tagline,
        item.command,
    )


def render_launchables_table(title: str, items: Iterable[Launchable]) -> Table:
    table = Table(title=f"[bold]{title}[/]", title_style="cyan", expand=True)
    table.add_column("Key", style="dim", width=5, justify="center")
    table.add_column("Name", style="bold", min_width=22)
    table.add_column("What it does", overflow="fold")
    table.add_column("Command", style="dim", min_width=22)
    for item in items:
        table.add_row(*_launchable_row(item))
    return table


def render_apps_panel() -> Panel:
    return Panel(
        render_launchables_table("Core Apps", APPS),
        border_style="blue",
        padding=(0, 1),
    )


def render_agents_panel() -> Panel:
    return Panel(
        render_launchables_table("Sector-Specialized Agents", AGENTS),
        border_style="magenta",
        padding=(0, 1),
    )


def render_keybindings() -> Panel:
    table = Table(title="[bold]Keybindings[/]", title_style="cyan", expand=True)
    table.add_column("Key", style="bold", width=14)
    table.add_column("Action")
    table.add_row("f / c / p", "Launch Fundamental / Compare / Portfolio")
    table.add_row("1 … 9 0 -", "Launch a sector agent (by number shown)")
    table.add_row("r", "Recommend an agent for a company")
    table.add_row("l", "List all launchables")
    table.add_row("a", "About dialog")
    table.add_row("h, ?", "Help / keybindings")
    table.add_row("e", "Easter egg")
    table.add_row("PgUp / PgDn", "Scroll long output")
    table.add_row("Esc", "Close modal / go back to dashboard")
    table.add_row("q, Ctrl+Q", "Quit")
    return Panel(table, border_style="cyan", padding=(0, 1))


def render_recommendation(rec: Recommendation) -> Panel:
    if not rec.query:
        return Panel(
            "[yellow]No company provided.[/]\n"
            "[dim]Try a ticker (AAPL), an ISIN, or a company name.[/]",
            title="[bold]Recommend[/]",
            border_style="yellow",
        )
    header_parts = [f"[bold]{rec.query}[/]"]
    if rec.profile.name and rec.profile.name != rec.query:
        header_parts.append(f"[dim]({rec.profile.name})[/]")
    header = "  ".join(header_parts)

    profile_bits = []
    if rec.profile.sector:
        profile_bits.append(f"sector: [bold]{rec.profile.sector}[/]")
    if rec.profile.industry:
        profile_bits.append(f"industry: [bold]{rec.profile.industry}[/]")
    profile_line = "  •  ".join(profile_bits) if profile_bits else "[dim]no profile data[/]"

    if not rec.has_match:
        body = (
            f"{header}\n{profile_line}\n\n"
            f"[yellow]{rec.reason}[/]\n"
            f"[dim]Tip: try one of the three core apps — they work on any company.[/]"
        )
        return Panel(body, title="[bold]Recommend[/]", border_style="yellow")

    primary = rec.primary
    assert primary is not None
    body = [
        header,
        profile_line,
        "",
        f"[bold green]Top pick:[/] [bold {primary.color}]{primary.name}[/] "
        f"[dim]({primary.command})[/]",
        f"    {primary.tagline}",
    ]
    if rec.alternates:
        body.append("")
        body.append("[bold]Also relevant:[/]")
        for alt in rec.alternates:
            body.append(
                f"  • [bold {alt.color}]{alt.name}[/] [dim]({alt.command})[/] — {alt.tagline}"
            )
    body.append("")
    body.append(f"[dim]{rec.reason}[/]")
    return Panel(
        "\n".join(body),
        title="[bold]Recommend[/]",
        border_style="green",
    )


def render_dashboard(console: Console) -> None:
    """Top-level console view: banner + apps + agents + keybindings."""
    render_banner(console)
    console.print(render_apps_panel())
    console.print(render_agents_panel())
    console.print(render_keybindings())
    console.print(
        Panel(
            "[dim]Use [bold]lynx-dashboard --help[/] for the full argument list, "
            "or [bold]lynx-dashboard -i[/] for interactive mode.[/]",
            border_style="dim",
        )
    )
