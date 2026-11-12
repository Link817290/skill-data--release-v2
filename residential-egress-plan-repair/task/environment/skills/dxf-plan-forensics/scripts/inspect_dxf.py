#!/usr/bin/env python3
"""Describe a DXF without interpreting compliance or proposing a repair."""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import ezdxf


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: inspect_dxf.py drawing.dxf")
    path = Path(sys.argv[1])
    doc = ezdxf.readfile(path)
    model = doc.modelspace()
    layers: dict[str, dict[str, object]] = defaultdict(lambda: {"entity_count": 0, "entity_types": Counter()})
    anchors: list[dict[str, object]] = []
    for entity in model:
        layer = str(entity.dxf.layer)
        item = layers[layer]
        item["entity_count"] = int(item["entity_count"]) + 1
        types = item["entity_types"]
        assert isinstance(types, Counter)
        types[entity.dxftype()] += 1
        if entity.dxftype() == "TEXT":
            anchors.append({"text": str(entity.dxf.text), "x": float(entity.dxf.insert.x), "y": float(entity.dxf.insert.y), "layer": layer})
        elif entity.dxftype() == "MTEXT":
            anchors.append({"text": str(entity.text), "x": float(entity.dxf.insert.x), "y": float(entity.dxf.insert.y), "layer": layer})
    normalized = {}
    for name, item in sorted(layers.items()):
        normalized[name] = {"entity_count": item["entity_count"], "entity_types": dict(sorted(item["entity_types"].items()))}
    print(json.dumps({"dxf_version": doc.dxfversion, "insunits": doc.header.get("$INSUNITS"), "layers": normalized, "text_anchors": anchors}, indent=2))


if __name__ == "__main__":
    main()
