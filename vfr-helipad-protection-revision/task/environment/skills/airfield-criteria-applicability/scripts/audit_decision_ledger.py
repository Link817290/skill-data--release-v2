#!/usr/bin/env python3
"""Check that review records close observation, criterion, disposition, and evidence."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterator


ANCHOR_KEYS = re.compile(r"(?:^|_)(?:id|topic|subject|title|name)(?:$|_)")
BASELINE_KEYS = re.compile(r"baseline|legacy|existing|observed|inspection|condition")
CRITERION_KEYS = re.compile(r"current|criterion|criteria|requirement|governing|control|basis")
DECISION_KEYS = re.compile(r"decision|disposition|status|action|conclusion")
EVIDENCE_KEYS = re.compile(r"source|evidence|citation|reference")
LOCATION_TEXT = re.compile(r"\b(?:page|section|paragraph|table|figure|note|item)\b", re.IGNORECASE)
DECISION_TEXT = re.compile(r"\b(?:retain|repair|revise|replace|exclude|hold|unresolved)\b", re.IGNORECASE)


def walk(value: Any, path: str = "$") -> Iterator[tuple[str, dict[str, Any]]]:
    if isinstance(value, dict):
        nested_keys = list(all_keys(value))
        if any(ANCHOR_KEYS.search(str(key).lower()) for key in value) and any(
            pattern.search(key) for pattern in (BASELINE_KEYS, CRITERION_KEYS, DECISION_KEYS, EVIDENCE_KEYS)
            for key in nested_keys
        ):
            yield path, value
        for key, child in value.items():
            yield from walk(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, f"{path}[{index}]")


def all_keys(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key).lower()
            yield from all_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from all_keys(child)


def values_for_keys(value: Any, pattern: re.Pattern[str]) -> Iterator[Any]:
    if isinstance(value, dict):
        for key, child in value.items():
            if pattern.search(str(key).lower()):
                yield child
            yield from values_for_keys(child, pattern)
    elif isinstance(value, list):
        for child in value:
            yield from values_for_keys(child, pattern)


def key_text(record: dict[str, Any], pattern: re.Pattern[str]) -> str:
    return json.dumps(list(values_for_keys(record, pattern)), ensure_ascii=True, sort_keys=True)


def canonical(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=True, sort_keys=True)
    return re.sub(r"\s+", " ", text.lower()).strip()


def load_topics(path: Path) -> list[str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read topic manifest: {exc}") from exc
    topics = payload.get("topics") if isinstance(payload, dict) else payload
    if not isinstance(topics, list) or not topics or not all(isinstance(topic, str) and topic.strip() for topic in topics):
        raise ValueError("topic manifest must be a nonempty JSON list of strings or an object with a topics list")
    normalized = [canonical(topic) for topic in topics]
    if len(set(normalized)) != len(normalized):
        raise ValueError("topic manifest contains duplicate topics")
    return normalized


def assign_topics(candidates: list[tuple[str, dict[str, Any]]], topics: list[str]) -> tuple[dict[str, str], list[str]]:
    assignment: dict[str, str] = {}
    used_paths: set[str] = set()
    for topic in topics:
        for path, record in candidates:
            if path in used_paths:
                continue
            anchor = canonical(list(values_for_keys(record, ANCHOR_KEYS)))
            if topic in anchor:
                assignment[topic] = path
                used_paths.add(path)
                break
    return assignment, [topic for topic in topics if topic not in assignment]


def audit(record: dict[str, Any]) -> list[str]:
    keys = " ".join(all_keys(record))
    whole = json.dumps(record, ensure_ascii=True, sort_keys=True)
    problems: list[str] = []
    if not BASELINE_KEYS.search(keys):
        problems.append("missing baseline or observed condition")
    if not CRITERION_KEYS.search(keys):
        problems.append("missing current governing criterion")
    decision = key_text(record, DECISION_KEYS)
    if decision == "[]" or not DECISION_TEXT.search(decision):
        problems.append("missing explicit retain/repair/exclude/hold disposition")
    evidence = key_text(record, EVIDENCE_KEYS)
    if evidence == "[]" or not LOCATION_TEXT.search(evidence):
        problems.append("missing resolvable section/table/figure/note/item/page evidence")
    if len(whole) < 120:
        problems.append("record is too terse to bind a review decision")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--minimum-records", type=int, default=1)
    parser.add_argument("--topic-manifest", type=Path)
    args = parser.parse_args()
    if not args.report.is_file():
        parser.error(f"report not found: {args.report}")
    if args.minimum_records < 1:
        parser.error("--minimum-records must be positive")

    try:
        document = json.loads(args.report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        parser.error(f"cannot read report JSON: {exc}")

    topics: list[str] = []
    if args.topic_manifest:
        try:
            topics = load_topics(args.topic_manifest)
        except ValueError as exc:
            parser.error(str(exc))

    candidates = list(walk(document))
    findings = [
        {"path": path, "problems": problems}
        for path, record in candidates
        if (problems := audit(record))
    ]
    assignment, missing_topics = assign_topics(candidates, topics)
    minimum_records = max(args.minimum_records, len(topics))
    result = {
        "records_checked": len(candidates),
        "minimum_records": minimum_records,
        "record_count_ok": len(candidates) >= minimum_records,
        "records_closed": not findings,
        "topic_assignment": assignment,
        "missing_topics": missing_topics,
        "topic_coverage_ok": not missing_topics,
        "findings": findings,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["record_count_ok"] and result["records_closed"] and result["topic_coverage_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
