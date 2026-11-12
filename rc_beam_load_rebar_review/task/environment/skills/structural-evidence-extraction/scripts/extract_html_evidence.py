#!/usr/bin/env python3
"""Extract neutral, local evidence fragments from an HTML/MathML file.

This utility intentionally does not calculate a structural result. It emits
headings, paragraph text and MathML blocks so a reviewer can build an evidence
ledger without losing formula context.
"""
from __future__ import annotations
import argparse, json, re
from html.parser import HTMLParser
from pathlib import Path

class FragmentParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.heading = ""
        self.in_heading = False
        self.in_para = False
        self.in_math = False
        self.buf = []
        self.fragments = []
        self.kind = None
    def handle_starttag(self, tag, attrs):
        if tag in {"h1", "h2", "h3", "h4"}:
            self.in_heading = True; self.buf = []; self.kind = "heading"
        elif tag == "p":
            self.in_para = True; self.buf = []; self.kind = "paragraph"
        elif tag == "math":
            self.in_math = True; self.buf = []; self.kind = "mathml"
    def handle_data(self, data):
        if self.in_heading or self.in_para or self.in_math:
            self.buf.append(data)
    def handle_entityref(self, name):
        if self.in_heading or self.in_para or self.in_math:
            self.buf.append("&" + name + ";")
    def _finish(self):
        text = re.sub(r"\\s+", " ", "".join(self.buf)).strip()
        if text:
            self.fragments.append({"kind": self.kind, "heading": self.heading, "text": text})
        self.buf = []
    def handle_endtag(self, tag):
        if tag in {"h1", "h2", "h3", "h4"} and self.in_heading:
            self._finish(); self.heading = self.fragments[-1]["text"]; self.in_heading = False
        elif tag == "p" and self.in_para:
            self._finish(); self.in_para = False
        elif tag == "math" and self.in_math:
            self._finish(); self.in_math = False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html_path", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    parser = FragmentParser()
    parser.feed(args.html_path.read_text(encoding="utf-8", errors="replace"))
    payload = {"file": args.html_path.name, "fragments": parser.fragments}
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
