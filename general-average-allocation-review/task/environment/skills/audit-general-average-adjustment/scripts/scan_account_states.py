#!/usr/bin/env python3
"""Surface payment, security, account, and population statements in PDF records."""

from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from pathlib import Path


SIGNALS = {
    "payment": re.compile(r"\bpaid\b|\bpayment\b|contribution", re.I),
    "security": re.compile(r"secur(?:ity|ed)|average bond|guarantee|cash deposit", re.I),
    "account": re.compile(r"trust account|account-level|beneficial|refund|release|set-off", re.I),
    "population": re.compile(r"\b\d+(?:\.\d+)?\s*%|per cent|consignment|cargo interests?|container interests?|respondents?", re.I),
    "scope": re.compile(r"on behalf of|with the exception|without the necessity|not supplied|does not|rather than", re.I),
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


def page_blocks(page: str) -> list[str]:
    blocks = []
    for raw in re.split(r"\n\s*\n", page):
        value = re.sub(r"\s+", " ", raw).strip()
        if value:
            blocks.append(value)
    return blocks


def candidates(path: Path, excerpt: int) -> list[tuple[int, int, str, list[str]]]:
    result = []
    for page_number, page in enumerate(extract_pages(path), start=1):
        blocks = page_blocks(page)
        lines = [line.strip() for line in page.splitlines() if line.strip()]
        for index, line in enumerate(lines):
            if any(pattern.search(line) for pattern in SIGNALS.values()):
                blocks.append(" ".join(lines[max(0, index - 2) : index + 3]))
        for block in dict.fromkeys(blocks):
            flags = [label for label, pattern in SIGNALS.items() if pattern.search(block)]
            if not flags:
                continue
            rank = 2 * len(flags)
            if "account" in flags:
                rank += 5
            if "security" in flags and "population" in flags:
                rank += 4
            if "payment" in flags and "scope" in flags:
                rank += 4
            if "payment" in flags and "population" in flags:
                rank += 3
            clipped = block if len(block) <= excerpt else block[: excerpt - 3].rstrip() + "..."
            result.append((rank, page_number, clipped, flags))
    return result


def render(paths: list[Path], limit: int, per_page: int, excerpt: int) -> str:
    output = [
        "# Account-state scan",
        "",
        "For each excerpt identify the object, population, denominator, evidence type,",
        "and whether it proves payment, security, custody, debt, or only an unresolved state.",
    ]
    for path in paths:
        rows = candidates(path, excerpt)
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
            output.append("No account-state language detected.")
    return "\n".join(output) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-per-document", type=int, default=18)
    parser.add_argument("--max-per-page", type=int, default=2)
    parser.add_argument("--excerpt-chars", type=int, default=650)
    args = parser.parse_args()
    report = render(args.pdf, args.max_per_document, args.max_per_page, args.excerpt_chars)
    if args.output:
        args.output.write_text(report, encoding="utf-8")
        print(args.output)
    else:
        print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
