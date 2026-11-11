#!/usr/bin/env python3
# 本文件中的中文字符串是列名与枚举的匹配别名（材料与交付物均可为中文），
# 属评分所需，请勿翻译或删除。
"""Semantic v6 verifier. Truth is recomputed from materials, never read from golden."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import stdev
from xml.etree import ElementTree as ET
from zipfile import ZipFile
import hashlib
import json
import os
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "solution"))
from q12_pipeline import load_raw, adopted, metric, tier_questions, TIER_ORDER  # noqa: E402

M = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
P = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"a": M}; RN = {"p": P}


def norm(value):
    return re.sub(r"[\s_\-—–:：/（）()\[\]【】.]+", "", str(value or "").strip().lower())


def col_index(ref):
    match = re.match(r"[A-Z]+", ref or "")
    value = 0
    for ch in match.group() if match else "":
        value = value * 26 + ord(ch) - 64
    return value - 1


def workbook(path):
    out = {}
    with ZipFile(path) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(t.text or "" for t in node.findall(".//a:t", NS)) for node in root.findall("a:si", NS)]
        wb = ET.fromstring(archive.read("xl/workbook.xml"))
        rel = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {x.attrib["Id"]: x.attrib["Target"] for x in rel.findall("p:Relationship", RN)}
        for sheet in wb.find("a:sheets", NS):
            target = targets[sheet.attrib[f"{{{R}}}id"]].lstrip("/")
            target = target if target.startswith("xl/") else "xl/" + target
            xml = ET.fromstring(archive.read(target)); rows = []
            for node in xml.findall(".//a:sheetData/a:row", NS):
                row = []
                for cell in node.findall("a:c", NS):
                    i = col_index(cell.attrib.get("r", "")); row.extend([""] * (i - len(row) + 1)); typ = cell.attrib.get("t")
                    if typ == "inlineStr":
                        value = "".join(t.text or "" for t in cell.findall(".//a:t", NS))
                    else:
                        raw = cell.find("a:v", NS); value = "" if raw is None or raw.text is None else raw.text
                        if typ == "s" and value != "":
                            value = shared[int(value)]
                        elif typ in (None, "n") and value != "":
                            try:
                                number = float(value); value = int(number) if number.is_integer() else number
                            except ValueError:
                                pass
                    row[i] = value
                rows.append(row)
            out[sheet.attrib["name"]] = rows
    return out


def number(value):
    if value in (None, "") or isinstance(value, bool): return None
    text = str(value).strip().replace(",", "")
    if norm(text) in {"na", "n/a", "不适用", "抑制", "已抑制", "-"}: return None
    try: return float(text[:-1]) / 100 if text.endswith("%") else float(text)
    except ValueError: return None


def boolean(value):
    text = norm(value)
    if text in {"true", "yes", "y", "1", "是", "采用", "保留", "有效", "canonical", "主记录"}: return True
    if text in {"false", "no", "n", "0", "否", "不采用", "排除", "无效", "非主记录"}: return False
    return None


def close(value, expected, tol=1e-6):
    actual = number(value)
    if actual is None: return False
    return abs(actual - expected) <= max(tol, 2e-5 * abs(expected))


def aliases(value, terms):
    nv = norm(value)
    return any((nv == norm(term)) if len(norm(term)) <= 2 else (norm(term) in nv) for term in terms)


def matched_alias(value, terms):
    """最长的命中别名；没命中返回 None。"""
    nv = norm(value)
    hits = [nt for nt in (norm(term) for term in terms) if (nv == nt if len(nt) <= 2 else nt in nv)]
    return max(hits, key=len) if hits else None


def column(headers, terms, exclude=()):
    """取最具体的命中列，而不是最左的那一列。

    标注口径用的 provenance 列排在被描述的列左边——`item_family` 在 `deleted_item`
    左边——而且会被短别名子串命中：别名 `item` 命中的是 `item_family`。取第一个命中
    就会静默读错列，整块判据随之归零。先按是否完全相等排，再按命中别名的长度排。
    """
    best = None; best_rank = ()
    for i, value in enumerate(headers):
        if aliases(value, exclude): continue
        hit = matched_alias(value, terms)
        if hit is None: continue
        rank = (hit == norm(value), len(hit))
        if best is None or rank > best_rank: best, best_rank = i, rank
    return best


def value(row, index):
    return row[index] if index is not None and index < len(row) else ""


def best_table(book, required, min_hits=None):
    best = None; best_hits = -1
    for sheet, rows in book.items():
        for ri, row in enumerate(rows[:40]):
            hits = sum(any(aliases(cell, group) for cell in row) for group in required)
            if hits > best_hits:
                best_hits = hits; best = (sheet, ri, row)
            if hits == len(required): return sheet, ri, row
    minimum = min_hits if min_hits is not None else max(2, len(required) - 1)
    return best if best_hits >= minimum else None


def scope_id(value):
    text = norm(value)
    if "2023" in text or text in {"alpha", "a"}: return "2023"
    if "2024" in text or text in {"beta", "b"}: return "2024"
    if any(x in text for x in ("combined", "合计", "总体", "all", "total", "两期")): return "combined"
    return None


def item_id(value):
    match = re.search(r"q0?([1-9]|1[0-2])(?!\d)", str(value), re.I)
    return f"Q{int(match.group(1)):02d}" if match else None


def population_id(value):
    text = norm(value)
    if any(x in text for x in ("敏感", "sensitivity", "straightlineexcluded", "excludestraight", "softremoved")): return "sensitivity"
    return "main"


class Score:
    def __init__(self): self.total = 0.0; self.items = []; self.caps = []
    def add(self, item, maximum, earned, detail):
        earned = max(0.0, min(float(maximum), float(earned)))
        self.total += earned; self.items.append({"item": item, "maximum": maximum, "earned": round(earned, 4), "detail": detail})
    def cap(self, maximum, reason): self.caps.append({"maximum": maximum, "reason": reason})
    def final(self): return min([self.total] + [x["maximum"] for x in self.caps])


def field(row, headers, names, exclude=()):
    return value(row, column(headers, names, exclude))


def metric_map(book, required):
    table = best_table(book, required)
    if not table: return {}, [], None
    sheet, ri, headers = table
    rows = book[sheet][ri + 1:]
    key_col = column(headers, ["metric", "指标", "component", "分量", "check", "核对项"])
    value_col = column(headers, ["value", "数值", "结果", "actual", "实际值", "value5"], ["pct", "百分", "expected", "预期"])
    return {norm(value(r, key_col)): value(r, value_col) for r in rows if value(r, key_col) != ""}, headers, sheet


def evaluate(root: Path):
    materials = root / "materials"; output = root / "output"; score = Score()
    expected_raw, item_meta = load_raw(materials); expected_main = adopted(expected_raw); expected_sens = adopted(expected_raw, True)
    files = {name: output / name for name in ("cleaned_samples.xlsx", "engagement_analysis.xlsx")}
    notes = "\n".join(str(x) for rows in workbook(files["engagement_analysis.xlsx"]).values() for row in rows for x in row if isinstance(x, str)) if files["engagement_analysis.xlsx"].exists() else ""
    try: clean = workbook(files["cleaned_samples.xlsx"]) if files["cleaned_samples.xlsx"].exists() else {}
    except Exception as exc: clean = {}; score.items.append({"item": "clean_parse", "maximum": 0, "earned": 0, "detail": str(exc)})
    try: analysis = workbook(files["engagement_analysis.xlsx"]) if files["engagement_analysis.xlsx"].exists() else {}
    except Exception as exc: analysis = {}; score.items.append({"item": "analysis_parse", "maximum": 0, "earned": 0, "detail": str(exc)})

    ledger_table = best_table(clean, [["responsekey", "响应键", "答卷id", "responseid"], ["participanttoken", "人员键", "匿名代号", "员工代号"], ["submittedat", "提交时间", "投票时间"], ["sourcefile", "来源文件", "文件名"]], 3) if clean else None
    ledger_rows = []; headers = []
    if ledger_table:
        sheet, ri, headers = ledger_table; ledger_rows = clean[sheet][ri + 1:]
    idx = {
        "response": column(headers, ["responsekey", "响应键", "答卷id", "responseid"]),
        "token": column(headers, ["participanttoken", "人员键", "匿名代号", "员工代号"]),
        "source": column(headers, ["sourcefile", "来源文件", "文件名"]),
        "source_row": column(headers, ["sourcerow", "来源行", "原始行"]),
        "wave": column(headers, ["wave", "波次", "调查期"]),
        "submitted": column(headers, ["submittedat", "提交时间", "投票时间"]),
        "org": column(headers, ["surveyorg", "问卷部门", "调查组织", "调查部门"]),
        "duplicate": column(headers, ["duplicateexport", "重复导出", "批次重复"]),
        "copy_count": column(headers, ["responsecopycount", "logicalcopycount", "exportcopycount", "副本数", "重复次数"]),
        "canonical": column(headers, ["canonicalexport", "canonicalcopy", "adoptedflag", "selectedflag", "主导出记录", "规范记录", "去重保留"]),
        "hard": column(headers, ["hardeligible", "硬资格", "硬有效"]),
        "straight": column(headers, ["straightline", "straightlineall12", "直线作答", "全同"]),
        "main": column(headers, ["mainadopted", "mainadopt", "主口径采用", "最终采用"]),
        "sens": column(headers, ["sensitivityadopted", "sensitivityadopt", "敏感性采用"]),
        "link": column(headers, ["corelinkstatus", "人员连接状态", "匹配状态", "连接状态"]),
        "core_matched": column(headers, ["corematched", "核心人员匹配"]),
        "employment_valid": column(headers, ["employmenttimevalid", "任职时点有效", "就业时点有效"]),
        "usable": column(headers, ["personnelattributesusable", "personnelsupported", "人员属性可用", "属性可用"]),
        "snapshot_org": column(headers, ["orgsnapshot", "快照组织", "花名册部门"]),
        "conflict": column(headers, ["orgconflict", "组织冲突", "部门冲突"]),
        "level": column(headers, ["technicallevelatsubmission", "technicallevelatsubmit", "提交时点级别", "历史级别"]),
        "age": column(headers, ["agebandatsubmission", "agecompletedyearsatsubmit", "提交时点年龄", "年龄段"]),
        "tenure": column(headers, ["tenurebandatsubmission", "tenurecompletedyearsatsubmit", "提交时点司龄", "司龄段"]),
    }
    qscore = [column(headers, [f"q{q:02d}score", f"q{q}score", f"q{q:02d}得分", f"q{q}得分"]) for q in range(1, 13)]
    qsource = [column(headers, [f"q{q:02d}sourcevalue", f"q{q}sourcevalue", f"q{q:02d}原始", f"q{q}原始", f"q{q:02d}原值"]) for q in range(1, 13)]

    expected_counts = Counter(r["response_key"] for r in expected_raw)
    candidate_counts = Counter(str(value(r, idx["response"])).strip() for r in ledger_rows if value(r, idx["response"]) != "")
    count_match = sum(min(candidate_counts[k], n) for k, n in expected_counts.items())
    source_evidence = sum(idx[x] is not None for x in ("source", "source_row", "submitted", "org")) / 4
    score.add("A1", 2, 1.5 * count_match / len(expected_raw) + 0.5 * source_evidence, f"raw_key_rows={count_match}/{len(expected_raw)}, source_fields={source_evidence:.2f}")

    by_key = {r["response_key"]: r for r in expected_raw}
    mapped = original = wave_ok = 0; considered = 0
    for row in ledger_rows:
        key = str(value(row, idx["response"])).strip(); exp = by_key.get(key)
        if not exp: continue
        considered += 1
        mapped += sum(close(value(row, qscore[q]), exp["scores"][q]) for q in range(12))
        original += sum(str(value(row, qsource[q])).strip() == exp["original"].get(f"Q{q+1:02d}", "") for q in range(12))
        wave_ok += norm(value(row, idx["wave"])) == norm(exp["wave"]) if idx["wave"] is not None else False
    long_table = best_table(clean, [["responsekey", "响应键"], ["canonicalitem", "标准题号", "题号"], ["sourcevalue", "源值", "原始编码"], ["standardscore", "normalizedscore", "标准分", "得分"]], 3) if clean else None
    long_mapped = long_original = 0; candidate_long_scores = defaultdict(dict)
    if long_table:
        sheet, ri, h = long_table
        rk = column(h, ["responsekey", "响应键"]); qi = column(h, ["canonicalitem", "标准题号", "题号"]); sv = column(h, ["sourcevalue", "源值", "原始编码"]); ss = column(h, ["standardscore", "normalizedscore", "标准分", "得分"])
        for row in clean[sheet][ri + 1:]:
            key = str(value(row, rk)).strip(); q = item_id(value(row, qi)); exp = by_key.get(key)
            if not exp or not q: continue
            qn = int(q[1:]); long_mapped += close(value(row, ss), exp["scores"][qn - 1]); long_original += str(value(row, sv)).strip() == exp["original"].get(q, "")
            if number(value(row, ss)) is not None: candidate_long_scores[key][q] = number(value(row, ss))
    mapped = max(mapped, long_mapped); original = max(original, long_original)
    denom = max(1, len(expected_raw) * 12)
    score.add("A2", 3, 2 * mapped / denom + 0.5 * original / denom + 0.5 * wave_ok / max(1, considered), f"mapped={mapped}/{denom}, original={original}/{denom}, wave={wave_ok}/{considered}")

    canonical_by_key = Counter(); duplicate_ok = 0
    for row in ledger_rows:
        key = str(value(row, idx["response"])).strip(); exp_n = expected_counts.get(key)
        if not exp_n: continue
        if boolean(value(row, idx["canonical"])) is True: canonical_by_key[key] += 1
        expected_dup = exp_n > 1; got_dup = boolean(value(row, idx["duplicate"]))
        if got_dup is None and idx["copy_count"] is not None: got_dup = (number(value(row, idx["copy_count"])) or 0) > 1
        duplicate_ok += got_dup is expected_dup
    canonical_ok = sum(canonical_by_key[k] == 1 for k in expected_counts)
    logical_count = sum(boolean(value(r, idx["canonical"])) is True for r in ledger_rows)
    dedup_doc = any(x in norm(notes) for x in ("重复导出", "overlappingexport", "批次重叠")) and any(x in norm(notes) for x in ("responsekey", "响应键"))
    score.add("A3", 3, 1.2 * canonical_ok / 739 + 0.8 * duplicate_ok / max(1, count_match) + 0.5 * (logical_count == 739) + 0.5 * dedup_doc, f"canonical={canonical_ok}/739, duplicate_flags={duplicate_ok}/{count_match}, logical={logical_count}")

    canonical_candidates = {}
    for row in ledger_rows:
        key = str(value(row, idx["response"])).strip()
        if boolean(value(row, idx["canonical"])) is True: canonical_candidates[key] = row
    states = {"hard": 0, "straight": 0, "main": 0, "sens": 0}
    for key, row in canonical_candidates.items():
        exp = by_key.get(key)
        if not exp: continue
        states["hard"] += boolean(value(row, idx["hard"])) is exp["hard"]
        states["straight"] += boolean(value(row, idx["straight"])) is exp["straight"]
        states["main"] += boolean(value(row, idx["main"])) is exp["main"]
        states["sens"] += boolean(value(row, idx["sens"])) is exp["sensitivity"]
    score.add("A4", 2, 0.5 * sum(states.values()) / 739, f"state_matches={states}")

    link_ok = usable_ok = level_ok = conflict_ok = age_ok = tenure_ok = 0
    def band_match(actual, expected):
        a = norm(actual); e = norm(expected)
        if not expected: return a in {"", "na", "n/a", "不可用", "未匹配", "时点冲突"} or any(x in a for x in ("不可用", "未匹配", "冲突"))
        return a == e or a.replace("岁", "") == e.replace("岁", "") or a.replace("年", "") == e.replace("年", "")
    for key, row in canonical_candidates.items():
        exp = by_key.get(key)
        if not exp: continue
        link_text = norm(value(row, idx["link"])); got_link = "unmatched" if any(x in link_text for x in ("unmatched", "未匹配")) else "time_impossible" if any(x in link_text for x in ("timeimpossible", "temporal", "时点", "时间不可能", "日期异常")) else "time_usable"
        if idx["link"] is None and idx["core_matched"] is not None:
            core_match = boolean(value(row, idx["core_matched"])); employment_valid = boolean(value(row, idx["employment_valid"]))
            got_link = "unmatched" if core_match is False else "time_impossible" if employment_valid is False else "time_usable"
        link_ok += got_link == exp["core_link"]
        usable_ok += boolean(value(row, idx["usable"])) is exp["attr_usable"]
        level_ok += str(value(row, idx["level"])).strip() == exp["technical_level"]
        got_conflict = boolean(value(row, idx["conflict"]))
        if got_conflict is None and idx["snapshot_org"] is not None and idx["org"] is not None:
            snapshot_org = str(value(row, idx["snapshot_org"])).strip(); survey_org = str(value(row, idx["org"])).strip()
            got_conflict = bool(snapshot_org and survey_org and snapshot_org != survey_org)
        conflict_ok += got_conflict is exp["department_conflict"]
        age_value = value(row, idx["age"]); tenure_value = value(row, idx["tenure"])
        age_ok += (number(age_value) == exp.get("age_years")) if number(age_value) is not None else band_match(age_value, exp["age"])
        tenure_ok += (number(tenure_value) == exp.get("tenure_years")) if number(tenure_value) is not None else band_match(tenure_value, exp["tenure"])
    ncanon = max(1, len(canonical_candidates))
    notes_n = norm(notes)
    score.add("B1", 3, 2.5 * link_ok / ncanon + 0.5 * ("唯一" in notes or "unique" in notes.lower()), f"link={link_ok}/{ncanon}")
    time_doc = all(x in notes_n for x in ("入职", "提交")) and any(x in notes_n for x in ("离职", "结束"))
    level_doc = any(x in notes_n for x in ("生效日", "effectivedate")) and any(x in notes_n for x in ("不晚于", "notlater"))
    score.add("B2", 3, 1.2 * usable_ok / ncanon + 1.2 * level_ok / ncanon + 0.3 * time_doc + 0.3 * level_doc, f"usable={usable_ok}, level={level_ok}, time_doc={time_doc}, level_doc={level_doc}")
    snapshot_doc = "20250831" in notes_n and "快照" in notes and any(x in notes for x in ("不是历史", "不能还原", "不解释为", "当前快照"))
    score.add("B3", 2, 0.8 * conflict_ok / ncanon + 0.6 * (idx["snapshot_org"] is not None) + 0.6 * snapshot_doc, f"conflicts={conflict_ok}, snapshot_doc={snapshot_doc}")
    derived_doc = "提交日" in notes and "年龄" in notes and "司龄" in notes
    score.add("B4", 2, 0.75 * age_ok / ncanon + 0.75 * tenure_ok / ncanon + 0.5 * derived_doc, f"age={age_ok}, tenure={tenure_ok}, doc={derived_doc}")

    company_table = best_table(analysis, [["population", "分析口径", "口径"], ["scope", "period", "范围", "年度", "期间"], ["nsubmissions", "样本量", "采用提交数"], ["mean5", "rawmean1to5", "五点均值", "五分制得分"], ["scorepct", "得分百分比"]], 4) if analysis else None
    company_found = {}; company_headers = []
    if company_table:
        sheet, ri, company_headers = company_table
        pc = column(company_headers, ["population", "分析口径", "口径"]); scp = column(company_headers, ["scope", "period", "范围", "年度", "期间"])
        for row in analysis[sheet][ri + 1:]: company_found[(population_id(value(row, pc)), scope_id(value(row, scp)))] = row
    cn = column(company_headers, ["nsubmissions", "样本量", "采用提交数"]); cm = column(company_headers, ["mean5", "rawmean1to5", "五点均值", "五分制得分"], ["pct", "百分"]); cp = column(company_headers, ["scorepct", "得分百分比"])
    company_checks = 0
    for scope, rows in (("2023", [r for r in expected_main if r["year"] == 2023]), ("2024", [r for r in expected_main if r["year"] == 2024]), ("combined", expected_main)):
        exp = metric(rows); row = company_found.get(("main", scope), [])
        company_checks += number(value(row, cn)) == exp["n"]; company_checks += close(value(row, cm), exp["mean"]); company_checks += close(value(row, cp), exp["pct"])
    # A comparison-row layout is equivalent to period rows for the two periods;
    # combined still needs to be stated somewhere to earn all nine checks.
    comparison_table = best_table(analysis, [["comparison", "比较"], ["alphan", "2023样本"], ["betan", "2024样本"], ["alphascorepct", "2023得分"], ["betascorepct", "2024得分"]], 4)
    if comparison_table:
        sheet, ri, h = comparison_table; cc = column(h, ["comparison", "比较"]); an = column(h, ["alphan", "2023样本"]); bn = column(h, ["betan", "2024样本"]); ap = column(h, ["alphascorepct", "2023得分"]); bp = column(h, ["betascorepct", "2024得分"])
        row = next((r for r in analysis[sheet][ri + 1:] if any(x in norm(value(r, cc)) for x in ("横截面", "crosssection", "alllogical"))), [])
        direct = sum((number(value(row, an)) == 312, close(value(row, ap), metric([r for r in expected_main if r["year"] == 2023])["pct"]), number(value(row, bn)) == 427, close(value(row, bp), metric([r for r in expected_main if r["year"] == 2024])["pct"])))
        company_checks = max(company_checks, direct)
    weighted_doc = any(x in notes_n for x in ("提交加权", "逻辑提交加权", "响应单元"))
    score.add("C1", 3, 2.7 * company_checks / 9 + 0.3 * weighted_doc, f"company_elements={company_checks}/9")

    item_table = best_table(analysis, [["item", "题号", "canonicalitem"], ["scope", "范围", "年度"], ["mean5", "五点均值", "均分"], ["population", "口径", "分析口径"]], 3)
    tier_table = best_table(analysis, [["tier", "阶梯"], ["scope", "范围", "年度"], ["mean5", "五点均值", "均分"], ["population", "口径", "分析口径"], ["members", "题目成员", "所含题目"]], 4)
    item_ok = tier_ok = 0; item_total = 2 * 3 * 12; tier_total = 2 * 3 * 4
    if item_table:
        sheet, ri, h = item_table; pi = column(h, ["population", "口径", "分析口径"]); si = column(h, ["scope", "范围", "年度"]); qi = column(h, ["item", "题号", "canonicalitem"]); mi = column(h, ["mean5", "五点均值", "均分"], ["pct"]); found = {}
        for row in analysis[sheet][ri + 1:]:
            q = item_id(value(row, qi)); s = scope_id(value(row, si)); p = population_id(value(row, pi))
            if q and s: found[(p, s, q)] = row
        for pop, rows in (("main", expected_main), ("sensitivity", expected_sens)):
            for s, subset in (("2023", [r for r in rows if r["year"] == 2023]), ("2024", [r for r in rows if r["year"] == 2024]), ("combined", rows)):
                for q in range(1, 13): item_ok += close(value(found.get((pop, s, f"Q{q:02d}"), []), mi), metric(subset, [q])["mean"])
    if tier_table:
        sheet, ri, h = tier_table; pi = column(h, ["population", "口径", "分析口径"]); si = column(h, ["scope", "范围", "年度"]); ti = column(h, ["tier", "阶梯"]); mi = column(h, ["mean5", "五点均值", "均分"], ["pct"]); found = {}
        for row in analysis[sheet][ri + 1:]:
            t = next((x for x in TIER_ORDER if norm(x) in norm(value(row, ti))), None); s = scope_id(value(row, si)); p = population_id(value(row, pi))
            if t and s: found[(p, s, t)] = row
        for pop, rows in (("main", expected_main), ("sensitivity", expected_sens)):
            for s, subset in (("2023", [r for r in rows if r["year"] == 2023]), ("2024", [r for r in rows if r["year"] == 2024]), ("combined", rows)):
                for t in TIER_ORDER: tier_ok += close(value(found.get((pop, s, t), []), mi), metric(subset, tier_questions(item_meta, t))["mean"])
    wide_item = best_table(analysis, [["canonicalitem", "题号"], ["rawmeanalpha", "alpha均值", "2023均值"], ["rawmeanbeta", "beta均值", "2024均值"], ["population", "口径"]], 3)
    if wide_item:
        sheet, ri, h = wide_item; qi = column(h, ["canonicalitem", "题号"]); pi = column(h, ["population", "口径"]); ma = column(h, ["rawmeanalpha", "alpha均值", "2023均值"]); mb = column(h, ["rawmeanbeta", "beta均值", "2024均值"]); found = {}
        for row in analysis[sheet][ri + 1:]:
            q = item_id(value(row, qi))
            if q: found[(population_id(value(row, pi)), q)] = row
        wide_ok = 0
        for pop, rows in (("main", expected_main), ("sensitivity", expected_sens)):
            for q in range(1, 13):
                row = found.get((pop, f"Q{q:02d}"), []); wide_ok += close(value(row, ma), metric([r for r in rows if r["year"] == 2023], [q])["mean"]); wide_ok += close(value(row, mb), metric([r for r in rows if r["year"] == 2024], [q])["mean"])
        item_ok = max(item_ok, wide_ok)
    pct_item = best_table(analysis, [["item", "题号"], ["alphascorepct", "2023得分"], ["betascorepct", "2024得分"], ["alphan", "2023样本"], ["betan", "2024样本"]], 4)
    if pct_item:
        sheet, ri, h = pct_item; qi = column(h, ["item", "题号"]); ap = column(h, ["alphascorepct", "2023得分"]); bp = column(h, ["betascorepct", "2024得分"]); found = {item_id(value(r, qi)): r for r in analysis[sheet][ri + 1:] if item_id(value(r, qi))}
        direct = 0
        for q in range(1, 13):
            row = found.get(f"Q{q:02d}", []); direct += close(value(row, ap), metric([r for r in expected_main if r["year"] == 2023], [q])["pct"]); direct += close(value(row, bp), metric([r for r in expected_main if r["year"] == 2024], [q])["pct"])
        item_ok = max(item_ok, direct)
    wide_tier = best_table(analysis, [["tier", "阶梯"], ["items", "题目成员"], ["rawmeanalpha", "alpha均值", "2023均值"], ["rawmeanbeta", "beta均值", "2024均值"], ["population", "口径"]], 4)
    if wide_tier:
        sheet, ri, h = wide_tier; ti = column(h, ["tier", "阶梯"]); pi = column(h, ["population", "口径"]); ma = column(h, ["rawmeanalpha", "alpha均值", "2023均值"]); mb = column(h, ["rawmeanbeta", "beta均值", "2024均值"]); found = {}
        for row in analysis[sheet][ri + 1:]:
            t = next((x for x in TIER_ORDER if norm(x) in norm(value(row, ti))), None)
            if t: found[(population_id(value(row, pi)), t)] = row
        wide_ok = 0
        for pop, rows in (("main", expected_main), ("sensitivity", expected_sens)):
            for t in TIER_ORDER:
                row = found.get((pop, t), []); qs = tier_questions(item_meta, t); wide_ok += close(value(row, ma), metric([r for r in rows if r["year"] == 2023], qs)["mean"]); wide_ok += close(value(row, mb), metric([r for r in rows if r["year"] == 2024], qs)["mean"])
        tier_ok = max(tier_ok, wide_ok)
    score.add("C2", 3, 2 * item_ok / item_total + tier_ok / tier_total, f"items={item_ok}/{item_total}, tiers={tier_ok}/{tier_total}")
    top_doc = any(x in notes_n for x in ("topbox", "顶级回答", "顶级率")) and any(x in notes_n for x in ("标准分5", "得分5", "分值5", "标准分=5"))
    sd_doc = any(x in notes for x in ("样本标准差", "原始分标准差")) and any(x in notes_n for x in ("n1", "n-1", "原始15分", "底层15分", "原始分"))
    reconcile_map, _, _ = metric_map(analysis, [["check", "核对项"], ["actual", "实际值"], ["expected", "预期值"]])
    reconcile_ok = sum(close(reconcile_map.get(norm(name)), expected) for name, expected in (("raw_rows", 795), ("distinct_response_keys", 739), ("overlap_extra_rows", 56), ("main_response_cells", 8868)))
    recon_table = best_table(analysis, [["check", "核对项"], ["expected", "预期"], ["actual", "实际"], ["status", "状态"]], 3)
    if recon_table:
        sheet, ri, h = recon_table; kc = column(h, ["check", "核对项"]); ec = column(h, ["expected", "预期"]); ac = column(h, ["actual", "实际"]); sc_ = column(h, ["status", "状态"]); semantic = 0
        rows = analysis[sheet][ri + 1:]
        patterns = (("exportrows", 795), ("canonicalperresponsekey", 739), ("extraexport", 56))
        for pattern, expected in patterns:
            semantic += any(pattern in norm(value(row, kc)) and close(value(row, ec), expected) and close(value(row, ac), expected) and norm(value(row, sc_)) in {"pass", "通过", "true"} for row in rows)
        alpha_cells = next((number(value(row, ac)) for row in rows if "mainalphaitemcells" in norm(value(row, kc))), None)
        beta_cells = next((number(value(row, ac)) for row in rows if "mainbetaitemcells" in norm(value(row, kc))), None)
        semantic += alpha_cells is not None and beta_cells is not None and alpha_cells + beta_cells == 8868
        reconcile_ok = max(reconcile_ok, semantic)
    score.add("C3", 4, top_doc + sd_doc + 0.5 * reconcile_ok, f"top_doc={top_doc}, sd_doc={sd_doc}, reconciliations={reconcile_ok}/4")

    expected_by_person = {(r["token"], r["year"]): r for r in expected_main}; repeats = sorted({p for p, _ in expected_by_person if all((p, y) in expected_by_person for y in (2023, 2024))})
    panel_books = dict(clean); panel_books.update(analysis)
    panel_table = best_table(panel_books, [["participanttoken", "人员键", "匿名代号"], ["mean2023", "2023均值"], ["mean2024", "2024均值"], ["delta", "变化", "差值"]], 3)
    panel_member = panel_values = 0; published_identity = False
    if panel_table:
        sheet, ri, h = panel_table; pc = column(h, ["participanttoken", "人员键", "匿名代号"]); a = column(h, ["mean2023", "2023均值"]); b = column(h, ["mean2024", "2024均值"]); d = column(h, ["delta5", "变化", "差值"]); rows = panel_books[sheet][ri + 1:]; found = {str(value(r, pc)).strip(): r for r in rows}
        for person in repeats:
            row = found.get(person); m23 = sum(expected_by_person[(person, 2023)]["scores"]) / 12; m24 = sum(expected_by_person[(person, 2024)]["scores"]) / 12
            panel_member += row is not None
            if row: panel_values += close(value(row, a), m23) + close(value(row, b), m24) + close(value(row, d), m24 - m23)
        published_identity = True
    # Equivalent controlled-detail design: identities need not be published in the
    # analysis workbook when the cleaned audit ledger can reproduce every pair.
    if panel_member == 0 and candidate_long_scores:
        candidate_by_person_year = {}
        for key, row in canonical_candidates.items():
            person = str(value(row, idx["token"])).strip(); year = scope_id(value(row, idx["wave"])); scores = candidate_long_scores.get(key, {})
            if person and year in {"2023", "2024"} and all(f"Q{q:02d}" in scores for q in range(1, 13)):
                candidate_by_person_year[(person, int(year))] = sum(scores[f"Q{q:02d}"] for q in range(1, 13)) / 12
        derived_members = derived_values = 0
        for person in repeats:
            akey = (person, 2023); bkey = (person, 2024)
            if akey in candidate_by_person_year and bkey in candidate_by_person_year:
                derived_members += 1; ca = candidate_by_person_year[akey]; cb = candidate_by_person_year[bkey]
                ea = sum(expected_by_person[akey]["scores"]) / 12; eb = sum(expected_by_person[bkey]["scores"]) / 12
                derived_values += close(ca, ea) + close(cb, eb) + close(cb - ca, eb - ea)
        panel_member = max(panel_member, derived_members); panel_values = max(panel_values, derived_values)
    panel_doc = any(x in notes_n for x in ("横截面", "repeatedcrosssection")) and any(x in notes_n for x in ("面板", "panel"))
    score.add("D1", 10, 4 * panel_member / 131 + 4 * panel_values / (131 * 3) + 2 * panel_doc, f"members={panel_member}/131, values={panel_values}/{131*3}, boundary={panel_doc}")

    pmap, _, _ = metric_map(analysis, [["metric", "指标"], ["value", "数值", "结果"]])
    deltas = []
    for person in repeats:
        m23 = sum(expected_by_person[(person, 2023)]["scores"]) / 12; m24 = sum(expected_by_person[(person, 2024)]["scores"]) / 12; deltas.append(m24 - m23)
    dm = sum(deltas) / len(deltas); dsd = stdev(deltas); se = dsd / len(deltas) ** 0.5
    pair_checks = sum(close(pmap.get(norm(k)), v) for k, v in (("repeat_people", 131), ("paired_mean_2023", 3.96501272264631), ("paired_mean_2024", 3.91793893129771), ("paired_delta_5", dm)))
    uncert_checks = sum(close(pmap.get(norm(k)), v) for k, v in (("delta_sd", dsd), ("delta_se", se), ("normal_approx_ci_low", dm - 1.96 * se), ("normal_approx_ci_high", dm + 1.96 * se)))
    panel_summary = best_table(analysis, [["population", "口径"], ["npairedpeople", "配对人数"], ["rawmeanalpha", "2023均值"], ["rawmeanbeta", "2024均值"], ["meanwithinpersonchange", "同人变化"], ["sdpersonchange", "差值标准差"]], 5)
    if panel_summary:
        sheet, ri, h = panel_summary; pc = column(h, ["population", "口径"]); main_row = next((r for r in analysis[sheet][ri + 1:] if population_id(value(r, pc)) == "main"), [])
        np = column(h, ["npairedpeople", "配对人数"]); ma = column(h, ["rawmeanalpha", "2023均值"]); mb = column(h, ["rawmeanbeta", "2024均值"]); md = column(h, ["meanwithinpersonchange", "同人变化"])
        sd = column(h, ["sdpersonchange", "差值标准差"]); sec = column(h, ["sechange", "标准误"]); lo = column(h, ["ci95low", "区间下限"]); hi = column(h, ["ci95high", "区间上限"])
        pair_checks = max(pair_checks, sum((number(value(main_row, np)) == 131, close(value(main_row, ma), 3.96501272264631), close(value(main_row, mb), 3.91793893129771), close(value(main_row, md), dm / 5))))
        uncert_checks = max(uncert_checks, sum((close(value(main_row, sd), dsd / 5), close(value(main_row, sec), se / 5), close(value(main_row, lo), (dm - 1.96 * se) / 5), close(value(main_row, hi), (dm + 1.96 * se) / 5))))
    paired_comparison = best_table(analysis, [["comparison", "比较"], ["alphan", "2023样本"], ["betan", "2024样本"], ["alphascorepct", "2023得分"], ["betascorepct", "2024得分"], ["delta", "变化"]], 5)
    if paired_comparison:
        sheet, ri, h = paired_comparison; cc = column(h, ["comparison", "比较"]); row = next((r for r in analysis[sheet][ri + 1:] if any(x in norm(value(r, cc)) for x in ("同一员工", "配对", "panel"))), [])
        an = column(h, ["alphan", "2023样本"]); bn = column(h, ["betan", "2024样本"]); ap = column(h, ["alphascorepct", "2023得分"]); bp = column(h, ["betascorepct", "2024得分"]); dc = column(h, ["delta", "变化"]); lo = column(h, ["95cilow", "区间下限"]); hi = column(h, ["95cihigh", "区间上限"])
        pair_checks = max(pair_checks, sum((number(value(row, an)) == 131 and number(value(row, bn)) == 131, close(value(row, ap), 3.96501272264631 / 5), close(value(row, bp), 3.91793893129771 / 5), close(value(row, dc), dm / 5))))
        uncert_checks = max(uncert_checks, 2 * sum((close(value(row, lo), (dm - 1.96 * se) / 5), close(value(row, hi), (dm + 1.96 * se) / 5))))
    uncertainty_doc = any(x in notes_n for x in ("个人差值", "personleveldifference", "personlevelpaireddifference", "人员差值")) and any(x in notes_n for x in ("区间", "uncertainty", "不确定性"))
    score.add("D2", 8, 4 * pair_checks / 4 + 3 * uncert_checks / 4 + uncertainty_doc, f"paired={pair_checks}/4, uncertainty={uncert_checks}/4, unit_doc={uncertainty_doc}")

    comp_table = best_table(analysis, [["component", "分量", "队列"], ["value5", "五点值", "结果"]], 2)
    cmap = {}
    if comp_table:
        sheet, ri, h = comp_table; kc = column(h, ["component", "分量", "队列", "指标"]); vc = column(h, ["value5", "五点值", "结果", "数值"], ["pct", "百分"]); cmap = {norm(value(r, kc)): value(r, vc) for r in analysis[sheet][ri + 1:] if value(r, kc) != ""}
    cohort_truth = {
        "n_2023_repeat": 131, "n_2024_repeat": 131, "n_2023_nonrepeat": 181, "n_2024_nonrepeat": 296,
        "mean_2023_repeat": 3.96501272264631, "mean_2024_repeat": 3.91793893129771,
        "mean_2023_nonrepeat": 3.98848987108656, "mean_2024_nonrepeat": 4.0365990990991,
        "weight_2023_repeat": 131 / 312, "weight_2024_repeat": 131 / 427,
        "weight_2023_nonrepeat": 181 / 312, "weight_2024_nonrepeat": 296 / 427,
    }
    cohort_checks = sum(close(cmap.get(norm(k)), v) for k, v in cohort_truth.items())
    cohort_table = best_table(analysis, [["population", "口径"], ["cohort", "队列"], ["period", "期间"], ["n", "样本量"], ["share", "权重"], ["scorepct", "得分"]], 5)
    if cohort_table:
        sheet, ri, h = cohort_table; pc = column(h, ["population", "口径"]); cc = column(h, ["cohort", "队列"]); tc = column(h, ["period", "期间"]); nc = column(h, ["n", "样本量"]); wc = column(h, ["share", "权重"]); mc = column(h, ["scorepct", "得分"])
        found = {(norm(value(r, cc)), scope_id(value(r, tc))): r for r in analysis[sheet][ri + 1:] if population_id(value(r, pc)) == "main"}
        direct = 0
        for cohort, scope, n, weight, mean5 in (("repeat", "2023", 131, 131/312, cohort_truth["mean_2023_repeat"]), ("repeat", "2024", 131, 131/427, cohort_truth["mean_2024_repeat"]), ("nonrepeat", "2023", 181, 181/312, cohort_truth["mean_2023_nonrepeat"]), ("nonrepeat", "2024", 296, 296/427, cohort_truth["mean_2024_nonrepeat"])):
            row = found.get((cohort, scope), []); direct += number(value(row, nc)) == n; direct += close(value(row, wc), weight); direct += close(value(row, mc), mean5 / 5)
        cohort_checks = max(cohort_checks, direct)
    if paired_comparison:
        sheet, ri, h = paired_comparison; cc = column(h, ["comparison", "比较"]); an = column(h, ["alphan", "2023样本"]); bn = column(h, ["betan", "2024样本"]); ap = column(h, ["alphascorepct", "2023得分"]); bp = column(h, ["betascorepct", "2024得分"])
        repeat_row = next((r for r in analysis[sheet][ri + 1:] if any(x in norm(value(r, cc)) for x in ("同一员工", "配对", "panel"))), [])
        nonrepeat_row = next((r for r in analysis[sheet][ri + 1:] if any(x in norm(value(r, cc)) for x in ("非同人", "nonrepeat", "仅alpha"))), [])
        direct = sum((number(value(repeat_row, an)) == 131, number(value(repeat_row, bn)) == 131, close(value(repeat_row, ap), cohort_truth["mean_2023_repeat"] / 5), close(value(repeat_row, bp), cohort_truth["mean_2024_repeat"] / 5), number(value(nonrepeat_row, an)) == 181, number(value(nonrepeat_row, bn)) == 296, close(value(nonrepeat_row, ap), cohort_truth["mean_2023_nonrepeat"] / 5), close(value(nonrepeat_row, bp), cohort_truth["mean_2024_nonrepeat"] / 5), number(value(repeat_row, an)) / 312 == 131/312 if number(value(repeat_row, an)) is not None else False, number(value(repeat_row, bn)) / 427 == 131/427 if number(value(repeat_row, bn)) is not None else False, number(value(nonrepeat_row, an)) / 312 == 181/312 if number(value(nonrepeat_row, an)) is not None else False, number(value(nonrepeat_row, bn)) / 427 == 296/427 if number(value(nonrepeat_row, bn)) is not None else False))
        cohort_checks = max(cohort_checks, direct)
    nonrepeat_doc = any(x in notes_n for x in ("nonrepeat", "非重复", "非同人")) and any(x in notes_n for x in ("不是同一人群", "不是跨期相同的同一人群", "不同人员", "不是面板", "notthesame"))
    score.add("D3", 7, 6 * cohort_checks / len(cohort_truth) + nonrepeat_doc, f"cohort={cohort_checks}/{len(cohort_truth)}, boundary={nonrepeat_doc}")
    decomp_truth = {"cross_section_delta": 0.0215626813987466, "within_component": 0.0135262214921979, "composition_component": 0.00803645990654905, "reconciliation_error": 0.0}
    decomp_checks = sum(close(cmap.get(norm(k)), v) for k, v in decomp_truth.items())
    decomp_table = best_table(analysis, [["population", "口径"], ["componentscope", "分量范围"], ["withincohortcomponent", "队列内分量"], ["sharecompositioncomponent", "构成分量"], ["totalcomponent", "总变化"], ["formula", "公式"]], 5)
    if decomp_table:
        sheet, ri, h = decomp_table; pc = column(h, ["population", "口径"]); sc = column(h, ["componentscope", "分量范围"]); wc = column(h, ["withincohortcomponent", "队列内分量"]); cc = column(h, ["sharecompositioncomponent", "构成分量"]); tc = column(h, ["totalcomponent", "总变化"]); fc = column(h, ["formula", "公式"])
        row = next((r for r in analysis[sheet][ri + 1:] if population_id(value(r, pc)) == "main" and norm(value(r, sc)) in {"total", "合计", "总计"}), [])
        direct = sum((close(value(row, tc), decomp_truth["cross_section_delta"] / 5), close(value(row, wc), decomp_truth["within_component"] / 5), close(value(row, cc), decomp_truth["composition_component"] / 5), "residual" in norm(value(row, fc)) and any(x in str(value(row, fc)) for x in ("0.000000", "e-"))))
        decomp_checks = max(decomp_checks, direct)
    decomp_doc = any(x in notes_n for x in ("kitagawa", "中点分解", "构成项")) and any(x in notes_n for x in ("勾稽", "之和", "reconcile"))
    score.add("D4", 10, 8 * decomp_checks / 4 + 2 * decomp_doc, f"components={decomp_checks}/4, formula_doc={decomp_doc}")
    boundaries = [
        (any(x in notes for x in ("横截面", "公司")) and any(x in notes for x in ("面板", "同一"))),
        any(x in notes for x in ("因果", "不能证明", "描述性")),
        any(x in notes for x in ("正式响应率", "邀请名单", "非响应")),
        ("快照" in notes and any(x in notes for x in ("不能还原", "不是历史", "当前快照"))),
        any(x in notes for x in ("显著性", "不确定性", "区间")),
    ]
    score.add("D5", 5, sum(boundaries), f"boundaries={boundaries}")

    priority_item_table = best_table(analysis, [["item", "题号"], ["priority", "优先级"], ["scorepct2023", "scorepctalpha", "2023得分"], ["scorepct2024", "scorepctbeta", "2024得分"], ["change", "变化"]], 4)
    expected_item_priority = {"Q02": "P2", "Q04": "P2", "Q06": "P2", "Q07": "P2", "Q08": "P2", "Q10": "P2", "Q11": "P2", "Q12": "P2", "Q05": "P3", "Q01": "monitor", "Q03": "monitor", "Q09": "monitor"}
    item_members = item_stats = 0; item_sens_cols = False
    if priority_item_table:
        sheet, ri, h = priority_item_table; qi = column(h, ["item", "题号"]); pr = column(h, ["priority", "优先级"]); p23 = column(h, ["scorepct2023", "scorepctalpha", "2023得分"]); p24 = column(h, ["scorepct2024", "scorepctbeta", "2024得分"]); ch = column(h, ["change", "变化"]); sp = column(h, ["sensitivity", "敏感性"]); found = {item_id(value(r, qi)): r for r in analysis[sheet][ri + 1:] if item_id(value(r, qi))}
        for q, expected in expected_item_priority.items():
            row = found.get(q); item_members += row is not None and norm(expected) in norm(value(row, pr))
            if row:
                qn = int(q[1:]); m23 = metric([r for r in expected_main if r["year"] == 2023], [qn]); m24 = metric([r for r in expected_main if r["year"] == 2024], [qn])
                item_stats += close(value(row, p23), m23["pct"]) + close(value(row, p24), m24["pct"]) + close(value(row, ch), m24["pct"] - m23["pct"])
        item_sens_cols = sp is not None or sum("敏感" in norm(x) or "sensitivity" in norm(x) for x in h) >= 2
    threshold_doc = ("80%" in notes or "0.8" in notes) and (("1" in notes and "百分点" in notes) or any(x in notes for x in ("1个百分", "0.01")))
    score.add("E1", 7, 2 * threshold_doc + 2 * item_stats / 36 + 2 * item_members / 12 + item_sens_cols, f"threshold={threshold_doc}, stats={item_stats}/36, priorities={item_members}/12, sensitivity={item_sens_cols}")

    dept_table = best_table(analysis, [["surveyorg", "调查组织", "问卷部门"], ["priority", "优先级"], ["n2023", "nalpha", "2023样本"], ["n2024", "nbeta", "2024样本"], ["weakest", "lowestbetaitemdriver", "最弱阶梯"]], 4)
    dept_expected = {"技术服务部": "P1", "云网产品部": "P2", "媒体产品部": "monitor", "产品拓展部": "monitor", "工程建设部": "monitor", "测试部": "monitor"}
    dept_member = dept_stats = weakest_present = 0
    if dept_table:
        sheet, ri, h = dept_table; oc = column(h, ["surveyorg", "调查组织", "问卷部门"]); pc = column(h, ["priority", "优先级"]); n23 = column(h, ["n2023", "nalpha", "2023样本"]); n24 = column(h, ["n2024", "nbeta", "2024样本"]); weak = column(h, ["weakest", "lowestbetaitemdriver", "最弱阶梯"]); found = {str(value(r, oc)).strip(): r for r in analysis[sheet][ri + 1:]}
        expected_ns = {"技术服务部": (29, 20), "云网产品部": (35, 53), "媒体产品部": (23, 33), "产品拓展部": (68, 84), "工程建设部": (24, 29), "测试部": (29, 48)}
        for org, expected in dept_expected.items():
            row = found.get(org); actual_priority = norm(value(row, pc)); dept_member += row is not None and (norm(expected) in actual_priority or (expected == "monitor" and actual_priority.startswith("p4")))
            if row: dept_stats += number(value(row, n23)) == expected_ns[org][0]; dept_stats += number(value(row, n24)) == expected_ns[org][1]; weakest_present += bool(str(value(row, weak)).strip())
    action_doc = (("两期各" in notes and "20" in notes) or "actionn20" in notes_n)
    score.add("E2", 6, 1.5 * action_doc + 2 * dept_member / 6 + 1.5 * dept_stats / 12 + weakest_present / 6, f"threshold={action_doc}, priorities={dept_member}/6, n={dept_stats}/12, weakest={weakest_present}/6")
    sens_doc = any(x in notes_n for x in ("敏感性", "sensitivity")) and any(x in notes_n for x in ("分类", "优先级", "稳健", "反转"))
    sens_company = ("559" in notes or any(close(v, 559) for v in reconcile_map.values()))
    score.add("E3", 5, 1 * sens_company + 2 * item_sens_cols + 2 * sens_doc, f"population={sens_company}, columns={item_sens_cols}, interpretation={sens_doc}")
    group_table = best_table(analysis, [["dimension", "维度"], ["group", "category", "分组"], ["n", "nalpha", "样本量"], ["suppressed", "release", "抑制"]], 3)
    small = small_ok = 0
    if group_table:
        sheet, ri, h = group_table; nc = column(h, ["n", "样本量"]); mc = column(h, ["mean5", "五点均值", "得分"]); scp = column(h, ["suppressed", "抑制", "发布状态"])
        for row in analysis[sheet][ri + 1:]:
            n = number(value(row, nc))
            if n is not None and n < 10:
                small += 1; small_ok += number(value(row, mc)) is None and (boolean(value(row, scp)) is True or "抑制" in norm(value(row, scp)) or "不发布" in norm(value(row, scp)))
        na = column(h, ["nalpha", "2023样本"]); nb = column(h, ["nbeta", "2024样本"]); sa = column(h, ["scorepctalpha", "2023得分"]); sb = column(h, ["scorepctbeta", "2024得分"]); ra = column(h, ["alpharelease", "2023发布"]); rb = column(h, ["betarelease", "2024发布"])
        if na is not None and nb is not None:
            small = small_ok = 0
            for row in analysis[sheet][ri + 1:]:
                for nc_, mc_, rc_ in ((na, sa, ra), (nb, sb, rb)):
                    n = number(value(row, nc_))
                    if n is not None and n < 10:
                        small += 1; small_ok += number(value(row, mc_)) is None and "suppress" in norm(value(row, rc_))
    suppress_doc = any(x in notes_n for x in ("n10", "n<10", "少于10", "小于10")) and "抑制" in notes
    group_time_doc = any(x in notes_n for x in ("时间不可能", "时点不可用", "人员属性")) and any(x in notes_n for x in ("不使用", "排除", "为空"))
    score.add("E4", 4, suppress_doc + group_time_doc + 2 * (small_ok / small if small else 0), f"small={small_ok}/{small}, docs={suppress_doc}/{group_time_doc}")
    summary_points = [
        any(x in notes for x in ("横截面", "公司")) and (any(x in notes for x in ("略升", "上升", "增加")) or "+0.4" in notes),
        any(x in notes for x in ("面板下降", "同人下降", "配对下降", "面板")),
        any(x in notes for x in ("构成项", "样本构成")),
        any(x in notes for x in ("优先", "行动")),
        any(x in notes for x in ("不确定", "区间", "不能证明")),
    ]
    trace_doc = any(x in notes_n for x in ("canonical", "主导出记录", "responsekey")) and any(x in notes for x in ("工作表", "结果位置", "来源"))
    score.add("E5", 3, 2.5 * sum(summary_points) / 5 + 0.5 * trace_doc, f"summary={summary_points}, trace={trace_doc}")

    present = all(path.exists() for path in files.values()); distinct = False
    if files["cleaned_samples.xlsx"].exists() and files["engagement_analysis.xlsx"].exists():
        distinct = hashlib.sha256(files["cleaned_samples.xlsx"].read_bytes()).digest() != hashlib.sha256(files["engagement_analysis.xlsx"].read_bytes()).digest()
    score.add("F1", 1, 1 if present and distinct and count_match == 795 else 0.5 if present and distinct else 0, f"present={present}, distinct={distinct}, raw={count_match}")
    method_topics = ("字典", "重复导出", "主口径", "快照", "面板", "分解", "敏感性", "抑制", "优先级", "来源")
    topic_count = sum(topic in notes for topic in method_topics)
    score.add("F2", 2, 2 * topic_count / len(method_topics), f"topics={topic_count}/{len(method_topics)}")

    all_text = notes + "\n" + "\n".join(str(v) for book_ in (clean, analysis) for rows in book_.values() for row in rows for v in row if isinstance(v, str))
    privacy_hits = []
    patterns = {"phone": r"(?<!\d)1[3-9]\d{9}(?!\d)", "id": r"(?<!\d)\d{17}[\dXx](?!\d)", "email": r"[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}", "private_ip": r"\b(?:10\.|192\.168\.|172\.(?:1[6-9]|2\d|3[01])\.)\d{1,3}\.\d{1,3}\b"}
    privacy_text = "\n".join(line for line in all_text.splitlines() if not re.fullmatch(r"[0-9a-fA-F]{32,128}", line.strip()))
    for name, pattern in patterns.items():
        if re.search(pattern, privacy_text): privacy_hits.append(name)
    for path in (files["cleaned_samples.xlsx"], files["engagement_analysis.xlsx"]):
        if path.exists():
            with ZipFile(path) as archive:
                names = archive.namelist()
                if any(x.startswith(("xl/externalLinks/", "xl/comments", "xl/embeddings/")) for x in names): privacy_hits.append("ooxml_hidden_payload")
                for name in ("docProps/core.xml", "docProps/custom.xml"):
                    if name in names and any(x in archive.read(name).decode("utf-8", "ignore").lower() for x in ("xujing", "administrator")): privacy_hits.append("metadata")
    score.add("F3", 2, 2 if not privacy_hits else 0, f"privacy={privacy_hits}")

    if present and not distinct: score.cap(20, "two XLSX files identical")
    if logical_count and logical_count != 739: score.cap(30, "wrong logical response population")
    if idx["main"] is None or idx["sens"] is None: score.cap(35, "missing adopted population states")
    if panel_member == 0 and decomp_checks == 0: score.cap(45, "no panel or composition analysis")
    if privacy_hits: score.cap(0, "privacy disclosure")
    if not present: score.cap(50, "missing deliverable")
    final = score.final()
    return {"reward": round(final / 100, 4), "score": round(final, 4), "uncapped_score": round(score.total, 4), "caps": score.caps, "items": score.items}


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("ROOT", "/app/environment")).resolve()
    try: result = evaluate(root)
    except Exception as exc: result = {"reward": 0.0, "score": 0.0, "uncapped_score": 0.0, "caps": [{"maximum": 0, "reason": f"verifier error: {type(exc).__name__}: {exc}"}], "items": []}
    for directory in (root / "verifier", Path("/logs/verifier"), Path("/verifier")):
        try:
            directory.mkdir(parents=True, exist_ok=True); (directory / "reward.txt").write_text(f"{result['reward']}\n"); (directory / "reward.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
        except Exception: pass
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
