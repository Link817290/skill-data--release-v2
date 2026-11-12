#!/usr/bin/env python3
"""Validate a value-free PDF decision ledger and emit canonical audit rows."""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import fitz


OFF_VALUES = {"", "off", "/off", "false", "none", "null", "0"}
RETAIN_ACTIONS = {"RETAIN", "RETAIN-PRO", "RETAIN-ADMIN"}
VALID_DECISIONS = {"alias", "remove", "retain"}


def is_filled(widget: fitz.Widget) -> bool:
    value = widget.field_value
    if value is None or value is False:
        return False
    return str(value).strip().lower() not in OFF_VALUES


def clean_rect(value: Any, label: str, errors: list[str]) -> list[float] | None:
    if not isinstance(value, list) or len(value) != 4:
        errors.append(f"{label}: rect must contain four numbers")
        return None
    try:
        rect = [float(item) for item in value]
    except (TypeError, ValueError):
        errors.append(f"{label}: rect must contain only numbers")
        return None
    if not all(math.isfinite(item) for item in rect):
        errors.append(f"{label}: rect contains a non-finite number")
        return None
    if rect[2] <= rect[0] or rect[3] <= rect[1]:
        errors.append(f"{label}: rect has no positive area")
        return None
    return [round(item, 3) for item in rect]


def expected_outcome(action: str, decision: str) -> str:
    if action == "ALIAS" or decision == "alias":
        return "REPLACED"
    if action in RETAIN_ACTIONS or decision == "retain":
        return "RETAINED"
    return "REMOVED"


def load_source_widgets(path: Path) -> set[str]:
    filled: set[str] = set()
    with fitz.open(path) as document:
        for page_index, page in enumerate(document):
            for widget in page.widgets() or []:
                if not is_filled(widget):
                    continue
                name = str(widget.field_name or "").strip()
                if not name:
                    name = "<unnamed>"
                filled.add(f"{page_index + 1}:{name}")
    return filled


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("--sources-dir", type=Path, required=True)
    parser.add_argument("--compiled", type=Path)
    args = parser.parse_args()

    try:
        data = json.loads(args.ledger.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ledger read failed: {exc}", file=sys.stderr)
        return 2

    sources = data.get("sources")
    entries = data.get("entries")
    if not isinstance(sources, list) or not isinstance(entries, list):
        print("ledger must contain list-valued sources and entries", file=sys.stderr)
        return 2

    errors: list[str] = []
    source_files: dict[str, Path] = {}
    for index, source in enumerate(sources, 1):
        if not isinstance(source, dict):
            errors.append(f"source {index}: expected an object")
            continue
        record = str(source.get("record", "")).strip()
        pdf_name = str(source.get("pdf", "")).strip()
        if not record or not pdf_name:
            errors.append(f"source {index}: record and pdf are required")
            continue
        if record in source_files:
            errors.append(f"source {index}: duplicate record {record!r}")
            continue
        candidate = Path(pdf_name)
        if candidate.is_absolute() or candidate.name != pdf_name:
            errors.append(f"source {index}: pdf must be a basename under --sources-dir")
            continue
        path = args.sources_dir / candidate
        if not path.is_file():
            errors.append(f"source {index}: PDF not found: {candidate}")
            continue
        source_files[record] = path

    normalized: list[dict[str, Any]] = []
    refs_by_record: dict[str, dict[str, int]] = defaultdict(dict)
    geometry_seen: set[tuple[Any, ...]] = set()
    for index, entry in enumerate(entries, 1):
        label = f"entry {index}"
        if not isinstance(entry, dict):
            errors.append(f"{label}: expected an object")
            continue
        record = str(entry.get("record", "")).strip()
        logical_page = str(entry.get("logical_page", "")).strip()
        action = str(entry.get("action", "")).strip().upper()
        decision = str(entry.get("decision", "")).strip().lower()
        outcome = str(entry.get("outcome", "")).strip().upper()
        publish = entry.get("publish")
        try:
            source_page = int(entry.get("source_page"))
        except (TypeError, ValueError):
            source_page = 0
        rect = clean_rect(entry.get("rect"), label, errors)
        refs = entry.get("field_refs", [])
        if record not in source_files:
            errors.append(f"{label}: unknown record {record!r}")
        if source_page < 1:
            errors.append(f"{label}: source_page must be one-based")
        if not logical_page:
            errors.append(f"{label}: logical_page is required")
        if not action or not decision:
            errors.append(f"{label}: action and decision are required")
        decision_valid = decision in VALID_DECISIONS
        if not decision_valid:
            errors.append(
                f"{label}: decision {decision!r} must be alias, remove, or retain"
            )
        if decision_valid:
            if decision == "alias" and action != "ALIAS":
                errors.append(f"{label}: alias decisions must use action 'ALIAS'")
            if decision == "retain" and action not in RETAIN_ACTIONS:
                errors.append(f"{label}: retain decisions must use a retain action")
            if decision == "remove" and (action == "ALIAS" or action in RETAIN_ACTIONS):
                errors.append(f"{label}: remove decisions must use a removal reason action")
            expected = expected_outcome(action, decision)
            if outcome != expected:
                errors.append(f"{label}: outcome {outcome!r} must be {expected!r}")
        if not isinstance(publish, bool):
            errors.append(f"{label}: publish must be true or false")
        elif decision_valid and decision in {"alias", "remove"} and not publish:
            errors.append(f"{label}: changed responses must use publish true")
        elif decision_valid and decision == "retain" and publish:
            errors.append(f"{label}: retained responses must use publish false")
        if not isinstance(refs, list) or any(not isinstance(ref, str) or not ref.strip() for ref in refs):
            errors.append(f"{label}: field_refs must be a list of nonempty strings")
            refs = []
        if rect is None:
            continue
        geometry_key = (record, source_page, *rect)
        if geometry_key in geometry_seen:
            errors.append(f"{label}: duplicate semantic-field geometry")
        geometry_seen.add(geometry_key)
        canonical_refs: list[str] = []
        for ref in refs:
            ref = ref.strip()
            qualified = ref if ":" in ref else f"{source_page}:{ref}"
            previous = refs_by_record[record].get(qualified)
            if previous is not None:
                errors.append(f"{label}: widget {qualified!r} already used by entry {previous}")
            else:
                refs_by_record[record][qualified] = index
            canonical_refs.append(qualified)
        normalized.append(
            {
                "record": record,
                "source_page": source_page,
                "logical_page": logical_page,
                "rect": rect,
                "field_refs": canonical_refs,
                "decision": decision,
                "action": action,
                "outcome": outcome,
                "publish": bool(publish),
            }
        )

    coverage: dict[str, dict[str, Any]] = {}
    for record, path in source_files.items():
        filled = load_source_widgets(path)
        covered = set(refs_by_record.get(record, {}))
        missing = sorted(filled - covered)
        unknown = sorted(covered - filled)
        coverage[record] = {
            "filled_widget_count": len(filled),
            "covered_widget_count": len(filled & covered),
            "unaccounted_widget_refs": missing,
            "unknown_or_unfilled_widget_refs": unknown,
        }
        if missing:
            errors.append(f"{record}: {len(missing)} nonempty widget(s) are unaccounted: {', '.join(missing)}")
        if unknown:
            errors.append(f"{record}: {len(unknown)} referenced widget(s) are not nonempty: {', '.join(unknown)}")

    record_order = {record: index for index, record in enumerate(source_files)}
    published = [entry for entry in normalized if entry["publish"]]
    published.sort(
        key=lambda entry: (
            record_order.get(entry["record"], len(record_order)),
            entry["source_page"],
            entry["rect"][1],
            entry["rect"][0],
        )
    )
    sequence: Counter[str] = Counter()
    register_rows: list[dict[str, Any]] = []
    for entry in published:
        sequence[entry["record"]] += 1
        register_rows.append(
            {
                "record": entry["record"],
                "logical_page": entry["logical_page"],
                "row": f"{sequence[entry['record']]:02d}",
                "action": entry["action"],
                "outcome": entry["outcome"],
                "sort_rect": entry["rect"],
            }
        )

    counts = Counter(row["action"] for row in register_rows)
    per_record: dict[str, Counter[str]] = defaultdict(Counter)
    for row in register_rows:
        per_record[row["record"]][row["action"]] += 1
    compiled = {
        "valid": not errors,
        "errors": errors,
        "coverage": coverage,
        "reviewed_field_count": len(normalized),
        "published_field_count": len(register_rows),
        "counts": dict(sorted(counts.items())),
        "counts_by_record": {
            record: dict(sorted(per_record[record].items())) for record in source_files
        },
        "register_rows": register_rows,
    }

    rendered = json.dumps(compiled, indent=2, ensure_ascii=True) + "\n"
    if args.compiled:
        args.compiled.parent.mkdir(parents=True, exist_ok=True)
        args.compiled.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(
        f"ledger valid: {len(normalized)} reviewed fields, {len(register_rows)} published actions",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
