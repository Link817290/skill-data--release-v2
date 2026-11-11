#!/usr/bin/env python3
"""Derive verifier facts from the material-derived reference deliverable."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def identity_category(text: str) -> str:
    return "false" if "FALSE" in text.upper() else "match"


def status_category(text: str) -> str:
    upper = text.upper()
    if "STRADDLES" in upper:
        return "straddle"
    if "OWNERSHIP" in upper and "UNRESOLVED" in upper:
        return "ownership_gap"
    if "DIRECTIVE 1" in upper:
        return "sectoral"
    if "NO APPLICABLE" in upper or "NO SANCTIONS" in upper:
        return "none"
    raise ValueError(text)


def action_category(identity: str, status: str) -> str:
    if identity == "false":
        return "false_close"
    if status == "none":
        return "temporal_close"
    if status == "straddle":
        return "date_hold"
    if status == "ownership_gap":
        return "ownership_hold"
    return "scope_hold"


def aml_category(text: str) -> str:
    return "inconclusive" if "INCONCLUSIVE" in text.upper() else "escalate"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("golden", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    gold = json.loads(args.golden.read_text(encoding="utf-8"))
    sanctions = {}
    for row in gold["sanctions_reviews"]:
        identity = identity_category(row["identity_assessment"])
        status = status_category(row["transaction_time_status"])
        sanctions[row["transaction_id"]] = {
            "identity": identity,
            "status": status,
            "action": action_category(identity, status),
            "evidence_count": len(row["evidence"]),
        }
    aml = {
        row["sar_id"]: {"outcome": aml_category(row["assessment"]), "evidence_count": len(row["evidence"])}
        for row in gold["aml_reviews"]
    }
    controls = {
        row["control_id"]: {
            "affected_records": row["affected_records"],
            "evidence_count": len(row["evidence"]),
        }
        for row in gold["control_assessments"]
    }
    payload = {"sanctions": sanctions, "aml": aml, "controls": controls}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
