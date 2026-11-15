#!/usr/bin/env python3
"""Validate agent-supplied contingency-table claims without reading source data."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--relative-tolerance", type=float, default=1e-6)
    parser.add_argument("--absolute-tolerance", type=float, default=1e-9)
    return parser.parse_args()


def cells(value: object) -> tuple[int, int, int, int] | None:
    if not isinstance(value, dict):
        return None
    result = []
    for key in ("a", "b", "c", "d"):
        item = value.get(key)
        if not isinstance(item, int) or isinstance(item, bool) or item < 0:
            return None
        result.append(item)
    return tuple(result)  # type: ignore[return-value]


def close(got: object, expected: float, args: argparse.Namespace) -> bool:
    try:
        value = float(got)
    except (TypeError, ValueError):
        return False
    return math.isfinite(value) and math.isclose(
        value,
        expected,
        rel_tol=args.relative_tolerance,
        abs_tol=args.absolute_tolerance,
    )


def validate_table(item: object, args: argparse.Namespace) -> bool:
    if not isinstance(item, dict):
        return False
    table = cells(item.get("cells"))
    size = item.get("universe_size")
    if table is None or not isinstance(size, int) or sum(table) != size or min(table) == 0:
        return False
    a, b, c, d = table
    estimate = (a * d) / (b * c)
    quantile = float(item.get("quantile", 1.96))
    lower = math.exp(math.log(estimate) - quantile * math.sqrt(sum(1 / x for x in table)))
    return close(item.get("claimed_ror"), estimate, args) and close(
        item.get("claimed_lower"), lower, args
    )


def validate_stratified(item: object, args: argparse.Namespace) -> bool:
    if not isinstance(item, dict) or not isinstance(item.get("strata"), list):
        return False
    numerator = 0.0
    denominator = 0.0
    for raw in item["strata"]:
        table = cells(raw)
        if table is None or sum(table) == 0:
            return False
        a, b, c, d = table
        size = sum(table)
        numerator += a * d / size
        denominator += b * c / size
    if numerator == 0 or denominator == 0:
        return False
    return close(item.get("claimed_common_or"), numerator / denominator, args)


def main() -> int:
    args = parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    ordinary = payload.get("tables", []) if isinstance(payload, dict) else []
    stratified = payload.get("stratified", []) if isinstance(payload, dict) else []
    checks = [validate_table(item, args) for item in ordinary]
    checks.extend(validate_stratified(item, args) for item in stratified)
    result = {"claims_checked": len(checks), "all_claims_valid": bool(checks) and all(checks)}
    print(json.dumps(result, indent=2))
    return 0 if result["all_claims_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
