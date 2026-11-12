#!/usr/bin/env python3
"""Compatibility entry point for the material-derived reference solution."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from reference_solution import build_report, main


if __name__ == "__main__":
    raise SystemExit(main())
