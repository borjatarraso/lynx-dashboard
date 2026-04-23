"""Entry point for lynx-dashboard.

Propagates ``run_cli()``'s return code to the process exit status so shell
scripts and CI pipelines can detect failures (--info for an unknown name,
--recommend with no match, mutually-exclusive-arg rejections, …).
"""

from __future__ import annotations

import sys

from lynx_dashboard.cli import run_cli


def main() -> int:
    rc = run_cli()
    return int(rc or 0)


if __name__ == "__main__":
    sys.exit(main())
