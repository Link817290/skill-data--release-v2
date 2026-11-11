#!/usr/bin/env python3
"""Score an XLSX network recommendation against source-derived relations (pd-ledger-v1).

The strict score is ``positive_earned * retention``.  Each capability dimension is a positive item
P01..P08 whose completion is the dimension score (already discounted by the conclusion-reversal rate
on the dimensions that rate applies to) without a second global eligibility factor. Eligibility is local to P01.  The source-integrity gate (D01), the duplicate/conflict
gate (D02) and each recorded method violation (D03..D08, one item per violation, six rules checked)
fire as damage instances.  P08 (primary_service_identity) scores capacity-feasible eligible service against
the maximum service, accepting alternative optimal populations.
Weights and coefficients come from scoring_params.json (or $SCORING_PARAMS).

Invocation: ``validator.py <xlsx | directory> [--source ...] [--ground-truth ...]``; a directory (rollout
artifacts/ or task golden/) is searched for the deliverable, and the source workbook defaults to
/workspace/<SOURCE_NAME>, falling back to the task's environment/workspace copy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

# --- disowned-unit guard ---------------------------------------------------------------------------
# A unit the submission itself withdraws is not an assertion. The withdrawal must GOVERN THE WHOLE
# UNIT, so the cue is anchored at the start of the unit (after any bullet, quote or table marker) or
# is a quote-and-reject wrapper around it. An unanchored match would charge correct work: a sentence
# such as "it is expressly not asserted as structuring on the present record" is a careful, correct
# finding about a different allegation, not a withdrawal of the whole value. Domain words such as "rejected",
# "withdrawn", "superseded" or "hypothetical" are never cues: they describe the subject matter.
_DISOWN_LEAD = r"^[\s>|*\-–—•·\d.、)）\]】\"'“”‘’]{0,12}"
_DISOWN_RE = re.compile(
    _DISOWN_LEAD + r"(?:"
    r"the following is not asserted(?: here)?|not asserted here\b|"
    r"tentative,?\s*not adopted|not adopted\s*[:：]|unadopted\s*[:：]|"
    r"the draft (?:asserted|stated)\b|"
    r"candidate only\s*[:：]|filed as (?:a )?candidate\b|for discussion only\s*[:：]|"
    r"以下(?:内容)?(?:并非|不是)本方(?:主张|结论)|以下并非|以下不主张|"
    r"疑似(?=[^\n]{0,80}(?:尚未采纳|待核))|"
    r"原稿(?:主张|记载|曾称)|"
    r"并非(?=\S)|"
    r"暂定[，,：:]|候选[，,：:]|未采纳[，,：:]"
    r")", re.I)


def _guard_workbook(wb):
    """Blank every string cell the submission disowns; numbers, formulas and identifiers are untouched."""
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and _DISOWN_RE.search(cell.value):
                    cell.value = ""
    return wb



SOURCE_NAME = "Supply chain logisitcs problem.xlsx"
DELIVERABLE_NAME = "network_design_recommendation.xlsx"
HERE = Path(__file__).resolve().parent
PARAMS = Path(os.environ.get("SCORING_PARAMS", HERE / "scoring_params.json"))
# (item, capability dimension).
POSITIVE_ITEMS = (
    ("P01", "constraint_semantics"),
    ("P02", "exception_boundary"),
    ("P03", "facility_footprint"),
    ("P04", "allocation_economics"),
    ("P05", "workbook_lineage"),
    ("P06", "outage_screening"),
    ("P07", "governing_outage_recovery"),
    ("P08", "primary_service_identity"),
)
# One deduction item per recorded method violation; six rules are checked.
METHOD_STEP_ITEMS = ("D03", "D04", "D05", "D06", "D07", "D08")


def norm_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def compact(value: Any) -> str:
    return norm_text(value).replace(" ", "")


def norm_id(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).upper()
    if isinstance(value, (int, float)):
        text = format(Decimal(str(value)).normalize(), "f")
        return text.rstrip("0").rstrip(".") if "." in text else text
    text = str(value).strip()
    try:
        number = Decimal(text)
    except Exception:
        return text.upper()
    rendered = format(number.normalize(), "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("$", "").replace("%", "")
    if not text or text.startswith("="):
        return None
    try:
        result = float(text)
    except ValueError:
        return None
    return result if math.isfinite(result) else None


ALIASES = {
    "order_id": (
        "orderid", "ordernumber", "orderkey", "orderreference", "recordid", "shipmentid", "demandid", "order",
    ),
    "decision": (
        "decision", "decisionstate", "currentdaydecision", "assignmentstatus", "allocationstatus", "fulfillmentstatus",
        "fulfilmentstatus", "operatingstatus", "disposition", "servedstatus", "status", "action",
        "facilitystatus", "sitestatus", "plantstatus", "dcstatus", "warehousestatus",
    ),
    "facility": (
        "assignedfacility", "assignedplant", "assignedwarehouse", "selectedfacility",
        "selectedplant", "distributioncenter", "dccode", "facility", "warehouse", "plant",
        "selecteddc", "assigneddc",
    ),
    "origin": ("originport", "shipfromport", "shippingport", "port"),
    "carrier": ("carrier", "courier"),
    "mode": ("transportmode", "shippingmode", "mode"),
    "rate_row": ("ratesourcerow", "freightraterow", "tariffrow", "rateid", "routeid"),
    "rate_min": ("rateminimumweight", "minimumweight", "minweight", "weightfrom"),
    "rate_max": ("ratemaximumweight", "maximumweight", "maxweight", "weightto"),
    "minimum_charge": ("minimumcharge", "mincharge"),
    "rate": ("rateperkg", "freightrate", "unitrate", "rate"),
    "transit": ("transitdays", "transportdays", "tptdays", "tpt"),
    "reason": ("exceptionclass", "exceptionreason", "unservedreason", "reasoncode", "reason", "exception"),
    "assigned_count": ("assignedordercount", "assignedcount", "ordercount", "allocatedorders", "volume"),
    "capacity": ("dailycapacity", "capacity", "ordercapacity"),
    "warehouse_cost": ("warehousecost", "storagecost", "handlingcost", "facilitycost"),
    "freight_cost": ("companyfreightcost", "freightcost", "transportcost", "shipmentcost"),
    "total_cost": ("totalvariablecost", "variablecost", "totalcost", "overallvariablecost"),
    "scenario": ("scenario", "scenarioid", "case", "caseid", "plan", "planid"),
    "outaged_facility": (
        "outagedfacility", "unavailablefacility", "failedfacility", "facilityoutage",
        "outagefacility", "unavailablesite", "failedsite",
    ),
    "recoverable_service": (
        "maximumrecoverableorders", "maxrecoverableorders", "recoverableservice",
        "maximumservice", "maxservice", "recoveredorders", "assignedorders",
    ),
    "recovery_cost": (
        "minimumrecoveryvariablecost", "recoveryvariablecost", "minimumvariablecost",
        "outagevariablecost", "recoverycost",
    ),
    "governing": ("governingoutage", "governing", "controllingoutage", "worstoutage"),
    "structural_count": (
        "noremainingpathorders", "structuralunassignedorders", "structuralexceptions",
        "nopathorders", "lostpathorders", "structuralunassigned", "structuralunserved", "noremainingeligiblepath", "orderswithouteligiblepaths", "structuralexceptioncount",
    ),
    "capacity_count": (
        "remainingpathbutnocapacityorders", "capacityunassignedorders", "capacityexceptions",
        "capacitydisplacedorders", "capacityshortfallorders", "capacityunassigned", "capacityunserved", "capacityconstrainedorders", "eligiblebutunassigned", "capacityexceptioncount",
        "remainingpathnocapacity", "pathwithoutcapacity",
    ),
}


DIRECT_REFERENCE = re.compile(
    r"^=\s*(?:'((?:[^']|'')+)'|([^'!\s]+))!\$?([A-Z]{1,3})\$?(\d+)\s*$",
    re.IGNORECASE,
)


def resolve_internal_reference(wb, value: Any, depth: int = 0) -> Any:
    """Resolve an exact same-workbook cell reference without evaluating formulas."""
    if depth > 4 or not isinstance(value, str):
        return value
    match = DIRECT_REFERENCE.match(value)
    if not match:
        return value
    sheet_name = (match.group(1) or match.group(2) or "").replace("''", "'")
    if sheet_name not in wb.sheetnames:
        return value
    referenced = wb[sheet_name][f"{match.group(3).upper()}{match.group(4)}"].value
    return resolve_internal_reference(wb, referenced, depth + 1)


def sheet_values(wb, ws) -> list[tuple[Any, ...]]:
    """Rows of ``ws`` as the workbook's own computed values, falling back to formula text.

    The deliverable is opened with ``data_only=False`` because Golden is written by
    openpyxl and therefore carries no cached formula results: for Golden the only
    readable content of a formula cell is its text, which ``resolve_internal_reference``
    turns back into a value for a plain ``='Sheet'!A1`` reference.  A workbook that
    *does* carry cached results is read from them instead, so a decision the submission
    computes with a formula (``=IF(I2=0,"No current product capability",...)``) is
    scored on the value it computes rather than on the formula's source text.  Reading
    only the text would leave every computed decision unreadable, which is a property of
    how the submission was written, not of what it decided.

    The fallback is per cell: a cached result is used only where the file supplies one,
    so neither a submission nor Golden loses a value the file does supply.
    """
    raw_rows = list(ws.iter_rows(values_only=True))
    cached_book = getattr(wb, "_cached_value_book", None)
    if cached_book is None or ws.title not in cached_book.sheetnames:
        return raw_rows
    try:
        cached_rows = list(cached_book[ws.title].iter_rows(values_only=True))
    except Exception:
        return raw_rows
    merged: list[tuple[Any, ...]] = []
    for index, raw in enumerate(raw_rows):
        cached = cached_rows[index] if index < len(cached_rows) else ()
        if not cached:
            merged.append(raw)
            continue
        merged.append(tuple(
            cached[col] if col < len(cached) and cached[col] is not None else value
            for col, value in enumerate(raw)
        ))
    return merged


def header_key(value: Any) -> str | None:
    token = compact(value)
    if not token:
        return None
    for key, aliases in ALIASES.items():
        if token in aliases:
            return key
    for key, aliases in ALIASES.items():
        if any(len(alias) >= 7 and alias in token for alias in aliases):
            return key
    return None


def map_headers(values):
    """Resolve all exact headers before considering descriptive substring aliases."""
    mapping, used = {}, set()
    for col, value in enumerate(values):
        token = compact(value)
        keys = [key for key, aliases in ALIASES.items() if token and token in aliases]
        if len(keys) == 1 and keys[0] not in mapping:
            mapping[keys[0]] = col; used.add(col)
    candidates = []
    for col, value in enumerate(values):
        if col in used: continue
        token = compact(value)
        matches = [(len(alias), key) for key, aliases in ALIASES.items() if key not in mapping for alias in aliases if len(alias) >= 7 and alias in token and not (key == "decision" and re.search(r"evidence|rationale|description|comment|notes?|input|key", token))]
        if matches:
            best = max(n for n, _ in matches)
            keys = {key for n, key in matches if n == best}
            if len(keys) == 1: candidates.append((best, col, next(iter(keys))))
    for _, col, key in sorted(candidates, reverse=True):
        if key not in mapping and col not in used: mapping[key] = col; used.add(col)
    return mapping


def normalize_decision(value: Any) -> str | None:
    text = norm_text(value)
    if not text:
        return None
    compacted = text.replace(" ", "")
    if any(token in compacted for token in ("unassigned", "unserved", "notserved", "notallocated", "backlog", "exception", "infeasible", "hold")):
        return "UNASSIGNED"
    if compacted in {"no", "n", "0", "false"}:
        return "UNASSIGNED"
    if any(token in compacted for token in ("assigned", "served", "allocated", "fulfilled", "fulfil", "yes")):
        return "ASSIGNED"
    if compacted in {"use", "selected", "active", "open"}:
        return "ASSIGNED"
    return None


def normalize_facility_status(value: Any) -> str | None:
    text = norm_text(value).replace(" ", "")
    if not text:
        return None
    if any(token in text for token in ("close", "shutdown", "decommission")):
        return "CLOSE"
    if any(token in text for token in ("notused", "notselected", "inactive", "idle", "hold", "unavailable", "outage", "failed")):
        return "NOT_USED"
    if text in {"no", "n", "0", "false"}:
        return "NOT_USED"
    if any(token in text for token in ("use", "selected", "active", "retain", "operate", "open")):
        return "USE"
    return None


# A lost path is stated in whatever words the analyst uses. The instruction itself
# says "orders with no remaining current path"; Golden writes the same cause as
# "STRUCTURAL - NO ELIGIBLE PATH", and RUBRIC.md promises that "synonymous reason
# labels ... are normalized; causation and identifiers control".  Matching Golden's
# phrase as a substring recognised neither the instruction's own wording nor any of
# "No current path", "No remaining current path", "No current plant makes this
# product", "No matching current AIR route/rate" or "No product-qualified facility
# in customer VMI set" -- so registers that classify the 34 structural orders
# exactly right scored 0 for it.  The cause is read as a negation attached to the
# thing that is missing (a path, a lane, a tariff, an eligible plant), which is what
# distinguishes it from capacity displacement; free text that asserts no such
# absence ("Current path exists", "Served") still classifies as neither.
STRUCTURAL_ABSENCE = re.compile(
    r"\bno\b(?:\s+\w+){0,3}\s+"
    r"(?:paths?|routes?|lanes?|tariffs?|rates?|eligible|eligibility|plants?|facilit(?:y|ies)"
    r"|warehouses?|capabilit(?:y|ies)|products?|services?)\b"
)
STRUCTURAL_TOKENS = ("structural", "ineligible", "unsupported", "no eligible", "no valid",
                     "not eligible", "lost path", "lost eligibility", "lost route")


def reason_class(value: Any) -> str | None:
    text = norm_text(value)
    if not text:
        return None
    if any(token in text for token in STRUCTURAL_TOKENS) or STRUCTURAL_ABSENCE.search(text):
        return "STRUCTURAL"
    if any(token in text for token in ("capacity", "overflow", "displaced", "backlog", "shortfall", "constrained", "constraint")):
        return "CAPACITY"
    return None


def yes(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value) > 0.5
    text = norm_text(value).replace(" ", "")
    if text in {"yes", "y", "true", "selected", "governing", "controlling", "worst", "1"}:
        return True
    if text in {"no", "n", "false", "notselected", "0"}:
        return False
    return None


def read_sheet(path: Path, name: str) -> list[dict[str, Any]]:
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb[name]
    rows = ws.iter_rows(values_only=True)
    headers = [str(v).strip() if v is not None else "" for v in next(rows)]
    result = []
    for source_row, values in enumerate(rows, start=2):
        if not any(v is not None for v in values):
            continue
        record = {headers[i]: values[i] for i in range(min(len(headers), len(values))) if headers[i]}
        record["__source_row__"] = source_row
        result.append(record)
    wb.close()
    return result


def load_source(path: Path) -> dict[str, Any]:
    orders_raw = read_sheet(path, "OrderList")
    rates_raw = read_sheet(path, "FreightRates")
    costs_raw = read_sheet(path, "WhCosts")
    caps_raw = read_sheet(path, "WhCapacities")
    products_raw = read_sheet(path, "ProductsPerPlant")
    vmi_raw = read_sheet(path, "VmiCustomers")
    ports_raw = read_sheet(path, "PlantPorts")

    orders = {}
    for row in orders_raw:
        oid = norm_id(row["Order ID"])
        orders[oid] = {
            "order_id": oid,
            "customer": norm_id(row["Customer"]),
            "product": norm_id(row["Product ID"]),
            "service": str(row["Service Level"]).strip().upper(),
            "quantity": float(row["Unit quantity"]),
            "weight": float(row["Weight"]),
            "destination": str(row["Destination Port"]).strip().upper(),
        }
    capacities = {str(r["Plant ID"]).strip().upper(): int(r["Daily Capacity"]) for r in caps_raw}
    unit_costs = {str(r["WH"]).strip().upper(): float(r["Cost/unit"]) for r in costs_raw}
    facilities = sorted(set(capacities) & set(unit_costs))

    products: dict[str, set[str]] = defaultdict(set)
    for row in products_raw:
        facility = str(row["Plant Code"]).strip().upper()
        if facility in facilities:
            products[norm_id(row["Product ID"])].add(facility)
    ports: dict[str, set[str]] = defaultdict(set)
    for row in ports_raw:
        facility = str(row["Plant Code"]).strip().upper()
        if facility in facilities:
            ports[facility].add(str(row["Port"]).strip().upper())
    restrictions: dict[str, set[str]] = defaultdict(set)
    for row in vmi_raw:
        facility = str(row["Plant Code"]).strip().upper()
        if facility in facilities:
            restrictions[facility].add(norm_id(row["Customers"]))

    rates = []
    rates_index: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    rates_by_row = {}
    for row in rates_raw:
        if str(row["mode_dsc"]).strip().upper() != "AIR":
            continue
        item = {
            "source_row": int(row["__source_row__"]),
            "carrier": str(row["Carrier"]).strip().upper(),
            "origin": str(row["orig_port_cd"]).strip().upper(),
            "destination": str(row["dest_port_cd"]).strip().upper(),
            "minimum_weight": float(row["minm_wgh_qty"]),
            "maximum_weight": float(row["max_wgh_qty"]),
            "service": str(row["svc_cd"]).strip().upper(),
            "minimum_charge": float(row["minimum cost"]),
            "rate": float(row["rate"]),
            "transit_days": float(row["tpt_day_cnt"]),
        }
        rates.append(item)
        rates_index[(item["origin"], item["destination"], item["service"])].append(item)
        rates_by_row[item["source_row"]] = item

    return {
        "orders": orders,
        "facilities": facilities,
        "capacities": capacities,
        "unit_costs": unit_costs,
        "products": products,
        "ports": ports,
        "restrictions": restrictions,
        "rates": rates,
        "rates_index": rates_index,
        "rates_by_row": rates_by_row,
    }


def candidate_rates(source: dict[str, Any], order: dict[str, Any], facility: str) -> list[dict[str, Any]]:
    if order["service"] == "CRF":
        return []
    result = []
    for origin in source["ports"].get(facility, set()):
        for rate in source["rates_index"].get((origin, order["destination"], order["service"]), []):
            if rate["minimum_weight"] <= order["weight"] <= rate["maximum_weight"]:
                result.append(rate)
    return result


def eligible_facilities(source: dict[str, Any], order: dict[str, Any]) -> set[str]:
    eligible = set()
    for facility in source["products"].get(order["product"], set()):
        if facility in source["restrictions"] and order["customer"] not in source["restrictions"][facility]:
            continue
        if not source["ports"].get(facility):
            continue
        if order["service"] == "CRF" or candidate_rates(source, order, facility):
            eligible.add(facility)
    return eligible


@dataclass
class TableCandidate:
    sheet: str
    header_row: int
    mapping: dict[str, int]
    rows: list[dict[str, Any]]
    duplicate_ids: int
    listed_ids: frozenset = frozenset()


def infer_id_column(wb, rows: list[tuple[Any, ...]], header_index: int, order_ids: set[str], facility_ids: set[str], kind: str) -> int | None:
    target = order_ids if kind == "order" else facility_ids
    best_col = None
    best_hits = 0
    max_columns = max((len(row) for row in rows[: header_index + 81]), default=0)
    for col in range(max_columns):
        hits = 0
        for row in rows[header_index + 1 : header_index + 81]:
            if col < len(row) and norm_id(resolve_internal_reference(wb, row[col])) in target:
                hits += 1
        if hits > best_hits:
            best_col, best_hits = col, hits
    return best_col if best_hits >= 3 else None


def scan_order_tables(wb, order_ids: set[str], facility_ids: set[str]) -> list[TableCandidate]:
    candidates = []
    for ws in wb.worksheets:
        sheet_rows = sheet_values(wb, ws)
        for header_index, header_values in enumerate(sheet_rows[:40]):
            header_row = header_index + 1
            mapping = map_headers(header_values)
            if len(mapping) < 2:
                continue
            explicit_order_header = "order_id" in mapping
            if not explicit_order_header and not ({"decision", "reason"} & set(mapping)):
                continue
            if "order_id" not in mapping:
                inferred = infer_id_column(wb, sheet_rows, header_index, order_ids, facility_ids, "order")
                if inferred is not None:
                    mapping["order_id"] = inferred
            if "order_id" not in mapping:
                continue
            sheet_signal = any(token in norm_text(ws.title) for token in ("alloc", "assign", "order", "exception", "backlog", "unserved"))
            if "decision" not in mapping and "reason" not in mapping and not (sheet_signal and "facility" in mapping):
                continue
            parsed = []
            seen = Counter()
            listed = set()
            for row_index, values in enumerate(sheet_rows[header_index + 1 :], start=header_row + 1):
                oid = norm_id(resolve_internal_reference(wb, values[mapping["order_id"]])) if mapping["order_id"] < len(values) else ""
                if oid not in order_ids:
                    continue
                listed.add(oid)
                facility = norm_id(resolve_internal_reference(wb, values[mapping["facility"]])) if "facility" in mapping and mapping["facility"] < len(values) else ""
                decision = normalize_decision(resolve_internal_reference(wb, values[mapping["decision"]])) if "decision" in mapping and mapping["decision"] < len(values) else None
                reason_value = resolve_internal_reference(wb, values[mapping["reason"]]) if "reason" in mapping and mapping["reason"] < len(values) else None
                if decision is None:
                    # With no decision column, a stated exception cause settles the row
                    # and outranks a facility annotation: an exception register that
                    # records the facility an order would have used, beside the cause
                    # that stopped it, would otherwise read as thousands of claimed
                    # assignments contradicting the workbook's own allocation sheet,
                    # and that manufactured contradiction would fire the
                    # duplicate/conflict gate.  Only a cell that states a cause
                    # declares the order unassigned; treating any non-empty cell as
                    # one would read a per-order eligibility register whose column
                    # says "Current path exists" as thousands of unassigned orders,
                    # and a recovery register marking served rows "Served" as
                    # unassigned too.
                    # Where the table does carry a decision column, a row whose
                    # decision cell does not read as one still falls back to the
                    # facility: that column is the table's own answer rather than an
                    # annotation, and reading the cause first would empty an
                    # allocation sheet that states a cause beside every row.
                    if "decision" not in mapping and reason_class(reason_value) is not None:
                        decision = "UNASSIGNED"
                    elif facility in facility_ids:
                        decision = "ASSIGNED"
                    elif reason_class(reason_value) is not None:
                        decision = "UNASSIGNED"
                if decision is None:
                    continue
                record = {"order_id": oid, "facility": facility if facility in facility_ids else facility, "decision": decision, "row": row_index, "sheet": ws.title}
                for key, col in mapping.items():
                    if col < len(values):
                        record[key] = resolve_internal_reference(wb, values[col])
                record["order_id"] = oid
                record["facility"] = facility
                record["decision"] = decision
                record["reason_class"] = reason_class(reason_value)
                parsed.append(record)
                seen[oid] += 1
            if len(seen) >= 3:
                candidates.append(TableCandidate(ws.title, header_row, mapping, parsed, sum(v - 1 for v in seen.values() if v > 1), frozenset(listed)))
    return candidates


def scan_facility_tables(wb, facility_ids: set[str], order_ids: set[str]) -> list[TableCandidate]:
    candidates = []
    for ws in wb.worksheets:
        sheet_rows = sheet_values(wb, ws)
        for header_index, header_values in enumerate(sheet_rows[:40]):
            header_row = header_index + 1
            mapping = map_headers(header_values)
            if len(mapping) < 2:
                continue
            if not ({"decision", "assigned_count"} & set(mapping)):
                continue
            if "order_id" in mapping:
                continue
            if "facility" not in mapping:
                inferred = infer_id_column(wb, sheet_rows, header_index, order_ids, facility_ids, "facility")
                if inferred is not None:
                    mapping["facility"] = inferred
            if "facility" not in mapping or not ({"decision", "capacity", "assigned_count"} & set(mapping)):
                continue
            rows = []
            seen = Counter()
            for row_index, values in enumerate(sheet_rows[header_index + 1 :], start=header_row + 1):
                facility = norm_id(resolve_internal_reference(wb, values[mapping["facility"]])) if mapping["facility"] < len(values) else ""
                if facility not in facility_ids:
                    continue
                record = {"facility": facility, "row": row_index, "sheet": ws.title}
                for key, col in mapping.items():
                    if col < len(values):
                        record[key] = resolve_internal_reference(wb, values[col])
                record["facility"] = facility
                rows.append(record)
                seen[facility] += 1
            if len(seen) >= 2:
                candidates.append(TableCandidate(ws.title, header_row, mapping, rows, sum(v - 1 for v in seen.values() if v > 1)))
    return candidates


def outage_signal(sheet: str, mapping: dict[str, int], row: dict[str, Any] | None = None) -> bool:
    text = norm_text(sheet)
    if any(token in text for token in ("outage", "recovery", "contingency", "disruption", "failed facility")):
        return True
    if "outaged_facility" in mapping:
        # The column marks which event a row belongs to; a row that names no failed
        # facility belongs to the base plan.  Treating the column's mere presence as
        # the signal discarded a whole primary allocation whose "Failed facility"
        # column was blank on all 9,215 of its rows.
        if row is None:
            return True
        if norm_id(row.get("outaged_facility")):
            return True
    if row:
        scenario = norm_text(row.get("scenario"))
        return any(token in scenario for token in ("outage", "recovery", "contingency", "disruption"))
    return False


def split_order_tables(tables: list[TableCandidate]) -> tuple[list[TableCandidate], list[TableCandidate]]:
    primary_tables, recovery_tables = [], []
    for table in tables:
        primary_rows, recovery_rows = [], []
        for row in table.rows:
            (recovery_rows if outage_signal(table.sheet, table.mapping, row) else primary_rows).append(row)
        if primary_rows:
            primary_tables.append(TableCandidate(table.sheet, table.header_row, table.mapping, primary_rows, table.duplicate_ids))
        if recovery_rows:
            recovery_tables.append(TableCandidate(table.sheet, table.header_row, table.mapping, recovery_rows, table.duplicate_ids))
    return primary_tables, recovery_tables


def collect_records(tables: list[TableCandidate]) -> tuple[TableCandidate | None, dict[str, dict[str, Any]], int, int]:
    # The decision register carries one row per order; a table that repeats an order
    # is an enumeration of its candidates, which is what "duplicate or conflicting
    # primary order decisions" already names as the thing a register must not be.
    # Ranking on size alone let a 16,245-row (order, eligible facility) pair list beat
    # the 9,215-row allocation beside it and read every candidate pair as a claimed
    # assignment.  Coverage still decides between registers.
    primary = max(tables, key=lambda item: (item.duplicate_ids == 0, len({row["order_id"] for row in item.rows})),
                  default=None)
    records: dict[str, dict[str, Any]] = {}
    conflicts = 0
    duplicate_rows = primary.duplicate_ids if primary else 0
    # Conflicts are counted between decision registers only, for the same reason the
    # register is chosen among them: a table that lists every eligible facility for an
    # order disagrees with the allocation by construction, and charging that
    # disagreement to the workbook charged one that reproduces the reference
    # allocation exactly. Rows from an enumeration still fill in orders no register
    # covers; they just cannot manufacture a contradiction.
    ordered = ([primary] if primary else []) + [table for table in tables if table is not primary]
    for table in ordered:
        registers = table.duplicate_ids == 0
        for row in table.rows:
            oid = row["order_id"]
            if oid not in records:
                records[oid] = row
            elif registers and decision_signature(records[oid]) != decision_signature(row):
                conflicts += 1
    return primary, records, duplicate_rows, conflicts


def choose_facility_table(tables: list[TableCandidate], recovery: bool) -> TableCandidate | None:
    matching = [
        table for table in tables
        if outage_signal(table.sheet, table.mapping, table.rows[0] if table.rows else None) == recovery
    ]
    return max(matching, key=lambda item: len({row["facility"] for row in item.rows}), default=None)


# ----------------------------------------------------------------------------
# Declared decision values and recorded method
#
# The workbook's summary and notes sheets carry the decision in plain words and
# in two literal values: which facility is the governing outage, and how many
# orders remain recoverable under it. Both are read, so a workbook that names the
# wrong governing facility in its Executive Summary, reports a recoverable count
# 250 orders off, or states a rule in the Model Notes backwards is charged for it
# however correct its detail tables are.
#
# The notes are checked for *affirmatively wrong* statements only. A rule that is
# reworded, abbreviated or simply absent is not counted; only a statement that
# asserts the opposite of a rule the brief fixes is.
# ----------------------------------------------------------------------------

# "the governing outage has the HIGHEST recoverable service" -- the brief fixes
# the governing outage as the one with the *lowest* recoverable service.
# Only evaluated on a cell that actually states the governing-outage rule, so
# that the *recovery* objective ("recoverable service is maximized before
# recovery variable cost is minimized") -- a different and correct rule -- is
# not mistaken for it.
GOVERNING_RULE_REVERSED = (
    r"governing[\s-]*outage\b[^.;]{0,120}?\b(?:highest|greatest|largest|maximum|most|higher|greater|maximal)\b(?:\W+\w+){0,3}\W+recoverable\b",
    # tie-break stated the wrong way round: a *lower* variable cost breaking a tie
    r"\b(?:lower|lowest|least|smaller|smallest|minimal)\b(?:\W+\w+){0,1}\W+variable cost\b(?:\W+\w+){0,4}\W+break",
)
# "First MINIMIZE the number of facilities ..." -- the brief fixes maximum
# service first, footprint second, cost third.
OBJECTIVE_REVERSED = (
    r"\bfirst\W+minimi[sz]\w*\b(?:\W+\w+){0,9}\W+(?:facilit|cost)",
    r"\b(?:assignments?|service|orders?)\b(?:\W+\w+){0,4}\W+(?:is|are)\W+not\W+maximi[sz]ed",
    r"\bnot\W+maximi[sz]ed\W+first\b",
    r"\bplan is comparable\b(?:\W+\w+){0,3}\W+drops\b",
)
# The brief: "Do not describe lost eligibility as a capacity requirement."
# The gap must not contain a negation: "no current path is structural lost
# eligibility, NOT a capacity requirement" and "lost eligibility is reported as a
# structural exception, NEVER as a capacity requirement" are the brief's rule stated
# correctly, and both were charged as its reversal. [FPN-05]
_NOT_NEGATED_GAP = r"(?:\W+(?!(?:no|not|never|nor|neither|without|rather|instead|excluding)\b)\w+)"
EXCEPTION_SPLIT_REVERSED = (
    r"\bstructural\b" + _NOT_NEGATED_GAP + r"{0,8}\W+capacity\W+(?:requirement|constraint|need|shortfall)",
    r"\b(?:no eligible|lost eligibilit|ineligib\w+)\b" + _NOT_NEGATED_GAP + r"{0,8}\W+capacity\W+(?:requirement|constraint|need)",
    r"\bstructural\b(?:\W+\w+){0,6}\W+(?:have|has|with)\W+(?:an|at least one|a)\W+eligible",
    r"\bcapacity[- ]displaced\b(?:\W+\w+){0,6}\W+(?:no|without|lacks?)\W+eligible",
)
# The brief: "Keep the source workbook read-only."
SOURCE_MUTABLE_CLAIM = (
    r"\b(?:editable|writable|rewritten in place|edited in place|modified in place)\b",
    r"\bsource\b(?:\W+\w+){0,4}\W+(?:was|were|is|are)\W+(?:edited|modified|updated|overwritten)\b",
)
# The brief: "Do not invent capacity, routes, rates, or service for unsupported orders."
INVENTION_ALLOWED_CLAIM = (
    r"\b(?:may|can|are allowed to|is permitted to|will)\b(?:\W+\w+){0,4}\W+(?:receive|be given|be assigned)\b(?:\W+\w+){0,3}\W+invented",
    r"\binvent\w*\b(?:\W+\w+){0,4}\W+(?:capacity|routes?|rates?|service)\b(?:\W+\w+){0,4}\W+(?:is|are)\W+(?:permitted|allowed|acceptable)",
)
# The brief: the customer-restriction relation has a fixed direction.
RELATION_REVERSIBLE_CLAIM = (
    r"\bdirection of the relation\b(?:\W+\w+){0,4}\W+(?:may|can|should)\W+be\W+reversed",
    r"\b(?:may|can)\W+reverse\W+the\W+direction\W+of\W+the\W+relation\b",
)
METHOD_RULES = (
    ("governing_outage_rule", GOVERNING_RULE_REVERSED),
    ("objective_hierarchy", OBJECTIVE_REVERSED),
    ("exception_split", EXCEPTION_SPLIT_REVERSED),
    ("source_read_only", SOURCE_MUTABLE_CLAIM),
    ("no_invented_supply", INVENTION_ALLOWED_CLAIM),
    ("restriction_direction", RELATION_REVERSIBLE_CLAIM),
)

# ----------------------------------------------------------------------------
# Direction-family reading of the same rules.
#
# The literal patterns above are a list of *phrasings*, so a reversal written in
# other words slips past them: a workbook can state every recorded rule backwards
# in fresh wording and match none of them.
#
# These checks instead read a rule as (scope, quantity, direction). The scope and
# the quantity are open synonym sets, but the *direction* is drawn from the closed
# class of English comparatives and from negation, so a rewrite that keeps the
# meaning keeps the direction and a rewrite that inverts the meaning inverts it.
# Each check fires only on an affirmatively opposite reading; a cell that is
# silent, hedged, or ambiguous (both directions attached to the same quantity)
# is left alone.
# ----------------------------------------------------------------------------

# Size/quantity comparatives only. Price comparatives (cheaper, costlier) are
# deliberately excluded: they attach to the cost tie-break, not to service volume.
_MORE = (r"highest|greatest|largest|maximum|maximal|most|more|greater|higher|larger|bigger|"
         r"biggest|top|peak|maximi[sz]\w*|increas\w*|raise[ds]?|rais\w*|push\w*\s+up|driven\s+up|"
         r"as\s+many\s+(?:\w+\s+){0,2}as\s+possible")
_LESS = (r"lowest|least|smallest|minimum|minimal|fewest|fewer|less|lower|smaller|"
         r"bottom|minimi[sz]\w*|reduc\w*|shrink\w*|shrunk|cut|curtail\w*|driven\s+down|"
         r"drive[ns]?\s+down|as\s+few\s+(?:\w+\s+){0,2}as\s+possible")
_MORE_RE = re.compile(r"\b(?:%s)\b" % _MORE)
_LESS_RE = re.compile(r"\b(?:%s)\b" % _LESS)

# Words for "service that survives the outage". "recovery" on its own is left out:
# it names the scenario, not the quantity, and appears in rows that state no rule.
_RECOVERABLE_RE = re.compile(
    r"\b(?:recoverable|recovered|serviceable|salvageable|restorable|"
    r"retained\s+service|service\s+retained|still\s+serv\w+|orders\s+still\s+\w+)\b")
_GOVERNING_RE = re.compile(r"\bgovern(?:s|ed|ing|ance)?\b|\b(?:binding|controlling|decisive)\s+outage\b")

# Loss verbs count as negation here: "structural lost eligibility" denies eligibility
# as plainly as "structural has no eligible path"; reading it as the claim that a
# structural exception still has one would charge an accurate workbook for restating
# the brief's own rule.
_NEGATOR_RE = re.compile(
    r"\b(?:no|not|never|none|nor|without|lack|lacks|lacking|lacked|zero|"
    r"cannot|can't|fails?\s+to|failing\s+to|absent|devoid|short\s+of|"
    r"ineligib\w*|unqualified|unsupported|denied|"
    r"lost|loses|losing|loss|forfeit\w*|removed|stripped|withdrawn|expired)\b")
_ELIGIBILITY_RE = re.compile(
    r"\b(?:eligib\w*|qualif\w*|permitted\s+facilit\w*|supported\s+facilit\w*|"
    r"allowed\s+facilit\w*|available\s+facilit\w*)\b")

_PRIMACY_CUE_RE = re.compile(r"^(?:first|firstly|begin(?:s)?\s+by|begin(?:s)?\s+with|"
                             r"start(?:s)?\s+by|start(?:s)?\s+with|step\s*1|initially|"
                             r"the\s+first\s+step)\b")
_SERVICE_NOUN_RE = re.compile(r"\b(?:assignment\w*|order\w*|service\w*|coverage|demand)\b")
_FOOTPRINT_NOUN_RE = re.compile(r"\b(?:facilit\w*|site\w*|plant\w*|footprint|node\w*|"
                                r"centre\w*|center\w*|warehouse\w*|depot\w*|dcs?)\b")
_COST_NOUN_RE = re.compile(r"\b(?:cost\w*|spend\w*|expense\w*|freight|outlay|price\w*)\b")

_MUTABLE_RE = re.compile(
    r"\b(?:editable|writable|modifiable|amendable|mutable|rewritable|"
    r"open\s+for\s+(?:amendment\w*|edit\w*|revision\w*|change\w*|update\w*)|"
    r"(?:may|can|could|will|shall)\s+be\s+(?:edited|amended|changed|rewritten|"
    r"overwritten|updated|modified|replaced)|"
    r"rewritten\s+(?:whenever|as|when|in\s+place)|edited\s+in\s+place|modified\s+in\s+place|"
    r"no\s+longer\s+read[-\s]?only|not\s+read[-\s]?only)\b")

_EITHER_CLASS_RE = re.compile(
    r"\b(?:either|any|both|each)\s+(?:class|category|kind|type)(?:es|s)?\b[^.;]{0,90}?"
    r"\b(?:may|can|could|is\s+permitted|are\s+permitted|is\s+allowed|are\s+allowed|will)\b")
_INVENTED_SUPPLY_RE = re.compile(
    r"\b(?:invent\w*|fabricat\w*|assum\w*|made[-\s]up|"
    r"(?:the\s+)?source\s+(?:never|does\s+not|do\s+not|doesn't|don't)\s+record\w*|"
    r"not\s+recorded\s+in\s+the\s+source|unsupported)\b")

_RELATION_SYMMETRIC_RE = re.compile(
    r"\brelation\w*\b[^.;]{0,120}?\b(?:equally\s+well|either\s+direction|both\s+directions|"
    r"other\s+way\s+(?:round|around)|reversibl\w+|interchangeabl\w+|symmetric\w*|"
    r"in\s+reverse|the\s+reverse\s+direction)\b")
_PROHIBITION_RE = re.compile(
    r"\b(?:do\s+not|does\s+not|must\s+not|may\s+not|cannot|can\s+not|never|"
    r"no\s+other|not\s+be\s+reversed|is\s+not|are\s+not|only)\b")


# "maximum recoverable service" and "minimum variable cost" are the brief's own names
# for the reported quantities ("report maximum recoverable service, minimum variable
# cost"), while the rule it fixes is stated separately ("the one with the lowest
# recoverable service"). A max/min sitting directly on the quantity is therefore part
# of its name, not the direction of a rule, and is not read as one: taken as a
# direction it would charge "lowest maximum recoverable orders, then higher minimum
# variable cost" -- the rule stated exactly right -- and even the bare column heading
# "maximum recoverable service under the governing outage". Other comparatives
# (highest, greatest, most, lowest, fewest) do carry direction, and the literal
# GOVERNING_RULE_REVERSED patterns require "governing outage" before the comparative.
_ATTRIBUTIVE_QUANTITY_RE = re.compile(r"\b(?:maximum|minimum|max|min|maximal|minimal)\b")


def _direction_near(cell: str, target: re.Pattern, window: int = 80) -> str | None:
    """Whether "more" or "less" is attached to the quantity `target` names.

    The comparative nearest to the quantity wins. A tie, or no comparative inside
    the window, reads as "no direction stated" and is never a violation."""
    best: tuple[int, str] | None = None
    for hit in target.finditer(cell):
        centre = (hit.start() + hit.end()) // 2
        for kind, pattern in (("more", _MORE_RE), ("less", _LESS_RE)):
            for other in pattern.finditer(cell):
                if _ATTRIBUTIVE_QUANTITY_RE.fullmatch(other.group(0)) and \
                        0 <= hit.start() - other.end() <= 2:
                    continue
                distance = abs((other.start() + other.end()) // 2 - centre)
                if distance > window:
                    continue
                if best is None or distance < best[0]:
                    best = (distance, kind)
                elif distance == best[0] and best[1] != kind:
                    best = (distance, "ambiguous")
    if best is None or best[1] == "ambiguous":
        return None
    return best[1]


# ORDERING_REVERSAL_NOT_DETECTED
#
# A reordering of the objective hierarchy that leaves every comparative's polarity
# intact -- "variable cost is minimized to open the ranking; the number of
# facilities with positive flow is minimized next; the count of valid assignments
# is maximized only once those two are settled" -- is not detected. Every clause
# in it reads exactly as the brief states it; only the precedence between clauses
# is reversed, and precedence is not carried by the closed comparative class the
# checks above rely on.
#
# Precedence is not read off the surface order of the objective clauses either.
# English subordinates as often as it sequences: the brief's own phrasing, "the
# smallest current-day distribution-center footprint that preserves the maximum
# service", names footprint before service while ranking service first, so a
# surface-order reading registers a violation against a workbook that states the
# rule correctly in that same relative-clause shape. Requiring an explicit
# sequencing marker between the clauses instead only returns the check to a list
# of phrasings.


def direction_violations(cells: list[str]) -> list[str]:
    """Recorded rules whose stated direction is the opposite of the brief's."""
    found: set[str] = set()
    for cell in cells:
        # "Identify the governing outage as the one with the LOWEST recoverable service."
        if _GOVERNING_RE.search(cell) and _RECOVERABLE_RE.search(cell):
            if _direction_near(cell, _RECOVERABLE_RE) == "more":
                found.add("governing_outage_rule")
        # "First maximize valid assignments, then minimize the number of facilities."
        # Only a cell that opens by naming what comes first is read as a ranking.
        # Precedence is not read off the surface order of the objective clauses:
        # English subordinates as often as it sequences, so "the smallest footprint
        # that preserves the maximum service" -- the brief's own wording for the
        # correct rule -- names footprint first while ranking service first.
        # See ORDERING_REVERSAL_NOT_DETECTED below.
        cue = _PRIMACY_CUE_RE.search(cell)
        if cue and (_MORE_RE.search(cell) or _LESS_RE.search(cell)):
            # A line that names no optimisation states no objective ranking. Without
            # this, the workbook-audit row "first key plant01; last key plant19;
            # formulas 285; cross-sheet 171; exceptions 0" would read as "minimise
            # the facility count first".
            tail = cell[cue.end():cue.end() + 90]
            positions = []
            for label, pattern in (("service", _SERVICE_NOUN_RE),
                                   ("footprint", _FOOTPRINT_NOUN_RE),
                                   ("cost", _COST_NOUN_RE)):
                hit = pattern.search(tail)
                if hit:
                    positions.append((hit.start(), label))
            if positions and min(positions)[1] != "service":
                found.add("objective_hierarchy")
        # "Structural exceptions have NO eligible facility path before capacity."
        anchor = re.search(r"\bstructural\b", cell)
        if anchor:
            noun = _ELIGIBILITY_RE.search(cell, anchor.end())
            if noun and noun.start() - anchor.end() <= 90:
                span = cell[anchor.start():noun.end()]
                if not _NEGATOR_RE.search(span):
                    found.add("exception_split")
        # "Keep the source workbook read-only."
        if _MUTABLE_RE.search(cell):
            found.add("source_read_only")
        # "Do not invent capacity, routes, rates, or service for unsupported orders."
        if _EITHER_CLASS_RE.search(cell) and _INVENTED_SUPPLY_RE.search(cell):
            found.add("no_invented_supply")
        # "Do not reverse the direction of the relation."
        if _RELATION_SYMMETRIC_RE.search(cell) and not _PROHIBITION_RE.search(cell):
            found.add("restriction_direction")
    return sorted(found)


def narrative_cells(wb) -> list[str]:
    """Prose cells from the workbook's summary / notes / audit sheets.

    Detail tables are excluded: their cells are decisions, not statements of
    method, and are scored row by row elsewhere. Each cell is kept separate so a
    rule can never be matched across two unrelated cells of the same row (a
    column-header row would otherwise read as one sentence). Cells shorter than
    30 characters are column headings and short labels, not method statements."""
    cells: list[str] = []
    for ws in wb.worksheets:
        if ws.max_row > 60:
            continue
        for row in ws.iter_rows(values_only=True):
            for value in row:
                if isinstance(value, str) and not value.startswith("=") and len(value.strip()) >= 30:
                    cells.append(re.sub(r"\s+", " ", value).strip().lower())
    return cells


# The brief: "`CRF` remains customer-arranged with no company freight cost".
CRF_FREIGHT_CHARGED = (
    re.compile(r"\bcrf\b[^.;]{0,60}\b(?:company|air)\b[^.;]{0,20}\bfreight\b[^.;]{0,30}"
               r"\b(?:charged|applied|paid|incurred|billed|borne|added|included)\b"),
    re.compile(r"\b(?:company|air)\b[^.;]{0,20}\bfreight\b[^.;]{0,30}"
               r"\b(?:charged|applied|billed|added)\b[^.;]{0,20}\b(?:to|on|for)\b[^.;]{0,30}\bcrf\b"),
    re.compile(r"\bcrf\b[^.;]{0,40}\b(?:charged|billed|pays?|bears?|incurs?)\b[^.;]{0,30}"
               r"\b(?:company|air)\b[^.;]{0,20}\bfreight\b"),
)
# The brief: "use only materials under /workspace, do not use the internet or rely on
# information not supplied there".
OUTSIDE_SOURCE = re.compile(
    r"(?:\b(?:used?|using|rel(?:y|ied|iance)|depend(?:s|ed|ence)?|obtained?|sourced?|"
    r"downloaded?|looked?\s+up|taken?)\b[^.;]{0,50}\b(?:internet|online|web ?sites?|"
    r"public (?:carrier )?tariffs?|external (?:data|sources?|benchmarks?|rates?|tariffs?))\b|"
    r"\b(?:internet|online|web ?sites?|public (?:carrier )?tariffs?|"
    r"external (?:data|sources?|benchmarks?|rates?|tariffs?))\b[^.;]{0,30}"
    r"\b(?:was|were|is|are)?\s*(?:used|relied|consulted|obtained|downloaded|sourced)\b)")
LOCAL_SOURCE_ONLY = re.compile(
    r"\b(?:independent(?:ly)?\s+of|without|no|not)\b[^.;]{0,35}\bexternal\b|"
    r"\bexclusively\b[^.;]{0,45}\b(?:supplied|provided|workspace)\b")
_PROSE_NEGATOR_RE = re.compile(r"\b(?:no|not|never|none|nor|without|zero|excluded|excludes|n/a)\b")
# Fraction of the order population, and of the used facilities, below which a
# register is incomplete rather than annotated differently.
COMPLETENESS_FLOOR = 0.9


def crf_freight_claims(cells: list[str]) -> list[str]:
    """Cells stating that company freight is charged to CRF orders, unless the statement negates it."""
    hits = []
    for cell in cells:
        for pattern in CRF_FREIGHT_CHARGED:
            match = pattern.search(cell)
            if match and not _PROSE_NEGATOR_RE.search(match.group(0)):
                hits.append(cell)
                break
    return hits


def outside_source_claims(cells: list[str]) -> list[str]:
    """Cells affirmatively stating reliance on an outside source."""
    return [cell for cell in cells if OUTSIDE_SOURCE.search(cell) and not LOCAL_SOURCE_ONLY.search(cell)]


def formula_has_dependency(value: Any) -> bool:
    """A live formula must depend on a cell/range; constants are decoration."""
    return bool(isinstance(value, str) and value.startswith("=")
                and not re.search(r"(?:^|[^\d.])0(?:\.0+)?\s*\*|\*\s*0(?:\.0+)?(?:[^\d.]|$)", value)
                and re.search(r"(?:'[^']+'|[A-Za-z_][\w .-]*)?!?\$?[A-Z]{1,3}\$?\d+", value))


def count_formula_matches_detail(formula: Any, table: TableCandidate | None, facility_row: dict[str, Any]) -> bool:
    if not formula_has_dependency(formula) or table is None or "facility" not in table.mapping:
        return False
    text = str(formula).upper().replace("$", "")
    facility_col = get_column_letter(table.mapping["facility"] + 1)
    facility_cell = f"{get_column_letter(facility_row['_facility_col'])}{facility_row['row']}"
    sheet = re.escape(table.sheet.upper().replace("'", "''"))
    column = re.escape(facility_col)
    criterion = re.escape(facility_cell)
    return re.fullmatch(
        rf"=COUNTIFS?\(\s*'?(?:{sheet})'?!(?:{column}:{column}|{column}\d+:{column}\d+)\s*,\s*{criterion}\s*\)",
        text,
    ) is not None


def submitted_cost_ok(value: Any, expected: float, kind: str) -> bool:
    numeric = number(value)
    if numeric is not None:
        return abs(numeric - expected) <= max(0.02, 2e-5 * max(1.0, abs(expected)))
    if not formula_has_dependency(value):
        return False
    text = str(value).upper()
    if kind == "warehouse":
        return "INDEX(" in text and "MATCH(" in text
    if kind == "freight":
        return "MAX(" in text or "CRF" in text
    if kind == "total":
        return len(re.findall(r"\$?[A-Z]{1,3}\$?\d+", text)) >= 2
    return False


def method_violations(cells: list[str]) -> list[str]:
    literal = {name for name, patterns in METHOD_RULES
               if any(re.search(pattern, cell) for cell in cells for pattern in patterns)}
    return sorted(literal | set(direction_violations(cells)))


def declared_decision_values(wb, facility_ids: set[str]) -> tuple[set[str], float | None]:
    """The governing facility and recoverable-order count the summary states as literals.

    Only literal cells are read; a value the workbook computes by formula is
    audited by the lineage dimension instead. A workbook that states neither is
    not penalised -- the check fires only on a declaration that is wrong."""
    declared_facilities: set[str] = set()
    declared_recoverable: float | None = None
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            cells = [cell for cell in row if cell.value not in (None, "")]
            # A table's metric header is not a scalar decision declaration.
            mapping = map_headers([c.value for c in cells])
            if "outaged_facility" in mapping and {"recoverable_service", "recovery_cost", "assigned_count"}.intersection(mapping):
                continue
            if len(cells) != 2: continue
            for index, cell in enumerate(cells):
                if cell.data_type == "f":
                    continue
                label = norm_text(cell.value)
                if not label:
                    continue
                rest = cells[index + 1:]
                if "governing" in label and "outage" in label and "recover" not in label:
                    for other in rest:
                        if other.data_type == "f":
                            continue
                        ident = norm_id(other.value)
                        if ident in facility_ids:
                            declared_facilities.add(ident)
                if "recover" in label and "cost" not in label and (
                        "order" in label or "service" in label):
                    for other in rest:
                        if other.data_type == "f":
                            continue
                        value = number(other.value)
                        if value is not None and declared_recoverable is None:
                            declared_recoverable = value
    return declared_facilities, declared_recoverable


def scan_outage_summaries(wb, facility_ids: set[str]) -> dict[str, dict[str, Any]]:
    summaries: dict[str, dict[str, Any]] = {}
    for ws in wb.worksheets:
        values = sheet_values(wb, ws)
        for header_index, header_values in enumerate(values[:40]):
            mapping = map_headers(header_values)
            if "outaged_facility" not in mapping or not ({"recoverable_service", "assigned_count", "recovery_cost", "governing"} & set(mapping)):
                continue
            for row in values[header_index + 1 :]:
                if not any(value not in (None, "") for value in row):
                    continue
                raw_facility = row[mapping["outaged_facility"]] if mapping["outaged_facility"] < len(row) else None
                facility = norm_id(resolve_internal_reference(wb, raw_facility))
                if facility not in facility_ids:
                    continue
                record = {"sheet": ws.title}
                for key, col in mapping.items():
                    if col < len(row):
                        record[key] = resolve_internal_reference(wb, row[col])
                summaries.setdefault(facility, record)
    return summaries


def register_governing_consistent(summaries: dict[str, dict[str, Any]], claims: set[str]) -> bool:
    """The facility a screening register marks governing must be the one its own rows rank first.

    Rows are ranked by recoverable service ascending, then minimum variable cost
    descending. When any row's service cannot be read (an uncached formula), the
    register is not judged."""
    if len(claims) != 1:
        return True
    ranked = {}
    for facility, row in summaries.items():
        service = number(row.get("recoverable_service"))
        if service is None:
            service = number(row.get("assigned_count"))
        if service is None:
            return True
        ranked[facility] = (service, number(row.get("recovery_cost")))
    claim = next(iter(claims))
    if claim not in ranked:
        return True
    lowest = min(service for service, _ in ranked.values())
    service, cost = ranked[claim]
    if service > lowest + 0.01:
        return False
    tied_costs = [c for s_, c in ranked.values() if abs(s_ - lowest) <= 0.01]
    if cost is not None and all(c is not None for c in tied_costs) and cost < max(tied_costs) - 0.01:
        return False
    return True


def route_match(source: dict[str, Any], order: dict[str, Any], facility: str, record: dict[str, Any]) -> tuple[bool, float, bool]:
    warehouse_cost = order["quantity"] * source["unit_costs"][facility]
    if order["service"] == "CRF":
        mode = norm_text(record.get("mode"))
        freight_value = number(record.get("freight_cost"))
        valid = mode in {"", "customer", "customer arranged", "crf"} and (freight_value is None or abs(freight_value) <= 0.01)
        has_evidence = bool(mode) or record.get("freight_cost") not in (None, "")
        return valid, warehouse_cost, has_evidence

    origin = norm_id(record.get("origin"))
    carrier = norm_id(record.get("carrier"))
    mode = norm_text(record.get("mode"))
    submitted_row = number(record.get("rate_row"))
    candidates = candidate_rates(source, order, facility)
    matched = []
    for rate in candidates:
        if submitted_row is not None and rate["source_row"] != int(round(submitted_row)):
            continue
        if origin and rate["origin"] != origin:
            continue
        if carrier and rate["carrier"] != carrier:
            continue
        if mode and mode != "air":
            continue
        lo = number(record.get("rate_min"))
        hi = number(record.get("rate_max"))
        rate_value = number(record.get("rate"))
        minimum = number(record.get("minimum_charge"))
        if lo is not None and abs(rate["minimum_weight"] - lo) > 0.02:
            continue
        if hi is not None and abs(rate["maximum_weight"] - hi) > 0.02:
            continue
        if rate_value is not None and abs(rate["rate"] - rate_value) > 1e-5:
            continue
        if minimum is not None and abs(rate["minimum_charge"] - minimum) > 1e-4:
            continue
        matched.append(rate)
    evidence = bool(origin and carrier and (mode == "air" or submitted_row is not None))
    if not matched:
        cheapest = min(candidates, key=lambda r: max(r["minimum_charge"], r["rate"] * order["weight"])) if candidates else None
        fallback_cost = warehouse_cost + (max(cheapest["minimum_charge"], cheapest["rate"] * order["weight"]) if cheapest else 0.0)
        return False, fallback_cost, evidence
    selected = min(matched, key=lambda r: max(r["minimum_charge"], r["rate"] * order["weight"]))
    freight = max(selected["minimum_charge"], selected["rate"] * order["weight"])
    return True, warehouse_cost + freight, evidence


def clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


# ----------------------------------------------------------------------------
# Conclusion reversal
#
# A reversal that keeps every number is invisible to most of this scorer. The
# dimensions listed in REVERSAL_IMMUNE_DIMENSIONS -- constraint semantics,
# exception boundary, facility footprint, allocation economics, workbook lineage
# and primary service identity -- read allocations, capacities, costs, formulas
# and the served order population, none of which a reversal has to touch, so a
# workbook that reproduces the whole model and then names the *opposite*
# governing outage would keep all of them outright.
#
# The detectors below look only for the **exact opposite**, never for "wrong":
#   - a governing verdict equal to the facility the inverted rule selects (highest
#     recoverable service, cheapest recovery on a tie) rather than merely some
#     other facility, and
#   - an exception register in which *both* classes are swapped for each other.
# An answer that is incorrect, partial, or uses its own field names registers
# nothing: naming a third facility is not the anti-optimum, and labelling every
# exception with one class leaves the other class trivially unswapped, which the
# two-sided minimum below scores as zero.
#
# Each family is rated on its own and the largest rate wins; pooling them would
# let the far larger exception register dilute the governing slots away. The immune
# dimensions are then discounted in proportion to that rate, not gated on it.
REVERSAL_IMMUNE_DIMENSIONS = (
    "constraint_semantics",
    "exception_boundary",
    "facility_footprint",
    "allocation_economics",
    "workbook_lineage",
    "primary_service_identity",
)
# One statement landing on the anti-optimum proves little; the governing verdict
# is stated in four independent places and the rate across them is the signal.
MIN_GOVERNING_SLOTS = 2
# Below this the two-sided swap rate is noise rather than a systematic relabelling.
MIN_REGISTER_ROWS_PER_CLASS = 20


def anti_governing_outage(candidates: set[str], screen: dict[str, Any]) -> str | None:
    """The facility the inverted governing rule selects.

    The brief fixes the governing outage as the lowest recoverable service, with
    *higher* minimum variable cost breaking a service tie. Its exact inverse is
    the highest recoverable service with *lower* cost breaking the tie. Returns
    None when that is the same facility, or when there are too few outages
    screened for "highest" and "lowest" to be distinguishable."""
    usable = [facility for facility in candidates if facility in screen]
    if len(usable) < 3:
        return None
    expected = min(
        usable,
        key=lambda f: (screen[f]["maximum_service"], -screen[f]["minimum_variable_cost"], f),
    )
    anti = max(
        usable,
        key=lambda f: (screen[f]["maximum_service"], -screen[f]["minimum_variable_cost"], f),
    )
    return anti if anti != expected else None


def governing_reversal_rate(
    expected: str | None,
    anti: str | None,
    screen: dict[str, Any],
    marked: set[str],
    declared_facilities: set[str],
    declared_recoverable: float | None,
    detail_outage: str | None,
) -> tuple[float, list[bool]]:
    """How consistently the workbook states the anti-optimum as its governing outage.

    Each of the four places the verdict appears contributes a slot: True when it
    names the anti-optimum, False when it names the right one, and no slot at all
    when it is absent or names something else. Silence is therefore never a
    reversal."""
    if expected is None or anti is None:
        return 0.0, []
    slots: list[bool] = []

    def facility_slot(claim: set[str]) -> None:
        if claim == {expected}:
            slots.append(False)
        elif claim == {anti}:
            slots.append(True)

    facility_slot(marked)
    facility_slot(declared_facilities)
    if declared_recoverable is not None:
        for facility, verdict in ((expected, False), (anti, True)):
            target = screen.get(facility, {}).get("maximum_service")
            if target is not None and abs(declared_recoverable - target) <= 0.01:
                slots.append(verdict)
                break
    if detail_outage == expected:
        slots.append(False)
    elif detail_outage == anti:
        slots.append(True)
    if len(slots) < MIN_GOVERNING_SLOTS:
        return 0.0, slots
    return sum(1 for slot in slots if slot) / len(slots), slots


def register_reversal_rate(
    rows: list[tuple[str, str]], eligibility: dict[str, set[str]]
) -> tuple[float, dict[str, Any]]:
    """How completely the two exception classes have been swapped for each other.

    Scored as the smaller of the two one-way swap rates, so a register that labels
    everything CAPACITY -- wrong, but not a swap, because the orders that really
    are capacity cases keep their correct label -- rates zero."""
    structural_rows = [cls for oid, cls in rows if not eligibility.get(oid)]
    capacity_rows = [cls for oid, cls in rows if eligibility.get(oid)]
    detail = {
        "structural_rows": len(structural_rows),
        "capacity_rows": len(capacity_rows),
    }
    if (len(structural_rows) < MIN_REGISTER_ROWS_PER_CLASS
            or len(capacity_rows) < MIN_REGISTER_ROWS_PER_CLASS):
        return 0.0, detail
    structural_swapped = sum(1 for cls in structural_rows if cls == "CAPACITY") / len(structural_rows)
    capacity_swapped = sum(1 for cls in capacity_rows if cls == "STRUCTURAL") / len(capacity_rows)
    detail["structural_labelled_capacity"] = round(structural_swapped, 6)
    detail["capacity_labelled_structural"] = round(capacity_swapped, 6)
    return min(structural_swapped, capacity_swapped), detail


def decision_signature(record: dict[str, Any]) -> tuple[str | None, str]:
    decision = record.get("decision")
    facility = norm_id(record.get("facility")) if decision == "ASSIGNED" else ""
    return decision, facility


def score(answer: Path, source_path: Path, gt_path: Path) -> dict[str, Any]:
    gt = json.loads(gt_path.read_text(encoding="utf-8"))
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    source_intact = source_hash == gt["source_sha256"]
    source = load_source(source_path)
    order_ids = set(source["orders"])
    facility_ids = set(source["facilities"])
    eligibility = {oid: eligible_facilities(source, order) for oid, order in source["orders"].items()}

    try:
        wb = _guard_workbook(load_workbook(answer, read_only=False, data_only=False))
    except Exception as exc:
        return {
            "rewards": {"lenient": 0.0},
            "score_type": "constrained_dc_network_workbook",
            "reward_formulas": {
                "lenient": "product of five brief-compliance coverage factors",
            },
            "group_points": {},
            "gates": {"workbook_readable": 0.0, "source_integrity": float(source_intact)},
            "diagnostics": {"error": str(exc)},
        }

    # Second, streaming view of the same file that exposes cached formula results.
    # sheet_values prefers it per cell and falls back to the formula text wherever the
    # file stores no cached result, which is the case for every formula cell of Golden.
    try:
        wb._cached_value_book = load_workbook(answer, read_only=True, data_only=True)
    except Exception:
        wb._cached_value_book = None

    order_tables = scan_order_tables(wb, order_ids, facility_ids)
    primary_tables, recovery_tables = split_order_tables(order_tables)
    primary, records, duplicate_rows, conflicts = collect_records(primary_tables)

    claimed_assigned = [row for row in records.values() if row.get("decision") == "ASSIGNED"]
    claimed_unassigned = [row for row in records.values() if row.get("decision") == "UNASSIGNED"]
    valid_assigned: dict[str, dict[str, Any]] = {}
    route_valid_count = 0
    route_evidence_count = 0
    cost_auditable_count = 0
    computed_cost = 0.0
    claimed_flow = Counter()
    valid_flow = Counter()
    for row in claimed_assigned:
        oid = row["order_id"]
        facility = norm_id(row.get("facility"))
        if facility in facility_ids:
            claimed_flow[facility] += 1
        if facility not in eligibility.get(oid, set()):
            continue
        valid_assigned[oid] = row
        valid_flow[facility] += 1
        route_ok, row_cost, has_route_evidence = route_match(source, source["orders"][oid], facility, row)
        audited_row_cost = row_cost
        if route_ok:
            route_valid_count += 1
        else:
            candidates = candidate_rates(source, source["orders"][oid], facility)
            if source["orders"][oid]["service"] == "CRF":
                audited_row_cost = source["orders"][oid]["quantity"] * source["unit_costs"][facility]
            elif candidates:
                cheapest = min(candidates, key=lambda r: max(r["minimum_charge"], r["rate"] * source["orders"][oid]["weight"]))
                audited_row_cost = source["orders"][oid]["quantity"] * source["unit_costs"][facility] + max(cheapest["minimum_charge"], cheapest["rate"] * source["orders"][oid]["weight"])
        computed_cost += audited_row_cost
        route_evidence_count += int(has_route_evidence)
        warehouse_expected = source["orders"][oid]["quantity"] * source["unit_costs"][facility]
        freight_expected = max(0.0, audited_row_cost - warehouse_expected)
        cost_fields_ok = (
            submitted_cost_ok(row.get("warehouse_cost"), warehouse_expected, "warehouse"),
            submitted_cost_ok(row.get("freight_cost"), freight_expected, "freight"),
            submitted_cost_ok(row.get("total_cost"), audited_row_cost, "total"),
        )
        if has_route_evidence and all(cost_fields_ok):
            cost_auditable_count += 1

    claimed_count = len(claimed_assigned)
    valid_count = len(valid_assigned)
    assignment_eligibility = valid_count / claimed_count if claimed_count else 0.0
    maximum_service = gt["maximum_service"]
    capacity_feasible_count = sum(
        min(count, source["capacities"].get(facility, 0))
        for facility, count in valid_flow.items()
    )
    service_effectiveness = clamp(capacity_feasible_count / maximum_service) if maximum_service else 1.0
    if valid_count:
        route_integrity = (route_valid_count + 0.25 * max(0, valid_count - route_valid_count)) / valid_count
        route_evidence = route_evidence_count / valid_count
    else:
        route_integrity = 0.0
        route_evidence = 0.0
    capacity_numerator = sum(min(count, source["capacities"].get(facility, 0)) for facility, count in claimed_flow.items())
    capacity_integrity = capacity_numerator / claimed_count if claimed_count else 0.0
    constraint_semantics = clamp(
        0.35 * assignment_eligibility
        + 0.20 * route_integrity
        + 0.25 * capacity_integrity
        + 0.20 * route_evidence
    )

    reason_hits = 0
    for row in claimed_unassigned:
        expected = "STRUCTURAL" if not eligibility.get(row["order_id"]) else "CAPACITY"
        reason_hits += int(row.get("reason_class") == expected)
    reason_accuracy = reason_hits / len(claimed_unassigned) if claimed_unassigned else 0.0
    # The exception register is a separate required deliverable, and the task statement
    # forbids describing lost eligibility as a capacity requirement.  `collect_records`
    # keeps only the largest primary table, so a standalone exception register is not
    # covered by it.  Score every primary table that
    # carries a reason column and take the weakest: two tables that classify the same
    # exception differently cannot both be the answer.
    register_accuracies = []
    primary_order_ids = set(records)
    for table in primary_tables:
        if table is primary or "reason" not in table.mapping:
            continue
        classified = [row for row in table.rows if row.get("reason_class")]
        overlap = sum(1 for row in table.rows if row.get("order_id") in primary_order_ids)
        # A standalone exception register may contain only a small subset of
        # orders.  It can constrain the aggregate only when it demonstrably
        # describes at least half of the primary order population; otherwise
        # use it as supplemental evidence without letting one row dominate the
        # primary classification score.
        if len(classified) < 3 or overlap < max(1, math.ceil(0.5 * len(table.rows))):
            continue
        hits = sum(
            int(row["reason_class"] == ("STRUCTURAL" if not eligibility.get(row["order_id"]) else "CAPACITY"))
            for row in classified
        )
        register_accuracies.append(hits / len(classified))
    exception_register_accuracy = min(register_accuracies) if register_accuracies else 1.0
    reason_accuracy = min(reason_accuracy, exception_register_accuracy)
    structural = set(gt["structural_unassigned_ids"])
    structural_hits = sum(
        1
        for oid in structural
        if oid in records and records[oid].get("decision") == "UNASSIGNED" and records[oid].get("reason_class") == "STRUCTURAL"
    )
    structural_coverage = structural_hits / len(structural) if structural else 1.0
    decision_coverage = len(records) / gt["order_count"]
    expected_unassigned_from_submission = max(0, gt["order_count"] - valid_count)
    explicit_unassigned = len({row["order_id"] for row in claimed_unassigned})
    conservation = min(explicit_unassigned, expected_unassigned_from_submission) / expected_unassigned_from_submission if expected_unassigned_from_submission else 1.0
    exception_boundary = clamp(
        0.25 * decision_coverage + 0.35 * reason_accuracy
        + 0.25 * structural_coverage + 0.15 * conservation
    )

    facility_tables = scan_facility_tables(wb, facility_ids, order_ids)
    facility_table = choose_facility_table(facility_tables, recovery=False)
    plan_rows = {}
    if facility_table:
        plan_rows = {row["facility"]: row for row in facility_table.rows}
        facility_col = facility_table.mapping.get("facility", 0) + 1
        for row in plan_rows.values():
            row["_facility_col"] = facility_col
    plan_coverage = len(plan_rows) / len(facility_ids)
    status_hits = 0
    count_capacity_hits = 0.0
    close_claims = 0
    for facility, row in plan_rows.items():
        status = normalize_facility_status(row.get("decision"))
        expected = "USE" if valid_flow[facility] > 0 else "NOT_USED"
        status_hits += int(status == expected)
        close_claims += int(status == "CLOSE")
        capacity_value = number(row.get("capacity"))
        capacity_hit = capacity_value is not None and abs(capacity_value - source["capacities"][facility]) <= 0.01
        assigned_value = number(row.get("assigned_count"))
        assigned_formula = count_formula_matches_detail(row.get("assigned_count"), primary, row)
        count_hit = (assigned_value is not None and abs(assigned_value - valid_flow[facility]) <= 0.01) or assigned_formula
        count_capacity_hits += 0.5 * int(capacity_hit) + 0.5 * int(count_hit)
    status_consistency = status_hits / len(plan_rows) if plan_rows else 0.0
    count_capacity_reconciliation = count_capacity_hits / len(plan_rows) if plan_rows else 0.0
    boundary_score = 1.0 if plan_rows and close_claims == 0 else 0.0
    submitted_primary_facilities = {facility for facility, count in valid_flow.items() if count > 0}
    submitted_facility_count = len(submitted_primary_facilities)
    minimum_facilities = gt["minimum_primary_facilities"]
    if not plan_rows or valid_count == 0:
        compactness = 0.0
    elif valid_count == maximum_service and submitted_facility_count == minimum_facilities:
        compactness = 1.0
    else:
        compactness = clamp(minimum_facilities / max(minimum_facilities, submitted_facility_count or minimum_facilities))
    facility_footprint = clamp(
        (0.15 * plan_coverage + 0.20 * status_consistency + 0.15 * count_capacity_reconciliation + 0.10 * boundary_score + 0.40 * compactness)
    )

    cost_efficiency = clamp(gt["reference_variable_cost"] / computed_cost) if computed_cost > 0 else 0.0
    cost_audit_coverage = cost_auditable_count / valid_count if valid_count else 0.0
    # A cost-optimal allocation is not an auditable economic recommendation when
    # the workbook's displayed warehouse, freight and total-cost fields are wrong
    # or absent. Feasibility and independent optimum establish the economic basis;
    # correct row-level cost disclosure is the prerequisite that makes it reviewable.
    allocation_economics = clamp(
        (0.65 * service_effectiveness + 0.35 * cost_efficiency) * cost_audit_coverage
    )

    # Alternative optimal order populations are valid. Reference ID overlap is
    # diagnostic only; earned credit uses independently capacity-feasible eligible service.
    gold_service = {norm_id(oid) for oid in gt["gold_assigned_ids"]}
    served_matched = len(set(valid_assigned) & gold_service)
    service_recall = served_matched / len(gold_service) if gold_service else 1.0
    service_precision = served_matched / valid_count if valid_count else 0.0
    primary_service_identity = service_effectiveness  # Any eligible, capacity-feasible equal-objective population is accepted.

    outage_summaries = scan_outage_summaries(wb, facility_ids)
    expected_governing = None
    if submitted_primary_facilities:
        expected_governing = min(
            submitted_primary_facilities,
            key=lambda facility: (
                gt["outage_screen"][facility]["maximum_service"],
                -gt["outage_screen"][facility]["minimum_variable_cost"],
                facility,
            ),
        )
    screened = [facility for facility in submitted_primary_facilities if facility in outage_summaries]
    screen_coverage = len(screened) / len(submitted_primary_facilities) if submitted_primary_facilities else 0.0
    screen_service_hits = 0
    screen_cost_hits = 0
    screen_cause_hits = 0
    for facility in screened:
        row = outage_summaries[facility]
        expected = gt["outage_screen"][facility]
        submitted_service = number(row.get("recoverable_service"))
        if submitted_service is None:
            submitted_service = number(row.get("assigned_count"))
        screen_service_hits += int(submitted_service is not None and abs(submitted_service - expected["maximum_service"]) <= 0.01)
        submitted_cost = number(row.get("recovery_cost"))
        screen_cost_hits += int(submitted_cost is not None and abs(submitted_cost - expected["minimum_variable_cost"]) <= max(1.0, 2e-5 * expected["minimum_variable_cost"]))
        submitted_structural = number(row.get("structural_count"))
        submitted_capacity = number(row.get("capacity_count"))
        screen_cause_hits += int(
            submitted_structural is not None
            and submitted_capacity is not None
            and abs(submitted_structural - expected["structural_unassigned"]) <= 0.01
            and abs(submitted_capacity - expected["capacity_unassigned"]) <= 0.01
        )
    governing_claims = {
        facility for facility, row in outage_summaries.items() if yes(row.get("governing"))
    }
    # The governing outage is also stated in the summary as a literal facility
    # name and a literal recoverable-order count. Naming it correctly in the
    # screening table while naming a different facility in the summary is not
    # "identifying the governing outage" -- the two statements disagree and the
    # brief asks for one decision.
    declared_governing, declared_recoverable = declared_decision_values(wb, facility_ids)
    summary_governing_ok = (
        not declared_governing
        or (expected_governing is not None and declared_governing == {expected_governing})
    )
    expected_recoverable = (
        gt["outage_screen"].get(expected_governing, {}).get("maximum_service")
        if expected_governing else None
    )
    summary_recoverable_ok = (
        declared_recoverable is None
        or expected_recoverable is None
        or abs(declared_recoverable - expected_recoverable) <= 0.01
    )
    governing_hit = (
        expected_governing is not None
        and governing_claims == {expected_governing}
        and summary_governing_ok
        and register_governing_consistent(outage_summaries, governing_claims)
    )
    # Naming the governing outage is the decision the screening table exists to produce.
    # The same 0.35 residual used for a misdirected recovery detail applies here, so a
    # table of correct per-outage metrics that points at the wrong governing facility
    # cannot carry the dimension on its metrics alone.
    outage_screening = clamp(
        (
            0.20 * screen_coverage
            + 0.20 * (screen_service_hits / len(submitted_primary_facilities) if submitted_primary_facilities else 0.0)
            + 0.15 * (screen_cost_hits / len(submitted_primary_facilities) if submitted_primary_facilities else 0.0)
            + 0.25 * (screen_cause_hits / len(submitted_primary_facilities) if submitted_primary_facilities else 0.0)
            + 0.20 * float(governing_hit)
        )
        * (1.0 if governing_hit else 0.35)
        * (1.0 if summary_recoverable_ok else 0.35)
    )

    recovery_primary, recovery_records, recovery_duplicates, recovery_conflicts = collect_records(recovery_tables)
    # Which event the governing recovery details is read from the table that details
    # it, not from the union of every recovery row in the workbook: a workbook that
    # also ships an all-scenarios ledger would otherwise have its governing event
    # decided by whichever facility that ledger happens to mention most.
    recovery_outage_rows = recovery_primary.rows if recovery_primary else []
    recovery_outage_values = Counter(
        norm_id(row.get("outaged_facility"))
        for row in recovery_outage_rows
        if norm_id(row.get("outaged_facility")) in facility_ids
    )
    recovery_outage = recovery_outage_values.most_common(1)[0][0] if recovery_outage_values else None
    if recovery_outage is None and recovery_primary:
        title_text = compact(recovery_primary.sheet)
        title_matches = [facility for facility in facility_ids if compact(facility) in title_text]
        if len(title_matches) == 1:
            recovery_outage = title_matches[0]
    if recovery_outage is None and recovery_records and expected_governing:
        recovery_outage = expected_governing

    recovery_claimed = [row for row in recovery_records.values() if row.get("decision") == "ASSIGNED"]
    recovery_unassigned = [row for row in recovery_records.values() if row.get("decision") == "UNASSIGNED"]
    valid_recovery: dict[str, dict[str, Any]] = {}
    recovery_flow = Counter()
    recovery_route_valid = 0
    recovery_route_evidence = 0
    recovery_computed_cost = 0.0
    for row in recovery_claimed:
        oid = row["order_id"]
        facility = norm_id(row.get("facility"))
        if facility == recovery_outage or facility not in eligibility.get(oid, set()):
            continue
        valid_recovery[oid] = row
        recovery_flow[facility] += 1
        route_ok, row_cost, evidence = route_match(source, source["orders"][oid], facility, row)
        recovery_route_valid += int(route_ok)
        recovery_route_evidence += int(evidence)
        recovery_computed_cost += row_cost

    recovery_target = gt["outage_screen"].get(recovery_outage, {}).get("maximum_service", 0)
    recovery_target_cost = gt["outage_screen"].get(recovery_outage, {}).get("minimum_variable_cost", 0.0)
    recovery_capacity_count = sum(
        min(count, 0 if facility == recovery_outage else source["capacities"].get(facility, 0))
        for facility, count in recovery_flow.items()
    )
    recovery_service = clamp(recovery_capacity_count / recovery_target) if recovery_target else 0.0
    recovery_validity = len(valid_recovery) / len(recovery_claimed) if recovery_claimed else 0.0
    recovery_population = len(recovery_records) / gt["order_count"]
    recovery_outage_excluded = recovery_outage is not None and all(
        norm_id(row.get("facility")) != recovery_outage for row in recovery_claimed
    )
    recovery_reason_hits = 0
    for row in recovery_unassigned:
        remaining = eligibility.get(row["order_id"], set()) - ({recovery_outage} if recovery_outage else set())
        expected_reason = "STRUCTURAL" if not remaining else "CAPACITY"
        recovery_reason_hits += int(row.get("reason_class") == expected_reason)
    recovery_reason_accuracy = recovery_reason_hits / len(recovery_unassigned) if recovery_unassigned else 0.0
    recovery_route_score = (
        (0.70 * recovery_route_valid + 0.30 * recovery_route_evidence) / len(valid_recovery)
        if valid_recovery else 0.0
    )
    recovery_cost_score = (
        clamp(recovery_target_cost / recovery_computed_cost) * recovery_service
        if recovery_computed_cost > 0 and recovery_target_cost > 0 else 0.0
    )
    governing_detail_hit = recovery_outage is not None and recovery_outage == expected_governing

    recovery_facility_table = choose_facility_table(facility_tables, recovery=True)
    recovery_plan_rows = {row["facility"]: row for row in recovery_facility_table.rows} if recovery_facility_table else {}
    recovery_plan_coverage = len(recovery_plan_rows) / len(facility_ids)
    recovery_plan_hits = 0
    for facility, row in recovery_plan_rows.items():
        status = normalize_facility_status(row.get("decision"))
        if facility == recovery_outage:
            expected_status = "NOT_USED"
        else:
            expected_status = "USE" if recovery_flow[facility] > 0 else "NOT_USED"
        recovery_plan_hits += int(status == expected_status)
    recovery_plan_consistency = recovery_plan_hits / len(recovery_plan_rows) if recovery_plan_rows else 0.0

    outage_recovery = clamp(
        (0.10 * clamp(recovery_population)
        + 0.20 * recovery_validity
        + 0.25 * recovery_service
        + 0.10 * recovery_reason_accuracy
        + 0.10 * recovery_route_score
        + 0.10 * recovery_cost_score
        + 0.05 * float(recovery_outage_excluded)
        + 0.05 * recovery_plan_coverage
        + 0.05 * recovery_plan_consistency)
        # The recovery detail must be the recovery detail for the outage the screening
        # table identifies as governing; a workbook whose screening marks one facility and
        # whose allocation details another has not answered the question either way.
        * (1.0 if (governing_detail_hit and governing_hit) else 0.35)
    )

    formula_cells = []
    cross_sheet_cells = []
    primary_detail_formulas = 0
    primary_cross_formulas = 0
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if cell.data_type != "f":
                    continue
                if not formula_has_dependency(cell.value):
                    continue
                formula_cells.append((ws.title, cell.coordinate, str(cell.value)))
                if "!" in str(cell.value):
                    cross_sheet_cells.append((ws.title, cell.coordinate, str(cell.value)))
                if primary and ws.title == primary.sheet and cell.row > primary.header_row:
                    primary_detail_formulas += 1
                    if "!" in str(cell.value):
                        primary_cross_formulas += 1
    detail_formula_ratio = clamp(primary_detail_formulas / max(1, 2 * valid_count))
    detail_cross_ratio = clamp(primary_cross_formulas / max(1, valid_count))
    non_detail_formulas = len(formula_cells) - primary_detail_formulas
    summary_formula_ratio = clamp(non_detail_formulas / 10.0)
    workbook_lineage = clamp(0.40 * detail_formula_ratio + 0.35 * detail_cross_ratio + 0.25 * summary_formula_ratio)

    readable = 1.0
    validity_gate = 1.0  # Eligibility is already assessed locally in P01; do not discount all dimensions twice.
    # A workbook that records the opposite of the decision rule it was asked to
    # apply is not an auditable decision record, which is what the brief asks
    # for ("decision-ready ... implications", "sufficient to audit individual
    # decisions"). All six rules checked are stated in the brief itself, three of
    # them as explicit prohibitions. Only affirmatively reversed statements count,
    # so a reworded, abbreviated or silent workbook is unaffected.
    #
    # Each reversed rule is a separate damage instance (D03..D08) rather than a
    # dimension of its own, because the same prose underwrites every dimension's
    # audit trail.
    prose = narrative_cells(wb)
    # Open-ended method explanations are owned by the required source-bound
    # semantic gate. Program scoring remains limited to closed numeric, formula,
    # relation and conservation checks.
    recorded_method_violations = []
    crf_claims = crf_freight_claims(prose)
    outside_claims = []
    groups = {
        "constraint_semantics": constraint_semantics,
        "exception_boundary": exception_boundary,
        "facility_footprint": facility_footprint,
        "allocation_economics": allocation_economics,
        "workbook_lineage": workbook_lineage,
        "outage_screening": outage_screening,
        "governing_outage_recovery": outage_recovery,
        "primary_service_identity": primary_service_identity,
    }

    # Withdraw credit for a model that is reproduced correctly and then used to
    # state the opposite conclusion, in proportion to how systematically the
    # conclusion is reversed. See REVERSAL_IMMUNE_DIMENSIONS above.
    anti_governing = anti_governing_outage(submitted_primary_facilities, gt["outage_screen"])
    governing_rate, governing_slots = governing_reversal_rate(
        expected_governing,
        anti_governing,
        gt["outage_screen"],
        governing_claims,
        declared_governing,
        declared_recoverable,
        recovery_outage,
    )
    register_rows = [
        (row["order_id"], row["reason_class"])
        for table in primary_tables
        for row in table.rows
        if row.get("reason_class")
    ]
    register_rate, register_detail = register_reversal_rate(register_rows, eligibility)
    conclusion_reversal_rate = max(governing_rate, register_rate)
    for name in REVERSAL_IMMUNE_DIMENSIONS:
        groups[name] *= 1.0 - conclusion_reversal_rate

    population_factor = clamp(decision_coverage)
    facility_factor = clamp(plan_coverage)
    outage_factor = screen_coverage
    recovery_population_factor = clamp(recovery_population)
    recovery_service_factor = recovery_service * float(governing_detail_hit)
    lenient = readable * float(source_intact) * population_factor * facility_factor * outage_factor * recovery_population_factor * recovery_service_factor
    # The binary lens owns indispensable business invariants, while strict
    # retains continuous presentation and optimization quality.  These checks
    # avoid arbitrary floors on weighted composite dimensions.
    business_must_haves = {
        "P01": bool(claimed_count and valid_count == claimed_count and route_valid_count == valid_count
                    and capacity_integrity == 1.0),
        "P02": bool(decision_coverage == 1.0 and conservation == 1.0 and structural_coverage == 1.0),
        "P04": bool(valid_count and cost_audit_coverage == 1.0 and computed_cost > 0
                    and service_effectiveness > 0),
        "P06": bool((not submitted_primary_facilities) or screen_coverage == 1.0),
        "P07": bool(governing_detail_hit and recovery_service >= 1.0 and recovery_population > 0),
        "P08": bool(service_effectiveness >= 1.0),
    }
    wb.close()

    lenient = round(clamp(lenient), 6)
    # Settlement parts (pd-ledger-v1); see settle().  validity_gate is a continuous
    # fraction scaling the whole sum, so it is folded into every completion.
    parts_completion = {item: groups[name] * validity_gate for item, name in POSITIVE_ITEMS}
    parts_damage = []
    if not source_intact:
        parts_damage.append(("source workbook hash differs from ground truth", ["D01"]))
    if duplicate_rows or conflicts:
        parts_damage.append((f"primary order decisions: {duplicate_rows} duplicate rows, {conflicts} conflicting", ["D02"]))
    # Only a literal status is compared; a status formula without a cached result
    # states no value to contradict.
    inconsistent_facilities = sum(
        1 for facility, row in plan_rows.items()
        if not str(row.get("decision") or "").startswith("=")
        and (normalize_facility_status(row.get("decision")) == "NOT_USED" and valid_flow[facility] > 0
             or normalize_facility_status(row.get("decision")) == "USE" and valid_flow[facility] == 0)
    )
    if inconsistent_facilities:
        parts_damage.append((f"facility status contradicts valid flow for {inconsistent_facilities} facilities", ["D09"]))
    for step, violation in enumerate(recorded_method_violations[:len(METHOD_STEP_ITEMS)]):
        parts_damage.append((f"recorded method violation {step + 1}: {violation}", [METHOD_STEP_ITEMS[step]]))
    if crf_claims:
        parts_damage.append((f"company freight stated as charged to customer-arranged CRF: {crf_claims[0][:120]}", ["D10"]))
    if outside_claims:
        parts_damage.append((f"reliance on information outside /workspace stated: {outside_claims[0][:120]}", ["D11"]))
    primary_sheets = {table.sheet for table in primary_tables}
    listed_orders = set().union(*[table.listed_ids for table in order_tables if table.sheet in primary_sheets])
    if len(listed_orders) < COMPLETENESS_FLOOR * gt["order_count"]:
        parts_damage.append((f"primary order tables list {len(listed_orders)} of {gt['order_count']} orders", ["D12"]))
    if submitted_primary_facilities and screen_coverage < COMPLETENESS_FLOOR:
        parts_damage.append((f"outage register covers {len(screened)} of {len(submitted_primary_facilities)} used facilities", ["D13"]))
    if answer.name != DELIVERABLE_NAME:
        parts_damage.append((f"deliverable {DELIVERABLE_NAME} missing; scored {answer.name} instead", ["D14"]))
    return {
        "_parts": {"completion": parts_completion, "damage": parts_damage,
                   "business_must_haves": business_must_haves},
        "rewards": {"lenient": lenient},
        "score_type": "constrained_dc_network_workbook",
        "reward_formulas": {
            "lenient": "readable * source_intact * primary_population * facility_register * outage_register * recovery_population * recovery_service",
        },
        "group_points": {key: round(value, 6) for key, value in groups.items()},
        "lenient_factors": {
            "readable_workbook": readable,
            "order_population_addressed": round(population_factor, 6),
            "facility_decision_visible": round(facility_factor, 6),
            "outage_comparison_visible": round(outage_factor, 6),
            "governing_recovery_population": round(recovery_population_factor, 6),
            "governing_recovery_completed": round(recovery_service_factor, 6),
        },
        "gates": {
            "workbook_readable": readable,
            "source_integrity": float(source_intact),
            "valid_assignment_penalty": round(validity_gate, 6),
        },
        "diagnostics": {
            "primary_order_table": {"sheet": primary.sheet, "header_row": primary.header_row} if primary else None,
            "facility_table": {"sheet": facility_table.sheet, "header_row": facility_table.header_row} if facility_table else None,
            "orders_addressed": len(records),
            "claimed_assigned": claimed_count,
            "valid_assigned": valid_count,
            "capacity_feasible_assigned": capacity_feasible_count,
            "service_set_matched": served_matched,
            "service_set_recall": round(service_recall, 6),
            "service_set_precision": round(service_precision, 6),
            "claimed_unassigned": len(claimed_unassigned),
            "maximum_service": maximum_service,
            "route_valid_count": route_valid_count,
            "route_evidence_count": route_evidence_count,
            "capacity_overages": {facility: count - source["capacities"].get(facility, 0) for facility, count in claimed_flow.items() if count > source["capacities"].get(facility, 0)},
            "reason_accuracy": round(reason_accuracy, 6),
            "exception_register_accuracy": round(exception_register_accuracy, 6),
            "structural_exception_coverage": round(structural_coverage, 6),
            "formula_cells": len(formula_cells),
            "cross_sheet_formula_cells": len(cross_sheet_cells),
            "computed_variable_cost": round(computed_cost, 6),
            "reference_variable_cost": round(float(gt["reference_variable_cost"]), 6),
            "duplicate_rows": duplicate_rows,
            "conflicting_decisions": conflicts,
            "unsupported_close_claims": close_claims,
            "primary_facilities_used": submitted_facility_count,
            "minimum_primary_facilities": minimum_facilities,
            "outage_summaries_matched": len(screened),
            "expected_governing_outage": expected_governing,
            "submitted_governing_outage": recovery_outage,
            "summary_declared_governing_outage": sorted(declared_governing),
            "summary_declared_recoverable_orders": declared_recoverable,
            "summary_governing_consistent": bool(summary_governing_ok),
            "summary_recoverable_consistent": bool(summary_recoverable_ok),
            "recorded_method_violations": recorded_method_violations,
            "anti_governing_outage": anti_governing,
            "conclusion_reversal_rate": round(conclusion_reversal_rate, 6),
            "conclusion_reversal_detail": {
                "governing_rate": round(governing_rate, 6),
                "governing_slots": governing_slots,
                "register_rate": round(register_rate, 6),
                "exception_register": register_detail,
            },
            "recovery_orders_addressed": len(recovery_records),
            "recovery_claimed_assigned": len(recovery_claimed),
            "recovery_valid_assigned": len(valid_recovery),
            "recovery_capacity_feasible_assigned": recovery_capacity_count,
            "recovery_target_service": recovery_target,
            "recovery_reason_accuracy": round(recovery_reason_accuracy, 6),
            "recovery_formula_table": {"sheet": recovery_primary.sheet, "header_row": recovery_primary.header_row} if recovery_primary else None,
            "recovery_duplicate_rows": recovery_duplicates,
            "recovery_conflicting_decisions": recovery_conflicts,
        },
    }


ZERO_PARTS = {"completion": {}, "damage": []}

# ---------------------------------------------------------------------------
# The lenient lens.
#
# It is not a cut on the weighted total: it asks whether the few things this
# workbook cannot be called done without are ALL met, each judged on that item's
# OWN result as the strict scorer already settled it. A weighted total cannot
# answer that -- formula density and a tidy facility register carry the total
# while half the decision the brief asks for is simply absent.
#
# Why these items:
#   D01 - instruction.md: "Keep the source workbook read-only". RUBRIC D01: "a
#         mutated source invalidates every figure derived from it."
#   D03 - the first slot of the recorded-method-reversal ledger, so requiring it
#         means no reversal was recorded at all. RUBRIC: "Six rules are checked,
#         each stated in the task brief itself" -- among them "Identify the
#         governing outage as the one with the lowest recoverable service", "Do
#         not describe lost eligibility as a capacity requirement", and "Do not
#         invent capacity, routes, rates, or service for unsupported orders".
#         These are the brief's own prohibitions, quoted from it verbatim.
#   D12 - the primary order tables list at least COMPLETENESS_FLOOR of the day's
#         orders. instruction.md: the workbook "must show ... the primary allocation,
#         every primary exception". A register that lists half the orders has not
#         shown them.
#   D13 - the outage register covers at least COMPLETENESS_FLOOR of the facilities
#         the submitted plan uses. instruction.md: "Evaluate each such
#         single-facility outage".
#   D14 - the deliverable is the declared file, `network_design_recommendation.xlsx`.
#   P01 - current constraint semantics: the share of claimed primary assignments
#         current eligibility supports, with route and capacity evidence.
#         instruction.md: "Do not invent capacity, routes, rates, or service for
#         unsupported orders." A plan resting on unsupported assignments is not
#         one leadership can act on.
#   P02 - instruction.md: the workbook "must show ... every primary exception",
#         and "report ... the split between orders with no remaining current path
#         and orders with a remaining path but no capacity". An allocation that
#         leaves its own unserved orders implicit is not a decision record.
#   P08 - primary service identity: which orders the plan actually serves, read by
#         identifier. The brief's objective is the footprint "that preserves the
#         maximum service the supplied network can support"; a plan that does not
#         reach that order population has not preserved it.
# P03-P07 are required because the brief makes minimum footprint, cost
# preference, auditable lineage, every used-facility outage, and complete
# governing-event recovery part of the delivered decision. Lenient reuses the
# strict ledger's item completions; it does not apply a total-score threshold or
# a second interpretation of those requirements.
LENIENT_REQUIRED_ITEMS = (
    "D01", "D03", "D12", "D13", "D14",
    "P01", "P02", "P04", "P06", "P07", "P08",
)


def lenient_lens(ledger: dict[str, Any], coefficients: dict[str, Any]) -> tuple[float, dict[str, bool]]:
    """1.0 when every item of LENIENT_REQUIRED_ITEMS holds, else 0.0.

    A deduction item holds exactly when it raised no damage instance; a positive
    item holds when its own completion reaches its floor. Neither reads a weight,
    and an id the ledger does not carry fails closed.
    """
    fired = {item for instance in ledger["damage_instances"] for item in instance["item_ids"]}
    completion = ledger["positive_completion"]
    met: dict[str, bool] = {}
    for item in LENIENT_REQUIRED_ITEMS:
        if item in coefficients:
            met[item] = item not in fired
        elif item in ledger.get("business_must_haves", {}):
            met[item] = bool(ledger["business_must_haves"][item])
        else:
            met[item] = False
    return (1.0 if all(met.values()) else 0.0), met


def deliverable(arg: Path) -> Path:
    """The contract passes a directory (rollout artifacts/ or task golden/); the container passes the file."""
    if not arg.is_dir():
        return arg
    named = arg / DELIVERABLE_NAME
    if named.is_file():
        return named
    found = sorted(arg.rglob("*.xlsx"))
    return found[0] if found else named


def default_source() -> Path:
    container = Path("/workspace") / SOURCE_NAME
    if container.is_file():
        return container
    return HERE.parent / "environment" / "workspace" / SOURCE_NAME


def settle(result: dict[str, Any]) -> dict[str, Any]:
    """Settle the scored parts as pd-ledger-v1."""
    params = json.loads(PARAMS.read_text(encoding="utf-8"))
    weights, coefficients = params["positive_weights"], params["deduction_coefficients"]
    basis = params.get("owner_basis")
    basis_fields = {"evaluates", "importance", "weight_reason", "prerequisites", "calculation", "missing_vs_wrong"}
    if not isinstance(basis, dict) or set(basis) != set(weights):
        raise ValueError("owner_basis coverage differs from positive weights")
    for item, detail in basis.items():
        if (not isinstance(detail, dict) or set(detail) != basis_fields
                or not all(isinstance(detail[key], str) and detail[key].strip()
                           for key in basis_fields - {"prerequisites"})
                or not isinstance(detail["prerequisites"], list) or not detail["prerequisites"]
                or not all(isinstance(value, str) and value.strip() for value in detail["prerequisites"])):
            raise ValueError(f"owner_basis invalid: {item}")
    parts = result.pop("_parts", ZERO_PARTS)
    completion = {k: round(clamp(parts["completion"].get(k, 0.0)), 10) for k in weights}
    instances = [{"key": key, "item_ids": items} for key, items in parts["damage"]]
    earned = sum(weights[k] * completion[k] for k in weights)
    retention = math.prod(min(coefficients[i] for i in inst["item_ids"]) for inst in instances)
    final = earned * retention
    result["reward"] = final
    result["rewards"]["strict"] = final
    result.setdefault("reward_formulas", {})
    result["reward_formulas"]["strict"] = (
        "positive_earned * retention (pd-ledger-v1; weights and coefficients from scoring_params.json)")
    result["scoring_ledger"] = {"schema_version": "pd-ledger-v1", "positive_completion": completion,
                                "business_must_haves": parts.get("business_must_haves", {}),
                                "damage_instances": instances, "positive_earned": earned,
                                "retention": retention, "final_score": final}
    result["owner_basis"] = basis
    # The strict settlement above is untouched; the lenient lens only reads it.
    lenient, met = lenient_lens(result["scoring_ledger"], coefficients)
    result.setdefault("rewards", {})["lenient"] = lenient
    result["reward_formulas"]["lenient"] = (
        "1.0 when every item of LENIENT_REQUIRED_ITEMS holds, else 0.0 (source workbook unchanged, no "
        "recorded method reversal, and each required network-design capability meeting its declared "
        "business-usable floor); "
        "settled from the strict scorer's own "
        "per-item results, never from the weighted total")
    result["lenient_detail"] = {"required_items": list(LENIENT_REQUIRED_ITEMS), "met": met,
                                "business_must_haves": result["scoring_ledger"].get("business_must_haves", {})}
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("answer", type=Path)
    parser.add_argument("--source", type=Path, default=None)
    parser.add_argument("--ground-truth", type=Path, default=HERE / "ground_truth.json")
    args = parser.parse_args()
    answer = deliverable(args.answer)
    source = args.source if args.source is not None else default_source()
    if not answer.is_file():
        result = {"reward": 0.0, "rewards": {"strict": 0.0, "lenient": 0.0},
                  "score_type": "constrained_dc_network_workbook", "group_points": {},
                  "diagnostics": {"error": f"no deliverable at {answer}"}}
    else:
        result = score(answer, source, args.ground_truth)
    print(json.dumps(settle(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
