"""Derive report facts from finalized records and disclosed operations context."""
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

import openpyxl
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.styles import Alignment, Font, PatternFill

CAUSES = ["产品问题", "第三方问题", "客服问题", "客户自身问题", "快递问题", "退款问题", "系统问题"]


def load_facts(materials):
    materials = Path(materials)
    source = materials / "quality-records.xlsx"
    context = materials / "operations-context.xlsx"
    book = openpyxl.load_workbook(source, data_only=True)
    ops = openpyxl.load_workbook(context, data_only=True)
    bases = {r[0]: (r[1], r[2]) for r in ops["接通量基数"].iter_rows(min_row=2, values_only=True) if r[0]}
    complaints = {r[0]: r[1] for r in ops["投诉工作量"].iter_rows(min_row=2, values_only=True) if r[0]}
    records = []
    for row in range(6, book.worksheets[1].max_row + 1):
        sheet = book.worksheets[1]
        if not isinstance(sheet.cell(row, 1).value, int):
            continue
        records.append(dict(row=row, team=sheet.cell(row, 5).value,
                            manager=sheet.cell(row, 6).value, name=sheet.cell(row, 3).value,
                            qa=sheet.cell(row, 7).value, date=sheet.cell(row, 8).value.date().isoformat(),
                            score=sheet[f"CF{row}"].value, issue=sheet[f"CM{row}"].value,
                            category=sheet[f"CH{row}"].value,
                            veto=any(str(sheet.cell(row, c).value).upper() == "Y" for c in range(74, 82))))
    if not records or any(not isinstance(r["score"], (int, float)) for r in records):
        raise ValueError("Finalized record scores or audit records unavailable")
    current_date = max(r["date"] for r in records)
    previous_date = min(r["date"] for r in records)
    teams = sorted({r["team"] for r in records})
    results = dict(daily={}, cumulative={}, mean_comparison={}, attainment_comparison={}, dissatisfaction={}, workload={}, incidents=[], dates=[previous_date, current_date])
    for team in teams:
        all_rows = [r for r in records if r["team"] == team]
        for period, rows, base_index in [("daily", [r for r in all_rows if r["date"] == current_date], 0), ("cumulative", all_rows, 1)]:
            results[period][team] = dict(manager=rows[0]["manager"], mean=mean(r["score"] for r in rows),
                attainment=sum(r["score"] >= 80 for r in rows) / len(rows), samples=len(rows),
                calls=bases[team][base_index], coverage=len(rows) / bases[team][base_index])
        for kind in ("mean_comparison", "attainment_comparison"):
            results[kind][team] = {}
            for day in results["dates"]:
                scores = [r["score"] for r in all_rows if r["date"] == day]
                results[kind][team][day] = mean(scores) if kind == "mean_comparison" else sum(s >= 80 for s in scores) / len(scores)
    dissatisfaction = book["不满意分析"]
    workload = Counter(r["qa"] for r in records if r["date"] == current_date)
    diss_workload = Counter()
    for row in range(2, dissatisfaction.max_row + 1):
        if not dissatisfaction.cell(row, 3).value:
            continue
        analysis_date = dissatisfaction.cell(row, 9).value.date().isoformat()
        if analysis_date != current_date:
            continue
        team = dissatisfaction.cell(row, 6).value
        cause = dissatisfaction.cell(row, 15).value
        counts = results["dissatisfaction"].setdefault(team, {c: 0 for c in CAUSES})
        if cause not in CAUSES:
            raise ValueError("Unrecognized authoritative cause: " + str(cause))
        counts[cause] += 1
        diss_workload[dissatisfaction.cell(row, 8).value] += 1
    for qa in sorted(set(workload) | set(diss_workload) | set(complaints)):
        monitor, dissatisfied, complaint = workload[qa], diss_workload[qa], complaints[qa]
        results["workload"][qa] = dict(monitor=monitor, dissatisfaction=dissatisfied, complaints=complaint, total=monitor+dissatisfied+complaint)
    for record in records:
        if record["date"] == current_date and record["veto"]:
            results["incidents"].append(dict(team=record["team"], name=record["name"], score=record["score"],
                category=record["category"], issue=record["issue"], source=f"quality-records.xlsx / 03月25日至今成绩!CB{record['row']},CM{record['row']}",
                action="修改联系方式前先核验交易截图或等效交易凭据；复核员工对身份核验与订单修改流程的掌握，复查后续执行情况。"))
    results["source_counts"] = dict(current=sum(r["date"] == current_date for r in records), cumulative=len(records), previous=sum(r["date"] == previous_date for r in records))
    return results


def chart(sheet, kind, title, min_col, max_col, min_row, max_row, label_col, anchor, percent=False):
    graph = LineChart() if kind == "line" else BarChart()
    graph.title = title
    graph.add_data(Reference(sheet, min_col=min_col, max_col=max_col, min_row=min_row, max_row=max_row), titles_from_data=True)
    graph.set_categories(Reference(sheet, min_col=label_col, min_row=min_row+1, max_row=max_row))
    graph.y_axis.title = "达成率" if percent else "均分 / 数量"
    if percent:
        graph.y_axis.numFmt = "0%"
    graph.width, graph.height = 23, 11
    sheet.add_chart(graph, anchor)


def create_report(materials, output):
    facts = load_facts(materials)
    book = openpyxl.Workbook()
    book.remove(book.active)
    for name, kind in [("日度排名", "daily"), ("累计排名", "cumulative")]:
        sheet = book.create_sheet(name)
        sheet.append(["所属主管", "TL&(A)TL", "Team平均分", "Team达成率", "质检抽测量", "组别接通量", "质检抽测率"])
        for team, item in sorted(facts[kind].items(), key=lambda p: (p[1]["attainment"], p[0])):
            sheet.append([item["manager"], team, item["mean"], item["attainment"], item["samples"], item["calls"], item["coverage"]])
        for row in range(2, sheet.max_row+1):
            for col in (4, 7):
                sheet.cell(row, col).number_format = "0.00%"
            sheet.cell(row, 3).number_format = "0.00"
        chart(sheet, "bar", name+"：组别均分", 3, 3, 1, sheet.max_row, 2, "I2")
    for name, kind, percent in [("均分对比", "mean_comparison", False), ("达成率对比", "attainment_comparison", True)]:
        sheet = book.create_sheet(name)
        sheet.append(["TL&(A)TL"] + facts["dates"])
        for team, values in sorted(facts[kind].items()):
            sheet.append([team]+[values[day] for day in facts["dates"]])
        for row in sheet.iter_rows(min_row=2, min_col=2):
            for cell in row:
                cell.number_format = "0.00%" if percent else "0.00"
        chart(sheet, "line", name, 2, 3, 1, sheet.max_row, 1, "F2", percent)
    sheet = book.create_sheet("不满意分布")
    sheet.append(["TL&(A)TL"]+CAUSES+["总计"])
    totals = Counter()
    for team, counts in sorted(facts["dissatisfaction"].items()):
        sheet.append([team]+[counts[c] for c in CAUSES]+[sum(counts.values())])
        totals.update(counts)
    sheet.append(["总计"]+[totals[c] for c in CAUSES]+[sum(totals.values())])
    sheet.append([])
    base = sheet.max_row+1
    sheet.append(["原因", "数量"])
    for cause in CAUSES:
        sheet.append([cause, totals[cause]])
    chart(sheet, "bar", "不满意原因分布（按分析日全量）", 2, 2, base, sheet.max_row, 1, "K2")
    sheet = book.create_sheet("重点案例")
    sheet.append(["TL&(A)TL", "组员姓名", "得分", "录音分类", "问题点", "证据来源", "提升建议"])
    for case in facts["incidents"]:
        sheet.append([case[k] for k in ("team", "name", "score", "category", "issue", "source", "action")])
    sheet = book.create_sheet("工作量")
    sheet.append(["QA", "监控条数", "不满意分析", "投诉分析", "总计"])
    for qa, item in facts["workload"].items():
        sheet.append([qa]+[item[k] for k in ("monitor", "dissatisfaction", "complaints", "total")])
    sheet = book.create_sheet("口径与来源")
    notes = [
        ["口径", "说明 / 复核路径"],
        ["报告日期", facts["dates"][-1]],
        ["达标", "最终得分CF>=80；平均分按每条已定稿成绩算术平均。致命违规保留明确零分，不把缺失适用分母改成N/A后丢弃该记录。"],
        ["覆盖范围", "日度取今日成绩；累计取03月25日至今成绩。累计表已包含今日记录，不能叠加。按监听日期，不按进线时间分期。"],
        ["周期对比", "累计记录按H监听日期及E团队分组，CF得分均值和及格条数/监听条数。K/L保持原始团队标识。"],
        ["抽测率", "质检抽测量/operations-context.xlsx接通量基数；日度基数是24、25日平均参考值，累计基数仅是业务给定参考基数，不等于有独立流水验证的二日总接通量。"],
        ["不满意", "quality-records.xlsx不满意分析!F,I,O：按分析日、团队、已定稿原因总结统计所有评价，保留有效和无效；不按客户评价时间或有效标签过滤。"],
        ["工作量", "当日监控按今日成绩!G统计；不满意按分析人H及分析日期I；投诉数量来自补充附件，仅代表已给定工作量。总工作量三者相加。"],
        ["重点案例", "致命违规按BV:CC是否Y识别；CB、CM为违规和备注依据。历史未核验不能写成已整改或已批准。"],
        ["附件来源局限", "operations-context.xlsx从专家报表提取固定运营前提，不是独立接通或投诉流水；不推导投诉责任结论或扩大统计期间。"],
    ]
    for note in notes:
        sheet.append(note)
    for ws in book:
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = f"A1:{openpyxl.utils.get_column_letter(ws.max_column)}{ws.max_row}"
        for cell in ws[1]:
            cell.fill = PatternFill("solid", fgColor="255C60")
            cell.font = Font(name="Microsoft YaHei", color="FFFFFF", bold=True)
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.font = Font(name="Microsoft YaHei", size=11)
                cell.alignment = Alignment(vertical="top", wrap_text=True)
        for col in range(1, ws.max_column+1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 20
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.page_setup.orientation = "landscape"
        ws.page_setup.paperSize = ws.PAPERSIZE_A3
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
    for col in ("E", "F", "G"):
        book["重点案例"].column_dimensions[col].width = 48
    book["重点案例"].row_dimensions[2].height = 100
    book["口径与来源"].column_dimensions["B"].width = 120
    for row in range(2, book["口径与来源"].max_row+1):
        book["口径与来源"].row_dimensions[row].height = 48
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    book.save(output)
    return facts
