#!/usr/bin/env python3
"""Semantic v9 verifier; all numeric truth is derived from supplied inputs."""

from __future__ import annotations

from pathlib import Path
import hashlib
import json
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "solution"))
import metric_checks as v8  # noqa: E402
from sheet_primitives import Score, best_table, close, column, item_id, norm, number, value, workbook  # noqa: E402
from q12_pipeline import load_raw, v9_quality_tables  # noqa: E402


def oi(report, key):
    return next((float(x["earned"]) for x in report.get("items", []) if x["item"] == key), 0.0)


def tab(book, required, hits=None):
    return best_table(book, required, hits) if book else None


def eq(raw, expected):
    return close(raw, expected, 1e-5) or close(raw, expected * 5, 1e-5) or close(raw, expected * 100, 1e-4)


def all_rows(analysis):
    return [row for rows in analysis.values() for row in rows]


def key_match(cell, key):
    """标识匹配：数值型比数值，文本型比规范化后的字符串。"""
    return number(cell) == key if isinstance(key, (int, float)) else norm(cell) == norm(key)


def carried(rows, keys, values, match=close):
    """某一行同时带上全部标识和全部期望数值，就算这一条对上了。

    判数值不判命名。同一个量的列名写法是开放集合——`alpha_estimate`、`estimate_alpha`、
    `period_1_estimate`、`alpha_anchor_pct` 指的都是它——别名表只能枚举有限几种，
    枚举不到就把算对的判成没做。十几位有效数字下，一行里恰好凑齐这些值不可能是巧合，
    所以直接认数值。
    """
    return any(
        all(any(key_match(cell, k) for cell in row) for k in keys)
        and all(any(match(cell, v) for cell in row) for v in values)
        for row in rows
    )


def wave_keys(row, header, primary):
    """这一行波次的所有写法。

    波次可能同时以描述性长名和短码出现在相邻两列（`period` = `alpha_2023_wave`，
    `wave_code` = `alpha`）。只认第一命中的列，就会整表查不到行、信度块全部归零，
    而短码其实就在隔壁。把该行每个波次列的写法都登记为键。
    """
    cols = [primary] + [i for i, cell in enumerate(header) if any(a in norm(cell) for a in ("wave", "period", "波次"))]
    return {norm(value(row, c)) for c in cols if c is not None and norm(value(row, c))}


def wave_index(rows, header, primary, key=None):
    """按波次的每种写法建行索引；`key` 可再附加一个行内键，例如题目 ID。"""
    found = {}
    for row in rows:
        for wave in wave_keys(row, header, primary):
            found.setdefault((wave, key(row)) if key else wave, row)
    return found


def reliability_evidence(analysis, truth):
    summary = tab(analysis, [["wave", "period", "波次"], ["cronbachalpha", "reliability", "信度"], ["n", "样本量"], ["items", "itemset", "itemcount", "题集"]], 3)
    summary_ok = 0
    if summary:
        s, ri, h = summary; wc = column(h, ["wave", "period", "波次"]); nc = column(h, ["n", "样本量"]); ac = column(h, ["weightedcronbachalpha", "cronbachalpha", "reliability", "信度"]); found = wave_index(analysis[s][ri + 1:], h, wc)
        for exp in truth["reliability_summary"][1:]:
            row = found.get(norm(exp[0]), []); summary_ok += number(value(row, nc)) == exp[1] and close(value(row, ac), exp[3])
    deleted = tab(analysis, [["wave", "period", "波次"], ["deleteditem", "item", "删题"], ["alphaifdeleted", "deletedalpha", "删题alpha"], ["correcteditemtotal", "itemtotal", "题总相关"]], 3)
    alpha_deleted = citc = 0; deleted_rows = 0
    if deleted:
        s, ri, h = deleted; wc = column(h, ["wave", "period", "波次"]); qc = column(h, ["deleteditem", "item", "删题"]); ac = column(h, ["alphaifdeleted", "deletedalpha", "删题alpha"]); cc = column(h, ["correcteditemtotalcorrelation", "correcteditemtotal", "itemtotal", "题总相关"]); rows = analysis[s][ri + 1:]; deleted_rows = len(rows)
        found = wave_index(rows, h, wc, key=lambda r: item_id(value(r, qc)))
        for exp in truth["reliability_deleted"][1:]:
            row = found.get((norm(exp[0]), exp[1]), []); alpha_deleted += close(value(row, ac), exp[3]); citc += close(value(row, cc), exp[4])
    reps = tab(analysis, [["variancegroup", "replicategroup", "方差组"], ["alphareliability", "alphaalpha", "alphaperiodalpha"], ["betareliability", "betaalpha", "alphaperiodbeta", "betaperiodalpha"], ["reliabilitychange", "alphachange", "alphachangebetaminusalpha", "信度变化"]], 3)
    rep_ok = 0; rep_rows = 0
    if reps:
        s, ri, h = reps; gc = column(h, ["variancegroup", "replicategroup", "方差组"]); ac = column(h, ["alphareliability", "alphaalpha", "alphaperiodalpha"]); bc = column(h, ["betareliability", "betaalpha", "alphaperiodbeta", "betaperiodalpha"]); dc = column(h, ["reliabilitychange", "alphachange", "alphachangebetaminusalpha", "信度变化"]); rows = analysis[s][ri + 1:]; rep_rows = len(rows); found = {int(number(value(r, gc))): r for r in rows if number(value(r, gc)) in range(1, 21)}
        for exp in truth["reliability_jackknife"][1:]:
            row = found.get(exp[0], []); rep_ok += close(value(row, ac), exp[3]) and close(value(row, bc), exp[4]) and close(value(row, dc), exp[5])
    # 名字路径没认出来的，按数值再认一遍（见 carried 的说明）。
    rows_all = all_rows(analysis)
    if summary_ok < len(truth["reliability_summary"]) - 1:
        summary_ok = max(summary_ok, sum(carried(rows_all, [exp[1]], [exp[3]]) for exp in truth["reliability_summary"][1:]))
    if alpha_deleted < len(truth["reliability_deleted"]) - 1:
        alpha_deleted = max(alpha_deleted, sum(carried(rows_all, [exp[1]], [exp[3]]) for exp in truth["reliability_deleted"][1:]))
    if citc < len(truth["reliability_deleted"]) - 1:
        citc = max(citc, sum(carried(rows_all, [exp[1]], [exp[4]]) for exp in truth["reliability_deleted"][1:]))
    if rep_ok < len(truth["reliability_jackknife"]) - 1:
        rep_ok = max(rep_ok, sum(carried(rows_all, [exp[0]], [exp[3], exp[4], exp[5]]) for exp in truth["reliability_jackknife"][1:]))

    change = tab(analysis, [["metric", "指标"], ["value", "数值"]], 2); change_ok = 0
    expected = {norm(r[0]): r[1] for r in truth["reliability_change"][1:]}
    best_values = {}
    if change:
        for s, rows in analysis.items():
            for ri, h in enumerate(rows[:30]):
                kc = column(h, ["metric", "指标"]); vc = column(h, ["value", "数值"])
                if kc is None or vc is None: continue
                vals = {norm(value(r, kc)): value(r, vc) for r in rows[ri + 1:]}; hits = sum(k in vals for k in expected)
                if hits > sum(k in best_values for k in expected): best_values = vals
        change_ok = sum(close(best_values.get(k), x) for k, x in expected.items())
    # 宽表兜底：同一组量可以一行多列地发布，指标名在表头而不在首列，长表查找就整块落空。
    # 只对长表没认出来的指标按数值找，十几位有效数字下误命中不成立。
    missing = {k: x for k, x in expected.items() if not close(best_values.get(k), x)}
    if missing:
        cells = [cell for rows in analysis.values() for row in rows for cell in row]
        change_ok += sum(any(close(cell, x) for cell in cells) for x in missing.values())
    presence = summary is not None and deleted_rows >= 20 and rep_rows >= 20 and (change is not None or change_ok >= 5)
    return summary_ok, alpha_deleted, citc, rep_ok, change_ok, presence


def org_evidence(analysis, truth):
    direct = tab(analysis, [["surveyorg", "组织"], ["directchange", "directchangebetaminusalpha", "直接变化"], ["jackknifese", "replicatese", "标准误"], ["shrinkagefactor", "shrinkagelambda", "收缩因子"], ["ebchange", "ebstabilizedchange", "收缩变化"], ["simcilow", "simultaneouscilcl", "simultaneouscilclarounddirect", "simultaneouscilow", "同时下限"], ["simcihigh", "simultaneousciucl", "simultaneousciuclarounddirect", "simultaneouscihigh", "同时上限"]], 5)
    direct_ok = eb_ok = ci_ok = 0; org_rows = 0
    if direct:
        s, ri, h = direct; oc = column(h, ["surveyorg", "组织"]); rows = analysis[s][ri + 1:]; org_rows = len(rows); found = {str(value(r, oc)): r for r in rows}
        for exp in truth["org_small_domain"][1:]:
            row = found.get(exp[0], []); direct_ok += number(value(row, column(h, ["alphan", "alpharetainedn", "alpha样本"]))) == exp[1] and number(value(row, column(h, ["betan", "betaretainedn", "beta样本"]))) == exp[2] and eq(value(row, column(h, ["directchangepct", "directchange", "directchangebetaminusalpha", "直接变化"])), exp[3]) and eq(value(row, column(h, ["jackknifese", "replicatese", "标准误"])), exp[4])
            eb_ok += close(value(row, column(h, ["tau2", "betweenvariance", "betweendomaintau2"])), exp[5]) and close(value(row, column(h, ["shrinkagefactor", "shrinkagelambda", "lambda", "收缩因子"])), exp[6]) and eq(value(row, column(h, ["ebchangepct", "ebchange", "ebstabilizedchange", "收缩变化"])), exp[7])
            ci_ok += close(value(row, column(h, ["simultaneouscritical", "maxcritical", "sharedmaxtcritical95", "sharedmaxtcritical", "同时临界值"])), exp[8]) and eq(value(row, column(h, ["simcilow", "simultaneouscilcl", "simultaneouscilclarounddirect", "simultaneouscilow", "同时下限"])), exp[9]) and eq(value(row, column(h, ["simcihigh", "simultaneousciucl", "simultaneousciuclarounddirect", "simultaneouscihigh", "同时上限"])), exp[10])
    reps = tab(analysis, [["variancegroup", "方差组"], ["surveyorg", "组织"], ["replicatechange", "replicatedirectchange", "directchangereplicate", "directchange", "复制变化"]], 3); rep_ok = 0; rep_rows = 0
    if reps:
        s, ri, h = reps; gc = column(h, ["variancegroup", "方差组"]); oc = column(h, ["surveyorg", "组织"]); vc = column(h, ["replicatechangepct", "replicatechange", "replicatedirectchange", "directchangereplicate", "directchange", "复制变化"]); rows = analysis[s][ri + 1:]; rep_rows = len(rows); found = {(int(number(value(r, gc))), str(value(r, oc))): r for r in rows if number(value(r, gc)) in range(1, 21)}
        for exp in truth["org_replicates"][1:]: rep_ok += eq(value(found.get((exp[0], exp[1]), []), vc), exp[2])
    # 名字路径没认出来的，按数值再认一遍（见 carried 的说明）。
    rows_all = all_rows(analysis); orgs = truth["org_small_domain"][1:]
    if direct_ok < len(orgs):
        direct_ok = max(direct_ok, sum(carried(rows_all, [exp[0], exp[1], exp[2]], [exp[3], exp[4]], eq) for exp in orgs))
    if eb_ok < len(orgs):
        eb_ok = max(eb_ok, sum(carried(rows_all, [exp[0]], [exp[5], exp[6], exp[7]], eq) for exp in orgs))
    if ci_ok < len(orgs):
        ci_ok = max(ci_ok, sum(carried(rows_all, [exp[0]], [exp[8], exp[9], exp[10]], eq) for exp in orgs))
    if rep_ok < len(truth["org_replicates"]) - 1:
        rep_ok = max(rep_ok, sum(carried(rows_all, [exp[0], exp[1]], [exp[2]], eq) for exp in truth["org_replicates"][1:]))
    return direct_ok, rep_ok, eb_ok, ci_ok, org_rows, rep_rows


def panel_selection(analysis, truth):
    t = tab(analysis, [["wave", "period", "波次"], ["cohort", "组别"], ["n", "样本量"], ["anchormean", "unweightedanchormean", "均值"], ["panelminusnonpanel", "meanpersonchangebetaminusalpha", "差异"]], 4)
    if not t: return 0
    s, ri, h = t; wc = column(h, ["wave", "period", "波次"]); cc = column(h, ["cohort", "组别"]); found = {(norm(value(r, wc)), norm(value(r, cc))): r for r in analysis[s][ri + 1:]}; ok = 0
    for exp in truth[1:]:
        row = found.get((norm(exp[0]), norm(exp[1])), []); ok += number(value(row, column(h, ["n", "样本量"]))) == exp[2] and eq(value(row, column(h, ["anchormeanpct", "anchormean", "unweightedanchormean", "均值"])), exp[3]) and eq(value(row, column(h, ["differencepanelminusnonpanel", "panelminusnonpanel", "meanpersonchangebetaminusalpha", "差异"])), exp[4])
    return ok


def evaluate(root: Path):
    materials = root / "materials"; output = root / "output"; score = Score(); raw, meta = load_raw(materials); truth = v9_quality_tables(raw, materials, meta)
    old = v8.evaluate(root); files = {n: output / n for n in ("cleaned_samples.xlsx", "engagement_analysis.xlsx")}; notes = "\n".join(str(x) for rows in workbook(files["engagement_analysis.xlsx"]).values() for row in rows for x in row if isinstance(x, str)) if files["engagement_analysis.xlsx"].exists() else ""; analysis = workbook(files["engagement_analysis.xlsx"]) if files["engagement_analysis.xlsx"].exists() else {}
    score.add("A1", 3, 1.5 * oi(old, "A1") / 3 + 1.5 * oi(old, "A2") / 4, "source and mapping")
    score.add("A2", 2, (oi(old, "A3") + oi(old, "A4") + oi(old, "A5")) / 8 * 2, "logical population and version")
    score.add("A3", 3, oi(old, "B1") / 6 * 3, "purpose identity")
    score.add("A4", 2, (oi(old, "B2") / 4 + oi(old, "B3") / 5), "as-of people and strict panel")
    score.add("B1", 7, oi(old, "C2"), "final weights")
    score.add("B2", 3, 1.5 * oi(old, "C3") / 5 + 1.5 * oi(old, "C4") / 5, "weight audit")
    score.add("B3", 5, oi(old, "D1") / 6 * 5, "primary anchor trend")
    score.add("B4", 7, oi(old, "D2") / 8 * 7, "matched replicate ledger")
    score.add("B5", 3, oi(old, "D3") / 4 * 3, "primary uncertainty")
    rs, rd, rc, rr, rch, reliability_present = reliability_evidence(analysis, truth)
    score.add("C1", 4, 2 * rs, f"wave reliability={rs}/2")
    score.add("C2", 5, 5 * rd / 20, f"alpha deleted={rd}/20")
    score.add("C3", 2, 2 * rc / 20, f"item-total={rc}/20")
    score.add("C4", 5, 5 * rr / 20, f"reliability replicates={rr}/20")
    score.add("C5", 4, 4 * rch / 7, f"reliability change={rch}/7")
    direct, oreps, eb, sim, org_rows, org_rep_rows = org_evidence(analysis, truth)
    score.add("D1", 5, 5 * direct / 6, f"org direct={direct}/6")
    score.add("D2", 4, 4 * oreps / 120, f"org replicates={oreps}/120")
    score.add("D3", 5, 5 * eb / 6, f"org EB={eb}/6")
    score.add("D4", 4, 4 * sim / 6, f"simultaneous={sim}/6")
    action_doc = all(x in notes.lower() for x in ("eb", "bh")) and ("同时" in notes or "simultaneous" in notes.lower())
    score.add("D5", 2, 2 if action_doc and org_rows >= 6 else 0, "small-domain action interpretation")
    score.add("E1", 4, oi(old, "E1") / 5 * 4, "anchor panel")
    score.add("E2", 4, oi(old, "E2"), "repeat/nonrepeat decomposition")
    selection = panel_selection(analysis, truth["panel_selection"]); score.add("E3", 3, 3 * selection / 4, f"panel selection={selection}/4")
    score.add("E4", 3, oi(old, "E3") / 7 * 3, "12-item multiplicity")
    score.add("E5", 3, oi(old, "E4") / 5 * 3, "sensitivity")
    boundaries = ("因果" in notes and ("正式响应率" in notes or "response rate" in notes.lower()) and ("抑制" in notes or "n<10" in notes.lower()))
    score.add("E6", 3, 3 if boundaries else 1.5 if notes else 0, "boundaries and suppression")
    score.add("F1", 1, oi(old, "F1"), "deliverables")
    score.add("F2", 2, oi(old, "F2"), "navigation")
    score.add("F3", 2, oi(old, "F3"), "privacy")
    old_caps = old.get("caps", [])
    if any("missing reproducible final calibration weights" in x.get("reason", "") for x in old_caps): score.cap(25, "missing reproducible final calibration weights")
    if not reliability_present: score.cap(45, "missing reproducible anchor-scale quality chain")
    if any("identity bridge misused" in x.get("reason", "") for x in old_caps): score.cap(30, "purpose-limited identity bridge misused")
    if any("wrong logical response population" in x.get("reason", "") for x in old_caps): score.cap(30, "wrong logical response population")
    present = all(x.exists() for x in files.values()); distinct = present and hashlib.sha256(files["cleaned_samples.xlsx"].read_bytes()).digest() != hashlib.sha256(files["engagement_analysis.xlsx"].read_bytes()).digest()
    if not present: score.cap(50, "missing deliverable")
    if present and not distinct: score.cap(20, "two XLSX files identical")
    text = notes + "\n" + "\n".join(str(x) for rows in analysis.values() for row in rows for x in row if isinstance(x, str)); privacy = any(re.search(p, text) for p in (r"(?<!\d)1[3-9]\d{9}(?!\d)", r"[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}"))
    if privacy: score.cap(0, "privacy disclosure")
    final = score.final(); return {"reward": round(final / 100, 4), "score": round(final, 4), "uncapped_score": round(score.total, 4), "caps": score.caps, "items": score.items}


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "/app/environment").resolve()
    try: report = evaluate(root)
    except Exception as exc: report = {"reward": 0.0, "score": 0.0, "uncapped_score": 0.0, "caps": [{"maximum": 0, "reason": f"verifier error: {type(exc).__name__}: {exc}"}], "items": []}
    for directory in (root / "verifier", Path("/logs/verifier"), Path("/verifier")):
        try: directory.mkdir(parents=True, exist_ok=True); (directory / "reward.txt").write_text(f"{report['reward']}\n"); (directory / "reward.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
        except Exception: pass
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
