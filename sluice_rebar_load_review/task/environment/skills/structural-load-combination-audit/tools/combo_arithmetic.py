#!/usr/bin/env python3
"""Compute signed intermediate load totals; never assigns a project verdict."""
import argparse
import json
from decimal import Decimal


def dec(value):
    return Decimal(str(value))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="JSON file with components and optional expected values")
    args = ap.parse_args()
    try:
        payload = json.loads(args.input)
    except json.JSONDecodeError:
        payload = json.load(open(args.input, encoding="utf-8"))
    c = {k: dec(v) for k, v in (payload.get("components") or {}).items()}
    out = {}
    if "downward" in c or "upward" in c:
        out["net_vertical"] = str(c.get("downward", Decimal("0")) - c.get("upward", Decimal("0")))
    moments = [v for k, v in c.items() if k.endswith("_moment")]
    if moments:
        out["signed_moment_sum"] = str(sum(moments, Decimal("0")))
    out["component_count"] = len(c)
    if payload.get("expected"):
        out["expected_values_echoed_for_comparison"] = {k: str(dec(v)) for k, v in payload["expected"].items()}
    print(json.dumps(out, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
