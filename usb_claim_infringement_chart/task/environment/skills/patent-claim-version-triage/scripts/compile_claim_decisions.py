#!/usr/bin/env python3
"""Compile analyst-supplied compact decisions into a visible claim-chart schema."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from init_claim_artifact import blank_record, require_keys, scaffold


def as_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def as_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def pair_key(target: object, claim: object) -> str:
    return f"{target}::{claim}"


def copy_fields(target: dict[str, object], source: dict[str, object], aliases: dict[str, str] | None = None) -> None:
    aliases = aliases or {}
    for key in list(target):
        source_key = aliases.get(key, key)
        if source_key in source:
            target[key] = source[source_key]


def keyed_rows(raw: object, id_field: str) -> dict[str, dict[str, object]]:
    if isinstance(raw, dict):
        out = {}
        for key, value in raw.items():
            if isinstance(value, dict):
                row = dict(value)
                row.setdefault(id_field, str(key))
                out[str(row[id_field])] = row
        return out
    out = {}
    for value in as_list(raw):
        if isinstance(value, dict) and value.get(id_field) is not None:
            out[str(value[id_field])] = value
    return out


def finding_value(
    decision: dict[str, object],
    feature: str,
    finding_keys: list[str],
    id_field: str,
) -> dict[str, object]:
    classes = as_dict(decision.get("classes"))
    overrides = as_dict(as_dict(decision.get("finding_overrides")).get(feature))
    status = classes.get(feature, decision.get("default_class"))
    row = blank_record(finding_keys, {id_field: feature})
    row["evidence_class"] = status
    for key in ("source_ids", "evidence_locator", "reason"):
        row[key] = overrides.get(key, decision.get(key, row.get(key)))
    if id_field == "element_id":
        for key in ("actor_direction", "medium_or_pins", "sequence_test"):
            row[key] = overrides.get(key, decision.get(key, row.get(key)))
    return row


def compile_published(artifact: dict[str, object], contract: dict[str, object], decisions: dict[str, object]) -> None:
    supplied = as_dict(decisions.get("published"))
    finding_keys = contract["published_comparison_schema"]["finding_keys"]
    for row in artifact["comparisons"]:
        decision = as_dict(supplied.get(pair_key(row["target_id"], row["claim_id"])))
        if not decision:
            continue
        row["terminal_call"] = decision.get("terminal_call", decision.get("call"))
        row["findings"] = [
            finding_value(decision, finding["element_id"], finding_keys, "element_id")
            for finding in row["findings"]
        ]


def compile_issued(artifact: dict[str, object], contract: dict[str, object], decisions: dict[str, object]) -> None:
    supplied = as_dict(decisions.get("issued"))
    finding_keys = contract["issued_comparison_schema"]["finding_keys"]
    for row in artifact["version_impact"]["granted_comparisons"]:
        decision = as_dict(supplied.get(pair_key(row["target_id"], row["claim_id"])))
        if not decision:
            continue
        copy_fields(row, decision, {"terminal_call": "call"})
        if "terminal_call" in decision:
            row["terminal_call"] = decision["terminal_call"]
        classes = as_dict(decision.get("classes"))
        features = decision.get("feature_refs", list(classes))
        row["feature_findings"] = [
            finding_value(decision, str(feature), finding_keys, "feature_ref")
            for feature in as_list(features)
        ]


def overlay_register(
    rows: list[dict[str, object]],
    raw: object,
    id_field: str,
) -> None:
    supplied = keyed_rows(raw, id_field)
    for row in rows:
        decision = supplied.get(str(row[id_field]))
        if decision:
            copy_fields(row, decision)


def compile_artifact(contract: dict[str, object], decisions: dict[str, object]) -> dict[str, object]:
    artifact = scaffold(contract)
    compile_published(artifact, contract, decisions)
    compile_issued(artifact, contract, decisions)
    overlay_register(
        artifact["version_impact"]["same_number_claims"],
        decisions.get("same_number"),
        "claim_id",
    )
    overlay_register(artifact["evidence_bridges"], decisions.get("bridges"), "bridge_id")
    overlay_register(
        artifact["construction_dependencies"], decisions.get("construction"), "issue_id"
    )
    overlay_register(artifact["sensitivity_matrix"], decisions.get("sensitivity"), "scenario_id")
    overlay_register(artifact["dependency_audit"], decisions.get("dependencies"), "claim_ref")
    overlay_register(
        artifact["family_correspondence"], decisions.get("family"), "published_claim_id"
    )
    assumptions = decisions.get("assumptions_and_scope")
    if isinstance(assumptions, list):
        artifact["assumptions_and_scope"] = assumptions
    return artifact


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("contract", type=Path)
    parser.add_argument("decisions", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    decisions = json.loads(args.decisions.read_text(encoding="utf-8"))
    if not isinstance(decisions, dict):
        raise SystemExit("the decision map root must be an object")
    artifact = compile_artifact(contract, decisions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    json.loads(args.output.read_text(encoding="utf-8"))
    print(f"compiled {args.output} from analyst-supplied decisions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
