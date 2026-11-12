#!/usr/bin/env python3
"""Validate report structure without judging citation membership."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate(report: dict, materials: Path) -> list[str]:
    errors: list[str] = []
    required = {"report_version", "manuscripts", "summary"}
    errors.extend(f"missing top-level key: {key}" for key in sorted(required - set(report)))
    files = sorted(path.name for path in materials.glob("*.docx"))
    manuscripts = report.get("manuscripts")
    if not isinstance(manuscripts, list) or not manuscripts:
        return errors + ["manuscripts must be a non-empty array"]
    seen = []
    total_refs = 0
    total_citations = 0
    for item in manuscripts:
        if not isinstance(item, dict):
            errors.append("manuscript item must be an object")
            continue
        seen.append(item.get("file"))
        for key in ("file", "bibliography_count", "cited_labels", "unmatched_references", "unmatched_citations"):
            if key not in item:
                errors.append(f"{item.get('file')}: missing {key}")
        count = item.get("bibliography_count")
        if not isinstance(count, int) or count < 0:
            errors.append(f"{item.get('file')}: bibliography_count must be a non-negative integer")
            count = 0
        for record in item.get("unmatched_references", []):
            if not isinstance(record, dict) or not isinstance(record.get("reference_number"), int):
                errors.append(f"{item.get('file')}: malformed unmatched reference")
            elif not 1 <= record["reference_number"] <= count:
                errors.append(f"{item.get('file')}: reference number outside local range")
            review = record.get("review") if isinstance(record, dict) else None
            if not isinstance(review, dict) or not all(isinstance(review.get(key), str) and review.get(key) for key in ("status", "action", "basis")) or not isinstance(review.get("compare_files"), list) or not all(isinstance(value, str) for value in review.get("compare_files", [])):
                errors.append(f"{item.get('file')}: malformed review for unmatched reference")
        for record in item.get("unmatched_citations", []):
            if not isinstance(record, dict) or not isinstance(record.get("citation_label"), int):
                errors.append(f"{item.get('file')}: malformed unmatched citation")
            review = record.get("review") if isinstance(record, dict) else None
            if not isinstance(review, dict) or not all(isinstance(review.get(key), str) and review.get(key) for key in ("status", "action", "basis")) or not isinstance(review.get("compare_files"), list) or not all(isinstance(value, str) for value in review.get("compare_files", [])):
                errors.append(f"{item.get('file')}: malformed review for unmatched citation")
        total_refs += len(item.get("unmatched_references", []))
        total_citations += len(item.get("unmatched_citations", []))
    if sorted(seen) != files:
        errors.append(f"manuscript files differ from materials: {sorted(seen)} != {files}")
    summary = report.get("summary", {})
    if summary.get("manuscript_count") != len(manuscripts):
        errors.append("summary manuscript_count does not match")
    if summary.get("unmatched_reference_count") != total_refs:
        errors.append("summary unmatched_reference_count does not match")
    if summary.get("unmatched_citation_count") != total_citations:
        errors.append("summary unmatched_citation_count does not match")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("materials", type=Path)
    args = parser.parse_args()
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"invalid report: {exc}")
        return 2
    errors = validate(report, args.materials)
    if errors:
        print("\n".join(errors))
        return 1
    print("report shape valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
