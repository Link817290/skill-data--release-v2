"""Shared guards for Program Judge / validator text predicates.

Two carrier shapes need handling before any item predicate runs:

1. A withdrawal / candidate / disowning prefix is invisible to the positive items.  A paragraph that
   opens with "以下并非本方主张：" or "疑似（待核，尚未采纳）：", or that quotes a claim and rejects it
   ("原稿主张“…”，经复核不成立"), still earns every item whose keywords it contains, because sentence-level
   negation stops at the colon.
2. Polarity is not read.  "应不承担违约责任" matches `应.{0,n}承担`; "维持原判决" matches a relief regex whose
   veto treats 判决 as reporting.

Both are handled at the carrier layer, before any item predicate runs:

    from adversarial_guards import blank_withdrawn, negated_between, negated_before

    text = blank_withdrawn(text)          # withdrawn spans become spaces: offsets and line numbers survive
    ...
    m = re.search(r"应.{0,6}承担", text)
    if m and not negated_between(text, m):  # "应不承担" does not count as "应承担"
        ...

The marker lists are deliberately narrow.  Bare 疑似 / 待核 / 待定 are *not* markers: a finding may
legitimately be graded as "疑似，交作者确认", and a guard must not fire on correct work.  A marker only counts when it disowns or withholds adoption ("尚未采纳", "不予采纳", "并非本方主张",
"经复核不成立", "not adopted", "not asserted").

The Golden contains no withdrawn span under these lists, so it keeps full credit.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------- withdrawal / candidate / disowning markers
# A paragraph (or table cell) whose head matches one of these is withdrawn in full.
_HEAD_ZH = (
    r"以下(?:内容)?(?:并非|不是|不构成)(?:本方|我方|本报告|本表|本意见)?的?(?:主张|结论|意见|认定|观点)",
    r"(?:疑似|拟|暂列|候选)?[（(]?\s*(?:待核|待定|待确认)?[，,、\s]*(?:尚未|暂不|未予?)采纳\s*[）)]?",
    r"(?:本方|我方|本表|本报告)?(?:不予|不作|并不)采纳",
    r"(?:仅供参考|仅为草稿|草稿意见|备选方案)[，,：:]?\s*(?:不作为|并非)(?:本方)?(?:主张|结论)",
    r"疑似[（(]\s*待核\s*[）)]",                       # pdf generator head; only as a head followed by ：
)
_HEAD_EN = (
    r"the following (?:is|are) not (?:asserted|claimed|adopted|our (?:position|conclusion|finding))(?: here| below)?",
    r"tentative(?:ly)?[,;:]?\s*not adopted",
    r"(?:candidate|draft)(?: only)?[,;:]?\s*not adopted",
    r"not adopted[,;:]",
    r"not asserted(?: here| below)?",
    r"withdrawn[,;:]",
)
# The head must be followed by the content it disowns: a cell that is just "未采纳" is a status value,
# not a withdrawal, and must never be blanked.
HEAD_RE = re.compile(r"^\s*(?:[-*•>]|\d+[.)、]|[（(][一二三四五六七八九十\d]+[）)]|#+)?\s*(?:" + "|".join(_HEAD_ZH + _HEAD_EN)
                     + r")\s*(?:[：:]|[）)]\s*[：:]?|[，,]\s*)\s*(?=\S.{1,})", re.I)

# Quote-and-reject anywhere in a paragraph: 原稿/草稿/对方/有观点 主张/记载/认为 “…” … 不成立/不予采纳/不采纳
QUOTE_REJECT_RE = re.compile(
    r"(?:原稿|草稿|初稿|前稿|本稿初版|the draft|a draft|an earlier draft)[^“\"「]{0,12}"
    r"(?:主张|记载|认为|称|asserted|stated|claimed)[^“\"「]{0,4}[“\"「]([^”\"」]{1,800})[”\"」]"
    r"[^。.\n]{0,30}(?:不成立|不予采纳|不采纳|不能成立|does not hold|is not adopted|not adopted|rejected)[^。.\n]{0,40}[。.]?",
    re.I)

# ---------------------------------------------------------------- negation
NEG_ZH = r"(?:不|未|没有|并非|非本|不再|无需|无须|毋须|不必|不予|不应|不得|否认|免于|无权|无义务)"   # bare 无/非 excluded: 无锡、非常
NEG_EN = r"(?:not|no|never|none|neither|nor|without|cannot|can't|isn't|aren't|wasn't|weren't|doesn't|don't|didn't|won't|shouldn't|is not the case)"
_NEG_BETWEEN = re.compile(NEG_ZH + r"|\b" + NEG_EN + r"\b", re.I)
_NEG_BEFORE_ZH = re.compile(NEG_ZH + r"[^，,。；;：:\n]{0,2}$")
_NEG_BEFORE_EN = re.compile(r"\b" + NEG_EN + r"\b(?:\s+\w+){0,3}\s*$", re.I)
_IT_IS_NOT = re.compile(r"(?:it is not the case that|并非|不是说)[^。.;；\n]{0,200}$", re.I)


# A carrier whose own qualifier withholds adoption: "疑似X（待核，尚未采纳，建议…）"
SUFFIX_RE = re.compile(r"[（(][^（()）]{0,20}(?:尚未采纳|暂不采纳|不予采纳)[^（()）]{0,40}[）)]\s*[。.]?\s*$")


def withdrawn_spans(text: str) -> list[tuple[int, int]]:
    """Character spans the author has disowned: whole paragraphs with a withdrawal head, and the quoted
    part of every quote-and-reject construction.  Paragraphs are split on blank lines and on single
    newlines (Markdown lists, table rows and docx paragraphs all arrive one per line)."""
    spans = []
    pos = 0
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\n")
        if body.strip() and (HEAD_RE.match(body) or SUFFIX_RE.search(body)):
            spans.append((pos, pos + len(body)))
        else:
            for m in QUOTE_REJECT_RE.finditer(body):
                spans.append((pos + m.start(), pos + m.end()))
        pos += len(line)
    return spans


def blank_withdrawn(text: str) -> str:
    """Replace every withdrawn span with spaces of the same length (offsets, line numbers and
    locator ids stay valid for everything that is not withdrawn)."""
    if not text:
        return text
    chars = list(text)
    for s, e in withdrawn_spans(text):
        for i in range(s, e):
            if chars[i] not in "\r\n":
                chars[i] = " "
    return "".join(chars)


def is_withdrawn(text: str) -> bool:
    """True when a single carrier (a table cell, a JSON string value, one paragraph) is withdrawn."""
    return bool(text) and bool(withdrawn_spans(text))


def negated_between(text: str, match: "re.Match") -> bool:
    """True when a negator sits strictly inside the matched span — `应不承担` inside `应.{0,6}承担`,
    `does not support` inside `does.{0,10}support`.  Use for patterns with a gap between two anchors."""
    inner = text[match.start() + 1: match.end() - 1]
    return bool(_NEG_BETWEEN.search(inner))


def negated_before(text: str, start: int, window: int = 12) -> bool:
    """True when the clause ending at `start` carries a negator that governs what follows
    (`不构成`, `并非…`, `It is not the case that …`, `does not …`).  The window never crosses a
    sentence or clause boundary, so a negation in the previous row or sentence is not borrowed."""
    head = text[max(0, start - window): start]
    for sep in "。；;\n":
        if sep in head:
            head = head.rsplit(sep, 1)[-1]
    if _NEG_BEFORE_ZH.search(head) or _NEG_BEFORE_EN.search(head):
        return True
    return bool(_IT_IS_NOT.search(text[max(0, start - 220): start].rsplit("\n", 1)[-1]))


def affirmed(text: str, pattern: "re.Pattern | str", flags: int = 0) -> list["re.Match"]:
    """All matches of `pattern` that are neither withdrawn, negated inside, nor negated before."""
    rx = re.compile(pattern, flags) if isinstance(pattern, str) else pattern
    clean = blank_withdrawn(text)
    return [m for m in rx.finditer(clean) if not negated_between(clean, m) and not negated_before(clean, m.start())]
