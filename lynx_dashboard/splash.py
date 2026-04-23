"""Animated splash screens for the GUI and TUI dashboards.

Both splashes follow the same choreography:

1. A brief fade-in (where supported).
2. The PNG / ASCII logo appears centered.
3. A progress bar fills with an ease-out-cubic curve.
4. A cycling status line advertises what is "loading".
5. A fade-out hands off to the real dashboard.

The whole thing lasts ~1.8 s in the GUI and ~1.5 s in the TUI — short enough
to feel polished, long enough for the eye to register the brand.

Skip it from the command line with ``--no-splash`` or by setting
``LYNX_NO_SPLASH=1`` in the environment.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Callable, Optional


__all__ = [
    "splash_disabled",
    "run_gui_splash",
    "TuiSplashScreen",
    "run_console_splash",
]


# ---------------------------------------------------------------------------
# Feature flag
# ---------------------------------------------------------------------------

def splash_disabled(*, cli_flag: bool = False) -> bool:
    """Return True if splashes should be suppressed.

    Respects ``--no-splash`` (passed as *cli_flag*) plus the environment
    variables ``LYNX_NO_SPLASH=1`` and ``NO_COLOR``/``CI`` — the last two so
    CI jobs and scripted runs don't waste time on animations.
    """
    if cli_flag:
        return True
    if os.environ.get("LYNX_NO_SPLASH", "").strip() in {"1", "true", "TRUE", "yes"}:
        return True
    if os.environ.get("CI", "").strip():
        return True
    return False


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------

_STATUS_STEPS = (
    "Initializing…",
    "Loading sector registry…",
    "Preparing agent launchers…",
    "Wiring keybindings…",
    "Rendering dashboard…",
    "Ready.",
)


def _ease_out_cubic(t: float) -> float:
    """Smoothly decelerate t∈[0,1]. Classic ease-out-cubic.

    NaN and ±Inf are treated as 0.0 — the alternative is an animation
    that crashes the splash thread, which is a worse UX than a stuttering
    progress bar.
    """
    t = _clamp_fraction(t)
    return 1.0 - (1.0 - t) ** 3


def _status_at(t: float) -> str:
    """Pick the status line for fraction t∈[0,1] of the splash timeline."""
    t = _clamp_fraction(t)
    idx = min(int(t * len(_STATUS_STEPS)), len(_STATUS_STEPS) - 1)
    return _STATUS_STEPS[idx]


def _clamp_fraction(t: float) -> float:
    """Coerce *t* to [0, 1]. NaN / ±Inf collapse to 0.0."""
    try:
        if t != t:           # NaN check — NaN is the only float that !=self
            return 0.0
    except TypeError:
        return 0.0
    if t <= 0.0 or t == float("-inf"):
        return 0.0
    if t >= 1.0 or t == float("inf"):
        return 1.0
    return t


# ---------------------------------------------------------------------------
# GUI splash (Tkinter)
# ---------------------------------------------------------------------------

_PALETTE = {
    "bg": "#0f1420",
    "bg_alt": "#151a2b",
    "bar_bg": "#1f2740",
    "bar_fg": "#4da3ff",
    "accent": "#4da3ff",
    "accent2": "#b46bff",
    "ok": "#46d15f",
    "fg": "#e8ecf1",
    "fg_dim": "#8892a6",
}


def run_gui_splash(
    *,
    duration_ms: int = 1800,
    on_done: Optional[Callable[[], None]] = None,
    parent_root=None,
) -> None:
    """Show the GUI splash and invoke *on_done* when it's finished.

    Creates its own transient Tk root if *parent_root* is None. The splash
    window is borderless, always-on-top during its lifetime, and centered on
    the screen. Uses window alpha to fade in and out; on platforms where
    alpha is unsupported the splash simply pops on and off.
    """
    import tkinter as tk
    from tkinter import ttk  # noqa: F401 — preload ttk so subsequent imports are instant

    # Lazy import so tests that don't want a display can still import this module.
    from lynx_dashboard import APP_NAME, APP_TAGLINE, SUITE_LABEL

    owns_root = parent_root is None
    root = parent_root or tk.Tk()
    if owns_root:
        root.withdraw()  # hide the root; splash is our only visible window

    win = tk.Toplevel(root)
    try:
        win.overrideredirect(True)
    except tk.TclError:
        pass
    win.configure(bg=_PALETTE["bg"])

    # Budget: small logo (157×179) + title (~30) + tagline (~24) + bar (~24)
    # + status (~20) + suite (~20) + hint (~20) + paddings ≈ 460 px.
    # 520 × 480 gives comfortable breathing room without any content clipped.
    width, height = 520, 480
    screen_w = win.winfo_screenwidth()
    screen_h = win.winfo_screenheight()
    x = (screen_w - width) // 2
    y = (screen_h - height) // 2
    win.geometry(f"{width}x{height}+{x}+{y}")
    try:
        win.attributes("-topmost", True)
    except tk.TclError:
        pass

    supports_alpha = True
    try:
        win.attributes("-alpha", 0.0)
    except tk.TclError:
        supports_alpha = False

    # --- content -------------------------------------------------------

    # Logo — use the small (157×179) variant so content has room for the
    # title block, progress bar, and status lines without clipping. The
    # large variant is 423 px tall and would not fit in any reasonable
    # splash window size.
    logo_image = _load_png(win, "logo_sm_green.png") or _load_png(win, "logo_sm_half_green.png")
    if logo_image is not None:
        win._splash_logo = logo_image  # keep a strong reference
        tk.Label(
            win, image=logo_image, bg=_PALETTE["bg"],
            borderwidth=0, highlightthickness=0,
        ).pack(pady=(24, 6))
    else:
        # Fallback ASCII banner — still striking.
        ascii_logo = _load_ascii()
        tk.Label(
            win, text=ascii_logo or "L Y N X",
            bg=_PALETTE["bg"], fg=_PALETTE["ok"],
            font=("TkFixedFont", 7),
            justify=tk.LEFT,
        ).pack(pady=(20, 6))

    tk.Label(
        win, text=APP_NAME,
        bg=_PALETTE["bg"], fg=_PALETTE["accent"],
        font=("TkDefaultFont", 22, "bold"),
    ).pack()
    tk.Label(
        win, text=APP_TAGLINE,
        bg=_PALETTE["bg"], fg=_PALETTE["fg_dim"],
        font=("TkDefaultFont", 11, "italic"),
    ).pack(pady=(2, 18))

    # Progress bar — a custom canvas because ttk.Progressbar's "determinate"
    # animation is stepped; we want a silky ease-out-cubic fill.
    bar_pad = 48
    bar_h = 6
    bar_w = width - 2 * bar_pad
    bar_canvas = tk.Canvas(
        win,
        width=bar_w,
        height=bar_h,
        bg=_PALETTE["bar_bg"],
        highlightthickness=0,
        borderwidth=0,
    )
    bar_canvas.pack(pady=(0, 6))
    fill_item = bar_canvas.create_rectangle(
        0, 0, 0, bar_h, fill=_PALETTE["bar_fg"], outline="",
    )

    status_var = tk.StringVar(value=_STATUS_STEPS[0])
    tk.Label(
        win, textvariable=status_var,
        bg=_PALETTE["bg"], fg=_PALETTE["fg_dim"],
        font=("TkDefaultFont", 9),
    ).pack()

    # Footer with suite version.
    tk.Label(
        win, text=SUITE_LABEL,
        bg=_PALETTE["bg"], fg=_PALETTE["accent2"],
        font=("TkDefaultFont", 9, "bold"),
    ).pack(side=tk.BOTTOM, pady=(0, 18))

    # Subtle hint at the bottom that the splash can be skipped.
    tk.Label(
        win, text="Click or press any key to skip",
        bg=_PALETTE["bg"], fg=_PALETTE["fg_dim"],
        font=("TkDefaultFont", 8, "italic"),
    ).pack(side=tk.BOTTOM, pady=(0, 8))

    # --- animation loop ------------------------------------------------

    fade_in_ms = 280
    fade_out_ms = 260
    start = time.monotonic()
    done = {"fired": False}

    def _skip(_event=None) -> None:
        if done["fired"]:
            return
        done["fired"] = True
        _finish()

    win.bind("<Button-1>", _skip)
    win.bind("<Key>", _skip)
    win.focus_set()

    def tick() -> None:
        if done["fired"]:
            return
        elapsed_ms = (time.monotonic() - start) * 1000
        if elapsed_ms >= duration_ms:
            done["fired"] = True
            _finish()
            return

        # Alpha fade.
        if supports_alpha:
            if elapsed_ms < fade_in_ms:
                alpha = elapsed_ms / fade_in_ms
            elif elapsed_ms > duration_ms - fade_out_ms:
                alpha = max(0.0, (duration_ms - elapsed_ms) / fade_out_ms)
            else:
                alpha = 1.0
            try:
                win.attributes("-alpha", alpha)
            except tk.TclError:
                pass

        # Progress bar with ease-out-cubic easing.
        t = elapsed_ms / duration_ms
        fill_w = int(bar_w * _ease_out_cubic(t))
        bar_canvas.coords(fill_item, 0, 0, fill_w, bar_h)

        # Cycling status line.
        status_var.set(_status_at(t))

        win.after(16, tick)  # ~60 fps

    def _finish() -> None:
        try:
            win.destroy()
        except tk.TclError:
            pass
        if on_done is not None:
            on_done()
        if owns_root:
            # If no callback started a mainloop, tear down the hidden root.
            try:
                root.after(0, root.destroy)
            except tk.TclError:
                pass

    win.after(10, tick)


def _load_png(parent, filename: str):
    """Tk-PhotoImage the image at dashboard root / img / *filename*."""
    import tkinter as tk

    root_dir = Path(__file__).resolve().parent.parent
    candidate = root_dir / "img" / filename
    if not candidate.is_file():
        return None
    try:
        return tk.PhotoImage(master=parent, file=str(candidate))
    except tk.TclError:
        return None


def _load_ascii() -> str:
    path = Path(__file__).resolve().parent.parent / "img" / "logo_ascii.txt"
    try:
        return path.read_text().rstrip("\n")
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# TUI splash (Textual)
# ---------------------------------------------------------------------------

def _tui_splash_class():
    """Lazy import of the Textual TUI splash so headless tests can import
    this module without Textual having to resolve."""
    from textual.app import ComposeResult
    from textual.containers import Vertical, Center
    from textual.screen import Screen
    from textual.widgets import ProgressBar, Static

    from lynx_dashboard import APP_NAME, APP_TAGLINE, SUITE_LABEL, get_logo_ascii

    from textual.binding import Binding

    class TuiSplashScreenImpl(Screen):
        """Full-screen splash shown for ~1.5 s before the real dashboard.

        Any keypress (Enter, Escape, Space, q, …) skips straight to the
        dashboard, so users who've seen the splash already aren't held up.
        """

        BINDINGS = [
            Binding("escape", "skip", "Skip", show=True),
            Binding("enter", "skip", "Skip", show=False),
            Binding("space", "skip", "Skip", show=False),
            Binding("q", "skip", "Skip", show=False),
        ]

        CSS = """
        Screen {
            align: center middle;
            background: $surface;
        }
        #splash-box {
            width: auto;
            height: auto;
            padding: 2 6;
            border: thick $primary;
            content-align: center middle;
        }
        #splash-logo {
            color: $success;
            content-align: center middle;
            margin-bottom: 1;
        }
        #splash-title {
            color: $primary;
            text-style: bold;
            content-align: center middle;
            margin-bottom: 0;
        }
        #splash-tagline {
            color: $text-muted;
            text-style: italic;
            content-align: center middle;
            margin-bottom: 2;
        }
        #splash-bar {
            width: 60;
            margin: 1 0;
        }
        #splash-status {
            color: $text-muted;
            content-align: center middle;
        }
        #splash-suite {
            color: $accent;
            text-style: bold;
            content-align: center middle;
            margin-top: 2;
        }
        #splash-skip-hint {
            color: $text-muted;
            text-style: italic;
            content-align: center middle;
            margin-top: 1;
        }
        """

        def __init__(self, duration_ms: int = 1500) -> None:
            super().__init__()
            self._duration_ms = duration_ms
            self._start_monotonic: float = 0.0
            self._finished = False

        def compose(self) -> ComposeResult:
            logo = get_logo_ascii() or "L Y N X"
            with Vertical(id="splash-box"):
                yield Static(logo, id="splash-logo")
                yield Static(APP_NAME, id="splash-title")
                yield Static(APP_TAGLINE, id="splash-tagline")
                yield ProgressBar(total=100, show_eta=False, show_percentage=False, id="splash-bar")
                yield Static(_STATUS_STEPS[0], id="splash-status")
                yield Static(SUITE_LABEL, id="splash-suite")
                yield Static("Press any key to skip", id="splash-skip-hint")

        def on_mount(self) -> None:
            self._start_monotonic = time.monotonic()
            # 30 fps is plenty smooth for a text-mode bar.
            self.set_interval(1 / 30, self._tick)

        def _tick(self) -> None:
            if self._finished:
                return
            elapsed_ms = (time.monotonic() - self._start_monotonic) * 1000
            if elapsed_ms >= self._duration_ms:
                self._dismiss_safely()
                return
            t = elapsed_ms / self._duration_ms
            progress = int(100 * _ease_out_cubic(t))
            try:
                self.query_one("#splash-bar", ProgressBar).update(progress=progress)
                self.query_one("#splash-status", Static).update(_status_at(t))
            except Exception:
                # Screen may have been torn down; harmless.
                pass

        def action_skip(self) -> None:
            self._dismiss_safely()

        def _dismiss_safely(self) -> None:
            if self._finished:
                return
            self._finished = True
            try:
                self.app.pop_screen()
            except Exception:
                pass

    return TuiSplashScreenImpl


def TuiSplashScreen(duration_ms: int = 1500):
    """Factory that returns a ready-to-push Textual splash Screen."""
    cls = _tui_splash_class()
    return cls(duration_ms=duration_ms)


# ---------------------------------------------------------------------------
# Console / interactive splash (Rich progress bar)
# ---------------------------------------------------------------------------

def run_console_splash(*, duration_s: float = 1.4) -> None:
    """Rich-powered progress bar for the console and interactive entry points.

    Transient (clears itself on exit) so it doesn't leave scrollback clutter.
    """
    from rich.console import Console
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TextColumn,
    )

    console = Console()
    steps = 60
    sleep = duration_s / steps
    with Progress(
        SpinnerColumn(style="cyan"),
        TextColumn("[bold blue]Lynx Dashboard[/]"),
        BarColumn(bar_width=32, complete_style="blue", finished_style="green"),
        TextColumn("[dim]{task.description}[/]"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(_STATUS_STEPS[0], total=steps)
        for i in range(steps):
            t = (i + 1) / steps
            progress.update(task, advance=1, description=_status_at(t))
            time.sleep(sleep)
