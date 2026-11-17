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
from dataclasses import dataclass
from pathlib import Path

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


@dataclass
class Para:
    index: int
    path: str
    text: str


# A Chinese document may carry its numerals fullwidth (１９３，４４０．５０元, ２０２４年, ３０％). Every
# reader below folds them to ASCII before any predicate runs -
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
        from lxml import etree
        with zipfile.ZipFile(artifact) as z:
            root = etree.fromstring(z.read("word/document.xml"))
        body = root.find(W + "body")
        out: list[Para] = []
        for n, child in enumerate(body):
            tag = child.tag.replace(W, "")
            if tag == "p":
                # A manual line break (<w:br/>, <w:cr/>) inside one paragraph is a visual line, and drafters
                # write the closing block that way ("此致" / the court / the signatory / the date in one
                # paragraph). Read as one string it would hide the 此致 heading, so the closing block would
                # never be a section: its length unit, the court check and the filing date would all fall
                # silent. Each line is its own paragraph, as python-docx's own .text renders it.
                lines, buf = [], []
                for node in child.iter():
                    tag_n = node.tag.replace(W, "")
                    if tag_n == "t":
                        buf.append(node.text or "")
                    elif tag_n in ("br", "cr"):
                        lines.append("".join(buf)); buf = []
                lines.append("".join(buf))
                if len(lines) == 1:
                    out.append(Para(len(out), f"body/p[{n}]", canonical_notation(halfwidth_numerals(lines[0]))))
                else:
                    for k, line in enumerate(lines):
                        if line.strip():
                            out.append(Para(len(out), f"body/p[{n}]/l[{k}]", canonical_notation(halfwidth_numerals(line))))
            elif tag == "tbl":
                for r, row in enumerate(child.iter(W + "tr")):
                    cells = ["".join(t.text or "" for t in tc.iter(W + "t")) for tc in row.iter(W + "tc")]
                    out.append(Para(len(out), f"body/tbl[{n}]/tr[{r}]", canonical_notation(halfwidth_numerals(" | ".join(cells)))))
        return out
    lines = artifact.read_text(encoding="utf-8").splitlines()
    return [Para(i, f"line[{i + 1}]", canonical_notation(halfwidth_numerals(re.sub(r"^\s*(#+|[-*+]|\|)\s*", "", line).strip(" |"))))
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
    would also blank the amount and deadline the item asks for. A formal citation closes
    its sentence at the quotation, so with `keep_embedded` the quote survives whenever the author's own
    predicate continues after it within the same sentence."""
    quotes = []

    def repl(m):
        if keep_embedded:
            # A formal source citation stays stripped even mid-sentence: a 《书名号》 title or a 第N条 reference
            # right before the quotation marks it as the statute's words, not the author's restatement (two
            # statutory quotations inside one sentence would otherwise fill the whole span).
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


def sections(paras: list[Para], headings: dict[str, list[str]], suffix_tolerance: int = 1) -> dict[str, list[Para]] | None:
    """Split by registered heading aliases; a heading paragraph starts with the alias and is short.

    `suffix_tolerance` is how many characters a heading may carry beyond the alias before it stops
    counting as that heading. A tolerance of 1 would require the heading to be the alias and nothing
    else, so a drafter who labels the block "请求事项与事实理由" instead of "请求事项" would lose the whole
    section: every item bound to it would report parse_failure and the caption block's length contract
    would swallow the entire document. A short allowance keeps the rule at "a heading paragraph is the
    alias plus at most a few words", while an ordinary body paragraph stays far too long to qualify.

    Returns None when a heading alias matches in more than one place (unresolved location)."""
    marks: list[tuple[int, str]] = []
    for position, p in enumerate(paras):
        head = re.sub(r"^(第?[一二三四五六七八九十\d]+[、.．)）]|[（(][一二三四五六七八九十\d]+[)）])", "", nonspace(p.text))
        for name, aliases in headings.items():
            if any(head.startswith(a) and (len(head) <= len(a) + suffix_tolerance or head[len(a)] in "：:") for a in aliases):
                marks.append((position, name))
                break
    counts: dict[str, int] = {}
    for _, name in marks:
        counts[name] = counts.get(name, 0) + 1
    # A name matched in several places is still resolved when exactly ONE of those paragraphs is the bare
    # alias (optionally followed by "："). The other matches are sub-headings that merely begin with an
    # alias -- "四、申请事项金额说明" over the amount note, which the alias "申请事项" plus the 8-character
    # suffix tolerance also accepts -- and dropping the whole section for that would zero every item bound
    # to it. A sub-heading that names the SAME section ("申请事项金额说明" under 申请执行事项) is part of that
    # section, not a boundary: the amount note under it is the note Golden itself writes inside the
    # applied-for block. Marks of other names stay boundaries. Two bare-alias headings, or none among
    # several matches, stay unresolved.
    def _bare_alias(start: int, name: str) -> bool:
        head = re.sub(r"^(第?[一二三四五六七八九十\d]+[、.．)）]|[（(][一二三四五六七八九十\d]+[)）])", "", nonspace(paras[start].text))
        return any(head == a or head.rstrip("：:") == a for a in headings[name])
    resolved = []
    for name in dict.fromkeys(n for _, n in marks):
        cand = [st for st, n in marks if n == name]
        if len(cand) == 1:
            resolved.append((cand[0], name))
            continue
        bare = [st for st in cand if _bare_alias(st, name)]
        if len(bare) == 1:
            resolved.append((bare[0], name))
    resolved.sort()
    if not resolved:
        return None
    resolved_names = {name for _, name in resolved}
    subheads = {start for start, name in marks if name in resolved_names and (start, name) not in resolved}
    boundaries = [start for start, _ in marks if start not in subheads]
    out: dict[str, list[Para]] = {"__head__": paras[:marks[0][0]] if marks else list(paras)}
    for start, name in resolved:
        end = next((b for b in boundaries if b > start), len(paras))
        out[name] = paras[start:end]
    # The attachment list is NOT split off here: this package's contract registers the closing block as
    # "closing/attachment-list/signature block", so the attachment lines are scored content (they carry the
    # measured length contract, and the unsupported-specifics scan skips the whole block to leave the signature
    # date alone). Splitting them into __tail__ would charge the Golden itself.
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
    clause longer than about ten characters anywhere in it, so requiring the longest clause to stay short as
    well as the median keeps the
    detector aimed at real spray without being tripped by a one-character synonym swap inside a reasoned claim."""
    sentence = _THOUSANDS_COMMA.sub("", sentence)
    # A caption field list -- "住所地：某市某区某镇****，法定代表人：黄某，执行董事兼总经理" -- is two or more
    # "label：value" pairs, not a bag of keywords. Splitting on "：" would make every short label and value a
    # clause of its own, so a party line whose fields are separated by "；" would trip the spray gate once
    # the second sentence carried the address and representative.
    if len(re.findall(r"(?:^|[，、；,;])[\u4e00-\u9fff]{2,10}[：:]", sentence)) >= 2:
        return False
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
    for p in paras:
        if lead_excluded(p, list(lead_exclusions)):
            continue
        own, _ = strip_authority_quotes(p.text, keep_embedded=True)
        sents = sentences(own)
        usable = [s for s in sents if not (ex and ex.search(nonspace(s))) and not is_keyword_spray(s)]
        for i in range(len(usable)):
            window = "".join(usable[i:i + sentence_window])
            flat = nonspace(window)
            if len(flat) > max_chars:
                flat = flat[:max_chars]
            # Amounts are matched with and without thousands separators: "8,061,635.72元" and "8061635.72元" are
            # the same figure, and a registered pattern written in one style must not miss the other.
            degrouped = re.sub(r"(?<=\d)[,，](?=\d{3}(?!\d))", "", flat)
            # "40,000.00元" is the same figure as "40000元" -- a whole-yuan amount written with two zero decimals
            # is a notation, not a different value; a pattern registered as "40000元" must match it.
            degrouped = re.sub(r"(?<=\d)\.00(?=元)", "", degrouped)
            hits = sum(1 for g in compiled if g.search(flat) or g.search(degrouped))
            if hits > best[0]:
                best = (hits, (p, window))
                if hits == len(compiled):
                    return hits, len(compiled), best[1]
    return best[0], len(compiled), best[1]


DATE = re.compile(r"(?:(\d{4})\s*年\s*)?(\d{1,2})\s*月\s*(\d{1,2})\s*日")
AMOUNT = re.compile(r"(?<!\d)(?<!\d[,，.])(\d{1,3}(?:[,，]\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*(亿元|万元|元)")
LONG_NUMBER = re.compile(r"\d{11,}")
PERIOD = re.compile(r"(?<![\d.])(\d{1,3})\s*(个月|日|天|年)")
PLACEHOLDER = re.compile(
    r"[×xX＊*_＿]{2,}"            # masked identifiers
    r"|【(?:[·•\-—\s]{0,2}(?:待|请填|请补|占位)[^】]{0,200}|[^】]{0,30})】|〖[^〗]{0,60}〗|〔[^〕]{0,30}〕|\[[^\]]{0,30}\]|［[^］]{0,30}］"   # bracketed placeholder of any style
    r"|（[待占][^）)]{0,12}[）)]|\([待占][^）)]{0,12}\)"                  # （待确认）/（占位）
    r"|待补充|待确认|待核实|占位符?|placeholder|PLACEHOLDER|某某"
)
"""Accepted placeholder forms: a fact the Materials do not establish must be marked as a placeholder rather than
invented, and every listed form counts as such a marking.

A 【】 marker that opens with a gap word (待填/待补充/请填写/占位, optionally after a bullet dot as in "【·请填写：…·】")
may run to 200 characters: a marker such as "【待填：本申请提交之日，应在《中华人民共和国民事诉讼法》规定的二年申请执行
期间内，即2026年11月3日之前】" is a marker, not prose, and the date inside it is not an assertion of that date.
Marker wording is never scored (gap_marker_fold_v1), so what a marker says about the missing value is not an
assertion of it. Brackets without a gap word keep the 30-character cap."""



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
    # Chinese-numeral dates are the same assertion in another notation. Scanning only the Arabic form
    # let a Golden that signs off "二〇二四年十一月四日" past a check that charged a submission writing
    # the same day as "2024年11月4日" -- a notation-dependent decision, which the judge never makes.
    # Normalised to the Arabic spelling so `supported` compares like with like.
    for m in re.finditer(r"([〇零○0-9一二三四五六七八九]{2,4})\s*年\s*([一二三四五六七八九十]{1,3})\s*月\s*"
                         r"([一二三四五六七八九十]{1,3})\s*日", own):
        try:
            year = "".join(str(CN_DIGIT[ch]) if ch in CN_DIGIT else ch for ch in m.group(1))
            month, day = _cn_date_number(m.group(2)), _cn_date_number(m.group(3))
        except (KeyError, ValueError):
            continue
        if len(year) == 4 and year.isdigit() and 1 <= month <= 12 and 1 <= day <= 31:
            found.append(("date", f"{year}年{month}月{day}日"))
    for m in AMOUNT.finditer(own):
        found.append(("amount", m.group(0)))
    for m in LONG_NUMBER.finditer(own):
        found.append(("identifier", m.group(0)))
    date_spans = [(m.start(), m.end()) for m in DATE.finditer(own)]
    for m in PERIOD.finditer(own):
        # The day component of a date ("2026年1月1日" -> "1日") is not a duration; reporting it as one would charge
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



CN_DIGIT = {"〇": 0, "零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
            "壹": 1, "贰": 2, "叁": 3, "肆": 4, "伍": 5, "陆": 6, "柒": 7, "捌": 8, "玖": 9, "0": 0, "1": 1,
            "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9}
CN_DATE = re.compile(r"([〇零○0-9一二三四五六七八九]{2,4})\s*年\s*([一二三四五六七八九十]{1,3})\s*月\s*"
                     r"([一二三四五六七八九十]{1,3})\s*日")
COMPACT_DATE = re.compile(r"(?<!\d)(20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?!\d)")


def _cn_date_number(token: str) -> int:
    """Chinese numerals for 1-31 (month and day-of-month), not the digit-by-digit reading used for the year.

    Named apart from a package's own `_cn_small_number`, which may also accept 两 for periods ("两年"); a second
    definition of the same name would shadow it."""
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
                # buys nothing. A flat one-percent band would let two dozen candidate amounts coincidentally
                # bracket a figure nobody derived.
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
    the amounts. A dictionary search over partial sums would grow with the number of distinct partial sums and
    never finish on a filing whose amounts run to hundreds of millions."""
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


def derive_period_deadlines(dates: set[tuple]) -> set[tuple]:
    """R3: 民事诉讼法关于期间计算的通用规则——`自送达之日起十日内履行` 的履行期届满日是送达日+10个
    公历日（送达当日不计入，从次日起算，第十日届满），迟延履行期间起算日是届满日的次日（+11）。

    This document's only unresolved-in-Materials date (the 2024-10-24 service date) is supplied by
    instruction.md; both downstream dates (11-3 deadline, 11-4 accrual start) are then a deterministic
    replay of this public civil-procedure counting rule, not a second opaque fact. Restricting the
    derivation to exactly three fixed offsets (not a tolerance window) keeps it from legitimising a
    fabricated nearby date: only the specific, ruled dates become supported.

    The same rule has a second branch, and +12 is that branch, not a widening. Where the tenth day
    falls on a day the procedural rules treat as a holiday, the period expires on the next day
    instead (service+11) and the consequences of non-performance then start on the day after that
    (service+12). 2024-11-03, the tenth day here, is a Sunday, so a drafter may derive 11-04 as the
    expiry and 11-05 as the accrual start, write the rule out in the document, and use the result
    consistently. Charging 11-05 as a fabricated date would be a false positive; the branch is admitted
    as a named offset so that it stays a rule and not a tolerance window."""
    import datetime

    out: set[tuple] = set()
    for year, month, day in dates:
        if year is None:
            continue
        try:
            base = datetime.date(int(year), month, day)
        except ValueError:
            continue
        for offset in (1, 10, 11, 12):
            derived = base + datetime.timedelta(days=offset)
            out.add((str(derived.year), derived.month, derived.day))
            if offset in (10, 11):
                # 民诉法 250 条 -- the two-year period for applying for enforcement runs from the last day of
                # the performance period, so its end is that day plus two years (2026-11-03 on the service-day
                # chain, 2026-11-04 with the rest-day extension, 2026-11-02 on the pronouncement chain). A
                # statement that names the anchor in the same sentence is read as a computation anyway; one
                # that does not is supported here. It is the same public counting rule, one more hop.
                try:
                    end = derived.replace(year=derived.year + 2)
                except ValueError:
                    end = derived.replace(year=derived.year + 2, day=28)
                out.add((str(end.year), end.month, end.day))
    return out


CN_DIGIT = {"〇": 0, "零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CN_DATE = re.compile(r"([〇零一二三四五六七八九]{2,4})年([一二三四五六七八九十]{1,3})月([一二三四五六七八九十]{1,3})日")


def _cn_small_number(token: str) -> int:
    """Chinese numerals for 1-31 (day-of-month / month range), not the 年 digit-by-digit reading."""
    if len(token) == 1:
        return 10 if token == "十" else CN_DIGIT[token]
    if len(token) == 2 and token[0] == "十":
        return 10 + CN_DIGIT[token[1]]
    if len(token) == 2 and token[1] == "十":
        return CN_DIGIT[token[0]] * 10
    if len(token) == 3 and token[1] == "十":
        return CN_DIGIT[token[0]] * 10 + CN_DIGIT[token[2]]
    raise ValueError(f"unsupported Chinese numeral: {token}")


def derive_cn_numeral_dates(texts: list[str]) -> set[tuple]:
    """Judgment signature blocks date themselves in Chinese numerals (二〇二四年五月二十八日), which the
    Arabic-digit DATE regex cannot see. Both instance judgments' issuance dates are only visible this way,
    so without this the Golden filing's own accurate transcription of them would be flagged as fabricated."""
    out: set[tuple] = set()
    for t in texts:
        for m in CN_DATE.finditer(t):
            try:
                year = "".join(str(CN_DIGIT[c]) for c in m.group(1))
                month = _cn_small_number(m.group(2))
                day = _cn_small_number(m.group(3))
            except (KeyError, ValueError):
                continue
            out.add((year, month, day))
    return out


def derive_task_totals(amounts: set) -> set:
    """R4: two formula totals this filing depends on, each replayed from amounts that must themselves
    already be visible in Materials (the court-apportioned case/preservation fee 77394 and appraisal fee
    283500; the awarded principal 8061635.72 and deposit 40000). Only these two specific sums are
    registered -- this is not a general combinatorial search over every visible amount, so it cannot be
    used to launder an unrelated fabricated total."""
    out: set = set()
    fee_terms = (77394.0, 283500.0)
    if all(term in amounts for term in fee_terms):
        fees_total = round(sum(fee_terms), 2)
        out.add(fees_total)
        basis_terms = (8061635.72, 40000.0)
        if all(term in amounts for term in basis_terms):
            out.add(round(sum(basis_terms) + fees_total, 2))
    # Sums of two or three of the operative part's own figures (the awarded principals, the court fees as
    # advanced and as apportioned) are replays of the record, not new facts -- "该两项费用81,898元已由申请执行人
    # 预交" (76898 + 5000) is such a replay whether or not the word 合计 stands beside it. The list is closed
    # (the figures the judgments award or apportion); this is still not a search over every amount the
    # corpus mentions.
    import itertools
    record = [f for f in (8061635.72, 5825075.93, 40000.0, 76898.0, 5000.0, 300000.0, 77394.0, 4504.0, 283500.0, 16500.0)
              if f in amounts]
    for n in (2, 3):
        for combo in itertools.combinations(record, n):
            out.add(round(sum(combo), 2))
    return out

# ---------------------------------------------------------------------------------------------------------------
# Written computations.
# A drafter who shows the computation -- "40000股×15.6元/股＝624,000元", "1,871,866.02元（1,216,712.91÷65%）",
# "自次日起算，十五日期满之日为2025年9月2日" -- has derived the figure, so correct products, quotients and deadlines
# are not charged as fabricated alongside sums and differences of established amounts.
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
    r"[【〖〔\[［（(][^】〗〕\]］）)]{0,200}?(?:待补充|待确认|待核实|待定|占位|placeholder|PLACEHOLDER|TBD)[^】〗〕\]］）)]{0,200}?[】〗〕\]］）)]"
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


# format-canonical v1: pure notation is normalised before any predicate reads the text, so a document written
# 2024年05月28日 or 第66条 decides exactly as one written 2024年5月28日 or 第六十六条.
_CN_DIGITS = "零一二三四五六七八九"


def _int_to_cn(value: int) -> str:
    if value < 10:
        return _CN_DIGITS[value]
    if value < 20:
        return "十" + (_CN_DIGITS[value % 10] if value % 10 else "")
    if value < 100:
        return _CN_DIGITS[value // 10] + "十" + (_CN_DIGITS[value % 10] if value % 10 else "")
    hundreds, rest = divmod(value, 100)
    tail = "" if rest == 0 else ("零" + _CN_DIGITS[rest] if rest < 10 else
                                 (_CN_DIGITS[rest // 10] + "十" + (_CN_DIGITS[rest % 10] if rest % 10 else "")))
    return _CN_DIGITS[hundreds] + "百" + tail


def canonical_notation(text: str) -> str:
    text = re.sub(r"(\d{4})\s*年\s*0?(\d{1,2})\s*月\s*0?(\d{1,2})\s*日",
                  lambda m: f"{m.group(1)}年{int(m.group(2))}月{int(m.group(3))}日", text)
    if True:
        text = re.sub(r"第\s*(\d{1,3})\s*条", lambda m: f"第{_int_to_cn(int(m.group(1)))}条", text)
    return text
