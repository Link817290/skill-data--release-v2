#!/usr/bin/env python3
"""Semantic v7 verifier; all truth is recomputed from supplied materials."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from statistics import stdev
from zipfile import ZipFile
import hashlib
import json
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "solution"))
from sheet_primitives import (  # noqa: E402
    Score, aliases, best_table, boolean, close, column, item_id, norm, number,
    population_id, scope_id, value, workbook,
)
from q12_pipeline import (  # noqa: E402
    TIER_ORDER, adopted, calibration_targets, load_raw, metric, panel_tables,
    rake_rows, tier_questions,
)

_base_boolean = boolean


def boolean(raw):
    parsed = _base_boolean(raw)
    if parsed is not None:
        return parsed
    text = norm(raw)
    if text.startswith(("keep", "adopted", "yes", "included")):
        return True
    if text.startswith(("drop", "notadopted", "no", "excluded")):
        return False
    return None


def evaluate(root: Path) -> dict:
    materials = root / "materials"; output = root / "output"; score = Score()
    expected_raw, item_meta = load_raw(materials); expected_main = adopted(expected_raw); expected_sens = adopted(expected_raw, True)
    files = {name: output / name for name in ("cleaned_samples.xlsx", "engagement_analysis.xlsx")}
    notes = "\n".join(str(x) for rows in workbook(files["engagement_analysis.xlsx"]).values() for row in rows for x in row if isinstance(x, str)) if files["engagement_analysis.xlsx"].exists() else ""
    clean = workbook(files["cleaned_samples.xlsx"]) if files["cleaned_samples.xlsx"].exists() else {}
    analysis = workbook(files["engagement_analysis.xlsx"]) if files["engagement_analysis.xlsx"].exists() else {}

    ledger_table = best_table(clean, [["responsekey", "响应键"], ["participanttoken", "surveytoken", "调查代号"], ["submittedat", "提交时间"], ["sourcefile", "来源文件"]], 3)
    ledger_rows = []; h = []
    if ledger_table:
        sheet, ri, h = ledger_table; ledger_rows = clean[sheet][ri + 1:]
    idx = {
        "response": column(h, ["responsekey", "响应键"]), "token": column(h, ["surveytoken", "participanttoken", "调查代号"]),
        "source": column(h, ["sourcefile", "来源文件"]), "source_row": column(h, ["sourcerow", "来源行"]),
        "wave": column(h, ["wave", "波次"]), "submitted": column(h, ["submittedat", "提交时间"]), "org": column(h, ["surveyorg", "调查组织"]),
        "canonical": column(h, ["canonicalexport", "canonicalcopy", "dedupdecision", "adoptedstatus", "adoptedflag", "adopted", "去重保留"]),
        "copy_count": column(h, ["responsecopycount", "logicalcopycount", "copycount", "dedupgroupsize", "dedupcount", "副本数"]),
        "duplicate": column(h, ["duplicateexport", "重复导出"]), "hard": column(h, ["hardeligible", "硬资格"]),
        "straight": column(h, ["straightline", "直线作答"]), "main": column(h, ["mainadopt", "adoptedresponse", "adoptedstatus", "主口径采用"]),
        "sens": column(h, ["sensitivityadopt", "敏感性采用"]), "person": column(h, ["personkey", "personkeyallowed", "bridgepersonkey", "稳定人员键"]),
        "bridge_valid": column(h, ["bridgetemporallyvalid", "bridgevalidatsubmission", "bridgevalidonsubmit", "temporalvalid", "bridgevalid", "桥有效"]), "grade": column(h, ["bridgematchgrade", "matchgrade", "匹配等级"]),
        "allowed": column(h, ["bridgealloweduse", "alloweduse", "允许用途"]), "personnel_allowed": column(h, ["personneluseallowed", "personneluseeligible", "personneluse", "personnelenrichmentallowed", "人员用途允许"]),
        "panel_allowed": column(h, ["paneluseallowed", "paneluseeligible", "paneluse", "panellinkallowed", "面板用途允许"]), "frame": column(h, ["frameband", "bridgeframeband", "抽样框分组"]),
        "cal_org": column(h, ["orgcalibrationgroup", "组织校准组"]), "cal_adopt": column(h, ["calibrationadopt", "calibrationuse", "adoptedresponse", "校准采用"]),
        "weight": column(h, ["finalcalibrationweight", "calibrationweight", "finalweight", "最终权重"]), "link": column(h, ["corelinkstatus", "连接状态"]),
        "usable": column(h, ["personnelattributesusable", "coreactiveonsubmit", "coreactiveatsubmission", "人员属性可用"]),
    }
    qs = [column(h, [f"q{q:02d}score", f"scoreq{q:02d}", f"q{q}score", f"q{q:02d}标准分"]) for q in range(1, 13)]
    qo = [column(h, [f"q{q:02d}sourcevalue", f"rawq{q:02d}", f"q{q}sourcevalue", f"q{q:02d}raw", f"q{q:02d}原值"]) for q in range(1, 13)]
    expected_counts = Counter(r["response_key"] for r in expected_raw); by_key = {r["response_key"]: r for r in expected_raw}
    candidate_counts = Counter(str(value(r, idx["response"])).strip() for r in ledger_rows if value(r, idx["response"]) != "")
    raw_matches = sum(min(candidate_counts[k], v) for k, v in expected_counts.items())
    trace_fields = sum(idx[x] is not None for x in ("source", "source_row", "submitted", "org"))
    score.add("A1", 3, 2.4 * raw_matches / 795 + 0.6 * trace_fields / 4, f"raw={raw_matches}/795, trace={trace_fields}/4")

    mapped = original = 0
    for row in ledger_rows:
        exp = by_key.get(str(value(row, idx["response"])).strip())
        if not exp: continue
        mapped += sum(close(value(row, qs[i]), exp["scores"][i]) for i in range(12))
        original += sum(str(value(row, qo[i])).strip() == exp["original"].get(f"Q{i+1:02d}", "") for i in range(12))
    long_table = best_table(clean, [["responsekey", "响应键"], ["canonicalitem", "题号"], ["sourcevalue", "源值"], ["standardscore", "normalizedscore", "标准分"]], 3)
    if long_table:
        sheet, ri, lh = long_table; rk = column(lh, ["responsekey", "响应键"]); qi = column(lh, ["canonicalitem", "题号"]); sv = column(lh, ["sourcevalue", "源值"]); sc = column(lh, ["standardscore", "normalizedscore", "标准分"]); lm = lo = 0
        for row in clean[sheet][ri + 1:]:
            exp = by_key.get(str(value(row, rk)).strip()); q = item_id(value(row, qi))
            if not exp or not q: continue
            n = int(q[1:]); lm += close(value(row, sc), exp["scores"][n - 1]); lo += str(value(row, sv)).strip() == exp["original"].get(q, "")
        mapped = max(mapped, lm); original = max(original, lo)
    score.add("A2", 3, 2.2 * mapped / 9540 + 0.8 * original / 9540, f"scores={mapped}/9540, original={original}/9540")

    canonical = {}; canon_ok = dup_ok = 0
    for row in ledger_rows:
        key = str(value(row, idx["response"])).strip(); exp_n = expected_counts.get(key)
        if not exp_n: continue
        if boolean(value(row, idx["canonical"])) is True: canonical[key] = row
        got_dup = boolean(value(row, idx["duplicate"]))
        if got_dup is None and idx["copy_count"] is not None: got_dup = (number(value(row, idx["copy_count"])) or 0) > 1
        dup_ok += got_dup is (exp_n > 1)
    canon_ok = sum(sum(boolean(value(r, idx["canonical"])) is True for r in ledger_rows if str(value(r, idx["response"])).strip() == k) == 1 for k in expected_counts)
    score.add("A3", 3, 1.8 * canon_ok / 739 + 1.2 * dup_ok / 795, f"canonical={canon_ok}, duplicate={dup_ok}/795")
    states = 0
    for key, row in canonical.items():
        exp = by_key[key]
        states += sum((boolean(value(row, idx["hard"])) is exp["hard"], boolean(value(row, idx["straight"])) is exp["straight"], boolean(value(row, idx["main"])) is exp["main"], boolean(value(row, idx["sens"])) is exp["sensitivity"], boolean(value(row, idx["cal_adopt"])) is exp["calibration_adopted"]))
    score.add("A4", 3, 3 * states / (739 * 5), f"states={states}/{739*5}")
    bridge_fields = sum(idx[x] is not None for x in ("person", "bridge_valid", "grade", "allowed", "personnel_allowed", "panel_allowed", "frame", "cal_org", "weight"))
    score.add("A5", 3, 3 * bridge_fields / 9, f"fields={bridge_fields}/9")

    bridge_checks = personnel_checks = 0; identity_misuse = False
    weight_checks = 0
    for key, row in canonical.items():
        exp = by_key[key]
        bridge_checks += str(value(row, idx["person"])).strip() == exp["person_key"]
        bridge_checks += boolean(value(row, idx["bridge_valid"])) is exp["bridge_temporal"]
        bridge_checks += norm(value(row, idx["grade"])) == norm(exp["match_grade"])
        bridge_checks += norm(value(row, idx["allowed"])) == norm(exp["allowed_use"])
        bridge_checks += boolean(value(row, idx["panel_allowed"])) is exp["panel_allowed"]
        personnel_checks += norm(value(row, idx["link"])) == norm(exp["core_link"])
        personnel_checks += boolean(value(row, idx["usable"])) is exp["attr_usable"]
        weight_checks += close(value(row, idx["weight"]), exp["calibration_weight"], 1e-7)
        if boolean(value(row, idx["panel_allowed"])) is True and not exp["panel_allowed"]: identity_misuse = True
    score.add("B1", 10, 10 * bridge_checks / (739 * 5), f"bridge={bridge_checks}/{739*5}")
    score.add("B2", 5, 5 * personnel_checks / (739 * 2), f"personnel={personnel_checks}/{739*2}")
    panel_truth = panel_tables(expected_raw); pmap_truth = {norm(r[0]): r[1] for r in panel_truth["panel_summary"][1:]}
    panel_detail = best_table({**clean, **analysis}, [["personkey", "稳定人员键"], ["mean2023", "alphaanchorscore", "alpha均值"], ["mean2024", "betaanchorscore", "beta均值"], ["delta", "differencescore", "变化"]], 3)
    panel_members = 0
    if panel_detail:
        sheet, ri, ph = panel_detail; pk = column(ph, ["personkey", "稳定人员键"]); expected_people = {str(r[0]) for r in panel_truth["panel_detail"][1:]}; found = {str(value(r, pk)).strip() for r in ({**clean, **analysis})[sheet][ri + 1:]}; panel_members = len(expected_people & found)
    score.add("B3", 5, 3 * panel_members / max(1, int(pmap_truth["repeatpeople"])) + 2 * ("allowed_use" in notes or "用途" in notes), f"panel_members={panel_members}")

    company_table = best_table(analysis, [["population", "口径"], ["scope", "period", "范围"], ["nsubmissions", "样本量"], ["mean5", "五点均值"], ["scorepct", "得分百分比"]], 4)
    company_ok = 0
    if company_table:
        sheet, ri, ch = company_table; pc = column(ch, ["population", "口径"]); scp = column(ch, ["scope", "period", "范围"]); nc = column(ch, ["nsubmissions", "样本量"]); mc = column(ch, ["mean5", "五点均值"], ["pct"]); pct = column(ch, ["scorepct", "得分百分比"])
        found = {(population_id(value(r, pc)), scope_id(value(r, scp))): r for r in analysis[sheet][ri + 1:]}
        for scope, rows in (("2023", [r for r in expected_main if r["year"] == 2023]), ("2024", [r for r in expected_main if r["year"] == 2024]), ("combined", expected_main)):
            exp = metric(rows); row = found.get(("main", scope), []); company_ok += number(value(row, nc)) == exp["n"]; company_ok += close(value(row, mc), exp["mean"]); company_ok += close(value(row, pct), exp["pct"])
    score.add("C1", 3, 3 * company_ok / 9, f"company={company_ok}/9")
    wide_company = best_table(analysis, [["alphan", "alpha样本"], ["betan", "beta样本"], ["alphaunweightedpct", "alphascorepct"], ["betaunweightedpct", "betascorepct"], ["unweightedchange", "changepp"]], 4)
    if wide_company:
        sheet, ri, wh = wide_company; acn = column(wh, ["alphan", "alpha样本"]); bcn = column(wh, ["betan", "beta样本"]); ap = column(wh, ["alphaunweightedpct", "alphascorepct"]); bp = column(wh, ["betaunweightedpct", "betascorepct"]); mc = column(wh, ["method", "estimand", "metric", "方法"])
        candidates = analysis[sheet][ri + 1:]; row = next((r for r in candidates if any(x in norm(value(r, mc)) for x in ("unweightedrespondents", "q12meanpct", "q12overall"))), candidates[0] if candidates else [])
        direct = sum((number(value(row, acn)) == 312, number(value(row, bcn)) == 427, close(value(row, ap), metric([r for r in expected_main if r["year"] == 2023])["pct"]), close(value(row, bp), metric([r for r in expected_main if r["year"] == 2024])["pct"])))
        company_ok = max(company_ok, direct); old_earned = score.items[-1]["earned"]; new_earned = 3 * company_ok / 9; score.items[-1]["earned"] = round(new_earned, 4); score.items[-1]["detail"] = f"company={company_ok}/9"; score.total += new_earned - old_earned
    # Coverage credit for explicit item/tier result families; exact weighted item
    # values receive their high-value checks below.
    item_family = best_table(analysis, [["item", "题号"], ["population", "口径"], ["scope", "范围"], ["mean5", "均值"]], 3)
    tier_family = best_table(analysis, [["tier", "阶梯"], ["population", "口径"], ["scope", "范围"], ["mean5", "均值"]], 3)
    if not item_family: item_family = best_table(analysis, [["item", "题号"], ["alphan", "alpha样本"], ["betan", "beta样本"], ["alphaunweighted", "alpharawscore"], ["betaunweighted", "betarawscore"]], 4)
    if not tier_family: tier_family = best_table(analysis, [["tier", "阶梯"], ["alphan", "alpha样本"], ["betan", "beta样本"], ["alphaunweighted", "alpharawscore"], ["betaunweighted", "betarawscore"]], 4)
    score.add("C2", 4, 2 * bool(item_family) + 2 * bool(tier_family), f"item={bool(item_family)}, tier={bool(tier_family)}")
    reconciled = raw_matches == 795 and len(canonical) == 739 and mapped == 9540
    score.add("C3", 3, 3 if reconciled else 1 if raw_matches == 795 else 0, f"reconciled={reconciled}")

    score.add("D1", 10, 10 * weight_checks / 739, f"weights={weight_checks}/739")
    targets = calibration_targets(materials); margin_truth = {}
    diagnostics_truth = {}
    for wave in ("alpha", "beta"):
        rows = [r for r in expected_raw if r["wave"] == wave and r["calibration_adopted"]]; weights, diag = rake_rows(rows, targets); diagnostics_truth[wave] = diag
        for dimension, field in (("org_calibration_group", "calibration_org"), ("frame_band", "frame_band")):
            total = sum(weights.values())
            for category in targets[dimension]: margin_truth[(wave, dimension, category)] = sum(weights[r["response_key"]] for r in rows if r[field] == category) / total
    mt = best_table(analysis, [["wave", "波次"], ["dimension", "维度"], ["category", "类别"], ["targetshare", "目标占比"], ["weightedshare", "加权占比"]], 4)
    margin_ok = 0
    if mt:
        sheet, ri, mh = mt; wc = column(mh, ["wave", "波次"]); dc = column(mh, ["dimension", "维度"]); cc = column(mh, ["category", "类别"]); tc = column(mh, ["targetshare", "fixedtargetshare", "目标占比"]); ac = column(mh, ["weightedshare", "actualshare", "achievedshare", "finalweightedshare", "加权占比"], ["unweighted", "rawshare", "未加权"]); stage = column(mh, ["stage", "阶段"]); rows = analysis[sheet][ri + 1:]; final_rows = [r for r in rows if stage is None or any(x in norm(value(r, stage)) for x in ("final", "posttrim", "最终"))]; found = {(norm(value(r, wc)), norm(value(r, dc)), str(value(r, cc))): r for r in final_rows}
        for (wave, dim, cat), expected in margin_truth.items():
            row = found.get((norm(wave), norm(dim), cat), []); margin_ok += close(value(row, tc), targets[dim][cat]); margin_ok += close(value(row, ac), expected)
    score.add("D2", 8, 8 * margin_ok / max(1, 2 * len(margin_truth)), f"margins={margin_ok}/{2*len(margin_truth)}")
    dt = best_table(analysis, [["wave", "波次"], ["sumw", "weightsum", "finalweightsum", "权重和"], ["minw", "weightmin", "minfinalweight", "最小权重"], ["maxw", "weightmax", "maxfinalweight", "最大权重"], ["kishess", "kisheffectiven", "有效样本量"], ["maxmarginerror", "finalmaxerror", "finalmaxmarginerror", "边际误差"]], 4)
    diag_ok = 0
    if dt:
        sheet, ri, dh = dt; wc = column(dh, ["wave", "波次"]); found = {norm(value(r, wc)): r for r in analysis[sheet][ri + 1:]}
        for wave, exp in diagnostics_truth.items():
            row = found.get(norm(wave), [])
            for names, key in ((["sumw", "weightsum", "finalweightsum", "权重和"], "sum_w"), (["minw", "weightmin", "minfinalweight", "最小权重"], "min_w"), (["maxw", "weightmax", "maxfinalweight", "最大权重"], "max_w"), (["kishess", "kisheffectiven", "有效样本量"], "ess"), (["maxmarginerror", "finalmaxerror", "finalmaxmarginerror", "边际误差"], "margin_error")): diag_ok += close(value(row, column(dh, names)), exp[key], 1e-7)
    score.add("D3", 5, 5 * diag_ok / 10, f"diagnostics={diag_ok}/10")
    ct = best_table(analysis, [["estimand", "估计量"], ["wave", "波次"], ["n", "样本量"], ["sumw", "权重和"], ["mean5", "五点均值"], ["scorepct", "得分"]], 5)
    cal_company_ok = 0
    if ct:
        sheet, ri, hh = ct; wc = column(hh, ["wave", "波次"]); ec = column(hh, ["estimand", "估计量"]); nc = column(hh, ["n", "样本量"]); sw = column(hh, ["sumw", "权重和"]); mc = column(hh, ["mean5", "五点均值"]); pc = column(hh, ["scorepct", "得分"])
        for wave in ("alpha", "beta"):
            row = next((r for r in analysis[sheet][ri + 1:] if norm(value(r, wc)) == wave and "fixed" in norm(value(r, ec))), []); rows = [r for r in expected_raw if r["wave"] == wave and r["calibration_adopted"]]; expm = sum(float(r["calibration_weight"]) * sum(r["scores"]) for r in rows) / (12 * sum(float(r["calibration_weight"]) for r in rows))
            cal_company_ok += number(value(row, nc)) == len(rows); cal_company_ok += close(value(row, sw), len(rows)); cal_company_ok += close(value(row, mc), expm); cal_company_ok += close(value(row, pc), expm / 5)
    wide_cal = best_table(analysis, [["alphan", "alpha样本"], ["betan", "beta样本"], ["alphafinalpct", "alphaweightedscorepct", "alphascorepct"], ["betafinalpct", "betaweightedscorepct", "betascorepct"], ["finalchange", "weightedchange", "changepp"]], 4)
    if wide_cal:
        sheet, ri, hh = wide_cal; keyc = column(hh, ["metric", "method", "估计量"]); candidates = analysis[sheet][ri + 1:]; row = next((r for r in candidates if any(x in norm(value(r, keyc)) for x in ("q12meanpct", "fixedstructurefinal", "q12overall"))), candidates[0] if candidates else [])
        an = column(hh, ["alphan", "alpha样本"]); bn = column(hh, ["betan", "beta样本"]); ap = column(hh, ["alphafinalpct", "alphaweightedscorepct", "alphascorepct"]); bp = column(hh, ["betafinalpct", "betaweightedscorepct", "betascorepct"])
        expa, expb = [], []
        for wave, sink in (("alpha", expa), ("beta", expb)):
            rows = [r for r in expected_raw if r["wave"] == wave and r["calibration_adopted"]]; sink.append(sum(float(r["calibration_weight"]) * sum(r["scores"]) for r in rows) / (60 * sum(float(r["calibration_weight"]) for r in rows)))
        direct = sum((number(value(row, an)) == 312, number(value(row, bn)) == 427, close(value(row, ap), expa[0]), close(value(row, bp), expb[0])))
        cal_company_ok = max(cal_company_ok, 2 * direct)
    score.add("D4", 4, 4 * cal_company_ok / 8, f"calibrated_company={cal_company_ok}/8")
    cit = best_table(analysis, [["estimand", "估计量"], ["wave", "波次"], ["item", "题号"], ["mean5", "均值"], ["scorepct", "得分"]], 4)
    cal_item_ok = 0
    if cit:
        sheet, ri, ih = cit; wc = column(ih, ["wave", "波次"]); qi = column(ih, ["item", "题号"]); mc = column(ih, ["mean5", "均值"], ["pct"]); found = {(norm(value(r, wc)), item_id(value(r, qi))): r for r in analysis[sheet][ri + 1:]}
        for wave in ("alpha", "beta"):
            rows = [r for r in expected_raw if r["wave"] == wave and r["calibration_adopted"]]; total = sum(float(r["calibration_weight"]) for r in rows)
            for q in range(1, 13):
                expm = sum(float(r["calibration_weight"]) * r["scores"][q - 1] for r in rows) / total; cal_item_ok += close(value(found.get((wave, f"Q{q:02d}"), []), mc), expm)
    wide_items = best_table(analysis, [["item", "题号"], ["alphan", "alpha样本"], ["betan", "beta样本"], ["alphafinalpct", "alphaweightedscorepct"], ["betafinalpct", "betaweightedscorepct"]], 4)
    if wide_items:
        sheet, ri, hh = wide_items; qi = column(hh, ["item", "题号"]); ap = column(hh, ["alphafinalpct", "alphaweightedscorepct"]); bp = column(hh, ["betafinalpct", "betaweightedscorepct"]); found = {item_id(value(r, qi)): r for r in analysis[sheet][ri + 1:] if item_id(value(r, qi))}; direct = 0
        for wave, col_ in (("alpha", ap), ("beta", bp)):
            rows = [r for r in expected_raw if r["wave"] == wave and r["calibration_adopted"]]; total = sum(float(r["calibration_weight"]) for r in rows)
            for q in range(1, 13): direct += close(value(found.get(f"Q{q:02d}", []), col_), sum(float(r["calibration_weight"]) * r["scores"][q - 1] for r in rows) / (5 * total))
        cal_item_ok = max(cal_item_ok, direct)
    score.add("D5", 3, 3 * cal_item_ok / 24, f"calibrated_items={cal_item_ok}/24")

    pm = {}
    panel_summary = best_table(analysis, [["metric", "指标"], ["value", "数值"]], 2)
    if panel_summary:
        sheet, ri, ph = panel_summary; kc = column(ph, ["metric", "指标"]); vc = column(ph, ["value", "数值"]); pm = {norm(value(r, kc)): value(r, vc) for r in analysis[sheet][ri + 1:]}
    panel_ok = sum(close(pm.get(k), pmap_truth[k]) for k in ("repeatpeople", "pairedmean2023", "pairedmean2024", "paireddelta5", "deltasd", "deltase", "normalapproxcilow", "normalapproxcihigh"))
    wide_panel = best_table(analysis, [["paneln", "verifiedpaneln", "面板人数"], ["alphapanelpct", "panelalphascorepct", "alpha面板"], ["betapanelpct", "panelbetascorepct", "beta面板"], ["panelchange", "samepersonchange", "同人变化"]], 3)
    if wide_panel:
        sheet, ri, hh = wide_panel; keyc = column(hh, ["metric", "指标"]); candidates = analysis[sheet][ri + 1:]; row = next((r for r in candidates if any(x in norm(value(r, keyc)) for x in ("q12meanpct", "q12overall"))), candidates[0] if candidates else []); nc = column(hh, ["paneln", "verifiedpaneln", "面板人数"]); ap = column(hh, ["alphapanelpct", "panelalphascorepct", "alpha面板"]); bp = column(hh, ["betapanelpct", "panelbetascorepct", "beta面板"]); dc = column(hh, ["panelchange", "samepersonchange", "同人变化"])
        panel_ok = max(panel_ok, sum((number(value(row, nc)) == pmap_truth["repeatpeople"], close(value(row, ap), pmap_truth["pairedmean2023"] / 5), close(value(row, bp), pmap_truth["pairedmean2024"] / 5), close(value(row, dc), pmap_truth["paireddelta5"] / 5))))
    score.add("E1", 6, 6 * panel_ok / 8, f"panel={panel_ok}/8")
    comp_truth = {norm(r[0]): r[1] for r in panel_truth["composition"][1:]}
    comp_table = best_table(analysis, [["component", "分量"], ["value5", "五点值", "结果"]], 2); comp_ok = 0
    if comp_table:
        sheet, ri, hh = comp_table; kc = column(hh, ["component", "分量"]); vc = column(hh, ["value5", "五点值", "结果"]); found = {norm(value(r, kc)): value(r, vc) for r in analysis[sheet][ri + 1:]}; comp_ok = sum(close(found.get(k), comp_truth[k]) for k in ("crosssectiondelta", "withincomponent", "compositioncomponent", "reconciliationerror"))
    wide_decomp = best_table(analysis, [["compositiongroup", "构成组"], ["within", "组内分量"], ["sharecomposition", "构成分量"], ["totalcomponent", "总分量"]], 3)
    if wide_decomp:
        sheet, ri, hh = wide_decomp; gc = column(hh, ["compositiongroup", "构成组"]); row = next((r for r in analysis[sheet][ri + 1:] if norm(value(r, gc)) in {"total", "合计"}), []); wc = column(hh, ["within", "组内分量"]); sc = column(hh, ["sharecomposition", "构成分量"]); tc = column(hh, ["totalcomponent", "总分量"]); direct = sum((close(value(row, wc), comp_truth["withincomponent"] / 5), close(value(row, sc), comp_truth["compositioncomponent"] / 5), close(value(row, tc), comp_truth["crosssectiondelta"] / 5), close(number(value(row, tc)) - number(value(row, wc)) - number(value(row, sc)) if all(number(value(row, x)) is not None for x in (tc, wc, sc)) else "", 0)))
        comp_ok = max(comp_ok, direct)
    score.add("E2", 4, 4 * comp_ok / 4, f"composition={comp_ok}/4")
    sens_doc = ("敏感" in notes or "sensitivity" in notes.lower()) and ("559" in notes or any("straightline" in norm(x) for rows in analysis.values() for row in rows for x in row if isinstance(x, str)))
    score.add("E3", 4, 2 * (len(expected_sens) == 559 and idx["sens"] is not None) + 2 * sens_doc, f"sensitivity={sens_doc}")
    priority = best_table(analysis, [["priority", "优先级"], ["item", "题号", "surveyorg", "调查组织"], ["n2023", "nalpha", "样本量"], ["change", "变化"]], 3)
    priority_doc = "80%" in notes and "20" in notes and ("1个百分点" in notes or "1 个百分点" in notes)
    score.add("E4", 4, 2 * bool(priority) + 2 * priority_doc, f"table={bool(priority)}, rules={priority_doc}")
    interpretation = ("固定" in notes and "未加权" in notes and any(x in notes for x in ("反转", "下降"))) + ("不能" in notes and any(x in notes for x in ("代表性", "非响应", "因果")))
    score.add("E5", 2, interpretation, f"interpretation={interpretation}/2")

    present = all(p.exists() for p in files.values()); distinct = present and hashlib.sha256(files["cleaned_samples.xlsx"].read_bytes()).digest() != hashlib.sha256(files["engagement_analysis.xlsx"].read_bytes()).digest()
    score.add("F1", 1, present and distinct, f"present={present}, distinct={distinct}")
    score.add("F2", 2, min(2, sum(x in notes for x in ("字典", "身份桥", "权重", "Kish", "面板", "敏感性", "抑制", "限制")) / 4), "method coverage")
    privacy = []
    text = notes + "\n" + "\n".join(str(x) for book in (clean, analysis) for rows in book.values() for row in rows for x in row if isinstance(x, str))
    for name, pattern in (("phone", r"(?<!\d)1[3-9]\d{9}(?!\d)"), ("id", r"(?<!\d)\d{17}[\dXx](?!\d)"), ("email", r"[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}")):
        if re.search(pattern, "\n".join(line for line in text.splitlines() if not re.fullmatch(r"[0-9a-fA-F]{32,128}", line.strip()))): privacy.append(name)
    score.add("F3", 2, 2 if not privacy else 0, f"privacy={privacy}")

    if present and not distinct: score.cap(20, "two XLSX files identical")
    if canon_ok < 739: score.cap(30, "wrong logical response population")
    if idx["weight"] is None or weight_checks < 700: score.cap(25, "missing reproducible final calibration weights")
    if identity_misuse: score.cap(30, "purpose-limited identity bridge misused for panel")
    if privacy: score.cap(0, "privacy disclosure")
    if not present: score.cap(50, "missing deliverable")
    final = score.final()
    return {"reward": round(final / 100, 4), "score": round(final, 4), "uncapped_score": round(score.total, 4), "caps": score.caps, "items": score.items}


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "/app/environment").resolve()
    try: result = evaluate(root)
    except Exception as exc: result = {"reward": 0.0, "score": 0.0, "uncapped_score": 0.0, "caps": [{"maximum": 0, "reason": f"verifier error: {type(exc).__name__}: {exc}"}], "items": []}
    for directory in (root / "verifier", Path("/logs/verifier"), Path("/verifier")):
        try:
            directory.mkdir(parents=True, exist_ok=True); (directory / "reward.txt").write_text(f"{result['reward']}\n"); (directory / "reward.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
        except Exception: pass
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
