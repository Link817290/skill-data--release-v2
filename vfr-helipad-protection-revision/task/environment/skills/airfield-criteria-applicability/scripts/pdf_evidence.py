#!/usr/bin/env python3
"""Find query terms in a PDF text layer while retaining physical page numbers."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


def page_count(pdf: Path) -> int:
    result = subprocess.run(
        ["pdfinfo", str(pdf)],
        check=True,
        capture_output=True,
        text=True,
    )
    match = re.search(r"^Pages:\s+(\d+)\s*$", result.stdout, re.MULTILINE)
    if not match:
        raise RuntimeError("pdfinfo did not report a page count")
    return int(match.group(1))


def page_text(pdf: Path, page: int) -> list[str]:
    result = subprocess.run(
        ["pdftotext", "-layout", "-f", str(page), "-l", str(page), str(pdf), "-"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.splitlines()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--query", action="append", required=True)
    parser.add_argument("--context", type=int, default=1)
    args = parser.parse_args()
    if not args.pdf.is_file():
        parser.error(f"PDF not found: {args.pdf}")
    if args.context < 0:
        parser.error("--context must be nonnegative")

    patterns = [re.compile(re.escape(query), re.IGNORECASE) for query in args.query]
    hits = 0
    for page in range(1, page_count(args.pdf) + 1):
        lines = page_text(args.pdf, page)
        matched = [index for index, line in enumerate(lines) if any(pattern.search(line) for pattern in patterns)]
        if not matched:
            continue
        hits += len(matched)
        print(f"=== physical page {page} ===")
        emitted: set[int] = set()
        for index in matched:
            for line_index in range(max(0, index - args.context), min(len(lines), index + args.context + 1)):
                if line_index not in emitted:
                    marker = ">" if line_index == index else " "
                    print(f"{marker}{line_index + 1:04d}: {lines[line_index]}")
                    emitted.add(line_index)
    if not hits:
        print("no matches", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
