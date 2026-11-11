#!/usr/bin/env python3
"""Check simple roll-forward rows supplied by the user.

Input is a CSV with columns beginning, additions, grants, exercises, vests,
forfeitures, expirations, ending. The script only reports arithmetic differences;
it does not infer or emit domain conclusions.
"""
import csv, sys

def num(v):
    if v is None or str(v).strip() == "": return 0.0
    return float(str(v).replace(",", "").replace("(", "-").replace(")", ""))

if len(sys.argv) != 2:
    raise SystemExit("usage: check_rollforward.py <ledger.csv>")
with open(sys.argv[1], newline="", encoding="utf-8-sig") as fh:
    for row in csv.DictReader(fh):
        expected = num(row.get("beginning")) + num(row.get("additions")) + num(row.get("grants"))
        expected -= num(row.get("exercises")) + num(row.get("vests")) + num(row.get("forfeitures")) + num(row.get("expirations"))
        diff = expected - num(row.get("ending"))
        print(f"{row.get('award_class','row')}: expected={expected:.6f}, ending={num(row.get('ending')):.6f}, difference={diff:.6f}")
