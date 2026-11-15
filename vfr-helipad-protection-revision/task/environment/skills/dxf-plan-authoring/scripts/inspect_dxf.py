#!/usr/bin/env python3
"""Inspect modelspace units, extents, closed boundaries, and annotations."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import ezdxf


def points(entity: Any) -> list[tuple[float, float, float]]:
    if entity.dxftype() == "LWPOLYLINE":
        elevation = float(entity.dxf.elevation)
        return [(float(point[0]), float(point[1]), elevation) for point in entity.get_points("xy")]
    if entity.dxftype() == "POLYLINE":
        return [
            (float(vertex.dxf.location.x), float(vertex.dxf.location.y), float(vertex.dxf.location.z))
            for vertex in entity.vertices
        ]
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dxf", type=Path)
    parser.add_argument("--json", dest="json_path", type=Path)
    args = parser.parse_args()
    if not args.dxf.is_file():
        parser.error(f"DXF not found: {args.dxf}")

    doc = ezdxf.readfile(args.dxf)
    entities = list(doc.modelspace())
    polylines = [entity for entity in entities if entity.dxftype() in {"LWPOLYLINE", "POLYLINE"}]
    closed = [entity for entity in polylines if bool(getattr(entity, "closed", False) or getattr(entity, "is_closed", False))]
    coordinates = [point for entity in entities for point in points(entity)]
    finite = all(math.isfinite(value) for point in coordinates for value in point)
    zero_z = all(abs(point[2]) <= 1e-9 for point in coordinates)
    if coordinates:
        extents = {
            "min_x": min(point[0] for point in coordinates),
            "max_x": max(point[0] for point in coordinates),
            "min_y": min(point[1] for point in coordinates),
            "max_y": max(point[1] for point in coordinates),
        }
    else:
        extents = None
    summary = {
        "dxf_version": doc.dxfversion,
        "insunits": int(doc.header.get("$INSUNITS", 0)),
        "modelspace_entity_count": len(entities),
        "polyline_count": len(polylines),
        "closed_polyline_count": len(closed),
        "annotation_count": sum(entity.dxftype() in {"TEXT", "MTEXT", "DIMENSION", "LEADER", "MLEADER"} for entity in entities),
        "finite_polyline_coordinates": finite,
        "planar_polyline_coordinates": zero_z,
        "polyline_extents": extents,
        "layers": sorted({str(entity.dxf.layer) for entity in entities}),
    }
    rendered = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if finite and zero_z and len(closed) else 1


if __name__ == "__main__":
    raise SystemExit(main())
