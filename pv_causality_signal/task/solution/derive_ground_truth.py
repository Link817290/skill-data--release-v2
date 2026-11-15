#!/usr/bin/env python3
"""Derive verifier anchors from a solved professional deliverable."""
from __future__ import annotations

import json
import hashlib
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) not in {3, 4}:
        raise SystemExit("usage: derive_ground_truth.py GOLD_JSON OUTPUT_JSON [WORKSPACE]")
    source = Path(sys.argv[1])
    output = Path(sys.argv[2])
    book = json.loads(source.read_text(encoding="utf-8"))
    required = {
        "universes",
        "pair_assessments",
        "version_driver_assessments",
        "case_assessments",
        "longitudinal_assessments",
    }
    missing = sorted(required - set(book))
    if missing:
        raise SystemExit(f"gold deliverable is missing: {', '.join(missing)}")
    anchors = {key: book[key] for key in sorted(required)}
    if len(sys.argv) == 4:
        workspace = Path(sys.argv[3])
        protected = [
            path for path in workspace.rglob("*")
            if path.is_file() and path.name != "faers_adjudication.json"
        ]
        anchors["source_sha256"] = {
            path.relative_to(workspace).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(protected)
        }
    output.write_text(json.dumps(anchors, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
