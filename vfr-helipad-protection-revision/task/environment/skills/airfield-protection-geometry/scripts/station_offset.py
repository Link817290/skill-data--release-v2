#!/usr/bin/env python3
"""Generate auditable station-offset trapezoid vertices."""

from __future__ import annotations

import argparse
import json


def vertices(start: float, length: float, start_width: float, end_width: float, direction: int) -> list[list[float]]:
    start_station = direction * start
    end_station = direction * (start + length)
    return [
        [start_station, -start_width / 2.0],
        [end_station, -end_width / 2.0],
        [end_station, end_width / 2.0],
        [start_station, start_width / 2.0],
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=float, required=True)
    parser.add_argument("--length", type=float, required=True)
    parser.add_argument("--start-width", type=float, required=True)
    parser.add_argument("--end-width", type=float, required=True)
    parser.add_argument("--both", action="store_true")
    args = parser.parse_args()
    if args.start < 0 or args.length <= 0 or args.start_width <= 0 or args.end_width <= 0:
        parser.error("stations and widths must be positive, with a nonnegative start")

    directions = (1, -1) if args.both else (1,)
    output = {
        "inputs": vars(args),
        "polygons": [
            {
                "direction": "positive" if direction == 1 else "negative",
                "vertices": vertices(args.start, args.length, args.start_width, args.end_width, direction),
                "measured_length": args.length,
                "measured_start_full_width": args.start_width,
                "measured_end_full_width": args.end_width,
            }
            for direction in directions
        ],
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
