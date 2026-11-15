#!/usr/bin/env python3
"""Answer-blind structural linter for JSON comparison matrices."""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("document", type=Path)
    parser.add_argument("--collection", required=True, help="Dotted path to the matrix")
    parser.add_argument(
        "--axis",
        action="append",
        required=True,
        metavar="FIELD=A,B,C",
        help="Expected axis field and comma-separated values; repeat for each axis",
    )
    parser.add_argument(
        "--required",
        default="",
        help="Comma-separated non-empty fields required on every matrix row",
    )
    parser.add_argument(
        "--nested",
        metavar="FIELD:KEY",
        help="Optional nested collection and identifier field to check for duplicates",
    )
    return parser.parse_args()


def dotted_get(document: object, path: str) -> object:
    value = document
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            raise KeyError(path)
        value = value[part]
    return value


def matrix_rows(raw: object, axis_names: list[str]) -> list[dict]:
    if isinstance(raw, list):
        return [row for row in raw if isinstance(row, dict)]
    if not isinstance(raw, dict):
        return []
    rows = []
    for key, value in raw.items():
        if not isinstance(value, dict):
            continue
        row = dict(value)
        parts = str(key).replace("/", "::").split("::")
        if len(parts) == len(axis_names):
            for name, part in zip(axis_names, parts):
                row.setdefault(name, part)
        rows.append(row)
    return rows


def is_nonempty(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return bool(value)
    return True


def main() -> int:
    args = parse_args()
    try:
        document = json.loads(args.document.read_text(encoding="utf-8"))
        raw = dotted_get(document, args.collection)
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2

    axes: list[tuple[str, list[str]]] = []
    for spec in args.axis:
        if "=" not in spec:
            print(json.dumps({"ok": False, "error": f"invalid axis: {spec}"}, indent=2))
            return 2
        name, raw_values = spec.split("=", 1)
        values = [value.strip() for value in raw_values.split(",") if value.strip()]
        if not name.strip() or not values:
            print(json.dumps({"ok": False, "error": f"empty axis: {spec}"}, indent=2))
            return 2
        axes.append((name.strip(), values))

    axis_names = [name for name, _ in axes]
    expected = set(itertools.product(*(values for _, values in axes)))
    rows = matrix_rows(raw, axis_names)
    observed: dict[tuple[str, ...], int] = {}
    incomplete_keys = []
    missing_fields = []
    nested_duplicates = []
    required = [field.strip() for field in args.required.split(",") if field.strip()]

    nested_field = nested_key = None
    if args.nested:
        if ":" not in args.nested:
            print(json.dumps({"ok": False, "error": "--nested requires FIELD:KEY"}, indent=2))
            return 2
        nested_field, nested_key = args.nested.split(":", 1)

    for position, row in enumerate(rows):
        key = tuple(str(row.get(name, "")).strip() for name in axis_names)
        if any(not value for value in key):
            incomplete_keys.append(position)
        else:
            observed[key] = observed.get(key, 0) + 1
        for field in required:
            if not is_nonempty(row.get(field)):
                missing_fields.append({"row": position, "field": field})
        if nested_field and nested_key:
            nested = row.get(nested_field, [])
            nested_rows = nested.values() if isinstance(nested, dict) else nested
            if isinstance(nested_rows, (list, tuple, dict_values_type())):
                identifiers = [
                    str(item.get(nested_key, "")).strip()
                    for item in nested_rows
                    if isinstance(item, dict) and str(item.get(nested_key, "")).strip()
                ]
                duplicates = sorted({item for item in identifiers if identifiers.count(item) > 1})
                if duplicates:
                    nested_duplicates.append({"row": position, "ids": duplicates})

    duplicates = [list(key) for key, count in observed.items() if count > 1]
    missing = [list(key) for key in sorted(expected - set(observed))]
    unexpected = [list(key) for key in sorted(set(observed) - expected)]
    report = {
        "ok": not any((incomplete_keys, missing_fields, nested_duplicates, duplicates, missing, unexpected)),
        "row_count": len(rows),
        "expected_unique_rows": len(expected),
        "missing_keys": missing,
        "unexpected_keys": unexpected,
        "duplicate_keys": duplicates,
        "incomplete_key_rows": incomplete_keys,
        "missing_required_fields": missing_fields,
        "nested_duplicate_ids": nested_duplicates,
    }
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


def dict_values_type() -> type:
    return type({}.values())


if __name__ == "__main__":
    raise SystemExit(main())
