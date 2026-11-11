#!/usr/bin/env python3
"""Surface classification notes and adjacent accounting language in adjustment PDFs."""

from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from pathlib import Path


SIGNALS = {
    "note": re.compile(r"adjusters?' note|we (?:are|have been) (?:advised|informed)", re.I),
    "timing": re.compile(r"after refloat|before refloat|following.*refloat|during.*refloat|subsequent", re.I),
    "classification": re.compile(r"particular average|general average|not allowable|remainder|sacrifice", re.I),
    "substitution": re.compile(r"saved|instead|substitut|original vessel|would have", re.I),
    "causal_basis": re.compile(r"conditional|consequence|common safety|place of refuge|detention", re.I),
    "rule": re.compile(r"rule\s+(?:[ivxlcdm]+|\d+)", re.I),
}


def extract_pages(path: Path) -> list[str]:
    with tempfile.NamedTemporaryFile(suffix=".txt") as temporary:
        subprocess.run(
            ["pdftotext", "-layout", str(path), temporary.name],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return Path(temporary.name).read_text(encoding="utf-8", errors="replace").split("\f")


def line_windows(page: str, radius: int) -> list[str]:
    lines = [line.strip() for line in page.splitlines() if line.strip()]
    windows = []
    for index, line in enumerate(lines):
        if any(pattern.search(line) for pattern in SIGNALS.values()):
            windows.append(" ".join(lines[max(0, index - radius) : index + radius + 1]))
    return list(dict.fromkeys(windows))


def candidates(path: Path, radius: int, excerpt: int) -> list[tuple[int, int, str, list[str]]]:
    result = []
    for page_number, page in enumerate(extract_pages(path), start=1):
        for block in line_windows(page, radius):
            flags = [label for label, pattern in SIGNALS.items() if pattern.search(block)]
            rank = 2 * len(flags)
            if "classification" in flags and "timing" in flags:
                rank += 5
            if "classification" in flags and "substitution" in flags:
                rank += 5
            if "causal_basis" in flags and "rule" in flags:
                rank += 4
            if "note" in flags:
                rank += 2
            clipped = block if len(block) <= excerpt else block[: excerpt - 3].rstrip() + "..."
            result.append((rank, page_number, clipped, flags))
    return result


def render(paths: list[Path], limit: int, per_page: int, radius: int, excerpt: int) -> str:
    output = [
        "# Adjustment-classification scan",
        "",
        "For every candidate, inspect the facing allocation columns and record the event time,",
        "safety state, expenditure object, gross amount, remainder, admitted amount, and basis.",
    ]
    for path in paths:
        rows = candidates(path, radius, excerpt)
        rows.sort(key=lambda row: (-row[0], row[1]))
        page_counts: dict[int, int] = {}
        chosen = []
        for row in rows:
            page = row[1]
            if page_counts.get(page, 0) >= per_page:
                continue
            chosen.append(row)
            page_counts[page] = page_counts.get(page, 0) + 1
            if len(chosen) >= limit:
                break
        chosen.sort(key=lambda row: row[1])
        output.extend(["", f"## {path.name}", ""])
        for _, page, block, flags in chosen:
            output.append(f"- PDF page {page} [{', '.join(sorted(flags))}]: {block}")
        if not chosen:
            output.append("No classification language detected.")
    return "\n".join(output) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-per-document", type=int, default=24)
    parser.add_argument("--max-per-page", type=int, default=2)
    parser.add_argument("--line-radius", type=int, default=4)
    parser.add_argument("--excerpt-chars", type=int, default=800)
    args = parser.parse_args()
    report = render(
        args.pdf, args.max_per_document, args.max_per_page, args.line_radius, args.excerpt_chars
    )
    if args.output:
        args.output.write_text(report, encoding="utf-8")
        print(args.output)
    else:
        print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
