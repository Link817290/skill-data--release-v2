#!/usr/bin/env python3
"""Deterministic carrier and proposition helpers for Chinese legal documents.

Layer 1 (raw carrier): `read_paragraphs` returns visible body paragraphs and native table rows of a DOCX, or the
non-empty lines of a Markdown/text export, each with a structural path.
Layer 2 (normalized observation): `sections`, `sentences`, `find_proposition` and `unsupported_specifics` turn the raw
records into located business observations using only rules registered in the rubric contract.
No model judgement is involved; every decision is reproducible from the artifact bytes and the contract.
"""
from __future__ import annotations

import re
import zipfile
from xml.etree import ElementTree
from dataclasses import dataclass
from pathlib import Path

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


@dataclass
class Para:
    index: int
    path: str
    text: str


# A Chinese document may carry its numerals fullwidth
# (１９３，４４０．５０元, ２０２４年, ３０％). Every reader below folds them to ASCII before any predicate runs -
# digits always, `％` always, and a fullwidth comma / point only when it sits between digits, so `（`, `：`,
# `；` and the sentence punctuation the judges key on are left exactly as written. Full NFKC would fold
# those too and break the section and quotation parsers.
_FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９％", "0123456789%")


def halfwidth_numerals(text: str) -> str:
    text = text.translate(_FULLWIDTH_DIGITS)
    text = re.sub(r"(?<=\d)，(?=\d)", ",", text)
    return re.sub(r"(?<=\d)．(?=\d)", ".", text)


def read_paragraphs(artifact: Path) -> list[Para]:
    """Body paragraphs and table rows in document order (DOCX) or non-empty lines (Markdown/text)."""
    if artifact.suffix.lower() == ".docx":
        with zipfile.ZipFile(artifact) as z:
            root = ElementTree.fromstring(z.read("word/document.xml"))
        body = root.find(W + "body")
        out: list[Para] = []
        for n, child in enumerate(body):
            tag = child.tag.replace(W, "")
            if tag == "p":
                text = "".join(t.text or "" for t in child.iter(W + "t"))
                out.append(Para(len(out), f"body/p[{n}]", halfwidth_numerals(text)))
            elif tag == "tbl":
                for r, row in enumerate(child.iter(W + "tr")):
                    cells = ["".join(t.text or "" for t in tc.iter(W + "t")) for tc in row.iter(W + "tc")]
                    out.append(Para(len(out), f"body/tbl[{n}]/tr[{r}]", halfwidth_numerals(" | ".join(cells))))
        return out
    lines = artifact.read_text(encoding="utf-8").splitlines()
    return [Para(i, f"line[{i + 1}]", halfwidth_numerals(re.sub(r"^\s*(#+|[-*+]|\|)\s*", "", line).strip(" |")))
            for i, line in enumerate(lines)]


def nonspace(text: str) -> str:
    return re.sub(r"\s", "", text)


QUOTE = re.compile(r"(纪要|案例|意见|规定|判决|裁定|案情摘要|指出|明确)[^“\"]{0,30}[：:，,]?\s*[“\"]([^”\"]{20,})[”\"]")


def strip_authority_quotes(text: str, keep_embedded: bool = False) -> tuple[str, list[str]]:
    """Remove verbatim quotations of authorities; they are cited text, not the author's own adopted claims.

    `keep_embedded` separates the two uses. For the fabricated-specific scan a figure inside any quotation
    belongs to the source, so every quotation is blanked and the figure is never charged. For proposition
    matching a quotation the author embeds inside its own sentence is a restatement rather than a citation
    ("一审判决已经查明并判令答辩人应于『收到…1200640元的增值税专用发票后十日内』支付制作费用"), and blanking it
    would also blank the amount and deadline an item asks for. A formal citation closes
    its sentence at the quotation, so with `keep_embedded` the quote survives whenever the author's own
    predicate continues after it within the same sentence."""
    quotes = []

    def repl(m):
        if keep_embedded:
            # A formal source citation stays stripped even mid-sentence: a 《书名号》 title or a 第N条 reference
            # right before the quotation marks it as the statute's words, not the author's restatement; two
            # statutory quotations inside one sentence would otherwise fill the whole span.
            lead = nonspace(text[max(0, m.start() - 40):m.start(2)])
            formal = re.search(r"《[^》]{2,40}》|第[一二三四五六七八九十百零\d]{1,8}条", lead)
            continuation = re.split(r"[。；;！!？?]", text[m.end():], 1)[0]
            if not formal and len(nonspace(continuation)) >= 4:
                return m.group(0)
        quotes.append(m.group(2))
        return m.group(0)[: m.start(2) - m.start(0)] + "〔引文〕" + m.group(0)[m.end(2) - m.start(0):]
    return QUOTE.sub(repl, text), quotes


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。；;！!？?])", text)
    return [p for p in (s.strip() for s in parts) if p]


ATTACHMENT_TAIL = re.compile(
    r"^(附件|附錄|附录|附[:：]|附\s*[一二三四五六七八九十\d]|证据(清单|目录|材料|材料清单)|附证据|随附材料|附送材料)")
"""The attachment list that closes a filing. It names documents rather than asserting the author's own claims, so
it is not part of the addressee block: a first-instance court named there is a citation, not the court addressed,
and its length is not part of any section's length contract. A paragraph that is itself a registered heading is
never treated as the tail, so a package whose deliverable really contains a 证据清单 section keeps it."""


def sections(paras: list[Para], headings: dict[str, list[str]]) -> dict[str, list[Para]] | None:
    """Split by registered heading aliases; a heading paragraph starts with the alias and is short.

    Returns None when a heading alias matches in more than one place (unresolved location)."""
    marks: list[tuple[int, str]] = []
    for position, p in enumerate(paras):
        head = re.sub(r"^(第?[一二三四五六七八九十\d]+[、.．)）]|[（(][一二三四五六七八九十\d]+[)）])", "", nonspace(p.text))
        for name, aliases in headings.items():
            if any(head.startswith(a) and (len(head) <= len(a) + 1 or head[len(a)] in "：:") for a in aliases):
                marks.append((position, name))
                break
    counts: dict[str, int] = {}
    for _, name in marks:
        counts[name] = counts.get(name, 0) + 1
    resolved = [(start, name) for start, name in marks if counts[name] == 1]
    if not resolved:
        return None
    boundaries = [start for start, _ in marks]
    out: dict[str, list[Para]] = {"__head__": paras[:marks[0][0]] if marks else list(paras)}
    for start, name in resolved:
        end = next((b for b in boundaries if b > start), len(paras))
        out[name] = paras[start:end]
    if marks:
        heading_positions = set(boundaries)
        last_name, last_start = resolved[-1][1], resolved[-1][0]
        for position in range(last_start + 1, len(paras)):
            if position in heading_positions:
                continue
            if ATTACHMENT_TAIL.search(nonspace(paras[position].text)):
                out[last_name] = paras[last_start:position]
                out["__tail__"] = paras[position:]
                break
    return out


_CHINESE_ORDINAL = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
_NUMBERED_HEADING = re.compile(r"^(?:证据)?(?:第)?([1-9]|[一二三四五六七八九十])(?:[、.．)）:：，,]|项证据|组证据|号证据|$)")
_SIGNATURE_LEAD = re.compile(r"^(答辩人|原告|被告|上诉人|被上诉人|申请人|被申请人|异议人|代理人)[：:]|^日期[：:]"
                             # A document-level closing heading, 此致 or the 质证人 line also ends the last exhibit.
                             r"|^[一二三四五六七八九十]+[、.．](综合|结论|总结|质证结论)|^(综合|结论|总结)(质证)?(意见|结论)?(及请求)?[:：]?$"
                             r"|^此致$|^质证人[（(:：]|^(结论[:：])?综上[，,]?(原告|彭某)[^。]{0,6}(提交的?)?[^。]{0,8}证据")


def numbered_evidence_sections(paras: list[Para], count: int) -> dict[str, list[Para]] | None:
    """Split a numbered-item document (证据1..证据N each opened by its own ordinal) into named
    regions 'E1'..'E{count}' by **list position**, not by `Para.index` (the raw document index
    skips blank paragraphs, so slicing by `.index` silently misaligns whenever a submission
    contains blank lines between items -- this function slices the already-filtered `paras`
    list by enumerate() position instead). A heading is a paragraph whose text opens with an
    Arabic or Chinese ordinal 1..count immediately followed by a delimiter, '项证据'/'组证据'/
    '号证据', or nothing else (a bare '证据一'). A trailing signature block ('答辩人：', '日期：',
    etc.) inside the last matched section is carved out into '__tail__' so it is never scored
    or counted toward that item's shape. Returns None (unresolved) when a marker repeats, the
    markers are not in strictly ascending 1..count order, or an expected ordinal is missing --
    ambiguous location per notes/04c-program-judge-template.md #2."""
    def collect(explicit_only: bool) -> list[tuple[int, int]]:
        found: list[tuple[int, int]] = []
        for position, p in enumerate(paras):
            flat = nonspace(p.text)
            m = _NUMBERED_HEADING.match(flat)
            if not m:
                continue
            if explicit_only and not flat.startswith(("证据", "第")):
                continue
            raw = m.group(1)
            number = _CHINESE_ORDINAL.get(raw) if raw in _CHINESE_ORDINAL else int(raw)
            if 1 <= number <= count:
                found.append((position, number))
        return found

    def usable(found: list[tuple[int, int]]) -> bool:
        numbers = [n for _, n in found]
        return (len(set(numbers)) == len(numbers) and sorted(numbers) == numbers
                and set(numbers) == set(range(1, count + 1)))

    # A submission may number its items as "证据一：…" while also using "一、" for ordinary section
    # headings; prefer the explicit 证据/第N号证据 markers and fall back to bare ordinals (Golden's form).
    marks = collect(True)
    if not usable(marks):
        marks = collect(False)
    numbers = [n for _, n in marks]
    if len(set(numbers)) != len(numbers) or sorted(numbers) != numbers or set(numbers) != set(range(1, count + 1)):
        return None
    out: dict[str, list[Para]] = {"__head__": paras[:marks[0][0]]}
    for k, (start, number) in enumerate(marks):
        end = marks[k + 1][0] if k + 1 < len(marks) else len(paras)
        out[f"E{number}"] = paras[start:end]
    last_key = f"E{marks[-1][1]}"
    last = out[last_key]
    for j, p in enumerate(last):
        if j > 0 and _SIGNATURE_LEAD.match(nonspace(p.text)):
            out["__tail__"] = last[j:]
            out[last_key] = last[:j]
            break
    return out


def compile_groups(groups: list[list[str]]) -> list[re.Pattern]:
    return [re.compile("|".join(f"(?:{g})" for g in group)) for group in groups]


_THOUSANDS_COMMA = re.compile(r"(?<=\d)[,，](?=\d)")
BRACKETED = re.compile(r"[（(【\[][^）)】\]]{0,80}[）)】\]]")


PREDICATION_TAIL = re.compile(
    r"(清楚|充分|正确|合法|成立|无误|适当|适法|合理|维持|不当|错误|一致|属实|有据|无据|有效|无效|"
    r"支持|驳回|承担|负担|采信|采纳|确认|认可|不符|相符|齐备|完备|缺乏|不足|违法|违规)$")
"""Chinese legal writing closes a clause with its judgement. A run of short clauses that each end in one of
these is a chain of predications ("认定事实清楚，证据充分，适用法律正确，审判程序合法，依法应予维持"), not a
keyword list, and treating it as spray would discard the author's own conclusion."""


def is_keyword_spray(sentence: str) -> bool:
    """Bare keyword lists: at least five clauses whose median length is at most six characters, AND no clause is
    long enough to be a genuine piece of reasoning prose.

    A thousands-separator comma inside a number (``4,468,031``) is not a clause boundary; splitting on it would
    shred one long figure into several short digit fragments and could misclassify an ordinary sentence that
    happens to cite a grouped number next to a short enumeration (e.g. a heading fused with a five-item cost
    list) as keyword spray.

    The longest-clause gate matters for the same reason: a reasoned sentence that happens to close with a short
    itemised list (e.g. "...造价应全额计入措施费、管理费、规费、利润和税金。") still carries one long clause of real
    argument before the list, so its median clause length can dip to the same range as a bare list purely because
    a legitimate one-word paraphrase (以及→和) shaved a character off the last item. A true bare list has no
    clause longer than about ten characters anywhere in it, so requiring the longest clause to stay short as well
    as the median keeps the detector aimed at real spray without being tripped by a one-character synonym swap
    inside a reasoned claim."""
    sentence = _THOUSANDS_COMMA.sub("", sentence)
    clauses = [c for c in re.split(r"[，、；：,;:/|\s]+", sentence) if c]
    if len(clauses) < 5:
        return False
    lengths = sorted(len(c) for c in clauses)
    if not (lengths[len(lengths) // 2] <= 6 and lengths[-1] <= 12):
        return False
    # Short clauses alone do not make a keyword list: a chain of predications is prose (see PREDICATION_TAIL).
    # The share matters, not the count -- a 40-term keyword bag happens to contain a few predicate-ending terms
    # ("自行承担", "交易因果关系不成立"), so prose requires most of its clauses to end in a judgement.
    predications = sum(1 for c in clauses if PREDICATION_TAIL.search(c))
    return predications < max(3, (len(clauses) + 1) // 2)


def lead_excluded(para: Para, lead_exclusions: list[str]) -> bool:
    """A paragraph introduced as a candidate, a hypothesis or the other side's position is excluded as a whole."""
    head = nonspace(para.text)
    return any(re.search(p, head) for p in lead_exclusions)


def find_proposition(paras: list[Para], groups: list[list[str]], exclude: list[str], generic_exclude: list[str],
                     vocabulary, max_chars: int, sentence_window: int, lead_exclusions=()):
    """Return (best_group_hits, total_groups, evidence) over bounded windows of adjacent sentences.

    A sentence is unusable when it matches an item exclusion (negation, wrong object, rejection) or a generic
    exclusion (candidate, quotation of the other side, hedged option), or when it is keyword spray."""
    compiled = compile_groups(groups)
    ex = re.compile("|".join(f"(?:{e})" for e in exclude + generic_exclude)) if exclude + generic_exclude else None
    best = (0, None)
    # One evidence item's opinion is routinely written as a short stance paragraph ("对真实性不予认可。") whose
    # reasons live in the numbered sub-paragraph that follows, or as a reason paragraph whose conclusion is drawn
    # in the very next "综上…" paragraph. Sliding the window inside a single paragraph only, the two halves of one
    # adopted proposition could never meet, so a correct answer would score zero purely for using two <p> instead
    # of one.
    # The window therefore runs over the sentences of a paragraph AND the one immediately following it in the
    # same region. Locality is still enforced by max_chars, which truncates the window, and by sentence_window;
    # a run never crosses a region boundary because `paras` is already one region. A paragraph that is excluded
    # as a whole (the other side's position) breaks the run, so its sentences never fuse with a neighbour's.
    runs: list[list[str]] = []
    pending: list[tuple] = []
    for p in paras:
        if lead_excluded(p, list(lead_exclusions)):
            pending = []
            continue
        own, _ = strip_authority_quotes(p.text, keep_embedded=True)
        sents = sentences(own)
        usable = [s for s in sents if not (ex and ex.search(nonspace(s))) and not is_keyword_spray(s)]
        pending.append((p, usable))
        if len(pending) > 2:
            pending = pending[-2:]
        runs.append([pending[0][0], [s for _q, ss in pending for s in ss]])
    for p, usable in runs:
        for i in range(len(usable)):
            window = "".join(usable[i:i + sentence_window])
            flat = nonspace(window)
            if len(flat) > max_chars:
                flat = flat[:max_chars]
            # Amounts are matched with and without thousands separators: "8,061,635.72元" and "8061635.72元" are
            # the same figure, and a registered pattern written in one style must not miss the other.
            degrouped = re.sub(r"(?<=\d)[,，](?=\d{3}(?!\d))", "", flat)
            hits = sum(1 for g in compiled if g.search(flat) or g.search(degrouped))
            if hits > best[0]:
                best = (hits, (p, window))
                if hits == len(compiled):
                    return hits, len(compiled), best[1]
    return best[0], len(compiled), best[1]


DATE = re.compile(r"(?:(\d{4})\s*年\s*)?(\d{1,2})\s*月\s*(\d{1,2})\s*日")
# A month with an empty day is still an asserted date fragment.  It is not a
# valid date and cannot be silently treated as a harmless signature blank.
PARTIAL_DATE = re.compile(r"(?:(\d{4})\s*年\s*)?(\d{1,2})\s*月(?!\s*\d{1,2}\s*日)")
AMOUNT = re.compile(r"(?<!\d)(?<!\d[,，.])(\d{1,3}(?:[,，]\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*(亿元|万元|元)")
LONG_NUMBER = re.compile(r"\d{11,}")
PERIOD = re.compile(r"(?<![\d.])(\d{1,3})\s*(个月|日|天|年)")
PLACEHOLDER = re.compile(
    r"[×xX＊*_＿]{2,}"            # masked identifiers
    r"|【[^】]{0,30}】|〔[^〕]{0,30}〕|\[[^\]]{0,30}\]|［[^］]{0,30}］"   # bracketed placeholder of any style
    r"|（[待占][^）)]{0,12}[）)]|\([待占][^）)]{0,12}\)"                  # （待确认）/（占位）
    r"|待补充|待确认|待核实|占位符?|placeholder|PLACEHOLDER|某某"
)
"""Accepted placeholder forms: a fact the Materials do not establish must be marked
as a placeholder rather than invented, and every listed form counts as such a marking."""



REJECTED_FIGURE = re.compile(
    r"不认可|不予认可|不予采纳|不应采纳|不予支持|不能成立|不予采信|无(任何)?(事实|法律)?(依据|根据)|系(错误|虚高)|明显(错误|偏高|偏低)")
"""A figure the author explicitly rejects is the other side's number, not the author's own assertion, so it is
not a fabricated specific. Unlike an attribution test this needs no knowledge of which party is writing: a
defence that says "答辩人不认可原告以…计算的212000元" is quoting the figure in order to contest it."""


HEDGE = re.compile(r"约|大约|近|接近|左右|余|上下|概(算|数)")


def specifics(text: str) -> list[tuple[str, str]]:
    """Dates, money amounts and long identifiers asserted in the author's own text (authority quotes removed)."""
    own, _ = strip_authority_quotes(text)
    own = PLACEHOLDER.sub("", own)
    # A figure inside a sentence the author uses to reject it belongs to the other side (rule R7).
    own = "".join(s for s in sentences(own) if not REJECTED_FIGURE.search(nonspace(s))) or ""
    found = []
    for m in DATE.finditer(own):
        found.append(("date", m.group(0)))
    for m in PARTIAL_DATE.finditer(own):
        if not any(start <= m.start() and m.end() <= end for start, end in [(x.start(), x.end()) for x in DATE.finditer(own)]):
            found.append(("date", m.group(0)))
    for m in AMOUNT.finditer(own):
        found.append(("amount", m.group(0)))
    for m in LONG_NUMBER.finditer(own):
        found.append(("identifier", m.group(0)))
    date_spans = [(m.start(), m.end()) for m in DATE.finditer(own)]
    for m in PERIOD.finditer(own):
        # The day component of a date ("2026年1月1日" -> "1日") is not a duration; reporting it as one charged
        # every date twice, once as a date the corpus establishes and once as a period it does not.
        if any(start <= m.start() and m.end() <= end for start, end in date_spans):
            continue
        # The closing day of a date range ("2020年9月18日至22日") is a calendar day, not a duration.
        if own[max(0, m.start() - 1):m.start()] in ("至", "到", "-", "—", "～", "~", "、") and \
                any(end <= m.start() and m.start() - end <= 12 for _start, end in date_spans):
            continue
        found.append(("period", m.group(0)))
    return found


def date_key(value: str):
    m = DATE.search(value)
    return (m.group(1), int(m.group(2)), int(m.group(3))) if m else None


def amount_key(value: str):
    m = AMOUNT.search(value)
    if not m:
        return None
    number = float(re.sub(r"[,，]", "", m.group(1)).rstrip("."))
    return round(number * {"亿元": 100000000, "万元": 10000}.get(m.group(2), 1), 2)


#: Quotation/accounting tables (e.g. materials/3.证据材料.docx's 投标报价汇总表) express money as a bare
#: two-decimal figure inside a table cell, with the currency word only in the column header ("金额(元)"),
#: never glued onto the individual figure the way prose would write "5306841.08元". Without this, every
#: real, verifiable table total would be judged "unsupported" the moment a candidate quotes it in prose
#: with a normal 元/万元 unit -- a false positive, not a real fabrication. Recognizing a bare two-decimal
#: number as a materials-established amount only widens what counts as SUPPORTED; it never changes what a
#: candidate's own text must look like to be scanned as a claimed amount (specifics() is untouched).
BARE_TABLE_AMOUNT = re.compile(r"(?<!\d)\d+\.\d{1,2}(?!\d)")
"""One OR two decimals. A quotation table may drop a trailing zero (临时设施 102607.8, 综合单价 1783.7), so a
two-decimal-only pattern would judge every figure the table writes with one decimal as unsupported the moment a
candidate quotes it back in prose with the conventional trailing zero (102607.80元), although the table does
establish it. Widening what the CORPUS establishes never changes what a candidate's own text must look like to be
scanned (specifics() is untouched)."""



CN_DIGIT = {"〇": 0, "零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
            "壹": 1, "贰": 2, "叁": 3, "肆": 4, "伍": 5, "陆": 6, "柒": 7, "捌": 8, "玖": 9, "0": 0, "1": 1,
            "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9}
CN_DATE = re.compile(r"([〇零○0-9一二三四五六七八九]{2,4})\s*年\s*([一二三四五六七八九十]{1,3})\s*月\s*"
                     r"([一二三四五六七八九十]{1,3})\s*日")
COMPACT_DATE = re.compile(r"(?<!\d)(20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?!\d)")


def _cn_date_number(token: str) -> int:
    """Chinese numerals for 1-31 (month and day-of-month), not the digit-by-digit reading used for the year.

    Kept apart from the period counters that also accept 两 ("两年"): a month or a day of the month never
    takes 两."""
    if len(token) == 1:
        return 10 if token == "十" else CN_DIGIT[token]
    if len(token) == 2 and token[0] == "十":
        return 10 + CN_DIGIT[token[1]]
    if len(token) == 2 and token[1] == "十":
        return CN_DIGIT[token[0]] * 10
    if len(token) == 3 and token[1] == "十":
        return CN_DIGIT[token[0]] * 10 + CN_DIGIT[token[2]]
    raise ValueError(token)


def cn_numeral_dates(text: str):
    """Dates written in Chinese numerals, as the (year, month, day) tuples `corpus_facts` stores."""
    out = set()
    for m in CN_DATE.finditer(text):
        try:
            year = "".join(str(CN_DIGIT[c]) for c in m.group(1).replace("○", "〇"))
            out.add((year, _cn_date_number(m.group(2)), _cn_date_number(m.group(3))))
        except (KeyError, ValueError):
            continue
    return out


def corpus_facts(texts: list[str]):
    """Dates, amounts, identifiers and periods visible to both parties (Materials plus instruction)."""
    dates, amounts, ids, periods = set(), set(), set(), set()
    for t in texts:
        flat = nonspace(t)
        for m in DATE.finditer(flat):
            dates.add((m.group(1), int(m.group(2)), int(m.group(3))))
        for m in re.finditer(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", flat):
            dates.add((m.group(1), int(m.group(2)), int(m.group(3))))
        # Judgment signature blocks date themselves in Chinese numerals and statement headers use 8 digits;
        # a submission that transcribes either faithfully must not be charged with fabricating it.
        dates |= cn_numeral_dates(t)
        for m in _MIXED_CN_MONTH_DATE.finditer(flat):
            month = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
                     "十一": 11, "十二": 12}.get(m.group(2))
            if month:
                dates.add((m.group(1), month, int(m.group(3))))
        for m in COMPACT_DATE.finditer(flat):
            dates.add((m.group(1), int(m.group(2)), int(m.group(3))))
        for m in re.finditer(r"(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})", t):
            month = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
                     "October", "November", "December"].index(m.group(2)) + 1
            dates.add((m.group(3), month, int(m.group(1))))
        for m in AMOUNT.finditer(flat):
            amounts.add(amount_key(m.group(0)))
        # Table cells state money without 元 ("| 141659311.00 |"); a two-decimal cell is an amount.
        for m in re.finditer(r"(?<=\|)(\d{1,3}(?:,\d{3})+\.\d{2}|\d{3,}\.\d{2})(?=\|)", flat):
            amounts.add(round(float(m.group(1).replace(",", "")), 2))
        for m in BARE_TABLE_AMOUNT.finditer(flat):
            amounts.add(round(float(m.group(0)), 2))
        ids.update(LONG_NUMBER.findall(flat))
        periods.update((m.group(1), m.group(2)) for m in PERIOD.finditer(flat))
    return dates, amounts, ids, periods


def supported(kind: str, value: str, facts) -> bool:
    dates, amounts, ids = facts[0], facts[1], facts[2]
    periods = facts[3] if len(facts) > 3 else set()
    if kind == "period":
        m = PERIOD.search(value)
        return bool(m) and (m.group(1), m.group(2)) in periods
    if kind == "date":
        y, mo, d = date_key(value)
        return any(mo == fm and d == fd and (y is None or fy is None or y == fy) for fy, fm, fd in dates)
    if kind == "amount":
        return amount_key(value) in amounts
    return value in ids



SUM_MARKER = re.compile(r"合计|共计|总计|小计|累计|合并计算|总额|之和|相加|合共")
ARITHMETIC_MARKER = re.compile(
    r"合计|共计|总计|小计|累计|合并|之和|相加|相差|差额|差异|价差|差价|之差|超出|超过|高于|低于|多于|少于|扣除|扣减|减去|扣回|增加|加上|上浮|下浮"
    r"|折算|分摊|按[^。；]{0,8}[％%]|[％%]")
PERCENT = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*[％%]")


def _paragraph_amounts(text: str) -> list[float]:
    own, _ = strip_authority_quotes(text)
    own = PLACEHOLDER.sub("", own)
    keys = [amount_key(m.group(0)) for m in AMOUNT.finditer(nonspace(own))]
    return [k for k in keys if k is not None]


ANAPHORIC_OPERAND = re.compile(r"(该|上述|前述|以上)(合计|总|总计)?(金额|数额|总额|价款|款项|合计)")


def stated_derivations(paras: list[Para], established: set) -> set:
    """Amounts whose arithmetic the submission states in the same sentence as the result.

    Two shapes count, and both require the operands to be visible next to the result: a percentage share, when
    that percentage is written in the same sentence as an established base; and a sum or difference, when both
    operands appear in the same sentence together with a summation or difference marker. Requiring the operands
    to be shown is what separates a derivation from a coincidence: over a corpus with many amounts, some
    combination equals almost any number, so an existence check alone would excuse fabricated figures.

    One operand may be named by reference instead of repeated: "该合计金额已超出合同价款X元约Y元" points back to
    the total that closes the preceding paragraph, so when a sentence carries such a reference the amounts of
    the preceding paragraph's last sentence join its operands."""
    found: set = set()
    previous_tail: list[float] = []
    for para in paras:
        own, _ = strip_authority_quotes(para.text)
        para_sentences = sentences(nonspace(own))
        for sentence in para_sentences:
            if not ARITHMETIC_MARKER.search(sentence):
                continue
            values = _paragraph_amounts(sentence)
            if ANAPHORIC_OPERAND.search(sentence):
                values = values + [v for v in previous_tail if v not in values]
            base = established | found
            for target in values:
                if target in base or target in found:
                    continue
                for text_pct in PERCENT.finditer(sentence):
                    pct = float(text_pct.group(1))
                    if any(abs(b * pct / 100 - target) < 0.01 for b in base):
                        found.add(target)
                        break
                if target in found:
                    continue
                operands = [v for v in values if v != target and v in base]
                # A hedged result ("约1332000元" for 2814000 − 1482040 = 1331960) may differ from the exact sum or
                # difference by the precision it is stated to, and no more (see _stated_precision).
                slack = _stated_precision(sentence, target) / 2 if HEDGE.search(sentence) else 0.01
                for a in operands:
                    for b in operands:
                        if abs(a + b - target) <= slack or abs(a - b - target) <= slack:
                            found.add(target)
                            break
                    if target in found:
                        break
        if para_sentences:
            previous_tail = _paragraph_amounts(para_sentences[-1])
    return found

def _stated_precision(text: str, target: float) -> float:
    """Half-width basis for a hedged amount: the unit of its last significant stated digit, in 元."""
    flat = nonspace(text)
    for m in AMOUNT.finditer(flat):
        if amount_key(m.group(0)) != target:
            continue
        digits = re.sub(r"[,，]", "", m.group(1))
        scale = {"亿元": 100000000.0, "万元": 10000.0}.get(m.group(2), 1.0)
        if "." in digits:
            return scale * 10 ** -len(digits.split(".")[1].rstrip("0") or "0") if digits.split(".")[1].rstrip("0") else scale
        stripped = digits.rstrip("0")
        return scale * 10 ** (len(digits) - len(stripped))
    return 1.0


def reconciled_totals(paras: list[Para], established: set, window: int = 14) -> set:
    """Totals the document marks as totals and that add up from the established amounts listed with them.

    A drafter who writes "以下九项签证合计482,411.60元" and then itemises the nine amounts states an arithmetic
    consequence of facts already in evidence, not a new fact, so the total must not be charged as a fabricated
    specific. The reconciliation is verified rather than taken on the author's word: the total has to equal the
    sum of a contiguous run of at least two established component amounts appearing in the same paragraph or in
    the following `window` paragraphs. A total that does not reconcile stays unsupported."""
    found: set = set()
    for i, para in enumerate(paras):
        if not SUM_MARKER.search(nonspace(para.text)):
            continue
        own = _paragraph_amounts(para.text)
        # The components may be listed before the total ("以上九项合计…元") or after it ("以下九项…合计…元"),
        # so the window reaches in both directions.
        pool: list[float] = []
        for q in paras[max(0, i - window):i + window + 1]:
            pool += _paragraph_amounts(q.text)
        for target in own:
            if target in established or target in found:
                continue
            components = sorted({a for a in pool if a != target and (a in established or a in found)})
            if _subset_sum(components, int(round(target * 100))):
                found.add(target)
                continue
            # A hedged total is a rounded statement of the same sum (rule R8): the components still have to be
            # established and to add up, but to one percent rather than to the cent.
            if HEDGE.search(nonspace(para.text)):
                # The slack a hedge buys is the precision the figure is stated to, not a flat percentage: "约1570万元"
                # is rounded to 10万 and may sit 5万 either side, but "约4617185.92元" is stated to the fen and
                # buys nothing. A flat one-percent band would let many candidate amounts coincidentally bracket a
                # figure nobody derived.
                tolerance = _stated_precision(para.text, target) / 2
                if _subset_sums_in_range(components, int(round((target - tolerance) * 100)),
                                         int(round((target + tolerance) * 100))):
                    found.add(target)
    return found


def _subset_sums_in_range(values: list[float], lo_cents: int, hi_cents: int, max_values: int = 26) -> bool:
    """True when at least two of `values` add up to an amount in [lo_cents, hi_cents] (integer cents).

    Exact meet-in-the-middle: the candidates are split into two halves, every subset sum of each half is
    enumerated with its element count, and each left sum looks up a matching right sum by bisection. At most
    `max_values` candidates are considered, so the work is bounded by 2 x 2^13 enumerations whatever the size of
    the amounts. A dictionary search over distinct partial sums would grow with the amounts and not finish on a
    securities filing whose amounts run to hundreds of millions."""
    from bisect import bisect_left, bisect_right
    candidates = sorted({int(round(v * 100)) for v in values if 0 < round(v * 100) <= hi_cents},
                        reverse=True)[:max_values]
    half = len(candidates) // 2

    def enumerate_half(items):
        sums = [(0, 0)]
        for cents in items:
            sums += [(s + cents, c + 1) for s, c in sums if s + cents <= hi_cents]
        return sums

    left = enumerate_half(candidates[:half])
    right = enumerate_half(candidates[half:])
    by_min_count = {k: sorted(s for s, c in right if c >= k) for k in (0, 1, 2)}
    for s, c in left:
        need = max(0, 2 - c)
        pool = by_min_count[need]
        i = bisect_left(pool, lo_cents - s)
        if i < len(pool) and pool[i] <= hi_cents - s:
            return True
    return False


def _subset_sum(values: list[float], target_cents: int, max_values: int = 26) -> bool:
    """True when at least two of `values` add up to exactly `target_cents` (see _subset_sums_in_range)."""
    return _subset_sums_in_range(values, target_cents, target_cents, max_values)


def with_document_derivations(facts, paras: list[Para], rounds: int = 4):
    """`facts` extended with the amounts the submission shows the derivation of.

    Two rounds let a total built from a subtotal that was itself shown reconcile as well. Only values whose
    arithmetic the document presents are added; nothing is accepted merely because some combination of corpus
    amounts happens to equal it."""
    dates, amounts, ids = set(facts[0]), set(facts[1]), set(facts[2])
    rest = tuple(facts[3:])
    for _ in range(rounds + 1):
        if rest:
            rest = (set(rest[0]) | date_difference_periods(paras, dates),) + tuple(rest[1:])
        pending = (reconciled_totals(paras, amounts) | stated_derivations(paras, amounts)
                   | document_operand_derivations(paras, amounts)
                   | unit_rate_derivations(paras, amounts) | document_pair_totals(paras, amounts)
                   | written_computations(paras) | table_row_derivations(paras, set(facts[1]))
                   | judgment_reference_differences(paras, set(facts[1]), amounts)) - amounts
        pending_dates = written_date_computations(paras, dates) - dates
        if not pending and not pending_dates:
            break
        amounts |= pending
        dates |= pending_dates
    return (dates, amounts, ids) + rest



# ---------------------------------------------------------------------------------------------------------------
# Document-operand derivations. A drafter who recomputes a figure often names its operands in another
# sentence of the same document ("还应支付605,894.06元" after stating the price and, elsewhere, the amount paid), or
# re-bases a figure by a percentage the document states ("按未下浮口径折算" at 65%). Such a result is derived, not
# invented, when it equals a sum, difference or stated-percentage transform of amounts that are both grounded and
# written in this document, and the result's own sentence carries derivation wording. The operands must appear in the
# submission (never the whole corpus), which keeps a fabricated figure from being excused by a coincidence among the
# many corpus amounts; three-term sums are limited to operands of the same or the preceding paragraph.

_DERIVATION_CUE = re.compile(
    r"增加|减少|差额|相差|之差|还应|尚应|尚欠|应付|应支付|应返还|应为|折算|基数|合计|共计|总计|损失|计算|扣除|扣减|剔除|计入|"
    r"减去|超出|较[^。；]{0,8}(增加|减少|多|少)|余额|备位|口径|每股|单价|×|÷|＝|=")


def _cents(value: float) -> int:
    return int(round(value * 100))


def document_operand_derivations(paras: list[Para], established: set) -> set:
    found: set = set()
    para_amounts = [_paragraph_amounts(p.text) for p in paras]
    doc_pool = sorted({v for vals in para_amounts for v in vals if v in established and v > 0})
    pool_cents = {_cents(v) for v in doc_pool}
    corpus_pool = sorted(v for v in established if v and v > 0)

    def near(cents: int, tol: int) -> bool:
        return any((cents + d) in pool_cents for d in range(-tol, tol + 1))

    for k, para in enumerate(paras):
        own, _ = strip_authority_quotes(para.text)
        flat_para = nonspace(own)
        local_text = (nonspace(paras[k - 1].text) if k else "") + flat_para
        percents = sorted({float(m.group(1)) / 100 for m in PERCENT.finditer(local_text) if 0 < float(m.group(1)) < 100})
        local = sorted({v for vals in (para_amounts[k - 1] if k else [], para_amounts[k]) for v in vals if v in (established | found) and v > 0})
        for sentence in sentences(flat_para):
            if not _DERIVATION_CUE.search(sentence):
                continue
            for target in _paragraph_amounts(sentence):
                if target in established or target in found or target <= 0:
                    continue
                t = _cents(target)
                # Hedged figures tolerate their stated precision, capped at 1元 so a "约X亿元" cannot open a range of
                # billions of cents.
                tol = min(100, max(2, int(_stated_precision(sentence, target) * 50))) if HEDGE.search(sentence) else 2
                ok = False
                for a in doc_pool:
                    ac = _cents(a)
                    if a != target and (near(t - ac, tol) or near(ac - t, tol) or near(t + ac, tol)):
                        ok = True
                        break
                    for p in percents:
                        if near(_cents(target + a * p), tol) or near(_cents(a * p - target), tol):
                            ok = True
                            break
                    if ok:
                        break
                if not ok and percents:
                    # A percentage re-base or its difference ("按未下浮口径折算", "差额") may start from a grounded amount the
                    # document does not repeat; the percentage itself must be written in this or the preceding paragraph.
                    for a in corpus_pool:
                        for p in percents:
                            if abs(a * p - target) * 100 <= tol or abs(a / p - target) * 100 <= tol \
                                    or abs(a / p - a - target) * 100 <= tol or abs(a - a * p - target) * 100 <= tol:
                                ok = True
                                break
                        if ok:
                            break
                if not ok and re.search(r"合计|共计|总计", sentence):
                    # "各项差额合计869,073.69元（A元、B元……）": the total of the other grounded amounts in the same sentence.
                    others = [v for v in _paragraph_amounts(sentence) if v != target and v in (established | found)]
                    if len(others) >= 2 and (abs(_cents(sum(others)) - t) <= tol or _subset_sum(others, t)):
                        ok = True
                if not ok and len(local) <= 60:
                    local_cents = {_cents(v) for v in local}
                    for i, a in enumerate(local):
                        for b in local[i + 1:]:
                            rest = t - _cents(a) - _cents(b)
                            if any((rest + d) in local_cents or (-rest + d) in local_cents for d in range(-tol, tol + 1)) \
                                    or near(rest, tol):
                                ok = True
                                break
                        if ok:
                            break
                if ok:
                    found.add(target)
    return found


def date_difference_periods(paras: list[Para], established_dates: set) -> set:
    """Day counts stated as the difference of two grounded dates in the same or the preceding sentence of a paragraph
    ("自2022年4月30日……自2022年10月19日……两者相差约172天"); exact, or within 1 day, or 3 when hedged."""
    import datetime
    found: set = set()
    for para in paras:
        own, _ = strip_authority_quotes(para.text)
        para_sentences = sentences(nonspace(own))
        for k, sentence in enumerate(para_sentences):
            periods = [m for m in PERIOD.finditer(sentence) if m.group(2) in ("日", "天")]
            if not periods:
                continue
            context = "".join(para_sentences[max(0, k - 2):k + 1])
            dates = []
            for m in DATE.finditer(context):
                key = (m.group(1), int(m.group(2)), int(m.group(3)))
                if key[0] and any(key[1:] == b[1:] and (b[0] is None or b[0] == key[0]) for b in established_dates):
                    try:
                        dates.append(datetime.date(int(key[0]), key[1], key[2]))
                    except ValueError:
                        pass
            loose = 3 if HEDGE.search(sentence) else 1
            for m in periods:
                n = int(m.group(1))
                if any(abs(abs((a - b).days) - n) <= loose for a in dates for b in dates if a != b):
                    found.add((m.group(1), m.group(2)))
    return found


def material_texts(materials: Path) -> list[str]:
    texts = []
    for f in sorted(materials.rglob("*")):
        if f.suffix.lower() == ".docx":
            texts.append("\n".join(p.text for p in read_paragraphs(f)))
        elif f.suffix.lower() in (".md", ".txt"):
            texts.append(f.read_text(encoding="utf-8", errors="ignore"))
    return texts

_LABELLED_HEADING = re.compile(r"^(?:[（(]?[一二三四五六七八九十]+[)）、.．]|\d{1,2}[、.．)）])?证据((?:(?:1[0-9]|[1-9]|十[一二三四五六七八九]?|[一二三四五六七八九])"
                               r"(?:[、,，和及至—\-~～]|$|(?=[:：（(《\s])))+)")
_LABEL_NUMBER = re.compile(r"1[0-9]|[1-9]|十[一二三四五六七八九]?|[一二三四五六七八九]")


def _label_numbers(label: str) -> list[int]:
    raw = [_CHINESE_ORDINAL.get(x, None) if not x.isdigit() else int(x) for x in _LABEL_NUMBER.findall(label)]
    nums = [n for n in raw if n]
    if re.search(r"[至—\-~～]", label) and len(nums) == 2 and nums[0] < nums[1]:
        return list(range(nums[0], nums[1] + 1))
    return nums


def labelled_evidence_sections(paras: list[Para], count: int) -> dict[str, list[Para]] | None:
    """Fallback split keyed by the evidence number written in each item heading ("（一）证据1：…", "证据5、证据6：…").

    Used only when the ordinal split cannot resolve, e.g. when a submission groups two exhibits under one heading,
    so its own ordinals no longer run 1..count. The heading
    must open the paragraph and be short; a grouped heading is visible to every exhibit it names. The labels must
    be strictly ascending without repeats, otherwise the location is unresolved; an exhibit the submission never
    heads simply has no region, so only the items bound to it lose credit."""
    marks: list[tuple[int, list[int]]] = []
    for position, p in enumerate(paras):
        # The same heading written differently: bracketed labels ("【证据一】…", "【证据五】至【证据十】："),
        # ranges that repeat the word ("证据5至证据10"), a "关于" lead ("一、关于证据1“…”") and a title quoted straight
        # after the label. Rewrite them to the plain "证据N：" form before parsing; the label rules themselves are unchanged.
        flat = nonspace(p.text)
        flat = re.sub(r"】\s*([至—\-~～])\s*【?证据", r"\1", flat)
        flat = re.sub(r"^【(证据[^】]{1,8})】", r"\1：", flat)
        flat = re.sub(r"([至—\-~～])证据", r"\1", flat)
        flat = re.sub(r"^((?:[（(]?[一二三四五六七八九十]+[)）、.．]|\d{1,2}[、.．)）])?)(?:关于|对于|针对|就|对)(?=证据)", r"\1", flat)
        flat = re.sub(r"^(.{0,6}?证据(?:1[0-9]|[1-9]|十[一二三四五六七八九]?|[一二三四五六七八九]))(?=[\"“「])", r"\1：", flat)
        m = _LABELLED_HEADING.match(flat)
        if not m or len(flat) > 80 or re.search(r"[。；;]$", flat):
            continue  # a sentence that merely opens with a label ("4.证据4“…”未随材料提交，无从质证。") is not a heading
        head = re.split(r"[:：《]", flat, maxsplit=1)[0]
        labels = re.findall(r"证据((?:1[0-9]|[1-9]|十[一二三四五六七八九]?|[一二三四五六七八九])(?:[至—\-~～](?:1[0-9]|[1-9]|十[一二三四五六七八九]?|[一二三四五六七八九]))?)", head)
        numbers = [n for label in labels for n in _label_numbers(label) if 1 <= n <= count]
        if numbers:
            marks.append((position, numbers))
    flat_numbers = [n for _, ns in marks for n in ns]
    if len(marks) < 2 or flat_numbers != sorted(set(flat_numbers)):
        return None
    out: dict[str, list[Para]] = {"__head__": paras[:marks[0][0]]}
    for k, (start, numbers) in enumerate(marks):
        end = marks[k + 1][0] if k + 1 < len(marks) else len(paras)
        for n in numbers:
            out[f"E{n}"] = paras[start:end]
    last_numbers = marks[-1][1]
    last = paras[marks[-1][0]:]
    for j, p in enumerate(last):
        if j > 0 and _SIGNATURE_LEAD.match(nonspace(p.text)):
            out["__tail__"] = last[j:]
            for n in last_numbers:
                out[f"E{n}"] = last[:j]
            break
    return out

# ---------------------------------------------------------------------------------------------------------------
# Written computations.
# A drafter who shows the computation -- "40000股×15.6元/股＝624,000元", "1,871,866.02元（1,216,712.91÷65%）",
# "自次日起算，十五日期满之日为2025年9月2日" -- has derived the figure, so correct products, quotients and deadlines
# are not charged as fabricated.
# The rule stays strict: the operands and the operator must be written next to the result, and the expression must
# evaluate to the result (to the fen, or to the stated precision of a hedged figure). A fabricated operand that is
# itself an amount is still charged on its own.

_EXPR_NUMBER = re.compile(r"(\d{1,3}(?:[,，]\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)(\s*万)?(\s*[％%])?")
_EXPR_OPERATOR = re.compile(r"[×xX＊*÷／/＋+－\-−]|乘以|除以")
_NOTE = re.compile(r"[（(][^（）()×÷＋+－\-−*/＝=]*[）)]")
_UNIT_DENOMINATOR = re.compile(r"(元|万元)?\s*[/／]\s*(股|天|日|月|年|秒|平方米|立方米|m³|㎡|吨|台|个|人|工日|次|份)")


def _evaluate_expression(expr: str):
    for _ in range(3):
        expr = _NOTE.sub("", expr)
    expr = _UNIT_DENOMINATOR.sub("", expr)
    tokens = []
    for m in re.finditer(r"(\d{1,3}(?:[,，]\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)(\s*万)?(\s*[％%])?|乘以|除以|[×xX＊*÷／/＋+－\-−]", expr):
        tok = m.group(0)
        if m.group(1):
            value = re.sub(r"[,，]", "", m.group(1))
            if m.group(2):
                value += "*10000"
            if m.group(3):
                value = "(" + value + "/100)"
            tokens.append(("n", value))
        elif tok in ("×", "x", "X", "＊", "*", "乘以"):
            tokens.append(("o", "*"))
        elif tok in ("÷", "/", "／", "除以"):
            tokens.append(("o", "/"))
        elif tok in ("＋", "+"):
            tokens.append(("o", "+"))
        else:
            tokens.append(("o", "-"))
    # Keep only the arithmetic run that ends the text: number (operator number)*. Running prose before it
    # ("对申请人主张的1,032,269.21元调减了1,032,269.21－967,031.24") contributes a stray number, not an operand.
    run = []
    for kind, value in reversed(tokens):
        if not run:
            if kind != "n":
                return None
            run.append(value)
        elif (kind == "o") == (len(run) % 2 == 1):
            run.append(value)
        else:
            break
    if run and len(run) % 2 == 0:
        run.pop()
    run.reverse()
    if len(run) < 3:
        return None
    text = "".join(run)
    if not re.fullmatch(r"[0-9.+\-*/()]+", text):
        return None
    try:
        return float(eval(text, {"__builtins__": {}}, {}))
    except Exception:
        return None

def _result_matches(value, target: float, sentence: str) -> bool:
    if value is None:
        return False
    slack = max(0.011, _stated_precision(sentence, target) / 2) if HEDGE.search(sentence) else 0.011
    return abs(value - target) <= slack


def written_computations(paras: list[Para]) -> set:
    """Amounts that close a written expression ("EXPR＝X元") or open one ("X元（EXPR）")."""
    found: set = set()
    for para in paras:
        own, _ = strip_authority_quotes(para.text)
        for sentence in sentences(nonspace(own)):
            if not _EXPR_OPERATOR.search(sentence):
                continue
            # Form A, "EXPR＝X元": explanatory notes without arithmetic ("（已进场材料费，系……第6页）") are removed
            # first, so their commas do not cut the expression short.
            cleaned = sentence
            for _ in range(3):
                cleaned = _NOTE.sub("", cleaned)
            for m in AMOUNT.finditer(cleaned):
                target = amount_key(m.group(0))
                if target is None or target in found:
                    continue
                before = cleaned[:m.start()]
                eq = max(before.rfind("＝"), before.rfind("="))
                if eq >= 0 and len(re.sub(r"[约为即合计共\s]", "", before[eq + 1:])) == 0:
                    cuts = [c.start() for c in re.finditer(r"[＝=：:；;]|(?<!\d)[，,]|[，,](?!\d)", before[:eq])]
                    start = cuts[-1] if cuts else -1
                    if _result_matches(_evaluate_expression(before[start + 1:eq]), target, sentence):
                        found.add(target)
            # Form B, "X元（EXPR）".
            for m in AMOUNT.finditer(sentence):
                target = amount_key(m.group(0))
                if target is None or target in found:
                    continue
                after = sentence[m.end():]
                paren = re.match(r"\s*[（(]([^（）()]*(?:[（(][^（）()]*[）)][^（）()]*)*)[）)]", after)
                if paren and _EXPR_OPERATOR.search(paren.group(1)):
                    expr = re.split(r"[＝=]", paren.group(1))[0]
                    if _result_matches(_evaluate_expression(expr), target, sentence):
                        found.add(target)
    return found


_CN_COUNT = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
_PERIOD_TEXT = re.compile(r"(\d{1,4}|[一二两三四五六七八九十]{1,3})\s*个?\s*(自然日|工作日|日|天|个月|月|年)(?![0-9]{1,2}日)")


def _count(token: str) -> int | None:
    if token.isdigit():
        return int(token)
    if token == "十":
        return 10
    if token.startswith("十"):
        return 10 + _CN_COUNT.get(token[1:], 0)
    if "十" in token:
        head, _, tail = token.partition("十")
        return _CN_COUNT.get(head, 0) * 10 + (_CN_COUNT.get(tail, 0) if tail else 0)
    return _CN_COUNT.get(token)


def _shift(date_tuple, amount: int, unit: str):
    import datetime
    year, month, day = date_tuple
    if year is None:
        return None
    try:
        base = datetime.date(int(year), month, day)
    except ValueError:
        return None
    if unit in ("日", "天", "自然日", "工作日"):
        return base + datetime.timedelta(days=amount)
    months = amount * 12 if unit == "年" else amount
    total = base.month - 1 + months
    y, mth = base.year + total // 12, total % 12 + 1
    for d in (day, 30, 29, 28):
        try:
            return datetime.date(y, mth, d)
        except ValueError:
            continue
    return None


def written_date_computations(paras: list[Para], established: set) -> set:
    """Dates stated as another date in the same sentence shifted by a period written in that sentence.

    Counting conventions differ by one day (the triggering day is excluded, "次日" starts the count), so the result
    may sit one day either side of the plain sum; working-day periods and hedged results ("左右") may sit three days
    either side. A year-less "8月31日" counts when its month and day match such a result."""
    import datetime
    found: set = set()
    for para in paras:
        own, _ = strip_authority_quotes(para.text)
        para_sentences = sentences(nonspace(own))
        for k, sentence in enumerate(para_sentences):
            # The anchor date is often stated in the sentence just before the count ("原告于X日收到裁定。自次日起算，
            # 十五日期满之日为Y日"), so anchors may come from the preceding sentence of the same paragraph; the
            # result and its period must still be written in this sentence.
            # The anchor and the period may sit anywhere earlier in the same paragraph ("有60天审核期限……
            # 即便于2021年1月7日提交……审核期满亦应在2021年3月8日左右"), and "期间开始之日不计入/起算" counts the day after.
            context = "".join(para_sentences[:k]) + sentence
            dates = [(m.group(1), int(m.group(2)), int(m.group(3))) for m in DATE.finditer(context)]
            if len(dates) < 2:
                continue
            periods = [(_count(m.group(1)), m.group(2)) for m in _PERIOD_TEXT.finditer(context)]
            periods = [(n, u) for n, u in periods if n]
            if re.search(r"次日|不计入|起算", context):
                periods.append((1, "日"))
            if not periods:
                continue
            base = established | found
            anchors = [d for d in dates if d[0] is not None and any(d[1:] == b[1:] and (b[0] is None or b[0] == d[0]) for b in base)]
            loose = 3 if (HEDGE.search(sentence) or "工作日" in sentence) else 1
            targets = [(m.group(1), int(m.group(2)), int(m.group(3))) for m in DATE.finditer(sentence)]
            for target in targets:
                if target in base:
                    continue
                for anchor in anchors:
                    if anchor == target:
                        continue
                    for n, unit in periods:
                        shifted = _shift(anchor, n, unit)
                        if shifted is None:
                            continue
                        for delta in range(-loose, loose + 1):
                            cand = shifted + datetime.timedelta(days=delta)
                            if (cand.month, cand.day) == target[1:] and (target[0] is None or int(target[0]) == cand.year):
                                found.add(target)
                                found.add((str(cand.year), cand.month, cand.day))
                                break
                        if target in found:
                            break
                    if target in found:
                        break
            # A result derived in this sentence can anchor a later result in the same sentence.
    return found

_JUDGMENT_REFERENCE = re.compile(r"(较|比|与)(原判|原审|一审判决|一审法院|原判决|判决)(认定|酌定|确定|判定|计算)?的?(同项)?(合计)?(数额|金额|价款|款项)")
_TABLE_NUMBER = re.compile(r"[＋+－\-−]?\s*(?:\d{1,3}(?:[,，]\d{3})+|\d+)(?:\.\d+)?")


def judgment_reference_differences(paras: list[Para], established: set, derived: set) -> set:
    """"X元，较原判认定数额增加Y元": Y is the difference between an amount written in the sentence and an amount the
    materials establish (the judgment's figure, named but not repeated). Only an explicit reference to the prior
    decision's figure opens this route, one operand must be written in the sentence, and the other must be a
    Materials amount, so a document-derived coincidence cannot supply it."""
    found: set = set()
    corpus = sorted(established)
    for para in paras:
        own, _ = strip_authority_quotes(para.text)
        for sentence in sentences(nonspace(own)):
            if not _JUDGMENT_REFERENCE.search(sentence):
                continue
            values = _paragraph_amounts(sentence)
            written = [v for v in values if v in established or v in derived or v in found]
            for target in values:
                if target in established or target in derived or target in found:
                    continue
                for a in written:
                    if a == target:
                        continue
                    if any(abs(abs(a - b) - target) <= 0.011 for b in corpus if b != a):
                        found.add(target)
                        break
    return found


def table_row_derivations(paras: list[Para], established: set) -> set:
    """Comparison tables ("|原判金额|改判金额|＋差额|"): a row whose signed change added to an established figure in
    the same row gives another figure in that row derives that figure."""
    found: set = set()
    for para in paras:
        text = para.text
        if text.count("|") < 2:
            continue
        cells = [c for c in text.split("|")]
        numbers = []
        for cell in cells:
            m = _TABLE_NUMBER.match(nonspace(cell))
            if m:
                raw = m.group(0)
                sign = -1 if raw.strip()[:1] in "－-−" else 1
                signed = raw.strip()[:1] in "＋+－-−"
                value = float(re.sub(r"[＋+－\-−,，\s]", "", raw))
                numbers.append((value, sign, signed))
        for a, _, a_signed in numbers:
            if a_signed or round(a, 2) not in established:
                continue
            for c, sign, c_signed in numbers:
                if not c_signed:
                    continue
                result = round(a + sign * c, 2)
                if any(abs(result - b) <= 0.011 for b, _, b_signed in numbers if not b_signed and b != a):
                    found.add(result)
    return found

_OPINION_LABEL = re.compile(r"^[（(]?[0-9一二三四五六七八九十]{1,2}[)）.．、]?(真实性|合法性|关联性|证明力|证明目的|结论|质证意见|[真合关][实法联]性[、及和与]?)+[:：]?$")


def merge_opinion_labels(paras: list[Para]) -> list[Para]:
    """Join a stand-alone opinion label ("1. 真实性", "3. 关联性及证明力") to the paragraph that follows it.

    The label names what the next paragraph is about; matching "真实性不予认可" against the opinion must see both,
    exactly as when the drafter writes "1. 真实性：不予认可……" on one line."""
    out: list[Para] = []
    pending = None
    for p in paras:
        flat = nonspace(p.text)
        if _OPINION_LABEL.match(flat):
            pending = p if pending is None else Para(pending.index, pending.path, pending.text + p.text)
            continue
        if pending is not None:
            label = re.sub(r"^[（(]?[0-9一二三四五六七八九十]{1,2}[)）.．、]?", "", nonspace(pending.text)).rstrip("：:")
            out.append(Para(p.index, p.path, label + "：" + p.text))
            pending = None
        else:
            out.append(p)
    if pending is not None:
        out.append(pending)
    return out

_UNIT_RATE = re.compile(r"(\d{1,3}(?:[,，]\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*元\s*[/／每]\s*(秒|吨|平方米|立方米|m³|㎡|个|台|天|日|月|股|米|千瓦时|度)")


def unit_rate_derivations(paras: list[Para], established: set, source_texts: list[str] | None = None) -> set:
    """Amounts that equal a quantity written in the same sentence times a unit rate the document or the materials
    state ("二期视频（60秒，对应合同款562,800元）" with "9,380元/秒" stated elsewhere). The rate must be written as a
    rate somewhere and the quantity must carry the rate's unit in the result's own sentence."""
    rates: dict[str, set] = {}
    texts = [nonspace(p.text) for p in paras] + [nonspace(t) for t in (source_texts or [])]
    for t in texts:
        for m in _UNIT_RATE.finditer(t):
            rates.setdefault(m.group(2), set()).add(float(re.sub(r"[,，]", "", m.group(1))))
    found: set = set()
    if not rates:
        return found
    for para in paras:
        own, _ = strip_authority_quotes(para.text)
        for sentence in sentences(nonspace(own)):
            quantities = []
            for unit in rates:
                for m in re.finditer(r"(\d{1,3}(?:[,，]\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*" + re.escape(unit) + r"(?![/／])", sentence):
                    quantities.append((unit, float(re.sub(r"[,，]", "", m.group(1)))))
            if not quantities:
                continue
            for m in AMOUNT.finditer(sentence):
                target = amount_key(m.group(0))
                if target is None or target in established:
                    continue
                if any(abs(q * r - target) <= 0.011 for unit, q in quantities for r in rates[unit]):
                    found.add(target)
    return found


_TOTAL_WORD = re.compile(r"合计|共计|总计|小计|之和")


def document_pair_totals(paras: list[Para], known: set) -> set:
    """A total stated with a summation word that equals the sum of exactly two amounts the same document already
    writes, wherever they stand ("…（6.2.6、6.2.7，合计1,096,244.44元）" with 280,899.49元 and 815,344.95元 given
    twenty paragraphs earlier). Restricted to totals stated to the fen with non-zero fen, where a coincidental pair
    among a document's amounts is negligible."""
    # Components are any amounts the document writes; one that is itself unsupported is charged on its own.
    doc_amounts = sorted({a for p in paras for a in _paragraph_amounts(p.text)})
    found: set = set()
    for para in paras:
        own, _ = strip_authority_quotes(para.text)
        for sentence in sentences(nonspace(own)):
            if not _TOTAL_WORD.search(sentence):
                continue
            for m in AMOUNT.finditer(sentence):
                target = amount_key(m.group(0))
                if target is None or target in known or round(target * 100) % 100 == 0:
                    continue
                cents = int(round(target * 100))
                pool = {int(round(a * 100)) for a in doc_amounts if a < target}
                if any((cents - a) in pool and (cents - a) != a for a in pool):
                    found.add(target)
    return found


_MIXED_CN_MONTH_DATE = re.compile(r"(\d{4})年?([一二三四五六七八九十]{1,3})月(\d{1,2})日")

GAP_MARKER = re.compile(
    r"[【〔\[［（(][^】〕\]］）)]{0,200}?(?:待补充|待确认|待核实|待定|占位|placeholder|PLACEHOLDER|TBD)[^】〕\]］）)]{0,200}?[】〕\]］）)]"
    r"|[【〔\[［][\s_＿]*[】〕\]］]"
    r"|[_＿]{2,}|待补充|待确认|待核实|占位符?|placeholder|PLACEHOLDER|TBD"
)
"""Gap-marker normalization (rule gap_marker_fold_v1): every declared marker form, including a bracketed span that
names what is missing, folds into one gap observation. Marker wording is never scored."""


def shape_chars(text: str) -> str:
    """Nonspace characters that count toward shape: gap-marker spans are removed before counting."""
    return nonspace(GAP_MARKER.sub("", text))


def gap_only(region) -> bool:
    """A region whose only content besides gap markers is short heading-like lines is a marked omission."""
    if not region or not any(GAP_MARKER.search(p.text) for p in region):
        return False
    residual = [shape_chars(p.text) for p in region]
    return all(len(r) <= 20 and not r.endswith(("。", "；", ";")) for r in residual)
