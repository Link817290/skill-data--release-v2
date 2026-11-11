#!/usr/bin/env python3
"""Semantic v8 verifier. Truth is recomputed only from supplied materials."""

from __future__ import annotations

from pathlib import Path
import hashlib
import json
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "solution"))
import item_checks as v7  # noqa: E402
from sheet_primitives import Score, best_table, boolean, close, column, item_id, norm, number, value, workbook  # noqa: E402
from q12_pipeline import advanced_tables, adopted, calibration_targets, load_raw  # noqa: E402


def old_item(report: dict, name: str) -> float:
    return next((float(x["earned"]) for x in report.get("items", []) if x["item"] == name), 0.0)


def table(book: dict, required: list[list[str]], hits: int):
    return best_table(book, required, hits) if book else None


def equivalent(raw, expected) -> bool:
    """Accept proportion, percentage-point, and 1-5 score units when labelled."""
    return close(raw, expected, 1e-5) or close(raw, expected * 5, 1e-5) or close(raw, expected * 100, 1e-4)


def metric_map(book: dict, keys=("metric", "estimand", "component", "指标", "估计量", "分量")) -> dict[str, object]:
    candidate = table(book, [[*keys], ["value", "数值", "结果"]], 2)
    if not candidate:
        return {}
    sheet, ri, headers = candidate
    kc = column(headers, list(keys)); vc = column(headers, ["value", "数值", "结果"])
    return {norm(value(row, kc)): value(row, vc) for row in book[sheet][ri + 1:] if value(row, kc) != ""}


def primary_checks(analysis: dict, truth: list[list[object]]) -> tuple[int, bool]:
    exp = truth[1]
    found = table(analysis, [["estimand", "metric", "view", "估计量"], ["itemset", "anchoritems", "题集"], ["alphan", "alpha样本"], ["betan", "beta样本"], ["alphapct", "alphapercent", "alphascorepct", "alpha得分"], ["betapct", "betapercent", "betascorepct", "beta得分"], ["changepct", "changepp", "变化"]], 5)
    if not found:
        return 0, False
    sheet, ri, h = found; rows = analysis[sheet][ri + 1:]
    ec = column(h, ["estimand", "metric", "view", "估计量"])
    ac = column(h, ["alphapct", "alphapercent", "alphascore", "alphascorepct", "alpha得分"]); bc = column(h, ["betapct", "betapercent", "betascore", "betascorepct", "beta得分"]); dc = column(h, ["changepct", "changepp", "changescore", "变化"])
    row = next((r for r in rows if equivalent(value(r, ac), exp[4]) and equivalent(value(r, bc), exp[5]) and equivalent(value(r, dc), exp[6])), [])
    checks = sum((
        number(value(row, column(h, ["alphan", "alpha样本"]))) == exp[2],
        number(value(row, column(h, ["betan", "beta样本"]))) == exp[3],
        equivalent(value(row, ac), exp[4]),
        equivalent(value(row, bc), exp[5]),
        equivalent(value(row, dc), exp[6]),
    ))
    item_text = norm(value(row, column(h, ["itemset", "anchoritems", "题集"])))
    mentioned = {int(q) for q in re.findall(r"q0*([0-9]{1,2})", item_text)}
    required = {1, 2, 4, 5, 6, 8, 9, 10, 11, 12}
    explicit = required <= mentioned and not ({3, 7} & mentioned)
    excluded_pair = {3,7} <= mentioned and bool(re.search(r"exclude|excluding|except|remove|omit|剔除|排除|不含",item_text))
    ten_item_description = bool(re.search(r"(?:10items?|10questions?|10题|十题)", item_text))
    checks += explicit or "10anchor" in item_text or ("anchor" in item_text and "excludeq03q07" in item_text) or (ten_item_description and excluded_pair)
    uncertainty = all(column(h, names) is not None for names in (["jackknifese", "replicatese", "changese", "标准误"], ["normalcilow", "ci95lowscore", "cilow", "区间下限"], ["normalcihigh", "ci95highscore", "cihigh", "区间上限"]))
    return checks, uncertainty


def replicate_checks(analysis: dict, truth: list[list[object]]) -> tuple[int, bool]:
    found = table(analysis, [["variancegroup", "replicategroup", "方差组"], ["alphan", "alpharetainedn", "alpha样本"], ["betan", "betaretainedn", "beta样本"], ["alphaanchorpct", "alphaestimatepercent", "alphaestimate", "alpha得分"], ["betaanchorpct", "betaestimatepercent", "betaestimate", "beta得分"], ["changepct", "changepp", "difference", "变化"]], 5)
    if not found:
        return 0, False
    sheet, ri, h = found; gc = column(h, ["variancegroup", "replicategroup", "方差组"])
    cols = [column(h, names) for names in (["alphan", "alpharetainedn", "alpha样本"], ["betan", "betaretainedn", "beta样本"], ["alphaanchorpct", "alphaestimatepercent", "alphaestimate", "alpha得分"], ["betaanchorpct", "betaestimatepercent", "betaestimate", "beta得分"], ["changepct", "changepp", "difference", "变化"])]
    found_rows = {int(number(value(r, gc))): r for r in analysis[sheet][ri + 1:] if number(value(r, gc)) in range(1, 21)}
    correct = 0
    for exp in truth[1:]:
        row = found_rows.get(int(exp[0]), [])
        correct += all((number(value(row, cols[0])) == exp[1], number(value(row, cols[1])) == exp[2], equivalent(value(row, cols[2]), exp[3]), equivalent(value(row, cols[3]), exp[4]), equivalent(value(row, cols[4]), exp[5])))
    convergence = column(h, ["converged", "success", "failurestatus", "收敛"]) is not None
    return correct, convergence


def sensitivity_checks(analysis: dict, truth: list[list[object]]) -> int:
    found = table(analysis, [["scenario", "情景"], ["itemset", "题集"], ["weighting", "权重方法"], ["alphan", "alpha样本"], ["betan", "beta样本"], ["alphapct", "alphascore", "alpha得分"], ["betapct", "betascore", "beta得分"], ["changepct", "changepp", "变化"]], 5)
    if not found:
        return 0
    sheet, ri, h = found; rows = analysis[sheet][ri + 1:]
    correct = 0
    for exp in truth[1:]:
        cols = [column(h, names) for names in (["alphan", "alpha样本"], ["betan", "beta样本"], ["alphapct", "alphascore", "alpha得分"], ["betapct", "betascore", "beta得分"], ["changepct", "changepp", "变化"])]
        match = next((row for row in rows if number(value(row, cols[0])) == exp[4] and number(value(row, cols[1])) == exp[5] and equivalent(value(row, cols[2]), exp[6]) and equivalent(value(row, cols[3]), exp[7]) and equivalent(value(row, cols[4]), exp[8])), None)
        correct += match is not None
    return correct


def panel_checks(analysis: dict, truth: list[list[object]]) -> int:
    expected = {norm(r[0]): r[1] for r in truth[1:]}
    values = {}; best = -1
    for rows in analysis.values():
        for ri, headers in enumerate(rows[:40]):
            kc = column(headers, ["metric", "指标"]); vc = column(headers, ["value", "数值", "结果"])
            if kc is None or vc is None:
                continue
            candidate = {norm(value(r, kc)): value(r, vc) for r in rows[ri + 1:] if value(r, kc) != ""}
            hits = sum(key in candidate for key in expected)
            if hits > best:
                best = hits; values = candidate
    direct = sum(equivalent(values.get(key), exp) for key, exp in expected.items())
    wide = table(analysis, [["paneln", "pairedn", "面板人数"], ["alphascore", "alphapct", "alpha得分"], ["betascore", "betapct", "beta得分"], ["difference", "changepp", "变化"], ["sdperson", "deltasd", "差值标准差"], ["sedifference", "deltase", "标准误"]], 4)
    if wide:
        sheet, ri, h = wide; rows = analysis[sheet][ri + 1:]; row = rows[0] if rows else []
        aliases_ = (["paneln", "pairedn", "面板人数"], ["alphascore", "alphapct", "alpha得分"], ["betascore", "betapct", "beta得分"], ["difference", "changepp", "变化"], ["sdpersondifferences", "deltasd", "差值标准差"], ["sedifferencescore", "deltase", "标准误"], ["ci95lowscore", "cilow", "区间下限"], ["ci95highscore", "cihigh", "区间上限"])
        direct = max(direct, sum(equivalent(value(row, column(h, names)), exp) for names, exp in zip(aliases_, expected.values())))
    return direct


# The four decomposition components, and the wordings a correct answer may use
# for each. The deliverable contract does not fix a sheet name, a table layout or
# a spelling for these rows, so a checker that only accepts one of them scores
# formatting luck rather than whether the decomposition was carried out. Each
# component is matched by an adjacent label, never by a bare numeric match.
DECOMP_LABELS = {
    "crosssectionanchorchange": ("crosssection", "anchorchange", "totalcomponent", "totalchange"),
    "withincomponent": ("within",),
    "compositioncomponent": ("composition", "sharecomponent", "betweencomponent"),
    "reconciliationerror": ("reconcil", "residual"),
}


def _label_matches(text: str, component: str) -> bool:
    key = norm(text)
    if not key:
        return False
    if key == component:
        return True
    # "composition" also prefixes the composition-component synonyms of other
    # rows, so require the fragment to carry the component's own wording.
    return any(fragment in key for fragment in DECOMP_LABELS[component])


def _label_anchored(analysis: dict, component: str, expected: float) -> bool:
    """True when the expected value sits in a row or column carrying this label."""
    for rows in analysis.values():
        for ri, row in enumerate(rows):
            for ci, cell in enumerate(row):
                if not isinstance(cell, str) or not _label_matches(cell, component):
                    continue
                # long form: label in this row, value further along the row
                if any(close(other, expected) for other in row[ci + 1:]):
                    return True
                # wide form: label in a header cell, value below it in the column
                for below in rows[ri + 1: ri + 12]:
                    if ci < len(below) and close(below[ci], expected):
                        return True
    return False


def decomposition_checks(analysis: dict, truth: list[list[object]]) -> int:
    expected = {norm(r[0]): r[1] for r in truth[1:]}
    found = table(analysis, [["component", "分量"], ["valuepct", "value", "结果"]], 2)
    values = {}
    if found:
        sheet, ri, h = found; kc = column(h, ["component", "分量"]); vc = column(h, ["valuepct", "value", "结果"])
        values = {norm(value(r, kc)): value(r, vc) for r in analysis[sheet][ri + 1:]}
    hits = 0
    for key, exp in expected.items():
        if close(values.get(key), exp):
            hits += 1
        elif key in DECOMP_LABELS and _label_anchored(analysis, key, exp):
            hits += 1
    return hits


def multiplicity_checks(analysis: dict, truth: list[list[object]]) -> tuple[int, bool]:
    found = table(analysis, [["item", "canonicalitem", "题号"], ["changepct", "changepp", "变化"], ["jackknifese", "replicatese", "jks e", "jkse", "标准误"], ["ptwosided", "rawp", "pvalue", "p值"], ["bhq", "adjustedp", "qvalue", "q值"]], 4)
    if not found:
        return 0, False
    sheet, ri, h = found; qi = column(h, ["item", "题号"]); rows = {item_id(value(r, qi)): r for r in analysis[sheet][ri + 1:] if item_id(value(r, qi))}
    cols = [column(h, names) for names in (["changepct", "changepp", "变化"], ["jackknifese", "replicatese", "jksescore", "jkse", "标准误"], ["ptwosided", "rawp", "pvalue", "p值"], ["bhq", "adjustedp", "qvalue", "q值"])]
    correct = 0
    for exp in truth[1:]:
        row = rows.get(str(exp[0]), [])
        correct += all(equivalent(value(row, col), target) for col, target in zip(cols, (exp[4], exp[5], exp[7], exp[8])))
    separate = all(col is not None for col in cols)
    return correct, separate


def evaluate(root: Path) -> dict:
    materials = root / "materials"; output = root / "output"; score = Score()
    raw, item_meta = load_raw(materials); advanced = advanced_tables(raw, materials, item_meta)
    files = {name: output / name for name in ("cleaned_samples.xlsx", "engagement_analysis.xlsx")}
    notes = "\n".join(str(x) for rows in workbook(files["engagement_analysis.xlsx"]).values() for row in rows for x in row if isinstance(x, str)) if files["engagement_analysis.xlsx"].exists() else ""
    clean = workbook(files["cleaned_samples.xlsx"]) if files["cleaned_samples.xlsx"].exists() else {}
    analysis = workbook(files["engagement_analysis.xlsx"]) if files["engagement_analysis.xlsx"].exists() else {}
    old = v7.evaluate(root); old_caps = old.get("caps", [])

    score.add("A1", 3, old_item(old, "A1"), "physical source ledger")
    score.add("A2", 4, 4 * old_item(old, "A2") / 3, "mapped source and standardized values")
    score.add("A3", 3, old_item(old, "A3"), "logical response deduplication")
    state_table = table(clean, [["responsekey", "响应键"], ["canonical", "dedupdecision", "采用"], ["straightline", "直线"], ["hardeligible", "硬资格"]], 3)
    has_hard = bool(state_table and column(state_table[2], ["hardeligible", "硬资格"]) is not None)
    score.add("A4", 3, 3 if has_hard and old_item(old, "A4") >= 2 else max(old_item(old, "A4"), 2.5 if state_table else 0), "analysis state machine")
    roles = table({**clean, **analysis}, [["item", "canonicalitem", "题号"], ["trendrole", "comparability", "趋势角色"]], 2)
    role_ok = 0
    if roles:
        sheet, ri, h = roles; qi = column(h, ["item", "canonicalitem", "题号"]); rc = column(h, ["trendrole", "comparability", "趋势角色"])
        found = {item_id(value(r, qi)): norm(value(r, rc)) for r in ({**clean, **analysis})[sheet][ri + 1:] if item_id(value(r, qi))}
        role_ok = sum(("context" in found.get(f"Q{q:02d}", "")) if q in (3, 7) else ("anchor" in found.get(f"Q{q:02d}", "")) for q in range(1, 13))
    if "q03" in norm(notes) and "q07" in norm(notes) and "anchor" in notes.lower(): role_ok = max(role_ok, 12)
    score.add("A5", 2, 2 * role_ok / 12, f"trend_roles={role_ok}/12")

    score.add("B1", 6, 6 * old_item(old, "B1") / 10, "purpose-aware bridge")
    people_table = table(clean, [["responsekey", "响应键"], ["coreactive", "employmentvalid", "任职有效"], ["technicallevel", "技术级别"]], 2)
    people_fields = 0; usable_correct = 0
    if people_table:
        sheet, ri, ph = people_table; rows = clean[sheet][ri + 1:]; rk = column(ph, ["responsekey", "响应键"]); uc = column(ph, ["personnelattributesusable", "coreactiveonsubmit", "coreactiveatsubmission", "任职有效"])
        people_fields = sum(column(ph, names) is not None for names in (["coreactive", "personnelattributesusable", "employmentvalid", "任职有效"], ["ageyears", "ageband", "年龄"], ["tenureyears", "tenureband", "司龄"], ["technicallevel", "技术级别"]))
        expected = {r["response_key"]: r for r in raw}
        for row in rows:
            exp = expected.get(str(value(row, rk)).strip())
            if exp and boolean(value(row, uc)) is exp["attr_usable"]: usable_correct += 1
    snapshot_doc = "2025-08-31" in notes and any(x in notes for x in ("不", "未", "不能"))
    score.add("B2", 4, 2 * usable_correct / 795 + 1.5 * people_fields / 4 + 0.5 * snapshot_doc, f"usable={usable_correct}/795, fields={people_fields}/4")
    strict_panel = panel_checks(analysis, advanced["panel_anchor"])
    identity_cap = any("purpose-limited identity bridge misused" in x.get("reason", "") for x in old_caps)
    score.add("B3", 5, 5 if strict_panel >= 4 and not identity_cap else old_item(old, "B3"), "strict panel population")

    score.add("C1", 3, min(3, 3 * old_item(old, "A5") / 3), "calibration categories and support")
    weight_exact = old_item(old, "D1") >= 9.99
    score.add("C2", 7, 7 if weight_exact else 0, "response-level required final weights")
    score.add("C3", 5, 5 * old_item(old, "D2") / 8, "achieved margins")
    diag = table(analysis, [["wave", "波次"], ["kishess", "有效样本"], ["designeffect", "设计效应"], ["minw", "minimum", "最小权重"], ["maxw", "maximum", "最大权重"]], 4)
    extra_diag = 0
    if diag:
        _, _, h = diag; quantiles = sum(column(h, names) is not None for names in (["p01", "q01", "1stpercentile"], ["p05", "q05", "5thpercentile"], ["p25", "q25", "25thpercentile"], ["p50", "median", "中位数"], ["p75", "q75", "75thpercentile"], ["p95", "q95", "95thpercentile"], ["p99", "q99", "99thpercentile"])); extra_diag = (column(h, ["weightcv", "coefficientvariation", "coefficientofvariation", "变异系数"]) is not None) + min(3, quantiles)
    diag_credit = 5 if weight_exact and diag and extra_diag >= 4 else 4 if diag and extra_diag >= 3 else 3 * old_item(old, "D3") / 5 + 2 * min(1, extra_diag / 4)
    score.add("C4", 5, diag_credit, f"diagnostics, extra={extra_diag}/4")

    primary, uncertainty_columns = primary_checks(analysis, advanced["primary_trend"])
    score.add("D1", 6, 6 if primary == 6 else 0, f"primary={primary}/6")
    replicates, replicate_convergence = replicate_checks(analysis, advanced["jackknife_replicates"])
    score.add("D2", 8, 7.5 * replicates / 20 + 0.5 * replicate_convergence, f"replicates={replicates}/20")
    expected_primary = advanced["primary_trend"][1]
    ptab = table(analysis, [["jackknifese", "replicatese", "changesescore", "标准误"], ["normalcilow", "ci95lowscore", "cilow", "区间下限"], ["normalcihigh", "ci95highscore", "cihigh", "区间上限"]], 2)
    unc = 0
    if ptab:
        sheet, ri, h = ptab; rows = analysis[sheet][ri + 1:]; sec = column(h, ["jackknifese", "replicatese", "changesescore", "标准误"]); lc = column(h, ["normalcilow", "ci95lowscore", "cilow", "区间下限"]); hc = column(h, ["normalcihigh", "ci95highscore", "cihigh", "区间上限"])
        row = next((r for r in rows if equivalent(value(r, sec), expected_primary[7]) and equivalent(value(r, lc), expected_primary[8]) and equivalent(value(r, hc), expected_primary[9])), [])
        unc = sum((equivalent(value(row, sec), expected_primary[7]), equivalent(value(row, lc), expected_primary[8]), equivalent(value(row, hc), expected_primary[9])))
    uncertainty_evidence = unc == 3
    score.add("D3", 4, 4 * unc / 3 if unc else 0.5 if uncertainty_evidence else 0, f"uncertainty={unc}/3")
    sens_correct = sensitivity_checks(analysis, advanced["sensitivity_matrix"])
    sensitivity_table = table(analysis, [["scenario", "情景"], ["alpha", "2023"], ["beta", "2024"], ["change", "变化"]], 3)
    score.add("D4", 2, 2 * min(1, sens_correct / 4) if sens_correct else 1 if sensitivity_table else 0, f"estimand contrasts={sens_correct}/6")

    panel = strict_panel
    score.add("E1", 5, 5 * panel / 8 if panel >= 7 else 4.5 if panel >= 6 else 5 * panel / 8, f"anchor_panel={panel}/8")
    decomp = decomposition_checks(analysis, advanced["anchor_decomposition"])
    score.add("E2", 4, decomp, f"anchor_decomposition={decomp}/4")
    multi, separate = multiplicity_checks(analysis, advanced["multiplicity_items"])
    multiplicity_table = table(analysis, [["item", "canonicalitem", "题号"], ["pvalue", "rawp", "p值"], ["qvalue", "bhq", "q值"]], 2)
    score.add("E3", 7, 6.5 * multi / 12 + 0.5 * separate if multi else 2 if multiplicity_table else 0, f"multiplicity={multi}/12")
    score.add("E4", 5, 5 * sens_correct / 6 if sens_correct else 3 if sensitivity_table else 0, f"sensitivity={sens_correct}/6")
    score.add("E5", 4, min(old_item(old, "E4"), 4 if weight_exact else 2), "business action and suppression")

    present = all(path.exists() for path in files.values()); distinct = present and hashlib.sha256(files["cleaned_samples.xlsx"].read_bytes()).digest() != hashlib.sha256(files["engagement_analysis.xlsx"].read_bytes()).digest()
    score.add("F1", 1, present and distinct, f"present={present}, distinct={distinct}")
    topics = ("来源", "版本", "去重", "身份", "权重", "jackknife", "面板", "kitagawa", "benjamini", "敏感", "抑制", "因果")
    score.add("F2", 2, 2 * sum(term in notes.lower() for term in topics) / len(topics), "method-chain coverage")
    text = notes + "\n" + "\n".join(str(x) for book in (clean, analysis) for rows in book.values() for row in rows for x in row if isinstance(x, str))
    privacy = any(re.search(pattern, text) for pattern in (r"(?<!\d)1[3-9]\d{9}(?!\d)", r"[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}", r"(?<!\d)\d{17}[\dXx](?!\d)"))
    score.add("F3", 2, 0 if privacy else 2, f"privacy_violation={privacy}")

    weight_table = table(clean, [["responsekey", "响应键"], ["finalweight", "finalcalibrationweight", "calibrationweight", "最终权重"]], 2)
    weighted_keys = set()
    if weight_table:
        sheet, ri, wh = weight_table; rk = column(wh, ["responsekey", "响应键"]); wc = column(wh, ["finalweight", "finalcalibrationweight", "calibrationweight", "最终权重"])
        weighted_keys = {str(value(r, rk)).strip() for r in clean[sheet][ri + 1:] if str(value(r, rk)).strip() and number(value(r, wc)) is not None}
    missing_weight = len(weighted_keys) < 700 or old_item(old, "D2") < 7.9
    identity_misuse = any("purpose-limited identity bridge misused" in x.get("reason", "") for x in old_caps)
    duplicate_inflation = any("wrong logical response population" in x.get("reason", "") for x in old_caps) and old_item(old, "A1") >= 2.9 and old_item(old, "A2") >= 2.9
    if missing_weight: score.cap(25, "missing reproducible final calibration weights")
    if identity_misuse: score.cap(30, "purpose-limited identity bridge misused for panel")
    if duplicate_inflation: score.cap(30, "wrong logical response population")
    if not uncertainty_evidence: score.cap(45, "missing reproducible primary trend uncertainty")
    if present and not distinct: score.cap(20, "two XLSX files identical")
    if not present: score.cap(50, "missing deliverable")
    if privacy: score.cap(0, "privacy disclosure")
    final = score.final()
    return {"reward": round(final / 100, 4), "score": round(final, 4), "uncapped_score": round(score.total, 4), "caps": score.caps, "items": score.items}


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "/app/environment").resolve()
    try:
        report = evaluate(root)
    except Exception as exc:
        report = {"reward": 0.0, "score": 0.0, "uncapped_score": 0.0, "caps": [{"maximum": 0, "reason": f"verifier error: {type(exc).__name__}: {exc}"}], "items": []}
    for directory in (root / "verifier", Path("/logs/verifier"), Path("/verifier")):
        try:
            directory.mkdir(parents=True, exist_ok=True); (directory / "reward.txt").write_text(f"{report['reward']}\n"); (directory / "reward.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
        except Exception:
            pass
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
