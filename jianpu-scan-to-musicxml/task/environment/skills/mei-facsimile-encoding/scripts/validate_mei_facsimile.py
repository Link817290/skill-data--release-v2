#!/usr/bin/env python3
"""Validate generic MEI facsimile linkage without supplying musical answers."""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


XML_NAMESPACE = "http://www.w3.org/XML/1998/namespace"
XML_ID = f"{{{XML_NAMESPACE}}}id"


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def validate(path: Path) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        root = ET.parse(path).getroot()
    except Exception as exc:
        return {"valid": False, "errors": [f"XML parse failed: {exc}"], "warnings": [], "counts": {}}

    if local_name(root.tag) != "mei":
        errors.append("root element must be mei")
    ids: dict[str, ET.Element] = {}
    for node in root.iter():
        value = node.get(XML_ID) or node.get("id")
        if not value:
            continue
        if value in ids:
            errors.append(f"duplicate XML ID: {value}")
        ids[value] = node

    surfaces = [node for node in root.iter() if local_name(node.tag) == "surface"]
    zones = [node for node in root.iter() if local_name(node.tag) == "zone"]
    graphics = [node for node in root.iter() if local_name(node.tag) == "graphic"]
    events = [node for node in root.iter() if local_name(node.tag) == "syllable" or (local_name(node.tag) == "annot" and node.get("type") == "suzipu-event")]

    if not surfaces:
        errors.append("no facsimile surfaces")
    for surface in surfaces:
        if not any(local_name(child.tag) == "graphic" and child.get("target") for child in surface):
            errors.append(f"surface {surface.get(XML_ID, '<without-id>')} has no graphic target")

    for zone in zones:
        zone_id = zone.get(XML_ID) or zone.get("id") or "<without-id>"
        try:
            ulx, uly, lrx, lry = (float(zone.get(key, "")) for key in ("ulx", "uly", "lrx", "lry"))
        except ValueError:
            errors.append(f"zone {zone_id} has nonnumeric coordinates")
            continue
        if not (ulx < lrx and uly < lry):
            errors.append(f"zone {zone_id} has unordered or empty coordinates")

    used_refs: set[str] = set()
    for node in root.iter():
        for ref in node.get("facs", "").split():
            target = ref[1:] if ref.startswith("#") else ref
            if target:
                used_refs.add(target)
                if target not in ids:
                    errors.append(f"unresolved facsimile reference: {ref}")
    unused_zones = sorted((zone.get(XML_ID) or zone.get("id")) for zone in zones if (zone.get(XML_ID) or zone.get("id")) not in used_refs)
    if unused_zones:
        warnings.append(f"unused zones: {len(unused_zones)}")
    if not events:
        errors.append("no music-position containers")
    for index, event in enumerate(events, 1):
        has_text = any(local_name(node.tag) == "syl" for node in event.iter()) or event.get("data-text") is not None
        has_notation = any(local_name(node.tag) == "nc" for node in event.iter()) or event.get("data-pitch") is not None
        if not has_text:
            warnings.append(f"event {index} has no text representation")
        if not has_notation:
            warnings.append(f"event {index} has no notation representation")

    counts = {
        "surfaces": len(surfaces),
        "graphics": len(graphics),
        "zones": len(zones),
        "referenced_zones": len({ref for ref in used_refs if ref in ids and local_name(ids[ref].tag) == "zone"}),
        "events": len(events),
    }
    return {"valid": not errors, "errors": errors, "warnings": warnings, "counts": counts}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mei", type=Path)
    parser.add_argument("--json", action="store_true", help="emit a JSON report")
    args = parser.parse_args()
    result = validate(args.mei)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("VALID" if result["valid"] else "INVALID")
        print(json.dumps(result["counts"], ensure_ascii=False, sort_keys=True))
        for item in result["errors"]:
            print(f"ERROR: {item}")
        for item in result["warnings"]:
            print(f"WARNING: {item}")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
