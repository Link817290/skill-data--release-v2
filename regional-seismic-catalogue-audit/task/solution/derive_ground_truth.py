#!/usr/bin/env python3
"""Generate the expected report from the bundled materials."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reference_solution import build_report

out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "tests" / "ground_truth.json"
out.write_text(__import__("json").dumps(build_report(str(Path(__file__).resolve().parents[1] / "environment" / "workspace" / "materials")), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
