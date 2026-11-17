#!/usr/bin/env python3
"""Mixed program/semantic scorer for the structural-review workbook."""
from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from openpyxl import load_workbook

from semantic_judge import adjudicate


HERE = Path(__file__).resolve().parent
GROUND = json.loads((HERE / "ground_truth.json").read_text(encoding="utf-8"))
EXPECTED = GROUND["checks"]

ALIASES = {
    "row_id": {"check id", "check", "id", "item id", "reference"},
    "subject": {"subject", "member", "item", "review item", "check subject", "description"},
    "status": {"status", "conclusion", "verdict", "result", "disposition"},
    "source": {"source locator", "source", "locator", "evidence location", "report location", "reference location"},
    "observed": {"observed value", "observed", "observation", "value", "source value", "evidence"},
    "criterion": {"governing criterion", "criterion", "expected or limit", "limit", "requirement", "basis"},
    "finding": {"finding", "note", "reason", "explanation", "comment", "review finding"},
    "formula": {"formula", "calculation", "derived value", "working"},
}

DIMENSIONS = {
    "load_arithmetic": (0.04, {"LC-05", "LC-06"}),
    "stability_scope": (0.07, {"LC-01", "LC-02", "LC-03", "LC-04", "LC-07"}),
    "serviceability_limit_application": (0.06, {"SV-01", "SV-02", "SV-03", "SV-04", "SV-05", "SV-06", "CL-01"}),
    "reinforcement_demand_boundary": (0.20, {"RF-01", "RF-02", "RF-03", "RF-04", "RF-05", "RF-06", "RF-07", "RF-08"}),
    "approval_chain_reproducibility": (0.55, {"AP-01", "AP-02", "AP-03", "AP-04", "AP-05", "AP-06", "AP-07", "AP-08", "AP-09"}),
}


def norm_header(value):
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").strip().lower())
    return re.sub(r"\s+", " ", text)


def field_map(values):
    result = {}
    headers = [norm_header(value) for value in values]
    for key, names in ALIASES.items():
        candidates = []
        for position, header in enumerate(headers):
            exact = header in names
            contained = any(name in header or header in name for name in names if header)
            if exact or contained:
                preference = int(exact)
                if key == "source" and ("locator" in header or "location" in header):
                    preference += 2
                candidates.append((preference, position))
        if candidates:
            result[key] = max(candidates)[1]
    return result


def mean(values):
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def candidate_file(target):
    if target.is_dir():
        preferred = target / "review.xlsx"
        if preferred.is_file():
            return preferred
        candidates = sorted(target.glob("*.xlsx"))
        if not candidates:
            raise FileNotFoundError("no xlsx deliverable")
        return candidates[0]
    return target


def safe_workbook(path):
    if not path.is_file() or path.suffix.lower() != ".xlsx":
        raise ValueError("review.xlsx is missing")
    if path.stat().st_size > 50_000_000:
        raise ValueError("review.xlsx exceeds the 50 MB safety limit")
    with zipfile.ZipFile(path) as archive:
        entries = [entry.lower() for entry in archive.namelist()]
        if any("vbaproject" in entry or entry.startswith("xl/externallinks/") for entry in entries):
            raise ValueError("macros and external workbook links are not accepted")


def open_calculated(path):
    """Return formula and calculated-value books without modifying the submission."""
    safe_workbook(path)
    expressions = load_workbook(path, data_only=False, read_only=False)
    values = load_workbook(path, data_only=True, read_only=False)
    formula_cells = [
        (sheet.title, cell.coordinate)
        for sheet in expressions.worksheets
        for row in sheet.iter_rows()
        for cell in row
        if cell.data_type == "f" or (isinstance(cell.value, str) and cell.value.startswith("="))
    ]
    missing_cache = any(values[sheet][coordinate].value is None for sheet, coordinate in formula_cells)
    if not formula_cells or not missing_cache:
        return expressions, values, {
            "engine": "packaged formula cache" if formula_cells else "no formulas",
            "formula_cells": len(formula_cells),
            "submission_modified": False,
        }

    office = shutil.which("libreoffice") or shutil.which("soffice")
    if not office:
        raise RuntimeError("formula caches are missing and LibreOffice is unavailable")
    expressions.close()
    values.close()
    temporary = tempfile.TemporaryDirectory(prefix="sluice-review-recalc-")
    temp = Path(temporary.name)
    source = temp / path.name
    shutil.copy2(path, source)
    out = temp / "out"
    out.mkdir()
    command = [
        office,
        "-env:UserInstallation=" + (temp / "profile").as_uri(),
        "--headless",
        "--norestore",
        "--nolockcheck",
        "--nodefault",
        "--convert-to",
        "xlsx",
        "--outdir",
        str(out),
        str(source),
    ]
    process = subprocess.run(command, capture_output=True, text=True, timeout=180)
    calculated = out / path.name
    if process.returncode or not calculated.is_file():
        temporary.cleanup()
        raise RuntimeError("LibreOffice formula recalculation failed")
    expressions = load_workbook(calculated, data_only=False, read_only=False)
    values = load_workbook(calculated, data_only=True, read_only=False)
    if any(values[sheet][coordinate].value is None for sheet, coordinate in formula_cells):
        expressions.close()
        values.close()
        temporary.cleanup()
        raise RuntimeError("formula recalculation left unresolved cells")
    expressions._calculation_temporary = temporary
    return expressions, values, {
        "engine": subprocess.check_output([office, "--version"], text=True).strip(),
        "formula_cells": len(formula_cells),
        "submission_modified": False,
    }


def load_rows(target):
    target = candidate_file(target)
    book, calculated, calculation = open_calculated(target)
    try:
        raw_sheets = {}
        value_sheets = {}
        for sheet in book.worksheets:
            raw_sheets[sheet.title] = [[cell.value for cell in row] for row in sheet.iter_rows()]
            value_sheet = calculated[sheet.title]
            value_sheets[sheet.title] = [[cell.value for cell in row] for row in value_sheet.iter_rows()]

        best = None
        for sheet, values in raw_sheets.items():
            for header_row, row in enumerate(values[:10]):
                mapping = field_map(row)
                usable = len(set(mapping) & {"row_id", "subject", "source", "observed", "criterion", "finding"})
                if "status" not in mapping or usable < 2:
                    continue
                score_value = len(mapping)
                if best is None or score_value > best[0]:
                    best = (score_value, sheet, values, header_row, mapping)
        if best is None:
            raise ValueError("no review table with a status and evidence fields")

        _, sheet, values, header_row, mapping = best
        cached_values = value_sheets[sheet]
        rows = []
        duplicate_ids = 0
        seen_ids = set()
        status_position = mapping["status"]
        for row_no, row in enumerate(values[header_row + 1 :], header_row + 2):
            item = {key: (row[position] if position < len(row) else None) for key, position in mapping.items()}
            if not any(str(value or "").strip() for value in item.values()):
                continue
            computed_row = cached_values[row_no - 1] if row_no - 1 < len(cached_values) else []
            raw_status = row[status_position] if status_position < len(row) else None
            computed_status = computed_row[status_position] if status_position < len(computed_row) else None
            status_formula = isinstance(raw_status, str) and raw_status.startswith("=")
            if status_formula:
                item["status"] = computed_status
            identifier = str(item.get("row_id") or "").strip()
            if identifier and identifier in seen_ids:
                duplicate_ids += 1
            if identifier:
                seen_ids.add(identifier)
            row_formulas = [
                {"column": position + 1, "expression": value, "calculated": computed_row[position] if position < len(computed_row) else None}
                for position, value in enumerate(row)
                if position != status_position and isinstance(value, str) and value.startswith("=")
            ]
            item.update(
                _row=row_no,
                _sheet=sheet,
                _status_formula=raw_status if status_formula else None,
                _status_resolved=item.get("status"),
                _row_formulas=row_formulas,
            )
            rows.append(item)

        guide_text = "\n".join(
            " | ".join(str(cell) for cell in row if cell is not None)
            for title, sheet_rows in raw_sheets.items()
            if any(key in title.lower() for key in ("readme", "guide", "notes", "legend"))
            for row in sheet_rows
        )
        for item in rows:
            item["_serialized"] = json.dumps(item, ensure_ascii=False, sort_keys=True)
        meta = {
            "review_sheet": sheet,
            "rows": len(rows),
            "duplicates": duplicate_ids,
            "sheet_count": len(book.sheetnames),
            "calculation": calculation,
            "guide_text": guide_text,
        }
        return rows, meta
    finally:
        temporary = getattr(book, "_calculation_temporary", None)
        book.close()
        calculated.close()
        if temporary:
            temporary.cleanup()


def evidence_quality(candidate_rows, semantic_positive):
    return mean(
        [
            float(semantic_positive),
            float(any(str(row.get("source") or "").strip() for row in candidate_rows)),
            float(any(str(row.get("observed") or "").strip() for row in candidate_rows)),
            float(any(str(row.get("finding") or "").strip() for row in candidate_rows)),
        ]
    )


def score(rows, meta):
    candidate_lines = [row["_serialized"] for row in rows]
    candidate_lines.append(json.dumps({"kind": "workbook_guidance", "text": meta["guide_text"]}, ensure_ascii=False, sort_keys=True))
    candidate = "\n".join(candidate_lines)
    semantic = adjudicate(candidate, json.loads((HERE / "semantic_source.json").read_text(encoding="utf-8")))
    by_id = {gold["check_id"]: gold for gold in EXPECTED}
    per_check = []
    selected_by_id = {}

    for gold in EXPECTED:
        identifier = gold["check_id"]
        verdict = semantic["items"][identifier]
        selected = [row for row in rows if any(quote in row["_serialized"] for quote in verdict["quotes"])]
        selected_by_id[identifier] = selected
        semantic_positive = verdict["fraction"] == 1 and bool(selected)
        # The source-bound criterion includes the adopted status. This keeps
        # equivalent professional conclusions and negation handling in the
        # semantic judge instead of duplicating them with a status word list.
        status_correct = semantic_positive
        formula_present = (not gold.get("formula_required")) or any(row.get("_row_formulas") for row in selected)
        evidence = evidence_quality(selected, semantic_positive)
        per_check.append(
            {
                "anchor": identifier,
                "semantic": float(semantic_positive),
                "status": float(status_correct),
                "evidence": round(evidence, 6),
                "formula_required": bool(gold.get("formula_required")),
                "formula_at_calculation_row": bool(formula_present),
                "candidate_rows": [f"{row['_sheet']}!{row['_row']}" for row in selected],
                "semantic_evidence": verdict,
            }
        )

    check_result = {item["anchor"]: item for item in per_check}
    dimensions = {}
    strict = 0.0
    for name, (weight, members) in DIMENSIONS.items():
        value = mean(check_result[identifier]["status"] for identifier in members)
        dimensions[name] = {"weight": weight, "score": round(value, 6)}
        strict += weight * value

    evidence_value = mean(item["evidence"] for item in per_check)
    formula_items = [item for item in per_check if item["formula_required"]]
    formula_placement = mean(item["formula_at_calculation_row"] for item in formula_items)
    guide_quality = float(semantic["items"]["WORKBOOK-GUIDANCE"]["fraction"] == 1)
    closure_value = 0.4 * guide_quality + 0.4 * formula_placement + 0.2 * float(meta["duplicates"] == 0)
    dimensions["evidence_binding"] = {"weight": 0.05, "score": round(evidence_value, 6)}
    dimensions["workbook_closure"] = {"weight": 0.03, "score": round(closure_value, 6)}
    strict += 0.05 * evidence_value + 0.03 * closure_value

    semantic_coverage = mean(item["semantic"] for item in per_check)
    status_correctness = mean(item["status"] for item in per_check)
    traceability = mean(
        float(any(str(row.get("source") or "").strip() and str(row.get("finding") or "").strip() for row in selected_by_id[item["anchor"]]))
        for item in per_check
    )
    review_items = [item for item in per_check if by_id[item["anchor"]]["status"] == "REVIEW"]
    review_preservation = mean(item["status"] for item in review_items)
    workbook_usability = mean([guide_quality, formula_placement, float(meta["duplicates"] == 0)])
    lenient_parts = {
        "semantic_coverage": round(semantic_coverage, 6),
        "traceable_matched_rows": round(traceability, 6),
        "necessary_status_correctness": round(status_correctness, 6),
        "unresolved_state_preservation": round(review_preservation, 6),
        "formula_at_required_calculation_rows": round(formula_placement, 6),
        "workbook_usability": round(workbook_usability, 6),
    }
    lenient = float(
        semantic_coverage == 1.0
        and traceability == 1.0
        and status_correctness == 1.0
        and review_preservation == 1.0
        and formula_placement == 1.0
        and workbook_usability == 1.0
    )
    detail = {
        "meta": meta,
        "semantic_judge": {key: value for key, value in semantic.items() if key not in {"items", "raw"}},
        "matched": sum(item["semantic"] for item in per_check),
        "expected": len(EXPECTED),
        "strict_dimensions": dimensions,
        "lenient_components": lenient_parts,
        "per_check": per_check,
    }
    return min(max(strict, 0.0), 1.0), lenient, detail


def main():
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "/workspace/review.xlsx")
    try:
        rows, meta = load_rows(target)
    except (FileNotFoundError, ValueError, zipfile.BadZipFile) as exc:
        strict = lenient = 0.0
        detail = {"error": str(exc), "matched": 0, "expected": len(EXPECTED)}
    else:
        strict, lenient, detail = score(rows, meta)
    result = {
        "reward": round(strict, 6),
        "rewards": {"strict": round(strict, 6), "lenient": round(lenient, 6)},
        "reward_formulas": {
            "strict": "weighted professional dimensions over source-bound semantic conclusions, formula-resolved statuses, evidence binding, and workbook closure",
            "lenient": "1.0 only when all required conclusions and statuses are correct, traceable, formula-supported where applicable, and documented for handoff",
        },
        "group_points": {name: data["score"] for name, data in detail.get("strict_dimensions", {}).items()},
        "detail": detail,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
