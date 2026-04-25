"""Tkinter GUI dashboard for the Lince Investor Suite.

Layout
------

* Hero banner with the ASCII logo.
* "Recommend agent for a company" button — front and center, not just in a menu.
* A single 3-column grid shared between the "Core Apps" (one row of 3) and the
  "Sector Agents" (4 rows, 3 · 3 · 3 · 2). Columns use ``uniform="launch-col"``
  so the three app buttons line up with the three columns of agent buttons
  above/below, regardless of label length.
* Every card has a **Launch** button and an **ⓘ Info** button; Info opens a
  dialog with the longer description, data sources, and (for agents) the
  specialization that makes it sector-aware.

Readability
-----------

Button hover colors go through ``ttk.Style.map`` so the ``active`` state
stays dark-background / light-foreground — no more unreadable white-on-white.

Dialogs
-------

Every modal (About, Info, Keybindings, Recommend, Easter egg) is centered on
the dashboard window via an explicit geometry calculation; About uses a
fixed-width Text widget with ``wrap=tk.NONE`` so the ASCII logo renders in
full without wrapping.

Transitions
-----------

Launching a TUI/interactive/console child from the GUI can't inherit our
(non-existent) controlling terminal, so we open the child in a newly-spawned
terminal emulator via :func:`_spawn_in_terminal`. GUI→GUI stays detached
(new window, dashboard keeps running). When the child closes, the dashboard
is still alive and focused.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Iterable, List, NamedTuple, Optional, Tuple

from lynx_investor_core.pager import bind_tk_paging

from lynx_dashboard import APP_NAME, APP_TAGLINE, SUITE_LABEL, get_about_text, get_logo_ascii
from lynx_dashboard.easter import pick_easter_egg
from lynx_dashboard.history import HistoryEntry, HistoryStore
from lynx_dashboard.launcher import (
    LaunchRequest,
    build_command,
    format_command,
    launch_detached,
)
from lynx_dashboard.recommender import recommend_for_query
from lynx_dashboard.registry import AGENTS, APPS, Launchable
from lynx_dashboard import icons as icon_gen


# Root of the package — used to resolve img/*.png files the same way every
# other app in the suite resolves theirs (parent.parent.parent = checkout root).
_PACKAGE_ROOT = Path(__file__).resolve().parent.parent.parent


def _logo_path(name: str) -> Optional[Path]:
    """Return the absolute path to img/<name> if it exists, else None."""
    candidate = _PACKAGE_ROOT / "img" / name
    return candidate if candidate.is_file() else None


def _load_png(parent_widget, filename: str) -> Optional["tk.PhotoImage"]:
    """Load a PNG logo via tk.PhotoImage. Returns None if the file is missing
    or the Tk build can't decode it (pre-8.6 builds lack native PNG support)."""
    path = _logo_path(filename)
    if path is None:
        return None
    try:
        return tk.PhotoImage(master=parent_widget, file=str(path))
    except tk.TclError:
        return None


__all__ = ["run_gui", "DashboardGUI"]


_PALETTE = {
    "bg": "#0f1420",
    "bg_alt": "#151a2b",
    "bg_hover": "#24304d",
    "fg": "#e8ecf1",
    "fg_dim": "#8892a6",
    "accent": "#4da3ff",
    "accent2": "#b46bff",
    "ok": "#46d15f",
    "warn": "#e8b84c",
    "danger": "#ff6b6b",
}


# ---------------------------------------------------------------------------
# Terminal resolver — used when the GUI launches a TUI / console / interactive
# child. The child needs a real TTY, so we pop a fresh terminal emulator.
# ---------------------------------------------------------------------------

_TERMINAL_CANDIDATES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    # (executable-on-PATH, argv prefix before the command)
    ("x-terminal-emulator", ("-e",)),
    ("gnome-terminal", ("--",)),
    ("konsole", ("-e",)),
    ("xfce4-terminal", ("-e",)),
    ("alacritty", ("-e",)),
    ("kitty", ()),
    ("wezterm", ("start", "--")),
    ("foot", ()),
    ("xterm", ("-e",)),
    ("urxvt", ("-e",)),
)


def _resolve_terminal() -> Optional[Tuple[str, Tuple[str, ...]]]:
    """Return (path, prefix_args) for the first installed terminal, or None."""
    override = os.environ.get("LYNX_TERMINAL")
    if override:
        path = shutil.which(override)
        if path:
            return (path, ())
    for term, prefix in _TERMINAL_CANDIDATES:
        path = shutil.which(term)
        if path:
            return (path, prefix)
    return None


def _build_keep_open_script(cmd_argv: Tuple[str, ...]) -> str:
    """Wrap *cmd_argv* in a shell one-liner that keeps the terminal open.

    The resulting script runs the command, reports the exit code, then waits
    for Enter before closing. That way:

    * If the child launches a TUI and the user quits it cleanly, they see a
      confirmation line and can press Enter to close the terminal (same
      "quit returns to dashboard" model as inside a TUI).
    * If the child exits with an error or cannot start, the exit code is
      visible on screen instead of the terminal blinking closed. That is
      the single biggest usability fix for the GUI→TUI transition.
    """
    inner = shlex.join(cmd_argv)
    return (
        f"{inner}\n"
        f'__lynx_ec=$?\n'
        f'echo\n'
        f'echo "[lynx-dashboard] command exited with code $__lynx_ec"\n'
        f'echo "Press Enter to close this window…"\n'
        f'read -r __lynx_dummy\n'
    )


class SpawnResult(NamedTuple):
    """Result of a terminal-spawn attempt."""
    ok: bool
    terminal: str          # path or name of the terminal that was tried
    command: Tuple[str, ...]  # full argv that was executed
    message: str           # human-readable success / failure message
    stderr: str = ""       # captured stderr from the terminal (empty on success)


def _spawn_in_terminal(cmd_argv: Tuple[str, ...]) -> SpawnResult:
    """Spawn *cmd_argv* inside a detached terminal emulator.

    Tries each candidate terminal in order. For each:

    1. Spawns the terminal with a keep-open shell wrapper.
    2. Waits briefly to detect an immediate failure (e.g. a bad Wayland /
       DBus handshake on ``gnome-terminal``).
    3. Captures stderr — many terminals exit 0 from the client even when
       the underlying server couldn't open a window, so we ALSO look at
       whether anything was printed to stderr.

    Gnome-terminal's client-server model means it exits 0 quickly even on
    success — the actual window runs under ``gnome-terminal-server``.
    That's expected; the keep-open wrapper ensures the user still sees
    the child's output inside the opened window.
    """
    attempts: List[str] = []
    for candidate in _terminal_candidates():
        terminal = candidate[0]
        prefix = candidate[1]
        script = _build_keep_open_script(cmd_argv)
        full = (terminal, *prefix, "sh", "-c", script)
        try:
            proc = subprocess.Popen(
                list(full),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=(os.name == "posix"),
            )
        except (FileNotFoundError, OSError) as exc:
            attempts.append(f"{terminal}: {exc}")
            continue

        # Wait briefly to catch immediate client failures. Most terminals
        # that will open a window survive far past this tick; those that
        # die fast did so because of an env / DBus / display issue.
        try:
            rc = proc.wait(timeout=0.6)
        except subprocess.TimeoutExpired:
            # Still running — this is the normal case for non-client-server
            # terminals (xterm, konsole, alacritty, kitty). Pipes stay with
            # the long-lived child until it exits on its own; that's fine,
            # the child is detached (start_new_session=True) and the OS
            # reaps it when it dies. We explicitly DON'T close the pipes
            # from this side, because that would SIGPIPE the terminal if
            # it later writes anything.
            return SpawnResult(True, terminal, full, f"Launched via {os.path.basename(terminal)}.")

        # Client exited. Drain both pipes so no FDs leak on the way to
        # trying the next candidate. `communicate` is the only safe way
        # to read+close after wait() has already returned.
        try:
            out_bytes, err_bytes = proc.communicate(timeout=0.2)
        except subprocess.TimeoutExpired:
            proc.kill()
            out_bytes, err_bytes = proc.communicate()
        err = err_bytes.decode("utf-8", "replace").strip() if err_bytes else ""

        # For client-server terminals (gnome-terminal) rc=0 is expected:
        # the client handed off to the server and the window is now open.
        # For standalone terminals rc=0 means the window closed quickly,
        # which is abnormal — so we also require empty stderr.
        if rc == 0 and not err:
            return SpawnResult(True, terminal, full, f"Launched via {os.path.basename(terminal)}.")

        attempts.append(
            f"{os.path.basename(terminal)} exited rc={rc}"
            + (f": {err.splitlines()[-1]}" if err else "")
        )
        # Try the next candidate.

    if not attempts:
        return SpawnResult(
            False, "", cmd_argv,
            "No terminal emulator found on PATH. Install one of: "
            "gnome-terminal, konsole, xterm, alacritty, kitty, wezterm, foot "
            "— or set LYNX_TERMINAL to your preferred terminal.",
        )
    return SpawnResult(
        False, "", cmd_argv,
        "All terminal emulators failed to launch the child.\nAttempts:\n  - "
        + "\n  - ".join(attempts),
    )


def _terminal_candidates() -> Iterable[Tuple[str, Tuple[str, ...]]]:
    """Yield (absolute-path, prefix-args) for every installed terminal we can use."""
    override = os.environ.get("LYNX_TERMINAL")
    if override:
        path = shutil.which(override)
        if path:
            yield (path, ())
    for term, prefix in _TERMINAL_CANDIDATES:
        path = shutil.which(term)
        if path:
            yield (path, prefix)


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

class DashboardGUI(tk.Tk):
    _CARD_WIDTH = 330  # px — minimum column width so names never squash

    def __init__(
        self,
        *,
        run_mode: str = "production",
        offline: bool = False,
        dry_run: bool = False,
    ) -> None:
        super().__init__()
        self._run_mode = tk.StringVar(value=run_mode)
        self._launch_mode = tk.StringVar(value="gui")
        self._offline = offline
        self._dry_run = dry_run
        self._status_var = tk.StringVar()
        # Ensure domain icons exist on disk; silently noops if PIL is missing.
        try:
            icon_gen.generate_all()
        except Exception:
            pass
        # Hold PhotoImage refs so Tk doesn't garbage-collect them.
        self._icon_images: dict[str, tk.PhotoImage] = {}
        # Lazy — constructed the first time Recommend dialog opens so tests
        # that construct DashboardGUI in a temp dir don't accidentally touch
        # the user's real history file.
        self._history: Optional[HistoryStore] = None

        self.title(APP_NAME)
        self.geometry("1200x900")
        self.configure(bg=_PALETTE["bg"])
        self._apply_style()
        self._build_menu()
        self._build_layout()
        self._install_bindings()
        self._refresh_status()

    # ---- styling ----------------------------------------------------

    def _apply_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=_PALETTE["bg"])
        style.configure("Alt.TFrame", background=_PALETTE["bg_alt"])
        style.configure("TLabel", background=_PALETTE["bg"], foreground=_PALETTE["fg"])
        style.configure(
            "Hero.TLabel",
            background=_PALETTE["bg"],
            foreground=_PALETTE["accent"],
            font=("TkDefaultFont", 16, "bold"),
        )
        style.configure(
            "Sub.TLabel",
            background=_PALETTE["bg"],
            foreground=_PALETTE["fg_dim"],
            font=("TkDefaultFont", 10),
        )
        style.configure(
            "Section.TLabel",
            background=_PALETTE["bg"],
            foreground=_PALETTE["accent2"],
            font=("TkDefaultFont", 12, "bold"),
        )
        style.configure(
            "Title.TLabel",
            background=_PALETTE["bg_alt"],
            foreground=_PALETTE["accent"],
            font=("TkDefaultFont", 11, "bold"),
            padding=(10, 4, 10, 1),
        )
        style.configure(
            "Tag.TLabel",
            background=_PALETTE["bg_alt"],
            foreground=_PALETTE["fg_dim"],
            padding=(10, 0, 10, 2),
            wraplength=self._CARD_WIDTH - 20,
        )

        # Launch button — dark bg, light fg, and hover stays legible.
        style.configure(
            "Launch.TButton",
            padding=(10, 4),
            background=_PALETTE["bg_alt"],
            foreground=_PALETTE["fg"],
            bordercolor=_PALETTE["accent"],
            focusthickness=1,
            focuscolor=_PALETTE["accent"],
            font=("TkDefaultFont", 10, "bold"),
        )
        style.map(
            "Launch.TButton",
            background=[
                ("active", _PALETTE["bg_hover"]),
                ("pressed", _PALETTE["accent"]),
                ("disabled", _PALETTE["bg_alt"]),
            ],
            foreground=[
                ("active", _PALETTE["fg"]),
                ("pressed", _PALETTE["bg"]),
                ("disabled", _PALETTE["fg_dim"]),
            ],
            bordercolor=[("active", _PALETTE["accent"])],
        )

        # Info button — compact, readable, purple accent.
        style.configure(
            "Info.TButton",
            padding=(8, 4),
            background=_PALETTE["bg_alt"],
            foreground=_PALETTE["accent2"],
            font=("TkDefaultFont", 10, "bold"),
        )
        style.map(
            "Info.TButton",
            background=[
                ("active", _PALETTE["bg_hover"]),
                ("pressed", _PALETTE["accent2"]),
            ],
            foreground=[
                ("active", _PALETTE["accent2"]),
                ("pressed", _PALETTE["bg"]),
            ],
        )

        # Hero-level "Recommend" button — prominent but compact (sits in the
        # hero row, not its own bar).
        style.configure(
            "Recommend.TButton",
            padding=(14, 6),
            background=_PALETTE["accent"],
            foreground=_PALETTE["bg"],
            font=("TkDefaultFont", 10, "bold"),
        )
        style.map(
            "Recommend.TButton",
            background=[
                ("active", _PALETTE["accent2"]),
                ("pressed", _PALETTE["accent2"]),
            ],
            foreground=[
                ("active", _PALETTE["bg"]),
                ("pressed", _PALETTE["bg"]),
            ],
        )

        style.configure(
            "Dialog.TButton",
            padding=(10, 6),
            background=_PALETTE["bg_alt"],
            foreground=_PALETTE["fg"],
        )
        style.map(
            "Dialog.TButton",
            background=[
                ("active", _PALETTE["bg_hover"]),
                ("pressed", _PALETTE["accent"]),
            ],
            foreground=[
                ("active", _PALETTE["fg"]),
                ("pressed", _PALETTE["bg"]),
            ],
        )

        style.configure(
            "Status.TLabel",
            background=_PALETTE["bg_alt"],
            foreground=_PALETTE["fg_dim"],
            padding=(10, 5),
        )

        # Top-right Quit button — red accent on hover so users can't miss
        # the dedicated "exit the program" affordance.
        style.configure(
            "Quit.TButton",
            padding=(14, 7),
            background=_PALETTE["bg_alt"],
            foreground=_PALETTE["danger"],
            font=("TkDefaultFont", 10, "bold"),
        )
        style.map(
            "Quit.TButton",
            background=[
                ("active", _PALETTE["danger"]),
                ("pressed", _PALETTE["danger"]),
            ],
            foreground=[
                ("active", _PALETTE["bg"]),
                ("pressed", _PALETTE["bg"]),
            ],
        )

        # Compact "pill"-style buttons used by the Recommend dialog.
        style.configure(
            "Pill.TButton",
            padding=(8, 3),
            background=_PALETTE["bg_alt"],
            foreground=_PALETTE["accent"],
            font=("TkFixedFont", 9, "bold"),
        )
        style.map(
            "Pill.TButton",
            background=[
                ("active", _PALETTE["bg_hover"]),
                ("pressed", _PALETTE["accent"]),
            ],
            foreground=[
                ("active", _PALETTE["accent"]),
                ("pressed", _PALETTE["bg"]),
            ],
        )

    # ---- menu -------------------------------------------------------

    def _build_menu(self) -> None:
        menu_opts = dict(
            bg=_PALETTE["bg_alt"],
            fg=_PALETTE["fg"],
            activebackground=_PALETTE["bg_hover"],
            activeforeground=_PALETTE["fg"],
            borderwidth=0,
        )
        menubar = tk.Menu(self, **menu_opts)
        file_menu = tk.Menu(menubar, tearoff=0, **menu_opts)
        file_menu.add_command(
            label="Recommend agent for a company…   Ctrl+R",
            command=self._open_recommend,
        )
        file_menu.add_separator()
        file_menu.add_command(label="Quit   Ctrl+Q", command=self._quit)
        menubar.add_cascade(label="File", menu=file_menu)

        launch_menu = tk.Menu(menubar, tearoff=0, **menu_opts)
        for app in APPS:
            launch_menu.add_command(
                label=f"{app.name}   ({app.command})",
                command=lambda a=app: self._launch(a),
            )
        launch_menu.add_separator()
        for agent in AGENTS:
            launch_menu.add_command(
                label=f"{agent.name}   ({agent.command})",
                command=lambda a=agent: self._launch(a),
            )
        menubar.add_cascade(label="Launch", menu=launch_menu)

        view_menu = tk.Menu(menubar, tearoff=0, **menu_opts)
        view_menu.add_radiobutton(label="Launch children in TUI", variable=self._launch_mode, value="tui")
        view_menu.add_radiobutton(label="Launch children in GUI", variable=self._launch_mode, value="gui")
        view_menu.add_radiobutton(label="Launch children in interactive", variable=self._launch_mode, value="interactive")
        view_menu.add_radiobutton(label="Launch children in console", variable=self._launch_mode, value="console")
        view_menu.add_separator()
        view_menu.add_radiobutton(label="Production mode", variable=self._run_mode, value="production")
        view_menu.add_radiobutton(label="Testing mode", variable=self._run_mode, value="testing")
        menubar.add_cascade(label="View", menu=view_menu)

        help_menu = tk.Menu(menubar, tearoff=0, **menu_opts)
        help_menu.add_command(label="Keybindings…   F1", command=self._open_keys)
        help_menu.add_command(label="About…", command=self._open_about)
        # Easter egg is intentionally NOT listed here. It's still reachable
        # through the hidden trigger documented in docs/KEYBINDINGS.md.
        menubar.add_cascade(label="Help", menu=help_menu)

        self.config(menu=menubar)

    # ---- layout -----------------------------------------------------

    def _build_layout(self) -> None:
        container = ttk.Frame(self)
        container.pack(fill=tk.BOTH, expand=True)

        self._build_hero(container)
        self._build_grid_body(container)
        self._build_status_bar()

    def _build_hero(self, parent: ttk.Frame) -> None:
        hero = ttk.Frame(parent)
        hero.pack(fill=tk.X, padx=14, pady=(10, 6))

        # Single hero row: logo — titles — (stretchable spacer for centering) —
        # Recommend — Quit. The Recommend button sits between the titles and
        # Quit, keeps its natural width, and is vertically centered in the
        # row by pack's default anchor behaviour.
        row = ttk.Frame(hero)
        row.pack(fill=tk.X)

        # Quit button — packed first with side=RIGHT so it always claims the
        # right edge regardless of logo/title widths.
        ttk.Button(
            row,
            text="Quit   (Ctrl+Q)",
            style="Quit.TButton",
            command=self._quit,
        ).pack(side=tk.RIGHT, padx=(10, 0), pady=4)

        # Recommend button — packed with side=RIGHT AFTER Quit, so it lands
        # just to the left of Quit. No `fill`, so it shrinks to the natural
        # width of its text and pad — much less wide than before.
        ttk.Button(
            row,
            text="🔍  Recommend an Agent   (Ctrl+R)",
            style="Recommend.TButton",
            command=self._open_recommend,
        ).pack(side=tk.RIGHT, padx=(10, 10), pady=4)

        self._hero_logo_image = (
            _load_png(self, "logo_sm_half_green.png")
            or _load_png(self, "logo_sm_quarter_green.png")
            or _load_png(self, "logo_sm_green.png")
        )
        if self._hero_logo_image is not None:
            tk.Label(
                row,
                image=self._hero_logo_image,
                bg=_PALETTE["bg"],
                borderwidth=0,
                highlightthickness=0,
            ).pack(side=tk.LEFT, padx=(0, 14), pady=4)
        else:
            logo = get_logo_ascii()
            if logo:
                tk.Label(
                    row,
                    text=logo,
                    bg=_PALETTE["bg"],
                    fg=_PALETTE["ok"],
                    font=("TkFixedFont", 8),
                    justify=tk.LEFT,
                ).pack(side=tk.LEFT, padx=(0, 14))

        titles = ttk.Frame(row)
        titles.pack(side=tk.LEFT, anchor="w", fill=tk.X, expand=True)
        ttk.Label(titles, text=APP_NAME, style="Hero.TLabel").pack(anchor="w")
        ttk.Label(titles, text=APP_TAGLINE, style="Sub.TLabel").pack(anchor="w")
        ttk.Label(titles, text=f"Part of {SUITE_LABEL}", style="Sub.TLabel").pack(anchor="w")

    def _build_grid_body(self, parent: ttk.Frame) -> None:
        outer = ttk.Frame(parent)
        outer.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 2))

        canvas = tk.Canvas(outer, bg=_PALETTE["bg"], highlightthickness=0)
        # Scrollbar is packed on demand — only visible when the content
        # actually overflows the viewport. Showing it unconditionally is
        # visual noise whenever the window is tall enough for all cards.
        scrollbar = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        inner = ttk.Frame(canvas)
        inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _resize(_event=None) -> None:
            bbox = canvas.bbox("all")
            if bbox is None:
                return
            canvas.configure(scrollregion=bbox)
            canvas.itemconfigure(inner_id, width=canvas.winfo_width())
            content_h = bbox[3] - bbox[1]
            view_h = canvas.winfo_height()
            # Small tolerance so rounding doesn't flicker the scrollbar.
            if content_h <= view_h + 2:
                scrollbar.pack_forget()
            else:
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        inner.bind("<Configure>", _resize)
        canvas.bind("<Configure>", _resize)
        bind_tk_paging(self, canvas)

        # One unified 3-column grid for apps+agents. uniform="launch-col"
        # keeps column widths locked even across the two section dividers,
        # so the three app buttons line up with the three-wide agent rows.
        grid = ttk.Frame(inner)
        grid.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        for col in range(3):
            grid.columnconfigure(col, weight=1, uniform="launch-col", minsize=self._CARD_WIDTH)

        row_cursor = 0

        # Core apps header + cards.
        ttk.Label(grid, text="Core Apps", style="Section.TLabel").grid(
            row=row_cursor, column=0, columnspan=3, sticky="w", padx=6, pady=(2, 2),
        )
        row_cursor += 1
        for idx, item in enumerate(APPS):
            self._build_card(grid, item, row=row_cursor + idx // 3, col=idx % 3)
        row_cursor += (len(APPS) + 2) // 3

        # Agents header + cards.
        ttk.Label(grid, text="Sector-Specialized Agents", style="Section.TLabel").grid(
            row=row_cursor, column=0, columnspan=3, sticky="w", padx=6, pady=(8, 2),
        )
        row_cursor += 1
        for idx, item in enumerate(AGENTS):
            self._build_card(grid, item, row=row_cursor + idx // 3, col=idx % 3)

    def _load_icon(self, command: str) -> Optional[tk.PhotoImage]:
        """Load (and cache) the PNG icon for *command*. Returns None on failure."""
        if command in self._icon_images:
            return self._icon_images[command]
        try:
            path = icon_gen.get_icon_path(command)
        except Exception:
            return None
        if path is None or not path.exists():
            return None
        try:
            img = tk.PhotoImage(master=self, file=str(path))
        except tk.TclError:
            return None
        self._icon_images[command] = img
        return img

    def _build_card(self, parent: ttk.Frame, item: Launchable, *, row: int, col: int) -> None:
        cell = ttk.Frame(parent, style="Alt.TFrame")
        cell.grid(row=row, column=col, sticky="nsew", padx=5, pady=4)
        cell.columnconfigure(0, weight=1)
        cell.columnconfigure(1, weight=0, minsize=100)

        icon_img = self._load_icon(item.command)

        # Name + tagline on the left; icon top-right, spanning both rows so
        # the card height matches the pre-icon version — no extra row.
        ttk.Label(cell, text=item.name, style="Title.TLabel").grid(
            row=0, column=0, sticky="ew",
        )
        ttk.Label(cell, text=item.tagline, style="Tag.TLabel").grid(
            row=1, column=0, sticky="ew",
        )
        if icon_img is not None:
            icon_label = tk.Label(
                cell,
                image=icon_img,
                bg=_PALETTE["bg_alt"],
                borderwidth=0,
                highlightthickness=0,
            )
            icon_label.grid(
                row=0, column=1, rowspan=2,
                sticky="ne",
                padx=(4, 8), pady=(4, 0),
            )

        key_hint = f"  [{_display_key(item.keybinding)}]" if item.keybinding else ""
        ttk.Button(
            cell,
            text=f"Launch {item.short_name}{key_hint}",
            style="Launch.TButton",
            command=lambda i=item: self._launch(i),
        ).grid(row=2, column=0, sticky="ew", padx=(10, 4), pady=(2, 6))

        ttk.Button(
            cell,
            text="ⓘ  Info",
            style="Info.TButton",
            command=lambda i=item: self._open_info(i),
        ).grid(row=2, column=1, sticky="ew", padx=(0, 10), pady=(2, 6))

    def _build_status_bar(self) -> None:
        status = ttk.Label(
            self,
            textvariable=self._status_var,
            style="Status.TLabel",
            anchor="w",
        )
        status.pack(side=tk.BOTTOM, fill=tk.X)
        for v in (self._run_mode, self._launch_mode):
            v.trace_add("write", lambda *_: self._refresh_status())

    def _refresh_status(self) -> None:
        # Guard against callbacks firing after the window is destroyed. Tk
        # raises if we touch a StringVar on a dead interpreter.
        try:
            self._status_var.set(
                f"Launch mode: {self._launch_mode.get()}     "
                f"Run mode: {self._run_mode.get()}     "
                f"Ctrl+R recommend  •  Ctrl+Q quit  •  F1 keys"
            )
        except tk.TclError:
            pass

    def _flash_status(self, message: str, *, revert_ms: int = 4500) -> None:
        """Temporarily replace the status bar with *message*, then revert.

        Cancels any previous flash's pending-revert callback so flashes in
        quick succession don't race each other on a partially-destroyed
        window.
        """
        if getattr(self, "_pending_flash_id", None) is not None:
            try:
                self.after_cancel(self._pending_flash_id)
            except (tk.TclError, ValueError):
                pass
        try:
            self._status_var.set(message)
            self._pending_flash_id = self.after(revert_ms, self._refresh_status)
        except tk.TclError:
            self._pending_flash_id = None

    # ---- bindings ---------------------------------------------------

    def _install_bindings(self) -> None:
        self.bind_all("<Control-q>", lambda _e: self._quit())
        self.bind_all("<Control-Q>", lambda _e: self._quit())
        self.bind_all("<Control-r>", lambda _e: self._open_recommend())
        self.bind_all("<Control-R>", lambda _e: self._open_recommend())
        self.bind_all("<F1>", lambda _e: self._open_keys())
        self.bind_all("?", lambda _e: self._open_keys())
        self.bind_all("<Escape>", lambda _e: self._dismiss_topmost())

        # Easter-egg hidden trigger: the "lynx" sequence — never surfaced in
        # menus, status bar, or help text.
        self._egg_buffer: List[str] = []

        def _watch_key(event):
            # Don't track keystrokes while the user is typing into an input —
            # otherwise searching for a company whose name contains "lynx"
            # would fire the egg unexpectedly.
            if self._is_text_input_focused(event.widget):
                return
            ch = (event.char or "").lower()
            if not ch:
                return
            self._egg_buffer.append(ch)
            if len(self._egg_buffer) > 8:
                self._egg_buffer = self._egg_buffer[-8:]
            if "".join(self._egg_buffer[-4:]) == "lynx":
                self._egg_buffer.clear()
                self._open_easter()

        self.bind_all("<KeyPress>", _watch_key, add="+")

        # Per-launchable shortcut keys. CRITICAL: these live on ``bind_all`` so
        # they work from any focused widget — but we must NOT hijack a key
        # when the focus is inside an Entry / Text / Combobox widget, or
        # pressing 'p' while typing "Procter & Gamble" into the Recommend
        # box would launch lynx-portfolio instead of inserting the letter.
        for item in APPS + AGENTS:
            if not item.keybinding:
                continue
            self.bind_all(
                f"<Key-{item.keybinding}>",
                lambda _e, i=item: self._maybe_launch_from_key(_e, i),
            )

    def _maybe_launch_from_key(self, event, item: Launchable) -> Optional[str]:
        """Shortcut-key handler that yields to text-input widgets."""
        if self._is_text_input_focused(event.widget):
            return None  # let the Entry/Text see the key normally
        self._launch(item)
        return "break"  # stop propagation

    @staticmethod
    def _is_text_input_focused(widget) -> bool:
        """True when *widget* is an Entry, Text, Combobox, or Spinbox.

        ``bind_all`` fires for every widget, so we need this check wherever a
        letter shortcut might clash with text input.
        """
        if widget is None:
            return False
        # Match both tk and ttk flavors.
        cls = widget.winfo_class() if hasattr(widget, "winfo_class") else ""
        return cls in {"Entry", "TEntry", "Text", "Combobox", "TCombobox", "Spinbox", "TSpinbox"}

    def _dismiss_topmost(self) -> None:
        for child in reversed(self.winfo_children()):
            if isinstance(child, tk.Toplevel):
                child.destroy()
                return

    # ---- launch -----------------------------------------------------

    def _launch(self, target: Launchable, ticker: Optional[str] = None) -> None:
        """Launch *target* in the current mode, optionally auto-analyzing
        *ticker*.

        When the user clicks "Launch top pick" from the Recommend dialog,
        or "Launch" from an Info dialog opened on a resolved company, the
        resolved Yahoo symbol is threaded in here so the child app runs
        its analysis for that company straight away — no re-typing.
        """
        mode = self._launch_mode.get()
        if not target.supports(mode):
            self._show_message(
                "Mode not supported",
                f"{target.name} has no '{mode}' mode.\n"
                f"Switch via View → Launch children in…",
            )
            return
        request = LaunchRequest(
            target=target,
            mode=mode,
            run_mode=self._run_mode.get(),
            ticker=ticker or None,
        )
        cmd_tuple = build_command(request)
        cmd_str = format_command(cmd_tuple)
        if self._dry_run:
            self._show_message("Dry run", cmd_str)
            return

        if mode == "gui":
            result = launch_detached(request)
            if not result.launched:
                self._show_message("Launch failed", result.message, icon="error")
                return
            self._flash_status(f"Launched {target.command} (new GUI window).")
            return

        # TUI / interactive / console need a real TTY. We're running inside
        # Tk, so pop a fresh terminal emulator for the child. The new
        # _spawn_in_terminal handles multi-terminal fallback and captures
        # stderr so failures are visible instead of silent.
        # Always log what we're attempting — if the user launched the GUI
        # from a parent terminal (the common case), they see the command
        # there too; handy for debugging DE quirks.
        print(f"[lynx-dashboard] launching: {cmd_str}", flush=True)

        result = _spawn_in_terminal(cmd_tuple)
        if not result.ok:
            # Always tell the user *what* went wrong plus the exact command
            # they can paste into a terminal themselves.
            self._show_message(
                "Couldn't open a terminal window",
                (
                    f"{result.message}\n\n"
                    f"Equivalent command you can run yourself:\n  {cmd_str}"
                ),
                icon="error",
            )
            return
        self._flash_status(
            f"Launched {target.command}"
            + (f" ({ticker})" if ticker else "")
            + f" in {mode} mode via {os.path.basename(result.terminal)} — "
            f"check the new terminal window."
        )

    # ---- dialogs ----------------------------------------------------

    def _open_about(self) -> None:
        about = get_about_text()
        # Width/height sized so every line fits on one screen without a
        # vertical scrollbar — small logo + compact metadata + wrapped
        # description fit in roughly 560 px of vertical space.
        win = self._modal("About", width=680, height=620, resizable=False)

        # CRITICAL: pack the button bar FIRST so it always claims the
        # bottom strip. If it's packed last, an expand=True sibling above
        # it eats the leftover space and hides the close button.
        self._dialog_buttons(
            win,
            [
                ("View License…", lambda: self._open_license_modal(about)),
                ("Close (Esc)", win.destroy),
            ],
        )

        # Top banner: small logo + title + version + release line.
        banner = tk.Frame(win, bg=_PALETTE["bg"])
        banner.pack(fill=tk.X, side=tk.TOP)
        # Prefer the small (157×179) logo so the whole dialog fits. Half /
        # quarter are fallbacks if the small file is missing.
        win._about_logo = (
            _load_png(win, "logo_sm_green.png")
            or _load_png(win, "logo_sm_half_green.png")
        )
        if win._about_logo is not None:
            tk.Label(
                banner,
                image=win._about_logo,
                bg=_PALETTE["bg"],
                borderwidth=0,
                highlightthickness=0,
            ).pack(pady=(14, 6))
        tk.Label(
            banner,
            text=about["name"],
            bg=_PALETTE["bg"],
            fg=_PALETTE["accent"],
            font=("TkDefaultFont", 16, "bold"),
        ).pack(pady=(0, 2))
        tk.Label(
            banner,
            text=f"Version {about['version']}   ·   Part of {about['suite']} v{about['suite_version']}",
            bg=_PALETTE["bg"],
            fg=_PALETTE["fg_dim"],
            font=("TkDefaultFont", 10),
        ).pack()
        tk.Label(
            banner,
            text=f"Released {about['year']}   ·   {about['license']}",
            bg=_PALETTE["bg"],
            fg=_PALETTE["fg_dim"],
            font=("TkDefaultFont", 10),
        ).pack(pady=(0, 10))

        # Compact body — metadata lines + wrapped description. No scrollbar:
        # wraplength keeps everything inside the dialog and the full license
        # text is off-loaded to a dedicated modal accessed from the button bar.
        body = tk.Frame(win, bg=_PALETTE["bg_alt"])
        body.pack(fill=tk.BOTH, expand=True, padx=18, pady=(6, 10))

        def _row(label: str, value: str) -> None:
            row = tk.Frame(body, bg=_PALETTE["bg_alt"])
            row.pack(fill=tk.X, padx=14, pady=(8, 0))
            tk.Label(
                row, text=label, width=14, anchor="w",
                bg=_PALETTE["bg_alt"], fg=_PALETTE["accent2"],
                font=("TkDefaultFont", 10, "bold"),
            ).pack(side=tk.LEFT)
            tk.Label(
                row, text=value, anchor="w",
                bg=_PALETTE["bg_alt"], fg=_PALETTE["fg"],
                font=("TkDefaultFont", 10),
            ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        _row("Developed by", about["author"])
        _row("Contact",      about["email"])
        _row("License",      f"{about['license_name']} ({about['license']})")

        tk.Label(
            body, text=about["description"],
            bg=_PALETTE["bg_alt"], fg=_PALETTE["fg"],
            font=("TkDefaultFont", 10),
            wraplength=620, justify=tk.LEFT, anchor="w",
        ).pack(fill=tk.BOTH, expand=True, padx=14, pady=(14, 14))

    def _open_license_modal(self, about: dict) -> None:
        """Full BSD license text in its own scroll dialog — out of the way
        unless the user specifically wants it."""
        win = self._modal("License", width=720, height=560)
        self._dialog_buttons(win, [("Close (Esc)", win.destroy)])
        text = tk.Text(
            win,
            bg=_PALETTE["bg_alt"],
            fg=_PALETTE["fg_dim"],
            wrap=tk.WORD,
            padx=16,
            pady=16,
            font=("TkFixedFont", 9),
            borderwidth=0,
            highlightthickness=0,
        )
        scroll = ttk.Scrollbar(win, orient=tk.VERTICAL, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        text.pack(fill=tk.BOTH, expand=True)
        text.insert(tk.END, f"{about['license_name']}\n\n", "label")
        text.insert(tk.END, about["license_text"])
        text.tag_configure("label", foreground=_PALETTE["accent"], font=("TkDefaultFont", 11, "bold"))
        text.configure(state=tk.DISABLED)
        bind_tk_paging(win, text)

    def _open_keys(self) -> None:
        win = self._modal("Keybindings", width=680, height=580, resizable=False)
        # Pack the button bar FIRST so it reliably claims the bottom strip.
        self._dialog_buttons(win, [("Close (Esc)", win.destroy)])
        body = tk.Text(
            win,
            bg=_PALETTE["bg_alt"],
            fg=_PALETTE["fg"],
            wrap=tk.WORD,
            padx=18,
            pady=18,
            borderwidth=0,
            highlightthickness=0,
            font=("TkDefaultFont", 10),
        )
        body.tag_configure("head", foreground=_PALETTE["accent"], font=("TkDefaultFont", 11, "bold"))
        body.tag_configure("key", foreground=_PALETTE["accent2"], font=("TkFixedFont", 10, "bold"))
        body.tag_configure("text", foreground=_PALETTE["fg"])
        body.pack(fill=tk.BOTH, expand=True)

        def row(key: str, text: str) -> None:
            body.insert(tk.END, f"  {key:<12}", "key")
            body.insert(tk.END, f"  {text}\n", "text")

        body.insert(tk.END, "Global\n", "head")
        row("Ctrl+R", "Recommend agent for a company")
        row("Ctrl+Q", "Quit")
        row("F1 / ?", "This help")
        row("Esc", "Close dialog")
        body.insert(tk.END, "\nCore apps\n", "head")
        for app in APPS:
            row(f"[{_display_key(app.keybinding)}]", f"{app.name}   ({app.command})")
        body.insert(tk.END, "\nSector agents\n", "head")
        for agent in AGENTS:
            row(f"[{_display_key(agent.keybinding)}]", f"{agent.name}   ({agent.command})")
        body.configure(state=tk.DISABLED)

    def _open_info(self, item: Launchable, ticker: Optional[str] = None) -> None:
        """Info dialog for *item*.

        When *ticker* is given (e.g. opened from the Recommend dialog after
        resolving a company), the dialog's Launch button auto-analyzes
        that company instead of launching the agent empty.
        """
        label_suffix = f"   ({ticker})" if ticker else ""
        win = self._modal(f"Info — {item.name}", width=780, height=640)

        # "Copy command" puts the exact shell command the dashboard would run
        # onto the system clipboard — useful for users who want to run in
        # their own terminal or share it.
        def _copy_cmd() -> None:
            request = LaunchRequest(
                target=item,
                mode=self._launch_mode.get() if item.supports(self._launch_mode.get()) else "console",
                run_mode=self._run_mode.get(),
                ticker=ticker,
            )
            cmd = format_command(build_command(request))
            self.clipboard_clear()
            self.clipboard_append(cmd)
            self.update()  # keep clipboard alive after window dies
            self._flash_status(f"Copied: {cmd}")

        # Buttons first so they always claim the bottom strip.
        self._dialog_buttons(
            win,
            [
                (
                    f"Launch {item.short_name}{label_suffix}",
                    lambda: (win.destroy(), self._launch(item, ticker=ticker)),
                ),
                ("Copy command", _copy_cmd),
                ("Close (Esc)", win.destroy),
            ],
        )
        body = tk.Text(
            win,
            bg=_PALETTE["bg_alt"],
            fg=_PALETTE["fg"],
            wrap=tk.WORD,
            padx=18,
            pady=18,
            borderwidth=0,
            highlightthickness=0,
            font=("TkDefaultFont", 10),
        )
        body.tag_configure("title", foreground=_PALETTE["accent"], font=("TkDefaultFont", 14, "bold"))
        body.tag_configure("tag", foreground=_PALETTE["accent2"], font=("TkDefaultFont", 10, "italic"))
        body.tag_configure("head", foreground=_PALETTE["accent2"], font=("TkDefaultFont", 11, "bold"))
        body.tag_configure("body", foreground=_PALETTE["fg"], font=("TkDefaultFont", 10))
        body.tag_configure("bullet", foreground=_PALETTE["fg"], font=("TkDefaultFont", 10))
        body.tag_configure("dim", foreground=_PALETTE["fg_dim"], font=("TkDefaultFont", 10))
        body.pack(fill=tk.BOTH, expand=True)

        body.insert(tk.END, f"{item.name}\n", "title")
        body.insert(tk.END, f"{item.tagline}\n\n", "tag")

        body.insert(tk.END, "What it does\n", "head")
        body.insert(tk.END, (item.details or item.description) + "\n\n", "body")

        if item.data_sources:
            body.insert(tk.END, "Data sources\n", "head")
            for source in item.data_sources:
                body.insert(tk.END, f"  • {source}\n", "bullet")
            body.insert(tk.END, "\n")

        if item.specialization:
            body.insert(tk.END, "What makes it specialized\n", "head")
            body.insert(tk.END, item.specialization + "\n\n", "body")

        body.insert(tk.END, "At a glance\n", "head")
        body.insert(tk.END, f"  Command:       {item.command}\n", "bullet")
        body.insert(tk.END, f"  Package:       {item.package}\n", "bullet")
        body.insert(tk.END, f"  Keybinding:    {_display_key(item.keybinding) or '—'}\n", "bullet")
        modes = ", ".join(sorted(item.modes)) if item.modes else "—"
        body.insert(tk.END, f"  Modes:         {modes}\n", "bullet")
        if item.example_tickers:
            body.insert(tk.END, f"  Try it with:   {', '.join(item.example_tickers)}\n", "bullet")
        body.configure(state=tk.DISABLED)

    def _open_easter(self) -> None:
        win = self._modal("", width=620, height=460, resizable=False)
        # Buttons first; content fills above.
        self._dialog_buttons(win, [("Close (Esc)", win.destroy)])
        frame = ttk.Frame(win, style="Alt.TFrame")
        frame.pack(fill=tk.BOTH, expand=True)
        body = tk.Text(
            frame,
            bg=_PALETTE["bg_alt"],
            fg=_PALETTE["ok"],
            wrap=tk.NONE,
            padx=20,
            pady=20,
            borderwidth=0,
            highlightthickness=0,
            font=("TkFixedFont", 10),
        )
        body.pack(fill=tk.BOTH, expand=True)
        body.insert(tk.END, _strip_rich_markup(pick_easter_egg()))
        body.configure(state=tk.DISABLED)

    def _open_recommend(self) -> None:
        win = self._modal("Recommend agent", width=760, height=620)

        header = ttk.Frame(win, style="Alt.TFrame")
        header.pack(fill=tk.X, padx=0, pady=0)
        ttk.Label(header, text="Recommend an agent for a company", style="Hero.TLabel").pack(
            anchor="w", padx=18, pady=(16, 2),
        )
        ttk.Label(
            header,
            text="Enter a ticker, ISIN, or company name. Press Enter.",
            style="Sub.TLabel",
        ).pack(anchor="w", padx=18, pady=(0, 10))

        entry = ttk.Entry(win, font=("TkDefaultFont", 11))
        entry.pack(fill=tk.X, padx=18, pady=(0, 4))
        entry.focus_set()

        def _set_entry(text: str) -> None:
            entry.delete(0, tk.END)
            entry.insert(0, text)
            entry.focus_set()
            run_query()

        # Clickable example-ticker pills. One per agent sector so every part
        # of the recommender has a quick "try me" the user can click.
        samples = ttk.Frame(win)
        samples.pack(fill=tk.X, padx=18, pady=(0, 4))
        ttk.Label(samples, text="Try:", style="Sub.TLabel").pack(side=tk.LEFT, padx=(0, 6))
        for sample in _recommend_samples():
            ttk.Button(
                samples, text=sample, style="Pill.TButton",
                command=lambda s=sample: _set_entry(s),
            ).pack(side=tk.LEFT, padx=2)

        # Recently-searched pills (persisted across sessions). Rendered only
        # if history has entries; skips gracefully on first launch.
        if self._history is None:
            self._history = HistoryStore()
        recent_queries = self._history.recent_queries(max_items=6)
        if recent_queries:
            recent = ttk.Frame(win)
            recent.pack(fill=tk.X, padx=18, pady=(0, 10))
            ttk.Label(recent, text="Recent:", style="Sub.TLabel").pack(side=tk.LEFT, padx=(0, 6))
            for past in recent_queries:
                ttk.Button(
                    recent, text=past, style="Pill.TButton",
                    command=lambda s=past: _set_entry(s),
                ).pack(side=tk.LEFT, padx=2)
        else:
            ttk.Frame(win, height=6).pack(fill=tk.X)

        result = tk.Text(
            win,
            bg=_PALETTE["bg_alt"],
            fg=_PALETTE["fg"],
            wrap=tk.WORD,
            height=14,
            padx=14,
            pady=14,
            borderwidth=0,
            highlightthickness=0,
            font=("TkDefaultFont", 10),
        )
        result.tag_configure("title", foreground=_PALETTE["accent"], font=("TkDefaultFont", 12, "bold"))
        result.tag_configure("head", foreground=_PALETTE["accent2"], font=("TkDefaultFont", 11, "bold"))
        result.tag_configure("hit", foreground=_PALETTE["ok"], font=("TkDefaultFont", 11, "bold"))
        result.tag_configure("body", foreground=_PALETTE["fg"])
        result.tag_configure("dim", foreground=_PALETTE["fg_dim"])
        result.pack(fill=tk.BOTH, expand=True, padx=18, pady=(0, 10))
        result.configure(state=tk.DISABLED)

        # Buttons docked at the bottom BEFORE the result widget — otherwise
        # the result's expand=True eats the leftover and hides them.
        #
        # state["ticker"] carries the RESOLVED Yahoo symbol from the last
        # recommendation so clicking "Launch top pick" auto-analyzes that
        # company in the child agent.
        state: dict = {"primary": None, "ticker": None}
        button_row = ttk.Frame(win)
        button_row.pack(side=tk.BOTTOM, fill=tk.X, padx=18, pady=(0, 14))
        launch_btn = ttk.Button(
            button_row,
            text="Launch top pick",
            style="Launch.TButton",
            state=tk.DISABLED,
            command=lambda: state["primary"] and (
                win.destroy(),
                self._launch(state["primary"], ticker=state.get("ticker")),
            ),
        )
        info_btn = ttk.Button(
            button_row,
            text="ⓘ Info on top pick",
            style="Info.TButton",
            state=tk.DISABLED,
            command=lambda: state["primary"] and self._open_info(
                state["primary"], ticker=state.get("ticker"),
            ),
        )
        close_btn = ttk.Button(
            button_row, text="Close (Esc)", style="Dialog.TButton", command=win.destroy,
        )
        launch_btn.pack(side=tk.LEFT, padx=(0, 8))
        info_btn.pack(side=tk.LEFT, padx=(0, 8))
        close_btn.pack(side=tk.RIGHT)

        def run_query(_event=None) -> None:
            query = entry.get().strip()
            if not query:
                return
            # Immediate "Searching…" feedback — yfinance + Yahoo search can
            # take 2-5 s for uncommon names like "Oroco" or "F3 Uranium".
            result.configure(state=tk.NORMAL)
            result.delete("1.0", tk.END)
            result.insert(tk.END, f"Searching Yahoo Finance for {query!r}…\n", "dim")
            result.insert(tk.END, "\n(This can take a few seconds for names / ISINs.)", "dim")
            result.configure(state=tk.DISABLED)
            launch_btn.configure(state=tk.DISABLED)
            info_btn.configure(state=tk.DISABLED)
            win.update_idletasks()  # force Tk to paint before we block

            rec = recommend_for_query(query, use_network=not self._offline)
            # Persist — recent pills in future sessions are populated from this.
            try:
                self._history.record(HistoryEntry(
                    query=query,
                    ticker=rec.profile.ticker or "",
                    sector=rec.profile.sector or "",
                    primary=rec.primary.registry_name if rec.primary else "",
                ))
            except Exception:
                pass
            state["primary"] = rec.primary
            # Prefer the resolved Yahoo symbol; fall back to the raw query
            # so offline matches (which may not set ticker) still propagate.
            state["ticker"] = rec.profile.ticker or rec.query or None
            # Reflect the company in the button label so the user sees
            # *what* will be analyzed.
            if rec.primary is not None and state["ticker"]:
                launch_btn.configure(text=f"Launch top pick   ({state['ticker']})")
                info_btn.configure(text=f"ⓘ Info on top pick   ({state['ticker']})")
            else:
                launch_btn.configure(text="Launch top pick")
                info_btn.configure(text="ⓘ Info on top pick")
            result.configure(state=tk.NORMAL)
            result.delete("1.0", tk.END)
            result.insert(tk.END, f"{rec.query}\n", "title")
            if rec.profile.name and rec.profile.name != rec.query:
                result.insert(tk.END, f"{rec.profile.name}\n", "dim")
            profile_bits = []
            if rec.profile.sector:
                profile_bits.append(f"sector: {rec.profile.sector}")
            if rec.profile.industry:
                profile_bits.append(f"industry: {rec.profile.industry}")
            if profile_bits:
                result.insert(tk.END, "  ·  ".join(profile_bits) + "\n", "dim")
            result.insert(tk.END, "\n")
            if rec.has_match:
                primary = rec.primary
                assert primary is not None
                result.insert(tk.END, "Top pick\n", "head")
                result.insert(tk.END, f"  {primary.name}", "hit")
                result.insert(tk.END, f"   ({primary.command})\n", "dim")
                result.insert(tk.END, f"  {primary.tagline}\n", "body")
                if primary.specialization:
                    result.insert(tk.END, f"  → {primary.specialization}\n", "body")
                if rec.alternates:
                    result.insert(tk.END, "\nAlso relevant\n", "head")
                    for alt in rec.alternates:
                        result.insert(tk.END, f"  • {alt.name} ({alt.command}) — {alt.tagline}\n", "body")
            else:
                result.insert(tk.END, rec.reason + "\n", "body")
            result.insert(tk.END, f"\n{rec.reason}\n", "dim")
            result.configure(state=tk.DISABLED)

            enabled = tk.NORMAL if rec.primary is not None else tk.DISABLED
            launch_btn.configure(state=enabled)
            info_btn.configure(state=enabled)

        entry.bind("<Return>", run_query)

    # ---- modal plumbing -------------------------------------------

    def _modal(
        self,
        title: str,
        *,
        width: int = 720,
        height: int = 560,
        resizable: bool = True,
    ) -> tk.Toplevel:
        win = tk.Toplevel(self)
        if title:
            win.title(f"{APP_NAME} — {title}")
        win.configure(bg=_PALETTE["bg"])
        win.transient(self)
        win.bind("<Escape>", lambda _e: win.destroy())
        win.resizable(resizable, resizable)
        self._center_toplevel(win, width, height)
        win.after_idle(win.lift)
        win.after_idle(win.focus_set)
        return win

    def _center_toplevel(self, win: tk.Toplevel, width: int, height: int) -> None:
        self.update_idletasks()
        root_x = self.winfo_rootx()
        root_y = self.winfo_rooty()
        root_w = max(self.winfo_width(), 1)
        root_h = max(self.winfo_height(), 1)
        if root_w <= 100 or root_h <= 100:
            # Main window not laid out yet — center on the screen instead.
            root_x, root_y = 0, 0
            root_w = self.winfo_screenwidth()
            root_h = self.winfo_screenheight()
        x = root_x + (root_w - width) // 2
        y = root_y + (root_h - height) // 2
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x = max(0, min(x, sw - width))
        y = max(0, min(y, sh - height))
        win.geometry(f"{width}x{height}+{x}+{y}")

    def _dialog_buttons(self, win: tk.Toplevel, buttons) -> None:
        bar = ttk.Frame(win)
        bar.pack(fill=tk.X, side=tk.BOTTOM, padx=14, pady=10)
        for label, callback in buttons:
            ttk.Button(bar, text=label, style="Dialog.TButton", command=callback).pack(
                side=tk.RIGHT, padx=(8, 0),
            )

    def _show_message(self, title: str, body: str, *, icon: str = "info") -> None:
        if icon == "error":
            messagebox.showerror(f"{APP_NAME} — {title}", body, parent=self)
        elif icon == "warning":
            messagebox.showwarning(f"{APP_NAME} — {title}", body, parent=self)
        else:
            messagebox.showinfo(f"{APP_NAME} — {title}", body, parent=self)

    # ---- quit -------------------------------------------------------

    def _quit(self) -> None:
        # Cancel pending after-callbacks so they don't fire against the
        # destroyed Tk interpreter.
        if getattr(self, "_pending_flash_id", None) is not None:
            try:
                self.after_cancel(self._pending_flash_id)
            except (tk.TclError, ValueError):
                pass
            self._pending_flash_id = None
        self.destroy()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _display_key(keybinding: Optional[str]) -> str:
    if not keybinding:
        return ""
    return "-" if keybinding == "minus" else keybinding


def _strip_rich_markup(text: str) -> str:
    """Rough Rich-markup stripper for Tk display."""
    import re
    return re.sub(r"\[/?[^\[\]]*?\]", "", text)


def _recommend_samples() -> Tuple[str, ...]:
    """One well-known ticker per sector, used as click-to-try pills."""
    # Picks chosen so every sector registry entry is reachable with one click.
    return ("AAPL", "XOM", "JPM", "JNJ", "NEM", "TSLA", "PG", "BA", "NEE", "GOOGL", "PLD")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_gui(
    *,
    run_mode: str = "production",
    offline: bool = False,
    dry_run: bool = False,
    show_splash: bool = True,
) -> None:
    try:
        app = DashboardGUI(run_mode=run_mode, offline=offline, dry_run=dry_run)
    except tk.TclError as exc:
        raise RuntimeError(f"Tkinter could not open a display: {exc}") from exc

    if show_splash:
        # Splash takes the screen first; the main window stays withdrawn
        # until the splash finishes, at which point we deiconify and focus.
        app.withdraw()
        from lynx_dashboard.splash import run_gui_splash

        def _reveal_dashboard() -> None:
            try:
                app.deiconify()
                app.lift()
                app.focus_force()
            except tk.TclError:
                pass

        run_gui_splash(parent_root=app, on_done=_reveal_dashboard)

    app.mainloop()
