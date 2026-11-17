#!/usr/bin/env python3
"""Deterministic strict scorer for the seismic catalogue report (pd-ledger-v1).

Usage: validator.py <report>
  <report> is seismic_catalogue_report.json, or a directory holding it (rollout artifacts/ or task golden/);
  default /workspace/output/seismic_catalogue_report.json. Materials are hashed from /workspace/materials, falling
  back to the task's environment/workspace/materials.

The strict score is settled in the standard form
  final = positive_earned * retention
  positive_earned = sum(weight[P] * completion[P])      (weights from scoring_params.json or $SCORING_PARAMS)
  retention = prod over damage instances of min(coefficient[D] for D in the instance)

P01-P08 are the eight report dimensions (manifest, source_structure, event_normalization, sequence_statistics,
identity_reconciliation, evidence_binding, comparative_audit, aggregate_closure); P09-P14 are the verdict layer
(record-status distribution, published verdicts, and the record, event, completeness and b-value verdicts). Each
completion is the item's fraction with the three continuous gates folded in (screening x observation x status,
each gate = 0.2 + 0.8 * its fidelity fraction).
Deductions (each fires as one damage instance):
  D01 gate: catalogue HTML materials missing or sha256 differs
  D02 gate: report missing/unparseable or schema_version != "1.0"
  D03 a page's b estimate is not the one `regional-screen-v1` produces on that page's quality-supported events
  D04 a normalized coordinate or magnitude that appears nowhere in the event's own source-row cells
A report the scorer cannot score returns a ledger with every completion 0. ``reward_strict``/``reward`` and the
reward files carry the settled strict.

This package publishes only the strict lens.

Schema tolerance
----------------
The memorandum fixes the deliverable, the screening rule and a *minimum*
skeleton, and says explicitly that additional evidence fields are allowed. It
does not fix the key names inside a record, the nesting, the stable-event-key
recipe, the unit of an epoch, the timezone the pages are read in, or the
vocabulary of a quality flag. The reference solution picks one of each; a report
that picks another is answering the same question.

So this scorer reads by meaning, not by path:

* a value is looked up through a synonym set and may sit one or two levels down
  (``magnitude: {"value": 7.6}`` is a magnitude of 7.6);
* a quantity may be published as a JSON number or as the decimal text the page
  printed (``"17.43"`` and ``17.43`` are the same observation);
* the lookup does not descend into a mapping that describes *where* a value was
  read from rather than the value itself -- a ``column_map`` saying
  ``{"lat": 2}`` is a column index, not a latitude;
* an event is identified by the source row it came from. The report may say
  which row that is in any of the three ways the memorandum leaves open: the
  verbatim cells, a row pointer that resolves inside the report's own row
  inventory, or the row as the page printed it (its time string and place);
* an epoch may be stated in seconds or milliseconds, and the whole report may
  read the pages in one constant timezone offset, provided the same offset holds
  for every event;
* ``supported``/``usable``/``valid``/``true`` mean the same thing, as do
  ``unusable``/``invalid``/``rejected``/``false``.

Nothing here relaxes a number, a derived statistic or a disposition. A report
whose magnitudes, counts, b-value or classification differ from the recomputed
ones still loses those checks.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def locate_materials() -> Path:
    candidates = [Path("/workspace/materials"), ROOT / "environment" / "workspace" / "materials"]
    for candidate in candidates:
        if all((candidate / name).is_file() for name in (
            "catalog_2018_full.html", "catalog_2018_partial.html", "catalog_2019_q1_q3.html"
        )):
            return candidate
    return candidates[-1]


MATERIALS = locate_materials()
# Numeric measurements use a relative tolerance only where the source has no
# fixed display precision. Epoch values are handled separately: the HTML pages
# print whole seconds, so a large epoch must not create a large absolute window.
TOL = 1e-6
TIME_TOL_MS = 1000.0
HASHES = {
    "catalog_2018_full.html": "ed460f489138113c9b44e3072354298ecadf7814c4ea371609947c576faf7ee3",
    "catalog_2018_partial.html": "f2a7ea06f29b0a5d3ed2715b624e15c0503c55e5474967807b87a5bbd3ad376b",
    "catalog_2019_q1_q3.html": "23c3c1f9ddfb33c78e13135b27df62a0303e3f5af9700e1d0cac42baa9bafefe",
}


def number(value):
    """The finite quantity a field states, whether it was written as a JSON
    number or as the decimal text the page printed beside it.

    The memorandum fixes neither, so `17.43` and `"17.43"` are one observation.
    Nothing else is relaxed: a different number is still a different number, and
    a value that is not a number at all stays not a number.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        v = float(value)
        return v if math.isfinite(v) else None
    if isinstance(value, str):
        t = value.replace("°", "").replace(" ", " ").strip()
        if t.startswith("+"):
            t = t[1:]
        try:
            v = float(t)
        except ValueError:
            return None
        return v if math.isfinite(v) else None
    return None


def equal(a, b):
    na, nb = number(a), number(b)
    if na is not None and nb is not None:
        return abs(na - nb) <= TOL * max(1.0, abs(nb))
    return a == b


def equal_epoch(a, b):
    """Compare source timestamps at the pages' one-second precision."""
    na, nb = number(a), number(b)
    return abs(na - nb) <= TIME_TOL_MS if na is not None and nb is not None else a == b


def fraction(items):
    values = list(items)
    return sum(bool(x) for x in values) / len(values) if values else 0.0


# ----------------------------------------------------------------- lookups

def nkey(text_value):
    return re.sub(r"[^a-z0-9]+", "", str(text_value or "").lower())


# Mappings that name *where* a value was read from, or what the schema of a row
# is, rather than stating an observation. `column_map: {"lat": 2}` is a column
# index; reading it as a latitude turns a report that documented its column
# resolution -- which the brief asks for -- into a report with wrong
# coordinates. The lookup never descends into one of these.
SCHEMA_CONTAINERS = {
    "columnmap", "colmap", "columnmapping", "columnmaps", "columnindex", "columnindices",
    "columnindexused", "columnorder", "columnpositions", "sourcecolumns", "sourcecolumn",
    "sourcecolumnorder", "columns", "header", "headers", "headertokens", "headertokensraw",
    "headermap", "validrange", "validranges", "range", "ranges", "schema",
}


def pluck(obj, names, depth=2):
    """First value stored under any synonym of `names`, searched breadth-first."""
    targets = {nkey(n) for n in names}
    level = [obj]
    for _ in range(depth + 1):
        nxt = []
        for node in level:
            if not isinstance(node, dict):
                continue
            for k, v in node.items():
                if nkey(k) in targets:
                    return v
            for k, v in node.items():
                if isinstance(v, dict) and nkey(k) not in SCHEMA_CONTAINERS:
                    nxt.append(v)
        if not nxt:
            break
        level = nxt
    return None


SCALAR_KEYS = ["value", "normalized", "parsed", "number", "degrees", "deg", "amount", "magnitude"]
TEXT_KEYS = ["raw", "display", "text", "raw_text", "display_text", "original", "source_text",
             "string", "value", "normalized"]


def scalar(value):
    """A quantity may be written bare or wrapped with its raw text and flags.

    Only unwrap when the wrapper really holds a scalar under one of those keys;
    a mapping that *is* the answer (bin counts, classification counts) is left
    alone.
    """
    if isinstance(value, dict):
        inner = pluck(value, SCALAR_KEYS, depth=1)
        if isinstance(inner, (int, float, str, bool)):
            return inner
    return value


def text(value):
    """The string a text field states, unwrapped from its evidence wrapper."""
    if isinstance(value, dict):
        inner = pluck(value, TEXT_KEYS, depth=1)
        return str(inner) if isinstance(inner, (str, int, float)) and not isinstance(inner, bool) else None
    if value is None or isinstance(value, (list, bool)):
        return None
    return str(value)


def get(obj, names, depth=2):
    return scalar(pluck(obj, names, depth))


# A field name may carry a qualifier: `place_source_text`, `canonical_place`,
# `magnitude_raw`, `time_epoch_ms` all still name the observation. A qualifier
# that turns the field into something else does not: `latitude_column` is a
# column, `epoch_interval_start` is a bound, `parse_status` is a verdict.
DISQUALIFIERS = ("column", "index", "count", "status", "flag", "reason",
                 "precision", "scale", "unit", "type", "policy", "interval", "range",
                 "confidence", "quality", "rule", "method", "note", "comment", "key")


def loose_pluck(obj, names, depth=2):
    """Second pass, used only when the exact synonym set finds nothing at all."""
    targets = [nkey(n) for n in names if len(nkey(n)) >= 5]
    if not targets:
        return None
    level = [obj]
    for _ in range(depth + 1):
        nxt = []
        for node in level:
            if not isinstance(node, dict):
                continue
            for k, v in node.items():
                t = nkey(k)
                if any(g in t for g in targets) and not any(d in t for d in DISQUALIFIERS):
                    return v
            for k, v in node.items():
                if isinstance(v, dict) and nkey(k) not in SCHEMA_CONTAINERS:
                    nxt.append(v)
        if not nxt:
            break
        level = nxt
    return None


def read(obj, names, depth=2):
    """The value a field states, read through the synonym set and then, only if
    that finds nothing, through a qualified form of the same name."""
    value = pluck(obj, names, depth)
    if value is None:
        value = loose_pluck(obj, names, depth)
    return scalar(value)


def hashable(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    return value


def file_names(seq):
    """Manifest entries may be plain names or objects carrying the name."""
    out = set()
    for item in seq if isinstance(seq, list) else []:
        if isinstance(item, dict):
            name = pluck(item, ["file", "name", "filename", "path", "file_name"], depth=1)
            out.add(Path(str(name)).name if name is not None else hashable(item))
        else:
            out.add(Path(str(item)).name)
    return out


# --------------------------------------------------------------- vocabulary

# `regional-screen-v1` states its own verdict for a derived statistic in these
# words -- "leaves b undefined" -- so a register that writes `defined` / `undefined`
# where the reference writes `supported` / `unsupported` has stated the same verdict.
SUPPORTED = {"supported", "usable", "valid", "ok", "true", "good", "accepted", "complete",
             "defined", "computed"}
UNSUPPORTED = {"unsupported", "unusable", "invalid", "rejected", "false", "bad", "incomplete",
               "unknown", "undefined", "notdefined"}


# A register may state its verdict and the findings it disclosed in one
# word: `ok_with_findings`, `ok_with_quality_findings`, `ok_with_anomalies`,
# `ok_with_exclusions`, `complete_with_quality_flags`,
# `complete_with_disclosed_source_warnings`, `supported_with_warning`. The
# verdict is the head of that phrase and the clause after the connective is the
# disclosure, which RUBRIC.md's Schema tolerance leaves to the register ("the
# vocabulary of a quality flag" is not fixed and is not scored). A section's
# `status` is read through the controlled vocabulary, and a verdict that carries
# its own disclosure is read on that head.
# Only a concessive connective is recognised -- a conditional one (`supported
# under an assumption`) states a different, qualified claim, not the same one.
STATUS_CONNECTIVES = {"with", "but", "though", "although", "despite"}


def verdict_head(value):
    """The verdict a compound status states, i.e. the words before the
    connective that introduces its disclosure. None if it states none."""
    words = [w for w in re.split(r"[^a-z0-9]+", str(value if value is not None else "").lower()) if w]
    for i in range(1, len(words)):
        if words[i] in STATUS_CONNECTIVES:
            return "".join(words[:i])
    return None


def quality(value):
    if isinstance(value, bool):
        return "supported" if value else "unsupported"
    t = nkey(value)
    if not t:
        return None
    if t in SUPPORTED:
        return "supported"
    if t in UNSUPPORTED:
        return "unsupported"
    head = verdict_head(value)
    if head in SUPPORTED:
        return "supported"
    if head in UNSUPPORTED:
        return "unsupported"
    return t


def reason_set(value):
    if value is None:
        return None
    if isinstance(value, (str, int, float)):
        value = [value]
    if not isinstance(value, list):
        return None
    return frozenset(nkey(hashable(x)) for x in value)


def epoch_ms(value):
    """Accept seconds or milliseconds; an epoch is never ambiguous at this scale."""
    v = number(value)
    if v is None:
        return None
    if abs(v) < 1e11:          # seconds
        return v * 1000.0
    if abs(v) < 1e14:          # milliseconds
        return v
    return v / 1000.0          # microseconds


# ------------------------------------------------------------ field synonyms

EV_FIELDS = {
    "source_file": ["source_file", "file", "filename", "page"],
    "source_row": ["source_row", "source_row_index", "row_index", "global_row"],
    "table_index": ["table_index", "source_table_index"],
    "row_number": ["row_number", "row_number_in_table", "row_in_table"],
    "time_text": ["time_text", "time_raw", "origin_time_raw", "raw_time", "time_string",
                  "time_display", "display_time", "time_local", "local_time", "origin_time",
                  "datetime", "time"],
    "time_ms": ["time_ms", "epoch_ms", "epoch_millis", "epoch_milliseconds",
                "epoch_seconds", "epoch_utc", "epoch", "origin_time_epoch_utc_seconds",
                "time_epoch", "time_epoch_ms", "time_epoch_seconds", "epoch_time",
                "unix_epoch", "unix_time", "timestamp"],
    "time_utc": ["time_utc", "origin_time_utc", "utc", "iso_utc", "origin_time_iso"],
    "place": ["place", "place_raw", "place_core", "location", "location_raw", "location_name",
              "epicentre", "epicenter", "place_text", "place_name", "region"],
    # The screening rule's own words are "quality-supported events"; the register names
    # that verdict after the use it licenses, so every spelling below states the same
    # screening outcome for the event.
    # The specific names are listed before the bare "state", so a register that also
    # carries a sub-check's own state (`coordinate_check.state`) is read on the verdict
    # it published rather than on the check.
    "quality_status": ["quality_status", "quality_state", "quality_supported",
                       "supported_for_sequence", "usable_for_sequence_assessment",
                       "usable_for_page_statistics", "sequence_statistics_eligible",
                       "quality_supported_for_rule", "sequence_supported",
                       "supported_for_regional_screen_v1", "usable_for_rule_statistics",
                       "statistics_included", "supported_for_statistics",
                       "usable_for_statistics", "statistics_supported",
                       "state", "status"],
    "quality_reasons": ["quality_reasons", "quality_flags", "field_issues", "reasons", "flags"],
    "latitude": ["latitude", "latitude_deg", "lat", "lat_deg"],
    "longitude": ["longitude", "longitude_deg", "lon", "lng", "lon_deg"],
    "magnitude": ["magnitude", "mag"],
    "raw_cells": ["raw_cells", "cells", "row_cells", "cells_raw", "raw_row", "row_raw",
                  "cell_text", "cell_values"],
}

ROW_LISTS = ["event_rows", "rows", "rows_extracted", "row_inventory"]

SEQ_FIELDS = {
    "primary_event_key": ["primary_event_key", "primary_event", "primary_key"],
    "event_count": ["event_count", "event_count_total", "events_total", "total_events"],
    "valid_numeric_event_count": ["valid_numeric_event_count", "quality_supported_event_count",
                                  "valid_event_count", "usable_event_count", "supported_event_count"],
    "invalid_event_count": ["invalid_event_count", "unusable_event_count", "invalid_events",
                            "excluded_event_count", "unsupported_event_count", "excluded_events",
                            "events_excluded_from_statistics",
                            "rows_excluded_from_rule_statistics"],
    "duplicate_occurrence_count": ["duplicate_occurrence_count", "duplicate_row_count",
                                   "duplicate_occurrences"],
    "classification": ["classification", "disposition"],
    "confidence": ["confidence"],
    "time_span_hours": ["time_span_hours", "span_hours", "time_span_h", "epoch_span_hours"],
    "primary_time_fraction": ["primary_time_fraction", "primary_position_fraction",
                              "primary_fraction"],
}

# (field, names searched inside the located section, names searched on the
# assessment itself -- kept specific so a bare "status" cannot be picked up)
SEQ_SECTIONS = {
    "magnitude_stats": {
        "min": (["min"], ["min_magnitude", "magnitude_min"]),
        "max": (["max"], ["max_magnitude", "magnitude_max"]),
        "mean": (["mean"], ["mean_magnitude", "magnitude_mean"]),
        "median": (["median"], ["median_magnitude", "magnitude_median"]),
        "dominance_over_median": (["dominance_over_median", "dominance",
                                   "dominance_over_median_magnitude"], ["dominance"]),
    },
    "completeness": {
        "magnitude_bin": (["magnitude_bin", "bin"], ["completeness_bin", "magnitude_of_completeness"]),
        "bin_counts": (["bin_counts", "bin_count_map", "magnitude_bin_counts",
                        "magnitude_bin_frequencies"],
                       ["magnitude_bin_counts", "completeness_bin_counts", "bin_count_map",
                        "magnitude_bin_frequencies"]),
        "usable_event_count": (["usable_event_count", "usable_events", "usable_set_size",
                                "usable_set_count"], ["usable_set_size", "usable_set_count"]),
        "status": (["status"], ["completeness_status"]),
        # The memorandum does not fix the nesting, so a register that lists the
        # keys its statistics ran on once, on the assessment, has stated them
        "included_event_keys": (["included_event_keys", "included_keys"],
                                ["included_event_keys", "usable_set_event_keys", "included_keys"]),
    },
    "b_value": {
        "value": (["value", "b_estimate", "b"], ["b_estimate", "b_value"]),
        # The same verdict written as an affirmative boolean: `b_value_defined`,
        # `b_defined`. `quality()` reads a bool as a verdict. The negated form
        # `b_undefined` is deliberately not read: it appears inside a branch/disposition
        # test, which states which rule branch fired, not what the register concluded
        # about b.
        "status": (["status", "state"], ["b_state", "b_status", "b_value_defined", "b_defined"]),
        "included_event_keys": (["included_event_keys", "included_keys"],
                                ["included_event_keys", "usable_set_event_keys", "included_keys"]),
    },
    "temporal_decay": {
        "aftershock_count": (["aftershock_count", "later_event_count", "lag_count",
                              "post_primary_event_count"], []),
        "bin_edges_hours": (["bin_edges_hours", "lag_bin_edges_hours", "lag_edges_hours"], []),
        "bin_counts": (["bin_counts", "lag_bin_counts", "lag_counts"], []),
        "log_rate_slope": (["log_rate_slope", "log_log_slope", "decay_slope",
                            "slope_log10_count_vs_log_lag", "slope"], []),
        "included_event_keys": (["included_event_keys", "lag_event_keys"], []),
    },
    "spatial_compactness": {
        "centroid": (["centroid"], []),
        "median_radius_km": (["median_radius_km", "median_distance_km"], []),
        "max_radius_km": (["max_radius_km", "maximum_radius_km", "max_distance_km"], []),
        "included_event_keys": (["included_event_keys"], []),
    },
}

# The memorandum names none of these sub-objects -- it fixes only the screening rule's
# outputs -- so the register files them under whatever heading it chose. Every spelling
# below names the same section.
SECTION_ALIASES = {
    "magnitude_stats": ["magnitude_stats", "magnitude_statistics", "statistics", "magnitudes",
                        "magnitude_summary", "magnitude_distribution", "magnitude_profile",
                        "statistics_snapshot"],
    "completeness": ["completeness", "completeness_bin_detail", "magnitude_completeness",
                     "completeness_detail", "completeness_analysis"],
    # A register may publish the b-value block under `b_estimate`; that is also this
    # scorer's synonym for the b value itself, both inside the section and on the
    # assessment, so the section it names is the same section.
    "b_value": ["b_value", "b_estimate_detail", "b_estimate", "b"],
    "temporal_decay": ["temporal_decay", "decay", "temporal", "temporal_statistics",
                       "time_behaviour", "time_behavior", "post_primary_decay",
                       "aftershock_decay", "decay_diagnostic", "temporal_profile"],
    "spatial_compactness": ["spatial_compactness", "compactness", "spatial_context",
                            "spatial_diagnostic", "spatial_summary", "spatial",
                            "spatial_profile", "geographic_compactness"],
}

XFEED_FIELDS = {
    "duplicate_group_count": ["duplicate_group_count", "duplicate_groups_count",
                              "cross_page_identity_group_total", "cross_file_group_count"],
    "unique_identity_count": ["unique_identity_count", "identity_group_total", "unique_identities"],
    "total_event_occurrences": ["total_event_occurrences", "event_rows_total", "total_occurrences",
                                "event_total"],
    "duplicate_occurrence_count": ["duplicate_occurrence_count", "duplicate_row_pair_total",
                                   "duplicate_occurrences"],
    "status": ["status", "reconciliation_status"],
}

AGG_FIELDS = {
    "record_count": ["record_count", "file_count", "files", "page_count"],
    "source_event_count": ["source_event_count", "event_total", "event_rows_total", "events_total",
                           "event_occurrence_count", "event_row_occurrence_count",
                           "listed_event_occurrence_count", "event_rows_extracted",
                           "rows_observed_total", "events_normalized", "events_normalized_total"],
    "valid_event_count": ["valid_event_count", "quality_supported_event_total", "events_usable",
                          "valid_event_total", "usable_event_total", "events_quality_supported",
                          "quality_supported_event_count", "quality_supported_events",
                          "quality_supported_event_occurrence_count"],
    "unique_identity_count": ["unique_identity_count", "identity_group_total", "unique_identities"],
    "duplicate_group_count": ["duplicate_group_count", "cross_page_identity_group_total",
                              "duplicate_groups_count"],
    "classification_counts": ["classification_counts", "class_counts"],
    # A register that calls a record a page publishes its status distribution
    # under that word; the memorandum does not fix the key names inside the aggregate.
    "record_status_counts": ["record_status_counts", "status_counts", "page_status_counts",
                             "record_status_distribution", "page_status_distribution"],
    "overall_status": ["overall_status", "status"],
}

SRC_FIELDS = {
    "path": ["path", "file_path", "source_path", "relative_path"],
    "document_title": ["document_title", "page_title", "title"],
    "table_count": ["table_count", "tables_count", "data_table_count"],
    "event_row_count": ["event_row_count", "row_count", "event_rows_count", "observed_event_count"],
}


# --------------------------------------------------------------- event model

# Fields whose compound spellings are read through `read`. The quality verdicts
# are deliberately not among them: an unreadable verdict is neutral in the status
# gate, so guessing at one can only make that gate less honest.
QUALIFIED = ("latitude", "longitude", "magnitude", "place", "time_ms", "raw_cells")


# The event's screening verdict is read from the event itself, or from the block the
# register files its quality findings in -- never from an unrelated sub-object. The bare
# synonyms `status` and `state` reach two levels down through `pluck`, which would also
# reach a `normalized_source_tokens.status` or a `quality.coordinate_check.state`;
# neither of those states anything about the event's quality.
QUALITY_BLOCKS = ["quality", "quality_support", "quality_assessment", "quality_check",
                  "screening", "quality_summary"]


def event_quality(event):
    """The screening verdict an event states, on the event or in its quality block."""
    if not isinstance(event, dict):
        return None
    value = pluck(event, EV_FIELDS["quality_status"], depth=0)
    if value is None:
        block = pluck(event, QUALITY_BLOCKS, depth=0)
        if isinstance(block, dict):
            value = pluck(block, EV_FIELDS["quality_status"], depth=1)
    return scalar(value)


def norm_event(event):
    """Flatten one event into the fields the register is scored on."""
    if not isinstance(event, dict):
        return {}
    out = {name: (read(event, names) if name in QUALIFIED else get(event, names))
           for name, names in EV_FIELDS.items()}
    out["quality_status"] = quality(event_quality(event))
    out["quality_reasons"] = reason_set(out["quality_reasons"])
    out["time_ms"] = epoch_ms(out["time_ms"])
    for name in ("time_text", "time_utc", "place"):
        out[name] = text(out[name])
    cells = pluck(event, EV_FIELDS["raw_cells"]) or loose_pluck(event, EV_FIELDS["raw_cells"])
    out["raw_cells"] = ([str(c) for c in cells]
                        if isinstance(cells, list) and cells
                        and not any(isinstance(c, (dict, list)) for c in cells) else None)
    out["event_key"] = event.get("event_key")
    # Every name the report gave this event. The memorandum does not fix the
    # stable-event-key recipe or the field it is written under, so an event the
    # report calls `event_uid`, `key` or `observation_id` is naming itself just
    # as much as one that calls it `event_key`; a key list elsewhere in the
    # report is written in whichever of those names the report chose.
    out["labels"] = named_labels(event)
    for name in ("latitude", "longitude", "magnitude"):
        value = number(out[name])
        out[name] = value if value is not None else out[name]
    return out


def identity(obj):
    """A row is identified by the verbatim cells it was read from."""
    if not isinstance(obj, dict):
        return None
    flat = obj if isinstance(obj.get("raw_cells"), list) else norm_event(obj)
    cells = flat.get("raw_cells")
    if isinstance(cells, list) and cells:
        return ("cells",) + tuple(squash(c) for c in cells)
    key = flat.get("event_key")
    return ("key", key) if key is not None and not isinstance(key, (dict, list)) else None


def probes(table_index, row_number, source_row):
    """The row pointers an object publishes, most specific first."""
    ti, rn = number(table_index), number(row_number)
    out = []
    sr = None if isinstance(source_row, (dict, list)) else source_row
    if ti is not None and rn is not None:
        out.append(("tr", ti, rn))
    if sr is not None:
        if ti is not None:
            out.append(("ts", ti, str(sr)))
        out.append(("sr", str(sr)))
    return out


def row_directory(source):
    """Every row pointer the report's own inventory publishes -> that row's cells.

    The brief asks that a second analyst be able to follow each value to a page
    row; a report that keeps the verbatim cells once, in its row inventory, and
    points at them from each event has done that. An ambiguous pointer (two rows
    claiming it) resolves to nothing.
    """
    if not isinstance(source, dict):
        return {}
    rows = pluck(source, ROW_LISTS)
    seen = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        ident = identity(row)
        if ident is None or ident[0] != "cells":
            continue
        handles = probes(get(row, EV_FIELDS["table_index"]),
                         get(row, EV_FIELDS["row_number"]),
                         get(row, EV_FIELDS["source_row"]))
        # a row may also be pointed at by whatever name the report gave it
        handles += [("id", label) for label in labels_of(row)]
        for probe in handles:
            seen.setdefault(probe, set()).add(ident)
    return {k: next(iter(v)) for k, v in seen.items() if len(v) == 1}


def squash(value):
    """Whitespace-insensitive form of a source string. Unlike `nkey` this keeps
    the source-language characters: every place on these pages is Chinese."""
    return re.sub(r"\s+", "", str(value or "")).lower()


def same_text(a, b):
    r"""Two spellings of one cell's text.

    The pages print whitespace inside a cell -- `2018/01/10 \xa0 10:51:29` is one
    cell -- and the reference derivation collapses it
    (`re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()`), so the reference
    does not publish the verbatim characters either. Which of the two spellings a
    report transcribes is a convention the memorandum does not fix, and both name
    the same cell of the same row, so it is not scored. Everything the cell says
    -- its digits, its place name, its sign -- is still compared.
    """
    if a is None or b is None:
        return a == b
    return squash(a) == squash(b)


def same_cells(a, b):
    """The same, for a row's cell list."""
    if not isinstance(a, list) or not isinstance(b, list):
        return a == b
    return len(a) == len(b) and all(squash(x) == squash(y) for x, y in zip(a, b))


def printed_key(flat):
    """The row as the page printed it: its calendar minute and its place text."""
    digits = re.sub(r"\D", "", str(flat.get("time_text") or ""))[:12]
    place = squash(flat.get("place"))
    return ("row", digits, place) if len(digits) == 12 and place else None


def event_handles(flat, rows):
    """Every handle by which this event can be recognised as one source row."""
    out = []
    ident = identity(flat)
    if ident is not None and ident[0] == "cells":
        out.append(ident)
    for probe in probes(flat.get("table_index"), flat.get("row_number"), flat.get("source_row")):
        if probe in rows:
            out.append(rows[probe])
            break
    # the same row, whether or not the report collapsed the non-breaking spaces
    # the pages print inside a timestamp. Keeping them is still scored -- on
    # `raw_cells`, where the verbatim text is the answer.
    out += [("ncells",) + tuple(squash(c) for c in h[1:]) for h in list(out) if h[0] == "cells"]
    handle = printed_key(flat)
    if handle is not None:
        out.append(handle)
    return out


def flatten_record(record):
    if not isinstance(record, dict):
        return [], []
    rows = row_directory(record.get("source") if isinstance(record.get("source"), dict)
                         else pluck(record, ["source"], depth=1))
    flats = [norm_event(e) for e in (record.get("events") or []) if isinstance(e, dict)]
    return flats, [event_handles(f, rows) for f in flats]


def key_directory(pairs, side):
    """Every name one side of the comparison gives its events -> that row.

    A report names its events under whatever field it chose -- `event_key`,
    `event_uid`, `key`, `observation_id`. The memorandum fixes neither the
    stable-event-key recipe nor the field it is written under, and the key lists
    elsewhere in the same report are written in that same name, so each such
    field is read as a naming of the events.

    The fields are merged most-discriminating first: the field that tells the
    page's events apart is the one the report is using as its key, and a field
    that only labels a section or a table is merged after it and cannot displace
    it. Within one field the later event wins -- a page may print the same event
    twice under the same key.
    """
    fields = {}
    for pair in pairs:
        ident, flat = pair[0], pair[side]
        if not flat:
            continue
        for field, value in flat.get("labels") or []:
            fields.setdefault(field, {})[value] = ident
    out = {}
    for _, values in sorted(fields.items(), key=lambda kv: -len(kv[1])):
        for value, ident in values.items():
            out.setdefault(value, ident)
    return out


def pair_events(got_record, exp_record):
    """Match every reference event of a page to at most one submitted event.

    A page may list the very same row twice; the pairing is one-to-one, so a
    handle two rows share is spent once per row, in source order.
    """
    gflats, ghandles = flatten_record(got_record)
    eflats, ehandles = flatten_record(exp_record)
    index = {}
    for i, hs in enumerate(ghandles):
        for h in dict.fromkeys(hs):
            index.setdefault(h, []).append(i)
    taken, pairs = set(), []
    for ef, hs in zip(eflats, ehandles):
        got = {}
        for h in dict.fromkeys(hs):
            i = next((j for j in index.get(h, []) if j not in taken), None)
            if i is not None:
                got = gflats[i]
                taken.add(i)
                break
        ident = hs[0] if hs else ("key", ef.get("event_key"))
        pairs.append((ident, ef, got))
    return pairs, len(gflats)


def time_offset(paired):
    """One constant epoch offset for the whole report, or 0.0.

    A report may read the pages in a declared timezone; that shifts every epoch
    by the same whole number of minutes. A shift that is not constant, or not a
    whole number of minutes, is not a convention and is not granted.
    """
    deltas = []
    for pairs, _ in paired.values():
        for _, ee, ge in pairs:
            if isinstance(ge.get("time_ms"), float) and isinstance(ee.get("time_ms"), float):
                deltas.append(ge["time_ms"] - ee["time_ms"])
    if not deltas:
        return 0.0
    first = deltas[0]
    if any(abs(d - first) > 1.0 for d in deltas):
        return 0.0
    if abs(first) > 14 * 3600 * 1000 or abs(first) % 60000 > 1.0:
        return 0.0
    return first


def occurrence_directory(records):
    """(page, row pointer) -> that row, for one side of the comparison.

    An occurrence and an evidence pointer both name a row on a page. Each side
    numbers its own rows; resolving the pointer through the inventory it belongs
    to puts both sides in the same space, which is the row itself.
    """
    out = {}
    for name, record in records.items():
        source = record.get("source") if isinstance(record, dict) else None
        for probe, ident in row_directory(source).items():
            out[(name,) + probe] = ident
    return out


def named_labels(obj):
    """Every (field, name) under which the report names this row or occurrence:
    its own key, id or fingerprint, whatever it decided to call that field.

    The field is kept because a register names its events under one field and
    labels them with others; which is which is read off the data, not guessed
    from the spelling.
    """
    out = []
    if not isinstance(obj, dict):
        return out
    for k, v in obj.items():
        t = nkey(k)
        if isinstance(v, (str, int, float)) and not isinstance(v, bool) and (
                "key" in t or "fingerprint" in t or t == "id" or t.endswith("id")):
            out.append((t, str(v)))
    return out


def labels_of(obj):
    return [v for _, v in named_labels(obj)]


def canonical_ident(ident):
    """One spelling of a row identity, insensitive to the whitespace a page prints."""
    if isinstance(ident, tuple) and ident and ident[0] == "cells":
        return ("ncells",) + tuple(squash(c) for c in ident[1:])
    return ident


def occurrence_key(occ, directory, keymap):
    """What row this occurrence names, or the occurrence verbatim if unreadable."""
    if occ is None:
        return None
    if not isinstance(occ, dict):
        if isinstance(occ, list):
            return hashable(occ)
        ident = next((v for k, v in directory.items() if k[1:] == ("id", str(occ))), None)
        # a bare occurrence may equally be the key the report gave that event,
        # the same way an occurrence object carrying that key is resolved below
        if ident is None:
            ident = ident_of(keymap, occ)
        return canonical_ident(ident) if ident is not None else hashable(occ)
    name = pluck(occ, ["file", "filename", "file_name", "source_file", "page", "path"], depth=1)
    name = Path(str(name)).name if name is not None and not isinstance(name, (dict, list)) else None
    labels = labels_of(occ)
    handles = probes(get(occ, EV_FIELDS["table_index"]),
                     get(occ, EV_FIELDS["row_number"]),
                     get(occ, EV_FIELDS["source_row"]))
    handles += [("id", label) for label in labels]
    ident = None
    for probe in handles:
        if name is not None and (name,) + probe in directory:
            ident = directory[(name,) + probe]
            break
        if probe[0] == "id":
            ident = next((v for k, v in directory.items() if k[1:] == probe), None)
            if ident is not None:
                break
    if ident is None:
        ident = next((x for x in (ident_of(keymap, lab) for lab in labels) if x is not None), None)
    return canonical_ident(ident) if ident is not None else (name, hashable(occ))


OCC_NAMES = ["occurrences", "occurrence_list", "observations", "members", "source_rows", "rows",
             "member_keys", "member_event_keys", "member_ids", "occurrence_keys", "event_keys"]


def occurrences_of(obj):
    """The list of occurrences a group publishes, preferring the fullest spelling.

    Synonyms are tried in order rather than by the order the report happens to
    write its keys in, so a group that carries both a key list and an occurrence
    list is read through the occurrence list.
    """
    for name in OCC_NAMES:
        value = pluck(obj, [name])
        if isinstance(value, list) and value:
            return value
    return None


def entries_of(value):
    """The entries of a collection published either as an array or as a mapping
    keyed by whatever the report decided to index it by. The memorandum fixes
    neither the container nor the key it is indexed under."""
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict)]
    if isinstance(value, dict) and value and all(isinstance(x, dict) for x in value.values()):
        return list(value.values())
    return []


def collected_groups(node):
    """The identity groups a reconciliation object publishes, wherever it put them.

    A duplicate group is recognised by the set of rows it collects, so it cannot
    also be required to sit under a key whose name contains the word "group": a
    report that files the same objects under `occurrence_index`,
    `canonical_events` or `identity_index` has published the same grouping. What
    is required is that the entries really carry their occurrences -- a list of
    bare counts, or of placeholder objects with nothing in them, is not a
    grouping and is collected from nowhere.

    Every such collection on the object is taken, not the first one that
    matches, so a report that splits its groups across `duplicate_groups` and
    `conflict_groups` is not read as having published only half of them.
    """
    if not isinstance(node, dict):
        return None
    out = []
    for key, value in node.items():
        entries = entries_of(value)
        if not entries:
            continue
        named = ("group" in nkey(key)
                 and not any(d in nkey(key) for d in DISQUALIFIERS))
        # the shape test needs no name guard: an entry that carries its
        # occurrences is a group whatever the key above it is called, and an
        # entry that carries none is not one whatever it is called.
        carried = [e for e in entries if occurrences_of(e)]
        if named or carried:
            out += entries if named else carried
    return out or None


def occurrence_set(value, directory, keymap):
    if not isinstance(value, list):
        return None
    return frozenset(occurrence_key(x, directory, keymap) for x in value)


CLASS_COUNT_NAMES = ["class_counts", "classification_counts", "classification_distribution",
                     "class_distribution", "disposition_counts"]

# The assessment evidence: the primary row, the keys the arithmetic ran on, and
# the rows those keys stand for. The memorandum names none of these fields, so
# each is read through the spellings a register can reasonably use for it.
EVIDENCE_PRIMARY_NAMES = ["primary", "primary_event_key", "primary_event", "primary_row",
                          "primary_event_ref", "primary_occurrence"]
EVIDENCE_KEY_NAMES = ["event_keys", "included_event_keys", "included_keys", "event_keys_used",
                      "supported_event_keys", "included_event_uids", "event_keys_considered"]
EVIDENCE_ROW_NAMES = ["source_rows", "rows", "row_pointers", "source_row_pointers",
                      "included_source_rows", "evidence_rows"]


# The one occurrence a group nominates to stand for it. The memorandum asks for
# "a deterministic canonical occurrence" and fixes neither the field nor whether
# the group names that row by a pointer or by the key it gave the event.
CANONICAL_NAMES = ["canonical_occurrence", "canonical", "canonical_row",
                   "representative_occurrence", "representative_row", "representative",
                   "canonical_event_key", "canonical_key", "canonical_event",
                   "anchor_observation", "anchor_observation_id", "anchor_occurrence",
                   "preferred_observation", "preferred_observation_key"]


def primary_row(value, directory, keymap):
    """The row a pointer names, however the report addressed it: as a pointer
    into its own inventory, or as the key it gave the event."""
    return occurrence_key(value, directory, keymap)

PAIR_LIST_NAMES = {"pairwise", "pairs", "pairwisecomparisons", "pagepairs", "unorderedpairs"}


def index_by_file(value):
    """A per-page collection, indexed by the page each entry speaks for.

    The memorandum asks for one signature per page and fixes neither the
    container nor the key it is indexed under, so the collection may be an array
    of entries that each name their page or a mapping whose keys are the pages.
    """
    if isinstance(value, dict) and value and all(isinstance(x, dict) for x in value.values()):
        out = {}
        for k, v in value.items():
            name = Path(str(k)).name
            if name.lower().endswith(".html"):
                out.setdefault(name, v)
        if out:
            return out
    return by_file(value)


def collected_signatures(node):
    """The per-page signatures a comparative audit publishes, wherever it put them.

    A signature is recognised by the page it speaks for, not by the report
    calling its list `signatures`: `per_page`, `per_file`, `record_signatures`
    and `source_signatures` are the same collection. A page-pair list is not one
    of these -- it names two pages, not one, so it indexes by no single page and
    is skipped by name as well, in case a report writes its pairs as
    ``{"file": ...}`` entries.

    Every per-page block found is merged into that page's signature, so a report
    that split the same page's facts over two per-page blocks is read as having
    stated them; an empty entry adds nothing.
    """
    if not isinstance(node, dict):
        return {}
    out = {}
    for key, value in node.items():
        if nkey(key) in PAIR_LIST_NAMES:
            continue
        for name, entry in index_by_file(value).items():
            if entry:
                out.setdefault(name, {}).update(entry)
    return out


def by(items, key):
    return {item.get(key): item for item in items if isinstance(item, dict) and key in item}


def by_file(items):
    """Index records / signatures by the page they speak for.

    The page is named by its file; whether the report writes the bare name or
    the path it was read from is not a fact about the catalogue.
    """
    out = {}
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        name = pluck(item, ["file", "filename", "file_name", "source_file", "path", "name"], depth=1)
        if name is None or isinstance(name, (dict, list)):
            continue
        out.setdefault(Path(str(name)).name, item)
    return out


# -------------------------------------------------------------------- score

def score(got, exp):
    detail = {}
    em, gm = exp.get("input_manifest", {}), got.get("input_manifest", {})
    detail["manifest"] = fraction([
        equal(get(gm, ["count", "file_count", "files_count"]), get(em, ["count"])),
        file_names(pluck(gm, ["files"])) == file_names(pluck(em, ["files"])),
    ])

    erecs, grecs = by_file(exp.get("records", [])), by_file(got.get("records", []))
    paired = {name: pair_events(grecs.get(name, {}), er) for name, er in erecs.items()}
    offset = time_offset(paired)
    edir, gdir = occurrence_directory(erecs), occurrence_directory(grecs)

    source_checks, event_checks, stat_checks, evidence_checks = [], [], [], []
    # P11-P14: the verdict layer, collected alongside the dimensions it already sits inside.
    record_verdict, event_verdict, completeness_verdict, bvalue_verdict = [], [], [], []
    all_gkeys, all_ekeys = {}, {}
    for name, er in erecs.items():
        gr = grecs.get(name, {})
        es, gs = er.get("source", {}), gr.get("source", {})
        for field, names in SRC_FIELDS.items():
            source_checks.append(equal(get(gs, names), es.get(field)))
        record_verdict.append(quality(get(gr, ["status", "record_status"])) == quality(er.get("status")))
        # table descriptors: compare the facts each entry states, not its key names
        TABLE_FIELDS = {"section_title": ["section_title", "section_label", "caption", "title"],
                        "header": ["header", "header_tokens", "header_tokens_raw", "columns"],
                        # The reference's own field is a column index, so the qualifier
                        # `_index` does not turn it into something else; the exact spellings
                        # are listed because the generic qualifier pass refuses "index".
                        "latitude_column": ["latitude_column", "lat_column",
                                            "latitude_column_index", "lat_column_index"],
                        "longitude_column": ["longitude_column", "lon_column",
                                             "longitude_column_index", "lon_column_index"],
                        # A data section's row count is its event-row count
                        "row_count": ["row_count", "rows", "observed_event_count", "data_row_count",
                                      "event_row_count", "event_count_parsed", "event_rows_parsed"]}
        gtables = [t for t in (pluck(gs, ["tables"]) or []) if isinstance(t, dict)]
        etables = es.get("tables") or []
        # The reference publishes a page's three data sections; the pages carry 13
        # table elements, and the memorandum asks the register to "preserve page and table
        # evidence" and the "discovered table inventory". A register that documents every
        # table element has published the data sections too, further down its own list, so
        # the descriptor is located by the section it describes -- its title, else its
        # header tokens -- and only falls back to position when it names neither.
        by_title, by_head = {}, {}
        for t in gtables:
            title = text(get(t, TABLE_FIELDS["section_title"]))
            if title:
                by_title.setdefault(squash(title), t)
            head = pluck(t, TABLE_FIELDS["header"])
            if isinstance(head, list) and head and not any(isinstance(c, (dict, list)) for c in head):
                by_head.setdefault(tuple(squash(c) for c in head), t)
        source_checks.append(len(gtables) >= len(etables))
        for i, et in enumerate(etables):
            at = by_title.get(squash(et.get("section_title")))
            if at is None:
                at = by_head.get(tuple(squash(c) for c in et.get("header", [])))
            if at is None:
                at = gtables[i] if i < len(gtables) else {}
            for field, names in TABLE_FIELDS.items():
                if field in et:
                    if field == "section_title":
                        source_checks.append(same_text(text(get(at, names)), et.get(field)))
                    elif field == "header":
                        source_checks.append(same_cells(pluck(at, names), et.get(field)))
                    else:
                        source_checks.append(equal(get(at, names), et.get(field)))
        erows = {identity(r): r for r in es.get("event_rows", []) if identity(r)}
        grows = {identity(r): r for r in pluck(gs, ROW_LISTS) or [] if identity(r)}
        source_checks.append(set(erows) == set(grows))
        for ident, expected_row in erows.items():
            actual_row = grows.get(ident, {})
            # `table_index`, `source_row` and `row_number` are the reference's own
            # enumeration of the pages' tables and rows. The pages carry 13 table
            # elements of which 9 are data sections; the reference numbers the three
            # data sections of a page 1..3 and its event rows 1..N, and the memorandum
            # fixes neither which elements count as a table nor how either is numbered.
            # This scorer refuses to compare a pointer "with the reference's row
            # numbering" (Schema tolerance) and resolves every pointer through the
            # inventory it belongs to; the numbers themselves are a convention and are
            # not compared. The row is compared as a row, by its cells.
            source_checks += [
                identity(actual_row) == identity(expected_row),
                same_cells(pluck(actual_row, EV_FIELDS["raw_cells"]), expected_row.get("raw_cells")),
            ]

        pairs, got_event_count = paired[name]
        event_checks.append(all(ge for _, _, ge in pairs) and got_event_count == len(pairs))
        for _, ee, ge in pairs:
            for field in ("source_file", "time_text",
                          "time_utc", "place", "quality_status", "quality_reasons"):
                expected_value = ee.get(field)
                if field == "quality_status":
                    expected_value = quality(expected_value)
                    event_verdict.append(ge.get(field) == expected_value)
                if field == "time_utc":
                    # the page prints a wall clock; the label a report puts on it
                    # follows from the timezone it declares, which is its own choice
                    event_checks.append(nkey(ge.get(field))[:12] == nkey(expected_value)[:12]
                                        if expected_value else ge.get(field) == expected_value)
                    continue
                if field == "source_file":
                    event_checks.append(Path(str(ge.get(field) or "")).name == str(expected_value or ""))
                    continue
                if field in ("time_text", "place"):
                    event_checks.append(same_text(ge.get(field), expected_value))
                    continue
                event_checks.append(equal(ge.get(field), expected_value))
            expected_ms = ee.get("time_ms")
            event_checks.append(equal_epoch(ge.get("time_ms"), expected_ms + offset)
                                if isinstance(expected_ms, float) and isinstance(ge.get("time_ms"), float)
                                else ge.get("time_ms") == expected_ms)
            for field in ("latitude", "longitude", "magnitude"):
                event_checks.append(equal(ge.get(field), ee.get(field)))
            event_checks.append(same_cells(ge.get("raw_cells"), ee.get("raw_cells")))

        # Both sides name events however they like; a key is translated into the
        # row it stands for before any key list is compared.
        gkeys = key_directory(pairs, 2)
        ekeys = key_directory(pairs, 1)
        all_gkeys.update(gkeys)
        all_ekeys.update(ekeys)

        ga, ea = pluck(gr, ["sequence_assessment", "sequence"]) or {}, er.get("sequence_assessment", {})
        for field, names in SEQ_FIELDS.items():
            expected_value = ea.get(field)
            if field == "primary_event_key":
                stat_checks.append(ident_of(gkeys, get(ga, names)) == ident_of(ekeys, expected_value)
                                   and ident_of(ekeys, expected_value) is not None)
            else:
                stat_checks.append(equal(get(ga, names), expected_value))
        for section, fields in SEQ_SECTIONS.items():
            located = pluck(ga, SECTION_ALIASES[section])
            for field, (inner, outer) in fields.items():
                ev = ea.get(section, {}).get(field)
                av = get(located, inner) if isinstance(located, dict) else None
                if av is None and outer:
                    av = get(ga, outer)
                if field.endswith("included_event_keys"):
                    stat_checks.append(translate_keys(av, gkeys) == translate_keys(ev, ekeys)
                                       and translate_keys(ev, ekeys) is not None)
                elif field == "status":
                    # A derived statistic's state is a verdict in the controlled
                    # vocabulary, not a particular spelling of it
                    verdict_ok = quality(av) == quality(ev)
                    stat_checks.append(verdict_ok)
                    if section == "completeness":
                        completeness_verdict.append(verdict_ok)
                    elif section == "b_value":
                        bvalue_verdict.append(verdict_ok)
                elif isinstance(ev, (int, float)) and not isinstance(ev, bool):
                    stat_checks.append(equal(av, ev))
                else:
                    stat_checks.append(av == ev)
        # The memorandum's skeleton does not print an `evidence` object inside
        # the assessment at all, so it does not fix that nesting either: a
        # report that names the keys and rows its arithmetic ran on directly on
        # the assessment has stated the same evidence as one that files them
        # under a sub-object.
        gev = pluck(ga, ["evidence"])
        if not isinstance(gev, dict) or not gev:
            gev = ga
        eev = ea.get("evidence", {})
        # The memorandum allows additional evidence fields, so a field the
        # reference does not publish is not scored against a report that does.
        exp_primary = eev.get("primary")
        got_primary = pluck(gev, EVIDENCE_PRIMARY_NAMES, depth=1)
        if exp_primary is None:
            evidence_checks.append(True)
        else:
            # the pointer is compared as the row it names, resolved through the
            # inventory it belongs to, not as a mapping with particular key names
            evidence_checks.append(primary_row(got_primary, gdir, gkeys)
                                   == primary_row(exp_primary, edir, ekeys))
        exp_keys = eev.get("event_keys")
        evidence_checks.append(True if exp_keys is None else
                               (translate_keys(pluck(gev, EVIDENCE_KEY_NAMES), gkeys)
                                == translate_keys(exp_keys, ekeys)
                                and translate_keys(exp_keys, ekeys) is not None))
        exp_rows = eev.get("source_rows")
        evidence_checks.append(True if exp_rows is None else
                               (occurrence_set(pluck(gev, EVIDENCE_ROW_NAMES) or occurrences_of(gev), gdir, gkeys)
                                == occurrence_set(exp_rows, edir, ekeys)))

    detail["source_structure"] = fraction(source_checks)
    detail["event_normalization"] = fraction(event_checks)
    detail["sequence_statistics"] = fraction(stat_checks)
    detail["evidence_binding"] = fraction(evidence_checks)

    gd, ed = got.get("cross_feed_reconciliation", {}), exp.get("cross_feed_reconciliation", {})
    dup_checks = [
        (quality(get(gd, names)) == quality(ed.get(field))
         if field == "status" else equal(get(gd, names), ed.get(field)))
        for field, names in XFEED_FIELDS.items()
    ]

    GROUP_KEYS = ["event_key", "identity_key", "key", "representative_key", "group_key",
                  "canonical_key", "identity", "fingerprint"]
    def group_index(groups, directory, keymap):
        """Key a duplicate group by the rows it points at, not by the report's key.

        The memorandum does not fix the event-key recipe, so the group cannot be
        recognised by the string the report chose for it; it is recognised by the
        set of source rows it collects.
        """
        out = {}
        for g_ in groups if isinstance(groups, list) else []:
            if not isinstance(g_, dict):
                continue
            occ = occurrence_set(occurrences_of(g_), directory, keymap)
            if occ:
                key = occ
            else:
                ident = ident_of(keymap, pluck(g_, GROUP_KEYS, depth=1))
                key = ident if ident is not None else hashable(pluck(g_, GROUP_KEYS, depth=1))
            out.setdefault(key, g_)
        return out

    got_groups = pluck(gd, ["duplicate_groups", "groups", "identity_groups"])
    if not isinstance(got_groups, list):
        got_groups = collected_groups(gd)
    gdups = group_index(got_groups, gdir, all_gkeys)
    edups = group_index(ed.get("duplicate_groups", []), edir, all_ekeys)
    dup_checks.append(set(gdups) == set(edups))
    for key, item in edups.items():
        actual = gdups.get(key, {})
        actual_occurrences = occurrence_set(occurrences_of(actual), gdir, all_gkeys)
        dup_checks += [occurrence_set(occurrences_of(actual), gdir, all_gkeys)
                       == occurrence_set(item.get("occurrences"), edir, all_ekeys),
                       equal(get(actual, ["occurrence_count", "count"]), item.get("occurrence_count")),
                       bool(actual_occurrences)
                       and primary_row(pluck(actual, CANONICAL_NAMES), gdir, all_gkeys)
                       in actual_occurrences]
    detail["identity_reconciliation"] = fraction(dup_checks)

    gc, ec = got.get("comparative_audit", {}), exp.get("comparative_audit", {})
    comp_checks = [quality(get(gc, ["status"])) == quality(ec.get("status")),
                   get(gc, CLASS_COUNT_NAMES) == ec.get("class_counts")]
    gsigs = index_by_file(pluck(gc, ["signatures", "page_signatures", "page_summaries"]))
    if not gsigs:
        gsigs = collected_signatures(gc)
    esigs = by_file(ec.get("signatures", []))
    comp_checks.append(set(gsigs) == set(esigs))
    for name, item in esigs.items():
        actual = gsigs.get(name, {})
        for k in ("classification", "event_count", "valid_event_count"):
            comp_checks.append(equal(get(actual, [k] + SEQ_FIELDS.get(k, [])), item.get(k)))
        comp_checks.append(ident_of(all_gkeys, pluck(actual, ["primary_event_key"]))
                           == ident_of(all_ekeys, item.get("primary_event_key"))
                           and ident_of(all_ekeys, item.get("primary_event_key")) is not None)
    PAIR_FIELDS = {"same_classification": ["same_classification", "same_class", "same_disposition",
                                           "classification_matches", "shared_classification"],
                   "shared_primary_event": ["shared_primary_event", "shared_primary_identity",
                                            "shared_primary", "same_primary_event", "same_primary"]}

    def pair_key(item):
        """A pair is named by the two pages it compares, in either order."""
        names = pluck(item, ["files", "pair", "pages"], depth=1)
        if not isinstance(names, list):
            names = [item.get("left_file"), item.get("right_file")]
        return frozenset(Path(str(n)).name for n in names if n is not None and not isinstance(n, (dict, list)))

    gpairs = {}
    for x in (pluck(gc, ["pairwise", "pairs", "pairwise_comparisons"]) or []):
        if isinstance(x, dict):
            gpairs.setdefault(pair_key(x), x)
    for item in ec.get("pairwise", []):
        actual = gpairs.get(pair_key(item), {})
        comp_checks += [get(actual, names) == item.get(field) for field, names in PAIR_FIELDS.items()]
    detail["comparative_audit"] = fraction(comp_checks)

    ga, ea = got.get("aggregate", {}), exp.get("aggregate", {})
    def status_counts(counts):
        out = {}
        for key, value in (counts or {}).items():
            name = quality(key) or nkey(key)
            out[name] = out.get(name, 0) + (number(scalar(value)) or 0)
        return out

    aggregate_checks = []
    for field, names in AGG_FIELDS.items():
        actual, expected_value = get(ga, names), ea.get(field)
        if field == "record_status_counts":
            aggregate_checks.append(status_counts(actual) == status_counts(expected_value))
        elif field == "overall_status":
            aggregate_checks.append(quality(actual) == quality(expected_value))
        else:
            aggregate_checks.append(equal(actual, expected_value))

    # Reconcile the candidate's own roll-up with its detail rows before comparing
    # it with the reference.  Otherwise a stale copied summary can conceal a
    # contradictory event/status table and still receive full aggregate credit.
    candidate_records = list(grecs.values())
    candidate_events = [event for record in candidate_records for event in flatten_record(record)[0]]
    derived_classifications = {}
    derived_record_statuses = {}
    valid_events = 0
    for record in candidate_records:
        status = quality(get(record, ["status", "record_status"]))
        if status:
            derived_record_statuses[status] = derived_record_statuses.get(status, 0) + 1
        sequence = pluck(record, ["sequence_assessment", "sequence"]) or {}
        classification = get(sequence, SEQ_FIELDS["classification"])
        if classification is not None:
            key = nkey(classification)
            derived_classifications[key] = derived_classifications.get(key, 0) + 1
    for event in candidate_events:
        if quality(event.get("quality_status")) == "supported":
            valid_events += 1
    def normalize_counts(counts):
        out = {}
        for key, value in (counts or {}).items():
            name = quality(key) or nkey(key)
            out[name] = out.get(name, 0) + (number(scalar(value)) or 0)
        return out
    internal_checks = [
        number(get(ga, ["record_count", "records_count"])) == len(candidate_records),
        number(get(ga, ["source_event_count", "event_count", "events_count"])) == len(candidate_events),
        number(get(ga, ["valid_event_count", "usable_event_count", "supported_event_count"])) == valid_events,
        normalize_counts(get(ga, AGG_FIELDS["classification_counts"]) or {}) == derived_classifications,
        normalize_counts(get(ga, AGG_FIELDS["record_status_counts"]) or {}) == derived_record_statuses,
    ]
    detail["aggregate_internal_consistency"] = fraction(internal_checks)
    aggregate_checks.extend(internal_checks)
    detail["aggregate_closure"] = fraction(aggregate_checks)

    # ------------------------------------------------- the verdict layer (P09-P14)
    # Every verdict the reference states, each bound to the object that states it:
    # the aggregate's distribution of record verdicts, the three top-level verdicts,
    # each record's verdict, each normalized event's quality verdict, and the
    # completeness and b-value verdicts of each page's assessment. These leaves also
    # sit inside the dimensions above; the items name them separately so the rubric
    # can weight what the register *concludes* apart from the arithmetic under it.
    # Each is read through the controlled vocabulary, exactly as the section and
    # record statuses are -- the spelling of a quality flag is not scored.
    esc = ea.get("record_status_counts")
    gsc = get(ga, AGG_FIELDS["record_status_counts"])
    gsc = gsc if isinstance(gsc, dict) else {}
    # The distribution's keys are verdicts, so they are read through the same
    # controlled vocabulary as every other verdict in this layer: a register that
    # publishes {"complete_with_quality_flags": 3} has stated the reference's
    # {"supported": 3} together with its disclosure, and agrees with it.
    def by_verdict(counts):
        out = {}
        for key, value in counts.items():
            name = quality(key) or nkey(key)
            out[name] = out.get(name, 0) + (number(scalar(value)) or 0)
        return out
    detail["record_status_distribution"] = fraction(
        [equal(by_verdict(gsc).get(k), n) for k, n in by_verdict(esc).items()]
    ) if isinstance(esc, dict) else 1.0
    detail["published_verdicts"] = fraction([
        quality(get(ga, AGG_FIELDS["overall_status"])) == quality(ea.get("overall_status")),
        quality(get(got.get("comparative_audit", {}), ["status"]))
        == quality(exp.get("comparative_audit", {}).get("status")),
        quality(get(got.get("cross_feed_reconciliation", {}), XFEED_FIELDS["status"]))
        == quality(exp.get("cross_feed_reconciliation", {}).get("status")),
    ])
    detail["record_verdict"] = fraction(record_verdict)
    detail["event_verdict"] = fraction(event_verdict)
    detail["completeness_verdict"] = fraction(completeness_verdict)
    detail["b_value_verdict"] = fraction(bvalue_verdict)

    DIMENSIONS = ("manifest", "source_structure", "event_normalization", "sequence_statistics",
                  "identity_reconciliation", "evidence_binding", "comparative_audit", "aggregate_closure")

    # Screening gate. Applying `regional-screen-v1` is what the desk asked for, and the
    # disposition it produces is the report's conclusion. Inside the statistics bucket it
    # would be two equality checks out of roughly a hundred, so a report that files every
    # page under the wrong disposition would barely be marked down for it. It is a
    # separate measure, and it scales the rest.
    screen_checks = []
    for name, er in erecs.items():
        ga_ = pluck(grecs.get(name, {}), ["sequence_assessment", "sequence"]) or {}
        ea_ = er.get("sequence_assessment", {})
        screen_checks.append(get(ga_, SEQ_FIELDS["classification"]) == ea_.get("classification")
                             and get(ga_, SEQ_FIELDS["confidence"]) == ea_.get("confidence"))
    # The per-page dispositions on their own: "derive a sequence assessment for each page" and
    # "Apply it exactly as written". This remains a strict-only diagnostic.
    # `screening` below is these same checks plus the three bookkeeping checks.
    detail["screening_page_dispositions"] = fraction(screen_checks)
    screen_checks.append(got.get("rule_version") == exp.get("rule_version"))
    screen_checks.append(get(got.get("comparative_audit", {}), ["class_counts", "classification_counts"])
                         == exp.get("comparative_audit", {}).get("class_counts"))
    screen_checks.append(get(got.get("aggregate", {}), AGG_FIELDS["classification_counts"])
                         == exp.get("aggregate", {}).get("classification_counts"))
    screening = fraction(screen_checks)

    # Observation gate. "A second analyst can follow each value to a page row" fails if
    # the normalized magnitudes and coordinates are wrong, however well-formed the rest
    # of the register is. Each normalized event counts once, not once per field, so a
    # uniformly mis-scaled catalogue cannot be diluted by its correct metadata.
    obs_checks = []
    for pairs, _ in paired.values():
        for _, ee, ge in pairs:
            ok = all(equal(ge.get(f), ee.get(f)) for f in ("magnitude", "latitude", "longitude"))
            expected_ms = ee.get("time_ms")
            ok = ok and (equal_epoch(ge.get("time_ms"), expected_ms + offset)
                         if isinstance(expected_ms, float) and isinstance(ge.get("time_ms"), float)
                         else ge.get("time_ms") == expected_ms)
            obs_checks.append(ok)
    observation = fraction(obs_checks)

    # Status gate. The disposition of a page is not the register's only verdict:
    # calling every row usable, or every page supported, is also a conclusion a
    # reader acts on. Left inside the normalization bucket it is one check in
    # fourteen, so a report that mirrors every quality verdict while keeping the
    # arithmetic loses almost nothing. It is a separate measure, and it scales
    # the rest the same way the screening disposition does.
    # Only a verdict the report actually states in the controlled vocabulary is
    # measured: a field written under a name this scorer cannot read, or left
    # out, says nothing and costs nothing here. What is penalised is stating the
    # opposite of what the rows support.
    BINARY = {"supported", "unsupported"}
    status_pairs = []
    for name, er in erecs.items():
        gr = grecs.get(name, {})
        for _, ee, ge in paired[name][0]:
            status_pairs.append((ge.get("quality_status"), quality(ee.get("quality_status"))))
        status_pairs.append((quality(get(gr, ["status", "record_status"])), quality(er.get("status"))))
    status_pairs.append((quality(get(got.get("aggregate", {}), AGG_FIELDS["overall_status"])),
                         quality(exp.get("aggregate", {}).get("overall_status"))))
    status_pairs.append((quality(get(got.get("cross_feed_reconciliation", {}), XFEED_FIELDS["status"])),
                         quality(exp.get("cross_feed_reconciliation", {}).get("status"))))
    readable = [(g, e) for g, e in status_pairs if g in BINARY and e in BINARY]
    status_fidelity = 1.0 - (sum(1 for g, e in readable if g != e) / len(readable)) if readable else 1.0

    screening_gate = 0.2 + 0.8 * screening
    observation_gate = 0.2 + 0.8 * observation
    status_gate = 0.2 + 0.8 * status_fidelity
    detail["status_fidelity"] = status_fidelity
    detail["status_gate"] = status_gate
    detail["screening_disposition"] = screening
    detail["observation_fidelity"] = observation
    detail["screening_gate"] = screening_gate
    detail["observation_gate"] = observation_gate
    detail["epoch_offset_ms"] = offset

    # ------------------------------------------------------------- deductions
    # D03 and D04 charge affirmative errors -- a conclusion the register states
    # that the supplied rows do not support -- rather than credit it failed to
    # earn. Both are decided per page; the reference triggers neither.
    damage = []
    for name, er in erecs.items():
        gr = grecs.get(name, {})
        ga_ = pluck(gr, ["sequence_assessment", "sequence"]) or {}
        ea_ = er.get("sequence_assessment", {})
        # D03: the screening rule's own quantitative output, recomputed on a
        # different event set than the rule prescribes. `regional-screen-v1`
        # fixes the set: "Statistics, computed over the quality-supported events
        # of a page only", and "Apply it exactly as written; do not substitute
        # your own cut values". The reference finds every listed row on every
        # page quality-supported (`invalid_event_count` 0 on all three), so a
        # report that drops listed rows from a page's statistics -- or
        # miscomputes the slope -- states a b estimate the page does not
        # support. The margin is loose enough that publishing the same estimate
        # to six decimals is never charged; only a different estimate is.
        located = pluck(ga_, SECTION_ALIASES["b_value"])
        got_b = number(get(located, ["value", "b_estimate", "b"]) if isinstance(located, dict)
                       else get(ga_, ["b_estimate", "b_value"]))
        exp_b = number((ea_.get("b_value") or {}).get("value"))
        if got_b is not None and exp_b is not None and abs(got_b - exp_b) > 1e-3 * max(1.0, abs(exp_b)):
            damage.append((f"page:{name}:b_estimate_not_the_rule's", ["D03"]))
        # D04: a normalized value that is not on the row the report reads it
        # from. The memorandum asks the register to "expose unusable values
        # instead of silently repairing them", and the state policy keeps
        # "missing or contradictory supplied values" visible and unimputed. A
        # coordinate or magnitude that appears nowhere in the event's own cells
        # has been repaired or invented. Only events that publish their own
        # cells are examined, so a report that keeps its cells once, in the row
        # inventory, is never charged on a row it did not restate.
        for _, _, ge in paired[name][0]:
            cells = ge.get("raw_cells")
            if not isinstance(cells, list) or not cells:
                continue
            printed = {round(v, 6) for v in (number(c) for c in cells) if v is not None}
            stated = [number(ge.get(f)) for f in ("latitude", "longitude", "magnitude")]
            if any(v is not None and round(v, 6) not in printed for v in stated):
                damage.append((f"page:{name}:value_not_on_its_row", ["D04"]))
                break

    # pd-ledger-v1 parts.
    fold = screening_gate * observation_gate * status_gate
    # P01-P08 are the report dimensions in the order above; P09-P14 are the verdict
    # layer. Every completion is the item's fraction with the three gates folded in.
    LEDGER_ITEMS = list(DIMENSIONS) + ["record_status_distribution", "published_verdicts",
                                       "record_verdict", "event_verdict",
                                       "completeness_verdict", "b_value_verdict"]
    submitted_events = sum(len(flatten_record(r)[0]) for r in grecs.values())
    matched_events = sum(bool(ge) for pairs,_ in paired.values() for _,_,ge in pairs)
    precision = matched_events/submitted_events if submitted_events else 0.0
    detail["event_precision"] = {"matched":matched_events,"submitted":submitted_events,
        "unmatched_or_duplicate":submitted_events-matched_events,"fraction":precision}
    detail["_parts"] = {"completion": {"P%02d" % i: detail[k] * fold * precision for i, k in enumerate(LEDGER_ITEMS, 1)},
                        "damage": damage}
    return detail


def ident_of(mapping, value):
    """Resolve a report's own reference to an event into a row identity.

    The reference may be the bare key or an object that carries it.
    """
    if isinstance(value, dict):
        value = pluck(value, ["event_key", "key", "primary_event_key"], depth=1)
    if isinstance(value, (dict, list)) or value is None:
        return None
    return mapping.get(value)


def translate_keys(keys, mapping):
    """Turn a report's own event keys into row identities, so two reports that
    name events differently can still be compared on which events they mean."""
    if not isinstance(keys, list):
        return None
    out = []
    for k in keys:
        ident = mapping.get(k) if not isinstance(k, (dict, list)) else None
        if ident is None:
            return None
        out.append(ident)
    return frozenset(out)


# ---------------------------------------------------------------------------
# pd-ledger-v1 settlement.
PARAMS = Path(os.environ.get("SCORING_PARAMS", Path(__file__).resolve().parent / "scoring_params.json"))
DELIVERABLE = "seismic_catalogue_report.json"


def deliverable(arg: str) -> Path:
    """The contract passes a directory (rollout artifacts/ or task golden/); the container passes the file."""
    path = Path(arg)
    if not path.is_dir():
        return path
    named = path / DELIVERABLE
    if named.is_file():
        return named
    found = sorted(path.glob("**/" + DELIVERABLE))
    return found[0] if found else named


def settle(detail, parts):
    """Settle the scored items and damage instances as pd-ledger-v1."""
    params = json.loads(PARAMS.read_text(encoding="utf-8"))
    weights, coefficients = params["positive_weights"], params["deduction_coefficients"]
    completion = {k: round(min(1.0, max(0.0, float(parts["completion"].get(k, 0.0)))), 10) for k in weights}
    instances = [{"key": key, "item_ids": items} for key, items in parts["damage"]]
    earned = sum(weights[k] * completion[k] for k in weights)
    retention = math.prod(min(coefficients[i] for i in inst["item_ids"]) for inst in instances)
    final = earned * retention
    detail["rewards"] = {"strict":final}
    detail["reward_strict"] = detail["reward"] = final
    detail["reward_formulas"] = {"strict":"sum(weight * completion * screening * observation * status * event_precision) * retention"}
    detail["scoring_ledger"] = {"schema_version": "pd-ledger-v1", "positive_completion": completion,
                                "damage_instances": instances, "positive_earned": earned,
                                "retention": retention, "final_score": final}
    return detail


def lenient_value(got, detail, expected, source_integrity, damage):
    """Independent delivery check; never caps or rescales strict."""
    if not isinstance(got, dict) or got.get("schema_version") != "1.0" or not source_integrity:
        return 0.0
    if any("D0%d" % i in item_ids for _, item_ids in damage for i in range(1, 5)):
        return 0.0
    records = by_file(got.get("records", []))
    expected_records = by_file(expected.get("records", []))
    if set(records) != set(expected_records):
        return 0.0
    for record in records.values():
        sequence = pluck(record, ["sequence_assessment", "sequence"]) or {}
        completeness = pluck(sequence, ["completeness", "completeness_bin_detail", "magnitude_completeness"], depth=1)
        b_value = pluck(sequence, ["b_value", "b_estimate_detail", "b_estimate", "b"], depth=1)
        if not isinstance(completeness, dict) or quality(get(completeness, ["status"])) is None:
            return 0.0
        if not isinstance(b_value, dict) or quality(get(b_value, ["status", "state"])) is None:
            return 0.0
    if detail.get("source_structure", 0.0) < 1.0 or detail.get("aggregate_closure", 0.0) < 1.0:
        return 0.0
    return 1.0


def main():
    expected = json.loads((Path(__file__).resolve().parent / "ground_truth.json").read_text(encoding="utf-8"))
    candidates = [deliverable(sys.argv[1])] if len(sys.argv) > 1 else []
    candidates += [Path(os.environ[x]) for x in ("SEISMIC_CATALOGUE_OUTPUT", "SEISMIC_OUTPUT") if os.environ.get(x)]
    candidates += [Path("/workspace/output/seismic_catalogue_report.json"), Path("/root/workspace/output/seismic_catalogue_report.json")]
    def readable(p):
        try:
            return p.is_file()
        except OSError:                          # an unreadable default location is simply not the report
            return False
    out = next((p for p in candidates if readable(p)), None)
    try:
        got = json.loads(out.read_text(encoding="utf-8")) if out else {}
    except Exception:
        got = {}
    source_integrity = all(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == digest for name, digest in HASHES.items() for path in [MATERIALS / name])
    if not isinstance(got, dict):
        got = {}
    try:
        detail = score(got, expected)
    except Exception as exc:                     # a malformed report is a zero, not a crash
        detail = {"error": f"{type(exc).__name__}: {exc}"}
    detail["source_integrity"] = source_integrity
    parts = detail.pop("_parts", {"completion": {}, "damage": []})
    if not source_integrity:
        parts["damage"].append(("gate: catalogue HTML materials missing or sha256 differs", ["D01"]))
    if got.get("schema_version") != "1.0":
        parts["damage"].append(("gate: report schema_version is not \"1.0\" (or report missing/unparseable)", ["D02"]))
    detail = settle(detail, parts)
    lenient = lenient_value(got, detail, expected, source_integrity, parts["damage"])
    detail["rewards"]["lenient"] = lenient
    detail["reward_lenient"] = lenient
    value = detail["rewards"]["strict"]
    # Reward files are written for the container call (a file path); the contract call (a directory) and an
    # explicit log dir aside, nothing is written outside stdout.
    contract_call = len(sys.argv) > 1 and Path(sys.argv[1]).is_dir()
    if os.environ.get("SEISMIC_CATALOGUE_LOG_DIR") or not contract_call:
        log_dir = Path(os.environ.get("SEISMIC_CATALOGUE_LOG_DIR", os.environ.get("VERIFIER_OUTPUT_DIR", "/logs/verifier")))
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "reward.txt").write_text(f"{value:.6f}\n")
        (log_dir / "reward_strict.txt").write_text(f"{value:.6f}\n")
        (log_dir / "reward_lenient.txt").write_text(f"{lenient:.6f}\n")
        (log_dir / "reward.json").write_text(json.dumps(
            {"reward": value, "reward_strict": value, "reward_lenient": lenient}, indent=2) + "\n")
    print(json.dumps(detail, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
