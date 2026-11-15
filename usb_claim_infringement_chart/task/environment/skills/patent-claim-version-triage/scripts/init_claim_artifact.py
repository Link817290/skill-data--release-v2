#!/usr/bin/env python3
"""Initialize an answer-blind claim-triage artifact from a visible contract."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


ARRAY_KEYS = {
    "findings",
    "decisive_feature_refs",
    "source_ids",
    "feature_findings",
    "granted_required_feature_refs",
    "source_published_claim_ids",
    "affected_feature_refs",
    "evidence_locators",
    "affected_claim_refs",
    "claim_locators",
    "candidate_issued_claim_ids",
    "issued_expanded_feature_refs",
}


def blank_record(keys: list[str], identifiers: dict[str, object]) -> dict[str, object]:
    record = {key: ([] if key in ARRAY_KEYS else None) for key in keys}
    record.update(identifiers)
    return record


def require_keys(contract: dict[str, object], schema_name: str) -> list[str]:
    schema = contract.get(schema_name)
    if not isinstance(schema, dict) or not isinstance(schema.get("row_keys"), list):
        raise SystemExit(f"contract has no usable {schema_name}.row_keys")
    return schema["row_keys"]


def scaffold(contract: dict[str, object]) -> dict[str, object]:
    published_row_keys = require_keys(contract, "published_comparison_schema")
    published_finding_keys = contract["published_comparison_schema"].get("finding_keys")
    if not isinstance(published_finding_keys, list):
        raise SystemExit("contract has no usable published_comparison_schema.finding_keys")

    element_ids = contract.get("published_element_ids")
    if not isinstance(element_ids, dict):
        raise SystemExit("contract has no published_element_ids object")

    comparisons = []
    for pair in contract.get("published_review_pairs", []):
        claim_id = str(pair["claim_id"])
        row = blank_record(published_row_keys, {
            "target_id": pair["target_id"],
            "claim_id": claim_id,
        })
        row["findings"] = [
            blank_record(published_finding_keys, {"element_id": element_id})
            for element_id in element_ids.get(claim_id, [])
        ]
        comparisons.append(row)

    same_number_keys = require_keys(contract, "same_number_claim_schema")
    issued_row_keys = require_keys(contract, "issued_comparison_schema")
    bridge_keys = require_keys(contract, "evidence_bridge_schema")
    construction_keys = require_keys(contract, "construction_dependency_schema")
    sensitivity_keys = require_keys(contract, "sensitivity_schema")
    dependency_keys = require_keys(contract, "dependency_audit_schema")
    family_keys = require_keys(contract, "family_correspondence_schema")

    return {
        "comparisons": comparisons,
        "version_impact": {
            "same_number_claims": [
                blank_record(same_number_keys, {"claim_id": str(claim_id)})
                for claim_id in contract.get("same_number_claim_ids", [])
            ],
            "granted_comparisons": [
                blank_record(issued_row_keys, {
                    "target_id": pair["target_id"],
                    "claim_id": str(pair["claim_id"]),
                })
                for pair in contract.get("issued_review_pairs", [])
            ],
        },
        "evidence_bridges": [
            blank_record(bridge_keys, {"bridge_id": issue["bridge_id"]})
            for issue in contract.get("evidence_bridge_issues", [])
        ],
        "construction_dependencies": [
            blank_record(construction_keys, {"issue_id": issue["issue_id"]})
            for issue in contract.get("construction_issues", [])
        ],
        "sensitivity_matrix": [
            blank_record(sensitivity_keys, {"scenario_id": scenario["scenario_id"]})
            for scenario in contract.get("sensitivity_scenarios", [])
        ],
        "dependency_audit": [
            blank_record(dependency_keys, {"claim_ref": claim_ref})
            for claim_ref in contract.get("dependency_audit_claim_refs", [])
        ],
        "family_correspondence": [
            blank_record(family_keys, {"published_claim_id": str(claim_id)})
            for claim_id in contract.get("family_correspondence_published_claim_ids", [])
        ],
        "assumptions_and_scope": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("contract", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.output.exists() and not args.force:
        raise SystemExit(f"refusing to overwrite existing artifact: {args.output}")
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    declared_top_level = contract.get("top_level_schema")
    if not isinstance(declared_top_level, dict) or not declared_top_level:
        raise SystemExit("contract has no non-empty top_level_schema object")
    artifact = scaffold(contract)
    if set(artifact) != set(declared_top_level):
        raise SystemExit("initializer and top_level_schema keys do not match")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    json.loads(args.output.read_text(encoding="utf-8"))
    print(
        f"initialized {args.output} with {len(artifact)} collections, "
        f"{len(artifact['comparisons'])} published rows, and "
        f"{len(artifact['version_impact']['granted_comparisons'])} issued rows"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
