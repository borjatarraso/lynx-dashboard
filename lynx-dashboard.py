#!/usr/bin/env python3
"""
Lynx Dashboard — entry point.
Run directly:   python3 lynx-dashboard.py [args]
Or via pip:     lynx-dashboard [args]
"""
import sys

from lynx_dashboard.cli import run_cli

if __name__ == "__main__":
    sys.exit(run_cli() or 0)
