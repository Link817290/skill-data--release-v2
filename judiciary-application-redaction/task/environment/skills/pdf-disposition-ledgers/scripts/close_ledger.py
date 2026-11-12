#!/usr/bin/env python3
"""Apply explicit exceptions and a residual removal rule to a PDF ledger."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any


RETAIN_ACTIONS = {"RETAIN", "RETAIN-PRO", "RETAIN-ADMIN"}
VALID_DECISIONS = {"alias", "remove", "retain"}


def fail(message: str) -> None:
    raise ValueError(message)


def read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"{label} read failed: {exc}")
    if not isinstance(value, dict):
        fail(f"{label} must contain a JSON object")
    return value


def rect(value: Any, label: str) -> list[float]:
    if not isinstance(value, list) or len(value) != 4:
        fail(f"{label}: rect must contain four numbers")
    try:
        result = [round(float(item), 3) for item in value]
    except (TypeError, ValueError):
        fail(f"{label}: rect must contain only numbers")
    if not all(math.isfinite(item) for item in result):
        fail(f"{label}: rect contains a non-finite number")
    if result[2] <= result[0] or result[3] <= result[1]:
        fail(f"{label}: rect has no positive area")
    return result


def union_rect(rectangles: list[list[float]]) -> list[float]:
    return [
        min(item[0] for item in rectangles),
        min(item[1] for item in rectangles),
        max(item[2] for item in rectangles),
        max(item[3] for item in rectangles),
    ]


def disposition(decision: Any, action: Any, label: str) -> tuple[str, str, str, bool]:
    decision_text = str(decision or "").strip().lower()
    action_text = str(action or "").strip().upper()
    if decision_text not in VALID_DECISIONS:
        fail(f"{label}: decision must be alias, remove, or retain")
    if decision_text == "alias" and action_text != "ALIAS":
        fail(f"{label}: alias decisions must use ALIAS")
    if decision_text == "retain" and action_text not in RETAIN_ACTIONS:
        fail(f"{label}: retain decisions must use a retain action")
    if decision_text == "remove" and (
        not action_text or action_text == "ALIAS" or action_text in RETAIN_ACTIONS
    ):
        fail(f"{label}: remove decisions need a removal action")
    outcome = {
        "alias": "REPLACED",
        "remove": "REMOVED",
        "retain": "RETAINED",
    }[decision_text]
    return decision_text, action_text, outcome, decision_text != "retain"


def record_rules(data: dict[str, Any], source_ids: list[str]) -> dict[str, dict[str, str]]:
    raw = data.get("records", {})
    if not isinstance(raw, dict):
        fail("policy records must be an object")
    unknown = sorted(set(raw) - set(source_ids))
    if unknown:
        fail(f"policy records contains unknown source id(s): {', '.join(unknown)}")
    result: dict[str, dict[str, str]] = {}
    for source_id in source_ids:
        rule = raw.get(source_id, {})
        if not isinstance(rule, dict):
            fail(f"record rule {source_id!r} must be an object")
        name = str(rule.get("name", source_id)).strip()
        prefix = str(rule.get("logical_prefix", "PAGE")).strip()
        if not name or not prefix:
            fail(f"record rule {source_id!r} needs nonempty name and logical_prefix")
        result[source_id] = {"name": name, "prefix": prefix}
    return result


def allowlist_rules(
    data: dict[str, Any], source_ids: list[str]
) -> dict[str, dict[str, Any]]:
    raw = data.get("allowlist", [])
    if not isinstance(raw, list):
        fail("policy allowlist must be a list")
    result: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(raw, 1):
        label = f"allowlist rule {index}"
        if not isinstance(item, dict):
            fail(f"{label} must be an object")
        rule_id = str(item.get("id", "")).strip()
        basis = str(item.get("basis", "")).strip()
        records = item.get("records")
        if not rule_id or rule_id in result:
            fail(f"{label} needs a unique nonempty id")
        if not isinstance(records, list) or not records:
            fail(f"{label} needs a nonempty records list")
        record_set = {str(value).strip() for value in records}
        if "" in record_set:
            fail(f"{label} contains an empty record id")
        unknown = sorted(record_set - set(source_ids))
        if unknown:
            fail(f"{label} contains unknown record id(s): {', '.join(unknown)}")
        if len(basis) < 12:
            fail(f"{label} needs a concrete assignment-derived basis")
        result[rule_id] = {
            "id": rule_id,
            "records": sorted(record_set, key=source_ids.index),
            "basis": basis,
        }
    return result


def checked_allowlist_rule(
    item: dict[str, Any],
    source_id: str,
    decision: str,
    rules: dict[str, dict[str, Any]],
    label: str,
) -> str | None:
    rule_id = str(item.get("allowlist_rule", "")).strip()
    if decision != "retain":
        if rule_id:
            fail(f"{label}: only retain decisions may cite allowlist_rule")
        return None
    if not rule_id:
        fail(f"{label}: retain decision must cite allowlist_rule")
    rule = rules.get(rule_id)
    if rule is None:
        fail(f"{label}: unknown allowlist_rule {rule_id!r}")
    if source_id not in rule["records"]:
        fail(f"{label}: allowlist_rule {rule_id!r} does not cover record {source_id!r}")
    return rule_id


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--default-removal", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        ledger = read_object(args.ledger, "ledger")
        policy = read_object(args.policy, "policy")
        sources = ledger.get("sources")
        entries = ledger.get("entries")
        if not isinstance(sources, list) or not isinstance(entries, list):
            fail("ledger must contain list-valued sources and entries")

        source_ids: list[str] = []
        source_pdfs: dict[str, str] = {}
        for index, source in enumerate(sources, 1):
            if not isinstance(source, dict):
                fail(f"source {index} must be an object")
            source_id = str(source.get("record", "")).strip()
            pdf = str(source.get("pdf", "")).strip()
            if not source_id or not pdf or source_id in source_pdfs:
                fail(f"source {index} has a missing or duplicate record/pdf")
            source_ids.append(source_id)
            source_pdfs[source_id] = pdf

        rules = record_rules(policy, source_ids)
        allowlist = allowlist_rules(policy, source_ids)
        indexed: dict[tuple[str, str], tuple[int, dict[str, Any]]] = {}
        normalized_entries: list[dict[str, Any]] = []
        for index, raw_entry in enumerate(entries):
            if not isinstance(raw_entry, dict):
                fail(f"ledger entry {index + 1} must be an object")
            entry = dict(raw_entry)
            source_id = str(entry.get("record", "")).strip()
            if source_id not in source_pdfs:
                fail(f"ledger entry {index + 1} has unknown record {source_id!r}")
            try:
                page = int(entry.get("source_page"))
            except (TypeError, ValueError):
                fail(f"ledger entry {index + 1} has invalid source_page")
            refs = entry.get("field_refs")
            if not isinstance(refs, list) or not refs:
                fail(f"ledger entry {index + 1} needs field_refs")
            entry["rect"] = rect(entry.get("rect"), f"ledger entry {index + 1}")
            entry["logical_page"] = f"{rules[source_id]['prefix']}-{page}"
            for raw_ref in refs:
                ref = str(raw_ref).strip()
                if not ref:
                    fail(f"ledger entry {index + 1} contains an empty field ref")
                ref = ref if ":" in ref else f"{page}:{ref}"
                key = (source_id, ref)
                if key in indexed:
                    fail(f"widget reference {source_id}/{ref} appears more than once")
                indexed[key] = (index, entry)
            normalized_entries.append(entry)

        explicit = policy.get("decisions", [])
        if not isinstance(explicit, list):
            fail("policy decisions must be a list")
        consumed: set[tuple[str, str]] = set()
        replacements: dict[int, dict[str, Any]] = {}
        suppressed: set[int] = set()
        for index, item in enumerate(explicit, 1):
            label = f"policy decision {index}"
            if not isinstance(item, dict):
                fail(f"{label} must be an object")
            source_id = str(item.get("record", "")).strip()
            if source_id not in source_pdfs:
                fail(f"{label}: unknown record {source_id!r}")
            refs = item.get("field_refs")
            if not isinstance(refs, list) or not refs:
                fail(f"{label}: field_refs must be a nonempty list")
            selected: list[tuple[int, dict[str, Any]]] = []
            canonical_refs: list[str] = []
            for raw_ref in refs:
                ref = str(raw_ref).strip()
                key = (source_id, ref)
                if key in consumed:
                    fail(f"{label}: widget {source_id}/{ref} is assigned twice")
                if key not in indexed:
                    fail(f"{label}: widget {source_id}/{ref} is not in the bootstrap ledger")
                consumed.add(key)
                selected.append(indexed[key])
                canonical_refs.append(ref)
            pages = {int(entry["source_page"]) for _, entry in selected}
            if len(pages) != 1:
                fail(f"{label}: one semantic response cannot span source pages")
            decision, action, outcome, publish = disposition(
                item.get("decision"), item.get("action"), label
            )
            allowlist_rule = checked_allowlist_rule(
                item, source_id, decision, allowlist, label
            )
            first = min(position for position, _ in selected)
            merged = dict(selected[0][1])
            merged.update(
                {
                    "rect": union_rect([entry["rect"] for _, entry in selected]),
                    "field_refs": canonical_refs,
                    "decision": decision,
                    "action": action,
                    "outcome": outcome,
                    "publish": publish,
                    "allowlist_rule": allowlist_rule,
                }
            )
            replacements[first] = merged
            suppressed.update(position for position, _ in selected if position != first)

        default_decision = disposition("remove", args.default_removal, "default removal")
        closed: list[dict[str, Any]] = []
        for position, entry in enumerate(normalized_entries):
            if position in suppressed:
                continue
            if position in replacements:
                chosen = replacements[position]
            else:
                chosen = dict(entry)
                decision, action, outcome, publish = default_decision
                chosen.update(
                    {
                        "decision": decision,
                        "action": action,
                        "outcome": outcome,
                        "publish": publish,
                        "allowlist_rule": None,
                    }
                )
            chosen["record"] = rules[str(entry["record"])]["name"]
            closed.append(chosen)

        regions = policy.get("regions", [])
        if not isinstance(regions, list):
            fail("policy regions must be a list")
        for index, item in enumerate(regions, 1):
            label = f"policy region {index}"
            if not isinstance(item, dict):
                fail(f"{label} must be an object")
            source_id = str(item.get("record", "")).strip()
            if source_id not in source_pdfs:
                fail(f"{label}: unknown record {source_id!r}")
            try:
                page = int(item.get("source_page"))
            except (TypeError, ValueError):
                fail(f"{label}: source_page must be one-based")
            if page < 1:
                fail(f"{label}: source_page must be one-based")
            decision, action, outcome, publish = disposition(
                item.get("decision"), item.get("action"), label
            )
            allowlist_rule = checked_allowlist_rule(
                item, source_id, decision, allowlist, label
            )
            closed.append(
                {
                    "record": rules[source_id]["name"],
                    "source_page": page,
                    "logical_page": f"{rules[source_id]['prefix']}-{page}",
                    "rect": rect(item.get("rect"), label),
                    "field_refs": [],
                    "decision": decision,
                    "action": action,
                    "outcome": outcome,
                    "publish": publish,
                    "allowlist_rule": allowlist_rule,
                }
            )

        output = {
            "sources": [
                {"record": rules[source_id]["name"], "pdf": source_pdfs[source_id]}
                for source_id in source_ids
            ],
            "allowlist": [
                {
                    **rule,
                    "records": [rules[source_id]["name"] for source_id in rule["records"]],
                }
                for rule in allowlist.values()
            ],
            "entries": closed,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(output, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
        )
    except ValueError as exc:
        print(f"close failed: {exc}", file=sys.stderr)
        return 2

    counts: dict[str, int] = {}
    retained: dict[str, int] = {}
    for entry in closed:
        if entry["decision"] == "retain":
            rule_id = str(entry["allowlist_rule"])
            retained[rule_id] = retained.get(rule_id, 0) + 1
        if not entry["publish"]:
            continue
        action = str(entry["action"])
        counts[action] = counts.get(action, 0) + 1
    rendered = ", ".join(f"{key}={counts[key]}" for key in sorted(counts))
    print(f"closed {len(closed)} response(s); published actions: {rendered or 'none'}")
    retained_rendered = ", ".join(
        f"{key}={retained[key]}" for key in sorted(retained)
    )
    print(f"retained by allowlist rule: {retained_rendered or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
