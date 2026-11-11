#!/usr/bin/env python3
"""Audit an exported allocation for uniqueness, eligibility, and capacity feasibility."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def normalized(value: Any) -> str:
    return str(value or "").strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("decisions", type=Path)
    parser.add_argument("capacities", type=Path)
    parser.add_argument("--unit-id", required=True)
    parser.add_argument("--facility-id", required=True)
    parser.add_argument("--status-column", required=True)
    parser.add_argument("--assigned-value", required=True)
    parser.add_argument("--capacity-column", required=True)
    parser.add_argument("--load-column")
    parser.add_argument("--allowed-pairs", type=Path)
    parser.add_argument("--allowed-unit-id")
    parser.add_argument("--allowed-facility-id")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    decisions = read_csv(args.decisions)
    capacity_rows = read_csv(args.capacities)
    capacity = {}
    input_errors = []
    for row_number, row in enumerate(capacity_rows, start=2):
        facility = normalized(row.get(args.facility_id))
        try:
            value = float(normalized(row.get(args.capacity_column)))
        except ValueError:
            input_errors.append({"file": str(args.capacities), "row": row_number, "error": "invalid capacity"})
            continue
        if not facility or value < 0:
            input_errors.append({"file": str(args.capacities), "row": row_number, "error": "missing facility or negative capacity"})
            continue
        if facility in capacity:
            input_errors.append({"file": str(args.capacities), "row": row_number, "error": "duplicate facility", "facility": facility})
        capacity[facility] = value

    allowed = None
    if args.allowed_pairs:
        allowed_unit = args.allowed_unit_id or args.unit_id
        allowed_facility = args.allowed_facility_id or args.facility_id
        allowed = {
            (normalized(row.get(allowed_unit)), normalized(row.get(allowed_facility)))
            for row in read_csv(args.allowed_pairs)
        }

    seen = Counter()
    loads = Counter()
    unknown_facilities = []
    ineligible = []
    invalid_loads = []
    assigned_rows = 0
    for row_number, row in enumerate(decisions, start=2):
        unit = normalized(row.get(args.unit_id))
        if unit:
            seen[unit] += 1
        if normalized(row.get(args.status_column)).casefold() != args.assigned_value.casefold():
            continue
        assigned_rows += 1
        facility = normalized(row.get(args.facility_id))
        try:
            load = float(normalized(row.get(args.load_column))) if args.load_column else 1.0
        except ValueError:
            invalid_loads.append({"row": row_number, "unit": unit, "value": row.get(args.load_column)})
            continue
        if load < 0:
            invalid_loads.append({"row": row_number, "unit": unit, "value": load})
            continue
        if facility not in capacity:
            unknown_facilities.append({"row": row_number, "unit": unit, "facility": facility})
            continue
        loads[facility] += load
        if allowed is not None and (unit, facility) not in allowed:
            ineligible.append({"row": row_number, "unit": unit, "facility": facility})

    duplicate_units = {unit: count for unit, count in seen.items() if count > 1}
    over_capacity = {
        facility: {"load": loads[facility], "capacity": limit, "overage": loads[facility] - limit}
        for facility, limit in capacity.items()
        if loads[facility] > limit + 1e-9
    }
    result = {
        "feasible": not any((input_errors, duplicate_units, unknown_facilities, ineligible, invalid_loads, over_capacity)),
        "decision_rows": len(decisions),
        "assigned_rows": assigned_rows,
        "distinct_units": len(seen),
        "facility_loads": dict(loads),
        "input_errors": input_errors,
        "duplicate_units": duplicate_units,
        "unknown_facilities": unknown_facilities,
        "ineligible_assignments": ineligible,
        "invalid_loads": invalid_loads,
        "capacity_overages": over_capacity,
    }
    rendered = json.dumps(result, indent=2, ensure_ascii=True, sort_keys=True) + "\n"
    if args.report:
        args.report.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if result["feasible"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

