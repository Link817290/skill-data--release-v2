#!/usr/bin/env python3
"""Emit a read-only structural inventory for a PDF."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import fitz


def widget_record(widget: fitz.Widget) -> dict:
    return {
        "field_name": widget.field_name,
        "field_type": widget.field_type,
        "field_value": widget.field_value,
        "field_flags": widget.field_flags,
        "rect": [round(float(v), 3) for v in widget.rect],
    }


def page_record(page: fitz.Page) -> dict:
    blocks = []
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        spans = []
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                spans.append(
                    {
                        "text": span.get("text", ""),
                        "bbox": [round(float(v), 3) for v in span.get("bbox", ())],
                        "size": span.get("size"),
                    }
                )
        blocks.append({"bbox": [round(float(v), 3) for v in block.get("bbox", ())], "spans": spans})
    annotations = []
    for annotation in page.annots() or []:
        annotations.append(
            {
                "type": annotation.type,
                "rect": [round(float(v), 3) for v in annotation.rect],
                "content": (annotation.info or {}).get("content", ""),
            }
        )
    images = []
    for item in page.get_images(full=True):
        xref = item[0]
        images.append(
            {
                "xref": xref,
                "width": item[2],
                "height": item[3],
                "rects": [
                    [round(float(v), 3) for v in rectangle]
                    for rectangle in page.get_image_rects(xref)
                ],
            }
        )
    return {
        "rect": [round(float(v), 3) for v in page.rect],
        "rotation": page.rotation,
        "text": page.get_text(),
        "blocks": blocks,
        "widgets": [widget_record(w) for w in (page.widgets() or [])],
        "annotations": annotations,
        "images": images,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--json", dest="output", type=Path, required=True)
    args = parser.parse_args()
    with fitz.open(args.pdf) as document:
        result = {
            "path": str(args.pdf),
            "page_count": document.page_count,
            "is_encrypted": document.is_encrypted,
            "needs_password": document.needs_pass,
            "metadata": document.metadata,
            "pages": [page_record(page) for page in document],
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
