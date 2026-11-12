#!/usr/bin/env python3
"""Index non-empty paragraphs in an identified bibliography interval."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("index", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)
    args = parser.parse_args()
    source = json.loads(args.index.read_text(encoding="utf-8"))
    entries = []
    for paragraph in source.get("paragraphs", []):
        number = int(paragraph["index"])
        text = paragraph.get("text", "").strip()
        if args.start < number < args.end and text:
            entries.append({"reference_number": len(entries) + 1, "paragraph_index": number, "reference_text": text})
    result = {"file": source.get("file"), "start": args.start, "end": args.end, "entries": entries}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
