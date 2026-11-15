#!/usr/bin/env python3
"""Derive verifier truth from the material-bound golden MEI."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from PIL import Image


def freeze_source_ink(payload: dict, materials: Path) -> None:
    images = {page: Image.open(materials / f"source_page_{page:02d}.png").convert("L") for page in (1, 2)}
    for event in payload["mei"]["events"]:
        image = images[event["page"]]
        for kind in ("text", "notation"):
            box = event.get(kind + "_box")
            runs = []
            if box:
                left, top, right, bottom = box
                for y in range(max(0, top), min(image.height, bottom)):
                    start = None
                    for x in range(max(0, left), min(image.width, right) + 1):
                        dark = x < min(image.width, right) and image.getpixel((x, y)) < 128
                        if dark and start is None:
                            start = x
                        if not dark and start is not None:
                            runs.append([y, start, x])
                            start = None
            event[kind + "_ink_runs"] = runs


def main(golden_dir: Path, output: Path) -> None:
    tests = Path(__file__).resolve().parents[1] / "tests"
    sys.path.insert(0, str(tests))
    from scoreio import parse_mei

    payload = {"schema": "suzipu-mei-ground-truth-v1", "mei": parse_mei(golden_dir / "揚州慢.mei")}
    freeze_source_ink(payload, Path(__file__).resolve().parents[1] / "environment/workspace/materials")
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: derive_ground_truth.py GOLDEN_DIR OUTPUT.json")
    main(Path(sys.argv[1]), Path(sys.argv[2]))
