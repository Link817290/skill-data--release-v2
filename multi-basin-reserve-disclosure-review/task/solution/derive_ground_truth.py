#!/usr/bin/env python3
"""Derive verifier ground truth from the generated expert register."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


WEIGHTS = {
    "R-01": 0.10,
    "R-02": 0.14,
    "R-03": 0.12,
    "R-04": 0.11,
    "R-05": 0.11,
    "R-06": 0.11,
    "R-07": 0.06,
    "R-08": 0.07,
    "R-09": 0.05,
    "R-10": 0.05,
    "evidence_and_closure": 0.08,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("register", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()

    with args.register.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    by_id = {row.get("review_id", ""): row for row in rows}
    expected = set(WEIGHTS) - {"evidence_and_closure"}
    if set(by_id) != expected:
        raise RuntimeError("generated expert register does not contain the expected matters")
    if abs(sum(WEIGHTS.values()) - 1.0) > 1e-9:
        raise RuntimeError("dimension weights do not sum to one")

    payload = {
        "weights": WEIGHTS,
        "expert_matters": [by_id[key] for key in sorted(expected)],
        "required_outputs": [
            "reserve_disclosure_review.md",
            "reserve_disclosure_register.csv",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
