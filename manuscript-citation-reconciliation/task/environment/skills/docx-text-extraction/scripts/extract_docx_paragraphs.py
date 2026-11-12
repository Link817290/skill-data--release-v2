#!/usr/bin/env python3
"""Extract direct body paragraphs from a DOCX into an intermediate JSON index."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from zipfile import BadZipFile, ZipFile
import xml.etree.ElementTree as ET


NS = {"w": "http://" + "schemas.openxmlformats.org/wordprocessingml/2006/main"}


def extract(path: Path) -> dict:
    with ZipFile(path) as archive:
        xml = archive.read("word/document.xml")
    root = ET.fromstring(xml)
    paragraphs = root.findall(".//w:body/w:p", NS)
    return {
        "file": path.name,
        "index_base": 0,
        "paragraphs": [
            {"index": index, "text": "".join(node.text or "" for node in paragraph.findall(".//w:t", NS))}
            for index, paragraph in enumerate(paragraphs)
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("docx", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        result = extract(args.docx)
    except (OSError, BadZipFile, KeyError, ET.ParseError) as exc:
        parser.error(str(exc))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
