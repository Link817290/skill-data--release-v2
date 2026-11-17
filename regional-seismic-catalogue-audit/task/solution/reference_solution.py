#!/usr/bin/env python3
"""Derive an auditable seismic-catalogue report from the supplied HTML pages."""
from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path


class TableParser(HTMLParser):
    """Collect table rows while retaining the source order and cell text."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.table_depth = 0
        self.in_row = False
        self.in_cell = False
        self.rows: list[list[str]] = []
        self.row: list[str] = []
        self.buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "table":
            self.table_depth += 1
        elif tag == "tr" and self.table_depth:
            self.in_row = True
            self.row = []
        elif tag in {"td", "th"} and self.in_row:
            self.in_cell = True
            self.buf = []

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {"td", "th"} and self.in_cell:
            self.row.append(normalize_text("".join(self.buf)))
            self.in_cell = False
        elif tag == "tr" and self.in_row:
            if self.row:
                self.rows.append(self.row)
            self.in_row = False
        elif tag == "table" and self.table_depth:
            self.table_depth -= 1

    def handle_data(self, data):
        if self.in_cell:
            self.buf.append(data)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def parse_number(value: str):
    try:
        value = normalize_text(value).replace("°", "")
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_datetime(raw: str):
    """Return a normalized local (UTC+08) datetime and epoch milliseconds."""
    digits = "".join(re.findall(r"\d", raw))
    if len(digits) < 12:
        return None, None
    # A page may contain spaces inserted between individual digits.
    digits = digits[:14]
    try:
        year, month, day = int(digits[:4]), int(digits[4:6]), int(digits[6:8])
        hour, minute = int(digits[8:10]), int(digits[10:12])
        second = int(digits[12:14]) if len(digits) >= 14 else 0
        dt = datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
    except ValueError:
        return None, None
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z"), int(dt.timestamp() * 1000)


def event_key(time_ms, place: str, magnitude, latitude, longitude) -> str:
    """Fingerprint a row at the page's minute precision for cross-page matching."""
    if time_ms is None:
        stamp = "invalid-time"
    else:
        stamp = datetime.fromtimestamp(time_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M")
    mag = "null" if magnitude is None else f"{magnitude:.3f}"
    lat = "null" if latitude is None else f"{latitude:.1f}"
    lon = "null" if longitude is None else f"{longitude:.1f}"
    raw = f"{stamp}|{place}|{mag}|{lat}|{lon}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def discover_tables(path: Path):
    parser = TableParser()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    tables = []
    current = None
    section = ""
    source_row = 0
    for row in parser.rows:
        if len(row) == 1:
            if "地震目录" in row[0]:
                section = row[0]
            continue
        if len(row) < 5:
            continue
        if any("发震时刻" in cell for cell in row) and any("震级" in cell for cell in row):
            if current:
                tables.append(current)
            lat_i = next((i for i, x in enumerate(row) if "纬度" in x), None)
            lon_i = next((i for i, x in enumerate(row) if "经度" in x), None)
            current = {
                "table_index": len(tables) + 1,
                "section_title": section,
                "header": row,
                "latitude_column": lat_i,
                "longitude_column": lon_i,
                "rows": [],
            }
            continue
        if current and len(row) >= 5 and row[0]:
            source_row += 1
            current["rows"].append({"source_row": source_row, "cells": row[:5]})
    if current:
        tables.append(current)
    return tables


def parse_page(path: Path):
    tables = discover_tables(path)
    events = []
    event_rows = []
    table_summaries = []
    for table in tables:
        lat_i, lon_i = table["latitude_column"], table["longitude_column"]
        for row_number, item in enumerate(table["rows"], 1):
            cells = item["cells"]
            time_text = cells[0]
            place = cells[1]
            lat = parse_number(cells[lat_i]) if lat_i is not None and lat_i < len(cells) else None
            lon = parse_number(cells[lon_i]) if lon_i is not None and lon_i < len(cells) else None
            mag = parse_number(cells[4])
            utc_text, time_ms = parse_datetime(time_text)
            key = event_key(time_ms, place, mag, lat, lon)
            valid_coord = lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180
            quality = "supported"
            reasons = []
            if time_ms is None:
                quality, reasons = "partial", ["invalid_time"]
            if mag is None:
                quality, reasons = "partial", reasons + ["invalid_magnitude"]
            if not valid_coord:
                quality, reasons = "partial", reasons + ["invalid_coordinate"]
            event = {
                "event_key": key,
                "source_file": path.name,
                "source_row": item["source_row"],
                "table_index": table["table_index"],
                "row_number": row_number,
                "time_text": time_text,
                "time_ms": time_ms,
                "time_utc": utc_text,
                "place": place,
                "latitude": lat,
                "longitude": lon,
                "magnitude": mag,
                "quality_status": quality,
                "quality_reasons": reasons,
                "evidence": {"source_file": path.name, "source_row": item["source_row"], "table_index": table["table_index"], "raw_cells": cells},
            }
            events.append(event)
            event_rows.append({"source_row": item["source_row"], "table_index": table["table_index"], "row_number": row_number, "event_key": key, "raw_cells": cells})
        table_summaries.append({k: table[k] for k in ("table_index", "section_title", "header", "latitude_column", "longitude_column") } | {"row_count": len(table["rows"])})
    return tables, events, event_rows, table_summaries


def haversine(lat1, lon1, lat2, lon2):
    radius = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(max(0, min(1, h))))


def slope(xs, ys):
    if len(xs) < 2:
        return None
    xm, ym = statistics.mean(xs), statistics.mean(ys)
    den = sum((x - xm) ** 2 for x in xs)
    return None if den == 0 else sum((x - xm) * (y - ym) for x, y in zip(xs, ys)) / den


def assess(events, occurrences):
    valid = [e for e in events if e["quality_status"] == "supported"]
    valid.sort(key=lambda e: (e["time_ms"], e["event_key"]))
    mags = [float(e["magnitude"]) for e in valid]
    times = [float(e["time_ms"]) for e in valid]
    primary = max(valid, key=lambda e: (e["magnitude"], -e["time_ms"], e["event_key"])) if valid else None
    span_h = (max(times) - min(times)) / 3600000 if len(times) >= 2 else 0.0
    bins = [round(m * 10) / 10 for m in mags]
    bin_counts = Counter(bins)
    mc = min(bin_counts, key=lambda x: (-bin_counts[x], x)) if bins else None
    usable = [m for m in mags if mc is not None and m >= mc - 1e-9]
    denom = statistics.mean(usable) - mc + 0.05 if len(usable) >= 2 else None
    bval = math.log10(math.e) / denom if denom and denom > 0 else None
    lags = [(t - primary["time_ms"]) / 3600000 for t in times if primary and t > primary["time_ms"]]
    temporal = {"aftershock_count": len(lags), "bin_counts": [], "log_rate_slope": None, "included_event_keys": []}
    if len(lags) >= 3:
        lo, hi = max(min(lags), 1e-6), max(lags)
        edges = [lo * (hi / lo) ** (i / 4) for i in range(5)] if hi > lo else [lo + i for i in range(5)]
        counts = [sum(edges[i] <= lag <= edges[i + 1] if i == 3 else edges[i] <= lag < edges[i + 1] for lag in lags) for i in range(4)]
        xs = [(math.log10(edges[i]) + math.log10(edges[i + 1])) / 2 for i in range(4)]
        temporal.update({"bin_edges_hours": edges, "bin_counts": counts, "log_rate_slope": slope(xs, [math.log10(c + 1) for c in counts])})
        temporal["included_event_keys"] = [e["event_key"] for e in valid if e["time_ms"] > primary["time_ms"]]
    if valid:
        lat, lon = statistics.mean(e["latitude"] for e in valid), statistics.mean(e["longitude"] for e in valid)
        distances = [haversine(lat, lon, e["latitude"], e["longitude"]) for e in valid]
        spatial = {"centroid": {"latitude": lat, "longitude": lon}, "median_radius_km": statistics.median(distances), "max_radius_km": max(distances), "included_event_keys": [e["event_key"] for e in valid]}
    else:
        spatial = {"centroid": None, "median_radius_km": None, "max_radius_km": None, "included_event_keys": []}
    dominance = max(mags) - statistics.median(mags) if mags else None
    fraction = ((primary["time_ms"] - min(times)) / (max(times) - min(times))) if primary and len(times) >= 2 and max(times) > min(times) else None
    if len(events) < 8 or bval is None:
        classification, confidence = "insufficient_evidence", "low"
    elif dominance is not None and dominance >= 1.0 and fraction is not None and fraction <= 0.25 and len(lags) >= 5:
        classification, confidence = "mainshock_aftershock", "high"
    elif dominance is not None and dominance < 1.0 and bval >= 0.9:
        classification, confidence = "swarm_like", "moderate"
    else:
        classification, confidence = "mixed_or_uncertain", "moderate"
    duplicate_occ = sum(max(0, len(occurrences[e["event_key"]]) - 1) for e in events)
    return {
        "primary_event_key": primary["event_key"] if primary else None,
        "event_count": len(events),
        "valid_numeric_event_count": len(valid),
        "invalid_event_count": len(events) - len(valid),
        "duplicate_occurrence_count": duplicate_occ,
        "time_span_hours": span_h,
        "magnitude_stats": {"min": min(mags) if mags else None, "max": max(mags) if mags else None, "mean": statistics.mean(mags) if mags else None, "median": statistics.median(mags) if mags else None, "dominance_over_median": dominance},
        "completeness": {"magnitude_bin": mc, "bin_counts": {str(k): v for k, v in sorted(bin_counts.items())}, "usable_event_count": len(usable), "status": "supported" if mc is not None else "unknown", "included_event_keys": [e["event_key"] for e in valid if e["magnitude"] >= mc - 1e-9] if mc is not None else []},
        "b_value": {"value": bval, "formula": "log10(e)/(mean_magnitude_minus_mc_plus_half_bin)", "status": "supported" if bval is not None else "unknown", "included_event_keys": [e["event_key"] for e in valid if mc is not None and e["magnitude"] >= mc - 1e-9]},
        "temporal_decay": temporal,
        "spatial_compactness": spatial,
        "primary_time_fraction": fraction,
        "classification": classification,
        "confidence": confidence,
        "evidence": {"event_keys": [e["event_key"] for e in valid], "source_rows": [{"source_file": e["source_file"], "source_row": e["source_row"]} for e in valid], "primary": primary["evidence"] if primary else None},
    }


def page_title(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
    return normalize_text(re.sub(r"<[^>]+>", "", m.group(1))) if m else path.stem


def build_report(material_dir: str = "/workspace/materials") -> dict:
    root = Path(material_dir)
    paths = sorted(root.glob("*.html"))
    loaded = []
    occurrences = defaultdict(list)
    for path in paths:
        tables, events, event_rows, summaries = parse_page(path)
        for event in events:
            occurrences[event["event_key"]].append({"file": path.name, "source_row": event["source_row"]})
        loaded.append((path, tables, events, event_rows, summaries))
    records = []
    for path, tables, events, event_rows, summaries in loaded:
        source = {"path": f"materials/{path.name}", "document_title": page_title(path), "table_count": len(tables), "tables": summaries, "event_rows": event_rows, "event_row_count": len(event_rows)}
        status = "supported" if events and all(e["quality_status"] == "supported" for e in events) else ("partial" if events else "unknown")
        records.append({"file": path.name, "source": source, "events": events, "sequence_assessment": assess(events, occurrences), "status": status})
    duplicate_groups = []
    for key, occ in sorted(occurrences.items()):
        if len(occ) > 1:
            canonical = min(occ, key=lambda x: (x["file"], x["source_row"]))
            duplicate_groups.append({"event_key": key, "occurrences": occ, "occurrence_count": len(occ), "canonical_occurrence": canonical})
    classifications = Counter(r["sequence_assessment"]["classification"] for r in records)
    signatures = [{"file": r["file"], "classification": r["sequence_assessment"]["classification"], "event_count": r["sequence_assessment"]["event_count"], "valid_event_count": r["sequence_assessment"]["valid_numeric_event_count"], "primary_event_key": r["sequence_assessment"]["primary_event_key"]} for r in records]
    pairwise = []
    for i, left in enumerate(signatures):
        for right in signatures[i + 1:]:
            pairwise.append({"left_file": left["file"], "right_file": right["file"], "same_classification": left["classification"] == right["classification"], "shared_primary_event": left["primary_event_key"] is not None and left["primary_event_key"] == right["primary_event_key"], "evidence": [left["file"], right["file"]]})
    return {
        "schema_version": "1.0",
        "rule_version": "regional-screen-v1",
        "input_manifest": {"files": [p.name for p in paths], "count": len(paths)},
        "records": records,
        "cross_feed_reconciliation": {"canonical_rule": "lexical source filename, then smallest source row", "duplicate_groups": duplicate_groups, "duplicate_group_count": len(duplicate_groups), "unique_identity_count": len(occurrences), "total_event_occurrences": sum(len(v) for v in occurrences.values()), "duplicate_occurrence_count": sum(len(v) - 1 for v in occurrences.values() if len(v) > 1), "status": "supported"},
        "comparative_audit": {"signatures": signatures, "pairwise": pairwise, "class_counts": dict(sorted(classifications.items())), "status": "supported"},
        "aggregate": {"record_count": len(records), "source_event_count": sum(len(r["events"]) for r in records), "valid_event_count": sum(r["sequence_assessment"]["valid_numeric_event_count"] for r in records), "unique_identity_count": len(occurrences), "duplicate_group_count": len(duplicate_groups), "classification_counts": dict(sorted(classifications.items())), "record_status_counts": dict(sorted(Counter(r["status"] for r in records).items())), "overall_status": "partial" if any(r["status"] != "supported" for r in records) else "supported"},
    }


if __name__ == "__main__":
    import sys
    material_dir = sys.argv[1] if len(sys.argv) > 1 else "/workspace/materials"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("/workspace/output/seismic_catalogue_report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build_report(material_dir), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
