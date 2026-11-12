#!/usr/bin/env python3
"""Create a value-free review-ledger skeleton from nonempty PDF widgets."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import fitz


OFF_VALUES = {"", "off", "/off", "false", "none", "null", "0"}


def is_filled(widget: fitz.Widget) -> bool:
    value = widget.field_value
    if value is None or value is False:
        return False
    return str(value).strip().lower() not in OFF_VALUES


def union_rect(rectangles: list[fitz.Rect]) -> list[float]:
    merged = fitz.Rect(rectangles[0])
    for rectangle in rectangles[1:]:
        merged.include_rect(rectangle)
    return [round(float(value), 3) for value in merged]


def source_entries(path: Path, record: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    with fitz.open(path) as document:
        for page_number, page in enumerate(document, 1):
            grouped: dict[str, list[fitz.Rect]] = {}
            for widget in page.widgets() or []:
                if not is_filled(widget):
                    continue
                name = str(widget.field_name or "").strip() or "<unnamed>"
                grouped.setdefault(name, []).append(fitz.Rect(widget.rect))
            for name, rectangles in grouped.items():
                entries.append(
                    {
                        "record": record,
                        "source_page": page_number,
                        "logical_page": f"PAGE-{page_number}",
                        "rect": union_rect(rectangles),
                        "field_refs": [f"{page_number}:{name}"],
                        "decision": "unreviewed",
                        "action": "UNREVIEWED",
                        "outcome": "UNREVIEWED",
                        "publish": False,
                    }
                )
    return entries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", nargs="+", help="PDF basename(s) under --sources-dir")
    parser.add_argument("--sources-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    sources: list[dict[str, str]] = []
    entries: list[dict[str, Any]] = []
    seen_records: set[str] = set()
    for pdf_name in args.pdf:
        candidate = Path(pdf_name)
        if candidate.is_absolute() or candidate.name != pdf_name:
            parser.error("each PDF must be a basename under --sources-dir")
        path = args.sources_dir / candidate
        if not path.is_file():
            parser.error(f"PDF not found: {candidate}")
        record = candidate.stem
        if record in seen_records:
            parser.error(f"duplicate record stem: {record}")
        seen_records.add(record)
        sources.append({"record": record, "pdf": candidate.name})
        entries.extend(source_entries(path, record))

    result = {"sources": sources, "entries": entries}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(f"bootstrapped {len(entries)} unreviewed widget response(s) from {len(sources)} PDF(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
