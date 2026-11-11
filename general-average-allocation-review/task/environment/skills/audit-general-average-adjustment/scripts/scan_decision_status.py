#!/usr/bin/env python3
"""Extract likely issue-status paragraphs from searchable judicial PDF records."""

from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from pathlib import Path


SIGNALS = {
    "scope": re.compile(r"not challenged|unchallenged|left undisturbed", re.I),
    "withdrawn": re.compile(r"abandon(?:ed)?|not pursued|withdrawn", re.I),
    "not_decided": re.compile(r"unnecessary to (?:decide|deal)|not necessary to (?:decide|deal)", re.I),
    "rejected": re.compile(
        r"reject(?:ed)?|unable to accept|not persuaded|not satisfied|do not consider|"
        r"did not accept|did not consider|no unseaworthiness|improbable that|doubt that",
        re.I,
    ),
    "issues": re.compile(r"grounds? of appeal|respondents?.{0,12}notice|burden of proof", re.I),
    "result": re.compile(r"appeal (?:must be|is|was) dismissed|claim must fail|conclusion", re.I),
}


def extract_pdf(path: Path) -> str:
    with tempfile.NamedTemporaryFile(suffix=".txt") as temporary:
        subprocess.run(
            ["pdftotext", "-layout", str(path), temporary.name],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return Path(temporary.name).read_text(encoding="utf-8", errors="replace")


def paragraphs(text: str) -> list[tuple[int, str]]:
    pattern = re.compile(
        r"(?ms)^\s*(\d{1,3})\.\s+(.*?)(?=^\s*\d{1,3}\.\s+|\Z)"
    )
    found = []
    for match in pattern.finditer(text):
        body = re.sub(r"\s+", " ", match.group(2)).strip()
        if body:
            found.append((int(match.group(1)), body))
    return found


def selected_rows(rows: list[tuple[int, str]], limit: int) -> list[tuple[int, str, list[str]]]:
    candidates = []
    edge_numbers = {number for number, _ in rows[:3] + rows[-3:]}
    last_number = max((number for number, _ in rows), default=0)
    for number, body in rows:
        flags = [label for label, pattern in SIGNALS.items() if pattern.search(body)]
        if number in edge_numbers:
            flags.append("edge")
        if flags:
            rank = 3 * len(flags) + (5 if "withdrawn" in flags or "result" in flags else 0)
            if "issues" in flags:
                rank += 3
            if last_number and number >= last_number * 0.8:
                rank += 4
            candidates.append((rank, number, body, sorted(set(flags))))
    candidates.sort(key=lambda row: (-row[0], row[1]))
    chosen = sorted(candidates[:limit], key=lambda row: row[1])
    return [(number, body, flags) for _, number, body, flags in chosen]


def render(paths: list[Path], limit: int, excerpt: int) -> str:
    output = [
        "# Decision-status scan",
        "",
        "Review each returned paragraph in context. Attribute party positions separately",
        "from findings and record whether each ground was accepted, rejected, withdrawn,",
        "not decided, or left undisturbed.",
    ]
    for path in paths:
        rows = paragraphs(extract_pdf(path))
        output.extend(["", f"## {path.name}", ""])
        if not rows:
            output.append("No numbered judicial paragraphs detected.")
            continue
        for number, body, flags in selected_rows(rows, limit):
            clipped = body if len(body) <= excerpt else body[: excerpt - 3].rstrip() + "..."
            output.append(f"- para {number} [{', '.join(flags)}]: {clipped}")
    return "\n".join(output) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-per-document", type=int, default=16)
    parser.add_argument("--excerpt-chars", type=int, default=650)
    args = parser.parse_args()
    report = render(args.pdf, args.max_per_document, args.excerpt_chars)
    if args.output:
        args.output.write_text(report, encoding="utf-8")
        print(args.output)
    else:
        print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
