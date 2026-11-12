#!/usr/bin/env python3
"""Scan an extracted paragraph index for numeric bracket-label occurrences."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


BRACKET_RE = re.compile(r"[\[［【]\s*([^\]］】]+?)\s*[\]］】]")
GROUP_SEPARATOR_RE = re.compile(r"[,，;；、]")
RANGE_RE = re.compile(r"^(\d+)\s*[~～至\-–—]\s*(\d+)$")


def expand_group(interior: str) -> list[int]:
    """Expand numeric groups while retaining single labels as-is."""
    labels: list[int] = []
    for token in GROUP_SEPARATOR_RE.split(interior):
        token = token.strip()
        match = RANGE_RE.fullmatch(token)
        if match:
            start, end = (int(value) for value in match.groups())
            if start <= end:
                labels.extend(range(start, end + 1))
            continue
        if token.isdigit():
            labels.append(int(token))
    return labels


def scan(index: dict, start: int, end: int) -> list[dict]:
    occurrences: list[dict] = []
    for paragraph in index.get("paragraphs", []):
        number = int(paragraph["index"])
        if number < start or number >= end:
            continue
        text = paragraph.get("text", "")
        for match in BRACKET_RE.finditer(text):
            interior = match.group(1)
            if not re.fullmatch(r"\s*\d+(?:\s*[,，;；、~～至\-–—]\s*\d+)*\s*", interior):
                continue
            labels = expand_group(interior)
            occurrences.append({"paragraph_index": number, "literal": match.group(0), "labels": labels})
    return occurrences


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("index", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)
    args = parser.parse_args()
    index = json.loads(args.index.read_text(encoding="utf-8"))
    result = {"file": index.get("file"), "start": args.start, "end": args.end, "occurrences": scan(index, args.start, args.end)}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
