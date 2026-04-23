"""Hidden features. Harmless, seasonal, and entirely optional."""

from __future__ import annotations

import datetime
import random

__all__ = ["LYNX_HUNT", "MARKET_QUIPS", "pick_easter_egg", "konami_match"]


LYNX_HUNT = r"""
[bold green]                 /\\_/\\
                ( o.o )
                 > ^ <          [bold white]The lynx hunts value in the markets.[/]
           .---./     \\.---.
          (   /   _   \\   )
           '-(   | |   )-'
              \\  \\_/  /
               '-----'[/]
"""

WOLF_ASCII = r"""
[bold cyan]             __
            / _)             [bold white]"Buy low, sell high."[/]
      .-^^^-/ /               [dim]— the old rule[/]
   __/       /
  <__.|_|-|_|[/]
"""

BULL_VS_BEAR = r"""
[bold yellow]       ___        [/]        [bold red]           ___[/]
[bold yellow]     ((_))        [/]        [bold red]       ___((_))[/]
[bold yellow]    //   \\\\       [/]  vs.  [bold red]      /     /  [/]
[bold yellow]   // B U L L      [/]        [bold red]     /  B E A R[/]
[bold yellow]  //     \\\\       [/]        [bold red]    /       \\\\[/]
"""


MARKET_QUIPS = (
    "Margin of safety first. Returns second.",
    "Price is what you pay. Value is what you get.",
    "Be fearful when others are greedy, and greedy when others are fearful.",
    "The stock market is a device for transferring money from the impatient to the patient.",
    "Risk comes from not knowing what you're doing.",
    "In the short run the market is a voting machine; in the long run, a weighing machine.",
    "Never invest in a business you cannot understand.",
    "Compound interest is the eighth wonder of the world.",
    "If a business does well, the stock eventually follows.",
    "Time in the market beats timing the market.",
)


# The konami-style sequence the TUI watches for — classic, harmless.
KONAMI_SEQUENCE = (
    "up", "up", "down", "down",
    "left", "right", "left", "right",
    "b", "a",
)


def konami_match(keystrokes: list[str]) -> bool:
    """Return True when the tail of *keystrokes* matches the konami sequence."""
    n = len(KONAMI_SEQUENCE)
    return len(keystrokes) >= n and tuple(keystrokes[-n:]) == KONAMI_SEQUENCE


def pick_easter_egg(seed: str = "") -> str:
    """Return a Rich-markup easter-egg block appropriate for today.

    Uses the current date so the output stays consistent within a day but
    still surprises users who try the egg more than once a month.
    """
    today = datetime.date.today()
    rng = random.Random(seed or today.isoformat())
    roll = rng.randint(0, 2)
    if roll == 0:
        art = LYNX_HUNT
    elif roll == 1:
        art = WOLF_ASCII
    else:
        art = BULL_VS_BEAR
    quip = rng.choice(MARKET_QUIPS)
    return f"{art}\n[italic]{quip}[/]"
