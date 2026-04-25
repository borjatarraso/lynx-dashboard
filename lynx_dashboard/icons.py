"""Domain-specific icons for every app and agent.

Generates modern flat-design 40×40 PNG icons on first use and caches
them in ``img/icons/``. Each icon is:

* a rounded-square background in the Launchable's house colour,
* a bold white glyph tuned to read clearly at thumbnail size (candlestick
  chart for Fundamental, balance scale for Compare, pie chart for ETF,
  lightning bolt for Energy, gear for Industrials, house for Real
  Estate, etc.).

Icons are rendered at 4× resolution (160×160) and downsampled with a
Lanczos filter so strokes stay crisp on high-DPI displays without
looking chunky.

Uses PIL (Pillow) for rendering. If PIL is not available, the generator
silently no-ops and the GUI falls back to a text-only card.

Public API:
    generate_all()      — build every icon (idempotent; skips existing files).
    get_icon_path(item) — resolve icon path for a Launchable; generates on miss.
    icon_glyph(item)    — Unicode glyph character used by the TUI.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Paths & catalog
# ---------------------------------------------------------------------------

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_ICONS_DIR = _PACKAGE_ROOT / "img" / "icons"

ICON_SIZE = 40        # final png size in px — half of the original 80
_RENDER_SIZE = 160    # 4× oversample for anti-aliasing


# (bg_color, glyph key, tui glyph char)
_CATALOG: dict[str, dict] = {
    # Core apps
    "lynx-fundamental":  {"bg": "#2563eb", "glyph": "candles",   "tui": "📊"},
    "lynx-compare":      {"bg": "#c026d3", "glyph": "scales",    "tui": "⚖"},
    "lynx-portfolio":    {"bg": "#16a34a", "glyph": "briefcase", "tui": "💼"},
    "lynx-etf":          {"bg": "#0891b2", "glyph": "pie",       "tui": "🧺"},
    "lynx-compare-etf":  {"bg": "#9333ea", "glyph": "pie_vs",    "tui": "⚖"},
    "lynx-fund":         {"bg": "#16a34a", "glyph": "vault",     "tui": "🏛"},
    "lynx-compare-fund": {"bg": "#15803d", "glyph": "vault_vs",  "tui": "⚖"},
    "lynx-theme":        {"bg": "#a855f7", "glyph": "palette",   "tui": "🎨"},

    # Sector agents
    "lynx-energy":       {"bg": "#f59e0b", "glyph": "bolt",      "tui": "⚡"},
    "lynx-finance":      {"bg": "#059669", "glyph": "bank",      "tui": "🏦"},
    "lynx-tech":         {"bg": "#0ea5e9", "glyph": "chip",      "tui": "💻"},
    "lynx-health":       {"bg": "#dc2626", "glyph": "cross",     "tui": "➕"},
    "lynx-mining":       {"bg": "#b45309", "glyph": "gem",       "tui": "⛏"},
    "lynx-discretionary":{"bg": "#db2777", "glyph": "bag",       "tui": "🛍"},
    "lynx-staples":      {"bg": "#15803d", "glyph": "cart",      "tui": "🛒"},
    "lynx-industrials":  {"bg": "#2563eb", "glyph": "gear",      "tui": "⚙"},
    "lynx-utilities":    {"bg": "#0284c7", "glyph": "drop",      "tui": "💧"},
    "lynx-comm":         {"bg": "#9333ea", "glyph": "tower",     "tui": "📡"},
    "lynx-realestate":   {"bg": "#ca8a04", "glyph": "house",     "tui": "🏠"},
}


# ---------------------------------------------------------------------------
# PIL-based generator
# ---------------------------------------------------------------------------

def _pil():
    try:
        from PIL import Image, ImageDraw  # noqa: F401
        return Image, ImageDraw
    except ImportError:
        return None


def _rounded_bg(draw, s: int, color: str, radius_ratio: float = 0.22) -> None:
    r = int(s * radius_ratio)
    draw.rounded_rectangle([(0, 0), (s - 1, s - 1)], radius=r, fill=color)


_FG = "#ffffff"


# ---------------------------------------------------------------------------
# Glyphs — all drawn on a square canvas of side *s*. All strokes are
# scaled to *s* so the same function works at any render size.
# ---------------------------------------------------------------------------

def _draw_candles(draw, s: int) -> None:
    """Stock chart: three candlesticks, last one breaking out upward."""
    c = _FG
    # Baseline axis — subtle
    draw.line([(int(s * 0.15), int(s * 0.82)), (int(s * 0.85), int(s * 0.82))],
              fill=c, width=max(2, s // 40))
    # Three candles
    candles = [
        # (x_center_ratio, body_top_ratio, body_bottom_ratio, wick_top_ratio, wick_bottom_ratio)
        (0.28, 0.55, 0.72, 0.45, 0.78),
        (0.50, 0.48, 0.62, 0.38, 0.70),
        (0.72, 0.22, 0.50, 0.15, 0.60),
    ]
    body_w = int(s * 0.12)
    wick_w = max(2, s // 30)
    for xr, top, bot, wtop, wbot in candles:
        x = int(s * xr)
        # Wick
        draw.line([(x, int(s * wtop)), (x, int(s * wbot))], fill=c, width=wick_w)
        # Body
        draw.rectangle(
            [(x - body_w // 2, int(s * top)), (x + body_w // 2, int(s * bot))],
            fill=c,
        )
    # Upward arrow at the top of the last candle
    ax = int(s * 0.72)
    ay = int(s * 0.12)
    arrow_s = int(s * 0.08)
    draw.polygon(
        [(ax, ay), (ax - arrow_s, ay + arrow_s + 2), (ax + arrow_s, ay + arrow_s + 2)],
        fill=c,
    )


def _draw_scales(draw, s: int) -> None:
    """Balance scale — clean, symmetric."""
    c = _FG
    mid = s // 2
    stroke = max(3, s // 22)
    # Pole
    draw.line([(mid, int(s * 0.20)), (mid, int(s * 0.78))], fill=c, width=stroke)
    # Base
    draw.rectangle(
        [(int(s * 0.30), int(s * 0.78)), (int(s * 0.70), int(s * 0.84))],
        fill=c,
    )
    # Beam
    draw.line(
        [(int(s * 0.18), int(s * 0.28)), (int(s * 0.82), int(s * 0.28))],
        fill=c, width=stroke,
    )
    # Left pan (cup)
    draw.chord(
        [(int(s * 0.10), int(s * 0.34)), (int(s * 0.38), int(s * 0.52))],
        start=0, end=180, fill=c,
    )
    draw.line(
        [(int(s * 0.24), int(s * 0.28)), (int(s * 0.24), int(s * 0.43))],
        fill=c, width=max(2, s // 40),
    )
    # Right pan
    draw.chord(
        [(int(s * 0.62), int(s * 0.34)), (int(s * 0.90), int(s * 0.52))],
        start=0, end=180, fill=c,
    )
    draw.line(
        [(int(s * 0.76), int(s * 0.28)), (int(s * 0.76), int(s * 0.43))],
        fill=c, width=max(2, s // 40),
    )
    # Top knob
    draw.ellipse(
        [(mid - int(s * 0.04), int(s * 0.14)),
         (mid + int(s * 0.04), int(s * 0.22))],
        fill=c,
    )


def _draw_briefcase(draw, s: int) -> None:
    """Briefcase with handle and latch."""
    c = _FG
    stroke = max(3, s // 22)
    # Body
    draw.rounded_rectangle(
        [(int(s * 0.15), int(s * 0.38)), (int(s * 0.85), int(s * 0.82))],
        radius=int(s * 0.05), fill=c,
    )
    # Handle
    draw.rounded_rectangle(
        [(int(s * 0.36), int(s * 0.20)), (int(s * 0.64), int(s * 0.38))],
        radius=int(s * 0.04), outline=c, width=stroke, fill=None,
    )
    # Inner handle hole
    draw.rectangle(
        [(int(s * 0.44), int(s * 0.25)), (int(s * 0.56), int(s * 0.33))],
        fill="#00000000" if False else None,
    )
    # Latch (dollar-sign horizontal bar)
    bg_hole = None  # we'll cut a contrasting notch
    # Dividing band across briefcase
    draw.rectangle(
        [(int(s * 0.15), int(s * 0.52)), (int(s * 0.85), int(s * 0.58))],
        fill="#00000055",
    )
    # Latch knob
    draw.rectangle(
        [(int(s * 0.46), int(s * 0.50)), (int(s * 0.54), int(s * 0.60))],
        fill="#00000099",
    )


def _draw_pie(draw, s: int) -> None:
    """Diversified pie chart — five wedges of slightly different shades."""
    c = _FG
    mid = s // 2
    r = int(s * 0.36)
    bbox = [(mid - r, mid - r), (mid + r, mid + r)]
    # Outer white circle
    draw.ellipse(bbox, fill=c)
    # Pie wedges — use semi-transparent black overlays to shade sectors
    wedges = [
        (0, 72, "#00000000"),       # top-right   — no overlay
        (72, 144, "#00000055"),
        (144, 216, "#00000022"),
        (216, 288, "#00000088"),
        (288, 360, "#00000033"),
    ]
    for start, end, overlay in wedges:
        if overlay == "#00000000":
            continue
        draw.pieslice(bbox, start=start, end=end, fill=overlay)
    # Slice divider lines
    line_w = max(2, s // 40)
    for deg in (0, 72, 144, 216, 288):
        rad = math.radians(deg - 90)
        x = mid + int(math.cos(rad) * r)
        y = mid + int(math.sin(rad) * r)
        draw.line([(mid, mid), (x, y)], fill="#000000", width=line_w)


def _draw_pie_vs(draw, s: int) -> None:
    """Two small pies with a beam across — Compare-ETF."""
    c = _FG
    stroke = max(3, s // 26)
    r = int(s * 0.18)
    left_cx, right_cx, cy = int(s * 0.28), int(s * 0.72), int(s * 0.58)
    # Left pie
    bbox_l = [(left_cx - r, cy - r), (left_cx + r, cy + r)]
    draw.ellipse(bbox_l, fill=c)
    draw.pieslice(bbox_l, start=-30, end=120, fill="#00000077")
    # Right pie
    bbox_r = [(right_cx - r, cy - r), (right_cx + r, cy + r)]
    draw.ellipse(bbox_r, fill=c)
    draw.pieslice(bbox_r, start=120, end=260, fill="#00000077")
    # Beam connecting them
    draw.line([(left_cx, int(s * 0.26)), (right_cx, int(s * 0.26))],
              fill=c, width=stroke)
    draw.line([(left_cx, int(s * 0.26)), (left_cx, cy - r)], fill=c, width=max(2, s // 40))
    draw.line([(right_cx, int(s * 0.26)), (right_cx, cy - r)], fill=c, width=max(2, s // 40))
    # Top knob
    draw.ellipse(
        [(int(s * 0.48), int(s * 0.15)),
         (int(s * 0.52), int(s * 0.19))],
        fill=c,
    )
    # Center pole
    draw.line([(int(s * 0.5), int(s * 0.19)), (int(s * 0.5), int(s * 0.26))],
              fill=c, width=stroke)


def _draw_bolt(draw, s: int) -> None:
    """Classic lightning bolt — symmetric, bold."""
    c = _FG
    draw.polygon(
        [
            (int(s * 0.58), int(s * 0.08)),   # top right
            (int(s * 0.22), int(s * 0.52)),   # mid left
            (int(s * 0.44), int(s * 0.52)),
            (int(s * 0.36), int(s * 0.92)),   # bottom
            (int(s * 0.78), int(s * 0.42)),   # mid right
            (int(s * 0.54), int(s * 0.42)),
            (int(s * 0.66), int(s * 0.08)),
        ],
        fill=c,
    )


def _draw_bank(draw, s: int) -> None:
    """Greek temple / bank facade."""
    c = _FG
    # Pediment (triangle roof)
    draw.polygon(
        [
            (int(s * 0.10), int(s * 0.32)),
            (int(s * 0.90), int(s * 0.32)),
            (int(s * 0.50), int(s * 0.12)),
        ],
        fill=c,
    )
    # Four columns
    col_y_top = int(s * 0.36)
    col_y_bot = int(s * 0.76)
    col_w = int(s * 0.08)
    for xr in (0.22, 0.40, 0.58, 0.76):
        cx = int(s * xr)
        draw.rectangle([(cx - col_w // 2, col_y_top),
                        (cx + col_w // 2, col_y_bot)], fill=c)
    # Base
    draw.rectangle(
        [(int(s * 0.08), int(s * 0.78)), (int(s * 0.92), int(s * 0.88))],
        fill=c,
    )


def _draw_chip(draw, s: int) -> None:
    """Microchip with pins — the CPU look."""
    c = _FG
    # Pins on all four sides (three per side)
    pin_w = int(s * 0.06)
    pin_l = int(s * 0.08)
    for yr in (0.30, 0.50, 0.70):
        y = int(s * yr)
        # Left pins
        draw.rectangle([(int(s * 0.06), y - pin_w // 2),
                        (int(s * 0.06) + pin_l, y + pin_w // 2)], fill=c)
        # Right pins
        draw.rectangle([(s - int(s * 0.06) - pin_l, y - pin_w // 2),
                        (s - int(s * 0.06), y + pin_w // 2)], fill=c)
    for xr in (0.30, 0.50, 0.70):
        x = int(s * xr)
        # Top pins
        draw.rectangle([(x - pin_w // 2, int(s * 0.06)),
                        (x + pin_w // 2, int(s * 0.06) + pin_l)], fill=c)
        # Bottom pins
        draw.rectangle([(x - pin_w // 2, s - int(s * 0.06) - pin_l),
                        (x + pin_w // 2, s - int(s * 0.06))], fill=c)
    # Chip body
    draw.rounded_rectangle(
        [(int(s * 0.20), int(s * 0.20)), (int(s * 0.80), int(s * 0.80))],
        radius=int(s * 0.05), fill=c,
    )
    # Inner marking — a square ring
    draw.rounded_rectangle(
        [(int(s * 0.32), int(s * 0.32)), (int(s * 0.68), int(s * 0.68))],
        radius=int(s * 0.03), outline="#00000099", width=max(2, s // 30),
    )


def _draw_cross(draw, s: int) -> None:
    """Medical cross — bold plus sign."""
    c = _FG
    t = int(s * 0.18)
    mid = s // 2
    # Vertical bar
    draw.rounded_rectangle(
        [(mid - t, int(s * 0.15)), (mid + t, int(s * 0.85))],
        radius=int(s * 0.03), fill=c,
    )
    # Horizontal bar
    draw.rounded_rectangle(
        [(int(s * 0.15), mid - t), (int(s * 0.85), mid + t)],
        radius=int(s * 0.03), fill=c,
    )


def _draw_gem(draw, s: int) -> None:
    """Faceted gemstone / diamond."""
    c = _FG
    # Top facets
    draw.polygon(
        [
            (int(s * 0.50), int(s * 0.16)),
            (int(s * 0.10), int(s * 0.40)),
            (int(s * 0.30), int(s * 0.40)),
            (int(s * 0.50), int(s * 0.16)),
        ],
        fill=c,
    )
    draw.polygon(
        [
            (int(s * 0.50), int(s * 0.16)),
            (int(s * 0.90), int(s * 0.40)),
            (int(s * 0.70), int(s * 0.40)),
            (int(s * 0.50), int(s * 0.16)),
        ],
        fill=c,
    )
    draw.polygon(
        [
            (int(s * 0.30), int(s * 0.40)),
            (int(s * 0.50), int(s * 0.16)),
            (int(s * 0.70), int(s * 0.40)),
        ],
        fill=c,
    )
    # Main body (trapezoid meeting point at bottom)
    draw.polygon(
        [
            (int(s * 0.10), int(s * 0.40)),
            (int(s * 0.90), int(s * 0.40)),
            (int(s * 0.50), int(s * 0.90)),
        ],
        fill=c,
    )
    # Facet lines
    line_w = max(2, s // 40)
    draw.line([(int(s * 0.30), int(s * 0.40)), (int(s * 0.50), int(s * 0.90))],
              fill="#00000099", width=line_w)
    draw.line([(int(s * 0.70), int(s * 0.40)), (int(s * 0.50), int(s * 0.90))],
              fill="#00000099", width=line_w)
    draw.line([(int(s * 0.50), int(s * 0.16)), (int(s * 0.50), int(s * 0.40))],
              fill="#00000099", width=line_w)


def _draw_bag(draw, s: int) -> None:
    """Shopping bag with two handles."""
    c = _FG
    stroke = max(3, s // 22)
    # Body
    draw.rounded_rectangle(
        [(int(s * 0.20), int(s * 0.40)), (int(s * 0.80), int(s * 0.88))],
        radius=int(s * 0.05), fill=c,
    )
    # Left handle (arc)
    draw.arc(
        [(int(s * 0.26), int(s * 0.18)), (int(s * 0.48), int(s * 0.52))],
        start=180, end=360, fill=c, width=stroke,
    )
    # Right handle
    draw.arc(
        [(int(s * 0.52), int(s * 0.18)), (int(s * 0.74), int(s * 0.52))],
        start=180, end=360, fill=c, width=stroke,
    )
    # Accent / fold line
    draw.rectangle(
        [(int(s * 0.20), int(s * 0.46)), (int(s * 0.80), int(s * 0.52))],
        fill="#00000055",
    )


def _draw_cart(draw, s: int) -> None:
    """Shopping cart with wheels."""
    c = _FG
    stroke = max(3, s // 26)
    # Handle stem
    draw.line([(int(s * 0.08), int(s * 0.22)), (int(s * 0.22), int(s * 0.22))],
              fill=c, width=stroke)
    draw.line([(int(s * 0.22), int(s * 0.22)), (int(s * 0.32), int(s * 0.40))],
              fill=c, width=stroke)
    # Basket (trapezoid)
    draw.polygon(
        [
            (int(s * 0.22), int(s * 0.40)),
            (int(s * 0.88), int(s * 0.40)),
            (int(s * 0.78), int(s * 0.66)),
            (int(s * 0.32), int(s * 0.66)),
        ],
        fill=c,
    )
    # Vertical basket dividers
    for xr in (0.42, 0.55, 0.68):
        draw.line([(int(s * xr), int(s * 0.40)),
                   (int(s * xr) - int(s * 0.03), int(s * 0.66))],
                  fill="#00000088", width=max(2, s // 40))
    # Wheels
    wheel_r = int(s * 0.08)
    for cx_r in (0.40, 0.72):
        cx = int(s * cx_r)
        cy = int(s * 0.80)
        draw.ellipse([(cx - wheel_r, cy - wheel_r), (cx + wheel_r, cy + wheel_r)], fill=c)
        draw.ellipse(
            [(cx - wheel_r // 2, cy - wheel_r // 2),
             (cx + wheel_r // 2, cy + wheel_r // 2)],
            fill="#00000088",
        )


def _draw_gear(draw, s: int) -> None:
    """Gear with 8 rounded teeth and a center hole."""
    c = _FG
    mid = s // 2
    # Eight teeth around a circle
    tooth_r = int(s * 0.08)
    outer_r = int(s * 0.38)
    for i in range(8):
        angle = i * (2 * math.pi / 8)
        x = mid + math.cos(angle) * outer_r
        y = mid + math.sin(angle) * outer_r
        draw.ellipse(
            [(x - tooth_r, y - tooth_r), (x + tooth_r, y + tooth_r)],
            fill=c,
        )
    # Body
    body_r = int(s * 0.32)
    draw.ellipse(
        [(mid - body_r, mid - body_r), (mid + body_r, mid + body_r)],
        fill=c,
    )
    # Center hole (contrast)
    hole_r = int(s * 0.12)
    draw.ellipse(
        [(mid - hole_r, mid - hole_r), (mid + hole_r, mid + hole_r)],
        fill="#00000099",
    )


def _draw_drop(draw, s: int) -> None:
    """Water drop — teardrop with highlight."""
    c = _FG
    # Teardrop: a tall triangle on top, a half-circle on the bottom
    mid = s // 2
    # Triangular top
    draw.polygon(
        [
            (mid, int(s * 0.10)),
            (int(s * 0.24), int(s * 0.54)),
            (int(s * 0.76), int(s * 0.54)),
        ],
        fill=c,
    )
    # Rounded bottom (half-circle)
    draw.pieslice(
        [(int(s * 0.24), int(s * 0.36)), (int(s * 0.76), int(s * 0.88))],
        start=0, end=180, fill=c,
    )
    # Subtle highlight (small ellipse)
    draw.ellipse(
        [(int(s * 0.38), int(s * 0.50)), (int(s * 0.46), int(s * 0.60))],
        fill="#ffffff",
    )


def _draw_tower(draw, s: int) -> None:
    """Signal tower with broadcast waves."""
    c = _FG
    stroke = max(3, s // 24)
    mid = s // 2
    base_y = int(s * 0.78)
    # Tower tripod legs
    draw.line([(mid, int(s * 0.30)), (int(s * 0.30), base_y)], fill=c, width=stroke)
    draw.line([(mid, int(s * 0.30)), (int(s * 0.70), base_y)], fill=c, width=stroke)
    draw.line([(int(s * 0.34), int(s * 0.60)), (int(s * 0.66), int(s * 0.60))],
              fill=c, width=stroke)
    # Emitter ball
    draw.ellipse(
        [(mid - int(s * 0.06), int(s * 0.24)),
         (mid + int(s * 0.06), int(s * 0.36))],
        fill=c,
    )
    # Signal arcs (two)
    for r_ratio, w_mult in ((0.22, 1), (0.30, 1)):
        r = int(s * r_ratio)
        # Left arc
        draw.arc(
            [(mid - r, int(s * 0.30) - r), (mid + r, int(s * 0.30) + r)],
            start=200, end=250, fill=c, width=max(2, int(stroke * w_mult)),
        )
        # Right arc
        draw.arc(
            [(mid - r, int(s * 0.30) - r), (mid + r, int(s * 0.30) + r)],
            start=290, end=340, fill=c, width=max(2, int(stroke * w_mult)),
        )
    # Base
    draw.rectangle(
        [(int(s * 0.24), base_y), (int(s * 0.76), base_y + int(s * 0.06))],
        fill=c,
    )


def _draw_house(draw, s: int) -> None:
    """Simple house with a peaked roof, door and window."""
    c = _FG
    # Roof
    draw.polygon(
        [
            (int(s * 0.12), int(s * 0.48)),
            (int(s * 0.88), int(s * 0.48)),
            (int(s * 0.50), int(s * 0.14)),
        ],
        fill=c,
    )
    # Chimney
    draw.rectangle(
        [(int(s * 0.66), int(s * 0.16)), (int(s * 0.76), int(s * 0.36))],
        fill=c,
    )
    # Body
    draw.rectangle(
        [(int(s * 0.20), int(s * 0.48)), (int(s * 0.80), int(s * 0.88))],
        fill=c,
    )
    # Door (dark)
    draw.rectangle(
        [(int(s * 0.44), int(s * 0.66)), (int(s * 0.56), int(s * 0.88))],
        fill="#00000088",
    )
    # Doorknob
    draw.ellipse(
        [(int(s * 0.53), int(s * 0.77)), (int(s * 0.55), int(s * 0.79))],
        fill=c,
    )
    # Windows (two)
    for xr in (0.26, 0.66):
        draw.rectangle(
            [(int(s * xr), int(s * 0.54)),
             (int(s * xr) + int(s * 0.10), int(s * 0.64))],
            fill="#00000088",
        )
        # Window cross
        x1 = int(s * xr)
        x2 = x1 + int(s * 0.10)
        ym = (int(s * 0.54) + int(s * 0.64)) // 2
        xm = (x1 + x2) // 2
        draw.line([(xm, int(s * 0.54)), (xm, int(s * 0.64))], fill=c, width=max(1, s // 60))
        draw.line([(x1, ym), (x2, ym)], fill=c, width=max(1, s // 60))


def _draw_palette(draw, s: int) -> None:
    """Painter's palette glyph for the theme editor."""
    c = "white"
    # Body of the palette — rounded blob.
    draw.ellipse([int(s * 0.10), int(s * 0.18),
                  int(s * 0.86), int(s * 0.86)], fill=c)
    # Thumbhole (cut-out circle bottom-right).
    draw.ellipse([int(s * 0.55), int(s * 0.46),
                  int(s * 0.78), int(s * 0.70)], fill=spec_bg(s))
    # Six paint dabs in distinct colours.
    palette_colors = ["#f38ba8", "#f9e2af", "#a6e3a1", "#94e2d5",
                       "#89b4fa", "#cba6f7"]
    centers = [
        (int(s * 0.26), int(s * 0.34)),
        (int(s * 0.40), int(s * 0.26)),
        (int(s * 0.56), int(s * 0.30)),
        (int(s * 0.66), int(s * 0.42)),
        (int(s * 0.32), int(s * 0.62)),
        (int(s * 0.48), int(s * 0.70)),
    ]
    r = int(s * 0.07)
    for (cx, cy), col in zip(centers, palette_colors):
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)


def spec_bg(s: int) -> str:
    """Return the current icon background colour for cut-outs (best-effort)."""
    # The palette glyph is rendered after the rounded-rect background, so
    # we cut the thumbhole back to the icon's background colour. We can't
    # access the background from inside the draw helper, so we use a
    # transparent stand-in (rendered as the panel bg by Tk).
    return "#000000"


def _draw_vault(draw, s: int) -> None:
    """Greek-temple bank — same as the financials sector glyph but slightly
    taller, used for mutual / index funds (traditional / institutional feel)."""
    _draw_bank(draw, s)


def _draw_vault_vs(draw, s: int) -> None:
    """Two-fund head-to-head: small temple on each side of a center bar."""
    c = "white"
    pad = int(s * 0.10)
    bar_w = max(2, s // 26)
    # Left mini temple ----------------------------------------------------
    left_x1 = pad
    left_x2 = int(s * 0.42)
    base_y = int(s * 0.82)
    roof_y = int(s * 0.42)
    draw.rectangle([left_x1, int(s * 0.74), left_x2, base_y], fill=c)
    draw.polygon([
        (left_x1, int(s * 0.50)),
        ((left_x1 + left_x2) // 2, roof_y),
        (left_x2, int(s * 0.50)),
    ], fill=c)
    # vertical columns
    for i in range(3):
        cx = left_x1 + int((left_x2 - left_x1) * (0.25 + i * 0.25))
        draw.rectangle([cx - 1, int(s * 0.55), cx + 1, int(s * 0.74)], fill=c)
    # Right mini temple ---------------------------------------------------
    right_x1 = int(s * 0.58)
    right_x2 = s - pad
    draw.rectangle([right_x1, int(s * 0.74), right_x2, base_y], fill=c)
    draw.polygon([
        (right_x1, int(s * 0.50)),
        ((right_x1 + right_x2) // 2, roof_y),
        (right_x2, int(s * 0.50)),
    ], fill=c)
    for i in range(3):
        cx = right_x1 + int((right_x2 - right_x1) * (0.25 + i * 0.25))
        draw.rectangle([cx - 1, int(s * 0.55), cx + 1, int(s * 0.74)], fill=c)
    # Center divider
    cx = s // 2
    draw.rectangle([cx - bar_w // 2, int(s * 0.30),
                    cx + bar_w // 2, int(s * 0.86)], fill=c)
    # Versus chevrons
    draw.polygon([(cx - bar_w * 2, int(s * 0.20)),
                  (cx + bar_w * 2, int(s * 0.20)),
                  (cx, int(s * 0.30))], fill=c)


_GLYPH_FNS = {
    "candles": _draw_candles,
    "scales": _draw_scales,
    "briefcase": _draw_briefcase,
    "pie": _draw_pie,
    "pie_vs": _draw_pie_vs,
    "vault": _draw_vault,
    "vault_vs": _draw_vault_vs,
    "palette": _draw_palette,
    "bolt": _draw_bolt,
    "bank": _draw_bank,
    "chip": _draw_chip,
    "cross": _draw_cross,
    "gem": _draw_gem,
    "bag": _draw_bag,
    "cart": _draw_cart,
    "gear": _draw_gear,
    "drop": _draw_drop,
    "tower": _draw_tower,
    "house": _draw_house,
}


def _render_icon(command: str, out_path: Path) -> bool:
    """Render one icon at 4× resolution then downsample for anti-aliasing."""
    pil = _pil()
    if pil is None:
        return False
    Image, ImageDraw = pil

    spec = _CATALOG.get(command)
    if spec is None:
        return False
    glyph_fn = _GLYPH_FNS.get(spec["glyph"])
    if glyph_fn is None:
        return False

    # Render at 4× size on a transparent canvas.
    big = Image.new("RGBA", (_RENDER_SIZE, _RENDER_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(big, "RGBA")
    _rounded_bg(draw, _RENDER_SIZE, spec["bg"], radius_ratio=0.22)
    glyph_fn(draw, _RENDER_SIZE)

    # Downsample with Lanczos for crisp strokes at small size.
    small = big.resize((ICON_SIZE, ICON_SIZE), resample=Image.LANCZOS)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    small.save(out_path, format="PNG")
    return True


def generate_all(force: bool = False) -> int:
    """Generate every icon. Returns how many were rendered."""
    rendered = 0
    for command in _CATALOG:
        out = _ICONS_DIR / f"{command}.png"
        if out.exists() and not force:
            continue
        if _render_icon(command, out):
            rendered += 1
    return rendered


def icons_dir() -> Path:
    return _ICONS_DIR


def get_icon_path(command: str) -> Optional[Path]:
    """Return the on-disk path to the icon, generating on miss.

    Returns None if PIL isn't available AND the icon hasn't already been
    rendered.
    """
    if command not in _CATALOG:
        return None
    path = _ICONS_DIR / f"{command}.png"
    if path.exists():
        return path
    if _render_icon(command, path):
        return path
    return None


def icon_glyph(command: str) -> str:
    """Return the Unicode glyph used by the TUI for *command*."""
    spec = _CATALOG.get(command)
    return spec["tui"] if spec else "•"
