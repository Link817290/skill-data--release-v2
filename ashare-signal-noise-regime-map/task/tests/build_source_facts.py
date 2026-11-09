#!/usr/bin/env python3
"""Freeze evaluator facts from original CSVs, never from candidate workspace data."""
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = ROOT / "task/environment/workspace"
sys.path.insert(0, str(ROOT / "task/tests"))
from reference_calibration import classify_reference


def read(name):
    with (WORKSPACE / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def main():
    rows, events = read("market_snapshots.csv"), read("events.csv")
    by_sample = {row["sample_id"]: [event["event_id"] for event in events if event["sample_id"] == row["sample_id"]] for row in rows}
    payload = {"source_rows": rows, "events": events, "events_by_sample": by_sample,
               "indicator_dictionary": read("indicator_dictionary.csv"),
               "reference_states": classify_reference(rows, events),
               "source_sha256": {name: hashlib.sha256((WORKSPACE / name).read_bytes()).hexdigest()
                                 for name in ("market_snapshots.csv", "events.csv", "indicator_dictionary.csv")}}
    (ROOT / "task/tests/source_facts.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
