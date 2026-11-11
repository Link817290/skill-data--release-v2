#!/usr/bin/env python3
"""Program Judge for 2-11b (B公司 opinions on Q银行's evidence in an enforcement objection action).

Three layers, as `notes/04c-program-judge-template.md` requires: `extract_raw` reads the DOCX or
Markdown carrier, `normalize` registers one observation per contracted item from bounded sentence
windows inside registered regions, `evaluate` turns observations into P/D decisions. Every term
list, exclusion, weight and shape baseline lives in `rubric-contract.json`; this file supplies only
the document's own structure.

Structure model (this deliverable has no per-exhibit numbered headings -- the Golden is
one evidence-detail list plus three grouped opinion paragraphs, `证据1-3` / `证据4-6` / `证据7`):

  LIST      every body paragraph that names a filed document (《…》, 裁定书, 通知书, 合同, 协议,
            登记, 明细, 报表, 流水). Content-addressed rather than position-addressed so a submission
            that folds the detail line and its opinion into one paragraph is not punished for layout.
  EV1..EV7  opinion paragraphs, keyed by the exhibit numbers each one speaks about. `证据1-3`,
            `证据1至3`, `证据1、2、3` and a blanket `全部证据` all expand; a paragraph with no
            reference of its own inherits the previous paragraph's set (a continuation).
  __tail__  the signature block, carved off the end so it is never scored as opinion text.
  __head__  everything before the first list or opinion paragraph.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from legal_prose import (GAP_MARKER, Para, corpus_facts, find_proposition, gap_only, lead_excluded, material_texts,
                         nonspace, read_paragraphs, sentences, shape_chars, specifics,
                         strip_authority_quotes, supported, with_document_derivations)
from program_judge_runtime import Locator, ProgramJudge, load_contract, sha256


PACKAGE_ROOT = Path(__file__).resolve().parents[3]
CANONICAL_CONTRACT = PACKAGE_ROOT / "rubric-contract.json"
EVIDENCE_COUNT = 7

_CN = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7}
_DOC_TOKEN = re.compile(r"《[^》]{2,40}》|裁定书|通知书|托管合同|质押合同|登记协议|登记表|登记证明|"
                        r"动产权属|交易明细|明细报表|明细表|账户流水|流水|征信中心")
_SIGNATURE_LEAD = re.compile(
    # A signature line names a party or an agent and then opens its value. The role word may carry an
    # ordinal and a parenthesised procedural status before the colon (`被告一（申请执行人）：B公司`);
    # without that allowance the whole sign-off block would stay in the body and be scored as part of
    # the last exhibit's opinion.
    r"^(提交人|质证人|答辩人|异议人|出具人|被告|原告|上诉人|被上诉人|申请执行人|申请人|案外人|"
    r"具状人|落款|委托诉讼代理人|代理人)[一二三四五六七八九十]?(?:[（(][^）)]{0,16}[）)])?\s*[：:]"
    r"|^日期[：:]|^[二〇零一二三四五六七八九十0-9]{2,4}年[0-9一二三四五六七八九十]{1,3}月")
_LIST_HEADING = re.compile(r"^(原告|异议人|案外人|对方)?.{0,8}(证据(明细|目录|清单|列表|一览)|举证(清单|目录))")
_SECTION_HEADING = re.compile(r"^[（(]?[一二三四五六七八九十]+[）)、.．]")
_CLOSING = re.compile(r"^(此致|综上|以上意见|特此)")
"""The valediction and a closing summary end the last exhibit's block for the same reason a new
numbered section does: they speak about the filing, not about that exhibit."""
"""A new top-level numbered section that names no exhibit ends the previous exhibit's block. Without
this, a closing `四、结论` and everything under it would inherit whichever exhibit the last opinion was
about, and paragraphs of general argument plus the signature block would all be attributed to the last
exhibit."""


def _num(token: str) -> int | None:
    if token in _CN:
        return _CN[token]
    return int(token) if token.isdigit() and 1 <= int(token) <= EVIDENCE_COUNT else None


_REF = re.compile(r"证据\s*(?:第)?\s*([1-9]|[一二三四五六七])"
                  r"((?:\s*[-－—–~～、,，和及与至到]\s*(?:证据)?\s*(?:第)?\s*(?:[1-9]|[一二三四五六七]))*)")
_REF_TAIL = re.compile(r"([1-9]|[一二三四五六七])")
_RANGE = re.compile(r"[-－—–~～至到]")
_BLANKET = re.compile(r"(全部|所有|上述|以上|前述|各[项份组]?|七份|7份|本案)\s*(?:原告)?\s*证据")


def evidence_refs(text: str) -> set[int]:
    """Exhibit numbers a paragraph speaks about, expanding ranges, enumerations and blanket forms."""
    flat = nonspace(text)
    if _BLANKET.search(flat):
        return set(range(1, EVIDENCE_COUNT + 1))
    found: set[int] = set()
    for m in _REF.finditer(flat):
        first = _num(m.group(1))
        if first is None:
            continue
        found.add(first)
        rest = [t for t in _REF_TAIL.findall(m.group(2) or "")]
        numbers = [n for n in (_num(t) for t in rest) if n is not None]
        if numbers and _RANGE.search(m.group(2) or ""):
            found |= set(range(min(first, numbers[0]), max(first, numbers[0]) + 1))
        found |= set(numbers)
    return {n for n in found if 1 <= n <= EVIDENCE_COUNT}


_ORDINAL_ENTRY = re.compile(r"^(?:证据)?\s*(?:第)?\s*([1-9]|[一二三四五六七])\s*[、.．)）:：]")
HEADING_MAX_CHARS = 60
DETAIL_ENTRY_MAX_CHARS = 120
"""A detail line says what an exhibit IS; it does not argue. The Golden's seven entries run 12 to 23
nonspace characters. Without this cap a numbered block of argument that happens to name a document in
each of three consecutive paragraphs (『1. 原告在执行异议审查阶段列明的证据为七项…』 / 『2. 据此…均未随本案
证据提交』 / 『3. 原告提交的材料中…』, 230+ characters each) would be read as the evidence list, which
would put D02's scan on the very paragraph that correctly identifies the superseded list as superseded."""
"""A paragraph this short that names a filed document is identifying that exhibit (a section heading or a
detail line). A long argument paragraph that happens to mention a document is not, so it inherits the
exhibit its block is already about instead of re-anchoring on an incidental citation -- otherwise a
quotation of the ruling inside exhibit 4's opinion would move that opinion to exhibit 1."""


def _entry_number(text: str) -> int | None:
    m = _ORDINAL_ENTRY.match(nonspace(text))
    return _num(m.group(1)) if m else None


def detail_list_run(body: list[Para]) -> list[Para]:
    """The evidence-detail list: the longest run of consecutive paragraphs that each open with an
    ascending ordinal and name a filed document, at least three long.

    Requiring a RUN is what separates a real detail list from an argument written as numbered points:
    '2．原告据以主张权利的《借款合同》…' and '4．案涉账户的流水恰恰证明…' are numbered paragraphs of argument,
    not exhibits, and scoring them as detail entries would put their characters into the list shape unit
    and pull argument paragraphs out of the opinion region."""
    best: list[Para] = []
    run: list[Para] = []
    last = 0
    for p in body:
        n = _entry_number(p.text)
        short = len(nonspace(p.text)) <= DETAIL_ENTRY_MAX_CHARS
        if n is not None and short and _DOC_TOKEN.search(p.text) and n > last:
            run.append(p)
            last = n
        else:
            if len(run) > len(best):
                best = run
            run, last = [], 0
            n2 = _entry_number(p.text)
            if n2 is not None and short and _DOC_TOKEN.search(p.text):
                run, last = [p], n2
    if len(run) > len(best):
        best = run
    return best if len(best) >= 3 else []


def alias_refs(text: str, aliases: dict[str, list[str]]) -> set[int]:
    """Exhibit numbers a short heading identifies by naming the document itself."""
    flat = nonspace(text)
    return {int(n) for n, patterns in aliases.items() if any(re.search(a, flat) for a in patterns)}


def cross_examination_sections(paras: list[Para], aliases: dict[str, list[str]] | None = None) -> dict[str, list[Para]]:
    """Named regions for this deliverable. Never returns None: an absent region is an empty list, so a
    submission that simply omits a part loses that item's credit as an ordinary omission (`04c` #3)
    rather than being reported as a parse failure, which is reserved for an unreadable carrier."""
    aliases = aliases or {}
    tail_start = len(paras)
    for position in range(len(paras) - 1, -1, -1):
        if _SIGNATURE_LEAD.match(nonspace(paras[position].text)):
            tail_start = position
        elif position < tail_start:
            break
    body, tail = paras[:tail_start], paras[tail_start:]

    out: dict[str, list[Para]] = {f"EV{n}": [] for n in range(1, EVIDENCE_COUNT + 1)}
    out["__tail__"] = tail
    out["LIST"] = [p for p in body if _DOC_TOKEN.search(p.text)]
    entries = detail_list_run(body)
    if entries:
        first = body.index(entries[0])
        if first and _LIST_HEADING.match(nonspace(body[first - 1].text)):
            entries = [body[first - 1]] + entries
    out["LIST_ENTRIES"] = entries

    entry_ids = {id(p) for p in entries}
    carried: set[int] = set()
    opinion: list[Para] = []
    anchor: dict[int, set[int]] = {}
    for p in body:
        if id(p) in entry_ids:
            continue                      # a detail line states what an exhibit IS, not an opinion on it
        refs = evidence_refs(p.text)
        if not refs and len(nonspace(p.text)) <= HEADING_MAX_CHARS:
            refs = alias_refs(p.text, aliases)
        if refs:
            carried = refs
        elif _SECTION_HEADING.match(nonspace(p.text)) or _CLOSING.match(nonspace(p.text)):
            carried = set()
        if not carried:
            continue
        anchor[id(p)] = carried
        opinion.append(p)
        for n in carried:
            out[f"EV{n}"].append(p)
    out["OPINION"] = opinion
    # Shape buckets. Each opinion paragraph lands in exactly ONE bucket, keyed by the lowest exhibit
    # number its block is about, so a grouped `证据4-6：…` paragraph is measured once even though EV4, EV5
    # and EV6 all see it. The three buckets are the Golden's own zones:
    # exhibits 1-3 (the court documents), 4-6 (the pledge instruments) and 7 (the account statement).
    for key in ("SHAPE_OP13", "SHAPE_OP46", "SHAPE_OP7"):
        out[key] = []
    for p in opinion:
        lead = min(anchor[id(p)])
        out["SHAPE_OP13" if lead <= 3 else "SHAPE_OP46" if lead <= 6 else "SHAPE_OP7"].append(p)
    assigned = entry_ids | {id(p) for p in opinion}
    leading = []
    for p in body:
        if id(p) in assigned:
            break
        leading.append(p)
    out["__head__"] = [p for p in body if id(p) not in assigned]
    out["SHAPE_LIST"] = entries
    # The caption block is what precedes the first exhibit the document speaks about; the unassigned
    # paragraphs further down (section headings, a closing summary) are scored nowhere and are not part
    # of any zone's size contract, so they are deliberately absent from every shape unit.
    out["SHAPE_ENDS"] = leading + tail
    out["__all__"] = list(paras)
    return out


def missing_opinions(secs: dict[str, list[Para]], aliases: dict[str, list[str]]) -> list[int]:
    """Exhibits the filing gives no opinion on at all (D08).

    An exhibit is missing when its EV region is empty AND no unassigned body paragraph longer than a heading
    names that exhibit's document by alias. The second half is a carrier guard: a long paragraph that argues
    about the 流水 without an explicit 证据7 label is an opinion the sectioner failed to anchor, not an
    omission, and it must not be charged as one. A marked gap (`证据4：【待补充】`) has a paragraph in its
    region and is therefore never counted here - only silent absence is."""
    unassigned = [p for p in secs.get("__head__", []) if len(nonspace(p.text)) > HEADING_MAX_CHARS]
    missing = []
    for n in range(1, EVIDENCE_COUNT + 1):
        if secs.get(f"EV{n}"):
            continue
        if any(n in alias_refs(p.text, aliases) for p in unassigned):
            continue
        missing.append(n)
    return missing


_CN_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def article_number(token: str) -> int | None:
    """`六百八十八` -> 688, `九十` -> 90, `二十四` -> 24, `425` -> 425."""
    token = token.strip()
    if token.isdigit():
        return int(token)
    total, current = 0, 0
    for ch in token:
        if ch in _CN_DIGITS:
            current = _CN_DIGITS[ch]
        elif ch == "十":
            total += (current or 1) * 10
            current = 0
        elif ch == "百":
            total += (current or 1) * 100
            current = 0
        elif ch == "千":
            total += (current or 1) * 1000
            current = 0
        else:
            return None
    return total + current


_TITLE = re.compile(r"《([^》]{2,60})》")
_ARTICLE = re.compile(r"第\s*([0-9]{1,4}|[零〇一二两三四五六七八九十百千]{1,8})\s*条")
_ANAPHORIC_LAW = re.compile(r"(?:该|前述|上述|同)(解释|规定|法)")


def cited_provisions(text: str, laws: list[dict], cue: re.Pattern, trailing: re.Pattern) -> list[tuple[dict, int, str]]:
    """Provisions the author relies on in one paragraph: (law, article, sentence).

    A citation is one of `《title》第N条` or `该解释/该法/该规定第N条` (resolving to the last law of that kind
    named earlier in the paragraph). It counts only when the author RELIES on it - a reliance cue precedes the
    title (依据/依照/根据/依/适用...) or `规定` follows the article - so a registration certificate's own
    printed legal basis (`登记证明所载当时《物权法》第二百二十八条`) is reported, not adopted, and never charged."""
    out = []
    last_by_kind: dict[str, dict] = {}
    for sentence in sentences(text):
        flat = nonspace(sentence)
        position = 0
        while True:
            title = _TITLE.search(flat, position)
            anaphor = _ANAPHORIC_LAW.search(flat, position)
            if not title and not anaphor:
                break
            if title and (not anaphor or title.start() <= anaphor.start()):
                law = next((entry for entry in laws
                            if re.search(entry["title"], title.group(1)) and not
                            (entry.get("not_title") and re.search(entry["not_title"], title.group(1)))), None)
                position = title.end()
                if law is None:
                    continue
                kind = "解释" if "解释" in title.group(1) else "规定" if "规定" in title.group(1) else "法"
                last_by_kind[kind] = law
                relied = bool(cue.search(flat[max(0, title.start() - 12):title.start() + 1]))
                head = title.end()
            else:
                law = last_by_kind.get(anaphor.group(1))
                position = anaphor.end()
                if law is None:
                    continue
                relied = bool(cue.search(flat[max(0, anaphor.start() - 12):anaphor.start() + 1]))
                head = anaphor.end()
            article = _ARTICLE.match(flat, head)
            if not article:
                continue
            number = article_number(article.group(1))
            if number is None:
                continue
            tail = flat[article.end():article.end() + 16]
            if relied or trailing.match(tail):
                out.append((law, number, sentence))
            position = article.end()
    return out


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
    secs = cross_examination_sections(paras, c["task_matching"].get("exhibit_aliases", {}))
    generic = c["task_matching"]["generic_exclusions"]
    lead = c["task_matching"]["paragraph_lead_exclusions"]
    turn_rule = c["task_matching"].get("rebuttal_turn")

    def scope(names: list[str]) -> list[Para]:
        """Union of the named regions, each paragraph kept once. A grouped opinion paragraph
        (`证据4-6：…`) is visible to EV4, EV5 and EV6, so a scan over several names must not observe
        the same sentence three times."""
        chosen: list[Para] = []
        for n in names:
            for p in secs.get(n, []):
                if all(p is not q for q in chosen):
                    chosen.append(p)
        return sorted(chosen, key=lambda p: p.index)

    def author_clauses(region: list[Para]) -> list[Para]:
        """Quote-then-rebut: `原告主张质权已有效设立，但…` reports the plaintiff's contention only before
        the turn. The generic attribution exclusion works per sentence and would void the author's own
        conclusion with it, so for positive matching the attributed clause is blanked and the rest of the
        sentence kept. A sentence still attributing after the turn is left excluded."""
        if not turn_rule:
            return region
        attribution, turn = re.compile(turn_rule["attribution"]), re.compile(turn_rule["turn"])
        out = []
        for p in region:
            if lead_excluded(p, lead):
                out.append(p)
                continue
            parts = []
            for s in sentences(p.text):
                t = turn.search(s)
                if t and attribution.search(nonspace(s[:t.start()])) and not attribution.search(nonspace(s[t.end():])):
                    s = "引述从略" + s[t.start():]
                parts.append(s)
            out.append(Para(p.index, p.path, "".join(parts)))
        return out

    for item in c["positive_items"]:
        m = item["match"]
        results = []
        for prop in m["propositions"]:
            region = author_clauses(scope(prop["sections"]))
            results.append(find_proposition(region, prop["groups"], prop.get("exclude", []), generic, None,
                                            prop["max_chars"], prop["sentence_window"], lead))
        complete = [r for r in results if r[0] == r[1]]
        evidence = [r[2] for r in results if r[2] is not None]
        if not evidence:
            loc = _locator(f"{item['id']}-scope", art, None, item["object_key"], "no matching proposition in scope")
            obs["positive"][item["id"]] = (judge.observe(f"{item['id']}-obs", "confirmed_missing", [loc]), (results, []))
            continue
        locs = [_locator(f"{item['id']}-ev{n}", art, p, item["object_key"], w) for n, (p, w) in enumerate(evidence)]
        obs["positive"][item["id"]] = (judge.observe(f"{item['id']}-obs", "identified", locs), (results, complete))

    facts = corpus_facts(material_texts(PACKAGE_ROOT / "materials")
                         + [(PACKAGE_ROOT / "instruction.md").read_text(encoding="utf-8")])
    facts = with_document_derivations(facts, paras)
    for item in c["deduction_items"]:
        m = item["match"]
        occ = []
        if m["kind"] == "shape":
            obs["deduction"][item["id"]] = (judge.observe(f"{item['id']}-scan", "identified", [doc_loc]), [])
            continue
            scan = judge.observe(f"{item['id']}-scan", "identified", [doc_loc])
            for unit in c["shape_units"]:
                region = scope(unit["sections"])
                if not region or gap_only(region):
                    continue
                count = sum(len(shape_chars(p.text)) for p in region)
                base = max(unit["golden_value"], unit["declared_floor"])
                ratio = count / base
                side = None
                if abs(count - base) >= unit.get("min_absolute_deviation", 150):
                    side = ("over" if ratio > 1 + unit["tau_over"]
                            else "under" if ratio < 1 - unit["tau_under"] else None)
                if side:
                    oid = judge.observe(f"{item['id']}-{unit['id']}", "identified",
                                        [_locator(f"{item['id']}-{unit['id']}-loc", art, region[0], unit["id"],
                                                  f"{count} nonspace chars vs {base} ({side})")])
                    occ.append((oid, unit["id"], side))
            obs["deduction"][item["id"]] = (scan, occ)
            continue
        if m["kind"] == "missing_opinion":
            # A filing that silently omits whole exhibits loses more than the positive credit it never earned.
            # Every `exhibits_per_instance` missing exhibits open one damage instance, capped at
            # `instance_cap`: batch loss is counted, but retention is never annihilated by it.
            scan = judge.observe(f"{item['id']}-scan", "identified", [doc_loc])
            missing = missing_opinions(secs, c["task_matching"].get("exhibit_aliases", {}))
            per = int(m.get("exhibits_per_instance", 2))
            count = min(int(m.get("instance_cap", 2)), (len(missing) + per - 1) // per) if missing else 0
            for k in range(count):
                oid = judge.observe(f"{item['id']}-{k}", "identified",
                                    [_locator(f"{item['id']}-{k}-loc", art, None, item["object_key"],
                                              f"no opinion on exhibits {missing} ({len(missing)} of {EVIDENCE_COUNT})")])
                occ.append((oid, f"{m['damage_object']}:{k + 1}", f"document#{k}"))
            obs["deduction"][item["id"]] = (scan, occ)
            continue
        if m["kind"] == "miscited_provision":
            # A provision relied on for a proposition its chapter does not govern
            # (《民法典》第六百八十八条 - suretyship - cited for the specification requirement of a money pledge)
            # is charged, one instance per provision, capped. Only provisions inside a range the contract
            # knows are judged; an unknown article is never charged, so a correct citation outside the
            # table costs nothing. A quoted authority, a gap-marked note and a sentence attributed to the
            # other side are not the author's reliance.
            scan = judge.observe(f"{item['id']}-scan", "identified", [doc_loc])
            cue = re.compile(m["reliance_cue"])
            trailing = re.compile(m["trailing_cue"])
            topics = {name: re.compile(pattern) for name, pattern in m["topic_terms"].items()}
            seen: set[str] = set()
            for p in paras:
                if lead_excluded(p, lead):
                    continue
                own, _ = strip_authority_quotes(p.text)
                own = GAP_MARKER.sub("", own)
                for law, number, sentence in cited_provisions(own, m["laws"], cue, trailing):
                    flat = nonspace(sentence)
                    if any(re.search(g, flat) for g in generic):
                        continue
                    span = next((r for r in law["ranges"] if r[0] <= number <= r[1]), None)
                    if span is None:
                        continue
                    # The subject is read off the author's own words: the cited title (`《物权法》` says 物权)
                    # is not what the sentence is about.
                    bare = _TITLE.sub("", flat)
                    said = {name for name, pattern in topics.items() if pattern.search(bare)}
                    if law['id'] == '民诉法' and number in (64, 67):
                        # Read the cited evidential duty in paragraph context, including
                        # "应说明/建立对应关系" rather than an exact 证明 token.
                        burden = re.search(r"(?:原告|Q银行|主张者|当事人)[^。;]{0,30}(?:应|须|负|承担|负责)[^。;]{0,100}(?:证据|举证|证明|对应关系|对应|衔接|关联性|关联|联系|来源|说明)", nonspace(own))
                        if burden: said.add('举证')
                    if not said or said & set(span[2]):
                        continue
                    key = f"{law['id']}:{number}"
                    if key in seen or len(seen) >= int(m.get("instance_cap", 2)):
                        continue
                    seen.add(key)
                    oid = judge.observe(f"{item['id']}-{p.index}-{len(seen)}", "identified",
                                        [_locator(f"{item['id']}-{p.index}-{len(seen)}-loc", art, p, item["object_key"],
                                                  f"{key} governs {'/'.join(span[2])}; sentence speaks of {'/'.join(sorted(said))}: {sentence}")])
                    occ.append((oid, f"{m['damage_object']}:{key}", f"{p.path}#{key}"))
            obs["deduction"][item["id"]] = (scan, occ)
            continue
        if m["kind"] == "delivery_carrier":
            # The brief says "Deliver it as a Chinese Word document at
            # artifacts/质证意见.docx". A Markdown fallback is not a Word document and another file name is
            # not the named path. One damage instance whatever the number of deviations.
            scan = judge.observe(f"{item['id']}-scan", "identified", [doc_loc])
            reasons = []
            # Both halves are judged only on a file that sits in the delivery directory: that is where a
            # submission delivers and where the validator's fallback finds a Markdown or a misnamed file. A
            # file anywhere else (Golden's own reference copies, the conformance suite's markdown export)
            # is not a delivery, and the judge reads its content exactly as it
            # reads the .docx - the conformance suite's equivalent-carrier property is kept.
            if art.parent.name == m["delivery_dir"]:
                if art.suffix.lower() != m["required_suffix"]:
                    reasons.append(f"carrier {art.suffix or '<none>'} is not {m['required_suffix']}")
                if art.name != m["required_name"]:
                    reasons.append(f"delivered as {art.name}, not {m['required_name']}")
            if reasons:
                oid = judge.observe(f"{item['id']}-0", "identified",
                                    [_locator(f"{item['id']}-0-loc", art, None, item["object_key"], "; ".join(reasons))])
                occ.append((oid, m["damage_object"], "document#delivery"))
            obs["deduction"][item["id"]] = (scan, occ)
            continue
        if m["kind"] == "unsupported_specifics":
            scan = judge.observe(f"{item['id']}-scan", "identified", [doc_loc])
            for p in paras:
                for n_hit, (kind, value) in enumerate(specifics(p.text)):
                    if not supported(kind, value, facts):
                        oid = judge.observe(f"{item['id']}-{p.index}-{n_hit}", "identified",
                                            [_locator(f"{item['id']}-{p.index}-{n_hit}-loc", art, p, kind, value)])
                        occ.append((oid, f"{kind}:{value}", f"{p.path}#{n_hit}"))
            obs["deduction"][item["id"]] = (scan, occ)
            continue
        region = scope(m["sections"])
        carrier = m.get("heading_carrier")
        if carrier:
            # A second carrier for the decoy-list error. Besides a numbered detail list
            # (SHAPE_LIST), a filing that writes one heading per exhibit (`一、证据1：价款合同`) has
            # adopted the superseded list just as plainly. Only a short heading-shaped paragraph that
            # labels an exhibit number counts; a long argument paragraph never re-anchors here, and the
            # item's own sentence and paragraph exclusions (未提交 / 此前阶段 ...) still apply to it.
            head_re = re.compile(carrier["pattern"])
            extra = [p for p in paras if len(nonspace(p.text)) <= int(carrier.get("max_chars", HEADING_MAX_CHARS))
                     and head_re.search(nonspace(p.text)) and all(p is not q for q in region)]
            region = sorted(region + extra, key=lambda p: p.index)
        blocked: set[int] = set()
        if m.get("exclude_block"):
            # An opinion block anchored on a document that was never filed (a heading or a
            # ref-carrying sentence naming 价款合同 / 应收账款质押合同 / 借款合同 / 融资租赁合同) is not an
            # opinion on a court instrument. Denying such a document's authenticity is the decoy-list error
            # and is charged by D02, not here. The block runs from the anchoring paragraph through the
            # continuation paragraphs that inherit its exhibit set, exactly as the sectioner assigns them.
            block_re = re.compile(m["exclude_block"])
            opinion_ids = {id(p) for p in secs.get("OPINION", [])}
            entry_ids = {id(p) for p in secs.get("LIST_ENTRIES", [])}
            in_block = False
            for p in paras:
                if id(p) not in opinion_ids:
                    if id(p) not in entry_ids:
                        in_block = False      # a section heading, a closing or the caption ends the block
                    continue
                flat = nonspace(p.text)
                refs = evidence_refs(p.text)
                if not refs and len(flat) <= HEADING_MAX_CHARS:
                    refs = alias_refs(p.text, c["task_matching"].get("exhibit_aliases", {}))
                if refs and len(flat) <= HEADING_MAX_CHARS:
                    in_block = bool(block_re.search(flat))      # a heading re-anchors the block
                elif refs and block_re.search(flat):
                    in_block = True                             # a long paragraph can open one, never close one
                if in_block:
                    blocked.add(id(p))
        scan = judge.observe(f"{item['id']}-scan", "identified",
                             [_locator(f"{item['id']}-scope", art, region[0] if region else None,
                                       item["object_key"], "scanned")])
        pattern = re.compile(m["error"])
        item_generic = [] if m.get("ignore_generic_exclusions") else generic
        ex_patterns = m.get("exclude", []) + item_generic
        ex = re.compile("|".join(f"(?:{e})" for e in ex_patterns)) if ex_patterns else None
        para_ex = m.get("exclude_paragraph") or []
        para_ex = re.compile("|".join(f"(?:{e})" for e in para_ex)) if para_ex else None
        for p in region:
            if lead_excluded(p, lead) or id(p) in blocked:
                continue
            if para_ex and para_ex.search(nonspace(p.text)):
                # The whole paragraph carries a context that makes the error proposition inapplicable
                # (for example: naming the superseded exhibit list AS superseded). A sentence-level
                # exclusion cannot see it, because the enumeration splits on the semicolons inside it.
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
        if semantic and item['id'] in semantic['items'] and item['id'] != 'P01':
            row=semantic['items'][item['id']];semantic_fraction=row['fraction']
            fraction = semantic_fraction
            identity_note = ""
            if detail is not None and item['id'] == 'P13':
                results, _ = detail
                identity_fraction = sum(results[i][0] == results[i][1] for i in (0, 2)) / 2
                fraction = .5 * identity_fraction + .5 * semantic_fraction
                identity_note = f"; deterministic exhibit identity={identity_fraction:.3f}"
            elif detail is not None and item['id'] in {'P14', 'P15', 'P16'}:
                results, _ = detail
                identity_fraction = float(results[0][0] == results[0][1])
                fraction = .4 * identity_fraction + .6 * semantic_fraction
                identity_note = f"; deterministic exhibit identity={identity_fraction:.3f}"
            oid=judge.observe('semantic-'+item['id'], 'identified' if fraction else 'confirmed_missing',
                              [_locator('semantic-'+item['id']+'-loc',judge.artifact_path,None,item['object_key'],'\n'.join(row['quotes']) or 'no supported proposition')])
            judge.positive(item['id'],round(fraction,6),oid,row['reason']+identity_note,'equivalent' if fraction==1 else 'partial' if fraction else 'missing')
            continue
        state = judge._observation(oid)["state"]
        if state != "identified":
            judge.positive(item["id"], 0.0, oid, f"state={state}", "missing" if state == "confirmed_missing" else "different")
            continue
        results, complete = detail
        m = item["match"]
        if m["require"] == "all" and len(complete) == len(results):
            judge.positive(item["id"], 1.0, oid, "every required proposition complete in one bounded span",
                           "equivalent" if item["comparison_mode"] != "exact" else "exact")
            continue
        if m["require"] == "any" and complete:
            judge.positive(item["id"], 1.0, oid, "a required proposition complete in one bounded span",
                           "equivalent" if item["comparison_mode"] != "exact" else "exact")
            continue
        partial = m.get("partial")
        if partial and len(complete) >= partial["min_complete_propositions"]:
            fraction = (len(complete) / len(results) if partial.get("mode") == "proportional"
                        else partial["fraction"])
            judge.positive(item["id"], round(fraction, 6), oid, partial["meaning"], "partial")
        else:
            judge.positive(item["id"], 0.0, oid, "proposition incomplete in every bounded span", "different")
    for item in c["deduction_items"]:
        scan, occ = obs["deduction"][item["id"]]
        state = judge._observation(scan)["state"]
        if state != "identified":
            judge.deduction(item["id"], state, [scan], f"scan state={state}")
            continue
        if semantic and item["id"] in {"D03", "D09"}:
            row = semantic["items"][item["id"]]
            if not row["fraction"]:
                judge.deduction(item["id"], "not_triggered", [scan], row["reason"])
                continue
            if not occ:
                oid = judge.observe(
                    "semantic-" + item["id"], "identified",
                    [_locator("semantic-" + item["id"] + "-loc", judge.artifact_path, None,
                              item["object_key"], "\n".join(row["quotes"]))],
                )
                occ = [(oid, item["match"]["damage_object"], "semantic")]
        if not occ:
            judge.deduction(item["id"], "not_triggered", [scan], "no affirmative adopted error in scope")
            continue
        occurrences = []
        for oid, obj, manifestation in occ:
            # Shape: one business damage per SIDE, not per zone. A filing that argues at brief length does
            # so across all of its zones at once -- those are manifestations of one damage ("the evidence
            # opinions stopped being evidence opinions"), and 04a §2 says repeated manifestations of one
            # damage multiply once. Over-run and under-run remain two separable damages.
            key = f"{item['id']}:{manifestation}" if item["match"]["kind"] == "shape" else f"{item['id']}:{obj}"
            occurrences.append({"damage_instance_key": key,
                                "causal_root_id": item["causal_root_id"],
                                "manifestation_id": f"{item['id']}:{obj}:{oid}",
                                "observation_id": oid})
        judge.deduction(item["id"], "triggered", [scan] + [o["observation_id"] for o in occurrences],
                        item["error_predicate"], occurrences)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--contract", type=Path, default=CANONICAL_CONTRACT)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    contract_path = args.contract.resolve()
    outer=Path(__file__).resolve().parents[4]/'rubric-contract.json'
    if outer.read_bytes() != CANONICAL_CONTRACT.read_bytes():
        raise RuntimeError('packaged rubric contracts differ; repair both copies before scoring')
    judge = ProgramJudge(load_contract(contract_path), args.artifact.resolve(), sha256(contract_path))
    raw=extract_raw(args.artifact.resolve())
    semantic=None
    if raw['paras'] is not None:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
        from semantic_judge import adjudicate
        semantic=adjudicate('\n'.join(p.text.strip() for p in raw['paras'] if p.text.strip()), (Path(__file__).resolve().parents[4]/'semantic_source.json').read_text())
    evaluate(normalize(raw, judge), judge, semantic)
    result = judge.finish()
    if semantic: result["semantic_judge"] = semantic
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json:
        args.json.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
