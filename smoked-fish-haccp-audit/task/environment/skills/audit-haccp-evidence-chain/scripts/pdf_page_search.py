#!/usr/bin/env python3
"""Locate concepts in text-bearing PDFs without loading the whole file into context."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Return PDF page numbers and bounded snippets for supplied queries."
    )
    parser.add_argument("--pdf", required=True, type=Path, help="Text-bearing PDF to inspect")
    parser.add_argument(
        "--query",
        action="append",
        default=[],
        help="Concept terms that must all occur on a page; repeat for alternatives",
    )
    parser.add_argument(
        "--extract-page",
        action="append",
        type=int,
        default=[],
        help="PDF page number to return in full; repeat for additional pages",
    )
    parser.add_argument("--max-hits", type=int, default=8, help="Maximum hits per query")
    parser.add_argument("--context-lines", type=int, default=2, help="Lines around a match")
    return parser.parse_args()


def pdf_pages(path: Path) -> list[str]:
    completed = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout.split("\f")


def normalized_terms(query: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", query.casefold())


def compact_lines(page: str, terms: list[str], context: int) -> str:
    lines = page.splitlines()
    if not lines:
        return ""
    lowered = [line.casefold() for line in lines]
    hit_indexes = [
        index for index, line in enumerate(lowered) if any(term in line for term in terms)
    ]
    if not hit_indexes:
        return " ".join(page.split())[:700]
    selected: set[int] = set()
    for index in hit_indexes:
        selected.update(range(max(0, index - context), min(len(lines), index + context + 1)))
    snippet = "\n".join(lines[index].rstrip() for index in sorted(selected))
    return snippet[:1400]


def main() -> int:
    args = parse_args()
    if not args.pdf.is_file():
        print(json.dumps({"error": f"PDF not found: {args.pdf}"}))
        return 2
    if not args.query and not args.extract_page:
        print(json.dumps({"error": "supply --query or --extract-page"}))
        return 2
    if args.max_hits < 1 or args.context_lines < 0:
        print(json.dumps({"error": "numeric options are outside their valid range"}))
        return 2

    try:
        pages = pdf_pages(args.pdf)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"error": f"text extraction failed: {exc}"}))
        return 2

    result: dict[str, object] = {"pdf": str(args.pdf), "page_count": len(pages)}
    query_results = []
    for query in args.query:
        terms = normalized_terms(query)
        matches = []
        if terms:
            for page_number, page in enumerate(pages, start=1):
                folded = page.casefold()
                if all(term in folded for term in terms):
                    matches.append(
                        {
                            "pdf_page": page_number,
                            "snippet": compact_lines(page, terms, args.context_lines),
                        }
                    )
                    if len(matches) >= args.max_hits:
                        break
        query_results.append({"query": query, "hits": matches})
    result["queries"] = query_results

    extracted = []
    for page_number in dict.fromkeys(args.extract_page):
        if 1 <= page_number <= len(pages):
            extracted.append({"pdf_page": page_number, "text": pages[page_number - 1].strip()})
        else:
            extracted.append({"pdf_page": page_number, "error": "page outside document"})
    result["extracted_pages"] = extracted

    json.dump(result, sys.stdout, indent=2, ensure_ascii=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
