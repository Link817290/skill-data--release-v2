"""Condition-blind numeric and source-binding verifier for quality reports."""
import argparse
import json
import math
import re
import shutil
import subprocess
import tempfile
import unicodedata
from datetime import datetime
from pathlib import Path

import openpyxl
from openpyxl.utils.cell import range_boundaries
from openpyxl.utils.datetime import from_excel

HERE = Path(__file__).resolve().parent
ALIASES = {
    "team": ["TL&(A)TL", "TeamLeader", "Team Leader", "团队", "班组", "组别", "TL", "team"],
    "manager": ["所属主管", "Supervisor", "主管", "manager"],
    "mean": ["Team平均分", "平均最终得分", "平均分", "平均得分", "均分", "mean", "average score"],
    "attainment": ["Team达成率", "达成率", "达标率", "及格率", "attainment", "pass rate"],
    "samples": ["质检抽测量", "质检监听", "质检监听量", "抽测量", "质检量", "质检条数", "抽检通数", "抽检数", "已质检联系数", "复核联系数", "sample count", "samples"],
    "calls": ["组别接通量", "接通量基数", "接通量", "calls", "call base"],
    "coverage": ["质检抽测率", "抽样覆盖率", "抽检覆盖率", "抽测率", "抽检率", "coverage", "sampling rate"],
    "qa": ["QA", "质检员", "分析人"],
    "monitor": ["监控条数", "监听条数", "质量监听", "质检复核", "质量复核", "监控", "monitor", "monitoring"],
    "dissatisfaction": ["不满意分析", "不满意分析条数", "dissatisfaction"],
    "complaints": ["投诉分析", "投诉分析条数", "complaints"],
    "total": ["总计", "合计", "完成总量", "总完成量", "完成复核总量", "总完成复核", "total"],
    "name": ["组员姓名", "员工姓名", "AgentName", "客服姓名", "员工", "姓名", "agent"],
    "score": ["最终得分", "最终分数", "最终质检分", "得分", "成绩", "score", "final score"],
    "category": ["联系类别", "联系分类", "接触类别", "接触分类", "录音分类", "业务分类", "contact type"],
    "issue": ["已记录观察（事实）", "记录观察（事实）", "记录观察事实", "已记录观察", "记录到的失误（CM备注）", "问题点", "问题描述", "违规原因", "issue", "finding"],
    "action": ["可执行改进建议", "建议未来行动（未执行）", "建议改进（未来行动）", "建议后续行动（未执行）", "建议的未来行动（未确认执行、未记录审批）", "提升建议", "整改建议", "建议", "action", "recommendation"],
    "source": ["证据来源", "来源", "source", "evidence"],
    "cause": ["原因", "原因总结", "原因分类", "cause"],
    "count": ["数量", "条数", "count"],
}


def norm(value):
    return re.sub(r"[\s\W_]+", "", str(value or "").lower())


def team_key(value):
    text = unicodedata.normalize("NFKC", str(value or "")).strip().upper()
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"(?:团队|小组|组|TEAM)$", "", text)
    return text


def header(value):
    key = norm(value)
    for field, aliases in ALIASES.items():
        if key in {norm(alias) for alias in aliases}:
            return field
    # A composite/decorated header still denotes one field when all recognized
    # semantic parts converge on that field. Unit suffixes and bilingual repeats
    # are presentation, not additional business columns.
    candidates = {
        field for field, aliases in ALIASES.items()
        if any(len(norm(alias)) >= 2 and norm(alias) in key for alias in aliases)
    }
    if len(candidates) == 1:
        return next(iter(candidates))
    if len(key) > 24:
        return None
    if re.search(r"平均.*(?:分|score)|均分", key):
        return "mean"
    if re.search(r"(?:达标|达成|及格).*率", key):
        return "attainment"
    if "接通量" in key:
        return "calls"
    if re.search(r"(?:抽样|抽检|抽测).*率", key):
        return "coverage"
    if "完成" not in key and re.search(r"(?:抽检|抽测|复核|质检).*(?:数|量)$", key):
        return "samples"
    if key in {"审核人", "复核人", "qa分析人", "质检员分析人"}:
        return "qa"
    if key in {"质量监听", "质量监控", "质检监听", "质量监听数"}:
        return "monitor"
    if key in {"完成总量", "完成审核总量", "完成复核总量", "完成复核合计", "总完成审查"}:
        return "total"
    if key in {"员工", "坐席", "客服员工"}:
        return "name"
    if re.search(r"(?:最终|终审|质检).*(?:得分|分数)|(?:得分|分数).*(?:cf|final)", key):
        return "score"
    if key in {"最终得分", "最终分", "最终质检得分", "已终审得分"}:
        return "score"
    if re.search(r"(?:联系|接触|业务|录音).*(?:类别|分类)", key):
        return "category"
    if key in {"接触类别", "联系类别", "联络分类"}:
        return "category"
    if re.search(r"(?:记录.*观察|观察.*事实|事实观察|已观察失败)", key):
        return "issue"
    if re.search(r"建议.*(?:改进|行动)|改进建议|拟议改进|未来行动", key):
        return "action"
    if key in {"证据位置", "证据定位", "源记录"}:
        return "source"
    if key in {"最终原因总结", "原因总结", "已记录根因类别"}:
        return "cause"
    return None


def number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) else None
    try:
        text = str(value).strip().replace(",", "")
        return float(text[:-1]) / 100 if text.endswith("%") else float(text)
    except (ValueError, TypeError):
        return None


def close(actual, expected, field):
    actual = number(actual)
    if actual is None:
        return False
    if field in {"attainment", "coverage", "attainment_comparison"}:
        return abs(actual-expected) <= 0.000051
    return abs(actual-expected) <= (0.0051 if field in {"mean", "mean_comparison", "score"} else 1e-8)


def day_key(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, (int, float)) and 40000 < value < 50000:
        return from_excel(value).date().isoformat()
    text = str(value).strip()
    match = re.search(r"(?:2015[年/-])?0?3[月/-]0?(25|26)(?:日)?", text)
    if not match:
        match = re.search(r"(?<!\d)(25|26)日", text)
    return "2015-03-"+match.group(1) if match else None


def descriptors(sheet, dates):
    found = []
    for r in range(1, sheet.max_row+1):
        mapping, day_columns, causes, comparison_columns = {}, {}, {}, {}
        for c in range(1, sheet.max_column+1):
            value = sheet.cell(r, c).value
            field = header(value)
            if field:
                mapping.setdefault(field, c)
            day = day_key(value)
            if day in dates:
                day_columns[day] = c
                if field in {"mean", "attainment"}:
                    comparison_columns.setdefault(field+"_comparison", {})[day] = c
            if value in {"产品问题", "第三方问题", "客服问题", "客户自身问题", "快递问题", "退款问题", "系统问题"}:
                causes[value] = c
        context = sheet.title + " " + " ".join(str(sheet.cell(p, c).value or "") for p in range(max(1, r-3), r) for c in range(1, sheet.max_column+1))
        lower = context.lower()
        kind = None
        if "team" in mapping and any(len(columns)==2 for columns in comparison_columns.values()):
            for comparison_kind, columns in comparison_columns.items():
                if len(columns)==2:
                    found.append(dict(row=r,kind=comparison_kind,mapping=mapping,dates=columns,causes={}))
            continue
        if {"team", "mean", "attainment"} <= mapping.keys():
            kind = "cumulative" if any(t in lower for t in ("累计", "至今", "cumulative")) else "daily"
            for prior in range(r-1,0,-1):
                caption=" ".join(str(sheet.cell(prior,col).value or "") for col in range(1,sheet.max_column+1))
                if re.search(r"(?:累计|至今|cumulative).*(?:排名|团队|ranking)|(?:排名|ranking).*(?:累计|至今|cumulative)",caption,re.I):
                    kind="cumulative"
                    break
                if re.search(r"(?:日度|日报|报告日|当日|今日).*(?:排名|成绩)|(?:排名).*(?:报告日|日度)",caption):
                    kind="daily"
                    break
        elif "team" in mapping and len(day_columns) == 2:
            kind = "attainment_comparison" if any(t in lower for t in ("达成", "达标", "及格", "attainment", "pass rate")) else "mean_comparison"
        elif "team" in mapping and len(causes) >= 2:
            kind = "dissatisfaction"
        elif {"team", "cause", "count"} <= mapping.keys():
            kind = "dissatisfaction_long"
        elif {"qa", "monitor", "complaints"} <= mapping.keys():
            kind = "workload"
        elif {"team", "name", "score"} <= mapping.keys():
            if not excluded_detail_sheet(sheet):
                kind = "incidents"
        valid_teams = set(truth_team for truth_team in ("A", "B", "C", "D"))
        team_columns = {team_key(sheet.cell(r,c).value): c for c in range(1,sheet.max_column+1)
                        if team_key(sheet.cell(r,c).value) in valid_teams}
        if "cause" in mapping and len(team_columns)>=2:
            found.append(dict(row=r,kind="dissatisfaction_transposed",mapping=mapping,dates={},causes={},team_columns=team_columns))
            continue
        if kind:
            found.append(dict(row=r, kind=kind, mapping=mapping, dates=day_columns, causes=causes))
    return found


def vertical_incident(sheet):
    if excluded_detail_sheet(sheet):
        return None
    fields = {"team", "name", "score", "category", "issue", "action"}
    values = {}
    for row in sheet:
        for cell in row:
            field = header(cell.value)
            if field not in fields or field in values:
                continue
            candidates = [sheet.cell(cell.row, c).value for c in range(cell.column + 1, sheet.max_column + 1)]
            if not any(value not in (None, "") and header(value) is None for value in candidates):
                for next_row in range(cell.row + 1, min(sheet.max_row, cell.row + 2) + 1):
                    candidates.extend(sheet.cell(next_row, c).value for c in range(cell.column, sheet.max_column + 1))
            value = next((value for value in candidates if value not in (None, "") and header(value) is None), None)
            if value is not None:
                values[field] = value
    if {"team", "name", "score", "category"} <= values.keys() and number(values["score"]) is not None:
        values["_sheet"] = sheet.title
        return values
    return None


def excluded_detail_sheet(sheet):
    if not re.search(r"明细|底稿|审计|原始|detail|ledger", sheet.title, re.I):
        return False
    text = " ".join(str(cell.value) for row in sheet.iter_rows() for cell in row if cell.value not in (None, ""))
    return not re.search(r"致命|严重|升级|事件|fatal|incident", text, re.I)


def extract(book, truth):
    result = {key: {} for key in ("daily", "cumulative", "mean_comparison", "attainment_comparison", "dissatisfaction", "workload")}
    result["incidents"] = []
    result["dissatisfaction_total"] = {}
    contradictions = set()
    for sheet in book:
        incident_start = len(result["incidents"])
        descriptions = descriptors(sheet, truth["dates"])
        for index, spec in enumerate(descriptions):
            end = next((other["row"] for other in descriptions[index+1:] if other["row"]>spec["row"]),sheet.max_row+1)
            kind, mapping = spec["kind"], spec["mapping"]
            for row in range(spec["row"]+1, end):
                item = {field: sheet.cell(row, col).value for field, col in mapping.items()}
                if kind == "incidents":
                    if item.get("name") and number(item.get("score")) is not None:
                        item["_sheet"] = sheet.title
                        result[kind].append(item)
                    continue
                if kind == "dissatisfaction_transposed":
                    cause=str(item.get("cause") or "").strip()
                    allowed={c for counts in truth["dissatisfaction"].values() for c in counts}
                    if cause in {"总计", "合计", "Total", "total"}:
                        for team,col in spec["team_columns"].items():
                            result["dissatisfaction"].setdefault(team,{})["total"] = sheet.cell(row,col).value
                        if "total" in mapping:
                            result["dissatisfaction_total"]["total"] = item.get("total")
                        continue
                    if cause not in allowed:
                        continue
                    for team,col in spec["team_columns"].items():
                        key=team_key(team)
                        value=sheet.cell(row,col).value
                        existing=result["dissatisfaction"].setdefault(key,{})
                        if cause in existing and number(value) is not None and not close(existing[cause],number(value),"count"):
                            contradictions.add(("dissatisfaction",key))
                        existing[cause]=value
                    if "total" in mapping:
                        result["dissatisfaction_total"][cause] = item.get("total")
                    continue
                key = (str(item.get("qa") or "").strip() if kind == "workload"
                       else team_key(item.get("team")))
                if not key:
                    continue
                if key in {"总计", "合计", "Total", "total"}:
                    if kind == "dissatisfaction":
                        result["dissatisfaction_total"] = {
                            cause: sheet.cell(row, col).value or 0 for cause, col in spec["causes"].items()
                        }
                        if "total" in mapping:
                            result["dissatisfaction_total"]["total"] = item.get("total")
                    continue
                if kind in {"daily", "cumulative"}:
                    if number(item.get("mean")) is None:
                        continue
                    values = {k: item.get(k) for k in ("manager", "mean", "attainment", "samples", "calls", "coverage")}
                elif kind in {"mean_comparison", "attainment_comparison"}:
                    values = {day: sheet.cell(row, col).value for day, col in spec["dates"].items()}
                    if not any(number(v) is not None for v in values.values()):
                        continue
                elif kind == "dissatisfaction":
                    values = {cause: sheet.cell(row, col).value or 0 for cause, col in spec["causes"].items()}
                    if "total" in mapping:
                        values["total"] = item.get("total")
                    if not any(number(v) is not None for v in values.values()):
                        continue
                elif kind == "dissatisfaction_long":
                    cause = str(item["cause"])
                    if cause not in {c for counts in truth["dissatisfaction"].values() for c in counts}:
                        continue
                    existing = result["dissatisfaction"].setdefault(key, {})
                    if cause in existing and not close(existing[cause], number(item["count"]), "count"):
                        contradictions.add(("dissatisfaction", key))
                    existing[cause] = item["count"]
                    continue
                else:
                    if number(item.get("monitor")) is None:
                        continue
                    values = {k: item.get(k) for k in ("monitor", "dissatisfaction", "complaints", "total")}
                if key in result[kind]:
                    old = result[kind][key]
                    for field in old.keys() & values.keys():
                        a, b = number(old[field]), number(values[field])
                        if a is not None and b is not None and not close(a, b, kind if "comparison" in kind else field):
                            contradictions.add((kind, key))
                result[kind][key] = values
        if len(result["incidents"]) == incident_start:
            incident = vertical_incident(sheet)
            if incident:
                result["incidents"].append(incident)
        sheet_incidents=[row for row in result["incidents"] if row.get("_sheet")==sheet.title]
        # Separate labeled prose can belong to a single incident on the same sheet.
        unmapped=[row for row in result["incidents"] if "_sheet" not in row]
        for incident in unmapped:
            incident["_sheet"]=sheet.title
        sheet_incidents.extend(unmapped)
        if len(sheet_incidents)==1:
            incident=sheet_incidents[0]
            for row in sheet:
                for cell in row:
                    field=header(cell.value)
                    if field not in {"issue","action"} or incident.get(field):
                        continue
                    siblings=[sheet.cell(cell.row,c).value for c in range(cell.column+1,sheet.max_column+1)]
                    following=[sheet.cell(cell.row+1,c).value for c in range(cell.column,sheet.max_column+1)] if cell.row<sheet.max_row else []
                    texts=[v for v in siblings+following if isinstance(v,str) and len(v.strip())>=8 and header(v) is None]
                    if texts:
                        incident[field]=" ".join(texts)
    return result, sorted(contradictions)


def chart_count(book, truth):
    def reference_values(formula):
        sheet_name, span = formula.rsplit("!", 1)
        source = book[sheet_name.strip("'").replace("''", "'")]
        lowc, lowr, highc, highr = range_boundaries(span)
        return [source.cell(r,c).value for r in range(lowr,highr+1) for c in range(lowc,highc+1)]

    role_options=[]
    for sheet in book:
        for chart in sheet._charts:
            series_values=[]
            labeled_series=[]
            dated_series={}
            valid_chart = bool(chart.series)
            for series in chart.series:
                if series.cat is None or series.val is None or series.val.numRef is None:
                    valid_chart = False
                    continue
                try:
                    category_ref=series.cat.numRef or series.cat.strRef
                    if category_ref is None:
                        valid_chart = False
                        continue
                    categories=reference_values(category_ref.f)
                    values=reference_values(series.val.numRef.f)
                    if len(categories) != len(values) or len(values) < 2 or any(
                            key is None or value is None for key, value in zip(categories, values)):
                        valid_chart = False
                        continue
                    pairs={team_key(key):value for key,value in zip(categories,values)}
                    if len(pairs)>=2:
                        series_values.append(pairs)
                        label=None
                        if series.tx:
                            label=reference_values(series.tx.strRef.f)[0] if series.tx.strRef else series.tx.v
                        labeled_series.append((team_key(label),pairs))
                        day=day_key(label)
                        if day in truth["dates"]:
                            dated_series.setdefault(day,[]).append(pairs)
                except (ValueError, KeyError, TypeError, AttributeError):
                    valid_chart = False
                    continue
            if not valid_chart:
                continue
            matches=set()
            for kind in ("daily","cumulative"):
                for field in ("mean","attainment","samples"):
                    if any(all(team in pairs and close(pairs[team],row[field],field) for team,row in truth[kind].items()) for pairs in series_values):
                        matches.add(kind)
            for kind in ("mean_comparison","attainment_comparison"):
                if all(any(all(team in pairs and close(pairs[team],row[day],kind) for team,row in truth[kind].items()) for pairs in dated_series.get(day,[])) for day in truth["dates"]):
                    matches.add(kind)
            totals={cause:sum(row[cause] for row in truth["dissatisfaction"].values()) for cause in next(iter(truth["dissatisfaction"].values()))}
            if any(all(cause in pairs and close(pairs[cause],count,"count") for cause,count in totals.items()) for pairs in series_values):
                matches.add("dissatisfaction")
            by_team={label:pairs for label,pairs in labeled_series if label in truth["dissatisfaction"]}
            by_cause={label:pairs for label,pairs in labeled_series if label in totals}
            team_matrix=all(team in by_team and all(cause in by_team[team] and close(by_team[team][cause],count,"count") for cause,count in counts.items()) for team,counts in truth["dissatisfaction"].items())
            cause_matrix=all(cause in by_cause and all(team in by_cause[cause] and close(by_cause[cause][team],counts[cause],"count") for team,counts in truth["dissatisfaction"].items()) for cause in totals)
            if team_matrix or cause_matrix:
                matches.add("dissatisfaction")
            if matches:
                role_options.append(matches)
    possible={frozenset()}
    for options in role_options:
        possible |= {used|{role} for used in list(possible) for role in options if role not in used}
    return max(map(len,possible))


def semantic_decisions(book, charts, incidents):
    rows = []
    atomic_rows = []
    for sheet in book.worksheets:
        sheet_rows = [" ".join(str(cell.value) for cell in row if cell.value not in (None, ""))
                      for row in sheet.iter_rows()]
        sheet_rows = [text for text in sheet_rows if text]
        atomic_rows.extend(sheet_rows)
        rows.extend(sheet_rows)
        rows.extend(" ".join(sheet_rows[start:start + size])
                    for size in (2, 3) for start in range(len(sheet_rows) - size + 1))

    def has(*patterns):
        return any(all(re.search(pattern, text, re.I) for pattern in patterns) for text in rows)

    incident_rows = [
        " ".join(str(incident.get(field) or "") for field in ("issue", "action"))
        for incident in incidents
    ]
    incident_rows.extend(text for text in rows if re.search(r"事故|事件|致命|严重升级|fatal|incident", text, re.I))

    def incident_has(*patterns):
        return any(all(re.search(pattern, text, re.I) for pattern in patterns) for text in incident_rows)

    overlap_scope = has(r"重叠|已包含|包含报告日|包含于累计", r"未.*拼接|不.*拼接|不得拼接|避免重复|未重复")
    overlap_keys = has(
        r"逐条|逐行|一一对应|按键|记录键|联系键|稳定联系键|逐字段|完全一致",
        r"工号|员工|姓名|进线时间|得分|记录键|联系键|字段|按键|一一对应",
        r"今日|日度|日报|报告日|26日|03-26",
        r"累计",
    )
    record_unit = has(r"一行\s*[=＝是]\s*一条|每行.{0,12}一条|每条(?:源)?记录.{0,12}(?:对应|代表|视为).{0,8}(?:一次|一条)(?:复核|质检|联系)")
    repeated_names = has(r"同一员工|同名|重复.{0,8}(?:员工|姓名)|员工.{0,8}重复",
                         r"不.{0,8}(?:去重|合并)|保留|分别")
    coverage_formula = has(r"覆盖率|抽检率", r"抽检|复核|质检", r"接通量", r"参考基数|分母|÷|/")
    cumulative_base_limit = has(r"累计", r"接通量|基数", r"仅|给定|披露|参考", r"期间|流水|验证|核实")

    def adopted_completed_action(text):
        for sentence in re.split(r"[。；;\n]", text):
            if not re.search(r"整改|培训|复训|辅导|纠正|改进|事件|事故|措施|审批|批准", sentence):
                continue
            if not re.search(r"整改(?:已)?完成|(?:已|已经|现已)(?:完成|落实|整改|批准|执行|关闭)|已获批|获得批准", sentence):
                continue
            if not re.search(r"尚未|未曾|未核验|不能|不得|不可|不应|不代表|无证据|没有.*(?:证据|记录)", sentence):
                return True
        return False

    no_false_completion = not any(adopted_completed_action(text) for text in atomic_rows)
    decisions = {
        "S01": float(record_unit and repeated_names),
        "S02": float(overlap_scope and overlap_keys),
        "S03": float(has(r"最终得分|最终分数|终审", r"CF", r"不重算|直接采用|采用.*存储|已存|定稿")),
        "S04": float(coverage_formula and cumulative_base_limit),
        "S05": float(has(r"监听日期|质检日期", r"分析日期|分析时间", r"投诉")),
        "S06": float(has(r"有效", r"无效", r"工作量|分析", r"不剔除|保留|仍.*计|20条|20 条")),
        "S07": float(has(r"投诉", r"62", r"个案|流水", r"仅|汇总|工作量|不.*个案")),
        "S08": float(has(r"105", r"20", r"62", r"187")),
        "S09": float(incident_has(r"事实|观察", r"建议|未来行动|拟议|拟采取", r"未执行|未确认|不代表|尚未")),
        "S10": float(charts >= 5 and has(r"图表", r"绑定|数据区域|系列", r"可编辑|原生")),
        "S11": float(has(r"对比|比较", r"报告日|3月26|03-26", r"一致|同一批|逐团队|逐组")),
        "I07": float(any(
            term in text for text in incident_rows
            for term in ("流程复训", "专项辅导", "针对性复训", "流程培训", "流程指导", "现场辅导")
        ) or incident_has(r"核验|核实|检查", r"凭据|截图|联系方式|手机号")),
        "I10": float(incident_has(
            r"流程复训|专项辅导|针对性复训|流程培训|流程指导|现场辅导|核验|核实|检查",
            r"\u540e\u7eed|\u590d\u8bad\u540e|\u8ddf\u8e2a",
            r"\u62bd\u68c0|\u590d\u6838",
        )),
        "N01": float(no_false_completion),
    }
    return decisions


def evaluate(path, truth, params):
    if not path.is_file():
        return dict(valid_evaluation=True, status="missing_artifact", reward_strict=0.0, items={}, damage_events=[])
    if path.stat().st_size > 50_000_000:
        return dict(valid_evaluation=True, status="invalid_artifact", reward_strict=0.0, items={}, damage_events=[])
    try:
        book = openpyxl.load_workbook(path, data_only=True)
        raw = openpyxl.load_workbook(path, data_only=False)
    except Exception as exc:
        return dict(valid_evaluation=True, status="invalid_artifact", reason=type(exc).__name__, reward_strict=0.0, items={}, damage_events=[])
    formula_without_cache = any(cell.data_type == "f" and book[sheet.title][cell.coordinate].value is None for sheet in raw for row in sheet for cell in row)
    if formula_without_cache:
        office = shutil.which("libreoffice") or shutil.which("soffice")
        if not office:
            raise RuntimeError("Formula caches missing and LibreOffice is unavailable; evaluation cannot be settled")
        with tempfile.TemporaryDirectory(prefix="quality-report-recalc-") as temp:
            command = [office, "-env:UserInstallation=file://"+temp+"/profile", "--headless", "--convert-to", "xlsx", "--outdir", temp, str(path)]
            recalc = subprocess.run(command, capture_output=True, text=True, timeout=90)
            recalculated = Path(temp)/path.name
            if recalc.returncode or not recalculated.is_file():
                raise RuntimeError("Report formula recalculation failed: "+recalc.stderr[:300])
            book = openpyxl.load_workbook(recalculated, data_only=True)
            raw = openpyxl.load_workbook(recalculated, data_only=False)
    actual, contradictions = extract(book, truth)
    items = {}

    def measure(item_id, tests):
        tests = list(tests)
        fraction = sum(t[0] for t in tests)/len(tests) if tests else 0.0
        items[item_id] = dict(fraction=fraction, weight=0.0, matched=sum(t[0] for t in tests), expected=len(tests), failures=[t[1] for t in tests if not t[0]])

    for item_id, kind in [("P01", "daily"), ("P02", "cumulative")]:
        tests = []
        for team, row in truth[kind].items():
            found = actual[kind].get(team, {})
            for field in ("mean", "attainment", "samples"):
                tests.append((close(found.get(field), row[field], field), f"{kind}/{team}/{field}"))
            tests.append((str(found.get("manager", "")).strip() == row["manager"], f"{kind}/{team}/manager"))
        ordered = [team for team in actual[kind] if team in truth[kind]]
        rates = [truth[kind][team]["attainment"] for team in ordered]
        tests.append((len(ordered) == len(truth[kind]) and all(a<=b for a,b in zip(rates,rates[1:])), kind+"/risk_order"))
        measure(item_id, tests)
    measure("P03", ((close(actual[kind].get(team,{}).get(day), value, kind), f"{kind}/{team}/{day}") for kind in ("mean_comparison", "attainment_comparison") for team, row in truth[kind].items() for day,value in row.items()))
    measure("P04", ((close(actual[kind].get(team,{}).get(field), row[field], field), f"{kind}/{team}/{field}") for kind in ("daily", "cumulative") for team,row in truth[kind].items() for field in ("calls", "coverage")))
    dissatisfaction_tests = [
        (close(actual["dissatisfaction"].get(team, {}).get(cause), count, "count"), f"dissatisfaction/{team}/{cause}")
        for team, row in truth["dissatisfaction"].items() for cause, count in row.items()
    ]
    dissatisfaction_tests.extend(
        (close(actual["dissatisfaction"].get(team, {}).get("total"), sum(row.values()), "count"), f"dissatisfaction/{team}/total")
        for team, row in truth["dissatisfaction"].items()
    )
    cause_totals = {cause: sum(row[cause] for row in truth["dissatisfaction"].values())
                    for cause in next(iter(truth["dissatisfaction"].values()))}
    dissatisfaction_tests.extend(
        (close(actual["dissatisfaction_total"].get(cause), count, "count"), f"dissatisfaction/total/{cause}")
        for cause, count in cause_totals.items()
    )
    dissatisfaction_tests.append((close(actual["dissatisfaction_total"].get("total"), sum(cause_totals.values()), "count"),
                                  "dissatisfaction/total/total"))
    measure("P05", dissatisfaction_tests)
    incident_tests = []
    expected_names = {case["name"] for case in truth["incidents"]}
    for case in truth["incidents"]:
        candidates = [row for row in actual["incidents"] if str(row.get("name")).strip() == case["name"]]
        found = candidates[0] if candidates else {}
        for field in ("team", "category"):
            incident_tests.append((norm(found.get(field)) == norm(case[field]), "incident/"+field))
        incident_tests.append((close(found.get("score"),case["score"],"score"), "incident/score"))
        text = str(found.get("issue", ""))
        incident_tests.append((any(word in text for word in ("手机", "号码", "联系方式")) and any(word in text for word in ("截图", "交易凭", "交易证", "购买凭")), "incident/verified_cause"))
        action = str(found.get("action", ""))
        incident_tests.append((len(action.strip()) >= 8 and any(word in action for word in ("流程", "核验", "核实", "培训", "熟悉", "凭证", "截图")), "incident/relevant_action"))
    measure("P06", incident_tests)
    measure("P07", ((close(actual["workload"].get(qa,{}).get(field), value, field), f"workload/{qa}/{field}") for qa,row in truth["workload"].items() for field,value in row.items()))
    charts = chart_count(book,truth)
    measure("P08", ((charts>=index,"native_chart/"+str(index)) for index in range(1,6)))
    # Open-ended prose owners are settled only by the required source-bound LLM
    # layer. The program layer supplies numeric/structural prerequisites and never
    # awards semantic credit from keywords or regular expressions.
    semantic = {key: 0.0 for key in ("S01","S02","S03","S04","S05","S06","S07","S08",
                                      "S09","S10","S11","I07","I10","N01")}
    core = items

    items = {}

    def add_item(item_id, members):
        values = [core[member]["fraction"] if member.startswith("P") else semantic[member] for member in members]
        failures = []
        for member, value in zip(members, values):
            if member.startswith("P"):
                failures.extend(core[member]["failures"])
            elif value < 1.0:
                failures.append("semantic/"+member)
        items[item_id] = dict(
            fraction=sum(values)/len(values),
            weight=params["positive_weights"][item_id],
            matched=sum(values),
            expected=len(values),
            failures=failures,
            components=dict(zip(members, values)),
        )

    items["C01"] = dict(
        fraction=sum(core[f"P{index:02d}"]["fraction"] for index in range(1, 9)) / 8,
        weight=0.0,
        matched=sum(core[f"P{index:02d}"]["fraction"] for index in range(1, 9)),
        expected=8,
        failures=[failure for index in range(1, 9) for failure in core[f"P{index:02d}"]["failures"]],
        components={f"P{index:02d}": core[f"P{index:02d}"]["fraction"] for index in range(1, 9)},
    )
    for index in range(1, 9):
        source_id = f"P{index:02d}"
        item_id = f"B{index:02d}"
        items[item_id] = dict(
            fraction=core[source_id]["fraction"],
            weight=params["positive_weights"][item_id],
            matched=core[source_id]["matched"],
            expected=core[source_id]["expected"],
            failures=core[source_id]["failures"],
            components={source_id: core[source_id]["fraction"]},
        )
    closure_values = {
        "A01": (semantic["S01"] * core["P01"]["fraction"], ("P01", "S01")),
        "A02": (semantic["S02"] * core["P02"]["fraction"], ("P02", "S02")),
        "A03": (core["P03"]["fraction"] * (semantic["S03"] + semantic["S11"]) / 2, ("P03", "S03", "S11")),
        "A04": (core["P04"]["fraction"] * semantic["S04"], ("P04", "S04")),
        "A05": ((semantic["S05"] + semantic["S06"]) / 2, ("S05", "S06")),
        "A06": (core["P06"]["fraction"] * semantic["N01"] * (semantic["S09"] + semantic["I07"]) / 2,
                ("P06", "S09", "I07", "N01")),
        "A07": ((semantic["S07"] + semantic["S08"]) / 2, ("S07", "S08")),
        "A08": (semantic["S10"] * core["P08"]["fraction"], ("P08", "S10")),
        "A09": (core["P06"]["fraction"] * semantic["I10"] * semantic["N01"], ("P06", "I10", "N01")),
    }
    for item_id, (value, members) in closure_values.items():
        items[item_id] = dict(
            fraction=value,
            weight=params["positive_weights"][item_id],
            matched=value,
            expected=1,
            failures=[] if value == 1.0 else ["semantic/"+item_id],
            components={member: (core[member]["fraction"] if member.startswith("P") else semantic[member]) for member in members},
        )
    require_dependencies = params["owner_dependencies"]
    positive_item_ids = {item_id for item_id in items if item_id != "C01"}
    if set(require_dependencies) != positive_item_ids:
        raise ValueError("Owner dependency contract does not cover every positive item")
    for item_id, expected in require_dependencies.items():
        if list(items[item_id]["components"]) != expected:
            raise ValueError("Owner dependency contract differs from settlement: " + item_id)
    damages = []
    if contradictions:
        damages.append(dict(id="D01", root_cause="conflicting_adopted_aggregates", penalty=params["deductions"]["D01"], evidence=contradictions))
    false_incidents = sorted({str(row.get("name")) for row in actual["incidents"] if str(row.get("name")).strip() not in expected_names and close(row.get("score"),0,"score")})
    if false_incidents:
        damages.append(dict(id="D02", root_cause="unsupported_zero_score_incident", penalty=params["deductions"]["D02"], evidence=false_incidents))
    positive = sum(item["fraction"]*item["weight"] for item in items.values())
    penalty = sum(row["penalty"] for row in damages)
    return dict(valid_evaluation=True, status="scored", reward_strict=max(0.0,positive-penalty), positive_earned=positive, independent_damage_penalties=penalty, items=items, damage_events=damages, chart_count=charts)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", nargs="?", type=Path, default=Path("/workspace"))
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    truth = json.loads((HERE/"ground_truth.json").read_text(encoding="utf-8"))["facts"]
    params = json.loads((HERE/"scoring_params.json").read_text(encoding="utf-8"))
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
    direct = args.workspace/"service-quality-report.xlsx"
    path = args.artifact or (direct if (not args.out and direct.is_file()) or args.workspace.name == "output" else args.workspace/"output/service-quality-report.xlsx")
    try:
        result = evaluate(path, truth, params)
    except Exception as exc:
        if args.out:
            (args.out/"reward_detail.json").write_text(json.dumps(dict(valid_evaluation=False, status="verifier_error", error=type(exc).__name__+": "+str(exc)),ensure_ascii=False,indent=2),encoding="utf-8")
        raise
    score = result["reward_strict"]
    damage_count = len(result.get("damage_events") or [])
    scored_items = result.get("items") or {}
    domain_routes = params["lenient_domain_routes"]
    route_items = [item_id for routes in domain_routes.values() for route in routes for item_id in route]
    if not domain_routes or not set(route_items) <= set(params["positive_weights"]):
        raise ValueError("Invalid lenient domain-route contract")
    route_results = {
        domain: [{item_id: (float(scored_items.get(item_id, {}).get("fraction") or 0.0) > 0.0
                            if item_id.startswith("B")
                            else float(scored_items.get(item_id, {}).get("fraction") or 0.0) == 1.0)
                  for item_id in route} for route in routes]
        for domain, routes in domain_routes.items()
    }
    domain_gates = {domain: any(all(route.values()) for route in routes)
                    for domain, routes in route_results.items()}
    lenient = 1.0 if all(domain_gates.values()) and damage_count == 0 else 0.0
    result["lenient_basis"] = dict(domain_gates=domain_gates, routes=route_results,
                                    damage_count=damage_count)
    result["rewards"] = dict(strict=score, lenient=lenient)
    if args.out:
        (args.out/"reward_detail.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
        (args.out/"reward.json").write_text(json.dumps(dict(reward=score,reward_strict=score,reward_lenient=lenient,score=score)),encoding="utf-8")
        for name in ("reward.txt", "reward_strict.txt"):
            (args.out/name).write_text(str(score)+"\n",encoding="utf-8")
        (args.out/"reward_lenient.txt").write_text(str(lenient)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))


if __name__ == "__main__":
    main()
