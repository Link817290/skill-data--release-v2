#!/usr/bin/env python3
"""Parse common bar marks and compute provided area only."""
import argparse
import json
import math
import re


def parse(mark):
    text = str(mark).strip().replace("Φ", "D").replace("φ", "D")
    m = re.search(r"(\d+)\s*[dD]\s*(\d+(?:\.\d+)?)", text)
    if m:
        n, diameter = int(m.group(1)), float(m.group(2))
        return {"count": n, "diameter_mm": diameter, "area_mm2": n * math.pi * diameter * diameter / 4.0}
    m = re.search(r"[dD]\s*(\d+(?:\.\d+)?)\s*@\s*(\d+(?:\.\d+)?)", text)
    if m:
        diameter, spacing = float(m.group(1)), float(m.group(2))
        return {"diameter_mm": diameter, "spacing_mm": spacing, "area_per_mm_width": math.pi * diameter * diameter / 4.0 / spacing}
    raise ValueError("unsupported bar notation")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mark")
    print(json.dumps(parse(args.mark) if False else parse(ap.parse_args().mark), ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
