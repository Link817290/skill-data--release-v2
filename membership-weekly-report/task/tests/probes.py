#!/usr/bin/env python3
"""Probe suite for RUBRIC.md, mechanical view.

Probe documents are built from the blank template plus material derived content.
None of them is derived from the reference answer's skeleton: notes/04 section 5
rules that a probe set built on the reference answer closes a loop in which the
criteria only recognise the reference answer's shape, the probes only exercise
that shape, and every probe passes while the extractor stays fragile.

Run: python3 task/tests/probes.py
Exit code is non zero if any assertion fails.
"""
import copy
import re
import subprocess
import sys
import json
from pathlib import Path

import openpyxl
from docx import Document
from docx.oxml.ns import qn

def _find(rel: str) -> Path:
    """Locate a package directory by searching upward instead of counting levels.

    The tests directory sits at a different depth in the working layout and in the
    delivered one, so a fixed parents[n] resolves to the wrong root in whichever layout
    it was not written for, and the suite then fails while looking for the materials.
    """
    here = Path(__file__).resolve()
    for base in here.parents:
        for candidate in (base / rel, base / "task" / rel):
            if candidate.exists():
                return candidate
    raise FileNotFoundError(rel)


ROOT = Path(__file__).resolve().parents[2]
MAT = _find("environment/workspace/materials")
TEMPLATE = MAT / "会员周报模板.docx"
import os
SCORER = Path(os.environ.get("MECH_SCORER", Path(__file__).resolve().parent / "mechanical_score.py"))
OUT = Path("/tmp/claude-10001/probe_docs")
OUT.mkdir(parents=True, exist_ok=True)

FAILURES = []
RESULTS = []


# ------------------------------------------------------------------ builders

def tracker():
    ws = openpyxl.load_workbook(next(MAT.glob("*项目进度*.xlsx"))).active
    rows = []
    for r in range(2, ws.max_row + 1):
        if not ws.cell(r, 4).value:
            continue
        rows.append({"name": str(ws.cell(r, 4).value).strip(),
                     "desc": (ws.cell(r, 5).value or "").strip(),
                     "prog": (ws.cell(r, 6).value or "").strip()})
    for it in rows:
        ms = [int(m) for m in re.findall(r"(\d{1,2})\s*月", it["prog"])]
        it["end"] = max(ms) if ms else None
    return rows


def detail_sheet():
    ws = openpyxl.load_workbook(next(MAT.glob("*数据明细*.xlsx")), data_only=True).active
    heads = [(ws.cell(1, c).value or "").strip() for c in range(1, ws.max_column + 1)]
    biz = [i for i, h in enumerate(heads) if h and not h.startswith("公式：") and not h.endswith("占比")]
    helper = [i for i, h in enumerate(heads) if h and (h.startswith("公式：") or h.endswith("占比"))]
    rows = []
    for r in range(2, ws.max_row + 1):
        if not ws.cell(r, 1).value:
            continue
        rows.append([ws.cell(r, c + 1).value for c in range(len(heads))])
    return heads, biz, helper, rows


def blank():
    return Document(str(TEMPLATE))


def set_section(doc, idx, lines):
    cell = doc.tables[0].rows[idx].cells[0]
    label = cell.paragraphs[0].text
    for p in cell.paragraphs[1:]:
        p._element.getparent().remove(p._element)
    cell.paragraphs[0].text = label
    for ln in lines:
        cell.add_paragraph(ln)


def add_nested(doc, idx, grid_rows):
    cell = doc.tables[0].rows[idx].cells[0]
    t = cell.add_table(rows=len(grid_rows), cols=len(grid_rows[0]))
    for i, row in enumerate(grid_rows):
        for j, v in enumerate(row):
            t.rows[i].cells[j].text = "" if v is None else str(v)
    return t


def schedule_grid(items, months, spans, cell_text=None, two_header=False):
    head = ["业务", "功能"] + [m["label"] for m in months]
    g = [["业务", "功能"] + ["预计上线时间及排期"] * len(months), head] if two_header else [head]
    for it in items:
        row = [it["name"].replace("专区项目-", ""), it["desc"] or it["name"]]
        for m in months:
            fill = spans(it, m)
            row.append((cell_text(it) if cell_text else it["prog"]) if fill else "")
        g.append(row)
    return g


def data_grid(heads, cols, rows, n):
    g = [[heads[c] for c in cols]]
    for r in rows[:n]:
        g.append([fmt(r[c]) for c in cols])
    return g


def fmt(v):
    if isinstance(v, float):
        return f"{v * 100:.2f}%" if abs(v) < 1 else f"{v:,.0f}"
    if isinstance(v, int):
        return f"{v:,}"
    return "" if v is None else str(v)


MONTHS_FINE = [{"label": f"{m}月", "months": {m}} for m in range(3, 13)]
# notation variants of the same one column per month axis
MONTHS_YEAR = [{"label": f"2024年{m}月", "months": {m}} for m in range(3, 13)]
MONTHS_FEN = [{"label": f"{m}月份", "months": {m}} for m in range(3, 13)]
# the same axis with April and May swapped: violates the calendar order P01 binds
MONTHS_SWAPPED = [MONTHS_FINE[0], MONTHS_FINE[2], MONTHS_FINE[1]] + MONTHS_FINE[3:]
MONTHS_COARSE = [{"label": "3月下旬", "months": {3}}, {"label": "4月", "months": {4}},
                 {"label": "5月", "months": {5}}, {"label": "6至7月", "months": {6, 7}}]


def span_correct(it, m):
    end = it["end"]
    if it["desc"].startswith("会员送"):
        end = 7
    return bool(m["months"] & set(range(3, (end or 3) + 1)))


def span_all_may(it, m):
    return bool(m["months"] & {3, 4, 5})


def build(name, *, months=MONTHS_FINE, spans=span_correct, weeks=4, cols="biz",
          groups=True, nil="无", pcts=("16.89%", "17.29%"), plan_abs=True,
          extra_lines=None, cell_text=None, decoy=False, nil_in_table=False, sched_n=None,
          two_header=False, settlement_row=False, merge_spans=False, plan_grouped=False,
          group_names=("合同与结算", "数据与运营", "产品交付"), rename_headers=False,
          progress_items="all", plan_items="all", subtitle="交叉运营合作概要",
          narrate_committed=False, period_keys=True, inline_groups=False, data_group_names=None,
          group_order=(0, 1, 2)):
    items = tracker()
    committed = [i for i in items if i["end"]]
    live = [i for i in items if not i["end"]]
    heads, biz, helper, rows = detail_sheet()
    doc = blank()

    framework = live[2]["prog"].split("2、", 1)
    framework_rows = [framework[0].strip()]
    if len(framework) == 2:
        framework_rows.append("2、" + framework[1].strip())
    issue_blocks = [
        [live[0]["prog"], live[1]["prog"]],
        framework_rows,
        [f"{live[3]['name']}：{live[3]['prog']}",
         next(f"{it['desc']}：{it['prog']}" for it in committed if it["desc"].startswith("会员送"))],
    ]
    issues = []
    for index in group_order:
        rows_for_group = issue_blocks[index]
        if not groups:
            issues.extend(rows_for_group)
        elif inline_groups:
            issues.extend(f"{group_names[index]}：{row}" for row in rows_for_group)
        else:
            issues.extend([group_names[index], *rows_for_group])
    if narrate_committed:
        # the roadmap written out again as narrative entries beside the schedule table
        issues += [f"{it['name']}（{it['desc']}）：{it['prog']}" for it in committed]
    set_section(doc, 1, issues)

    if decoy:
        add_nested(doc, 1, [["月份", "3月", "4月"], ["占位", "", ""]])
    sg = schedule_grid(committed[:sched_n] if sched_n else committed, months, spans, cell_text, two_header)
    if sched_n is None:
        sg.append(["数据基础", "基础数据框架"] +
                  ["周五供数" if 3 in m["months"] else "" for m in months])
    if settlement_row:
        # an item whose tracker entry commits it relatively (next week), placed with a date
        sg.append(["合作项目-三方合作", "2023年XX结算"] +
                  ["预计3月29日前完成" if m["months"] == {3} else "" for m in months])
    st = add_nested(doc, 1, sg)
    if merge_spans:
        for r in list(st.rows)[(2 if two_header else 1):]:
            idx = [j for j, c in enumerate(r.cells) if j >= 2 and c.text.strip()]
            if len(idx) >= 2 and idx == list(range(idx[0], idx[-1] + 1)):
                phrase = r.cells[idx[0]].text
                merged = r.cells[idx[0]].merge(r.cells[idx[-1]])
                merged.text = phrase

    dnames = data_group_names or group_names
    data_group = dnames[1] if len(dnames) > 1 else dnames[0]
    if inline_groups:
        dlines = [f"{data_group}：本周收入环比{pcts[0]}。", f"{data_group}：小会员收入环比{pcts[1]}。"]
    else:
        dlines = [f"本周收入环比{pcts[0]}。", f"小会员收入环比{pcts[1]}。"]
        if groups:
            dlines = [f"{data_group}数据"] + dlines
    if extra_lines:
        dlines += extra_lines
    set_section(doc, 2, dlines)
    use = {"biz": biz, "biz5": biz[:5]}.get(cols, biz + helper)
    dg = data_grid(heads, use, rows, weeks)
    if rename_headers:
        dg[0] = [f"列{j}" for j in range(len(dg[0]))]
    if not period_keys:
        for i in range(1, len(dg)):
            dg[i][0] = f"第{i}周"
    add_nested(doc, 2, dg)

    prog_items = {"all": items,
                  "live": [it for it in items if not it["end"]],
                  "live_no_framework": [it for it in items if not it["end"] and "基础数据框架" not in it["name"]]}[progress_items]
    set_section(doc, 3, [f"{it['desc'] or it['name']}：{it['prog'][:20]}" for it in prog_items])
    if nil_in_table:
        set_section(doc, 4, [])
        add_nested(doc, 4, [[nil]])
    else:
        set_section(doc, 4, [nil])
    plan = [f"{live[0]['name']}，继续督促", f"{live[1]['name']}，预计3月底可完成" if plan_abs
            else f"{live[1]['name']}，预计下周可完成"]
    if plan_grouped:
        plan += [f"{it['desc'] or it['name']}，跟进" for it in items[2:] if not it["end"]]
        plan += ["专区项目（游戏/云盘/个性化/阅读）：按计划推进"]
    elif plan_items == "live":
        plan += [f"{it['desc'] or it['name']}，跟进" for it in items[2:] if not it["end"]]
    else:
        plan += [f"{it['desc'] or it['name']}，跟进" for it in items[2:]]
    set_section(doc, 5, plan)
    set_section(doc, 6, [nil])

    p = OUT / f"{name}.docx"
    doc.save(str(p))
    return p


def relabel(src, name, fn):
    """Copy a probe document with its six section labels passed through fn."""
    doc = Document(str(src))
    rows = doc.tables[0].rows
    labels = fn([rows[i].cells[0].paragraphs[0].text for i in range(1, 7)])
    for i, lab in enumerate(labels, start=1):
        rows[i].cells[0].paragraphs[0].text = lab
    p = OUT / f"{name}.docx"
    doc.save(str(p))
    return p


def run(p):
    r = subprocess.run([sys.executable, str(SCORER), str(p), str(MAT)],
                       capture_output=True, text=True)
    if r.returncode != 0 and not r.stdout:
        return {"error": r.stderr[-500:]}
    return json.loads(r.stdout)


def check(label, cond, detail=""):
    RESULTS.append((label, "PASS" if cond else "FAIL", detail))
    if not cond:
        FAILURES.append(f"{label}: {detail}")


def share(res, pid):
    return float(res["items"][pid]["share"])


def dcount(res, did):
    return sum(1 for d in res["deductions"] if d["id"] == did)


# ------------------------------------------------------------------ probes

def main():
    base = run(build("full_correct"))
    check("full correct: weights sum to 1",
          abs(float(base["weight_sum"]) - 1) < 1e-9, base["weight_sum"])
    check("full correct: schedule and data tables both found",
          share(base, "P01") == 1 and share(base, "P06") == 1,
          f'P01={share(base,"P01")} P06={share(base,"P06")}')
    check("full correct: no helper column, four weeks",
          share(base, "P07") == 1 and share(base, "P08") == 1)
    check("full correct: spans correct on all five May items and the April item",
          share(base, "P03") == 1 and share(base, "P04") == 1,
          f'P03={share(base,"P03")} P04={share(base,"P04")}')
    check("full correct: no deduction fires on a clean product",
          not base["deductions"], str(base["deductions"]))
    check("full correct: nothing undecided", not base["undecided"], str(base["undecided"]))
    check("P10: a schedule table hosted in the issues section is not an issues entry",
          not base["items"]["P10"]["evidence"]["milestone_items_intruding"]
          and share(base, "P10") == 1.0,
          json.dumps(base["items"]["P10"]["evidence"], ensure_ascii=False)[:200])

    # partial: three of five May rows wrong, nothing else touched
    def span_short(it, m):
        if it["end"] == 5 and it["desc"] != tracker()[4]["desc"]:
            return bool(m["months"] & {3})
        return span_correct(it, m)
    part = run(build("partial", spans=span_short))
    check("partial: only the affected item loses share",
          share(part, "P03") < 1 and share(part, "P01") == 1 and share(part, "P06") == 1,
          f'P03={share(part,"P03")}')
    check("partial: a partial product gains no new deduction",
          len(part["deductions"]) == len(base["deductions"]), str(part["deductions"]))
    check("partial: raw and final are reported separately and are not floored to hide loss",
          float(part["raw"]) < float(base["raw"]) and float(part["final"]) == max(0.0, float(part["raw"])))

    # counterexample for the tightened P03: every row runs past its deadline
    def span_overrun(it, m):
        return bool(m["months"] & set(range(3, 8)))
    ov = run(build("overrun", spans=span_overrun))
    check("P03 counterexample: rows filled past their commitment are not correct",
          share(ov, "P03") < share(base, "P03") and share(ov, "P04") == 0,
          f'overrun P03={share(ov,"P03")} P04={share(ov,"P04")} vs clean P03={share(base,"P03")}')
    check("P03 counterexample: the cloud row with its supplied later phase stays correct",
          share(ov, "P03") > 0,
          f'overrun P03={share(ov,"P03")} (expected one row of five still correct)')

    # counterexample for the tightened P02: a table carrying one commitment of six
    one = run(build("one_row", sched_n=1))
    check("P02 counterexample: a one row schedule table cannot score full marks",
          share(one, "P02") <= round(1 / 6, 4) + 1e-9,
          f'one row P02={share(one,"P02")}')

    # carrier: merged span cells, which is how a real editor draws a span
    mg = run(build("merged_spans", merge_spans=True))
    check("carrier transformation: merged span cells score the same as repeated cells",
          all(share(mg, k) == share(base, k) for k in ("P02", "P03", "P04")),
          str({k: share(mg, k) for k in ("P02", "P03", "P04")}))

    # carrier: a two row header, the reference answer's layout, against a one row header
    th = run(build("two_header", two_header=True))
    check("carrier transformation: a two row header scores the same as a one row header",
          all(share(th, k) == share(base, k) for k in ("P01", "P02", "P03", "P04")),
          str({k: share(th, k) for k in ("P01", "P02", "P03", "P04")}))

    # allowed equivalence: a row for an item with a relative commitment
    rel = run(build("settlement_row", settlement_row=True))
    check("allowed equivalence: a row for an item with a relative commitment is not dateless",
          share(rel, "P02") == share(base, "P02") and share(rel, "P03") == share(base, "P03")
          and dcount(rel, "D03") == 0,
          f'P02={share(rel,"P02")} base={share(base,"P02")}')

    # nil returns judged by clause structure, not length
    npz = run(build("nil_phrase", nil="本周无团队管理问题需要汇报"))
    check("nil return: a plain nil sentence without a second clause is a phrase",
          share(npz, "P16") == share(base, "P16"), f'P16={share(npz,"P16")}')
    nj = run(build("nil_justified", nil="本周无（材料未涉及相关问题）"))
    check("nil return: a nil answer carrying a justification clause is not a phrase",
          share(nj, "P16") == 0, f'P16={share(nj,"P16")}')

    # allowed equivalence: one grouped plan line carrying several items forward
    pg = run(build("plan_grouped", plan_grouped=True))
    check("allowed equivalence: a grouped plan line carries every item in its category",
          share(pg, "P12") == share(base, "P12"), f'P12={share(pg,"P12")} base={share(base,"P12")}')

    # v3 corrections
    ca = run(build("coarse_axis", months=MONTHS_COARSE))
    check("P01: a time axis with a merged month bucket earns less than one column per month",
          share(ca, "P01") < share(base, "P01"), f'coarse P01={share(ca,"P01")} fine P01={share(base,"P01")}')
    rn = run(build("renamed_headers", rename_headers=True))
    check("P07: renamed extract headers still count when the cell values match the sheet",
          share(rn, "P07") == share(base, "P07"), f'renamed P07={share(rn,"P07")} base={share(base,"P07")}')
    b5 = run(build("five_columns", cols="biz5"))
    check("P07: an extract that selects five of the eleven business columns is still an extract",
          share(b5, "P07") == 1.0, f'P07={share(b5,"P07")}')
    # every label tracker derived: classification values plus a token shared by project names
    tg = run(build("tracker_group_names", group_names=("三方合作", "基础数据", "二方合作"), subtitle="专区项目"))
    check("P13: group names taken from the tracker establish no scheme to carry across sections",
          share(tg, "P13") == 0 and share(base, "P13") == 1, f'tracker names P13={share(tg,"P13")} own names P13={share(base,"P13")}')
    pl = run(build("progress_live_only", progress_items="live", plan_items="live"))
    check("P11: items carried as schedule rows count as covered wherever the table is hosted",
          share(pl, "P11") == share(base, "P11"), f'P11={share(pl,"P11")} base={share(base,"P11")}')
    check("P12: the plan need not restate items that carry their timeline in the schedule table",
          share(pl, "P12") == 1.0, f'P12={share(pl,"P12")}')
    nf = run(build("progress_no_framework", progress_items="live_no_framework", plan_items="live"))
    check("P11: an object Golden covers only through a held out unit is outside the denominator",
          share(nf, "P11") == share(base, "P11"), f'P11={share(nf,"P11")} base={share(base,"P11")}')

    # v3.1, notes/04 section 3a: a bound aspect loses share when violated, an open aspect does not
    sw = run(build("shuffled_axis", months=MONTHS_SWAPPED))
    check("binding violation P01 order: a month column out of calendar order is not its own column",
          share(sw, "P01") == 0.9 and all(share(sw, k) == share(base, k) for k in ("P02", "P03", "P04")),
          str({k: share(sw, k) for k in ("P01", "P02", "P03", "P04")}))
    for label, months in (("month_notation_year", MONTHS_YEAR), ("month_notation_fen", MONTHS_FEN)):
        mn = run(build(label, months=months))
        check(f"notation transformation: month labels written as {months[0]['label']} score the same",
              all(share(mn, k) == share(base, k) for k in ("P01", "P02", "P03", "P04")),
              str({k: share(mn, k) for k in ("P01", "P02", "P03", "P04")}))
    nr = run(build("narrated_roadmap", narrate_committed=True))
    check("binding violation P05: committed items narrated again beside the table lose P05",
          share(nr, "P05") < share(base, "P05") and share(nr, "P01") == share(base, "P01"),
          f'P05={share(nr,"P05")} base={share(base,"P05")}')
    uk = run(build("unkeyed_extract", period_keys=False))
    check("binding violation P06: an extract keyed by something other than the period labels earns half",
          share(uk, "P06") == 0.5 and share(uk, "P01") == share(base, "P01"), f'P06={share(uk,"P06")}')
    tw = run(build("two_weeks", weeks=2))
    check("binding violation P08: two periods earn half and the extract items keep their score",
          share(tw, "P08") == 0.5 and share(tw, "P06") == share(base, "P06") and share(tw, "P07") == share(base, "P07"),
          str({k: share(tw, k) for k in ("P06", "P07", "P08")}))
    ig = run(build("inline_groups", inline_groups=True))
    check("carrier transformation: group names written inline still establish the scheme",
          share(ig, "P13") == 1, json.dumps(ig["items"]["P13"]["evidence"], ensure_ascii=False)[:200])
    check("P13: inline group names from the issues section reused in the data section carry the scheme",
          share(ig, "P13") == 1, json.dumps(ig["items"]["P13"]["evidence"], ensure_ascii=False)[:200])
    dn = run(build("data_names_differ", data_group_names=("甲组",)))
    check("binding violation P13 wording: data section group names that differ from the issues section earn half",
          share(dn, "P13") == 0.5,
          f'P13={share(dn,"P13")} ' + json.dumps(dn["items"]["P13"]["evidence"], ensure_ascii=False)[:160])
    go = run(build("group_order", group_order=(2, 0, 1)))
    check("open aspect P09 order: reordering the groups changes nothing",
          share(go, "P13") == share(base, "P13"))
    full = build("full_correct")
    ls = run(relabel(full, "label_swap", lambda L: [L[1], L[0]] + L[2:]))
    check("binding violation G01 order: swapping two section labels fires D04 once",
          dcount(ls, "D04") == 1, str(ls["deductions"]))
    lr = run(relabel(full, "label_rename", lambda L: L[:2] + ["重点项目进展："] + L[3:]))
    check("binding violation G01 wording: renaming one section label fires D04 once",
          dcount(lr, "D04") == 1, str(lr["deductions"]))
    lw = run(relabel(full, "label_whitespace", lambda L: [L[0].replace(" & ", "&")] + L[1:]))
    check("open aspect G01 formatting: whitespace inside a section label is not a change",
          dcount(lw, "D04") == 0, str(lw["deductions"]))
    li = run(relabel(full, "label_inline_content", lambda L: L[:3] + [L[3] + "无"] + L[4:]))
    check("open aspect G01 layout: content written on the label's own line leaves the label unchanged",
          dcount(li, "D04") == 0, str(li["deductions"]))

    # transcription: everything as prose, no tables
    doc = blank()
    items = tracker()
    for idx, lines in ((1, [i["prog"] for i in items]), (2, [str(x) for x in detail_sheet()[3][0]]),
                       (3, [i["name"] for i in items]), (4, ["无"]), (5, [i["name"] for i in items]), (6, ["无"])):
        set_section(doc, idx, [l for l in lines if l])
    tp = OUT / "transcription.docx"; doc.save(str(tp))
    tr = run(tp)
    check("transcription: a keyword dump earns nothing in the shape cluster",
          all(share(tr, p) == 0 for p in ("P01", "P02", "P03", "P04", "P06", "P07", "P08")),
          str({p: share(tr, p) for p in ("P01", "P06", "P07")}))
    check("transcription: missing structure is confirmed_missing, not a deduction",
          tr["items"]["P01"]["state"] == "confirmed_missing" and dcount(tr, "D03") == 0)

    # false assertion
    fa = run(build("false_claim", extra_lines=["本周为近8周以来最高。"]))
    check("false assertion: D01 fires once", dcount(fa, "D01") == 1, str(fa["deductions"]))
    check("false assertion: unrelated positives keep their score",
          share(fa, "P01") == share(base, "P01") and share(fa, "P07") == share(base, "P07"))

    # dedup: the same false claim in two places
    dd = run(build("false_claim_twice", extra_lines=["本周为近8周以来最高。", "如前所述，近8周以来最高。"]))
    check("dedup: one root cause charged once however many times it is matched",
          dcount(dd, "D01") == 1, str(dd["deductions"]))

    # two genuinely independent harms
    ti = run(build("two_harms", extra_lines=["本周为近8周以来最高。", "过去12周持续增长。"]))
    check("two independent harms accumulate and are not capped",
          dcount(ti, "D01") == 2, str(ti["deductions"]))

    # legal equivalence: coarse month buckets, renamed and reordered columns
    heads, biz, helper, rows = detail_sheet()
    eq = run(build("equivalent", months=MONTHS_COARSE, cols="biz"))
    check("legal equivalence: coarsened time buckets score the same as fine ones",
          share(eq, "P03") == share(base, "P03") and share(eq, "P04") == share(base, "P04"),
          f'coarse P03={share(eq,"P03")} P04={share(eq,"P04")} vs fine {share(base,"P03")}/{share(base,"P04")}')

    # notation transformation: different fill token in every period cell
    nt = run(build("notation", cell_text=lambda it: "按期推进"))
    check("notation transformation: the fill token is not part of any criterion",
          share(nt, "P02") == share(base, "P02") and share(nt, "P03") == share(base, "P03"))

    # carrier transformation: the nil answer moved from a paragraph into a table cell
    ct = run(build("carrier", nil_in_table=True))
    check("carrier transformation: moving content between paragraph and table does not change P16",
          share(ct, "P16") == share(base, "P16"),
          f'table carrier={share(ct,"P16")} paragraph carrier={share(base,"P16")}')

    # same name distraction: a decoy month table placed before the real one
    dk = run(build("decoy", decoy=True))
    check("same name distraction: the locator still selects the authoritative table",
          share(dk, "P03") == share(base, "P03") and share(dk, "P04") == share(base, "P04"),
          f'with decoy P03={share(dk,"P03")} P04={share(dk,"P04")}')

    # helper column leak
    hl = run(build("helper_leak", cols="all"))
    check("helper column leak: P07 goes to zero and only P07",
          share(hl, "P07") == 0 and share(hl, "P06") == share(base, "P06"))

    # structural guardrail
    doc = blank()
    doc.tables[0]._element.remove(doc.tables[0].rows[6]._element)
    sp = OUT / "broken_shape.docx"; doc.save(str(sp))
    br = run(sp)
    check("guardrail: breaking the outer shape deducts and is not a missed positive",
          dcount(br, "D04") >= 1, str(br["deductions"]))

    # local parse failure does not spread
    doc = Document(str(build("full_correct")))
    cell = doc.tables[0].rows[2].cells[0]
    for t in list(cell.tables):
        t._element.getparent().remove(t._element)
    lp = OUT / "parse_local.docx"; doc.save(str(lp))
    pf = run(lp)
    check("local failure does not spread: the data cluster drops, the schedule cluster does not",
          share(pf, "P06") == 0 and share(pf, "P01") == share(base, "P01"),
          f'P06={share(pf,"P06")} P01={share(pf,"P01")}')

    # ---------------------------------------------------------------- report
    w = sum(1 for _, s, _ in RESULTS if s == "PASS")
    print(f"\n{'PROBE':70} RESULT")
    for label, st, detail in RESULTS:
        print(f"{label:70} {st}" + (f"   [{detail}]" if st == "FAIL" else ""))
    correct_but_different = ["equivalent", "notation", "carrier", "decoy", "merged_spans",
                             "two_header", "settlement_row", "nil_phrase", "plan_grouped",
                             "renamed_headers", "progress_live_only", "progress_no_framework",
                             "month_notation_year", "month_notation_fen", "group_order", "label_whitespace",
                             "label_inline_content"]
    wrong_content = ["false_claim", "false_claim_twice", "two_harms", "helper_leak",
                     "broken_shape", "transcription", "partial", "overrun", "one_row", "nil_justified",
                     "coarse_axis", "five_columns", "tracker_group_names"]
    print(f"\nsamples that are correct but written differently: {len(correct_but_different)}")
    print(f"samples whose content is wrong:                    {len(wrong_content)}")
    binding_violation = ["shuffled_axis", "narrated_roadmap", "unkeyed_extract", "two_weeks", "inline_groups",
                         "data_names_differ", "label_swap", "label_rename"]
    print(f"samples that violate a bound aspect:               {len(binding_violation)}")
    print(f"\n{w}/{len(RESULTS)} probes passed")
    if FAILURES:
        print("\nFAILURES:")
        for f in FAILURES:
            print("  -", f)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
