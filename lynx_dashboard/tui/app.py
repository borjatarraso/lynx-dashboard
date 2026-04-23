"""Textual TUI dashboard for the Lince Investor Suite.

The TUI is the marquee experience: a header with the suite logo, tabs for
"Apps", "Agents", "Recommend" (company → agent), and "About", each with a
data-table of every launchable. Every row has a visible Info button as well
as the Enter-to-launch affordance. A footer shows the full keybinding
cheat-sheet.

Launching a child app from the TUI follows a simple protocol:

1. Call ``self.suspend()`` to release the terminal so the child's own TUI /
   CLI can take it over.
2. Run the child with :func:`lynx_dashboard.launcher.launch_blocking`.
3. When the child exits, the suspend context restores the Textual screen and
   we re-render so the user is back in the dashboard.

Modal screens use ``align: center middle`` so they appear dead-center of the
viewport — never pinned to a corner.
"""

from __future__ import annotations

from typing import List, NamedTuple, Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Static,
    TabbedContent,
    TabPane,
)

from lynx_investor_core.about import about_static_text
from lynx_investor_core.pager import PagingAppMixin, tui_paging_bindings

from lynx_dashboard import APP_NAME, get_about_text, get_logo_ascii
from lynx_dashboard.easter import konami_match, pick_easter_egg
from lynx_dashboard.launcher import (
    LaunchRequest,
    build_command,
    format_command,
    launch_blocking,
)
from lynx_dashboard.recommender import recommend_for_query
from lynx_dashboard.registry import AGENTS, APPS, ALL_LAUNCHABLES, Launchable, by_name


def _display_key(key: Optional[str]) -> str:
    if not key:
        return "—"
    return "-" if key == "minus" else key


class LaunchIntent(NamedTuple):
    """A launchable plus the ticker to auto-analyze (may be None)."""
    target: Launchable
    ticker: Optional[str] = None


def _info_body(item: Launchable) -> str:
    """Rich-markup body for the Info modal. Shared by TUI modal + inline pane."""
    lines = [
        f"[bold blue]{item.name}[/]",
        f"[italic {item.color}]{item.tagline}[/]",
        "",
        "[bold magenta]What it does[/]",
        item.details or item.description,
    ]
    if item.data_sources:
        lines.extend(["", "[bold magenta]Data sources[/]"])
        for source in item.data_sources:
            lines.append(f"  • {source}")
    if item.specialization:
        lines.extend(
            [
                "",
                "[bold magenta]What makes it specialized[/]",
                item.specialization,
            ]
        )
    lines.extend(
        [
            "",
            "[bold magenta]At a glance[/]",
            f"  Command:    [bold]{item.command}[/]",
            f"  Package:    {item.package}",
            f"  Keybinding: [bold]{_display_key(item.keybinding)}[/]",
            f"  Modes:      {', '.join(sorted(item.modes)) if item.modes else '—'}",
        ]
    )
    if item.example_tickers:
        lines.append(f"  Try with:   {', '.join(item.example_tickers)}")
    return "\n".join(lines)


# ======================================================================
# Modal: About
# ======================================================================

class AboutModal(ModalScreen):
    """Unified About dialog using core's shared renderer."""
    BINDINGS = [Binding("escape", "dismiss_modal", "Close")]

    def compose(self) -> ComposeResult:
        about = get_about_text()
        with Vertical(id="about-dialog", classes="dialog"):
            yield Label(f"[bold blue]{about['name']}[/]", id="about-title")
            yield VerticalScroll(
                Static(about_static_text(about), id="about-content"),
                id="about-scroll",
            )
            yield Label("[dim]Press Escape to close[/]", id="about-hint")

    def action_dismiss_modal(self) -> None:
        self.dismiss()


# ======================================================================
# Modal: Keybindings / Help
# ======================================================================

class KeybindingsModal(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss_modal", "Close")]

    def compose(self) -> ComposeResult:
        lines = [
            "[bold cyan]Launch shortcuts[/]",
            "  [bold]f[/] / [bold]c[/] / [bold]p[/]   Fundamental / Compare / Portfolio",
            "  [bold]1[/] … [bold]9 0 -[/]   Sector agents (by number shown in the table)",
            "",
            "[bold cyan]Navigation[/]",
            "  [bold]Tab[/] / [bold]Shift+Tab[/]  Switch panels",
            "  [bold]↑ ↓[/] / [bold]PgUp PgDn[/]  Scroll & select rows",
            "  [bold]Enter[/]                Launch selected row",
            "  [bold]i[/]                    Info dialog for selected row",
            "",
            "[bold cyan]Discover[/]",
            "  [bold]r[/]        Recommend an agent for a company (opens dialog)",
            "  [bold]m[/]        Cycle launch mode (interactive → tui → gui → console)",
            "  [bold]t[/]        Toggle run mode (production ↔ testing)",
            "",
            "[bold cyan]Other[/]",
            "  [bold]a[/]        About dialog",
            "  [bold]?[/] / [bold]h[/]     This help screen",
            "  [bold]q[/] / [bold]Ctrl+Q[/] Quit",
        ]
        with Vertical(id="keys-dialog", classes="dialog"):
            yield Label("[bold]Keybindings[/]", id="keys-title")
            yield VerticalScroll(Static("\n".join(lines), id="keys-content"), id="keys-scroll")
            yield Label("[dim]Press Escape to close[/]", id="keys-hint")

    def action_dismiss_modal(self) -> None:
        self.dismiss()


# ======================================================================
# Modal: Info (per-launchable deep dive)
# ======================================================================

class InfoModal(ModalScreen[Optional[LaunchIntent]]):
    """Detailed info for a single app / agent.

    Dismisses with a :class:`LaunchIntent` (target + ticker) when the user
    chooses to launch, or ``None`` when they close without launching. The
    optional *ticker* constructor arg carries the pre-resolved company
    forward: when InfoModal is opened from the Recommend flow, the Launch
    button kicks off analysis for that company directly.
    """
    BINDINGS = [
        Binding("escape", "close_none", "Close"),
        Binding("enter", "close_launch", "Launch", priority=True),
    ]

    def __init__(
        self,
        item: Launchable,
        *,
        ticker: Optional[str] = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._item = item
        self._ticker = ticker

    def compose(self) -> ComposeResult:
        launch_label = f"Launch {self._item.short_name}"
        if self._ticker:
            launch_label += f"   ({self._ticker})"
        with Vertical(id="info-dialog", classes="dialog"):
            yield Label(f"[bold blue]{self._item.name}[/]", id="info-title")
            yield VerticalScroll(
                Static(_info_body(self._item), id="info-content"),
                id="info-scroll",
            )
            with Horizontal(id="info-buttons"):
                yield Button(launch_label, variant="success", id="info-launch")
                yield Button("Close (Esc)", variant="default", id="info-close")

    def action_close_none(self) -> None:
        self.dismiss(None)

    def action_close_launch(self) -> None:
        self.dismiss(LaunchIntent(self._item, self._ticker))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "info-launch":
            self.dismiss(LaunchIntent(self._item, self._ticker))
        elif event.button.id == "info-close":
            self.dismiss(None)


# ======================================================================
# Modal: Recommend
# ======================================================================

class RecommendModal(ModalScreen[Optional[LaunchIntent]]):
    """Prompt for a company and show the top-matching agent.

    Dismisses with a :class:`LaunchIntent` (target + resolved ticker) when
    the user clicks "Launch top pick", so the parent app can auto-analyze
    the recommended company. Returns ``None`` when the user closes
    without launching.
    """
    BINDINGS = [
        Binding("escape", "dismiss_none", "Close"),
        Binding("enter", "submit", "Recommend", priority=True),
    ]

    def __init__(self, *, offline: bool = False, **kwargs) -> None:
        super().__init__(**kwargs)
        self._offline = offline
        self._last: Optional[Launchable] = None
        self._ticker: Optional[str] = None

    def compose(self) -> ComposeResult:
        with Vertical(id="rec-dialog", classes="dialog"):
            yield Label("[bold]Recommend an agent[/]", id="rec-title")
            yield Label(
                "[dim]Enter a ticker, ISIN, or company name. Enter to submit.[/]",
                id="rec-hint",
            )
            yield Input(placeholder="e.g. AAPL", id="rec-input")
            yield VerticalScroll(
                Static("", id="rec-result"),
                id="rec-result-scroll",
            )
            with Horizontal(id="rec-buttons"):
                yield Button("Launch top pick", variant="success", id="rec-launch", disabled=True)
                yield Button("ⓘ Info on top pick", variant="primary", id="rec-info", disabled=True)
                yield Button("Close", variant="default", id="rec-close")

    def on_mount(self) -> None:
        self.query_one("#rec-input", Input).focus()

    def action_submit(self) -> None:
        self._run_query()

    def action_dismiss_none(self) -> None:
        self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._run_query()

    def _run_query(self) -> None:
        query = self.query_one("#rec-input", Input).value.strip()
        if not query:
            return
        # yfinance searches can take 2-5 s for uncommon queries. Push a
        # "Searching…" placeholder so the UI doesn't feel frozen. Textual
        # repaints between event-loop ticks, so the user sees this before
        # the blocking network call starts.
        self.query_one("#rec-result", Static).update(
            f"[dim]Searching Yahoo Finance for [bold]{query}[/] …[/]"
        )
        self.query_one("#rec-launch", Button).disabled = True
        self.query_one("#rec-info", Button).disabled = True
        self.refresh()

        rec = recommend_for_query(query, use_network=not self._offline)
        self._last = rec.primary
        # Prefer the resolved Yahoo symbol; fall back to the raw query so
        # offline matches (which may not set ticker) still propagate.
        self._ticker = rec.profile.ticker or rec.query or None
        lines: List[str] = []
        header = f"[bold]{rec.query}[/]"
        if rec.profile.name and rec.profile.name != rec.query:
            header += f"  [dim]({rec.profile.name})[/]"
        lines.append(header)
        if rec.profile.sector or rec.profile.industry:
            bits = []
            if rec.profile.sector:
                bits.append(f"sector: [bold]{rec.profile.sector}[/]")
            if rec.profile.industry:
                bits.append(f"industry: [bold]{rec.profile.industry}[/]")
            lines.append("  •  ".join(bits))
        lines.append("")
        if rec.has_match:
            primary = rec.primary
            assert primary is not None
            lines.append(
                f"[bold green]Top pick:[/] [bold {primary.color}]{primary.name}[/] "
                f"[dim]({primary.command})[/]"
            )
            lines.append(f"    {primary.tagline}")
            if primary.specialization:
                lines.append(f"    [dim]→[/] {primary.specialization}")
            if rec.alternates:
                lines.append("")
                lines.append("[bold]Also relevant:[/]")
                for alt in rec.alternates:
                    lines.append(
                        f"  • [bold {alt.color}]{alt.name}[/] [dim]({alt.command})[/] — {alt.tagline}"
                    )
        else:
            lines.append(f"[yellow]{rec.reason}[/]")
        lines.append("")
        lines.append(f"[dim]{rec.reason}[/]")
        self.query_one("#rec-result", Static).update("\n".join(lines))
        self.query_one("#rec-launch", Button).disabled = rec.primary is None
        self.query_one("#rec-info", Button).disabled = rec.primary is None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "rec-launch" and self._last is not None:
            self.dismiss(LaunchIntent(self._last, self._ticker))
        elif event.button.id == "rec-info" and self._last is not None:
            # Dismiss this modal first so InfoModal lands on the main screen —
            # stacking them leaves an orphan Recommend modal waiting behind.
            target, ticker = self._last, self._ticker
            self.dismiss(None)
            self.app.push_screen(InfoModal(target, ticker=ticker))
        elif event.button.id == "rec-close":
            self.dismiss(None)


# ======================================================================
# Modal: Easter egg
# ======================================================================

class EasterEggModal(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss_modal", "Close")]

    def compose(self) -> ComposeResult:
        with Vertical(id="egg-dialog", classes="dialog"):
            yield Label("[bold green]A wild lynx appears![/]", id="egg-title")
            yield VerticalScroll(Static(pick_easter_egg(), id="egg-content"), id="egg-scroll")
            yield Label("[dim]Press Escape to close[/]", id="egg-hint")

    def action_dismiss_modal(self) -> None:
        self.dismiss()


# ======================================================================
# Main dashboard app
# ======================================================================

class DashboardApp(PagingAppMixin, App):
    """The main TUI dashboard.

    Mode inheritance: launched children run in TUI mode (so the experience
    stays "TUI-native") unless the user has cycled the launch mode to
    something else with ``m``.
    """

    CSS = """
    Screen {
        layers: base modal;
    }
    #hero-row {
        height: auto;
        padding: 0 1;
    }
    #hero {
        width: 1fr;
        height: auto;
        color: $success;
    }
    #quit-btn {
        width: auto;
        height: 3;
        margin: 0 1;
    }
    #hero-title {
        text-style: bold;
        color: $primary;
    }
    #hero-sub {
        color: $text-muted;
    }
    TabbedContent {
        height: 1fr;
    }
    DataTable {
        height: 1fr;
    }
    #status-bar {
        dock: bottom;
        height: 1;
        background: $boost;
        color: $text;
        padding: 0 1;
    }

    /* Center every modal on screen. */
    ModalScreen {
        align: center middle;
    }
    .dialog {
        background: $surface;
        border: thick $primary;
        padding: 1 2;
        width: 80%;
        max-width: 110;
        height: 80%;
    }
    #rec-input {
        margin: 1 0;
    }
    #rec-result-scroll, #about-scroll, #keys-scroll, #info-scroll, #egg-scroll {
        height: 1fr;
        border: tall $primary-darken-2;
        padding: 1 2;
    }
    #rec-buttons, #info-buttons {
        height: 3;
        align-horizontal: right;
    }
    #rec-buttons Button, #info-buttons Button {
        margin: 0 1;
    }
    #inline-rec-input {
        margin: 1 0;
    }
    #inline-rec-result {
        padding: 1 2;
    }
    .tab-action-bar {
        height: 3;
        padding: 0 1;
    }
    .tab-action-bar Button {
        margin: 0 1 0 0;
    }
    """

    BINDINGS = [
        *tui_paging_bindings(),
        Binding("q", "quit", "Quit", priority=True),
        Binding("ctrl+q", "quit", "Quit", show=False),
        Binding("a", "about", "About"),
        Binding("question_mark", "keys", "Help", show=False),
        Binding("h", "keys", "Keys"),
        Binding("i", "info_focused", "Info"),
        Binding("r", "recommend", "Recommend"),
        Binding("m", "cycle_mode", "Mode"),
        Binding("t", "toggle_run_mode", "Prod/Test"),
        Binding("enter", "launch_focused", "Launch"),
        # Explicit launch shortcuts matching the visible keys.
        Binding("f", "launch_key('f')", show=False),
        Binding("c", "launch_key('c')", show=False),
        Binding("p", "launch_key('p')", show=False),
        Binding("1", "launch_key('1')", show=False),
        Binding("2", "launch_key('2')", show=False),
        Binding("3", "launch_key('3')", show=False),
        Binding("4", "launch_key('4')", show=False),
        Binding("5", "launch_key('5')", show=False),
        Binding("6", "launch_key('6')", show=False),
        Binding("7", "launch_key('7')", show=False),
        Binding("8", "launch_key('8')", show=False),
        Binding("9", "launch_key('9')", show=False),
        Binding("0", "launch_key('0')", show=False),
        Binding("minus", "launch_key('minus')", show=False),
    ]

    _paging_main_view_attr = "_main_scroll"

    _MODE_CYCLE = ("tui", "interactive", "gui", "console")

    def __init__(
        self,
        *,
        run_mode: str = "production",
        offline: bool = False,
        dry_run: bool = False,
        show_splash: bool = True,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._run_mode = run_mode
        self._offline = offline
        self._dry_run = dry_run
        self._show_splash = show_splash
        self._launch_mode = "tui"
        self._keystrokes: List[str] = []
        # Last recommendation from the inline "Recommend" tab, if any. Used
        # by the tab's Launch button to jump straight into the right agent
        # with the resolved company loaded.
        self._inline_recommendation: Optional[LaunchIntent] = None

    # -- layout --------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        # Hero row with the Quit button pinned to the right.
        with Horizontal(id="hero-row"):
            logo = get_logo_ascii()
            hero_bits = []
            if logo:
                hero_bits.append(f"[green]{logo}[/]")
            hero_bits.append(f"[bold blue]{APP_NAME}[/]")
            hero_bits.append("[dim]Unified launcher — select an app or sector agent below[/]")
            yield Static("\n".join(hero_bits), id="hero")
            yield Button("Quit (q)", variant="error", id="quit-btn")

        with TabbedContent(initial="tab-apps"):
            with TabPane("Apps", id="tab-apps"):
                with Vertical():
                    yield self._build_table("apps-table", APPS)
                    with Horizontal(classes="tab-action-bar"):
                        yield Button("Launch (Enter)", variant="success", id="apps-launch-btn")
                        yield Button("ⓘ Info (i)", variant="primary", id="apps-info-btn")
                        yield Button("🔍 Recommend (r)", variant="warning", id="apps-rec-btn")
            with TabPane("Agents", id="tab-agents"):
                with Vertical():
                    yield self._build_table("agents-table", AGENTS)
                    with Horizontal(classes="tab-action-bar"):
                        yield Button("Launch (Enter)", variant="success", id="agents-launch-btn")
                        yield Button("ⓘ Info (i)", variant="primary", id="agents-info-btn")
                        yield Button("🔍 Recommend (r)", variant="warning", id="agents-rec-btn")
            with TabPane("Recommend", id="tab-recommend"):
                with Vertical():
                    yield Label(
                        "[bold]Type a ticker, ISIN, or company name, press Enter.[/]\n"
                        "[dim]The dashboard will resolve the company and suggest the right sector agent.[/]",
                    )
                    yield Input(
                        placeholder="e.g. XOM, AAPL, 'Oroco', 'F3 Uranium', US0378331005",
                        id="inline-rec-input",
                    )
                    yield VerticalScroll(
                        Static("", id="inline-rec-result"),
                        id="inline-rec-scroll",
                    )
                    with Horizontal(classes="tab-action-bar"):
                        yield Button(
                            "Launch top pick",
                            variant="success",
                            id="inline-rec-launch-btn",
                            disabled=True,
                        )
                        yield Button(
                            "ⓘ Info on top pick",
                            variant="primary",
                            id="inline-rec-info-btn",
                            disabled=True,
                        )
                        yield Button("🔍 Open full dialog (r)", variant="warning", id="recommend-open-btn")
            with TabPane("About", id="tab-about"):
                yield VerticalScroll(
                    Static(about_static_text(get_about_text()), id="about-static"),
                    id="about-tab-scroll",
                )
        yield Static(self._status_line(), id="status-bar")
        yield Footer()

    def _build_table(self, table_id: str, items) -> DataTable:
        table = DataTable(id=table_id, zebra_stripes=True, cursor_type="row")
        table.add_columns("Key", "Name", "What it does", "Command")
        for item in items:
            table.add_row(
                _display_key(item.keybinding),
                f"[bold {item.color}]{item.name}[/]",
                item.tagline,
                item.command,
                key=item.command,
            )
        return table

    def on_mount(self) -> None:
        self.title = APP_NAME
        self.sub_title = "Lince Investor Suite"
        self.query_one("#apps-table", DataTable).focus()
        self._main_scroll = self.query_one("#about-tab-scroll", VerticalScroll)
        if self._show_splash:
            # Push the splash on top. It pops itself ~1.5 s later, revealing
            # the fully-composed dashboard underneath.
            from lynx_dashboard.splash import TuiSplashScreen
            self.push_screen(TuiSplashScreen())

    # -- status bar ----------------------------------------------------

    def _status_line(self) -> str:
        return (
            f"[dim]Launch:[/] [bold]{self._launch_mode}[/]   "
            f"[dim]Run:[/] [bold]{self._run_mode}[/]   "
            f"[dim]q[/] quit  "
            f"[dim]a[/] about  "
            f"[dim]r[/] recommend  "
            f"[dim]i[/] info  "
            f"[dim]m[/] mode  "
            f"[dim]t[/] prod/test  "
            f"[dim]?[/] keys"
        )

    def _refresh_status(self) -> None:
        self.query_one("#status-bar", Static).update(self._status_line())

    # -- actions -------------------------------------------------------

    def action_about(self) -> None:
        self.push_screen(AboutModal())

    def action_keys(self) -> None:
        self.push_screen(KeybindingsModal())

    def action_recommend(self) -> None:
        def _after(intent: Optional[LaunchIntent]) -> None:
            if intent is not None:
                self._launch(intent.target, ticker=intent.ticker)
        self.push_screen(RecommendModal(offline=self._offline), _after)

    def action_cycle_mode(self) -> None:
        idx = self._MODE_CYCLE.index(self._launch_mode) if self._launch_mode in self._MODE_CYCLE else 0
        self._launch_mode = self._MODE_CYCLE[(idx + 1) % len(self._MODE_CYCLE)]
        self._refresh_status()
        self.notify(f"Launch mode: {self._launch_mode}", severity="information")

    def action_toggle_run_mode(self) -> None:
        self._run_mode = "testing" if self._run_mode == "production" else "production"
        self._refresh_status()
        self.notify(f"Run mode: {self._run_mode}", severity="information")

    def action_launch_key(self, key: str) -> None:
        target = next((t for t in ALL_LAUNCHABLES if t.keybinding == key), None)
        if target is not None:
            self._launch(target)

    def action_launch_focused(self) -> None:
        target = self._focused_launchable()
        if target is not None:
            self._launch(target)

    def action_info_focused(self) -> None:
        target = self._focused_launchable()
        if target is not None:
            self._show_info(target)

    def _focused_launchable(self) -> Optional[Launchable]:
        focused = self.focused
        if isinstance(focused, DataTable):
            try:
                key = focused.coordinate_to_cell_key(focused.cursor_coordinate).row_key
            except Exception:
                return None
            if key is not None and key.value:
                return by_name(key.value)
        return None

    def _show_info(self, item: Launchable, *, ticker: Optional[str] = None) -> None:
        def _after(intent: Optional[LaunchIntent]) -> None:
            if intent is not None:
                self._launch(intent.target, ticker=intent.ticker)
        self.push_screen(InfoModal(item, ticker=ticker), _after)

    # -- easter egg sequence tracking ---------------------------------

    def on_key(self, event) -> None:
        self._keystrokes.append(event.key)
        if len(self._keystrokes) > 12:
            self._keystrokes = self._keystrokes[-12:]
        if konami_match(self._keystrokes):
            self._keystrokes.clear()
            self.push_screen(EasterEggModal())

    # -- inline recommend tab ----------------------------------------

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "inline-rec-input":
            return
        query = event.value.strip()
        if not query:
            return

        body = self.query_one("#inline-rec-result", Static)
        launch_btn = self.query_one("#inline-rec-launch-btn", Button)
        info_btn = self.query_one("#inline-rec-info-btn", Button)

        # Immediate feedback — network calls can take a few seconds.
        body.update(f"[dim]Searching Yahoo Finance for [bold]{query}[/] …[/]")
        launch_btn.disabled = True
        info_btn.disabled = True
        self.refresh()

        rec = recommend_for_query(query, use_network=not self._offline)

        resolved_ticker = rec.profile.ticker or rec.query or None
        if rec.primary is not None:
            self._inline_recommendation = LaunchIntent(rec.primary, resolved_ticker)
            launch_btn.label = (
                f"Launch top pick   ({resolved_ticker})"
                if resolved_ticker
                else "Launch top pick"
            )
            info_btn.label = (
                f"ⓘ Info on top pick   ({resolved_ticker})"
                if resolved_ticker
                else "ⓘ Info on top pick"
            )
            launch_btn.disabled = False
            info_btn.disabled = False
        else:
            self._inline_recommendation = None
            launch_btn.label = "Launch top pick"
            info_btn.label = "ⓘ Info on top pick"

        lines = [f"[bold]{rec.query}[/]"]
        if rec.profile.ticker and rec.profile.ticker != rec.query:
            lines.append(f"[dim]resolved to [bold]{rec.profile.ticker}[/][/]")
        if rec.profile.name and rec.profile.name != rec.query:
            lines.append(f"[dim]{rec.profile.name}[/]")
        if rec.profile.sector or rec.profile.industry:
            lines.append(
                "  •  ".join(
                    bit for bit in (
                        f"sector: [bold]{rec.profile.sector}[/]" if rec.profile.sector else "",
                        f"industry: [bold]{rec.profile.industry}[/]" if rec.profile.industry else "",
                    ) if bit
                )
            )
        lines.append("")
        if rec.has_match:
            primary = rec.primary
            assert primary is not None
            lines.append(
                f"[bold green]Top pick:[/] [bold {primary.color}]{primary.name}[/] "
                f"[dim]({primary.command})[/]"
            )
            lines.append(f"    {primary.tagline}")
            if primary.specialization:
                lines.append(f"    [dim]→[/] {primary.specialization}")
            lines.append("")
            launch_hint = (
                f"[dim]Click[/] [bold]Launch top pick[/][dim] — the agent will auto-analyze [/]"
                f"[bold]{resolved_ticker}[/]." if resolved_ticker
                else "[dim]Click[/] [bold]Launch top pick[/][dim] to open the agent.[/]"
            )
            lines.append(launch_hint)
            if rec.alternates:
                lines.append("")
                lines.append("[bold]Also relevant:[/]")
                for alt in rec.alternates:
                    lines.append(
                        f"  • [bold {alt.color}]{alt.name}[/] [dim]({alt.command})[/] — {alt.tagline}"
                    )
        else:
            lines.append(f"[yellow]{rec.reason}[/]")
        body.update("\n".join(lines))

    # -- action-bar button clicks ------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn = event.button.id
        if btn in ("apps-launch-btn", "agents-launch-btn"):
            self.action_launch_focused()
        elif btn in ("apps-info-btn", "agents-info-btn"):
            self.action_info_focused()
        elif btn in ("apps-rec-btn", "agents-rec-btn", "recommend-open-btn"):
            self.action_recommend()
        elif btn == "inline-rec-launch-btn" and self._inline_recommendation is not None:
            intent = self._inline_recommendation
            self._launch(intent.target, ticker=intent.ticker)
        elif btn == "inline-rec-info-btn" and self._inline_recommendation is not None:
            intent = self._inline_recommendation
            self._show_info(intent.target, ticker=intent.ticker)
        elif btn == "quit-btn":
            self.exit()

    # -- core launch -------------------------------------------------

    def _launch(self, target: Launchable, *, ticker: Optional[str] = None) -> None:
        if not target.supports(self._launch_mode):
            self.notify(
                f"{target.name} has no {self._launch_mode} mode — press 'm' to cycle.",
                severity="warning",
            )
            return
        request = LaunchRequest(
            target=target,
            mode=self._launch_mode,
            run_mode=self._run_mode,
            ticker=ticker or None,
        )
        cmd = format_command(build_command(request))
        if self._dry_run:
            self.notify(f"[dry-run] {cmd}", severity="information")
            return
        self.notify(f"Launching {target.command}…", severity="information")
        with self.suspend():
            print(f"$ {cmd}")
            result = launch_blocking(request)
            if not result.launched:
                print(result.message)
                try:
                    input("Press Enter to return to the dashboard…")
                except EOFError:
                    pass
        self.notify(
            f"Back from {target.command}"
            + (f" (exit {result.returncode})" if result.launched else ""),
            severity="information",
        )
