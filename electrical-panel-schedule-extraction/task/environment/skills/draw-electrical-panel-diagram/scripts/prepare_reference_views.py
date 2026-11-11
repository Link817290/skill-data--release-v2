#!/usr/bin/env python3
"""Create an overview and overlapping tiles for a dense schedule image."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from PIL import Image


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def overlap_fraction(value: str) -> float:
    parsed = float(value)
    if not 0 <= parsed < 0.5:
        raise argparse.ArgumentTypeError("must be in [0, 0.5)")
    return parsed


def positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--rows", type=positive_int, default=3)
    parser.add_argument("--cols", type=positive_int, default=3)
    parser.add_argument("--overlap", type=overlap_fraction, default=0.08)
    parser.add_argument("--scale", type=positive_float, default=2.0)
    parser.add_argument("--overview-width", type=positive_int, default=1800)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = args.image.resolve()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)

    with Image.open(source) as opened:
        image = opened.convert("RGB")
    width, height = image.size

    overview = image.copy()
    if overview.width > args.overview_width:
        overview.thumbnail((args.overview_width, height), Image.Resampling.LANCZOS)
    overview_path = output / "overview.png"
    overview.save(overview_path)

    tiles = []
    cell_width = width / args.cols
    cell_height = height / args.rows
    for row in range(args.rows):
        for column in range(args.cols):
            x0 = max(0, math.floor(column * cell_width - args.overlap * cell_width))
            y0 = max(0, math.floor(row * cell_height - args.overlap * cell_height))
            x1 = min(width, math.ceil((column + 1) * cell_width + args.overlap * cell_width))
            y1 = min(height, math.ceil((row + 1) * cell_height + args.overlap * cell_height))
            tile = image.crop((x0, y0, x1, y1))
            if args.scale != 1:
                size = (round(tile.width * args.scale), round(tile.height * args.scale))
                tile = tile.resize(size, Image.Resampling.LANCZOS)
            name = f"tile_r{row + 1:02d}_c{column + 1:02d}.png"
            tile.save(output / name)
            tiles.append({
                "file": name,
                "row": row + 1,
                "column": column + 1,
                "source_box": [x0, y0, x1, y1],
                "output_size": [tile.width, tile.height],
            })

    manifest = {
        "schema_version": "schedule-image-tiles-v1",
        "source_file": source.name,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "source_size": [width, height],
        "overview_file": overview_path.name,
        "grid": {"rows": args.rows, "columns": args.cols},
        "overlap_fraction": args.overlap,
        "scale": args.scale,
        "tiles": tiles,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
