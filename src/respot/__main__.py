"""Console entry point: ``python -m respot``."""

from __future__ import annotations

import sys


def main() -> int:
    from respot.cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())