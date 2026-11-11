#!/usr/bin/env python3
"""Extract searchable, paragraph-numbered text from an HTML filing."""

from __future__ import annotations

import argparse
import html
import re
from html.parser import HTMLParser
from pathlib import Path


class FilingTextParser(HTMLParser):
    BREAK_TAGS = {
        "br", "div", "p", "table", "tr", "td", "th", "li", "h1", "h2",
        "h3", "h4", "h5", "h6", "section", "article",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style"}:
            self.hidden_depth += 1
        if tag.lower() in self.BREAK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style"} and self.hidden_depth:
            self.hidden_depth -= 1
        if tag.lower() in self.BREAK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden_depth:
            self.parts.append(data)


def paragraphs(path: Path) -> list[str]:
    parser = FilingTextParser()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    text = html.unescape("".join(parser.parts)).replace("\xa0", " ")
    rows: list[str] = []
    for raw in text.splitlines():
        clean = re.sub(r"\s+", " ", raw).strip()
        if clean:
            rows.append(clean)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", type=Path, help="HTML filing or exhibit")
    ap.add_argument("--find", help="case-insensitive regular expression")
    ap.add_argument("--context", type=int, default=2, help="paragraphs around matches")
    ap.add_argument("--output", type=Path, help="write output instead of stdout")
    args = ap.parse_args()

    rows = paragraphs(args.input)
    selected = set(range(len(rows)))
    if args.find:
        pattern = re.compile(args.find, re.IGNORECASE)
        matches = [i for i, row in enumerate(rows) if pattern.search(row)]
        selected = set()
        for index in matches:
            lo = max(0, index - max(0, args.context))
            hi = min(len(rows), index + max(0, args.context) + 1)
            selected.update(range(lo, hi))

    output = "\n".join(f"P{index + 1:05d} {rows[index]}" for index in sorted(selected))
    if output:
        output += "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
