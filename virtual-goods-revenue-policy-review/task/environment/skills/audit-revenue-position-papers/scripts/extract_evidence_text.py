#!/usr/bin/env python3
"""Create temporary searchable text views of original PDF and HTML evidence."""

from __future__ import annotations

import argparse
import re
import subprocess
from html.parser import HTMLParser
from pathlib import Path


class VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() in {"script", "style"}:
            self.hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"script", "style"} and self.hidden_depth:
            self.hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden_depth:
            value = re.sub(r"\s+", " ", data).strip()
            if value:
                self.parts.append(value)


def extract(path: Path) -> str:
    suffix = path.suffix.casefold()
    if suffix == ".pdf":
        result = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout
    if suffix in {".htm", ".html"}:
        parser = VisibleText()
        parser.feed(path.read_text(encoding="utf-8", errors="ignore"))
        return "\n".join(parser.parts)
    raise ValueError(f"unsupported evidence format: {path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    written = 0
    for raw in args.inputs:
        path = Path(raw)
        if not path.is_file() or path.suffix.casefold() not in {".pdf", ".htm", ".html"}:
            continue
        output = args.output_dir / f"{path.name}.txt"
        output.write_text(extract(path), encoding="utf-8")
        print(f"{path.name} -> {output}")
        written += 1
    if not written:
        raise SystemExit("no supported evidence files were found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
