#!/usr/bin/env python3
"""Render a PDF for inspection and report page geometry; never edits the PDF."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import fitz


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--dpi", type=float, default=120.0)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    matrix = fitz.Matrix(args.dpi / 72.0, args.dpi / 72.0)
    report = {"page_count": 0, "pages": []}
    with fitz.open(args.pdf) as document:
        report["page_count"] = document.page_count
        for index, page in enumerate(document, start=1):
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            image_path = args.out_dir / f"page-{index:03d}.png"
            pixmap.save(image_path)
            report["pages"].append(
                {
                    "page": index,
                    "rect": [round(float(v), 3) for v in page.rect],
                    "rotation": page.rotation,
                    "text_chars": len(page.get_text()),
                    "image": str(image_path),
                }
            )
    (args.out_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
