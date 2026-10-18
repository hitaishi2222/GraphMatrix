"""Console entry point: ``python -m graphmatrix``."""

from __future__ import annotations

import sys


def main() -> int:
    from graphmatrix.cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
