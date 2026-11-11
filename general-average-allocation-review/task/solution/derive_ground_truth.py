#!/usr/bin/env python3
"""Derive hidden scoring data from completed reference deliverables."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def findings_from_memo(text: str) -> dict[str, dict[str, str]]:
    findings = {}
    for line in text.splitlines():
        match = re.match(r"^\|\s*(F\d{2})\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*$", line)
        if match:
            findings[match.group(1)] = {
                "determination": match.group(2),
                "evidence": match.group(3),
            }
    if len(findings) != 79:
        raise RuntimeError(f"expected 79 reference findings, found {len(findings)}")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden-dir", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    memo = (args.golden_dir / "general_average_review.md").read_text(encoding="utf-8")
    with (args.golden_dir / "general_average_schedule.csv").open(
        newline="", encoding="utf-8-sig"
    ) as stream:
        schedule = list(csv.DictReader(stream))
    if not schedule:
        raise RuntimeError("reference schedule is empty")

    data = {
        "source_sha256": {
            name: sha256(args.workspace / name)
            for name in (
                "general_average_adjustment.pdf",
                "first_instance_judgment.pdf",
                "court_of_appeal_judgment.pdf",
                "final_judgment.pdf",
            )
        },
        "schedule_rows": schedule,
        "findings": findings_from_memo(memo),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
