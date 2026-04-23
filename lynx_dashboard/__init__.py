"""Lynx Dashboard — Unified launcher for the Lince Investor Suite."""

from __future__ import annotations

from pathlib import Path

from lynx_investor_core import (
    LICENSE_NAME,
    LICENSE_TEXT,
    SUITE_LABEL,
    SUITE_NAME,
    SUITE_VERSION,
    __author__,
    __author_email__,
    __license__,
    __year__,
)

__version__ = "5.5"
APP_NAME = "Lynx Dashboard"
APP_SHORT_NAME = "Dashboard"
APP_TAGLINE = "Unified Launcher & Command Center"
APP_SCOPE = "the whole Lince Investor Suite"
PROG_NAME = "lynx-dashboard"
PACKAGE_NAME = "lynx_dashboard"

DESCRIPTION = (
    "Lynx Dashboard is the unified entry point to the Lince Investor Suite. "
    "It showcases every app and every sector-specialized agent, suggests the "
    "right agent for any company you type in, and launches any of them in the "
    "same interface mode you used to enter the dashboard.\n\n"
    "Apps: lynx-fundamental, lynx-compare, lynx-portfolio.\n"
    "Agents: 11 sector-specialized lynx-investor-* agents covering the entire "
    "GICS universe — from basic materials to utilities.\n\n"
    "Modes: console, interactive, Textual TUI, Tkinter GUI."
)


def get_logo_ascii() -> str:
    """Load the ASCII logo shared with the rest of the suite."""
    from lynx_investor_core.logo import load_logo_ascii
    return load_logo_ascii(Path(__file__).resolve().parent.parent) or ""


def get_about_text() -> dict:
    """Return the uniform About dict used by every renderer."""
    from lynx_investor_core.about import AgentMeta, build_about
    meta = AgentMeta(
        app_name=APP_NAME,
        short_name=APP_SHORT_NAME,
        tagline=APP_TAGLINE,
        package_name=PACKAGE_NAME,
        prog_name=PROG_NAME,
        version=__version__,
        description=DESCRIPTION,
        scope_description=APP_SCOPE,
    )
    about = build_about(meta, logo_ascii=get_logo_ascii())
    about["logo"] = about["logo_ascii"]
    return about


__all__ = [
    "APP_NAME",
    "APP_SHORT_NAME",
    "APP_TAGLINE",
    "APP_SCOPE",
    "DESCRIPTION",
    "LICENSE_NAME",
    "LICENSE_TEXT",
    "PACKAGE_NAME",
    "PROG_NAME",
    "SUITE_LABEL",
    "SUITE_NAME",
    "SUITE_VERSION",
    "__author__",
    "__author_email__",
    "__license__",
    "__version__",
    "__year__",
    "get_about_text",
    "get_logo_ascii",
]
