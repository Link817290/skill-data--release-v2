#!/usr/bin/env python3
"""Derive evaluator anchors from the mounted source files, not from an answer key."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import ezdxf

from reference_solution import CODE, DXF, INCH_TO_M, code_values, find_door, find_hall, room_faces


def main() -> None:
    doc = ezdxf.readfile(DXF)
    hx, hy, hall_handle = find_hall(doc)
    left, bottom, right, top, walls = room_faces(doc, (hx, hy))
    dx0, dx1, dy, door_handle = find_door(doc, (left, bottom, right, top))
    rules = code_values()
    root = Path(os.environ.get("GROUND_TRUTH_ROOT", Path(__file__).resolve().parents[1]))
    out = root / "tests" / "ground_truth.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    values = {"room_left_in": left, "room_bottom_in": bottom, "room_right_in": right, "room_top_in": top, "hall_x": hx, "hall_y": hy, "door_x0_in": dx0, "door_x1_in": dx1, "door_y_in": dy, "route_min_m": rules["route_min_m"], "door_min_m": rules["door_min_m"], "route_source_width_m": (top - bottom) * INCH_TO_M, "door_source_width_m": (dx1 - dx0) * INCH_TO_M}
    locked = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (DXF, CODE)}
    out.write_text(json.dumps({"expected_values": values, "locked_inputs": locked, "evidence": {"route": rules["evidence"], "door": rules["evidence"], "drawing_layers": walls, "door_handle": door_handle, "hall_handle": hall_handle}}, indent=2) + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
