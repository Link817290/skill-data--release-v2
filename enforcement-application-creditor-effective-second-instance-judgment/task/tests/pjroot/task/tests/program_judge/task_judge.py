#!/usr/bin/env python3
"""Program Judge for 2-9 (application for enforcement, applicant side of a construction-payment case).

Three layers: extract_raw reads the DOCX or Markdown carrier; normalize registers one observation per
contracted item from bounded sentence windows inside registered sections; evaluate turns observations into
P/D decisions. Every term list, section alias, exclusion and shape baseline comes from rubric-contract.json.

Two item kinds beyond the shared proposition/shape/unsupported_specifics vocabulary:
  - "party_scope" (P14): the correct answer is that only one respondent paragraph exists anywhere in the
    filing; find_proposition's per-sentence exclusion cannot express "and nowhere else does a second,
    already-dismissed party appear", so this is a dedicated document-wide presence/absence check.
  - "formula_basis_sum" (P13): the delay-interest basis must equal a specific replayed sum of three other
    already-scored amounts, not just match a literal expected string, so the candidate's own stated number is
    captured and compared arithmetically (every participating amount must be traceable).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from legal_prose import (PLACEHOLDER, shape_chars, gap_only, with_document_derivations, Para, corpus_facts, derive_cn_numeral_dates, derive_period_deadlines, derive_task_totals,
                         find_proposition, lead_excluded, material_texts, nonspace, read_paragraphs, sections,
                         sentences, specifics, strip_authority_quotes, supported)
from program_judge_runtime import Locator, ProgramJudge, load_contract, sha256


PACKAGE_ROOT = Path(__file__).resolve().parents[3]
CANONICAL_CONTRACT = PACKAGE_ROOT / "rubric-contract.json"


def extract_raw(artifact: Path) -> dict:
    """Layer 1: visible paragraphs and table rows with structural paths; unreadable carriers are parse failures."""
    try:
        paras = read_paragraphs(artifact)
    except Exception as exc:  # corrupt zip, missing document part, undecodable text
        return {"artifact": artifact, "paras": None, "error": f"{type(exc).__name__}: {exc}"}
    return {"artifact": artifact, "paras": paras, "error": None}


def _locator(lid: str, artifact: Path, para: Para | None, field: str, observed: str) -> Locator:
    return Locator(locator_id=lid, artifact_path=str(artifact),
                   container_type="docx_paragraph" if artifact.suffix == ".docx" else "text_line",
                   container_path=para.path if para else "document", object_key=field, field=field,
                   observed=observed[:400], evidence_origin="submitted")


def _usable_sentences(p: Para, generic: list[str], item_exclude: list[str]) -> list[str]:
    own, _ = strip_authority_quotes(p.text)
    ex = re.compile("|".join(f"(?:{e})" for e in item_exclude + generic)) if item_exclude + generic else None
    return [s for s in sentences(own) if not (ex and ex.search(nonspace(s)))]


def _party_scope(paras: list[Para], m: dict, generic: list[str], lead: list[str]):
    """P14: exactly one respondent paragraph (B公司) and no already-dismissed party anywhere."""
    correct_re = re.compile(m["correct_pattern"])
    wrong_re = re.compile(m["wrong_pattern"])
    ex = re.compile("|".join(f"(?:{e})" for e in m.get("exclude", []) + generic)) if m.get("exclude", []) + generic else None
    correct_para, wrong_paras = None, []
    for p in paras:
        if lead_excluded(p, lead):
            continue
        own, _ = strip_authority_quotes(p.text)
        flat = nonspace(own)
        if ex and ex.search(flat):
            continue
        if correct_para is None and correct_re.search(flat):
            correct_para = p
        if wrong_re.search(flat):
            wrong_paras.append(p)
    return correct_para, wrong_paras


def _formula_basis_sum(paras: list[Para], m: dict, generic: list[str], lead: list[str]):
    """P13: the candidate's own stated delay-interest basis, replayed against three already-scored amounts."""
    context_re = re.compile(m["context_pattern"])
    basis_re = re.compile(m["basis_pattern"])
    rate_re = re.compile(m["rate_pattern"])
    # The delay-performance item is not always the first place the document says "迟延履行期间的债务利息":
    # the opening passage says when it starts running, and the operative item that carries the base and the
    # rate comes later. Taking the first context hit would score the narrative sentence and report "no basis
    # figure captured" while the real item sits a few paragraphs down, so every clause in scope is scanned
    # and the most complete one wins.
    best = None
    for p in paras:
        if lead_excluded(p, lead):
            continue
        for s in _usable_sentences(p, generic, m.get("exclude", [])):
            flat = nonspace(s)
            if not context_re.search(flat):
                continue
            basis_match = basis_re.search(flat)
            if basis_match is not None and m.get("basis_reconciles_fallback"):
                # The adjacency pattern grabs whichever figure sits next to "基数", and in a clause that
                # lists the addends inside a parenthesis that is the LAST addend, not the base
                # ("……8462529.72元（……、鉴定费283500元之和）为基数"). Where the captured figure does not
                # reconcile, fall through to the reconciliation scan below rather than reporting the
                # addend as the stated base.
                captured = next(g for g in basis_match.groups() if g)
                if abs(round(float(re.sub(r"[,，]", "", captured)), 2) - round(sum(m["terms"]), 2)) > m.get("tolerance", 0.5):
                    basis_match = None
            if basis_match is None and m.get("basis_reconciles_fallback") and "基数" in flat:
                # enforcement-application.md section 3 asks for the base to be written out so it can be
                # reconciled with the items it is built from. A submission that does exactly that -- names
                # the total and then lists the three awarded principals inside a parenthesis -- pushes the
                # figure and the word "基数" too far apart for an adjacency pattern to see.
                # Where a figure in this clause reconciles with the replayed sum, that figure is the base.
                expected = round(sum(m["terms"]), 2)
                for hit in re.finditer(r"(?<![\d.])(\d[\d,，]*(?:\.\d+)?)\s*元", flat):
                    value = float(re.sub(r"[,，]", "", hit.group(1)))
                    if abs(round(value, 2) - expected) <= m.get("tolerance", 0.5):
                        basis_match = hit
                        break
                if basis_match is None:
                    # nothing in the clause reconciles: fall back to the adjacency capture so the item is
                    # still scored against whatever figure the drafter actually offered as the base
                    basis_match = basis_re.search(flat)
            rate_ok = bool(rate_re.search(flat))
            rank = (1 if basis_match is not None else 0) + (1 if rate_ok else 0)
            if best is None or rank > best[0]:
                best = (rank, p, s, basis_match, rate_ok)
            if rank == 2:
                return p, s, basis_match, rate_ok
    if best is not None:
        return best[1], best[2], best[3], best[4]
    return None, None, None, False


_DATE_TOKEN = r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日"


def _date_chain(paras: list[Para], m: dict, generic: list[str], lead: list[str]):
    """P07: the two derived dates of the performance period, taken from ONE declared chain.

    relation-matrix U004 records the baseline for this period as an equivalent set, and the task skill
    declines to choose one: it requires a chain to be picked, stated and carried through. So the item
    scores the chain, not Golden's particular dates. Three chains are defensible on this record:
    service-day baseline (Golden), service-day baseline with the rest-day extension that 2024-11-03
    being a Sunday triggers, and the pronouncement-day baseline. What fails is mixing them, which is
    the skill's own failure mode ("some dates follow one baseline and some the other").

    Each role's pattern binds its date to its predicate by adjacency and refuses to step over another
    date on the way, so "the tenth day is 11-03 ... the period therefore expires 11-04" cannot be read
    as "11-03 is the expiry".
    """
    ex = re.compile("|".join(f"(?:{e})" for e in m.get("exclude", []) + generic)) if m.get("exclude", []) + generic else None
    cue = re.compile(m["extension_cue_pattern"])
    hits: dict[str, dict[str, tuple]] = {}
    for p in paras:
        if lead_excluded(p, lead):
            continue
        own, _ = strip_authority_quotes(p.text, keep_embedded=True)
        # The extension guard is paragraph-scoped on purpose: a drafter writes the nominal last day and
        # the extended one in two clauses of the same passage, and Chinese legal prose separates them
        # with a semicolon, which `sentences` treats as a break. Read sentence by sentence, the
        # intermediate step would look like a second baseline.
        flat_para = nonspace(own)
        cue_at = min((mt.start() for mt in cue.finditer(flat_para)), default=None)
        for s in sentences(own):
            flat = nonspace(s)
            if ex and ex.search(flat):
                continue
            offset = flat_para.find(flat)
            for chain in m["chains"]:
                for role in ("expiry", "accrual"):
                    mt = re.search(chain[f"{role}_pattern"], flat)
                    if not mt:
                        continue
                    if role == "expiry" and cue_at is not None and offset >= 0 and offset + mt.start() < cue_at:
                        # a day the same passage then extends is not the day the period expired
                        continue
                    hits.setdefault(chain["chain_id"], {}).setdefault(role, (p, s))
    return hits


def _provisional_cutoff(paras: list[Para], m: dict, generic: list[str], lead: list[str]):
    """P15: running money items are labelled provisional and name one real cut-off day.

    `unsupported-specifics-and-placeholders.md` puts the day a running amount is counted to in Class A:
    the applicant chooses it, the record was never going to hold it, and marking it open concedes a
    judgement rather than recording a gap. `enforcement-application.md` section 3 requires the label
    and the named date, and its self-check 6 requires every cut-off date in the document to be the same
    day. The date must also fall on or after the earliest defensible expiry day, because the
    first-instance judgment recites the plaintiff's own pre-judgment cut-off ("暂计至2024年1月15日"):
    transcribing that is copying the record, not fixing this filing's cut-off.
    """
    ex = re.compile("|".join(f"(?:{e})" for e in m.get("exclude", []) + generic)) if m.get("exclude", []) + generic else None
    marker = re.compile(m["marker_pattern"])
    cutoff = re.compile(m["cutoff_pattern"])
    floor = tuple(m["earliest_valid_cutoff"])
    found, stale, evidence, placeholder = set(), [], None, False
    for p in paras:
        if lead_excluded(p, lead):
            continue
        own, _ = strip_authority_quotes(p.text, keep_embedded=True)
        for s in sentences(own):
            flat = nonspace(s)
            if (ex and ex.search(flat)) or not marker.search(flat):
                continue
            if re.search(r"【[^】]*(?:待补|待核|待填写|待确认|占位)[^】]*】|\[[^]]*(?:待补|待核|待填写|待确认|占位)[^]]*]", flat):
                placeholder = True
                evidence = evidence or (p, s)
            for hit in cutoff.finditer(flat):
                d = re.search(_DATE_TOKEN, hit.group(0))
                if not d:
                    continue
                y, mo, day = (int(x) for x in re.findall(r"\d+", d.group(0)))
                if (y, mo, day) < floor:
                    stale.append((p, s, (y, mo, day)))
                    continue
                found.add((y, mo, day))
                evidence = evidence or (p, s)
    return found, stale, evidence, placeholder


def _filing_dates(paras: list[Para], m: dict) -> set:
    """The day the filing itself carries, in either Arabic or Chinese numerals.

    The genre fixes the provisional cut-off as the day the application is made: Golden's own note says
    so in words ("一般债务利息暂计算至执行申请日2024年11月4日") and its sign-off carries the same day.
    Reading both notations matters because Golden writes its sign-off in Chinese numerals while a
    submission written with python-docx writes Arabic ones; a decision that flipped on that would be a
    notation-dependent decision, which the judge never makes."""
    out = set()
    for p in paras:
        flat = nonspace(p.text)
        for pattern in m["filing_date_patterns"]:
            for hit in re.finditer(pattern, flat):
                token = hit.group(1)
                digits = re.findall(r"\d+", token)
                if len(digits) == 3:
                    out.add(tuple(int(x) for x in digits))
                    continue
                for y, mo, d in derive_cn_numeral_dates([token]):
                    out.add((int(y), mo, d))
    return out


def _class_a_placeholder(paras: list[Para], m: dict, lead: list[str]):
    """D08: a specific the record (or the applicant's own choice) fixes, delivered as a gap marker.

    `unsupported-specifics-and-placeholders.md` section 2 is explicit that this is the worse of the two
    placeholder errors, because it moves work from the drafter to the reader and gets the filing sent
    back. Only fields the record demonstrably fixes are listed here: the party block's registration
    identifiers, registered address and representative (both judgments' party blocks carry all three
    verbatim), the day the filing itself carries, and the day a running amount is counted to. Fields the
    record genuinely does not hold -- a telephone number, a service address, an amount that turns on a
    published rate series -- are Class B and are deliberately absent from the list.
    """
    field_re = re.compile(m["class_a_marker_pattern"])
    hits = []
    for p in paras:
        if lead_excluded(p, lead):
            continue
        flat = nonspace(p.text)
        for hit in field_re.finditer(flat):
            field = next((name for name, pat in m["field_labels"].items() if re.search(pat, hit.group(0))), "class_a")
            if field in m.get("source_complete_fields", []):
                hits.append((p, hit.group(0), field))
    return hits


def _unactionable_item(paras: list[Para], m: dict, lead: list[str]):
    """D09: an enumerated item an enforcement officer could not carry out today.

    SKILL.md self-check 4 and `enforcement-application.md` section 3 both put the same test on every
    item: a figure, or a base, a period and a rate standard. An item that carries neither is not an
    instruction to the officer, it is a note to the applicant.
    """
    lead_re = re.compile(m["item_lead_pattern"])
    amount_re = re.compile(m["actionable_amount_pattern"])
    formula_re = re.compile(m["actionable_formula_pattern"])
    # A numbered section heading is not an item. Some drafters number the block itself
    # ("二、申请执行事项"), and charging that as an unactionable claim is the anti-skeleton guard
    # inverted: a heading carries no request at all.
    heading_re = re.compile(m["heading_exclusion_pattern"])
    # A numbered sub-heading inside the applied-for block ("三、执行款收款信息" over the bank-account
    # lines) is a title, not a request. An operative item is a sentence; a title of at most
    # `short_heading_max_chars` characters after its number, with no clause punctuation, is skipped.
    short_heading = int(m.get("short_heading_max_chars", 0))
    # An attachment list that a drafter keeps inside the block ("五、附件" then "1. …判决书；") names
    # documents, not requests: from its heading on, nothing in the block is an operative item.
    attachment_re = re.compile(m["attachment_heading_pattern"]) if m.get("attachment_heading_pattern") else None
    hits = []
    for p in paras:
        if lead_excluded(p, lead):
            continue
        flat = nonspace(p.text)
        if attachment_re and attachment_re.match(flat):
            break
        if not lead_re.match(flat) or heading_re.match(flat):
            continue
        body = lead_re.sub("", flat, count=1)
        if short_heading and len(body) <= short_heading and not re.search(r"[。；，,;：:]", body):
            continue
        fee_pattern = m.get("non_independent_fee_pattern")
        if fee_pattern and re.fullmatch(fee_pattern, body):
            continue
        if amount_re.search(flat) or formula_re.search(flat):
            continue
        hits.append((p, flat, "unactionable_item"))
    return hits


def _missing_operative_item(paras: list[Para], m: dict, lead: list[str]):
    """D09 second arm: a money item of the title's operative part that the applied-for list does not request
    at all.

    The first arm charges an item the officer cannot carry out; this one charges an item that is not there.
    A filing that drops the court-cost claim, or half of the operative part, is not the same document as one
    that carries every claim. The list is closed and comes from the judgments' operative parts: the
    construction payment, its two-period interest, the deposit, the deposit interest, the apportioned court
    and appraisal fees, and the statutory delay interest. Each absent item is one damage instance; at most
    `max_missing_instances` are opened.
    """
    text = "".join(nonspace(p.text) for p in paras if not lead_excluded(p, lead))
    text = re.sub(r"(?<=\d)[,，](?=\d{3}(?!\d))", "", text)
    hits = []
    for req in m["required_items"]:
        if not re.search(req["pattern"], text):
            hits.append((paras[0], f"missing operative item: {req['id']}", f"missing:{req['id']}"))
            if len(hits) >= int(m.get("max_missing_instances", 2)):
                break
    return hits


def _carried_over_designation(paras: list[Para], m: dict, lead: list[str]):
    """D13: a party labelled with its role in the concluded action inside the enforcement filing.

    `enforcement-filing-baseline.md` section 2: in an application to the enforcement organ "each party carries
    its enforcement designation and nothing else. Do not carry over the designation from the concluded action,
    and do not add a second label in brackets." A caption line such as "申请执行人（一审原告、二审上诉人）" or
    "被执行人（一审被告、二审被上诉人）" is charged; Golden uses the enforcement designations only. One instance
    for the whole caption (one labelling decision, however many parties it is applied to).
    """
    pat = re.compile(m["designation_pattern"])
    hits = []
    for p in paras:
        if lead_excluded(p, lead):
            continue
        flat = nonspace(p.text)
        mt = pat.match(flat)
        if mt:
            hits.append((p, flat[:120], "carried_over_designation"))
    return hits


def _non_filing_content(paras: list[Para], m: dict, lead: list[str]):
    """D12: drafting notes to the handler carried inside the filing.

    `enforcement-application.md` fixes what the application may contain; a memo that announces itself as
    "起草备注，非正式申请内容，提交前请删去本段" (paragraphs after the signature), a checklist page
    "提交前请逐项核实，正式文本中可删除本页", or an instruction to the submitter inside a heading
    ("附件目录（提交时请按实际材料核对、补页码）") is content the court receives and the filing must
    not carry. Placeholder wording is stripped first (a marker telling the drafter what to fill in is a gap,
    not a memo), and the whole item is one damage instance however many paragraphs the memo runs to.
    """
    note_re = re.compile(m["note_pattern"])
    hits = []
    for p in paras:
        if lead_excluded(p, lead):
            continue
        own, _ = strip_authority_quotes(p.text)
        flat = PLACEHOLDER.sub("", nonspace(own))
        mt = note_re.search(flat)
        if mt:
            hits.append((p, flat[:200], "non_filing_content"))
    return hits


def _operative_restated(paras: list[Para], m: dict, lead: list[str]):
    """D10: the operative part of the title told twice, once as narrative and once as the list.

    `enforcement-filing-baseline.md` section 7 lists this under Do not, and `enforcement-application.md`
    section 1 removes the facts-and-reasons part that usually carries it. Naming the decision is not the
    error; reproducing the sums it awarded outside the applied-for list is.
    """
    cue = re.compile(m["decision_cue_pattern"])
    figures = [re.compile(f) for f in m["award_figure_patterns"]]
    # The item's own predicate says "outside the applied-for list", and an item of that list naturally
    # carries award figures and may name the decision they come from ("该两项系（2024）某民初71号民事判决
    # ……确定由B公司负担的部分"). Scanning the list too would charge the derivation the genre asks for.
    item_re = re.compile(m["item_lead_exclusion_pattern"])
    hits = []
    for p in paras:
        if lead_excluded(p, lead):
            continue
        flat = nonspace(p.text)
        if not cue.search(flat) or item_re.match(flat):
            continue
        found = sum(1 for f in figures if f.search(flat))
        if found >= m["min_award_figures"]:
            hits.append((p, flat[:160], "operative_restated"))
    return hits


_CN_NUM = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def _article_number(token: str) -> int | None:
    """"二百六十四" / "264" -> 264; None when the token is not a number this filing could cite."""
    if token.isdigit():
        return int(token)
    total, current = 0, 0
    for ch in token:
        if ch in _CN_NUM:
            current = _CN_NUM[ch]
        elif ch == "十":
            current = (current or 1) * 10
            total += current
            current = 0
        elif ch == "百":
            total += (current or 1) * 100
            current = 0
        else:
            return None
    return total + current


def _miscited_provision(paras: list[Para], m: dict, lead: list[str]):
    """D11: a provision of the Civil Procedure Law cited under the wrong article number.

    The record itself fixes the numbering: materials/1 (L331) cites 第二百六十四条 for delay interest, the 2023
    amendment in force since 2024-01-01. A filing that names the pre-2021 or 2021 number for the same rule
    (第二百五十三条 / 第二百六十条 for delay interest, 第二百三十九条 / 第二百四十六条 for the two-year period,
    第二百二十四条 / 第二百三十一条 for enforcement jurisdiction) sends the officer to the wrong article; an
    accurate citation is not charged and a mis-citation is. The table is closed: a
    topic is charged only when the sentence cites the statute, the topic word stands within `window`
    characters of an article number, and no article number in the sentence is in the topic's allowed set.
    Other statutes (诉讼费用交纳办法, 法释) are never read. One instance per topic, at most `max_instances`.
    """
    statute = re.compile(m["statute_pattern"])
    article = re.compile(m["article_pattern"])
    window = int(m.get("window", 60))
    topics = [(t["id"], re.compile(t["topic_pattern"]), set(t["allowed"])) for t in m["topics"]]
    hits, seen = [], set()
    for p in paras:
        if lead_excluded(p, lead):
            continue
        own, _ = strip_authority_quotes(p.text, keep_embedded=True)
        for s in sentences(own):
            flat = nonspace(s)
            if not statute.search(flat):
                continue
            cited = [(mt.start(), _article_number(mt.group(1))) for mt in article.finditer(flat)]
            cited = [(pos, n) for pos, n in cited if n]
            if not cited:
                continue
            numbers = {n for _, n in cited}
            for tid, topic_re, allowed in topics:
                if tid in seen or numbers & allowed:
                    continue
                near = any(topic_re.search(flat[max(0, pos - window):pos + window]) for pos, _ in cited)
                if near:
                    seen.add(tid)
                    hits.append((p, flat[:200], tid))
                    if len(hits) >= int(m.get("max_instances", 2)):
                        return hits
    return hits


def normalize(raw: dict, judge: ProgramJudge) -> dict:
    """Layer 2: one registered observation per P and per D scan, plus per-occurrence observations for D hits."""
    c = judge.contract
    art = raw["artifact"]
    obs: dict = {"positive": {}, "deduction": {}}
    doc_loc = _locator("doc", art, None, "document", raw["error"] or "document")
    if raw["paras"] is None:
        for item in c["positive_items"]:
            obs["positive"][item["id"]] = (judge.observe(f"{item['id']}-parse", "parse_failure", [doc_loc]), None)
        for item in c["deduction_items"]:
            obs["deduction"][item["id"]] = (judge.observe(f"{item['id']}-parse", "parse_failure", [doc_loc]), [])
        return obs
    paras = [p for p in raw["paras"] if nonspace(p.text)]
    secs = sections(paras, c["task_matching"]["section_headings"],
                    c["task_matching"].get("heading_suffix_tolerance", 1))
    if secs is not None and secs.get("__head__"):
        # A caption may put each party's credit code, address and representative on lines of their own; those
        # continuation lines belong to the party line above them, so they are joined before matching.
        merged: list[Para] = []
        # A caption may also put the designation alone on one line and the name, code and address on the
        # next ("被执行人（一审被告、二审被上诉人）" / "B公司，统一社会信用代码：…"); the name line belongs to
        # the designation line above it, so it is joined the same way.
        designation_only = re.compile(r"^(?:申请执行人|被申请执行人|被执行人|申请人|被申请人)(?:[（(][^）)]{0,24}[）)])?[：:]?$")
        for p in secs["__head__"]:
            flat = nonspace(p.text)
            if merged and (re.match(r"^(统一社会信用代码|住所地?|住址|法定代表人|负责人|委托(诉讼)?代理人|联系电话|地址)", flat)
                           or designation_only.match(nonspace(merged[-1].text))):
                merged[-1] = Para(merged[-1].index, merged[-1].path, merged[-1].text + "，" + p.text)
            else:
                merged.append(p)
        secs["__head__"] = merged
    if secs is not None and secs.get("申请执行事项"):
        # Sub-items "（1）/(1)/①/1." written under a lead line that ends with "：" are one operative claim, not
        # several. A drafter may write the two-period interest formula as a lead plus two sub-lines; read line
        # by line, P09 would never see both periods in one window and D09 would count each sub-line as a
        # separate item. The sub-lines are joined onto their lead paragraph before any item reads the section.
        # A closing line that applies one standard to every sub-item ("以上均按同期贷款市场报价利率计算")
        # is the tail of the same claim, exactly as a shared rate clause is.
        sub = re.compile(r"^(?:[（(]\d{1,2}[)）]|[①②③④⑤⑥⑦⑧⑨]|\d{1,2}[.．、](?!\d))")
        tail = re.compile(r"^(?:以上|上述|前述)[^。；，]{0,4}(?:均|皆)")
        merged2, open_lead, in_sub = [], False, False
        for p in secs["申请执行事项"]:
            flat = nonspace(p.text)
            if merged2 and open_lead and (sub.match(flat) or (in_sub and tail.match(flat))):
                merged2[-1] = Para(merged2[-1].index, merged2[-1].path, merged2[-1].text + p.text)
                in_sub = bool(sub.match(flat))
                continue
            merged2.append(p)
            open_lead = flat.endswith(("：", ":"))
            in_sub = False
        secs["申请执行事项"] = merged2
    generic = c["task_matching"]["generic_exclusions"]
    lead = c["task_matching"]["paragraph_lead_exclusions"]

    def scope(names, any_present=False):
        # Location is resolved one section name at a time (see legal_prose.sections): a name that could not be
        # located is absent from the split, so only the items bound to it lose credit. Falling back to the whole
        # document would turn an unresolvable location into free credit.
        if secs is None:
            return None
        chosen = []
        for n in names:
            if n not in secs:
                if any_present:
                    # An optional block (e.g. a drafter's own 事实与理由 section) that this carrier does not have
                    # contributes nothing; the item is unlocatable only when none of its named blocks exists.
                    continue
                return None
            chosen += secs[n]
        if any_present and not any(n in secs for n in names):
            return None
        return chosen

    for item in c["positive_items"]:
        m = item["match"]
        kind = m.get("kind")
        if kind == "party_scope":
            region = scope(m.get("sections", []))
            if region is None:
                obs["positive"][item["id"]] = (judge.observe(f"{item['id']}-obs", "parse_failure", [doc_loc]), None)
                continue
            correct_para, wrong_paras = _party_scope(region, m, generic, lead)
            if correct_para is None and not wrong_paras:
                loc = _locator(f"{item['id']}-scope", art, None, item["object_key"], "no respondent paragraph found")
                obs["positive"][item["id"]] = (judge.observe(f"{item['id']}-obs", "confirmed_missing", [loc]),
                                               ("missing", None, None))
                continue
            locs = []
            if correct_para is not None:
                locs.append(_locator(f"{item['id']}-correct", art, correct_para, item["object_key"], correct_para.text))
            for n, wp in enumerate(wrong_paras):
                locs.append(_locator(f"{item['id']}-wrong{n}", art, wp, item["object_key"], wp.text))
            obs["positive"][item["id"]] = (judge.observe(f"{item['id']}-obs", "identified", locs),
                                           ("identified", correct_para, wrong_paras))
            continue
        if kind == "date_chain":
            region = scope(m["sections"], m.get("sections_mode") == "any_present")
            if region is None:
                obs["positive"][item["id"]] = (judge.observe(f"{item['id']}-obs", "parse_failure", [doc_loc]), None)
                continue
            hits = _date_chain(region, m, generic, lead)
            if not hits:
                loc = _locator(f"{item['id']}-scope", art, None, item["object_key"], "no derived period date found")
                obs["positive"][item["id"]] = (judge.observe(f"{item['id']}-obs", "confirmed_missing", [loc]), ("missing", {}))
                continue
            locs = [_locator(f"{item['id']}-{cid}-{role}", art, pair[0], item["object_key"], pair[1])
                    for cid, roles in sorted(hits.items()) for role, pair in sorted(roles.items())]
            obs["positive"][item["id"]] = (judge.observe(f"{item['id']}-obs", "identified", locs), ("identified", hits))
            continue
        if kind == "provisional_cutoff":
            region = scope(m["sections"], m.get("sections_mode") == "any_present")
            if region is None:
                obs["positive"][item["id"]] = (judge.observe(f"{item['id']}-obs", "parse_failure", [doc_loc]), None)
                continue
            found, stale, evidence, placeholder = _provisional_cutoff(region, m, generic, lead)
            # The filing's own date is a document-level fact: it lives in the sign-off, which is not
            # part of the region where the running items are. Searching the whole document for it keeps
            # the cut-off scope tight while still reading the sign-off.
            filing = _filing_dates(paras, m)
            if found and filing and not (found & filing):
                loc = _locator(f"{item['id']}-mismatch", art, evidence[0], item["object_key"],
                               f"cut-off {sorted(found)} vs filing date {sorted(filing)}")
                obs["positive"][item["id"]] = (judge.observe(f"{item['id']}-obs", "identified", [loc]),
                                               ("identified", set()))
                continue
            if found and not filing:
                loc = _locator(f"{item['id']}-nodate", art, evidence[0], item["object_key"],
                               "the filing carries no date of its own")
                obs["positive"][item["id"]] = (judge.observe(f"{item['id']}-obs", "identified", [loc]),
                                               ("identified", set()))
                continue
            if not found and not placeholder:
                observed = ("only pre-adjudication cut-off dates: "
                            + "; ".join(f"{y}-{mo}-{d}" for _p, _s, (y, mo, d) in stale)) if stale else "no provisional cut-off date"
                loc = _locator(f"{item['id']}-scope", art, stale[0][0] if stale else None, item["object_key"], observed)
                obs["positive"][item["id"]] = (judge.observe(f"{item['id']}-obs", "confirmed_missing", [loc]), ("missing", found))
                continue
            loc = _locator(f"{item['id']}-ev", art, evidence[0], item["object_key"], evidence[1])
            obs["positive"][item["id"]] = (judge.observe(f"{item['id']}-obs", "identified", [loc]), ("identified", found or {"placeholder"}))
            continue
        if kind == "formula_basis_sum":
            region = scope(m["sections"])
            if region is None:
                obs["positive"][item["id"]] = (judge.observe(f"{item['id']}-obs", "parse_failure", [doc_loc]), None)
                continue
            p, s, basis_match, rate_ok = _formula_basis_sum(region, m, generic, lead)
            if p is None:
                loc = _locator(f"{item['id']}-scope", art, None, item["object_key"], "no delay-interest clause found")
                obs["positive"][item["id"]] = (judge.observe(f"{item['id']}-obs", "confirmed_missing", [loc]),
                                               ("missing", None, None, None))
                continue
            loc = _locator(f"{item['id']}-ev", art, p, item["object_key"], s)
            obs["positive"][item["id"]] = (judge.observe(f"{item['id']}-obs", "identified", [loc]),
                                           ("identified", basis_match, rate_ok, s))
            continue
        # standard proposition kind
        results = []
        failed = False
        for prop in m["propositions"]:
            region = scope(prop["sections"], prop.get("sections_mode") == "any_present")
            if region is None:
                failed = True
                break
            hits, total, ev = find_proposition(region, prop["groups"], prop.get("exclude", []), generic,
                                               None, prop["max_chars"], prop["sentence_window"], lead)
            results.append((hits, total, ev))
        if failed:
            oid = judge.observe(f"{item['id']}-obs", "parse_failure", [doc_loc])
            obs["positive"][item["id"]] = (oid, None)
            continue
        complete = [r for r in results if r[0] == r[1]]
        evidence = [r[2] for r in results if r[2] is not None]
        if not evidence:
            loc = _locator(f"{item['id']}-scope", art, None, item["object_key"], "no matching proposition in scope")
            obs["positive"][item["id"]] = (judge.observe(f"{item['id']}-obs", "confirmed_missing", [loc]), results)
            continue
        locs = [_locator(f"{item['id']}-ev{n}", art, p, item["object_key"], w) for n, (p, w) in enumerate(evidence)]
        obs["positive"][item["id"]] = (judge.observe(f"{item['id']}-obs", "identified", locs), (results, complete))

    source_texts = material_texts(PACKAGE_ROOT / "materials") + [(PACKAGE_ROOT / "instruction.md").read_text(encoding="utf-8")]
    facts = corpus_facts(source_texts)
    # Order matters, and getting it wrong is a false-positive generator.
    # The public counting-rule dates have to enter the corpus BEFORE with_document_derivations runs:
    # a submission that writes "the tenth day is 11-03, a Sunday, so the period expires 11-04 and the
    # delay runs from 11-05" derives 11-05 from 11-04, and 11-04 only exists because of the counting
    # rule. Running the in-document pass first leaves it with the service date as its only anchor, so
    # every date beyond the first hop reads as fabricated.
    dates, amounts, ids = facts[0], facts[1], facts[2]
    periods = facts[3] if len(facts) > 3 else set()
    dates = dates | derive_cn_numeral_dates(source_texts)
    dates = dates | derive_period_deadlines(dates)
    amounts = amounts | derive_task_totals(amounts)
    facts = with_document_derivations((dates, amounts, ids, periods), paras)
    dates, amounts, ids = facts[0], facts[1], facts[2]
    periods = facts[3] if len(facts) > 3 else set()
    facts = (dates, amounts, ids, periods)

    for item in c["deduction_items"]:
        m = item["match"]
        occ = []
        if m["kind"] == "semantic_source_support":
            obs["deduction"][item["id"]] = (judge.observe(f"{item['id']}-scan", "identified", [doc_loc]), [])
            continue
        if m["kind"] in ("class_a_placeholder", "unactionable_item", "operative_restated", "miscited_provision",
                         "non_filing_content", "carried_over_designation"):
            region = scope(m.get("sections", ["__document__"]), m.get("sections_mode") == "any_present") \
                if m.get("sections") else paras
            if region is None:
                obs["deduction"][item["id"]] = (judge.observe(f"{item['id']}-scan", "parse_failure", [doc_loc]), [])
                continue
            scan = judge.observe(f"{item['id']}-scan", "identified",
                                 [_locator(f"{item['id']}-scope", art, region[0] if region else None,
                                           item["object_key"], "scanned")])
            if m["kind"] == "operative_restated" and secs is not None and secs.get("申请执行事项"):
                # The item's own scope is "any paragraph outside the applied-for list". The list's closing
                # note -- the reconciliation of the delay-interest base with the items it is built from, which
                # enforcement-application.md section 3 asks for ("write the base out so it can be reconciled")
                # -- sits inside the block and carries the same award figures next to "生效判决确定的".
                # Paragraphs of the applied-for block are left to D03/D09; D10 reads the rest of the document.
                inside = {q.index for q in secs["申请执行事项"]}
                region = [q for q in region if q.index not in inside]
            fn = {"class_a_placeholder": _class_a_placeholder,
                  "unactionable_item": _unactionable_item,
                  "operative_restated": _operative_restated,
                  "miscited_provision": _miscited_provision,
                  "non_filing_content": _non_filing_content,
                  "carried_over_designation": _carried_over_designation}[m["kind"]]
            single = m.get("single_damage_instance", m["kind"] == "class_a_placeholder")
            found = fn(region, m, lead)
            if m["kind"] == "unactionable_item" and m.get("required_items") and region:
                found = found + _missing_operative_item(region, m, lead)
            for n, (p, observed, obj) in enumerate(found):
                if single:
                    obj = item["object_key"]
                oid = judge.observe(f"{item['id']}-{p.index}-{n}", "identified",
                                    [_locator(f"{item['id']}-{p.index}-{n}-loc", art, p, item["object_key"], observed)])
                occ.append((oid, obj, f"{p.path}#{n}"))
            obs["deduction"][item["id"]] = (scan, occ)
            continue
        if m["kind"] == "shape":
            region_ok = secs is not None
            scan = judge.observe(f"{item['id']}-scan", "identified" if region_ok else "parse_failure", [doc_loc])
            if region_ok:
                for unit in c["shape_units"]:
                    region = scope(unit["sections"])
                    if region is None:
                        if not unit.get("required_section"):
                            continue
                        # A block the frame requires (the closing block: 此致, the court, the signatory, the
                        # date) that is not there at all is the extreme of "too thin", not an exemption from
                        # it. It is measured as zero characters, so the under-band ladder opens its full
                        # count. A closing block written with manual line breaks is still found, because
                        # legal_prose.read_paragraphs reads each line as a paragraph.
                        region, count = [], 0
                    else:
                        count = None
                    # A unit may exclude lines that are not part of what its length contract measures. For this
                    # package's closing block that is the attachment list: the Golden's baseline carries a single
                    # "附：…" line, and a submission listing six attachments must not be charged for them, or the
                    # baseline and the measurement would not be counting the same thing.
                    skip = re.compile(unit["exclude_line_pattern"]) if unit.get("exclude_line_pattern") else None
                    if count is None:
                        count = sum(len(shape_chars(p.text)) for p in region
                                    if not (skip and skip.search(nonspace(p.text))))
                        if gap_only(region):
                            continue
                    base = max(unit["golden_value"], unit["declared_floor"])
                    ratio = count / base
                    # A charge needs both a band violation and a material absolute deviation: a short
                    # fixed-form block (a 此致 or caption line) crosses any ratio band as soon as one clause is
                    # added, which is drafting variation rather than shape damage.
                    side = None
                    if abs(count - base) >= unit.get("min_absolute_deviation", 150):
                        side = ("over" if ratio > 1 + unit["tau_over"]
                                else "under" if ratio < 1 - unit["tau_under"] else None)
                    if side:
                        anchor = region[0] if region else None
                        oid = judge.observe(f"{item['id']}-{unit['id']}", "identified",
                                            [_locator(f"{item['id']}-{unit['id']}-loc", art, anchor, unit["id"],
                                                      f"{count} nonspace chars vs {base} ({side})")])
                        occ.append((oid, unit["id"], side))
                        # A block missing far more than the threshold is not the same damage as one just
                        # under it. Every further `under_step` of the baseline missing beyond the threshold
                        # opens one more instance, `under_max_instances` in all; the threshold itself decides
                        # whether anything is charged at all.
                        if side == "under":
                            step = float(unit.get("under_step", 0.15))
                            extra = int(((1 - unit["tau_under"]) - ratio) / step + 1e-9)
                            for k in range(1, min(extra, int(unit.get("under_max_instances", 3)) - 1) + 1):
                                oid_k = judge.observe(f"{item['id']}-{unit['id']}-under{k + 1}", "identified",
                                                      [_locator(f"{item['id']}-{unit['id']}-under{k + 1}-loc", art, anchor,
                                                                unit["id"], f"ratio {ratio:.3f}: {k * step:.2f} of the baseline "
                                                                f"missing beyond the {1 - unit['tau_under']:.2f} threshold")])
                                occ.append((oid_k, f"{unit['id']}#under{k + 1}", side))
            obs["deduction"][item["id"]] = (scan, occ)
            continue
        if m["kind"] == "unsupported_specifics":
            scan = judge.observe(f"{item['id']}-scan", "identified", [doc_loc])
            exclude_sentence = m.get("exclude_sentence", [])
            ex_sentence = re.compile("|".join(f"(?:{e})" for e in exclude_sentence)) if exclude_sentence else None
            # The day the filing itself is signed or submitted is the applicant's own choice (placeholders
            # §2 Class A, the same reading D08 and P15 apply), not a fact the record could hold. A sentence
            # that says so in words ("本申请签署日为……") and names a day on or after the earliest defensible
            # expiry day is not charged; an earlier day is not the filing's date but a copied or invented one
            # and is still scanned.
            own_date_re = re.compile(m["own_date_sentence_pattern"]) if m.get("own_date_sentence_pattern") else None
            own_floor = tuple(m.get("own_date_floor", (2024, 11, 2)))
            for p in paras:
                own, _ = strip_authority_quotes(p.text)
                for s_i, s in enumerate(sentences(own)):
                    if ex_sentence and ex_sentence.search(nonspace(s)):
                        continue
                    own_dated = bool(own_date_re and own_date_re.search(nonspace(s)))
                    # "period" (e.g. a bare day-count like "十日") is not a fact category this rubric scores;
                    # left enabled it misreads the day-of-month digits inside an ordinary date ("28日" out of
                    # "5月28日") as a free-standing period and flags Golden's own dates as fabricated.
                    for n_hit, (kind, value) in enumerate(specifics(s)):
                        if kind == "period":
                            continue
                        if own_dated and kind == "date":
                            y, mo, d = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日", value).groups() if re.match(r"\d{4}年", value) else (None, None, None)
                            if y and (int(y), int(mo), int(d)) >= own_floor:
                                continue
                        if not supported(kind, value, facts):
                            oid = judge.observe(f"{item['id']}-{p.index}-{s_i}-{n_hit}", "identified",
                                                [_locator(f"{item['id']}-{p.index}-{s_i}-{n_hit}-loc", art, p, kind, value)])
                            occ.append((oid, f"{kind}:{value}", f"{p.path}#s{s_i}n{n_hit}"))
            obs["deduction"][item["id"]] = (scan, occ)
            continue
        region = scope(m["sections"])
        if region is None:
            obs["deduction"][item["id"]] = (judge.observe(f"{item['id']}-scan", "parse_failure", [doc_loc]), [])
            continue
        scan = judge.observe(f"{item['id']}-scan", "identified",
                             [_locator(f"{item['id']}-scope", art, region[0], item["object_key"], "scanned")])
        pattern = re.compile(m["error"])
        ex = re.compile("|".join(f"(?:{e})" for e in m.get("exclude", []) + generic)) if m.get("exclude", []) + generic else None
        for p in region:
            if lead_excluded(p, lead):
                continue
            own, _ = strip_authority_quotes(p.text)
            for s_i, s in enumerate(sentences(own)):
                flat = nonspace(s)
                if pattern.search(flat) and not (ex and ex.search(flat)):
                    oid = judge.observe(f"{item['id']}-{p.index}-{s_i}", "identified",
                                        [_locator(f"{item['id']}-{p.index}-{s_i}-loc", art, p, item["object_key"], s)])
                    occ.append((oid, m["damage_object"], f"{p.path}#s{s_i}"))
        obs["deduction"][item["id"]] = (scan, occ)
    return obs


def evaluate(obs: dict, judge: ProgramJudge, semantic=None) -> None:
    """Layer 3: P fractions and D occurrences with damage lineage."""
    c = judge.contract
    for item in c["positive_items"]:
        oid, detail = obs["positive"][item["id"]]
        state = judge._observation(oid)["state"]
        m = item["match"]
        kind = m.get("kind")
        if kind == "party_scope":
            row=(semantic or {}).get("items",{}).get("P14_REACH")
            if item["id"]=="P14":
                if row is None:raise RuntimeError("required source-bound P14 reach adjudication missing")
                loc=judge.observe("P14-semantic","identified",[_locator("P14-semantic-loc",judge.artifact_path,None,item["object_key"],"\n".join(row["quotes"]) or "no supported reach conclusion")])
                judge.positive("P14",row["fraction"],loc,row["reason"],"equivalent" if row["fraction"] else "different")
                continue
            if state != "identified":
                judge.positive(item["id"], 0.0, oid, f"state={state}", "missing")
                continue
            _, correct_para, wrong_paras = detail
            if correct_para is not None and not wrong_paras:
                judge.positive(item["id"], 1.0, oid, "sole respondent named, no dismissed party added back", "exact")
            elif correct_para is None:
                judge.positive(item["id"], 0.0, oid, "no paragraph names the sole surviving respondent", "different")
            else:
                judge.positive(item["id"], 0.0, oid, "an already-dismissed party is named alongside the "
                                                       "respondent", "different")
            continue
        if kind == "date_chain":
            if state != "identified":
                judge.positive(item["id"], 0.0, oid, f"state={state}",
                               "missing" if state == "confirmed_missing" else "different")
                continue
            _, hits = detail
            complete = sorted(cid for cid, roles in hits.items() if len(roles) == 2)
            touched = sorted(hits)
            if len(touched) > 1:
                judge.positive(item["id"], 0.0, oid,
                               f"dates follow more than one baseline ({', '.join(touched)}); the chain is "
                               "internally inconsistent", "different")
            elif complete:
                judge.positive(item["id"], 1.0, oid,
                               f"chain {complete[0]}: expiry day and accrual day both derived and consistent",
                               "exact" if complete[0] == m["golden_chain_id"] else "equivalent")
            else:
                judge.positive(item["id"], m["partial"]["fraction"], oid, m["partial"]["meaning"], "partial")
            continue
        if kind == "provisional_cutoff":
            if state != "identified":
                judge.positive(item["id"], 0.0, oid, f"state={state}",
                               "missing" if state == "confirmed_missing" else "different")
                continue
            _, found = detail
            if found == {"placeholder"}:
                judge.positive(item["id"], 1.0, oid,
                               "running amounts are expressly provisional and the unfixed cut-off/application day is marked as a gap",
                               "equivalent")
                continue
            if not found:
                judge.positive(item["id"], 0.0, oid,
                               "the provisional cut-off day is not the day the filing itself carries, or the "
                               "filing carries no date of its own", "different")
            elif len(found) == 1:
                y, mo, d = next(iter(found))
                judge.positive(item["id"], 1.0, oid,
                               f"running items labelled provisional against one named cut-off day {y}-{mo}-{d}",
                               "equivalent")
            else:
                judge.positive(item["id"], 0.0, oid,
                               "provisional items name more than one cut-off day: "
                               + "; ".join(f"{y}-{mo}-{d}" for y, mo, d in sorted(found)), "different")
            continue
        if kind == "formula_basis_sum":
            if state != "identified":
                judge.positive(item["id"], 0.0, oid, f"state={state}", "missing" if state == "confirmed_missing" else "different")
                continue
            _, basis_match, rate_ok, _ = detail
            if basis_match is None:
                if rate_ok and m.get("partial") and detail[3] and re.search(m["accrual_pattern"], nonspace(detail[3])):
                    judge.positive(item["id"], m["partial"]["fraction"], oid,
                                  "starting day and named rate standard are present, but no basis figure is stated",
                                  "partial")
                else:
                    judge.positive(item["id"], 0.0, oid,
                                  "delay-interest clause found but no basis figure captured", "different")
                continue
            captured = next(g for g in basis_match.groups() if g)
            candidate_value = round(float(re.sub(r"[,，]", "", captured)), 2)
            expected = round(sum(m["terms"]), 2)
            within = abs(candidate_value - expected) <= m.get("tolerance", 0.5)
            if within and rate_ok:
                comparison = "exact" if abs(candidate_value - expected) < 1e-6 else "equivalent"
                judge.positive(item["id"], 1.0, oid,
                              f"basis {candidate_value} replays construction payment + deposit + apportioned "
                              f"fees = {expected}, rate stated", comparison)
            elif rate_ok and m.get("partial") and detail[3] and re.search(m["accrual_pattern"], nonspace(detail[3])):
                # enforcement-application.md section 3 makes this item three things at once: a base that
                # reconciles with the awarded principals, a starting day that is the day after the period
                # expired, and the rate named as the standard that fixes it. Two of the three is not the
                # same answer as one of the three, so they are not both scored as zero.
                judge.positive(item["id"], m["partial"]["fraction"], oid,
                              f"starting day and named rate standard are present, but the basis "
                              f"{candidate_value} does not reconcile with the awarded principals ({expected})",
                              "partial")
            else:
                judge.positive(item["id"], 0.0, oid,
                              f"basis {candidate_value} vs replayed {expected} (within={within}), rate_ok={rate_ok}",
                              "different")
            continue
        # standard proposition kind
        if state != "identified":
            judge.positive(item["id"], 0.0, oid, f"state={state}", "missing" if state == "confirmed_missing" else "different")
            continue
        results, complete = detail
        need_all = m["require"] == "all"
        if (need_all and len(complete) == len(results)) or (not need_all and complete):
            judge.positive(item["id"], 1.0, oid, "complete proposition in one bounded span",
                          "equivalent" if item["comparison_mode"] != "exact" else "exact")
            continue
        partial = m.get("partial")
        if partial and len(complete) >= partial["min_complete_propositions"]:
            judge.positive(item["id"], partial["fraction"], oid, partial["meaning"], "partial")
        else:
            judge.positive(item["id"], 0.0, oid, "proposition incomplete in every bounded span", "different")

    for item in c["deduction_items"]:
        if item["id"] == "D14":
            scan=obs["deduction"]["D14"][0]
            if judge._observation(scan)["state"] != "identified":
                judge.deduction("D14", judge._observation(scan)["state"], [scan], "artifact unavailable for semantic review")
                continue
            row=(semantic or {}).get("items",{}).get("SOURCE_SUPPORT")
            if row is None: raise RuntimeError("required source-bound semantic adjudication missing")
            if row["fraction"] == 1:
                judge.deduction("D14","not_triggered",[scan],row["reason"])
            else:
                oid=judge.observe("D14-hit","identified",[_locator("D14-hit-loc",judge.artifact_path,None,item["object_key"],"\n".join(row["quotes"]))])
                judge.deduction("D14","triggered",[scan,oid],row["reason"],[{"damage_instance_key":"unsupported_adopted_enforcement_fact","causal_root_id":"R-source-support","manifestation_id":"D14:source-support","observation_id":oid}])
            continue
        scan, occ = obs["deduction"][item["id"]]
        state = judge._observation(scan)["state"]
        if state != "identified":
            judge.deduction(item["id"], state, [scan], f"scan state={state}")
            continue
        if not occ:
            judge.deduction(item["id"], "not_triggered", [scan], "no affirmative adopted error in scope")
            continue
        occurrences = []
        for oid, obj, manifestation in occ:
            key = f"{item['id']}:{obj}"
            occurrences.append({"damage_instance_key": key, "causal_root_id": item["causal_root_id"],
                                "manifestation_id": f"{item['id']}:{manifestation}:{oid}", "observation_id": oid})
        judge.deduction(item["id"], "triggered", [scan] + [o["observation_id"] for o in occurrences],
                        item["error_predicate"], occurrences)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--contract", type=Path, default=CANONICAL_CONTRACT)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    contract_path = args.contract.resolve()
    judge = ProgramJudge(load_contract(contract_path), args.artifact.resolve(), sha256(contract_path))
    raw=extract_raw(args.artifact.resolve()); normalized=normalize(raw,judge); semantic=None
    if raw["paras"] is not None:
        import sys
        tests=Path(__file__).resolve().parents[4];sys.path.insert(0,str(tests))
        from semantic_judge import adjudicate
        source="\n".join(p.read_text(encoding="utf-8") for p in sorted((PACKAGE_ROOT/"materials").glob("*.md")))
        semantic=adjudicate("\n".join(p.text for p in raw["paras"] if p.text.strip()),source)
    evaluate(normalized, judge, semantic)
    result = judge.finish()
    if semantic: result["semantic_judge"]=semantic
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json:
        args.json.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
