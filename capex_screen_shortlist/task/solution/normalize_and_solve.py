#!/usr/bin/env python3
"""Reference solution for the heavy-capital-expansion audit worksheet.

Self-contained: it derives every worksheet cell from the agent-visible raw
workspace (structured provider snapshots + methodology figure) and a curated
acquisition-anchor file that records the PDF evidence locations a human auditor
read out of the official annual reports.  There is no shared calculator module;
all arithmetic lives here, so the reference does not depend on anything shipped
inside the (deliberately lean) skill.

Emits the per-company worksheet answer as an intermediate JSON (--output), the
delivered workbook golden/shortlist.xlsx (--workbook), and, alongside them, the
scoring anchors the validator consumes (--ground-truth).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any


def _workbook_module():
    """The workbook layout lives with the validator so writer and reader cannot
    drift; the oracle loads it by path rather than duplicating it."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "workbook", Path(__file__).with_name("reference") / "workbook.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

_ENTITY_SUFFIXES = ("股份有限公司", "有限责任公司", "有限公司", "集团股份", "集团", "公司")


def entity_tokens(name: Any) -> list[str]:
    """Normalized core of a business-combination counterparty name, used for a
    tolerant substring match at scoring time.  Parentheticals (which carry
    translations / notes) and the trailing corporate-form suffix are dropped so
    that an agent quoting the note's registered name matches the reference."""
    if not name:
        return []
    s = re.sub(r"[\(（【\[].*?[\)）】\]]", "", str(name))
    s = re.sub(r"\s+", "", s)
    for suf in _ENTITY_SUFFIXES:
        if s.endswith(suf):
            s = s[: -len(suf)]
            break
    return [s] if len(s) >= 2 else []

DATASET_ID = "capex-screen-shortlist"
CUTOFF = "2022-05-20"
YEARS = (2018, 2019, 2020, 2021)
WINDOW = (2019, 2020, 2021)
STATEMENTS = ("balance", "income", "cashflow")

# Raw provider field names -> normalized interest-bearing debt components.
DEBT_FIELDS = {
    "short_term_borrowings": "SHORT_LOAN",
    "current_portion_interest_bearing_debt": "NONCURRENT_LIAB_1YEAR",
    "long_term_borrowings": "LONG_LOAN",
    "bonds_payable": "BOND_PAYABLE",
    "other_interest_bearing_debt": "SHORT_BOND_PAYABLE",
    "short_term_financing_payable": "SHORT_FIN_PAYABLE",
}

# Source-calibrated reference bars. They appear in no agent-visible material;
# the Skill teaches how to calibrate and check each gate, and the agent chooses
# its own supported values. Equality fails every bar.
EFFICIENCY_NARRATIVE = 3.0
EFFICIENCY_STRICT = 4.0
COVERAGE_BAR = 2.0
EXPANSION_BAR = 0.10
PROFIT_QUALITY_BAR = 1.0

# Provenance anchors, no longer read by the scorer.  The debt-review company's
# co-movement is real but no filing binds a borrowing to a named project, so the
# only defensible answer is REVIEW; the acquisition-evidence and goodwill-trap
# lists document why their named companies are what they are.  All three groups
# were dropped from scoring -- acq/goodwill on 2026-08-30 (their citation check
# compared entity names and misjudged every anchor in both conditions), and the
# scorer later collapsed to the shortlist verdict alone.
ACQ_EVIDENCE_ANCHORS = ["002518.SZ", "600299.SH", "002223.SZ"]
GOODWILL_TRAP_ANCHORS = ["300285.SZ", "300450.SZ"]
DEBT_REVIEW_ANCHOR = "002223.SZ"

# Goodwill trajectory rule: a window year whose goodwill rises materially over
# the prior year signals a business combination that year.
ACQ_REL = 1.02
ACQ_ABS = 1e6

CONVENTIONS = {
    "fixed_asset_denominator": "period_end",
    "current_portion_treatment": "interest_bearing_only",
    "lease_liabilities": "excluded",
    "profit_basis": "consolidated_net_profit",
    "cash_basis": "as_reported",
    "expansion_threshold": "all three annual asset growth rates > 0.10",
    "coverage_threshold": "three-year mean monetary funds / interest-bearing debt > 2.0",
    "efficiency_threshold": "mean revenue / ending fixed assets > 3.0 (strict reading > 4.0)",
    "profit_quality_threshold": "mean operating cash flow / consolidated net profit > 1.0",
    "debt_funding_rule": "REVIEW when evidence cannot bind debt to capital expenditure",
}

# The three fixed irreconcilable readings the method does not resolve.
CONFLICTS = [
    {
        "conflict_id": "SCREEN_EFFICIENCY_BAR",
        "reading_a": "Investment efficiency passes at a three-year-mean revenue/ending-fixed-assets above 2.0 (narrative profile).",
        "reading_b": "Investment efficiency passes only above 3.0 (strict profile).",
        "why_irreconcilable": "The framework figure names one efficiency indicator but the method carries two profiles; a company between the declared 2.0 and 3.0 bars passes one and fails the other.",
    },
    {
        "conflict_id": "SCREEN_MEAN_VS_EVERY_YEAR",
        "reading_a": "Debt-risk coverage is judged on the three-year mean being above 1.0 (narrative profile).",
        "reading_b": "Debt-risk coverage must clear 1.0 in every single year (strict profile).",
        "why_irreconcilable": "A mean above 1.0 can hide a below-1.0 year; the two tests disagree on any company with one weak year, so both readings remain visible.",
    },
    {
        "conflict_id": "SCREEN_SIGNED_PROFIT",
        "reading_a": "The operating-cash-flow / net-profit ratio is kept with its sign even when net profit is negative (narrative profile).",
        "reading_b": "A year with non-positive net profit fails outright, so the signed ratio is rejected (figure-4 strict profile).",
        "why_irreconcilable": "With a negative denominator the ratio inverts its meaning; keeping it and rejecting it cannot both stand, and the framework figure shows only one profit-quality box.",
    },
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def source_state(row: dict, field: str) -> str:
    if field not in row:
        return "ABSENT"
    return "STANDARDIZED_NULL" if row[field] is None else "DISCLOSED"


def line_item(row: dict, field: str):
    if field not in row:
        return None
    return 0.0 if row[field] is None else row[field]


def annual_rows(document: dict, company_id: str, statement: str) -> dict[int, dict]:
    reqs = [r for r in document.get("requests", []) if r.get("statement") == statement]
    if len(reqs) != 1:
        raise ValueError(f"{company_id}: expected one {statement} request")
    selected: dict[int, dict] = {}
    for row in reqs[0]["payload"]["result"]["data"]:
        ytxt = str(row.get("REPORT_DATE", ""))[:4]
        if not (ytxt.isdigit() and int(ytxt) in YEARS):
            continue
        if row.get("SECUCODE") != company_id or row.get("REPORT_TYPE") != "年报":
            raise ValueError(f"{company_id} {statement} {ytxt}: wrong entity/report type")
        if str(row.get("NOTICE_DATE", ""))[:10] > CUTOFF:
            raise ValueError(f"{company_id} {statement} {ytxt}: notice after cutoff")
        selected[int(ytxt)] = row
    if set(selected) != set(YEARS):
        raise ValueError(f"{company_id} {statement}: incomplete years {sorted(selected)}")
    return selected


def load_company(company_id: str, snapshot_dir: Path) -> dict:
    """Extract the raw facts needed for every cell, preserving three states:
    a present number (including 0) is a fact; a present null reproduces a zero
    line item; an absent key is missing evidence and is recorded as such."""
    doc = json.loads((snapshot_dir / f"{company_id}.json").read_text(encoding="utf-8"))
    if doc.get("company_id") != company_id:
        raise ValueError(f"snapshot identity mismatch: {company_id}")
    rows = {s: annual_rows(doc, company_id, s) for s in STATEMENTS}
    fin: dict[str, Any] = {}
    for year in YEARS:
        b, inc, cf = rows["balance"][year], rows["income"][year], rows["cashflow"][year]
        debt_present, debt_sum, debt_absent = True, 0.0, []
        debt_has_null = False
        for _, raw in DEBT_FIELDS.items():
            if raw not in b:
                debt_present = False
                debt_absent.append(raw)
                continue
            v = b[raw]
            if v is None:
                debt_has_null = True
                continue
            debt_sum += float(v)
        direct_assets = b.get("TOTAL_ASSETS")
        liabilities_equity = b.get("TOTAL_LIAB_EQUITY")
        liabilities = b.get("TOTAL_LIABILITIES")
        equity = b.get("TOTAL_EQUITY")
        if is_num(direct_assets):
            total_assets, total_assets_source = direct_assets, "TOTAL_ASSETS"
        elif is_num(liabilities_equity):
            total_assets, total_assets_source = liabilities_equity, "TOTAL_LIAB_EQUITY"
        elif is_num(liabilities) and is_num(equity):
            total_assets, total_assets_source = liabilities + equity, "TOTAL_LIABILITIES+TOTAL_EQUITY"
        else:
            total_assets, total_assets_source = None, None
        fin[str(year)] = {
            "total_assets": total_assets,
            "total_assets_source": total_assets_source,
            "total_assets_direct_missing": not is_num(direct_assets),
            "total_assets_absent": total_assets_source is None,
            "cash": b.get("MONETARYFUNDS"),
            "fixed_assets": b.get("FIXED_ASSET"),
            "fixed_assets_absent": not is_num(b.get("FIXED_ASSET")),
            "cip": line_item(b, "CIP"),
            "goodwill": line_item(b, "GOODWILL"),
            "net_assets": b.get("TOTAL_EQUITY"),
            "revenue": inc.get("TOTAL_OPERATE_INCOME"),
            "net_profit": inc.get("NETPROFIT"),
            "net_profit_absent": not is_num(inc.get("NETPROFIT")),
            "cfo": cf.get("NETCASH_OPERATE"),
            "cfo_absent": not is_num(cf.get("NETCASH_OPERATE")),
            "capex": line_item(cf, "CONSTRUCT_LONG_ASSET"),
            "capex_absent": "CONSTRUCT_LONG_ASSET" not in cf,
            "borrowing": (None if line_item(cf, "RECEIVE_LOAN_CASH") is None or line_item(cf, "ISSUE_BOND") is None else
                          line_item(cf, "RECEIVE_LOAN_CASH") + line_item(cf, "ISSUE_BOND")),
            "debt_present": debt_present,
            "debt_sum": debt_sum if debt_present else None,
            "debt_has_null": debt_has_null,
            "debt_absent_fields": debt_absent,
            "source_states": {
                "TOTAL_ASSETS": source_state(b, "TOTAL_ASSETS"),
                "TOTAL_LIAB_EQUITY": source_state(b, "TOTAL_LIAB_EQUITY"),
                "MONETARYFUNDS": source_state(b, "MONETARYFUNDS"),
                "FIXED_ASSET": source_state(b, "FIXED_ASSET"),
                "CIP": source_state(b, "CIP"),
                "GOODWILL": source_state(b, "GOODWILL"),
                "NETPROFIT": source_state(inc, "NETPROFIT"),
                "NETCASH_OPERATE": source_state(cf, "NETCASH_OPERATE"),
                "CONSTRUCT_LONG_ASSET": source_state(cf, "CONSTRUCT_LONG_ASSET"),
                "RECEIVE_LOAN_CASH": source_state(cf, "RECEIVE_LOAN_CASH"),
                "ISSUE_BOND": source_state(cf, "ISSUE_BOND"),
                **{field: source_state(b, field) for field in DEBT_FIELDS.values()},
            },
        }
    return {"company_id": company_id, "financials": fin}


# ---------------- metric helpers ----------------

def asset_growth(fin: dict, year: int):
    cur, prior = fin[str(year)]["total_assets"], fin[str(year - 1)]["total_assets"]
    if not (is_num(cur) and is_num(prior)) or prior <= 0:
        return None
    return (cur - prior) / prior


def coverage(fin: dict, year: int):
    row = fin[str(year)]
    cash, debt = row["cash"], row["debt_sum"]
    if not is_num(cash) or debt is None:
        return None
    if debt == 0:
        return "INF" if cash >= 0 else None
    if debt < 0:
        return None
    return cash / debt


def turnover(fin: dict, year: int, denom_key: str = "fixed_assets"):
    row = fin[str(year)]
    rev, fx = row["revenue"], row[denom_key]
    if not (is_num(rev) and is_num(fx)) or fx <= 0:
        return None
    return rev / fx


def turnover_with_cip(fin: dict, year: int):
    row = fin[str(year)]
    rev, fx, cp = row["revenue"], row["fixed_assets"], row["cip"]
    if not (is_num(rev) and is_num(fx) and is_num(cp)) or (fx + cp) <= 0:
        return None
    return rev / (fx + cp)


def mean3(vals: list):
    if any(v == "INF" for v in vals):
        return "INF" if all(v == "INF" or is_num(v) for v in vals) else None
    if not all(is_num(v) for v in vals):
        return None
    return sum(vals) / 3


# ---------------- worksheet cells ----------------

def classify_acquisition(fin: dict):
    gw = {y: fin[str(y)]["goodwill"] for y in YEARS}
    increase_years = []
    changes = {}
    for y in WINDOW:
        a, b = gw.get(y), gw.get(y - 1)
        changes[str(y)] = a - b if is_num(a) and is_num(b) else None
        if is_num(a) and is_num(b) and a > b:
            increase_years.append(str(y))
    complete = all(is_num(value) for value in gw.values())
    classification = ("REVIEW" if not complete else
                      "BALANCE_INCREASE_REVIEW" if increase_years else "NO_WINDOW_INCREASE")
    return classification, increase_years, changes, gw


def cip_distortion(fin: dict):
    affected = []
    max_ratio = 0.0
    complete = True
    for y in WINDOW:
        row = fin[str(y)]
        t_fixed = turnover(fin, y)
        t_cip = turnover_with_cip(fin, y)
        cp, fx = row["cip"], row["fixed_assets"]
        if is_num(cp) and is_num(fx) and fx > 0:
            max_ratio = max(max_ratio, cp / fx)
        flips_by_profile = {}
        if t_fixed is not None and t_cip is not None:
            flips_by_profile = {
                "narrative": (t_fixed > EFFICIENCY_NARRATIVE) != (t_cip > EFFICIENCY_NARRATIVE),
                "strict": (t_fixed > EFFICIENCY_STRICT) != (t_cip > EFFICIENCY_STRICT),
            }
        else:
            complete = False
        affected.append({
            "year": str(y),
            "revenue": row["revenue"],
            "fixed_asset_ending": row["fixed_assets"],
            "cip": cp,
            "turnover_fixed_only": round(t_fixed, 10) if t_fixed is not None else None,
            "turnover_with_cip": round(t_cip, 10) if t_cip is not None else None,
            "gate_flips_by_profile": flips_by_profile,
        })
    distorted = None if not complete else any(any(a["gate_flips_by_profile"].values()) for a in affected)
    return distorted, round(max_ratio, 10), affected


def missing_data_cells(company_id: str, fin: dict):
    """Emit the three-state cells that carry a scored judgment for this company:
    an absent debt / statement field (REVIEW), and a disclosed-zero interest-
    bearing debt (FACT, unbounded coverage)."""
    cells = []
    # absent tracked fields
    for y in YEARS:
        row = fin[str(y)]
        if row["total_assets_direct_missing"] and row["total_assets_source"]:
            cells.append({
                "company_id": company_id, "field": "TOTAL_ASSETS", "years": [str(y)],
                "state": "RECOVERED", "call": "FACT",
                "recovery_source": row["total_assets_source"],
                "reason": "Recovered from an auditable same-statement balance-sheet identity; no interpolation or estimate used.",
            })
        for label, absent in (
            ("interest_bearing_debt_components", not row["debt_present"]),
            ("TOTAL_ASSETS", row["total_assets_absent"]),
            ("FIXED_ASSET", row["fixed_assets_absent"]),
            ("NETPROFIT", row["net_profit_absent"]),
            ("NETCASH_OPERATE", row["cfo_absent"]),
            ("CONSTRUCT_LONG_ASSET", row["capex_absent"]),
        ):
            if absent:
                cells.append({
                    "company_id": company_id, "field": label, "years": [str(y)],
                    "state": "ABSENT", "call": "REVIEW",
                    "reason": "Field absent from the snapshot; the dependent test cannot be formed.",
                })
    # disclosed-zero interest-bearing debt (all components present and summing to 0)
    disclosed_zero_years = [str(y) for y in YEARS if fin[str(y)]["debt_present"]
                            and not fin[str(y)]["debt_has_null"] and fin[str(y)]["debt_sum"] == 0]
    standardized_zero_years = [str(y) for y in YEARS if fin[str(y)]["debt_present"]
                               and fin[str(y)]["debt_has_null"] and fin[str(y)]["debt_sum"] == 0]
    if disclosed_zero_years:
        cells.append({
            "company_id": company_id, "field": "interest_bearing_debt", "years": disclosed_zero_years,
            "state": "DISCLOSED_ZERO", "call": "FACT",
            "reason": "All interest-bearing components are disclosed numbers and sum to zero; coverage is unbounded.",
        })
    if standardized_zero_years:
        cells.append({
            "company_id": company_id, "field": "interest_bearing_debt", "years": standardized_zero_years,
            "state": "STANDARDIZED_NULL_ZERO", "call": "FACT",
            "reason": "Present-null debt line items are normalized to zero for source reproduction; this is not a disclosed numeric zero.",
        })
    return cells


def debt_purpose_cell(company_id: str, fin: dict):
    """Co-movement of capex and borrowing is a proxy, never causal on its own."""
    cover_vals = [coverage(fin, y) for y in WINDOW]
    cover_mean = mean3(cover_vals)
    capex_values = [fin[str(y)]["capex"] for y in WINDOW]
    capex_all = None if any(value is None for value in capex_values) else all(value > 0 for value in capex_values)
    borrowing_present = any(is_num(fin[str(y)]["borrowing"]) and fin[str(y)]["borrowing"] > 0 for y in WINDOW)
    # REVIEW if a binding input is missing this window; else proxy-only.
    inputs_complete = all(fin[str(y)]["debt_present"] and is_num(fin[str(y)]["capex"]) for y in WINDOW)
    co_movement = capex_all is True and borrowing_present
    if not inputs_complete:
        confidence = "REVIEW"
        reason = "A binding debt or capex input is unavailable; quantitative purpose remains REVIEW."
    elif co_movement:
        confidence = "QUANTITATIVE_PROXY_ONLY"
        reason = "Positive capex and borrowing co-move, but no filing binds a specific borrowing to a named project."
    else:
        confidence = "NO_PROXY_SUPPORT"
        reason = "The quantitative borrowing/capex proxy is not satisfied; financing purpose remains REVIEW and no causal project claim is made."
    return {
        "company_id": company_id,
        "cash_coverage_mean": (cover_mean if cover_mean == "INF" else round(cover_mean, 10)) if cover_mean is not None else None,
        "borrowing_present": borrowing_present,
        "capex_positive_all_years": capex_all,
        "confidence": confidence,
        "filing_evidence": {"source_id": None, "pdf_page": None},
        "reason": reason,
    }, co_movement


def signed_profit_cells(company_id: str, fin: dict):
    cells = []
    for y in WINDOW:
        np_ = fin[str(y)]["net_profit"]
        if is_num(np_) and np_ < 0:
            cells.append({
                "company_id": company_id, "year": str(y), "netprofit": np_,
                "narrative_treatment": "keep signed CFO/net-profit ratio",
                "figure4_treatment": "reject: non-positive net profit fails the strict profit gate",
                "profiles_disagree": True,
            })
    return cells


def profit_quality(fin: dict, year: int):
    """Operating cash flow / net profit for one year.  A zero denominator has no
    ratio; a negative one keeps the signed value (the narrative profile's
    treatment -- the strict profile's disagreement is reported separately)."""
    row = fin[str(year)]
    cfo, net = row["cfo"], row["net_profit"]
    if not (is_num(cfo) and is_num(net)) or net == 0:
        return None
    return cfo / net


def selection_status(fin: dict):
    """Terminal narrative-profile verdict for one company.

    Four strict gates on the 2019-2021 window: total-asset growth above
    EXPANSION_BAR in *every* year, and three-year arithmetic means above
    COVERAGE_BAR, EFFICIENCY_NARRATIVE and PROFIT_QUALITY_BAR.

    A missing gate yields REVIEW only when every known gate still passes. A known
    failed gate is enough to exclude the company even when another input is
    unavailable, because the unavailable input cannot reverse that failure.
    """
    growth = [asset_growth(fin, y) for y in WINDOW]
    coverage_mean = mean3([coverage(fin, y) for y in WINDOW])
    efficiency_mean = mean3([turnover(fin, y) for y in WINDOW])
    quality_mean = mean3([profit_quality(fin, y) for y in WINDOW])
    capex_values = [fin[str(y)]["capex"] for y in WINDOW]
    gates = {
        "expansion_every_year": None if any(g is None for g in growth) else all(g > EXPANSION_BAR for g in growth),
        "debt_risk_mean": None if coverage_mean is None else coverage_mean == "INF" or coverage_mean > COVERAGE_BAR,
        "investment_efficiency_mean": None if efficiency_mean is None else efficiency_mean > EFFICIENCY_NARRATIVE,
        "profit_quality_mean": None if quality_mean is None else quality_mean > PROFIT_QUALITY_BAR,
        "capex_positive_all_years": None if any(v is None for v in capex_values) else all(v > 0 for v in capex_values),
    }
    return ("FAIL" if any(v is False for v in gates.values()) else
            "PASS" if all(v is True for v in gates.values()) else "REVIEW"), gates


# ---------------- assembly ----------------


def solve(workspace: Path, anchors_path: Path) -> tuple[dict, dict]:
    with (workspace / "candidate_universe.csv").open(encoding="utf-8-sig", newline="") as s:
        candidates = list(csv.DictReader(s))
    ids = [c["company_id"] for c in candidates]
    if len(ids) != 60 or len(set(ids)) != 60:
        raise ValueError("candidate universe must contain 60 unique companies")
    snapshot_dir = workspace / "structured-data" / "provider-snapshots"
    companies = {cid: load_company(cid, snapshot_dir) for cid in ids}

    acq_anchors = json.loads(anchors_path.read_text(encoding="utf-8")) if anchors_path.exists() else {}

    acquisition, cip, missing, debt, signed = [], [], [], [], []
    anchor_sets = {
        "acquisition_driven": [], "cip_distorted": [], "disclosed_zero_denominator": [],
        "absent_evidence": [], "negative_denominator_years": [], "debt_purpose_co_movement": [],
    }
    evidence = [{"source_id": "methodology-figure1", "pdf_page": 4,
                 "claim": "Financing-investment-production-collection framework and indicator groups"}]

    for cid in sorted(ids):
        fin = companies[cid]["financials"]

        cls, inc_years, changes, gw = classify_acquisition(fin)
        combos = []
        if inc_years:
            anchor_sets["acquisition_driven"].append(cid)
            for wc in (acq_anchors.get(cid, {}) or {}).get("window_combinations", []):
                combos.append(wc)
                if is_num(wc.get("pdf_page")):
                    evidence.append({"source_id": wc.get("source_id"), "pdf_page": wc.get("pdf_page"),
                                     "claim": f"{cid} business combination: {wc.get('acquired_entity')} ({wc.get('purchase_year')})"})
        acquisition.append({
            "company_id": cid, "classification": cls,
            "goodwill_by_year": {str(y): gw.get(y) for y in YEARS},
            "year_on_year_changes": changes,
            "window_increase_years": inc_years,
            "window_combinations": combos,
            "reason": (acq_anchors.get(cid, {}) or {}).get("reason")
                      or ("A year-end goodwill balance increases in the window, but no issued filing identifies an acquisition; causal classification remains REVIEW."
                          if inc_years else "No year-end goodwill increase appears in the window; this supports a historical/organic reading but cannot exclude offsetting purchases and impairment."),
        })

        distorted, max_ratio, affected = cip_distortion(fin)
        if distorted:
            anchor_sets["cip_distorted"].append(cid)
        cip.append({"company_id": cid, "distorted": distorted, "cip_over_fixed_max": max_ratio,
                    "affected": affected,
                    "reason": ("Folding CIP into the denominator flips an efficiency gate in a window year."
                               if distorted is True else
                               "CIP does not move either disclosed efficiency reading in any fully observed window year."
                               if distorted is False else
                               "At least one window year lacks a formable fixed-asset/CIP ratio; the all-window distortion conclusion remains REVIEW.")})

        mcells = missing_data_cells(cid, fin)
        missing.extend(mcells)
        for c in mcells:
            if c["state"] == "ABSENT":
                anchor_sets["absent_evidence"].append(cid)
            if c["state"] == "DISCLOSED_ZERO":
                anchor_sets["disclosed_zero_denominator"].append(cid)

        dcell, co_move = debt_purpose_cell(cid, fin)
        if co_move:
            debt.append(dcell)
            anchor_sets["debt_purpose_co_movement"].append(cid)

        scells = signed_profit_cells(cid, fin)
        signed.extend(scells)
        for c in scells:
            anchor_sets["negative_denominator_years"].append(f"{cid}:{c['year']}")

    # de-dup anchor company lists
    for k in ("acquisition_driven", "cip_distorted", "disclosed_zero_denominator",
              "absent_evidence", "debt_purpose_co_movement"):
        anchor_sets[k] = sorted(set(anchor_sets[k]))

    # Terminal selection.  Runs after the loop because REVIEW depends on the
    # absent-evidence set the three-state pass just built.
    absent_ids = set(anchor_sets["absent_evidence"])
    selection = []
    growth_expected = {}
    professional_analysis = []
    for cid in sorted(ids):
        fin = companies[cid]["financials"]
        status, gates = selection_status(fin)
        growth = {str(y): asset_growth(fin, y) for y in WINDOW}
        growth_expected[cid] = growth
        selection.append({
            "company_id": cid,
            "status": status,
            "profile_gates": gates,
            "metrics": {
                # Year-on-year total-asset growth is the one figure behind the
                # screen that carries no convention choice: it is a ratio of two
                # reported totals.  Coverage and profit quality depend on the
                # declared debt composition and profit basis, so they are
                # reported but not scored.
                "asset_growth": growth,
                "coverage_mean": mean3([coverage(fin, y) for y in WINDOW]),
                "efficiency_mean": mean3([turnover(fin, y) for y in WINDOW]),
                "profit_quality_mean": mean3([profit_quality(fin, y) for y in WINDOW]),
            },
            "reason": {
                "REVIEW": "All known gates pass, but a binding field remains unavailable and could change the call.",
                "PASS": "Clears every narrative-profile gate on the window.",
                "FAIL": "Fails at least one narrative-profile gate on the window.",
            }[status],
        })
        annual = {}
        for y in YEARS:
            row = fin[str(y)]
            annual[str(y)] = {
                "assets": row["total_assets"], "assets_source": row["total_assets_source"],
                "cash": row["cash"], "debt": row["debt_sum"],
                "revenue": row["revenue"], "fixed_assets": row["fixed_assets"], "cip": row["cip"],
                "net_profit": row["net_profit"], "operating_cashflow": row["cfo"],
                "capex": row["capex"], "borrowing": row["borrowing"], "goodwill": row["goodwill"],
                "net_assets": row["net_assets"], "coverage": coverage(fin, y),
                "efficiency": turnover(fin, y), "cip_adjusted": turnover_with_cip(fin, y),
                "profit_quality": profit_quality(fin, y),
                "goodwill_ratio": (row["goodwill"] / row["net_assets"]
                                   if is_num(row["goodwill"]) and is_num(row["net_assets"]) and row["net_assets"] else None),
            }
        narrative_gates = gates
        coverage_values = [coverage(fin, y) for y in WINDOW]
        efficiency_value = mean3([turnover(fin, y) for y in WINDOW])
        quality_value = mean3([profit_quality(fin, y) for y in WINDOW])
        profit_values = [fin[str(y)]["net_profit"] for y in WINDOW]
        capex_values = [fin[str(y)]["capex"] for y in WINDOW]
        strict_gates = {
            "expansion_every_year": None if any(growth[str(y)] is None for y in WINDOW) else all(growth[str(y)] > EXPANSION_BAR for y in WINDOW),
            "coverage_every_year": None if any(value is None for value in coverage_values) else all(value == "INF" or value > COVERAGE_BAR for value in coverage_values),
            "investment_efficiency_mean": None if efficiency_value is None else efficiency_value > EFFICIENCY_STRICT,
            "profit_quality_mean_and_positive_profit": (False if any(is_num(value) and value <= 0 for value in profit_values) else
                None if quality_value is None or any(value is None for value in profit_values) else
                quality_value > PROFIT_QUALITY_BAR),
            "capex_positive_all_years": None if any(value is None for value in capex_values) else all(value > 0 for value in capex_values),
        }
        strict_status = ("FAIL" if any(value is False for value in strict_gates.values()) else
                         "PASS" if all(value is True for value in strict_gates.values()) else "REVIEW")
        acq_row = next(row for row in acquisition if row["company_id"] == cid)
        cip_row = next(row for row in cip if row["company_id"] == cid)
        debt_row = next((row for row in debt if row["company_id"] == cid), debt_purpose_cell(cid, fin)[0])
        missing_rows = [row for row in missing if row["company_id"] == cid]
        annual_states = {str(y): {"assets_source": fin[str(y)]["total_assets_source"],
                                  "source_states": fin[str(y)]["source_states"]}
                         for y in YEARS}
        signed_rows = [row for row in signed if row["company_id"] == cid]
        if signed_rows:
            signed_summary = signed_rows
        elif any(fin[str(y)]["cfo"] is None or fin[str(y)]["net_profit"] is None for y in WINDOW):
            signed_summary = {"negative_profit_years": [],
                "treatment": "No disclosed window profit is nonpositive, but an absent CFO/profit input leaves the affected signed ratio and profile at REVIEW."}
        else:
            signed_summary = {"negative_profit_years": [],
                "treatment": "All window profits are positive and the signed cash-conversion ratio is formable under both profile readings."}
        professional_analysis.append({
            "company_id": cid, "primary_call": status,
            "profiles": {"primary_reading": "narrative", "narrative": {"status": status, "gates": narrative_gates},
                         "strict": {"status": strict_status, "gates": strict_gates}},
            "cip": cip_row, "goodwill": acq_row, "debt_purpose": debt_row,
            "signed_profit": signed_summary,
            "missingness": {"events": missing_rows, "annual_binding_states": annual_states,
                "policy": "Disclosed zero, standardized present null, auditable same-statement recovery and absent input remain distinct."},
            "annual": annual,
        })
    selection_expected = {r["company_id"]: r["status"] for r in selection}


    answer = {
        "dataset_id": DATASET_ID,
        "network_used": False,
        "conventions": dict(CONVENTIONS),
        "selection": {
            "selected_ids": [r["company_id"] for r in selection if r["status"] == "PASS"],
            "review_ids": [r["company_id"] for r in selection if r["status"] == "REVIEW"],
            "companies": selection,
        },
        "acquisition_audit": {"companies": acquisition},
        "cip_distortion": {"companies": cip},
        "missing_data_states": {"cells": missing},
        "debt_purpose": {"companies": debt},
        "signed_profit": {"cells": signed},
        "conflicts": {"items": [
            {**c, "affected_companies": (
                anchor_sets["negative_denominator_years"] if c["conflict_id"] == "SCREEN_SIGNED_PROFIT" else []
            )} for c in CONFLICTS
        ]},
        "evidence": evidence,
        "professional_analysis": professional_analysis,
    }

    # The scored contract.  validator.py reads exactly two keys -- cell_weights
    # and selection_expected -- so ground_truth.json carries those plus dataset
    # identity and the format conventions the verdicts are spelled in, and
    # nothing else.  All per-company derivation lives in the lineage file below.
    ground_truth = {
        "dataset_id": DATASET_ID,
        "candidate_count": 60,
        "conventions": dict(CONVENTIONS),
        "minimum_evidence_items": 9,
        # One checkpoint: the shortlist itself.  Selection is the deliverable the
        # method exists to produce, and it is a legitimate primary criterion --
        # the Skill no longer carries the bars, so reaching the right list
        # requires reading the figure's binding structure and anchoring each
        # ratio semantically.  Scored purely on enums, ids and numbers, over the
        # Historical oracle lineage only; the current scorer derives from source
        # and does not read this membership map.
        "cell_weights": {"shortlist": 1.00},
        "selection_expected": selection_expected,
    }
    # Non-scored derivation, retained for audit only: the per-company provenance
    # explaining why each verdict is what it is.  validator.py never reads this
    # file; it ships as lineage alongside ground_truth.json and is regenerated in
    # the same pass, so the two can never drift apart.
    ground_truth_lineage = {
        "dataset_id": DATASET_ID,
        "note": "Derivation and provenance for ground_truth.json. Not read by the scorer.",
        "conflict_ids": [c["conflict_id"] for c in CONFLICTS],
        "anchors": {
            # ACQUISITION_DRIVEN companies whose window_increase_years,
            # purchase_years and combo purchase years all agree, so the
            # all-or-nothing evidence credit cannot be lost to a dating
            # convention mismatch.
            "acq_evidence": ACQ_EVIDENCE_ANCHORS,
            # High goodwill *level*, flat *trajectory* -> ORGANIC for this
            # window.  Reading the level instead of the trajectory is the
            # signature error this checkpoint is built to catch; the four-year
            # trajectory must be supplied so a blanket ORGANIC guess earns
            # nothing.
            "goodwill_trap": GOODWILL_TRAP_ANCHORS,
            # Co-movement with no filing that binds a borrowing to a named
            # project: the answer is REVIEW, never a causal claim.
            "debt_review": DEBT_REVIEW_ANCHOR,
        },
        "goodwill_trap_expected": {
            cid: {str(y): companies[cid]["financials"][str(y)]["goodwill"] for y in YEARS}
            for cid in GOODWILL_TRAP_ANCHORS
        },
        "asset_growth_expected": growth_expected,
        "scoring_anchors": anchor_sets,
        "acquisition_expected": {
            r["company_id"]: {
                "classification": r["classification"],
                "window_increase_years": r["window_increase_years"],
                "purchase_years": sorted({str(wc.get("purchase_year")) for wc in r["window_combinations"]
                                          if wc.get("purchase_year") is not None}),
                # Verifiable evidence combos: only combos whose entity AND page are
                # actually inside the delivered packet.  A precise-citation credit
                # requires matching ANY one of these (year + entity token + page),
                # so companies whose earliest combo lives in an out-of-packet report
                # are never required to cite the missing one.
                "evidence_combos": [
                    {
                        "purchase_year": str(wc.get("purchase_year")),
                        "entity_tokens": entity_tokens(wc.get("acquired_entity")),
                        "pdf_page": wc.get("pdf_page"),
                        "accepted_pages": wc.get("accepted_pages") or [wc.get("pdf_page")],
                    }
                    for wc in r["window_combinations"]
                    if wc.get("purchase_year") is not None
                    and wc.get("acquired_entity")
                    and is_num(wc.get("pdf_page"))
                ],
            } for r in acquisition
        },
        "cip_expected": {r["company_id"]: r["distorted"] for r in cip},
        "debt_purpose_expected": {r["company_id"]: r["confidence"] for r in debt},
    }
    return answer, ground_truth, ground_truth_lineage


def write_shortlist_workbook(answer: dict, path: Path) -> None:
    """Render the screen as the workbook that goes to the committee: one table of
    verdicts with the figures behind them, plus the calibration used."""
    wb = _workbook_module()
    screen = []
    for row in answer["selection"]["companies"]:
        m = row.get("metrics") or {}
        growth = m.get("asset_growth") or {}
        screen.append({
            "company_id": row["company_id"], "status": row["status"],
            "growth_2019": growth.get("2019"), "growth_2020": growth.get("2020"),
            "growth_2021": growth.get("2021"),
            "coverage_mean": m.get("coverage_mean"),
            "efficiency_mean": m.get("efficiency_mean"),
            "profit_quality_mean": m.get("profit_quality_mean"),
        })
    wb.write_workbook(path, {"Screen": screen}, answer["conventions"])
    from openpyxl import load_workbook
    book = load_workbook(path)
    method = book.create_sheet("Methodology")
    method.append(["topic", "adopted method"])
    method_rows = {
        "source boundary": "Frozen structured provider snapshots only; cutoff 2022-05-20. Official filing PDFs are not included, and no network or discount-rate input is used.",
        "primary policy": "Narrative quantitative profile is the committee call; the strict profile is reported separately and disagreements remain visible.",
        "financial fields": "cash=MONETARYFUNDS; revenue=TOTAL_OPERATE_INCOME; profit=NETPROFIT; fixed assets=ending FIXED_ASSET; CIP is tested separately.",
        "debt fields": "SHORT_LOAN + NONCURRENT_LIAB_1YEAR + LONG_LOAN + BOND_PAYABLE + SHORT_BOND_PAYABLE + SHORT_FIN_PAYABLE; LEASE_LIAB excluded.",
        "window": "2019-2021 with 2018 as the first growth base; strict > comparisons; definitions constant across all companies.",
        "bars": "asset growth each year > 0.10; cash / interest-bearing debt > 2.0; narrative revenue / ending fixed assets > 3.0; strict reading > 4.0; operating cash flow / consolidated net profit > 1.0.",
        "calibration": "On the 48 companies with all four gates formable, sequential admissions are growth 27/48, cash coverage 17/27, narrative investment efficiency 12/17, and profit quality 6/12. The round bars represent material annual expansion, two-times cash debt coverage, three-times fixed-asset turnover, and full cash conversion of net profit. Moving each bar -10%/+10% changes final selections as follows: growth 8/6, coverage 8/6, narrative efficiency 9/5, strict efficiency 6/6, profit quality 6/6. The list remains nonempty and no nearby move admits most of the pool; narrative efficiency is the most locally sensitive and is therefore reported beside the strict reading rather than treated as certain.",
        "debt purpose": "Annual borrowing inflow is RECEIVE_LOAN_CASH + ISSUE_BOND. Cash/debt/capex and borrowing co-movement is QUANTITATIVE_PROXY_ONLY; no issued filing binds borrowing to a named project, so stronger causality remains REVIEW.",
        "goodwill limit": "Year-end goodwill trajectories date visible increases but cannot exclude purchase and impairment offset within a year.",
        "signed profit": "The narrative reading retains the signed operating-cash-flow / consolidated-net-profit ratio. The strict reading rejects a non-positive net-profit year outright; missing CFO or profit leaves the affected ratio at REVIEW.",
        "missingness": "The total-assets measure uses disclosed TOTAL_ASSETS or the same balance sheet's disclosed TOTAL_LIAB_EQUITY, which is its accounting-identity equivalent; the chosen source is recorded. Other absent binding inputs remain REVIEW only when no known gate already fails.",
    }
    for key, value in method_rows.items():
        method.append([key, value])
    audit = book.create_sheet("Company audits")
    audit.append(["company_id", "primary_call", "profiles", "CIP consequence", "goodwill trajectory",
                  "debt purpose", "signed profit", "missingness", "annual source-bound vectors"])
    for row in answer["professional_analysis"]:
        audit.append([row["company_id"], row["primary_call"],
            json.dumps(row["profiles"], ensure_ascii=False, separators=(",", ":")),
            json.dumps(row["cip"], ensure_ascii=False, separators=(",", ":")),
            json.dumps(row["goodwill"], ensure_ascii=False, separators=(",", ":")),
            json.dumps(row["debt_purpose"], ensure_ascii=False, separators=(",", ":")),
            json.dumps(row["signed_profit"], ensure_ascii=False, separators=(",", ":")),
            json.dumps(row["missingness"], ensure_ascii=False, separators=(",", ":")),
            json.dumps(row["annual"], ensure_ascii=False, separators=(",", ":"))])
    for sheet in (method, audit):
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
    book.save(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--anchors", type=Path, default=Path(__file__).resolve().parent / "acquisition_anchors.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ground-truth", type=Path)
    parser.add_argument("--workbook", type=Path, help="also render the delivered .xlsx")
    args = parser.parse_args()
    answer, ground_truth, ground_truth_lineage = solve(args.workspace.resolve(), args.anchors.resolve())
    args.output.write_text(json.dumps(answer, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.ground_truth:
        args.ground_truth.write_text(json.dumps(ground_truth, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        lineage_path = args.ground_truth.parent / "ground_truth_lineage.json"
        lineage_path.write_text(json.dumps(ground_truth_lineage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"WROTE {lineage_path}")
    if args.workbook:
        write_shortlist_workbook(answer, args.workbook.resolve())
        print(f"WROTE {args.workbook}")
    print(f"WROTE {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
