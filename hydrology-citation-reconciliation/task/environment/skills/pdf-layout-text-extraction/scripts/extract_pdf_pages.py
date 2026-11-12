#!/usr/bin/env python3
"""Create page-scoped layout and raw text views for a text-bearing PDF."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


def run(command: list[str]) -> str:
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    return completed.stdout


def page_count(pdf: Path) -> int:
    information = run(["pdfinfo", str(pdf)])
    match = re.search(r"^Pages:\s+(\d+)\s*$", information, flags=re.MULTILINE)
    if not match:
        raise RuntimeError("pdfinfo did not report a page count")
    return int(match.group(1))


def extract_page(pdf: Path, page: int, layout: bool) -> str:
    command = ["pdftotext", "-f", str(page), "-l", str(page)]
    command.append("-layout" if layout else "-raw")
    command.extend([str(pdf), "-"])
    return run(command)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    if not args.pdf.is_file():
        parser.error(f"PDF not found: {args.pdf}")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    count = page_count(args.pdf)
    records: list[dict[str, object]] = []
    for page in range(1, count + 1):
        layout_text = extract_page(args.pdf, page, layout=True)
        raw_text = extract_page(args.pdf, page, layout=False)
        layout_name = f"page-{page:03d}.layout.txt"
        raw_name = f"page-{page:03d}.raw.txt"
        (args.output_dir / layout_name).write_text(layout_text, encoding="utf-8")
        (args.output_dir / raw_name).write_text(raw_text, encoding="utf-8")
        records.append(
            {
                "physical_page": page,
                "layout_file": layout_name,
                "raw_file": raw_name,
                "layout_characters": len(layout_text),
                "raw_characters": len(raw_text),
            }
        )

    manifest = {"source": args.pdf.name, "physical_pages": count, "pages": records}
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
