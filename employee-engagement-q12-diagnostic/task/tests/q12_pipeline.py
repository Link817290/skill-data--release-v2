#!/usr/bin/env python3
"""Build the v10 Q12 decision-analysis reference outputs."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime
from math import erfc, sqrt
from pathlib import Path
from statistics import stdev
from typing import Any, Iterable

from xlsx_min import excel_serial_to_date, list_sheets, read_sheet, validate_xlsx, write_xlsx


MIN_CELL = 10
ACTION_N = 20
TARGET_PCT = 0.80
DECLINE_PP = -0.01
YEARS = (2023, 2024)
TIER_ORDER = ("基础支持", "个人贡献", "团队协作", "成长发展")


def as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                pass
    return excel_serial_to_date(value)


def as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(value.strip(), fmt)
            except ValueError:
                pass
    d = excel_serial_to_date(value)
    return datetime(d.year, d.month, d.day) if d else None


def dict_rows(path: Path, sheet: str) -> list[dict[str, Any]]:
    rows = read_sheet(path, sheet)
    if not rows:
        return []
    headers = [str(x).strip() for x in rows[0]]
    out = []
    for row in rows[1:]:
        padded = row + [""] * max(0, len(headers) - len(row))
        out.append({h: padded[i] for i, h in enumerate(headers)})
    return out


def completed_years(start: date, end: date) -> int:
    return end.year - start.year - ((end.month, end.day) < (start.month, start.day))


def age_band(value: int) -> str:
    return "<25" if value < 25 else "25-29" if value < 30 else "30-34" if value < 35 else "35-39" if value < 40 else "40-44" if value < 45 else "45-49" if value < 50 else "50+"


def tenure_band(value: int) -> str:
    return "<1" if value < 1 else "1-2" if value < 3 else "3-4" if value < 5 else "5-9" if value < 10 else "10+"


def mean(values: Iterable[float]) -> float | None:
    vals = list(values)
    return sum(vals) / len(vals) if vals else None


def sample_sd(values: Iterable[float]) -> float | None:
    vals = list(values)
    return stdev(vals) if len(vals) >= 2 else None


def quantile(values: Iterable[float], probability: float) -> float | None:
    vals = sorted(values)
    if not vals:
        return None
    position = (len(vals) - 1) * probability; lower = int(position); upper = min(lower + 1, len(vals) - 1)
    return vals[lower] + (vals[upper] - vals[lower]) * (position - lower)


def load_dictionary(materials: Path) -> tuple[dict[tuple[str, str], str], dict[tuple[str, str], int], dict[str, dict[str, str]], dict[str, str]]:
    crosswalk: dict[tuple[str, str], str] = {}
    meta: dict[str, dict[str, str]] = {}
    for row in dict_rows(materials / "survey_dictionary.xlsx", "item_crosswalk"):
        wave = str(row["wave_code"]); source = str(row["source_item_code"]); canonical = str(row["canonical_item"])
        crosswalk[(wave, source)] = canonical
        meta[canonical] = {
            "text": str(row["item_text"]),
            "tier": str(row["tier"]),
            "trend_role": str(row.get("trend_role", "anchor") or "anchor"),
            "comparability_note": str(row.get("comparability_note", "")),
        }
    scale = {(str(r["wave_code"]), str(r["source_value"])): int(r["score"]) for r in dict_rows(materials / "survey_dictionary.xlsx", "response_scale")}
    registry = {str(r["file_name"]): str(r["wave_code"]) for r in dict_rows(materials / "survey_dictionary.xlsx", "source_registry")}
    return crosswalk, scale, meta, registry


def load_people(materials: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, list[tuple[date | None, str]]]]:
    core = {str(r["person_key"]): r for r in dict_rows(materials / "employee_core.xlsx", "core")}
    snap = {str(r["person_key"]): r for r in dict_rows(materials / "people_snapshot.xlsx", "snapshot")}
    levels: dict[str, list[tuple[date | None, str]]] = defaultdict(list)
    for r in dict_rows(materials / "level_events.xlsx", "level_events"):
        levels[str(r["person_key"])].append((as_date(r["level_effective_date"]), str(r["technical_level"])))
    for key in levels:
        levels[key].sort(key=lambda x: x[0] or date.max)
    return core, snap, levels


def load_bridge(materials: Path) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, str]]:
    bridge = {(str(r["wave_code"]), str(r["survey_token"])): r for r in dict_rows(materials / "identity_bridge.xlsx", "bridge")}
    org_map = {str(r["survey_org"]): str(r["org_calibration_group"]) for r in dict_rows(materials / "population_margins.xlsx", "org_group_map")}
    return bridge, org_map


def calibration_targets(materials: Path) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = defaultdict(dict)
    for r in dict_rows(materials / "population_margins.xlsx", "targets"):
        out[str(r["dimension"])][str(r["category"])] = float(r["target_share"])
    return out


def rake_rows(rows: list[dict[str, Any]], targets: dict[str, dict[str, float]]) -> tuple[dict[str, float], dict[str, Any]]:
    weights = {r["response_key"]: 1.0 for r in rows}
    dimensions = {"org_calibration_group": "calibration_org", "frame_band": "frame_band"}
    for dimension, target in targets.items():
        observed = {str(r[dimensions[dimension]]) for r in rows}
        missing = {category for category, share in target.items() if share > 0 and category not in observed}
        if missing:
            raise ValueError(f"structural zero in {dimension}: {sorted(missing)}")

    def cycles(state: dict[str, float]) -> tuple[int, float]:
        error = 1.0
        for iteration in range(1, 501):
            for dimension, target in targets.items():
                field = dimensions[dimension]; total = sum(state.values())
                current = defaultdict(float)
                for r in rows: current[str(r[field])] += state[r["response_key"]]
                for category, share in target.items():
                    factor = share * total / current[category]
                    for r in rows:
                        if str(r[field]) == category: state[r["response_key"]] *= factor
            total = sum(state.values()); error = 0.0
            for dimension, target in targets.items():
                field = dimensions[dimension]; current = defaultdict(float)
                for r in rows: current[str(r[field])] += state[r["response_key"]]
                error = max(error, max(abs(current[k] / total - v) for k, v in target.items()))
            if error <= 1e-10: return iteration, error
        raise ValueError(f"raking did not converge; error={error}")

    preliminary_iterations, _ = cycles(weights)
    for key in weights: weights[key] = min(3.0, max(0.3, weights[key]))
    post_trim_iterations, error = cycles(weights)
    factor = len(rows) / sum(weights.values())
    for key in weights: weights[key] *= factor
    values = list(weights.values()); total = sum(values); ess = total * total / sum(w * w for w in values)
    return weights, {
        "n": len(rows), "sum_w": total, "min_w": min(values), "max_w": max(values),
        "ess": ess, "design_effect": len(rows) / ess, "margin_error": error,
        "preliminary_iterations": preliminary_iterations, "post_trim_iterations": post_trim_iterations,
    }


def load_raw(materials: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, str]]]:
    crosswalk, scale, item_meta, registry = load_dictionary(materials)
    core, snaps, levels = load_people(materials)
    bridge, org_map = load_bridge(materials)
    raw: list[dict[str, Any]] = []
    for filename, wave in registry.items():
        path = materials / filename
        sheets = list_sheets(path)
        if len(sheets) != 1:
            raise ValueError(f"unexpected survey workbook: {filename}")
        for source_row, row in enumerate(dict_rows(path, sheets[0][0]), 2):
            submitted = as_datetime(row.get("submitted_at"))
            exported = as_datetime(row.get("exported_at"))
            original: dict[str, str] = {}
            scores: dict[str, int | None] = {}
            for column, value in row.items():
                canonical = crosswalk.get((wave, column))
                if canonical:
                    original[canonical] = str(value)
                    scores[canonical] = scale.get((wave, str(value)))
            key = str(row.get("participant_token", "")).strip()
            br = bridge.get((wave, key)); submit_day = submitted.date() if submitted else None
            bridge_temporal = bool(br and submit_day and as_date(br.get("valid_from")) <= submit_day <= as_date(br.get("valid_to")))
            person_key = str(br.get("person_key", "")) if bridge_temporal and br else ""
            allowed_use = str(br.get("allowed_use", "")) if bridge_temporal and br else ""
            frame_band = str(br.get("frame_band", "")) if bridge_temporal and br else ""
            response_key = str(row.get("response_key", "")).strip()
            score_list = [scores.get(f"Q{q:02d}") for q in range(1, 13)]
            hard = bool(response_key and key and submitted and row.get("survey_org") and all(x in range(1, 6) for x in score_list))
            straight = hard and len(set(score_list)) == 1
            cr = core.get(person_key); sr = snaps.get(person_key)
            hire = as_date(cr.get("hire_date")) if cr else None
            end = as_date(cr.get("end_date")) if cr else None
            birth = as_date(cr.get("birth_date")) if cr else None
            temporal = bool(cr and submit_day and ((hire and hire > submit_day) or (end and end < submit_day)))
            link = "bridge_unresolved" if not person_key else "unmatched" if not cr else "time_impossible" if temporal else "time_usable"
            personnel_allowed = allowed_use in {"personnel_only", "personnel_and_panel"}
            panel_allowed = allowed_use == "personnel_and_panel" and str(br.get("match_grade", "")) == "verified" if br else False
            attr_usable = bool(personnel_allowed and cr and submit_day and not temporal)
            age_years = completed_years(birth, submit_day) if attr_usable and birth else None
            tenure_years = completed_years(hire, submit_day) if attr_usable and hire else None
            level = ""
            if attr_usable:
                eligible = [(d, v) for d, v in levels.get(key, []) if d and d <= submit_day and v]
                if eligible:
                    level = eligible[-1][1]
            raw.append({
                "source_file": filename, "source_row": source_row, "wave": wave,
                "year": submit_day.year if submit_day else None, "response_key": response_key,
                "token": key, "person_key": person_key, "bridge_temporal": bridge_temporal,
                "match_grade": str(br.get("match_grade", "")) if br else "", "allowed_use": allowed_use,
                "personnel_allowed": personnel_allowed, "panel_allowed": panel_allowed,
                "frame_band": frame_band, "calibration_org": org_map.get(str(row.get("survey_org", "")), ""),
                "submitted_at": str(row.get("submitted_at", "")),
                "survey_org": str(row.get("survey_org", "")), "export_batch": str(row.get("export_batch", "")),
                "exported_at": exported, "original": original, "scores": score_list,
                "hard": hard, "straight": straight, "core_link": link, "attr_usable": attr_usable,
                "org_snapshot": str(sr.get("org_snapshot", "")) if sr else "",
                "snapshot_as_of": str(sr.get("snapshot_as_of", "")) if sr else "",
                "department_conflict": bool(sr and str(sr.get("org_snapshot", "")) and str(sr.get("org_snapshot", "")) != str(row.get("survey_org", ""))),
                "location": str(sr.get("location_snapshot", "")) if attr_usable and sr else "",
                "gender": str(sr.get("gender_snapshot", "")) if attr_usable and sr else "",
                "worker_class": str(sr.get("worker_class_snapshot", "")) if attr_usable and sr else "",
                "job_family": str(sr.get("job_family_snapshot", "")) if attr_usable and sr else "",
                "status_snapshot": str(sr.get("employment_status_snapshot", "")) if attr_usable and sr else "",
                "technical_level": level,
                "age_years": age_years, "tenure_years": tenure_years,
                "age": age_band(age_years) if age_years is not None else "",
                "tenure": tenure_band(tenure_years) if tenure_years is not None else "",
            })

    by_response: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in raw:
        by_response[row["response_key"]].append(row)
    for key, rows in by_response.items():
        signatures = {(r["token"], r["submitted_at"], r["survey_org"], tuple(r["scores"])) for r in rows}
        if len(signatures) != 1:
            raise ValueError(f"conflicting batch copies for {key}")
        chosen = max(rows, key=lambda r: (r["exported_at"] or datetime.min, r["source_file"], r["source_row"]))
        for row in rows:
            row["duplicate_export"] = len(rows) > 1
            row["canonical"] = row is chosen
            row["main"] = bool(row is chosen and row["hard"])
            row["sensitivity"] = bool(row is chosen and row["hard"] and not row["straight"])
            row["calibration_adopted"] = bool(row is chosen and row["hard"] and row["frame_band"] and row["calibration_org"])
            row["hard_reason"] = "" if row["hard"] else "missing_or_unmapped_required_field"
    targets = calibration_targets(materials)
    for wave in ("alpha", "beta"):
        eligible = [r for r in raw if r["wave"] == wave and r["calibration_adopted"]]
        weights, _ = rake_rows(eligible, targets)
        for r in raw:
            if r["wave"] == wave: r["calibration_weight"] = weights.get(r["response_key"], "") if r["canonical"] else ""
    return raw, item_meta


def adopted(raw: list[dict[str, Any]], sensitivity: bool = False) -> list[dict[str, Any]]:
    key = "sensitivity" if sensitivity else "main"
    return [r for r in raw if r[key]]


def metric(rows: list[dict[str, Any]], questions: list[int] | None = None) -> dict[str, Any]:
    qidx = [q - 1 for q in (questions or range(1, 13))]
    vals = [float(r["scores"][i]) for r in rows for i in qidx]
    m = mean(vals)
    return {
        "n": len(rows), "responses": len(vals), "mean": m, "pct": m / 5 if m is not None else None,
        "top_count": sum(v == 5 for v in vals), "top_rate": sum(v == 5 for v in vals) / len(vals) if vals else None,
        "sd": sample_sd(vals),
    }


def weighted_metric(rows: list[dict[str, Any]], questions: list[int] | None = None) -> dict[str, Any]:
    qidx = [q - 1 for q in (questions or range(1, 13))]
    numerator = sum(float(r["calibration_weight"]) * float(r["scores"][i]) for r in rows for i in qidx)
    denominator = sum(float(r["calibration_weight"]) for r in rows for _ in qidx)
    value5 = numerator / denominator if denominator else None
    return {"n": len(rows), "sum_w": sum(float(r["calibration_weight"]) for r in rows), "mean": value5, "pct": value5 / 5 if value5 is not None else None}


def scope_rows(rows: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    return [(str(y), [r for r in rows if r["year"] == y]) for y in YEARS] + [("combined", rows)]


def tier_questions(item_meta: dict[str, dict[str, str]], tier: str) -> list[int]:
    return [q for q in range(1, 13) if item_meta[f"Q{q:02d}"]["tier"] == tier]


def clean_book(raw: list[dict[str, Any]], item_meta: dict[str, dict[str, str]]) -> list[tuple[str, list[list[Any]]]]:
    base = ["source_file", "source_row", "export_batch", "wave", "year", "response_key", "survey_token", "person_key", "submitted_at", "survey_org"]
    qorig = [f"Q{q:02d}_source_value" for q in range(1, 13)]
    qscores = [f"Q{q:02d}_score" for q in range(1, 13)]
    tail = [
        "hard_eligible", "hard_reason", "straightline_soft_flag", "duplicate_export_flag", "canonical_export_record",
        "main_adopted", "sensitivity_adopted", "bridge_temporally_valid", "bridge_match_grade", "bridge_allowed_use",
        "personnel_use_allowed", "panel_use_allowed", "frame_band", "org_calibration_group", "calibration_adopted", "final_calibration_weight",
        "core_link_status", "personnel_attributes_usable",
        "org_snapshot_2025", "snapshot_as_of", "survey_vs_snapshot_org_conflict", "location_snapshot_2025",
        "gender_snapshot_2025", "worker_class_snapshot_2025", "job_family_snapshot_2025", "status_snapshot_2025",
        "technical_level_at_submission", "age_band_at_submission", "tenure_band_at_submission",
    ]
    ledger = [base + qorig + qscores + tail]
    for r in sorted(raw, key=lambda x: (x["source_file"], x["source_row"])):
        ledger.append([
            r["source_file"], r["source_row"], r["export_batch"], r["wave"], r["year"], r["response_key"], r["token"], r["person_key"], r["submitted_at"], r["survey_org"],
            *[r["original"].get(f"Q{q:02d}", "") for q in range(1, 13)], *r["scores"],
            r["hard"], r["hard_reason"], r["straight"], r["duplicate_export"], r["canonical"], r["main"], r["sensitivity"],
            r["bridge_temporal"], r["match_grade"], r["allowed_use"], r["personnel_allowed"], r["panel_allowed"],
            r["frame_band"], r["calibration_org"], r["calibration_adopted"], r["calibration_weight"],
            r["core_link"], r["attr_usable"], r["org_snapshot"], r["snapshot_as_of"], r["department_conflict"],
            r["location"], r["gender"], r["worker_class"], r["job_family"], r["status_snapshot"], r["technical_level"], r["age"], r["tenure"],
        ])

    audit = [["metric", "alpha", "beta", "combined"]]
    for label, fn in (
        ("raw_export_rows", lambda rs: len(rs)),
        ("distinct_response_keys", lambda rs: len({r["response_key"] for r in rs})),
        ("overlap_extra_rows", lambda rs: len(rs) - len({r["response_key"] for r in rs})),
        ("hard_eligible_logical", lambda rs: sum(r["canonical"] and r["hard"] for r in rs)),
        ("straightline_logical", lambda rs: sum(r["canonical"] and r["straight"] for r in rs)),
        ("main_adopted", lambda rs: sum(r["main"] for r in rs)),
        ("sensitivity_adopted", lambda rs: sum(r["sensitivity"] for r in rs)),
    ):
        wave_rows = [[r for r in raw if r["wave"] == w] for w in ("alpha", "beta")]
        audit.append([label, fn(wave_rows[0]), fn(wave_rows[1]), fn(raw)])
    audit.extend([
        ["unmatched_logical", sum(r["canonical"] and r["core_link"] == "unmatched" for r in raw), "", ""],
        ["time_impossible_logical", sum(r["canonical"] and r["core_link"] == "time_impossible" for r in raw), "", ""],
        ["survey_snapshot_org_conflicts", sum(r["canonical"] and r["department_conflict"] for r in raw), "", ""],
    ])
    dictionary = [["canonical_item", "item_text", "tier", "trend_role", "comparability_note"]] + [[q, item_meta[q]["text"], item_meta[q]["tier"], item_meta[q]["trend_role"], item_meta[q]["comparability_note"]] for q in sorted(item_meta)]
    rules = [["state", "definition"],
        ["raw export row", "every row in every batch export; overlapping copies remain auditable"],
        ["canonical export record", "latest exported copy for a response_key after content equality check"],
        ["hard eligible", "identity, time, organization and all twelve mapped answers are present"],
        ["soft anomaly", "all twelve canonical scores are equal; retained in main population"],
        ["personnel usable", "dated core record exists and hire/end dates permit the submission date"],
        ["snapshot attribute", "describes 2025-08-31, not silently interpreted as historical"],
        ["panel identity", "requires a temporally valid verified bridge row whose allowed_use includes panel"],
        ["calibration weight", "raked to both fixed-reference margins, trimmed, reraked, and normalized within wave"],
    ]
    return [("raw_export_ledger", ledger), ("ingestion_audit", audit), ("item_dictionary", dictionary), ("state_dictionary", rules)]


def main_tables(raw: list[dict[str, Any]], item_meta: dict[str, dict[str, str]]) -> dict[str, list[list[Any]]]:
    main = adopted(raw); sens = adopted(raw, True)
    company = [["population", "scope", "n_submissions", "n_responses", "mean_5", "score_pct", "top_count", "top_rate", "sample_sd_raw"]]
    item = [["population", "scope", "item", "tier", "n", "mean_5", "score_pct", "top_count", "top_rate", "sample_sd_raw"]]
    tier = [["population", "scope", "tier", "members", "n_submissions", "n_responses", "mean_5", "score_pct", "top_rate", "sample_sd_raw"]]
    for pop, rows in (("main", main), ("straightline_excluded", sens)):
        for scope, subset in scope_rows(rows):
            m = metric(subset); company.append([pop, scope, m["n"], m["responses"], m["mean"], m["pct"], m["top_count"], m["top_rate"], m["sd"]])
            for q in range(1, 13):
                z = metric(subset, [q]); item.append([pop, scope, f"Q{q:02d}", item_meta[f"Q{q:02d}"]["tier"], z["n"], z["mean"], z["pct"], z["top_count"], z["top_rate"], z["sd"]])
            for t in TIER_ORDER:
                qs = tier_questions(item_meta, t); z = metric(subset, qs)
                tier.append([pop, scope, t, ",".join(f"Q{q:02d}" for q in qs), z["n"], z["responses"], z["mean"], z["pct"], z["top_rate"], z["sd"]])
    return {"company_period": company, "item_period": item, "tier_period": tier}


def calibration_tables(raw: list[dict[str, Any]], materials: Path, item_meta: dict[str, dict[str, str]]) -> dict[str, list[list[Any]]]:
    targets = calibration_targets(materials)
    diagnostics = [["wave", "n", "sum_w", "min_w", "p25_w", "median_w", "p75_w", "max_w", "weight_cv", "kish_ess", "design_effect", "max_margin_error", "preliminary_iterations", "post_trim_iterations", "converged"]]
    margins = [["wave", "dimension", "category", "target_share", "unweighted_share", "weighted_share", "absolute_error"]]
    company = [["estimand", "wave", "n", "sum_w", "mean_5", "score_pct", "change_vs_alpha_pct"]]
    items = [["estimand", "wave", "item", "tier", "n", "sum_w", "mean_5", "score_pct"]]
    estimates: dict[str, float] = {}
    dimension_fields = {"org_calibration_group": "calibration_org", "frame_band": "frame_band"}
    for wave in ("alpha", "beta"):
        rows = [r for r in raw if r["wave"] == wave and r["calibration_adopted"]]
        weights, diag = rake_rows(rows, targets)
        wv = list(weights.values()); wm = sum(wv) / len(wv); cv = sample_sd(wv) / wm
        diagnostics.append([wave, diag["n"], diag["sum_w"], diag["min_w"], quantile(wv, .25), quantile(wv, .5), quantile(wv, .75), diag["max_w"], cv, diag["ess"], diag["design_effect"], diag["margin_error"], diag["preliminary_iterations"], diag["post_trim_iterations"], True])
        for dimension, target in targets.items():
            field = dimension_fields[dimension]
            for category, share in sorted(target.items()):
                unweighted = sum(str(r[field]) == category for r in rows) / len(rows)
                weighted = sum(weights[r["response_key"]] for r in rows if str(r[field]) == category) / sum(weights.values())
                margins.append([wave, dimension, category, share, unweighted, weighted, abs(weighted - share)])
        numerator = sum(weights[r["response_key"]] * sum(r["scores"]) for r in rows)
        denominator = 12 * sum(weights.values()); mean5 = numerator / denominator; estimates[wave] = mean5 / 5
        company.append(["fixed_reference", wave, len(rows), sum(weights.values()), mean5, mean5 / 5, ""])
        for q in range(1, 13):
            qmean = sum(weights[r["response_key"]] * r["scores"][q - 1] for r in rows) / sum(weights.values())
            items.append(["fixed_reference", wave, f"Q{q:02d}", item_meta[f"Q{q:02d}"]["tier"], len(rows), sum(weights.values()), qmean, qmean / 5])
    company[2][-1] = estimates["beta"] - estimates["alpha"]
    company.append(["fixed_reference", "change", "", "", "", estimates["beta"] - estimates["alpha"], estimates["beta"] - estimates["alpha"]])
    return {"calibration_diagnostics": diagnostics, "calibration_margins": margins, "calibrated_company": company, "calibrated_items": items}


def ipf_unbounded(rows: list[dict[str, Any]], targets: dict[str, dict[str, float]]) -> dict[str, float]:
    """Unbounded IPF used as a declared weight-treatment sensitivity."""
    weights = {r["response_key"]: 1.0 for r in rows}
    fields = {"org_calibration_group": "calibration_org", "frame_band": "frame_band"}
    for _ in range(500):
        for dimension, target in targets.items():
            field = fields[dimension]; total = sum(weights.values())
            current = defaultdict(float)
            for row in rows:
                current[str(row[field])] += weights[row["response_key"]]
            if any(share > 0 and current[category] == 0 for category, share in target.items()):
                raise ValueError(f"structural zero in {dimension}")
            for category, share in target.items():
                factor = share * total / current[category]
                for row in rows:
                    if str(row[field]) == category:
                        weights[row["response_key"]] *= factor
        total = sum(weights.values()); error = 0.0
        for dimension, target in targets.items():
            current = defaultdict(float); field = fields[dimension]
            for row in rows:
                current[str(row[field])] += weights[row["response_key"]]
            error = max(error, *(abs(current[k] / total - v) for k, v in target.items()))
        if error <= 1e-10:
            factor = len(rows) / total
            return {key: value * factor for key, value in weights.items()}
    raise ValueError("unbounded IPF did not converge")


def weighted_pct(rows: list[dict[str, Any]], weights: dict[str, float], questions: list[int]) -> float:
    numerator = sum(weights[r["response_key"]] * sum(r["scores"][q - 1] for q in questions) for r in rows)
    denominator = 5 * len(questions) * sum(weights[r["response_key"]] for r in rows)
    return numerator / denominator


def unweighted_pct(rows: list[dict[str, Any]], questions: list[int]) -> float:
    return sum(sum(r["scores"][q - 1] for q in questions) for r in rows) / (5 * len(questions) * len(rows))


def bh_adjust(p_values: list[float]) -> list[float]:
    order = sorted(range(len(p_values)), key=lambda i: p_values[i])
    adjusted = [1.0] * len(p_values); running = 1.0; m = len(p_values)
    for rank_index in range(m - 1, -1, -1):
        original = order[rank_index]; rank = rank_index + 1
        running = min(running, p_values[original] * m / rank)
        adjusted[original] = min(1.0, running)
    return adjusted


def advanced_tables(raw: list[dict[str, Any]], materials: Path, item_meta: dict[str, dict[str, str]]) -> dict[str, list[list[Any]]]:
    """Primary anchor estimand, repeated-group uncertainty and screening audit."""
    targets = calibration_targets(materials)
    anchors = [q for q in range(1, 13) if item_meta[f"Q{q:02d}"]["trend_role"] == "anchor"]
    full = list(range(1, 13))
    groups = {str(r["response_key"]): int(r["variance_group"]) for r in dict_rows(materials / "variance_design.xlsx", "repeated_groups")}
    wave_rows = {wave: [r for r in raw if r["wave"] == wave and r["calibration_adopted"]] for wave in ("alpha", "beta")}
    final_weights = {wave: rake_rows(rows, targets)[0] for wave, rows in wave_rows.items()}
    primary = {wave: weighted_pct(wave_rows[wave], final_weights[wave], anchors) for wave in wave_rows}

    replicate_rows = [["variance_group", "alpha_n", "beta_n", "alpha_anchor_pct", "beta_anchor_pct", "change_pct", "converged"]]
    replicate_change: list[float] = []
    item_replicates: dict[int, list[float]] = defaultdict(list)
    for group in range(1, 21):
        kept = {wave: [r for r in rows if groups[r["response_key"]] != group] for wave, rows in wave_rows.items()}
        weights = {wave: rake_rows(rows, targets)[0] for wave, rows in kept.items()}
        estimates = {wave: weighted_pct(kept[wave], weights[wave], anchors) for wave in kept}
        change = estimates["beta"] - estimates["alpha"]; replicate_change.append(change)
        replicate_rows.append([group, len(kept["alpha"]), len(kept["beta"]), estimates["alpha"], estimates["beta"], change, True])
        for q in full:
            item_replicates[q].append(weighted_pct(kept["beta"], weights["beta"], [q]) - weighted_pct(kept["alpha"], weights["alpha"], [q]))

    center = mean(replicate_change)
    variance = 19 / 20 * sum((value - center) ** 2 for value in replicate_change)
    se = sqrt(variance); change = primary["beta"] - primary["alpha"]
    primary_table = [["estimand", "item_set", "alpha_n", "beta_n", "alpha_pct", "beta_pct", "change_pct", "jackknife_se", "normal_ci_low", "normal_ci_high", "variance_groups"],
        ["fixed_reference_primary", ",".join(f"Q{q:02d}" for q in anchors), len(wave_rows["alpha"]), len(wave_rows["beta"]), primary["alpha"], primary["beta"], change, se, change - 1.96 * se, change + 1.96 * se, 20]]

    item_records = []
    p_values = []
    for q in full:
        a = weighted_pct(wave_rows["alpha"], final_weights["alpha"], [q]); b = weighted_pct(wave_rows["beta"], final_weights["beta"], [q]); diff = b - a
        rep = item_replicates[q]; rep_center = mean(rep); item_se = sqrt(19 / 20 * sum((x - rep_center) ** 2 for x in rep))
        z = diff / item_se if item_se else 0.0; p = erfc(abs(z) / sqrt(2)); p_values.append(p)
        item_records.append([f"Q{q:02d}", item_meta[f"Q{q:02d}"]["trend_role"], a, b, diff, item_se, z, p])
    q_values = bh_adjust(p_values)
    multiplicity = [["item", "trend_role", "alpha_pct", "beta_pct", "change_pct", "jackknife_se", "z", "p_two_sided", "bh_q", "below_80", "decline_1pp", "q_lt_0_10"]]
    for row, q_value in zip(item_records, q_values):
        multiplicity.append(row + [q_value, row[3] < 0.8, row[4] <= -0.01, q_value < 0.10])

    scenarios = [["scenario", "population", "item_set", "weighting", "alpha_n", "beta_n", "alpha_pct", "beta_pct", "change_pct", "direction"]]
    def add_scenario(name: str, populations: dict[str, list[dict[str, Any]]], questions: list[int], weighting: str) -> None:
        if weighting == "unweighted":
            values = {w: unweighted_pct(populations[w], questions) for w in populations}
        else:
            maker = ipf_unbounded if weighting == "unbounded_ipf" else lambda rows, t: rake_rows(rows, t)[0]
            values = {w: weighted_pct(populations[w], maker(populations[w], targets), questions) for w in populations}
        delta = values["beta"] - values["alpha"]
        population = "straightline_excluded" if "straightline" in name else "main"
        scenarios.append([name, population, ",".join(f"Q{q:02d}" for q in questions), weighting, len(populations["alpha"]), len(populations["beta"]), values["alpha"], values["beta"], delta, "up" if delta > 0 else "down" if delta < 0 else "flat"])
    add_scenario("full_unweighted", wave_rows, full, "unweighted")
    add_scenario("anchor_unweighted", wave_rows, anchors, "unweighted")
    add_scenario("full_fixed_reference", wave_rows, full, "reviewed_final_ipf")
    add_scenario("anchor_fixed_reference_primary", wave_rows, anchors, "reviewed_final_ipf")
    add_scenario("anchor_unbounded_weights", wave_rows, anchors, "unbounded_ipf")
    sens_rows = {wave: [r for r in raw if r["wave"] == wave and r["sensitivity"] and r["frame_band"] and r["calibration_org"]] for wave in ("alpha", "beta")}
    add_scenario("anchor_straightline_excluded", sens_rows, anchors, "reviewed_final_ipf")

    panel_rows = [r for r in adopted(raw) if r["panel_allowed"] and r["person_key"]]
    by_person_wave = {(r["person_key"], r["wave"]): r for r in panel_rows}
    people = sorted({p for p, _ in by_person_wave if (p, "alpha") in by_person_wave and (p, "beta") in by_person_wave})
    panel_deltas = [unweighted_pct([by_person_wave[(p, "beta")]], anchors) - unweighted_pct([by_person_wave[(p, "alpha")]], anchors) for p in people]
    panel_delta = mean(panel_deltas); panel_sd = sample_sd(panel_deltas); panel_se = panel_sd / sqrt(len(people))
    panel_anchor = [["metric", "value", "unit"],
        ["panel_n", len(people), "people"],
        ["alpha_anchor_pct", mean(unweighted_pct([by_person_wave[(p, "alpha")]], anchors) for p in people), "proportion"],
        ["beta_anchor_pct", mean(unweighted_pct([by_person_wave[(p, "beta")]], anchors) for p in people), "proportion"],
        ["paired_change_pct", panel_delta, "proportion"],
        ["person_delta_sd", panel_sd, "proportion"],
        ["person_delta_se", panel_se, "proportion"],
        ["normal_ci_low", panel_delta - 1.96 * panel_se, "proportion"],
        ["normal_ci_high", panel_delta + 1.96 * panel_se, "proportion"]]

    all_main = adopted(raw)
    repeated = set(people)
    cohorts = {}
    for wave in ("alpha", "beta"):
        cohorts[(wave, "repeat")] = [r for r in all_main if r["wave"] == wave and r["panel_allowed"] and r["person_key"] in repeated]
        cohorts[(wave, "nonrepeat")] = [r for r in all_main if r["wave"] == wave and not (r["panel_allowed"] and r["person_key"] in repeated)]
    shares = {(wave, cohort): len(cohorts[(wave, cohort)]) / len([r for r in all_main if r["wave"] == wave]) for wave in ("alpha", "beta") for cohort in ("repeat", "nonrepeat")}
    means = {(wave, cohort): unweighted_pct(cohorts[(wave, cohort)], anchors) for wave in ("alpha", "beta") for cohort in ("repeat", "nonrepeat")}
    within = sum((shares[("alpha", c)] + shares[("beta", c)]) / 2 * (means[("beta", c)] - means[("alpha", c)]) for c in ("repeat", "nonrepeat"))
    composition = sum((means[("alpha", c)] + means[("beta", c)]) / 2 * (shares[("beta", c)] - shares[("alpha", c)]) for c in ("repeat", "nonrepeat"))
    cross = unweighted_pct(wave_rows["beta"], anchors) - unweighted_pct(wave_rows["alpha"], anchors)
    anchor_decomp = [["component", "value_pct", "definition"],
        ["cross_section_anchor_change", cross, "beta minus alpha anchor respondent estimate"],
        ["within_component", within, "symmetric Kitagawa within-cohort component"],
        ["composition_component", composition, "symmetric Kitagawa cohort-share component"],
        ["reconciliation_error", cross - within - composition, "must be zero within tolerance"]]

    return {"primary_trend": primary_table, "jackknife_replicates": replicate_rows, "multiplicity_items": multiplicity, "sensitivity_matrix": scenarios, "panel_anchor": panel_anchor, "anchor_decomposition": anchor_decomp}


def reliability(rows: list[dict[str, Any]], weights: dict[str, float], questions: list[int]) -> float:
    total_w = sum(weights[r["response_key"]] for r in rows); k = len(questions)
    item_means = [sum(weights[r["response_key"]] * r["scores"][q - 1] for r in rows) / total_w for q in questions]
    item_vars = [sum(weights[r["response_key"]] * (r["scores"][q - 1] - item_means[i]) ** 2 for r in rows) / total_w for i, q in enumerate(questions)]
    totals = [sum(r["scores"][q - 1] for q in questions) for r in rows]
    total_mean = sum(weights[r["response_key"]] * value for r, value in zip(rows, totals)) / total_w
    total_var = sum(weights[r["response_key"]] * (value - total_mean) ** 2 for r, value in zip(rows, totals)) / total_w
    return k / (k - 1) * (1 - sum(item_vars) / total_var)


def corrected_item_total(rows: list[dict[str, Any]], weights: dict[str, float], question: int, questions: list[int]) -> float:
    total_w = sum(weights[r["response_key"]] for r in rows)
    x = [r["scores"][question - 1] for r in rows]; y = [sum(r["scores"][q - 1] for q in questions if q != question) for r in rows]
    mx = sum(w * v for w, v in zip((weights[r["response_key"]] for r in rows), x)) / total_w
    my = sum(w * v for w, v in zip((weights[r["response_key"]] for r in rows), y)) / total_w
    cov = sum(weights[r["response_key"]] * (a - mx) * (b - my) for r, a, b in zip(rows, x, y)) / total_w
    vx = sum(weights[r["response_key"]] * (a - mx) ** 2 for r, a in zip(rows, x)) / total_w
    vy = sum(weights[r["response_key"]] * (b - my) ** 2 for r, b in zip(rows, y)) / total_w
    return cov / sqrt(vx * vy)


def v9_quality_tables(raw: list[dict[str, Any]], materials: Path, item_meta: dict[str, dict[str, str]]) -> dict[str, list[list[Any]]]:
    """Psychometric stability and small-domain decision diagnostics."""
    targets = calibration_targets(materials); anchors = [q for q in range(1, 13) if item_meta[f"Q{q:02d}"]["trend_role"] == "anchor"]
    groups = {str(r["response_key"]): int(r["variance_group"]) for r in dict_rows(materials / "variance_design.xlsx", "repeated_groups")}
    wave_rows = {w: [r for r in raw if r["wave"] == w and r["calibration_adopted"]] for w in ("alpha", "beta")}
    full_weights = {w: rake_rows(rows, targets)[0] for w, rows in wave_rows.items()}

    summary = [["wave", "n", "items", "weighted_cronbach_alpha"]]
    deleted = [["wave", "deleted_item", "items_remaining", "alpha_if_deleted", "corrected_item_total_correlation"]]
    full_alpha = {}
    for wave in ("alpha", "beta"):
        full_alpha[wave] = reliability(wave_rows[wave], full_weights[wave], anchors)
        summary.append([wave, len(wave_rows[wave]), ",".join(f"Q{q:02d}" for q in anchors), full_alpha[wave]])
        for q in anchors:
            remain = [x for x in anchors if x != q]
            deleted.append([wave, f"Q{q:02d}", len(remain), reliability(wave_rows[wave], full_weights[wave], remain), corrected_item_total(wave_rows[wave], full_weights[wave], q, anchors)])

    rep = [["variance_group", "alpha_n", "beta_n", "alpha_reliability", "beta_reliability", "reliability_change", "converged"]]
    rep_changes = []; replicate_state = []
    for group in range(1, 21):
        kept = {w: [r for r in rows if groups[r["response_key"]] != group] for w, rows in wave_rows.items()}
        weights = {w: rake_rows(rows, targets)[0] for w, rows in kept.items()}
        values = {w: reliability(kept[w], weights[w], anchors) for w in kept}; change = values["beta"] - values["alpha"]
        rep.append([group, len(kept["alpha"]), len(kept["beta"]), values["alpha"], values["beta"], change, True]); rep_changes.append(change); replicate_state.append((kept, weights))
    center = mean(rep_changes); se = sqrt(19 / 20 * sum((x - center) ** 2 for x in rep_changes)); delta = full_alpha["beta"] - full_alpha["alpha"]
    change_table = [["metric", "value"], ["alpha_reliability", full_alpha["alpha"]], ["beta_reliability", full_alpha["beta"]], ["reliability_change", delta], ["replicate_center", center], ["jackknife_se", se], ["normal_ci_low", delta - 1.96 * se], ["normal_ci_high", delta + 1.96 * se]]

    publishable = sorted(org for org in {r["survey_org"] for r in adopted(raw)} if all(sum(r["wave"] == w and r["survey_org"] == org for r in adopted(raw)) >= 20 for w in ("alpha", "beta")))
    direct = {}; org_reps = defaultdict(list)
    for org in publishable:
        estimates = {w: weighted_pct([r for r in wave_rows[w] if r["survey_org"] == org], full_weights[w], anchors) for w in ("alpha", "beta")}
        direct[org] = estimates["beta"] - estimates["alpha"]
    for kept, weights in replicate_state:
        for org in publishable:
            estimates = {w: weighted_pct([r for r in kept[w] if r["survey_org"] == org], weights[w], anchors) for w in ("alpha", "beta")}
            org_reps[org].append(estimates["beta"] - estimates["alpha"])
    org_se = {org: sqrt(19 / 20 * sum((x - mean(org_reps[org])) ** 2 for x in org_reps[org])) for org in publishable}
    company_change = weighted_pct(wave_rows["beta"], full_weights["beta"], anchors) - weighted_pct(wave_rows["alpha"], full_weights["alpha"], anchors)
    between = sum((direct[o] - mean(direct.values())) ** 2 for o in publishable) / max(1, len(publishable) - 1)
    tau2 = between
    max_t = []
    for g in range(20):
        max_t.append(max(sqrt(19) * abs((org_reps[o][g] - mean(org_reps[o])) / org_se[o]) for o in publishable if org_se[o] > 0))
    simultaneous_critical = sorted(max_t)[18]
    org_table = [["survey_org", "alpha_n", "beta_n", "direct_change_pct", "jackknife_se", "tau2", "shrinkage_factor", "eb_change_pct", "simultaneous_critical", "sim_ci_low", "sim_ci_high"]]
    for org in publishable:
        lam = tau2 / (tau2 + org_se[org] ** 2) if tau2 else 0.0; eb = company_change + lam * (direct[org] - company_change)
        org_table.append([org, sum(r["survey_org"] == org for r in wave_rows["alpha"]), sum(r["survey_org"] == org for r in wave_rows["beta"]), direct[org], org_se[org], tau2, lam, eb, simultaneous_critical, direct[org] - simultaneous_critical * org_se[org], direct[org] + simultaneous_critical * org_se[org]])
    org_rep = [["variance_group", "survey_org", "replicate_change_pct"]] + [[g + 1, org, org_reps[org][g]] for g in range(20) for org in publishable]
    org_method = [["metric", "value"], ["publishable_orgs", len(publishable)], ["company_anchor_change", company_change], ["empirical_between_org_variance_tau2", tau2], ["mean_sampling_variance", mean(org_se[o] ** 2 for o in publishable)], ["max_t_95_empirical_critical", simultaneous_critical]]
    eligible_panel = [r for r in adopted(raw) if r["panel_allowed"] and r["person_key"]]
    by_person_wave = {(r["person_key"], r["wave"]): r for r in eligible_panel}
    repeat_people = {p for p, _ in by_person_wave if (p, "alpha") in by_person_wave and (p, "beta") in by_person_wave}
    selection = [["wave", "cohort", "n", "anchor_mean_pct", "difference_panel_minus_nonpanel"]]
    selection_means = {}
    for wave in ("alpha", "beta"):
        panel_members = [r for r in wave_rows[wave] if r["panel_allowed"] and r["person_key"] in repeat_people]
        nonpanel = [r for r in wave_rows[wave] if not (r["panel_allowed"] and r["person_key"] in repeat_people)]
        selection_means[(wave, "strict_panel")] = unweighted_pct(panel_members, anchors); selection_means[(wave, "nonpanel")] = unweighted_pct(nonpanel, anchors)
        difference = selection_means[(wave, "strict_panel")] - selection_means[(wave, "nonpanel")]
        selection.extend([[wave, "strict_panel", len(panel_members), selection_means[(wave, "strict_panel")], difference], [wave, "nonpanel", len(nonpanel), selection_means[(wave, "nonpanel")], difference]])
    return {"reliability_summary": summary, "reliability_deleted": deleted, "reliability_jackknife": rep, "reliability_change": change_table, "org_small_domain": org_table, "org_replicates": org_rep, "org_shrinkage_method": org_method, "panel_selection": selection}


def panel_tables(raw: list[dict[str, Any]]) -> dict[str, list[list[Any]]]:
    main = [r for r in adopted(raw) if r["panel_allowed"] and r["person_key"]]
    by_person_year = {(r["person_key"], r["year"]): r for r in main}
    people = sorted({k for k, _ in by_person_year})
    repeat = [p for p in people if all((p, y) in by_person_year for y in YEARS)]
    deltas = []
    detail = [["person_key", "mean_2023", "mean_2024", "delta_5", "direction_gt_0_1"]]
    for p in repeat:
        m23 = mean(by_person_year[(p, 2023)]["scores"]); m24 = mean(by_person_year[(p, 2024)]["scores"]); d = m24 - m23
        deltas.append(d)
        direction = "improved" if d > 0.1 else "declined" if d < -0.1 else "stable"
        detail.append([p, m23, m24, d, direction])
    dm = mean(deltas); dsd = sample_sd(deltas); se = dsd / (len(deltas) ** 0.5)
    panel = [["metric", "value", "definition"],
        ["repeat_people", len(repeat), "same verified panel-allowed person_key has one adopted logical response in both periods"],
        ["paired_mean_2023", mean(mean(by_person_year[(p, 2023)]["scores"]) for p in repeat), "mean person Q12 score among repeat people"],
        ["paired_mean_2024", mean(mean(by_person_year[(p, 2024)]["scores"]) for p in repeat), "mean person Q12 score among repeat people"],
        ["paired_delta_5", dm, "2024 minus 2023 paired person mean"],
        ["paired_delta_pct", dm / 5, "paired_delta_5 divided by five"],
        ["delta_sd", dsd, "sample standard deviation of person-level deltas"],
        ["delta_se", se, "delta_sd divided by sqrt(repeat_people)"],
        ["normal_approx_ci_low", dm - 1.96 * se, "descriptive 95% normal approximation"],
        ["normal_approx_ci_high", dm + 1.96 * se, "descriptive 95% normal approximation"],
        ["improved_gt_0_1", sum(d > 0.1 for d in deltas), "person delta greater than 0.1 points"],
        ["declined_lt_minus_0_1", sum(d < -0.1 for d in deltas), "person delta less than -0.1 points"],
        ["stable_within_0_1", sum(abs(d) <= 0.1 for d in deltas), "absolute person delta at most 0.1 points"],
    ]

    all_main = adopted(raw)
    overall = {y: metric([r for r in all_main if r["year"] == y])["mean"] for y in YEARS}
    cohorts = {}
    for y in YEARS:
        cohorts[(y, "repeat")] = [by_person_year[(p, y)] for p in repeat]
        cohorts[(y, "nonrepeat")] = [r for r in all_main if r["year"] == y and not (r["panel_allowed"] and r["person_key"] in repeat)]
    weights = {(y, c): len(cohorts[(y, c)]) / len([r for r in all_main if r["year"] == y]) for y in YEARS for c in ("repeat", "nonrepeat")}
    means = {(y, c): metric(cohorts[(y, c)])["mean"] for y in YEARS for c in ("repeat", "nonrepeat")}
    within = sum((weights[(2023, c)] + weights[(2024, c)]) / 2 * (means[(2024, c)] - means[(2023, c)]) for c in ("repeat", "nonrepeat"))
    mix = sum((weights[(2024, c)] - weights[(2023, c)]) * (means[(2023, c)] + means[(2024, c)]) / 2 for c in ("repeat", "nonrepeat"))
    delta = overall[2024] - overall[2023]
    comp = [["component", "value_5", "value_pct", "definition"]]
    for c in ("repeat", "nonrepeat"):
        comp.extend([
            [f"n_2023_{c}", len(cohorts[(2023, c)]), "", "cohort count"],
            [f"n_2024_{c}", len(cohorts[(2024, c)]), "", "cohort count"],
            [f"mean_2023_{c}", means[(2023, c)], means[(2023, c)] / 5, "cohort mean"],
            [f"mean_2024_{c}", means[(2024, c)], means[(2024, c)] / 5, "cohort mean"],
            [f"weight_2023_{c}", weights[(2023, c)], "", "cohort share"],
            [f"weight_2024_{c}", weights[(2024, c)], "", "cohort share"],
        ])
    comp.extend([
        ["cross_section_delta", delta, delta / 5, "2024 overall mean minus 2023 overall mean"],
        ["within_component", within, within / 5, "Kitagawa midpoint within-cohort component"],
        ["composition_component", mix, mix / 5, "Kitagawa midpoint cohort-share component"],
        ["reconciliation_error", delta - within - mix, (delta - within - mix) / 5, "must equal zero within tolerance"],
    ])
    return {"panel_summary": panel, "panel_detail": detail, "composition": comp}


def grouped(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        value = str(r.get(key, "")).strip()
        out[value or "attribute_unavailable"].append(r)
    return out


def group_tables(raw: list[dict[str, Any]], item_meta: dict[str, dict[str, str]]) -> dict[str, list[list[Any]]]:
    main = adopted(raw)
    dims = [("survey_org", "survey_org"), ("age_at_submission", "age"), ("tenure_at_submission", "tenure"), ("technical_level_at_submission", "technical_level"), ("location_snapshot_2025", "location"), ("gender_snapshot_2025", "gender"), ("job_family_snapshot_2025", "job_family")]
    groups = [["dimension", "scope", "group", "n", "mean_5", "score_pct", "top_rate", "sample_sd_raw", *[f"tier_{t}" for t in TIER_ORDER], "suppressed"]]
    for dim, key in dims:
        for scope, subset in scope_rows(main):
            for label, members in sorted(grouped(subset, key).items()):
                n = len(members); suppress = n < MIN_CELL; m = metric(members)
                tier_vals = [metric(members, tier_questions(item_meta, t))["mean"] for t in TIER_ORDER]
                groups.append([dim, scope, label, n, "" if suppress else m["mean"], "" if suppress else m["pct"], "" if suppress else m["top_rate"], "" if suppress else m["sd"], *([""] * 4 if suppress else tier_vals), suppress])
    cross = [["secondary_dimension", "scope", "survey_org", "secondary_group", "n", "mean_5", "score_pct", "top_rate", "sample_sd_raw", "suppressed"]]
    for dim, key in dims[1:]:
        for scope, subset in scope_rows(main):
            cells: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
            for r in subset:
                cells[(r["survey_org"] or "unknown", str(r.get(key, "")) or "attribute_unavailable")].append(r)
            for (org, label), members in sorted(cells.items()):
                n = len(members); suppress = n < MIN_CELL; m = metric(members)
                cross.append([dim, scope, org, label, n, "" if suppress else m["mean"], "" if suppress else m["pct"], "" if suppress else m["top_rate"], "" if suppress else m["sd"], suppress])
    return {"group_analysis": groups, "department_crosses": cross}


def priority_tables(raw: list[dict[str, Any]], item_meta: dict[str, dict[str, str]]) -> dict[str, list[list[Any]]]:
    main = adopted(raw); sens = adopted(raw, True); item_rows = []
    for q in range(1, 13):
        m23 = metric([r for r in main if r["year"] == 2023], [q]); m24 = metric([r for r in main if r["year"] == 2024], [q])
        s23 = metric([r for r in sens if r["year"] == 2023], [q]); s24 = metric([r for r in sens if r["year"] == 2024], [q])
        change = m24["pct"] - m23["pct"]; schange = s24["pct"] - s23["pct"]
        below = m24["pct"] < TARGET_PCT; decline = change <= DECLINE_PP
        stable = (s24["pct"] < TARGET_PCT) == below and (schange <= DECLINE_PP) == decline
        priority = "P1" if below and decline else "P2" if below else "P3" if decline else "monitor"
        item_rows.append([f"Q{q:02d}", item_meta[f"Q{q:02d}"]["text"], item_meta[f"Q{q:02d}"]["tier"], m23["n"], m24["n"], m23["pct"], m24["pct"], change, s23["pct"], s24["pct"], schange, below, decline, stable, priority])
    rank = {"P1": 0, "P2": 1, "P3": 2, "monitor": 3}
    item_rows.sort(key=lambda r: (rank[r[-1]], r[6], r[7], -r[4], r[0]))
    items = [["item", "item_text", "tier", "n_2023", "n_2024", "score_pct_2023", "score_pct_2024", "change_pct", "sensitivity_pct_2023", "sensitivity_pct_2024", "sensitivity_change_pct", "below_target", "decline_signal", "sensitivity_same_class", "priority"]] + item_rows
    dept_rows = []
    for org in sorted({r["survey_org"] for r in main}):
        a = [r for r in main if r["year"] == 2023 and r["survey_org"] == org]; b = [r for r in main if r["year"] == 2024 and r["survey_org"] == org]
        if len(a) < ACTION_N or len(b) < ACTION_N:
            continue
        sa = [r for r in sens if r["year"] == 2023 and r["survey_org"] == org]; sb = [r for r in sens if r["year"] == 2024 and r["survey_org"] == org]
        ma, mb, msa, msb = metric(a), metric(b), metric(sa), metric(sb)
        change = mb["pct"] - ma["pct"]; schange = msb["pct"] - msa["pct"]
        below = mb["pct"] < TARGET_PCT; decline = change <= DECLINE_PP
        stable = (msb["pct"] < TARGET_PCT) == below and (schange <= DECLINE_PP) == decline
        weakest = min(((t, metric(b, tier_questions(item_meta, t))["pct"]) for t in TIER_ORDER), key=lambda x: x[1])[0]
        priority = "P1" if below and decline else "P2" if below else "P3" if decline else "monitor"
        dept_rows.append([org, len(a), len(b), ma["pct"], mb["pct"], change, len(sa), len(sb), msa["pct"], msb["pct"], schange, below, decline, stable, weakest, priority])
    dept_rows.sort(key=lambda r: (rank[r[-1]], r[4], r[5], -r[2], r[0]))
    departments = [["survey_org", "n_2023", "n_2024", "score_pct_2023", "score_pct_2024", "change_pct", "sensitivity_n_2023", "sensitivity_n_2024", "sensitivity_pct_2023", "sensitivity_pct_2024", "sensitivity_change_pct", "below_target", "decline_signal", "sensitivity_same_class", "weakest_2024_tier", "priority"]] + dept_rows
    return {"priority_items": items, "priority_departments": departments}


def reconciliation(raw: list[dict[str, Any]]) -> list[list[Any]]:
    main = adopted(raw); sens = adopted(raw, True); keys = Counter(r["response_key"] for r in raw)
    canonical_ok = sum(sum(r["canonical"] for r in raw if r["response_key"] == key) == 1 for key in keys)
    checks = [
        ("raw_rows", len(raw), 795), ("distinct_response_keys", len(keys), 739),
        ("overlap_extra_rows", len(raw) - len(keys), 56), ("main_adopted", len(main), 739),
        ("sensitivity_adopted", len(sens), 559), ("main_response_cells", sum(len(r["scores"]) for r in main), 8868),
        ("response_keys_with_one_canonical", canonical_ok, 739),
    ]
    return [["check", "actual", "expected", "pass"]] + [[name, actual, expected, actual == expected] for name, actual, expected in checks]


def build(materials: Path, output: Path) -> None:
    raw, item_meta = load_raw(materials); output.mkdir(parents=True, exist_ok=True)
    panel = panel_tables(raw)
    clean_sheets = clean_book(raw, item_meta) + [("panel_detail", panel.pop("panel_detail"))]
    write_xlsx(output / "cleaned_samples.xlsx", clean_sheets, title="Q12 v10 identity and weight audit")
    tables: dict[str, list[list[Any]]] = {}
    tables.update(main_tables(raw, item_meta)); tables.update(calibration_tables(raw, materials, item_meta)); tables.update(advanced_tables(raw, materials, item_meta)); tables.update(v9_quality_tables(raw, materials, item_meta)); tables.update(panel); tables.update(group_tables(raw, item_meta)); tables.update(priority_tables(raw, item_meta))
    tables["reconciliation"] = reconciliation(raw)
    tables["methodology"] = [["topic", "method", "boundary"],
        ["source lineage", "保留来源文件和来源行；response_key识别批次重叠、重复导出与去重，每键只保留一条逻辑提交", "导出副本不视为重复作答"],
        ["identity bridge", "连接前检查键唯一性、有效期、match_grade与allowed_use；用途受限的身份桥不升级", "波次键不用于跨期面板"],
        ["time alignment", "按提交日核对入职、离职或结束日期；级别生效日不晚于提交日；年龄和司龄按提交日计算", "无有效期字段不作为调查时点事实"],
        ["snapshot", "people_snapshot是2025-08-31当前快照", "不是历史，不能还原调查时点"],
        ["measurement", "Top-box或顶级回答等于标准分5；样本标准差基于原始1-5分且分母为n-1", "公司统计按逻辑提交，不按响应单元加权"],
        ["comparability", "Q03与Q07为context_only，其余10题为跨版本anchor", "12题全量结果不替代anchor趋势"],
        ["calibration", "按fixed_reference做IPF固定结构校准并保存最终权重、Kish ESS和边际误差", "校准不证明总体代表性"],
        ["uncertainty", "20个delete-one-group jackknife复制中重新校准，并报告标准误和区间", "管理线不等于统计显著性"],
        ["panel", "横截面与面板分开；同一人员按person-level个人差值计算配对变化", "面板变化为描述性结果"],
        ["cohorts", "repeat与nonrepeat分别报告", "nonrepeat不是跨期相同的同一人群"],
        ["decomposition", "使用Kitagawa中点分解，组内项与构成项之和勾稽横截面变化", "构成分解不证明因果"],
        ["priority", "80%为关注线，下降1个百分点为筛选线；行动单元要求两期各n>=20", "优先级不是显著性结论"],
        ["sensitivity", "敏感性口径含559份记录，并检查分类、优先级与方向是否反转", "直线作答仅作对称敏感性排除"],
        ["multiplicity", "12题家族使用Benjamini-Hochberg校正", "p值、q值与业务线分列"],
        ["reliability", "报告Cronbach alpha、删题alpha、校正题总相关与jackknife变化区间", "量表质量变化不证明组织措施效果"],
        ["disclosure", "人员或交叉单元n<10时只显示n并抑制统计和解释", "输出保持脱敏"],
        ["scope", "结果均为描述性分析", "不能证明因果；无邀请名单，不能计算正式响应率或非响应偏差；不使用外部常模"],
    ]
    tables["limitations"] = [["topic", "limitation"],
        ["response coverage", "无正式邀请名单；不能计算正式响应率或非响应偏差。"],
        ["snapshot attributes", "人员属性是2025-08-31当前快照，不能还原调查时点历史。"],
        ["causality", "横截面、面板和构成结果均为描述性分析，不能证明因果。"],
        ["uncertainty", "区间为描述性正态近似；行动阈值是管理筛选线。"],
        ["benchmark", "材料未提供外部常模。"],
    ]
    order = ["primary_trend", "jackknife_replicates", "reliability_summary", "reliability_deleted", "reliability_change", "reliability_jackknife", "org_small_domain", "org_shrinkage_method", "org_replicates", "panel_selection", "sensitivity_matrix", "multiplicity_items", "panel_anchor", "anchor_decomposition", "calibrated_company", "calibration_diagnostics", "calibration_margins", "calibrated_items", "company_period", "item_period", "tier_period", "panel_summary", "composition", "priority_items", "priority_departments", "group_analysis", "department_crosses", "reconciliation", "methodology", "limitations"]
    write_xlsx(output / "engagement_analysis.xlsx", [(name, tables[name]) for name in order], title="Q12 v10 measurement and small-domain analysis")
    for path in (output / "cleaned_samples.xlsx", output / "engagement_analysis.xlsx"):
        validate_xlsx(path)


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--materials", type=Path, required=True); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(); build(args.materials, args.output)


if __name__ == "__main__":
    main()
