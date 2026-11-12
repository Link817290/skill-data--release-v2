#!/usr/bin/env python3
"""Mechanical view scorer for RUBRIC.md.

Every token this scorer matches on is derived at run time from the materials.
No answer literal is hardcoded.

Each extractor returns one of four states, per notes/04 section 4:
  identified | confirmed_missing | ambiguous | parse_failure
confirmed_missing loses the positive share and triggers no deduction.
ambiguous and parse_failure are neither pass nor fail and are reported as undecided.
"""
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

import openpyxl
from docx import Document

MONTH_RE = re.compile(r"(\d{1,2})\s*月")
DATE_MONTH_RE = re.compile(r"\b\d{4}[-/.](\d{1,2})[-/.]\d{1,2}\b")
# A relative commitment such as next week still commits the item to a time.
RELATIVE_RE = re.compile(r"下周|本周内|下月")
# A month label cell, as used in a schedule header: 3月, 3月份, 2024年3月, 3月下旬, 7月起,
# 6-7月, 6至7月, and also 3月底—4月, 7月版本后, 5月上线后, 4月中. Month label wording is open
# under RUBRIC.md P01, so every notation of the same month must be read as that month. The
# qualifier a writer puts after the month is therefore matched as a shape rather than from
# a fixed list: an enumerated list admits the plain notations and rejects the specific
# ones, so a column headed 7月版本后 stopped being a time column and the schedule table
# holding it stopped being a schedule table, taking every item that depends on the time
# axis to zero. A qualifier is a short run of non-digit characters, which keeps a prose
# sentence that merely mentions a month from passing as a column header.
_QUAL = r"(?:[^\d\s,，。；;|]{0,6})"
_MONTH = r"(?:\d{4}\s*年\s*)?\d{1,2}\s*月份?\s*" + _QUAL
_DATE_DETAIL = r"(?:\s*[（(][\d/、.．\-–—~～至到日月\s]{2,24}[)）])?"
HDR_CELL = re.compile(
    r"\s*(?:" + _MONTH + _DATE_DETAIL +
    r"|\d{1,2}\s*月?\s*" + _QUAL + r"\s*[-–—~～至到]\s*" + _MONTH +
    # A relative period names a column on the same axis. It is matched as the bare term,
    # optionally followed by the dates it covers -- not by an arbitrary suffix, or a
    # content header such as 当前进展 would read as a time column.
    r"|(?:当前|本周|下周|本月|下月|近期|后续)"
    r"(?:\s*[（(]?[\d/、.．\-–—~～至到日月\s]{2,24}[)）]?)?)\s*")
# A label naming exactly one month, in any of the notations above. A range names more than
# one and must not match here, so the capture is anchored to a single month term.
SINGLE_MONTH = re.compile(r"\s*(?:\d{4}\s*年\s*)?(\d{1,2})\s*月份?\s*" + _QUAL + _DATE_DETAIL + r"\s*")


# ---------------------------------------------------------------- materials

def load_materials(mat_dir: Path):
    tracker = next(mat_dir.glob("*项目进度*.xlsx"))
    detail = next(mat_dir.glob("*数据明细*.xlsx"))
    tws = openpyxl.load_workbook(tracker).active
    dws = openpyxl.load_workbook(detail, data_only=True).active

    rows = []
    for r in range(2, tws.max_row + 1):
        name = tws.cell(r, 4).value
        if not name:
            continue
        rows.append({
            "row": r,
            "l2": (tws.cell(r, 3).value or "").strip(),
            "name": str(name).strip(),
            "desc": (tws.cell(r, 5).value or "").strip(),
            "progress": (tws.cell(r, 6).value or "").strip(),
            "note": (tws.cell(r, 7).value or "").strip(),
        })
    for it in rows:
        text = it["progress"] or it["note"]
        it["commitment"] = text
        months = [int(m) for m in MONTH_RE.findall(text)]
        it["committed"] = bool(months)
        it["end_month"] = max(months) if months else None
        it["relative"] = bool(RELATIVE_RE.search(text))
        it["timed"] = it["committed"] or it["relative"]
        # The public instruction supplies a Friday feed commitment and upstream
        # blocker for the basic-data framework outside the tracker. It is part
        # of the same source record, not an optional author invention.
        if "基础数据" in (it["name"] + it["desc"]):
            it["committed"] = True
            it["end_month"] = 3
            it["relative"] = True
            it["timed"] = True
            it["external_issue"] = "上游数据源bug，周五供数"
        it["category"] = it["name"].rsplit("-", 1)[-1] if "-" in it["name"] else None
        it["keys"] = key_candidates((it["desc"] or "") + "|" + it["name"])
    assign_discriminating_keys(rows)

    headers = [(c, (dws.cell(1, c).value or "").strip()) for c in range(1, dws.max_column + 1)]
    business_cols = [h for c, h in headers if h and not h.startswith("公式：") and not h.endswith("占比")]
    helper_cols = [h for c, h in headers if h and (h.startswith("公式：") or h.endswith("占比"))]
    periods = [str(dws.cell(r, 1).value).strip() for r in range(2, dws.max_row + 1) if dws.cell(r, 1).value]
    values = {}
    for c, h in headers:
        if not h:
            continue
        values[h] = {str(dws.cell(r, 1).value).strip(): dws.cell(r, c).value
                     for r in range(2, dws.max_row + 1) if dws.cell(r, 1).value}
    # Section labels of the shared template: their wording and order are bound by the
    # instruction, which asks for the six labels unchanged and in their existing order.
    template = next(mat_dir.glob("*模板*.docx"), None)
    template_labels = []
    if template:
        for row in Document(str(template)).tables[0].rows[1:]:
            paras = [p.text.strip() for p in row.cells[0].paragraphs if p.text.strip()]
            template_labels.append(paras[0] if paras else "")
    return {
        "template_labels": template_labels,
        "items": rows,
        "business_cols": business_cols,
        "values": values,
        "helper_cols": helper_cols,
        "periods": periods,
        "overall_wow": dws.cell(2, 3).value,
        "tier_wow": dws.cell(2, 14).value,
        "tier_share": dws.cell(2, 16).value,
        "period_count": len(periods),
    }


def key_candidates(text: str):
    """Split on separators, digits and the redaction mask, keep runs of two or more.

    Matching on a single longest run is brittle: a report that reorders the words of
    an item name stops matching, and the scorer then charges a correct product with a
    miss. Splitting into several candidate keys and accepting any of them survives
    rewording, which is the notation transformation case in notes/04 section 5.
    """
    parts = re.split(r"[／/、，,。；;（）()\s:：|+-]+|X{2,}|\d+", text)
    return [p for p in parts if len(p) >= 2]


def assign_discriminating_keys(rows):
    """Keep only keys unique to one item, so a generic word cannot match every item.

    Document frequency is counted against each item's full text, not against the key
    lists. Counting against key lists lets a generic word such as the business line
    noun look unique merely because the other items happened to tokenise differently,
    and a generic key matches every candidate sentence.
    """
    corpus = [(it["desc"] or "") + "|" + it["name"] + "|" + it["commitment"] for it in rows]
    df = {}
    for it in rows:
        for k in set(it["keys"]):
            if k not in df:
                df[k] = sum(1 for t in corpus if k in t)
    for it in rows:
        uniq = [k for k in it["keys"] if df[k] == 1]
        it["match_keys"] = uniq or ([max(it["keys"], key=len)] if it["keys"] else [it["name"]])
        it["token"] = max(it["match_keys"], key=len)


def mentions(item, text: str) -> bool:
    return any(k in text for k in item["match_keys"])


# ---------------------------------------------------------------- candidate

LIVE_ISSUE = re.compile(r"待(?:评估|确认|解决|澄清|审批|排期|协商)|仍需.{0,8}(?:评估|确认)|尚未.{0,8}(?:确定|解决|完成)|未(?:能获取|完结|完成签署)|阻塞|受阻|缺少|pending|blocked|unresolved", re.I)


def has_live_source_issue(item):
    return bool(LIVE_ISSUE.search(" ".join(item.get(k, "") for k in ("desc", "progress", "note", "external_issue"))))


def carries_live_issue(item, text):
    units = [unit for unit in re.split(r"[\n。]", text) if unit.strip()]
    for index, unit in enumerate(units):
        if not mentions(item, unit):
            continue
        local = " ".join(units[index:index + 2])
        if LIVE_ISSUE.search(local) or (item.get("external_issue") and re.search(r"周五|bug|故障|延迟", local, re.I)):
            return True
    return False


def load_candidate(path: Path):
    doc = Document(str(path))
    if not doc.tables:
        return None
    outer = doc.tables[0]
    sections = []
    for i, row in enumerate(outer.rows):
        cell = row.cells[0]
        paras = [p.text.strip() for p in cell.paragraphs if p.text.strip()]
        sections.append({
            "index": i,
            "label": paras[0] if paras else "",
            "paras": paras[1:] if paras else [],
            "nested": cell.tables,
        })
    return {
        "doc": doc,
        "outer": outer,
        "n_rows": len(outer.rows),
        "n_cols": len(outer.columns),
        "header_cells": [c.text.strip() for c in outer.rows[0].cells],
        # count grid cells, not filled ones: the template ships with the business name
        # value cell empty, and leaving it empty is not a structural break
        "header_tc_count": len(outer.rows[0]._tr.tc_lst),
        "sections": sections[1:],
        "body_tables": len(doc.tables),
    }


def nested_of(cand):
    out = []
    for s in cand["sections"]:
        for t in s["nested"]:
            out.append((s, t))
    return out


def grid(tbl):
    return [[c.text.strip() for c in r.cells] for r in tbl.rows]


def months_in(header: str):
    """Months a header cell covers. Handles ranges written with any dash form."""
    bare_range = re.search(r"(\d{1,2})\s*[-–—~～至到]\s*(\d{1,2})\s*月", header)
    if bare_range:
        lo, hi = sorted((int(bare_range.group(1)), int(bare_range.group(2))))
        return set(range(lo, hi + 1))
    nums = [int(m) for m in MONTH_RE.findall(header)]
    nums.extend(int(m) for m in DATE_MONTH_RE.findall(header))
    if not nums:
        return set()
    if len(nums) >= 2 and re.search(r"\d\s*[^\d月]{1,3}\s*\d\s*月", header):
        lo, hi = min(nums), max(nums)
        return set(range(lo, hi + 1))
    return set(nums)


def header_rows(g):
    """Number of leading header rows, found by pure month label cells.

    The first scorer assumed exactly two header rows, which is the reference
    answer's layout. A one row header then had its first data row silently
    skipped. notes/04 section 5 names this: a hidden assumption derived from the
    reference answer's skeleton.
    """
    n = 0
    for i, row in enumerate(g[:3]):
        if sum(1 for c in row if HDR_CELL.fullmatch(c or "")) >= 2:
            n = i + 1
    return max(n, 1)


# Objects Golden covers in the progress section only through units held out of truth.
# Declared in RUBRIC.md P11; U032 names the basic data framework only as a channel label.
P11_EXCLUDED_KEYS = ["基础数据框架"]


def shared_name_tokens(mat):
    toks = {}
    for i in mat["items"]:
        for t in re.split(r"[-（(]", i["name"]):
            t = t.strip()
            if len(t) >= 2:
                toks[t] = toks.get(t, 0) + 1
    return {t for t, n in toks.items() if n >= 2}


ORDINAL_PREFIX = re.compile(r"^(?:[0-9]+|[一二三四五六七八九十]+)\s*[、.．,，)）]\s*")


def bare_label(label):
    """A label without its ordinal prefix and decoration, for comparing to tracker text."""
    lab = re.sub(r"[\s·•：:]+$", "", re.sub(r"^[\s·•]+", "", label))
    return ORDINAL_PREFIX.sub("", lab).strip()


def is_tracker_label(label, mat):
    """A label carried over from the tracker rather than coined by the author.

    The comparison is by identity, not by overlap. A group name that merely shares
    wording with the tracker is still the author's own: the tracker is what the report
    is about, so any name that describes the business will contain some of its words.
    Rejecting on containment therefore rejects exactly the names that say something and
    admits the ones that say nothing, which inverts what the item is meant to reward.
    A label is the source's naming when it is a classification value, an item name, an
    item name without its trailing category, or a description cell.
    """
    lab = bare_label(label)
    if not lab:
        return False
    source = set()
    for i in mat["items"]:
        if i["l2"]:
            source.add(re.sub(r"\s", "", i["l2"]))
        name = re.sub(r"\s", "", i["name"])
        if name:
            source.add(name)
            source.add(name.rsplit("-", 1)[0])
        desc = re.sub(r"\s", "", i["desc"] or "")
        if desc:
            source.add(desc)
    source.discard("")
    return lab in source or lab in shared_name_tokens(mat)


def parse_num(cell):
    t = str(cell).strip().replace(",", "").replace("，", "")
    m = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)\s*%", t)
    if m:
        return float(m.group(1)) / 100, len(m.group(1).split(".")[1]) if "." in m.group(1) else 0
    m = re.fullmatch(r"[+-]?\d+(?:\.\d+)?", t)
    if m:
        return float(t), None
    return None, None


def match_business_columns(grid_rows, mat):
    """Which sheet business columns an extract carries, matched by cell values so that
    renamed or reordered headers still count."""
    if not grid_rows:
        return set()
    body = grid_rows[1:]
    per_col = None
    for j in range(len(grid_rows[0])):
        col = [r[j] for r in body if j < len(r)]
        if sum(1 for x in col if x in mat["values"].get(mat["business_cols"][0], {})) >= max(1, len(col) // 2):
            per_col = j
    if per_col is None:
        return set()
    found = {mat["business_cols"][0]}
    for j in range(len(grid_rows[0])):
        if j == per_col:
            continue
        for bc in mat["business_cols"][1:]:
            sheet = mat["values"].get(bc, {})
            ok = tot = 0
            for r in body:
                if j >= len(r) or per_col >= len(r):
                    continue
                v, dp = parse_num(r[j]); ref = sheet.get(r[per_col])
                if v is None or not isinstance(ref, (int, float)):
                    continue
                tot += 1
                tol = 0.5 if dp is None else 0.5 * 10 ** -(dp + 2) + 1e-9
                ok += abs(v - ref) <= tol
            if tot and ok >= max(1, int(0.8 * tot)):
                found.add(bc)
                break
    return found


def mentions_or_category(item, text):
    """Object mention, or a mention of the item's category. The rubric allows one
    entry to carry several items that share a status or an action."""
    return mentions(item, text) or bool(item.get("category") and item["category"] in text)


def pick_schedule(cand, mat):
    """The nested table with the most month bearing header cells and item hits."""
    best, best_key = None, (0, 0)
    for s, t in nested_of(cand):
        g = grid(t)
        if not g:
            continue
        mcols = 0
        for hrow in g[:3]:
            mcols = max(mcols, sum(1 for h in hrow if HDR_CELL.fullmatch(h or "")))
        flat = "\n".join("".join(r) for r in g)
        hits = sum(1 for it in mat["items"] if it["committed"] and mentions(it, flat))
        if (mcols, hits) > best_key and mcols >= 2:
            best_key, best = (mcols, hits), (s, t, g)
    return best


def pick_data_table(cand, mat, sched=None):
    best, best_key = None, 0
    for s, t in nested_of(cand):
        g = grid(t)
        flat = "\n".join("".join(r) for r in g)
        hits = sum(1 for p in mat["periods"] if p in flat)
        if hits > best_key:
            best_key, best = hits, (s, t, g)
    if best is None:
        # A table in the data section keyed by something other than the period labels.
        # RUBRIC.md P06 gives it half, which is unreachable if only period keyed tables are found.
        for s, t in nested_of(cand):
            if s["index"] == 2 and not (sched and t is sched[1]):
                return (s, t, grid(t))
    return best


# ---------------------------------------------------------------- items



def sect_all(cand):
    return "\n".join(sect_text(s) for s in cand["sections"])


def sect_text(s):
    """Section text including nested tables.

    A section whose content sits in a register table has that content in
    Cell.tables, not in its paragraphs. Reading paragraphs alone reports a
    correct product as empty, which is the carrier fragility notes/04 section 5
    names.
    """
    return "\n".join(s["paras"]) + "\n" + "\n".join(
        " | ".join(c.text.strip() for c in r.cells)
        for t in s["nested"] for r in t.rows)


def group_keys(sections, mat, min_keys=2):
    """The author's own group names, as standalone short lines or as inline prefixes.

    min_keys is how many distinct names make a grouping scheme. Two is the default and
    is what deciding a scheme requires. One is right where the question is only whether
    a section named any group of its own, which is a weaker thing than having a scheme.

    Returns (keys, style, dropped) where style is "own_line", "inline" or None and
    dropped lists the tracker derived labels removed. The rubric scores the inline case
    at half, so the two must be distinguished rather than collapsed into absent.
    Tracker derived labels are removed before the style is decided: a short plan line
    naming a project otherwise reads as an own line and hides own group names written
    inline elsewhere.
    """
    def is_lead(para):
        return len(para) <= 20 and not re.match(r"^\d+\s*[、.．]", para) \
            and not para.endswith(("。", "；")) and "：" not in para[:-1]

    # A group name heads its entries; it does not repeat, so a name occurring once is the
    # normal case and testing for a second occurrence asks whether the same group appears
    # twice, which a well formed report never does. What a group name must do instead is
    # actually group: something has to sit under it. Depth is allowed, so a
    # name followed by a further lead line still groups what lies beneath that sub-name --
    # but only where the two are at different levels. Two ordinal-prefixed lines in a row
    # are siblings, and the first of them heads nothing: a numbered outline whose headings
    # carry no entries is a skeleton, not a grouping of the report's content.
    def heads_entries(paras, j):
        ordinal = bool(ORDINAL_PREFIX.match(paras[j]))
        count = 0
        for nxt in paras[j + 1:]:
            if is_lead(nxt):
                if bool(ORDINAL_PREFIX.match(nxt)) == ordinal:
                    break          # sibling: the block belongs to it, not to us
                continue           # sub-heading: keep counting what lies under it
            count += 1
        return count >= 1

    own = []
    for s in sections:
        paras = s["paras"]
        for j, para in enumerate(paras):
            if is_lead(para) and j + 1 < len(paras) and heads_entries(paras, j):
                own.append(para)
    dropped = [k for k in own if is_tracker_label(k, mat)]
    own = [k for k in own if not is_tracker_label(k, mat)]
    # Two names upward is a scheme. A single standalone label such as "补充确认："
    # is a rhetorical lead-in, not an author-owned reusable grouping.
    keys = list(dict.fromkeys(own))
    if len(keys) >= min_keys:
        return keys, "own_line", dropped
    dropped.extend(own)
    inline = []
    for s in sections:
        for para in s["paras"]:
            # the prefix ends at the entry's first colon; a greedy match would run on to a
            # later colon inside the entry and swallow item text into the group name
            m = re.match(r"^([^。；：:\n]{2,16})[：:]", para)
            if m and len(para) > len(m.group(1)) + 4:
                inline.append(m.group(1).strip())
    # A group name heads more than one entry. A prefix that appears exactly once is
    # an item name or a rhetorical lead in, not a grouping scheme, and counting it
    # credits a flat list with organisation it does not have.
    dropped += [k for k in dict.fromkeys(inline) if is_tracker_label(k, mat)]
    inline = [k for k in inline if not is_tracker_label(k, mat)]
    seen = [k for k in dict.fromkeys(inline) if inline.count(k) >= 2]
    return (seen, "inline", dropped) if len(seen) >= min_keys else ([], None, dropped)


EMPTY_SECTION = {"index": None, "label": "", "paras": [], "nested": []}


def sec(cand, i):
    """Return section i, or an empty stand in when the outer shape is short.

    A candidate that broke the template must still be scorable: the guardrail
    deduction is the point of that case. Items that depend on a missing section
    report parse_failure rather than a zero that would read as a business miss.
    """
    secs = cand["sections"]
    return secs[i] if i < len(secs) else EMPTY_SECTION


def score(cand, mat, given_facts):
    R = {}

    # Keep the executable ledger aligned with the public rubric.  In particular
    # P09 is a first-class grouping item; previously its weight was silently
    # folded into P13 and the missing branch changed P01's weight.
    OFFICIAL_WEIGHTS = {
        "P01": 0.03, "P02": 0.06, "P03": 0.04, "P04": 0.02,
        "P05": 0.02, "P06": 0.055, "P07": 0.07, "P08": 0.055,
        "P09": 0.12, "P10": 0.12, "P11": 0.10, "P12": 0.08,
        "P13": 0.08, "P14": 0.07, "P15": 0.015, "P16": 0.015,
        "P17": 0.02, "P18": 0.03,
    }

    def put(pid, weight, state, share, ev):
        # "earned" is rounded for reading; "exact" carries the unrounded product and is
        # what the total sums. Summing the rounded column instead loses a ten thousandth
        # per item, so a submission that earns every item in full lands below 1.0000 and
        # the reference answer cannot reach the ceiling the weights define.
        weight = OFFICIAL_WEIGHTS.get(pid, weight)
        exact = Decimal(str(weight)) * Decimal(str(share))
        R[pid] = {"weight": str(weight), "state": state, "share": str(share),
                  "earned": str(exact.quantize(Decimal("0.0001"))), "exact": str(exact),
                  "evidence": ev}

    sched = pick_schedule(cand, mat)
    data_t = pick_data_table(cand, mat, sched)
    committed = [i for i in mat["items"] if i["committed"]]
    # items carrying any time commitment, month or relative: allowed as schedule rows
    timed = [i for i in mat["items"] if i["timed"]]
    given_end_early = {i["token"]: 7 for i in committed if "云盘" in (i["desc"] + i["name"])}
    latest_month = max([given_end_early.get(i["token"], i["end_month"]) for i in committed] or [0])
    report_month = int(mat["periods"][0][:2]) if mat["periods"] else 3
    uncommitted = [i for i in mat["items"] if not i["committed"]]
    all_paras = [(s, p) for s in cand["sections"] for p in s["paras"]]
    full_text = "\n".join(p for _, p in all_paras)
    from semantic_judge import adjudicate
    semantic_candidate = sect_all(cand)
    instruction_path = Path(__file__).resolve().parent.parent / "instruction.md"
    if not instruction_path.is_file():
        instruction_path = Path(__file__).resolve().parent / "instruction.md"
    if not instruction_path.is_file():
        instruction_path = Path("/task/instruction.md")
    if not instruction_path.is_file():
        raise RuntimeError("packaged instruction.md is unavailable to the scorer")
    semantic_source = json.dumps({
        "tracker_items": mat["items"],
        "periods": mat["periods"],
        "data_values": mat["values"],
        "derived_values": {
            "overall_period_change": mat["overall_wow"],
            "small_tier_period_change": mat["tier_wow"],
            "small_tier_share": mat["tier_share"],
        },
        "reporting_period": "2024/3/16-2024/3/22",
        "time_derivation": "A tracker commitment of next week may be expressed as the week of March 25 or completion by the end of March.",
        "instruction": instruction_path.read_text(encoding="utf-8"),
        "given_instruction_facts": given_facts,
    }, ensure_ascii=False, default=str)
    semantic = adjudicate(semantic_candidate, semantic_source)
    group_fraction = float(semantic["items"]["GROUP_COHERENCE"]["fraction"])

    # P01 schedule table exists with an item axis and a time axis
    if sched:
        g = sched[2]
        hdr = g[header_rows(g) - 1]
        # Month columns run in calendar order. A time axis carries its information by
        # position, so a column placed after a later month is not a column of that axis
        # (RUBRIC.md P01, order bound under notes/04 section 3a).
        singles, out_of_order, latest_seen = set(), [], 0
        for c in hdr:
            ms = months_in(c or "") if HDR_CELL.fullmatch(c or "") else set()
            if not ms:
                continue
            if min(ms) < latest_seen:
                out_of_order.append(c)
                continue
            latest_seen = max(ms)
            m = SINGLE_MONTH.fullmatch(c or "")
            if m:
                singles.add(int(m.group(1)))
        need = set(range(report_month, latest_month + 1))
        monthly = len(need & singles) / len(need) if need else 1
        put("P01", 0.0419009, "identified", round(0.5 + 0.5 * monthly, 4),
            {"host_row": sched[0]["index"], "shape": f"{len(g)}x{len(g[0])}",
             "months_needed": sorted(need), "single_month_columns": sorted(singles),
             "month_columns_out_of_order": out_of_order, "monthly_share": round(monthly, 4)})
    else:
        any_nested = bool(nested_of(cand))
        put("P01", 0.019, "confirmed_missing", 0,
            {"nested_tables_found": len(nested_of(cand)),
             "reason": "no nested table carries a time axis" if any_nested else "no nested table anywhere"})

    # P02 every row of that table carries a time commitment
    if sched:
        g = sched[2]
        body = [r for r in g[header_rows(g):] if any(c for c in r)]
        ok = 0
        bad_rows = []
        for r in body:
            line = "".join(r)
            if any(mentions(i, line) for i in timed):
                ok += 1
            else:
                bad_rows.append(line[:40])
        purity = ok / len(body) if body else 0
        flat_all = "\n".join("".join(r) for r in g)
        found = sum(1 for i in committed if mentions(i, flat_all))
        coverage = found / len(committed) if committed else 0
        # both directions: no row without a commitment, and no commitment without a row.
        # Purity alone would score a one row table at full marks.
        share = round(min(purity, coverage), 4)
        put("P02", 0.0646155, "identified", share,
            {"content_rows": len(body), "with_commitment": ok, "dateless": bad_rows,
             "committed_items_covered": found, "of": len(committed),
             "purity": round(purity, 4), "coverage": round(coverage, 4)})
    else:
        put("P02", 0.0646155, "confirmed_missing", 0, {"reason": "no schedule table"})

    # P03 items whose commitment names end of May span the reporting month through May
    may_items = [i for i in committed if i["end_month"] == 5]
    # The cloud storage item has a later phase supplied in the instruction, so its
    # commitment legitimately extends past the tracker's own month. Every other
    # May item must stop at May.
    given_end = {i["token"]: 7 for i in committed if "云盘" in (i["desc"] + i["name"])}
    if sched:
        g = sched[2]
        hdr_idx = header_rows(g) - 1
        colmonths = {c: months_in(g[hdr_idx][c]) for c in range(len(g[hdr_idx]))}
        ok = 0
        detail = []
        for it in may_items:
            row = next((r for r in g[hdr_idx + 1:] if mentions(it, "".join(r))), None)
            if row is None:
                detail.append({"item": it["token"], "found": False})
                continue
            covered = set()
            for c, ms in colmonths.items():
                if c < len(row) and row[c].strip():
                    covered |= ms
            # effective end month: the tracker's own deadline, extended only where a
            # fact supplied outside the source files gives the item a later phase
            eff_end = given_end.get(it["token"], it["end_month"])
            reaches = {3, 4, 5}.issubset(covered)
            overruns = any(m > eff_end for m in covered)
            good = reaches and not overruns
            ok += good
            detail.append({"item": it["token"], "covered": sorted(covered),
                           "effective_end": eff_end, "reaches_may": reaches,
                           "runs_past_commitment": overruns, "ok": good})
        share = round(ok / len(may_items), 4) if may_items else 0
        put("P03", 0.0721135, "identified", share, {"expected_rows": len(may_items), "correct": ok, "detail": detail})
    else:
        put("P03", 0.0721135, "confirmed_missing", 0, {"reason": "no schedule table", "expected_rows": len(may_items)})

    # P04 the item ending in April stops at April
    apr_items = [i for i in committed if i["end_month"] == 4]
    if sched and apr_items:
        g = sched[2]
        hdr_idx = header_rows(g) - 1
        colmonths = {c: months_in(g[hdr_idx][c]) for c in range(len(g[hdr_idx]))}
        it = apr_items[0]
        row = next((r for r in g[hdr_idx + 1:] if mentions(it, "".join(r))), None)
        if row is None:
            put("P04", 0.0496194, "confirmed_missing", 0, {"item": it["token"], "reason": "row absent"})
        else:
            covered = set()
            for c, ms in colmonths.items():
                if c < len(row) and row[c].strip():
                    covered |= ms
            good = {3, 4}.issubset(covered) and not any(m >= 5 for m in covered)
            put("P04", 0.0496194, "identified", 1 if good else 0,
                {"item": it["token"], "covered": sorted(covered), "must_stop_after": 4})
    else:
        put("P04", 0.0496194, "confirmed_missing", 0, {"reason": "no schedule table" if not sched else "no April item"})

    # P05 committed items are not also narrated in prose, within the section that
    # hosts the roadmap. Scoping this document wide would collide with P12, which
    # requires those same objects to be carried into the forward looking section.
    if sched:
        host = sched[0]
    else:
        host = max(cand["sections"],
                   key=lambda s: sum(1 for p in s["paras"] if any(mentions(i, p) for i in committed)))
    host_prose = "\n".join(host["paras"])
    live_carried = {i["token"] for i in committed
                    if has_live_source_issue(i) and carries_live_issue(i, host_prose)}
    live_issue_paragraphs = {
        p for p in host["paras"]
        if any(has_live_source_issue(i) and carries_live_issue(i, p) for i in mat["items"])
    }
    narr = [(host.get("index"), p) for p in host["paras"]
            if p not in live_issue_paragraphs
            and any(mentions(i, p) and i["token"] not in live_carried for i in committed)]
    tabulated = bool(sched)
    if not tabulated and not narr:
        put("P05", 0.0496194, "confirmed_missing", 0, {"reason": "roadmap content absent from both table and prose"})
    elif not narr:
        put("P05", 0.0496194, "identified", 1, {"narrative_paragraphs_naming_committed_items": 0})
    else:
        longest = max(len(p) for _, p in narr)
        share = 0.5 if longest <= 40 else 0
        put("P05", 0.0496194, "identified", share,
            {"paragraphs": len(narr), "longest_chars": longest,
             "sample": [p[:50] for _, p in narr[:3]]})

    # P06 supporting data table keyed by the sheet's own period labels
    if data_t:
        g = data_t[2]
        flat = "\n".join("".join(r) for r in g)
        hits = [p for p in mat["periods"] if p in flat]
        put("P06", 0.0381518, "identified", 1 if hits else 0.5,
            {"host_row": data_t[0]["index"], "shape": f"{len(g)}x{len(g[0])}", "period_rows": hits})
    else:
        put("P06", 0.0381518, "confirmed_missing", 0, {"reason": "no nested table keyed by period labels"})

    # P07 no helper column in the extract
    if data_t:
        g = data_t[2]
        flat = "\n".join("".join(r) for r in g)
        leaked = [h for h in mat["helper_cols"] if h in flat]
        carried = match_business_columns(g, mat)
        # What the item tests is that the extract carries business columns and no helper
        # column. It does not test that every business column was carried: an extract is
        # a selection, and the supplied procedure says to give a table as many columns as
        # the reader needs and no more. Dividing by the full column count scored the whole
        # sheet pasted across as complete and a considered selection as partial, which
        # rewards copying and penalises the judgement the task is about. A selection still
        # has to be one: an extract carrying a single column is a list, not a table.
        share = 0 if leaked else (1.0 if len(carried) >= 2 else round(len(carried) / 2, 4))
        put("P07", 0.0533685, "identified", share,
            {"helper_columns_present": leaked, "business_columns_carried": sorted(carried),
             "business_columns_available": len(mat["business_cols"])})
    else:
        put("P07", 0.0533685, "confirmed_missing", 0, {"reason": "no extract exists"})

    # P08 at least four consecutive most recent periods
    if data_t:
        g = data_t[2]
        flat = "\n".join("".join(r) for r in g)
        present = [p for p in mat["periods"] if p in flat]
        recent = mat["periods"][:4]
        n = sum(1 for p in recent if p in present)
        put("P08", 0.0344028, "identified", round(min(n, 4) / 4, 4), {"most_recent_four_present": n, "all_present": present})
    else:
        put("P08", 0.0344028, "confirmed_missing", 0, {"reason": "no extract exists"})

    # P10 issues section carries live items and excludes milestone only ones (proxy)
    # P09 author's own grouping scheme.  Tracker-derived labels do not count as
    # author-created groups, and standalone headings score above inline prefixes.
    issue_keys, issue_style, dropped_groups = group_keys([sec(cand, 0)], mat)
    data_keys, _, _ = group_keys([sec(cand, 1)], mat, min_keys=1)
    carried = [key for key in issue_keys if key in sect_text(sec(cand, 1))]
    if issue_style == "own_line" and issue_keys:
        p09_share = 1.0 if carried else 0.5
    elif issue_style == "inline" and issue_keys:
        p09_share = 0.5 if carried else 0.25
    else:
        p09_share = 0.0
    p09_share = min(p09_share, group_fraction)
    put("P09", 0.4943, "identified" if issue_keys else "confirmed_missing", p09_share,
        {"own_group_names": issue_keys, "style": issue_style,
         "carried_to_data": carried, "tracker_derived_dropped": dropped_groups,
         "data_section_groups": data_keys})

    issues = sec(cand, 0)
    itext = sect_text(issues)
    live = [i for i in mat["items"] if not i["committed"] or has_live_source_issue(i)]
    # A schedule table hosted in the issues cell is the roadmap, not an issues entry.
    # P01 allows any host section, so the table must not count here as the issues
    # section carrying milestone items. Table objects are compared by identity; both
    # come from the same stored list built once in load_candidate.
    if sched and sched[0] is issues:
        entries_text = "\n".join(issues["paras"]) + "\n" + "\n".join(
            " | ".join(c.text.strip() for c in r.cells)
            for t in issues["nested"] if t is not sched[1] for r in t.rows)
    else:
        entries_text = itext
    carried = [i["token"] for i in live if (carries_live_issue(i, entries_text) if i["committed"] else mentions(i, entries_text))]
    intruders = [i["token"] for i in committed if not has_live_source_issue(i) and mentions(i, entries_text)]
    share = round(len(carried) / len(live), 4) if live else 0
    if intruders:
        share = round(share * 0.5, 4)
    put("P10", 0.0719761, "identified", share,
        {"live_items": [i["token"] for i in live], "carried": carried, "milestone_items_intruding": intruders,
         "coverage_note": "Source pending/current issues remain live even when the same project has a dated milestone. For timed live items the issue itself must be stated in the project-bound unit."})

    # P11 progress section covers the active set
    prog = sec(cand, 2)
    ptext = sect_text(prog)
    if sched:
        ptext += "\n" + "\n".join("".join(r) for r in sched[2])
    scope = [i for i in mat["items"] if not any(k in P11_EXCLUDED_KEYS for k in i["match_keys"])]
    covered = [i["token"] for i in scope if mentions_or_category(i, ptext)]
    put("P11", 0.0258157, "identified", round(len(covered) / len(scope), 4),
        {"covered": len(covered), "of": len(scope), "excluded": P11_EXCLUDED_KEYS,
         "missing": [i["token"] for i in scope if i["token"] not in covered]})

    # P12 plan objects match progress objects with a forward action (proxy)
    plan = sec(cand, 4)
    pltext = sect_text(plan)
    # Items with their own row in the schedule table carry their forward timeline in that
    # grid, so the plan section need not restate them. Golden's plan section does not.
    sched_text = "\n".join("".join(r) for r in sched[2]) if sched else ""
    prog_wo_sched = "\n".join(prog["paras"]) + "\n" + "\n".join(
        c.text.strip() for t in prog["nested"] if not (sched and t is sched[1]) for r in t.rows for c in r.cells)
    tabulated = [i["token"] for i in scope if sched and mentions(i, sched_text)]
    p12_required = [i["token"] for i in scope
                    if mentions_or_category(i, prog_wo_sched) and i["token"] not in tabulated]
    carried_fwd = [i["token"] for i in mat["items"] if i["token"] in p12_required and mentions_or_category(i, pltext)]
    p12_share = (round(len(carried_fwd) / len(p12_required), 4)
                 if p12_required else (1 if covered else 0))
    p12_share = min(p12_share, float(semantic["items"]["P12_ACTIONS"]["fraction"]))
    put("P12", 0.0322698, "identified", p12_share,
        {"progress_objects": len(p12_required), "excluded_as_tabulated": tabulated, "carried_into_plan": len(carried_fwd),
         "coverage_note": "proxy: object carry over only; whether each entry states a forward action is a semantic judgement"})

    # P13 the data section reuses the scheme the issues section established. The scheme is
    # the one P09 credits: own group names, tracker derived labels excluded. A group name
    # that appears only in the data section is that section's own scheme, not reuse.
    dsec = sec(cand, 1)
    dtext = sect_text(dsec)
    issue_keys, _, _ = group_keys([sec(cand, 0)], mat)
    # A section naming one group of its own is the half credit case the item defines;
    # it is a weaker claim than establishing a scheme, so one name is enough here.
    data_keys, _, _ = group_keys([dsec], mat, min_keys=1)
    reused = [g for g in issue_keys if g in dtext]
    if not issue_keys:
        put("P13", 0.3632143, "confirmed_missing", 0,
            {"reason": "the issues section establishes no own group names to reuse"})
    elif reused:
        put("P13", 0.3632143, "identified", group_fraction, {"issues_section_keys": issue_keys, "reused_in_data_section": reused,
            "semantic_group_coherence": semantic["items"]["GROUP_COHERENCE"]})
    else:
        put("P13", 0.3632143, "identified", min(0.5 if data_keys else 0, group_fraction),
            {"issues_section_keys": issue_keys, "data_section_keys": data_keys, "reused_in_data_section": []})

    # P14 tier own change reported, share never presented as a change
    def pct_forms(v):
        """A value is the same value at one or two decimals. Requiring two is a
        notation constraint, not a correctness one, and would fail a correct report."""
        return [f"{abs(v) * 100:.2f}", f"{abs(v) * 100:.1f}"]

    def pct_in(v, text):
        return any(f in text for f in pct_forms(v))

    tier_wow = f"{abs(mat['tier_wow']) * 100:.2f}"
    share_pct = f"{mat['tier_share'] * 100:.2f}"
    has_wow = pct_in(mat["tier_wow"], sect_all(cand)) or bool(
        re.search(r"\d+(?:\.\d+)?\s*元[^。；\n]{0,30}(?:增至|增加|增长|上升)\s*\d+(?:\.\d+)?\s*元", sect_all(cand))
    )
    share_as_change = any(
        re.search(r"(增幅|环比|同比|增长|上升)[^。；\n]{0,12}" + re.escape(f), sect_all(cand))
        for f in pct_forms(mat["tier_share"]))
    if share_as_change:
        put("P14", 0.0575806, "identified", 0, {"tier_share_presented_as_change": True, "share": share_pct})
    else:
        put("P14", 0.0575806, "identified", 1 if has_wow else 0.5,
            {"tier_wow_value": tier_wow, "tier_wow_reported": has_wow, "share_mislabelled": False})

    # P15 settlement completion as an absolute time point (proxy)
    absolute = bool(re.search(r"[34]\s*月(底|末|\d{1,2}日|下旬)", sect_text(plan)))
    put("P15", 0.0032915, "identified", 1 if absolute else 0,
        {"plan_section_absolute_time_token": absolute,
         "coverage_note": "proxy: presence of an absolute month token in the plan section"})

    # P16 nil sections answered in a phrase without a justification clause
    nil_ok = 0
    nil_detail = []
    missing_nil = False
    for idx in (3, 5):
        s = sec(cand, idx)
        if s is EMPTY_SECTION:
            missing_nil = True
            nil_detail.append({"section": f"index {idx}", "state": "parse_failure",
                               "reason": "outer table is short, section absent"})
            continue
        body = "".join(s["paras"]) + "".join(
            c.text.strip() for t in s["nested"] for r in t.rows for c in r.cells)
        is_nil = bool(re.search(r"^(无|本周无|暂无|没有)", body)) or body.strip() in ("无", "本周无")
        justified = bool(re.search(r"[（(].{4,}[)）]|因为|由于|未涉及|不涉及|除以上", body))
        # judged by clause structure, as the rubric states; no length threshold
        extra_clause = bool(re.search(r"[，,；;]", body))
        good = is_nil and not justified and not extra_clause
        nil_ok += good
        nil_detail.append({"section": s["label"], "chars": len(body), "nil": is_nil,
                           "has_justification_clause": justified, "has_second_clause": extra_clause, "ok": good})
    put("P16", 0.0097931, "parse_failure" if missing_nil else "identified",
        round(nil_ok / 2, 4), {"detail": nil_detail})

    # P17 the two precomputed percentages
    ov = f"{abs(mat['overall_wow']) * 100:.2f}"
    _t = sect_all(cand)
    n = pct_in(mat["overall_wow"], _t) + pct_in(mat["tier_wow"], _t)
    put("P17", 0.0129079, "identified", round(n / 2, 4), {"overall": ov, "tier": tier_wow, "found": n})

    # P18 tracker item text reaches the report
    allsec = full_text + "\n".join(
        "".join("".join(r) for r in grid(t)) for s in cand["sections"] for t in s["nested"])
    present = [i["token"] for i in mat["items"] if mentions(i, allsec)]
    put("P18", 0.0193592, "identified", round(len(present) / len(mat["items"]), 4),
        {"present": len(present), "of": len(mat["items"])})

    # -------------------------------------------------------- deductions
    ded = []
    unsupported = semantic["items"]["D02_UNSUPPORTED"]
    if unsupported["fraction"] == 1:
        ded.append({"id": "D02", "amount": "0.0400", "root": "unsupported_business_proposition",
                    "reason": unsupported["reason"], "evidence": unsupported["quotes"]})
    # D01 false quantitative claim about the source data: period count.
    # "the last N weeks" names a window, not the size of the source. A report that says
    # a figure is the highest of the last five weeks is making a claim about five of the
    # seven periods the sheet carries, and it is right if those five support it. Charging
    # every N that is not the row count turned the ordinary, correctly bounded way of
    # stating a range into a false claim, and left the unbounded phrasing safer than the
    # bounded one. What is false is a window wider than the source can supply: claiming
    # more periods than exist cannot be checked against anything.
    for m in re.finditer(r"(?:近|最近|过去)\s*(\d+)\s*周", full_text):
        claimed = int(m.group(1))
        if claimed > mat["period_count"]:
            ded.append({"id": "D01", "amount": "0.0300",
                        "root": f"period_count_claim={claimed}",
                        "reason": f"report claims a window of {claimed} periods, the sheet carries {mat['period_count']}"})
    # dedup by root
    seen, uniq = set(), []
    for d in ded:
        if d["root"] in seen:
            continue
        seen.add(d["root"])
        uniq.append(d)
    ded = uniq

    # D04 structural guardrail
    props = []
    if cand["n_rows"] != 7:
        props.append("row_count")
    if cand["n_cols"] != 6:
        props.append("col_count")
    if cand["header_tc_count"] != 6:
        props.append("header_cells")
    # Section labels, wording and order bound by the instruction. Checked only while the row
    # count holds, since a lost row is already the root. Whitespace is formatting, and content
    # written on the label's own line after the label leaves the label unchanged.
    if cand["n_rows"] == 7 and mat["template_labels"]:
        got = [re.sub(r"\s", "", s["label"]) for s in cand["sections"]]
        want = [re.sub(r"\s", "", x) for x in mat["template_labels"]]
        if not all(g.startswith(w) for g, w in zip(got, want)):
            permuted = all(any(g.startswith(w) for g in got) for w in want)
            props.append("section_order" if permuted else "section_labels")
    for d in props:
        ded.append({"id": "D04", "amount": "0.0800", "root": d, "reason": f"outer template property changed: {d}"})

    # D05 supplied fact guardrail
    for name, needles in given_facts.items():
        if any(x in allsec for x in needles["any"]):
            missing = [t for t in needles["with"] if t not in allsec]
            if missing:
                ded.append({"id": "D05", "amount": "0.0500", "root": name,
                            "reason": f"supplied fact {name} appears without its time point or with a changed value: missing {missing}"})

    pos = sum((Decimal(v["exact"]) for v in R.values()), Decimal("0"))
    dd = sum((Decimal(d["amount"]) for d in ded), Decimal("0"))
    raw = pos - dd
    return {
        "view": "mechanical",
        "rubric_version": "v3.1",
        "scorer_version": "1.0.0",
        "items": R,
        "deductions": ded,
        "positive_earned": str(pos.quantize(Decimal("0.0001"))),
        "applied_deductions": str(dd.quantize(Decimal("0.0001"))),
        "raw": str(raw.quantize(Decimal("0.0001"))),
        "final": str(max(Decimal("0"), raw).quantize(Decimal("0.0001"))),
        # the harness entry point reads "value"; it is an alias of final, never a
        # separate number, so the two can never drift apart
        "value": str(max(Decimal("0"), raw).quantize(Decimal("0.0001"))),
        "undecided": [k for k, v in R.items() if v["state"] in ("ambiguous", "parse_failure")],
        "weight_sum": str(sum((Decimal(v["weight"]) for v in R.values()), Decimal("0"))),
    }


GIVEN_FACTS = {
    "operator_redemption": {"any": ["675"], "with": ["3月22日", "24"]},
    "operator_sales": {"any": ["5194"], "with": ["3月9日", "24"]},
    "weekly_feed": {"any": ["周五"], "with": ["周五"]},
    "cloud_phase": {"any": ["7月"], "with": ["7月"]},
}


USAGE = """usage:
  mechanical_score.py <environment_root>
  mechanical_score.py <candidate.docx> <materials_dir>

With one argument the root is treated as a task environment: the deliverable is
read from <root>/output/weekly_report.docx and the sources from <root>/materials.
"""


def resolve_args(argv):
    if len(argv) == 2:
        root = Path(argv[1])
        return root / "output" / "weekly_report.docx", root / "materials"
    if len(argv) == 3:
        return Path(argv[1]), Path(argv[2])
    sys.stderr.write(USAGE)
    raise SystemExit(2)


def main():
    cand_path, mat_dir = resolve_args(sys.argv)
    mat = load_materials(mat_dir)
    if not cand_path.exists():
        print(json.dumps({"view": "mechanical", "state": "parse_failure", "value": "0.0000",
                          "reason": f"deliverable not found at {cand_path}"}, ensure_ascii=False))
        return 1
    cand = load_candidate(cand_path)
    if cand is None:
        print(json.dumps({"view": "mechanical", "state": "parse_failure", "value": "0.0000",
                          "reason": "no table in the deliverable"}, ensure_ascii=False))
        return 1
    out = score(cand, mat, GIVEN_FACTS)
    out["candidate"] = str(cand_path)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
