#!/usr/bin/env python3
"""Derive verifier facts after the source-derived reference workbook exists."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from openpyxl import load_workbook


def norm(value) -> str:
    return str(value).strip().upper() if value is not None else ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from reference_solution import build_options, load_problem, solve_assignment

    problem = load_problem(args.source)
    _, eligible = build_options(problem)

    wb = load_workbook(args.gold, read_only=True, data_only=False)
    ws = wb["Order Allocation"]
    headers = {norm(cell.value): i for i, cell in enumerate(next(ws.iter_rows(values_only=False)))}
    required = ["ORDER ID", "DECISION", "FACILITY"]
    if any(name not in headers for name in required):
        raise RuntimeError("gold allocation headers are incomplete")

    assigned = 0
    assigned_ids: list[str] = []
    unassigned_ids: list[str] = []
    primary_facilities: set[str] = set()
    for row in ws.iter_rows(min_row=2, values_only=True):
        order_id = str(row[headers["ORDER ID"]]).strip()
        decision = norm(row[headers["DECISION"]])
        if decision == "ASSIGNED":
            assigned += 1
            assigned_ids.append(order_id)
            primary_facilities.add(str(row[headers["FACILITY"]]).strip())
        elif decision == "UNASSIGNED":
            unassigned_ids.append(order_id)
    wb.close()

    structural_ids = [
        order.order_id for order in problem["orders"] if not eligible.get(order.index)
    ]
    capacities = problem["capacities"]
    reference_cost = 0.0
    formula_wb = load_workbook(args.gold, read_only=True, data_only=False)
    aws = formula_wb["Order Allocation"]
    h = {norm(cell.value): i for i, cell in enumerate(next(aws.iter_rows(values_only=False)))}
    by_order = {order.order_id: order for order in problem["orders"]}
    options, _ = build_options(problem)
    option_lookup = {(problem["orders"][idx].order_id, plant): option for (idx, plant), option in options.items()}
    for row in aws.iter_rows(min_row=2, values_only=True):
        if norm(row[h["DECISION"]]) != "ASSIGNED":
            continue
        order_id = str(row[h["ORDER ID"]]).strip()
        plant = str(row[h["FACILITY"]]).strip()
        option = option_lookup.get((order_id, plant))
        if option is None:
            raise RuntimeError(f"gold contains an invalid assignment: {order_id} -> {plant}")
        reference_cost += option.total_cost
    formula_wb.close()

    outage_screen = {}
    for facility in problem["plants"]:
        recovery, recoverable, recovery_cost, recovery_used = solve_assignment(
            problem, options, unavailable=facility
        )
        structural_count = sum(
            1 for order in problem["orders"]
            if not [plant for plant in eligible.get(order.index, []) if plant != facility]
        )
        outage_screen[facility] = {
            "maximum_service": recoverable,
            "minimum_variable_cost": recovery_cost,
            "facilities_used": recovery_used,
            "structural_unassigned": structural_count,
            "capacity_unassigned": len(problem["orders"]) - recoverable - structural_count,
            "assigned_ids": [problem["orders"][idx].order_id for idx in sorted(recovery)],
        }
    governing_facility = min(
        primary_facilities,
        key=lambda facility: (
            outage_screen[facility]["maximum_service"],
            -outage_screen[facility]["minimum_variable_cost"],
            facility,
        ),
    )

    payload = {
        "source_sha256": hashlib.sha256(args.source.read_bytes()).hexdigest(),
        "order_count": len(problem["orders"]),
        "order_ids": [order.order_id for order in problem["orders"]],
        "facility_ids": problem["plants"],
        "capacities": capacities,
        "maximum_service": assigned,
        "minimum_primary_facilities": len(primary_facilities),
        "gold_primary_facilities": sorted(primary_facilities),
        "reference_variable_cost": reference_cost,
        "structural_unassigned_ids": structural_ids,
        "gold_assigned_ids": assigned_ids,
        "gold_unassigned_ids": unassigned_ids,
        "outage_screen": outage_screen,
        "gold_governing_outage": governing_facility,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
