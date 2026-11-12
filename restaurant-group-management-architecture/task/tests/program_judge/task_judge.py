#!/usr/bin/env python3
"""Program Judge for the XX餐饮 group control system and long-term architecture chapter.

Three explicit layers:
  1. extract_raw()  parses the Markdown carrier into spans: table cell lines (with row and
     column headers), list items (with lead-in), paragraph sentences and fenced lines, each
     with its heading path and structural locator.
  2. normalize()    turns spans into business observations: decision triples
     (decision item, body, role), target-issuing pairs (issuer, receivers), investment approval
     statements, architecture-variant statements (N+1, 2型), positioning statements and shape
     counts. Every non-trivial step cites a rule registered in rubric-contract.json.
  3. evaluate()     makes exactly one decision per contracted P and D item.

Vocabulary and allowed allocations come from the frozen relation matrix; the Judge never reads
Golden at scoring time.
"""

from __future__ import annotations

import argparse
import sys
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from program_judge_runtime import Locator, ProgramJudge, load_contract, sha256


import os as _os
PACKAGE_ROOT = Path(_os.environ.get("SKILL_PACKAGE_ROOT") or Path(__file__).resolve().parents[1])
CANONICAL_CONTRACT = PACKAGE_ROOT / "rubric-contract.json"

# ---------------------------------------------------------------------------
# Frozen vocabulary (N02 bodies, N03 decision items, N04 roles, N05 receivers)
# ---------------------------------------------------------------------------

BODY_PATTERNS = [
    ("养老公司", r"养老公司|养怡(?:股份)?(?:有限)?公司|老年养怡[一-鿿]{0,4}公司"),
    ("酒店BU", r"酒店\s*BU|酒店事业部|酒店业务单元|酒管公司|酒店管理公司"),
    ("投资BU", r"投资\s*BU|投资事业部|投资业务单元"),
    ("股份", r"股份公司(?:董事会|总部)?|股份董事会|股份总部|股份有限公司|股份(?![一-鿿]{0,2}制)"),
    ("集团", r"集团总部|集团公司|集团董事会|集团有限公司|集团(?!性|套|化|型)"),
]
RANK = {"集团": 3, "股份": 2, "养老公司": 2, "酒店BU": 1, "投资BU": 1}

STRATEGY_TOKENS = [
    ("portfolio", r"(?:产业|业务|投资)?组合(?:发展)?(?:战略|策略|规划)|(?:主)?产业(?:的)?进退|(?:规模、)?节奏与资源配比|资源配比|内部组合|之间的组合|规模与节奏(?:的)?配比|节奏配比|(?:产业|业务)组合(?!方式|管理|战略|策略|规划)|组合决策(?=\s*[:：])"),
    ("invfin", r"投融资(?:战略|策略|规划|计划|安排)|投资(?:规划|计划)|融资(?:规划|计划|策略)|投资(?:与|和|及)?融资(?:战略|策略|规划)|投资战略|融资战略"),
    ("comp", r"竞争(?:战略|策略|规划|计划)|经营(?:战略|策略)"),
    ("dev", r"(?:整体)?发展(?:战略|策略|规划|计划)|战略规划|中长期(?:发展)?规划"),
]
SUBJECT_TOKENS = [
    ("core_hotel", r"核心酒店|重点酒店|核心单体酒店|核心企业|重点企业"),
    ("unit_hotel", r"(?:自有|委托|特许|合资|参股)(?:[/、及和与]|管理|经营|控股|自有|委托|特许|合资|参股)*酒店|(?:其他|其余)[^，,；;。]{0,10}酒店|(?:单体|各|每个|每家|所有|非核心|辖下|下属|所属|一般|普通)(?:的)?(?:单体)?酒店|酒店经营单位|酒管公司"),
    ("units", r"(?:辖下|下属|所辖|所属|旗下|存续)(?:各|的|类)?(?:业务)?(?:企业|经营单位|公司)|(?:各|每个|每一|所管|所管普通|普通)(?:存续)?经营单位|各(?:多元业务)?企业|每个企业|存续企业|(?:各|每个)?存续(?:多元业务)?(?:业务)?单位|(?:各|每个)?存续业务"),
    # N03: 电商/物业 are the settled key incubation businesses (the receiver vocabulary already reads them so)
    ("incub", r"(?:重点)?孵化(?:培[养育])?(?:类|中)?(?:的)?(?:业务|产业|项目)?|电子商务(?:业务)?|电商(?:业务)?|物业(?:服务)?(?:业务)?"),
    ("div", r"存续(?:多元)?业务(?:组合|群|集合|整体)|投资\s*BU(?:所管|所辖|辖下|管理的|归口的?)(?:的)?(?:存续)?(?:业务)?集合|投资\s*BU所辖[^，,；;。]{0,6}业务群|多元化?(?:投资)?(?:与孵化)?(?:类)?(?:业务|产业|板块)?"),
    ("pension", r"养老(?:产业|业务|板块)?"),
    ("hotel", r"酒店(?:产业|业务|板块)?(?!\s*BU|事业部|管理公司|业务单元)"),
    ("gufen", r"股份公司|股份"),
    ("group", r"集团(?:整体|层面)?"),
]
SUBJECT_GAP = r"(?:的|之|整体|总体|层面|自身|单体级|单位级|单体|单位|\s|[:：]|[（(][^）)]{0,40}[）)])*"
ITEM_MAP = {
    ("group", "portfolio"): "group_portfolio", ("group", "invfin"): "group_invfin", ("group", "dev"): "group_dev",
    ("gufen", "invfin"): "gufen_invfin", ("gufen", "dev"): "gufen_dev", ("gufen", "portfolio"): "gufen_portfolio",
    ("hotel", "dev"): "hotel_dev", ("hotel", "comp"): "hotel_comp", ("hotel", "invfin"): "hotel_invfin",
    ("core_hotel", "comp"): "core_hotel_comp", ("unit_hotel", "comp"): "hotel_unit_comp",
    ("pension", "dev"): "pension_dev", ("pension", "comp"): "pension_comp",
    ("div", "portfolio"): "div_portfolio", ("div", "dev"): "div_dev", ("div", "invfin"): "div_invfin",
    ("div", "comp"): "div_comp",
    ("incub", "dev"): "incub_dev", ("incub", "comp"): "incub_comp",
    ("units", "comp"): "div_unit_comp",
}
ROLE_TOKENS = [
    ("final", r"最终审批|最终决策|最终决定|终审|审批|批准|批复|核准|审定|决策|决定|拍板"),
    ("review", r"初审|审核|审查|预审|复核|把关|评审|审议"),
    ("draft", r"制定|制订|起草|拟定|拟订|编制|草拟|提出|提议|提案|建议权|牵头|主导"),
]
# N04: a role label may carry a stage qualifier (初步审核： reads as 审核：, 最终审定： as 审定：)
LABEL = r"^\s*(?:初步|最终|最后|正式)?(" + "|".join(pattern for _role, pattern in ROLE_TOKENS) + r")(?:权)?\s*[:：]"
NEG = r"不|无需|无须|并非|而非|非|未|不需|不必|无权|没有|无"
RECEIVER_TOKENS = [
    ("incub", r"(?:重点)?孵化(?:培[养育])?(?:业务|产业)?|电商(?:业务)?[、和与及]物业(?:业务)?"),
    ("hotel_units", r"(?:每个|每家|各|所有|全部|各家|单体|下属|辖下|旗下)(?:的)?(?:单体)?酒店|核心酒店"
                    r"|(?:所有|全部|各)(?:[、和与及]?(?:自有|合资控股|合资|控股|参股|委托管理|委托|特许经营|特许))+(?:的)?酒店"
                    r"|(?:自有|合资控股|合资|控股|参股|委托管理|委托|特许经营|特许)(?:[、和与及](?:自有|合资控股|合资|控股|参股|委托管理|委托|特许经营|特许))+(?:的)?酒店"),
    ("enterprise_units", r"(?:每个|每家|各|所有|全部|辖下|下属|旗下|存续)(?:的)?(?:多元业务|存续)?(?:企业|经营单位|公司|业务)|各多元业务|每个多元业务|各项多元业务|(?:各|每个|每一)业务类型"),
    ("hotel_agg", r"酒店(?:产业|业务|板块)?"),
    ("pension_agg", r"养老(?:产业|业务|板块)?"),
    ("div_agg", r"多元(?:投资)?(?:业务|产业)?"),
]
TARGET_WORD = r"目标|预算|指标"
EXECUTOR = r"\s*(?:只|仅)?(?:负责|承办|跟踪|准备|落实|统筹|支持|协助)|\s*(?:不是|并非|不作为|不单独作为)下达方|\s*(?:所辖|辖下|下属|旗下|所属|直管的)"
TARGET_VERB = r"下达|下发|分解|设定|核定|下目标|制定[^，,；;。]{0,4}目标"
INVEST_BU = r"投资\s*BU|投资事业部|投资业务单元"
INVEST_WORD = r"投资|(?<![轻重])资产(?:变更|处置|重组|新增|评估)?|并购|收购"
NEGATED_INVEST = r"(?:不涉及|不含|不包括|非)[^，,；;。)）]{0,6}(?:投资|资产)|投资发展部|投资孵化|投资管控(?:型)?"
TYPE_WORDS = r"投资管控型|战略控制型|运营管控型|战略指导型|财务管控型"
WRONG_TYPES = {
    "集团": r"战略控制型|运营管控型|战略指导型",
    "股份": r"运营管控型|投资管控型|战略指导型",
    "酒店BU": r"战略控制型|投资管控型|战略指导型",
}
GAP_MARKERS = ["[待补充]", "【待补充】", "[placeholder]", "未提供", "材料未提供", "unspecified", "TBD"]

EXCLUDED_HEADING = r"现状|诊断|案例|借鉴|备选|不采纳|未采纳|附录|背景|回顾|思考|问题|参考|自查|自检"
CANDIDATE = r"可考虑|可以考虑|或可|或者|备选|候选|待定|待讨论|尚待|视情况|二选一|倾向于|初步设想|拟议|方案[一二三四ABCD甲乙]|也可|亦可|是否"
REJECT = r"不采纳|不予采纳|否决|驳回|不建议|有观点认为|有人提出|有意见认为|曾有提议|被否定|不宜采用|不予采用"
# R02: a variant name may be quoted (“2”型, “N+1”型) or spelled out (N个主产业+1个投资孵化群; 两个上市平台/两大关联板块)
QUOTE = r"[“”\"'「」『』‘’]?"
ARCH_N1 = r"[Nn]\s*\+\s*1"
ARCH_TWO = r"(?<![0-9Nn+])" + QUOTE + r"(?:2|二)" + QUOTE + r"\s*型|两大板块型|双板块型"
# R02: spelled-out variant names count only in a heading (a near-term table row such as 两个资本平台定位 is not a variant)
ARCH_N1_HEADING = ARCH_N1 + r"|[Nn]\s*个[^，,；;。:：]{0,8}\+\s*1\s*个"
ARCH_TWO_HEADING = ARCH_TWO + r"|两(?:个|大)(?:上市|资本)平台|两大(?:关联)?(?:产业)?板块"
CHARS = r"[一-鿿A-Za-z0-9]"
# R06: the settled issuing chain (golden 2.8 目标管控 row): 股份 to its two BUs and the key incubation
# businesses, each BU to its own units
# R26: required units of the brief. Headquarters departments are the settled department names of the
# listed company (materials 上游已确定的方案结论); a chapter names at least HQ_DEPARTMENTS_MIN of them.
HQ_DEPARTMENTS = ["目标管控部", "投资发展部", "证券业务部", "风险稽查部", "人才发展中心", "总裁办公室", "财务中心",
                  "采购中心", "信息中心", "项目拓展部", "品牌运营部", "市场营销部", "工程咨询部", "餐饮研发部"]
HQ_DEPARTMENTS_MIN = 3
DECISION_ITEMS_MIN = 2
# R27: the deliverable directory (output/ in the workspace; only this path is scored since the 0922 fix)
HARNESS_ALLOWLIST = {"manifest.json"}  # R27: harness collection manifest, never an agent deliverable (fix batch 3)
DELIVERY_DIRS = {"output"}  # fix batch 1: artifacts/ is no longer a delivery directory
# R28: a span with at least this many Latin letters, more than its CJK characters, is not written in Chinese
LATIN_SPAN_MIN = 20
SPAN_MAX_CHARS = 300
SPAN_MAX_ITEMS = 8


# ---------------------------------------------------------------------------
# Layer 1: raw carrier
# ---------------------------------------------------------------------------

@dataclass
class Span:
    index: int
    kind: str
    path: str
    headings: tuple[str, ...]
    text: str
    row_header: str = ""
    col_header: str = ""
    lead_in: str = ""
    row_cells: tuple[str, ...] = ()
    header_cells: tuple[str, ...] = ()
    depth: int = 0


def _clean(text: str) -> str:
    """N01: drop Markdown emphasis, code ticks and link targets."""
    text = text.replace("**", "").replace("__", "").replace("`", "")
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    return text.strip()


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[。！？!?])", text) if s.strip()]


def extract_raw(artifact: Path) -> dict:
    if not artifact.is_file():
        return {"state": "confirmed_missing", "artifact": artifact, "spans": [], "text": ""}
    try:
        text = artifact.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        return {"state": "parse_failure", "artifact": artifact, "spans": [], "text": ""}
    if "\x00" in text or not re.search(r"[一-鿿]", text):
        return {"state": "parse_failure", "artifact": artifact, "spans": [], "text": text}
    text = unicodedata.normalize("NFKC", text).replace("\r\n", "\n")
    spans: list[Span] = []
    headings: list[tuple[int, str]] = []
    state = {"block": 0, "lead_in": ""}
    paragraph: list[str] = []
    table: list[list[str]] = []
    in_fence = False
    list_stack: list[tuple[int, str]] = []

    def htuple() -> tuple[str, ...]:
        return tuple(title for _level, title in headings)

    def add(kind: str, body: str, path: str, **extra) -> None:
        body = _clean(body)
        if body:
            spans.append(Span(len(spans), kind, path, htuple(), body, **extra))

    def flush_paragraph() -> None:
        if not paragraph:
            return
        joined = "".join(line.strip() for line in paragraph)
        paragraph.clear()
        state["block"] += 1
        for number, sentence in enumerate(_sentences(joined)):
            add("paragraph_sentence", sentence, f"block[{state['block']}]/sentence[{number}]",
                lead_in=_clean(state["lead_in"]))
        state["lead_in"] = joined if re.search(r"[:：]\s*$", joined) else ""

    def flush_table() -> None:
        if not table:
            return
        state["block"] += 1
        header, rows = table[0], table[1:]
        if not rows:
            header, rows = [""] * len(table[0]), table[:]
        for r_index, row in enumerate(rows):
            row_header = _clean(re.sub(r"<br\s*/?>", " ", row[0])) if row else ""
            for c_index, cell in enumerate(row):
                if c_index == 0 and len(row) > 1:
                    continue
                col_header = _clean(re.sub(r"<br\s*/?>", " ", header[c_index])) if c_index < len(header) else ""
                for l_index, line in enumerate(re.split(r"<br\s*/?>", cell)):
                    for s_index, sentence in enumerate(_sentences(line)):
                        add("table_cell_line", sentence,
                            f"block[{state['block']}]/row[{r_index}]/col[{c_index}]/line[{l_index}]/sentence[{s_index}]",
                            row_header=row_header, col_header=col_header,
                            row_cells=tuple(_clean(re.sub(r"<br\s*/?>", " ", c)) for c in row),
                            header_cells=tuple(_clean(re.sub(r"<br\s*/?>", " ", c)) for c in header))
        table.clear()
        state["lead_in"] = ""

    for raw_line in text.split("\n"):
        stripped = raw_line.strip()
        if stripped.startswith("```"):
            flush_paragraph()
            flush_table()
            in_fence = not in_fence
            state["block"] += 1
            continue
        if in_fence:
            body = stripped.strip("└├│─┬┴┼┌┐┘┏┓┗┛━┃ \t")
            if body:
                prefix = re.match(r"^[\s└├│─┬┴┼┌┐┘┏┓┗┛━┃]*", raw_line.rstrip()).group(0)
                add("code_line", body, f"block[{state['block']}]/line[{len(spans)}]", depth=len(prefix))
            continue
        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            flush_paragraph()
            flush_table()
            level = len(heading.group(1))
            headings = [item for item in headings if item[0] < level]
            headings.append((level, _clean(heading.group(2))))
            state["lead_in"] = ""
            list_stack = []
            continue
        if not stripped:
            flush_paragraph()
            flush_table()
            continue
        if stripped.startswith("|"):
            flush_paragraph()
            if re.fullmatch(r"\|?(\s*:?-{2,}:?\s*\|)+\s*:?-*:?\s*\|?", stripped):
                continue
            table.append([cell.strip() for cell in stripped.strip("|").split("|")])
            continue
        flush_table()
        item = re.match(r"^(\s*)(?:[-*+]|\d+[.、)]|[一二三四五六七八九十]+、)\s*(.*)$", raw_line)
        if item and item.group(2).strip():
            flush_paragraph()
            indent = len(item.group(1).replace("\t", "    "))
            list_stack = [entry for entry in list_stack if entry[0] < indent]
            parent = list_stack[-1][1] if list_stack else state["lead_in"]
            state["block"] += 1
            for number, sentence in enumerate(_sentences(item.group(2))):
                add("list_item", sentence, f"block[{state['block']}]/item/sentence[{number}]", lead_in=_clean(parent))
            list_stack.append((indent, _clean(item.group(2))))
            continue
        paragraph.append(stripped)
    flush_paragraph()
    flush_table()
    return {"state": "identified", "artifact": artifact, "spans": spans, "text": text}


# ---------------------------------------------------------------------------
# Layer 2: normalized business observations
# ---------------------------------------------------------------------------

def _mask(text: str, start: int, end: int) -> str:
    return text[:start] + "□" * (end - start) + text[end:]


def find_bodies(text: str) -> tuple[list[tuple[int, int, str]], str]:
    """N02: body mentions in priority order, masking each match."""
    found = []
    for name, pattern in BODY_PATTERNS:
        for match in re.finditer(pattern, text):
            found.append((match.start(), match.end(), name))
            text = _mask(text, match.start(), match.end())
    found.sort()
    return found, text


def subject_of(text: str) -> str | None:
    """N03: subject kind of a span; overlapping subject tokens resolve to the longest match, then list order."""
    outside = re.sub(r"[（(][^）)]*[）)]", lambda m: "□" * len(m.group(0)), text)
    if outside != text:
        # N03: a bracketed clarification does not cancel the subject named outside it
        resolved = subject_of(outside)
        if resolved:
            return resolved
    candidates = []
    for priority, (kind, pattern) in enumerate(SUBJECT_TOKENS):
        for match in re.finditer(pattern, text):
            if match.end() > match.start():
                candidates.append((match.start(), match.end(), kind, priority))
    chosen: list[tuple[int, int, str, int]] = []
    for candidate in sorted(candidates, key=lambda c: (-(c[1] - c[0]), c[3], c[0])):
        if all(candidate[1] <= other[0] or candidate[0] >= other[1] for other in chosen):
            chosen.append(candidate)
    kinds = {c[2] for c in chosen}
    return next(iter(kinds)) if len(kinds) == 1 else None


ELLIPSIS = r"(发展|竞争|投融资|投资|融资|组合)((?:[、与和及](?:发展|竞争|投融资|投资|融资|组合))+)(战略|策略|规划|计划)"


def expand_ellipsis(text: str) -> str:
    """N09: an elliptical list sharing one head noun (发展、竞争与投融资战略) names one strategy per member."""
    def replace(match: re.Match) -> str:
        head = match.group(3)
        parts = re.split(r"([、与和及])", match.group(1) + match.group(2))
        return "".join(part + head if index % 2 == 0 else part for index, part in enumerate(parts))
    return re.sub(ELLIPSIS, replace, text)


def find_items(text: str, inherited_subject: str | None) -> tuple[list[tuple[int, int, str]], str, str | None]:
    """N03: decision item = subject token joined to a strategy token by a connective gap only."""
    text = expand_ellipsis(text)
    strategies = []
    work = text
    for kind, pattern in STRATEGY_TOKENS:
        for match in re.finditer(pattern, work):
            strategies.append((match.start(), match.end(), kind))
            work = _mask(work, match.start(), match.end())
    strategies.sort()
    subjects = []
    for priority, (kind, pattern) in enumerate(SUBJECT_TOKENS):
        for match in re.finditer(pattern, text):
            subjects.append((match.start(), match.end(), kind, priority))
    items = []
    last_subject = inherited_subject
    masked = text
    for start, end, kind in strategies:
        candidates = [s for s in subjects if s[1] <= start and re.fullmatch(SUBJECT_GAP, text[s[1]:start])]
        subject, item_start = None, start
        if candidates:
            best = sorted(candidates, key=lambda s: (-s[1], s[3], s[0]))[0]
            subject, item_start = best[2], best[0]
        elif kind == "portfolio" and inherited_subject is None:
            nearby = text[max(0, start - 20):start] + re.split(r"[,，;；。]", text[start:])[0]
            if re.search(r"酒店[^,，;；。]{0,4}养老|三大|各产业", nearby):
                subject = "group"
            elif "多元" in nearby:
                subject = "div"
            elif re.search(r"集团", nearby) and not re.search(r"股份", nearby):
                subject = "group"
        if subject is None:
            subject = last_subject
        if subject is None:
            continue
        last_subject = subject
        item = ITEM_MAP.get((subject, kind))
        if item:
            items.append((item_start, end, item))
            masked = _mask(masked, item_start, end)
    # N03: an item named inside brackets next to an item outside brackets is a cross-reference, not a decision
    brackets = [(m.start(), m.end()) for m in re.finditer(r"[（(][^）)]*[）)]", text)]
    inside = [item for item in items if any(a <= item[0] and item[1] <= b for a, b in brackets)]
    if inside and len(inside) < len(items):
        items = [item for item in items if item not in inside]
    return items, masked, last_subject


ROLE_NOUNS = r"战略决策(?:委员会)?|决策(?:与|和)(?:监督|执行)|决策(?:机构|委员会|事项|层级|层|体系|流程|支持|依据)|决定性"


def find_roles(text: str) -> list[tuple[int, int, str]]:
    """N04: role tokens folded to draft / review / final; noun uses such as 战略决策 are not roles."""
    found = []
    work = text
    for match in re.finditer(ROLE_NOUNS, work):
        work = _mask(work, match.start(), match.end())
    for role, pattern in ROLE_TOKENS:
        for match in re.finditer(pattern, work):
            found.append((match.start(), match.end(), role))
            work = _mask(work, match.start(), match.end())
    found.sort()
    return found


def strip_quotes(text: str) -> tuple[str, bool]:
    """N07: a quoted proposition carrying a role or issuing verb is not the author's adopted statement."""
    quoted = False
    role_or_verb = "|".join(pattern for _r, pattern in ROLE_TOKENS) + "|" + TARGET_VERB

    def replace(match: re.Match) -> str:
        nonlocal quoted
        inner = match.group(0)[1:-1]
        if re.search(role_or_verb, inner):
            quoted = True
            return "〔引文〕"
        return inner
    return re.sub(r"“[^”]*”|「[^」]*」|『[^』]*』|\"[^\"]*\"", replace, text), quoted


def arch_of(span: Span) -> str | None:
    """R02: architecture variant from the table column header or the deepest variant heading."""
    for position, source in enumerate((span.col_header, span.row_header, *reversed(span.headings))):
        heading = position >= 2
        n1 = bool(re.search(ARCH_N1_HEADING if heading else ARCH_N1, source))
        two = bool(re.search(ARCH_TWO_HEADING if heading else ARCH_TWO, source))
        if n1 and two:
            return "both"
        if n1:
            return "n1"
        if two:
            return "two"
    return None


@dataclass
class View:
    span: Span
    text: str
    excluded: bool
    candidate: bool
    rejected: bool
    spray: bool
    arch: str | None
    context_body: str | None
    context_subject: str | None
    context_items: tuple[str, ...]
    gap: bool

    @property
    def adopted(self) -> bool:
        """R01 section scope, R03 adoption status, R04 spray."""
        return not (self.excluded or self.candidate or self.rejected or self.spray)


def _single_body(text: str) -> str | None:
    names = {name for _s, _e, name in find_bodies(text)[0]}
    return next(iter(names)) if len(names) == 1 else None


LEGEND_PAIR = r"(?:^|[:：；;，,、\s])([一-鿿]|[A-Z])\s*=\s*([^；;。，,=\s]{1,12})"
# N08: a Latin code may also be defined by a space (角色：D 起草、R 复核、F 终审)
# N08: a symbol legend (◎决策/批准 ●审核 ○提案) defines symbol codes the same way
LEGEND_PAIR_SYMBOL = r"(?:^|[:：；;，,、\s])([◎●○◉■□◆◇★☆▲△▼▽])\s*([^\s；;。，,=◎●○◉■□◆◇★☆▲△▼▽]{1,12})"
LEGEND_PAIR_SPACED = r"(?:^|[:：；;，,、\s])([A-Z])\s+([一-鿿]{1,10})(?=$|[、；;，,。\s])"
LEGEND_ROLE_WORD = {"final": "审批", "review": "审核", "draft": "制定"}


def legend_codes(spans: list[Span]) -> dict[str, str]:
    """N08: a legend span defining at least two single-character codes maps each code whose
    meaning names a role token to that role."""
    codes: dict[str, str] = {}
    for span in spans:
        pairs = re.findall(LEGEND_PAIR, span.text)
        if len(pairs) < 2:
            pairs = re.findall(LEGEND_PAIR_SPACED, span.text)
        if len(pairs) < 2:
            pairs = re.findall(LEGEND_PAIR_SYMBOL, span.text)
        if len(pairs) < 2:
            continue
        for code, meaning in pairs:
            roles = {role for _s, _e, role in find_roles(meaning)}
            if len(roles) == 1 and code not in codes:
                codes[code] = next(iter(roles))
    return codes


NEGATED_HEADER = r"不做|不负责|不参与|无权|不包括|不决定"
MATTER_HEADER = r"事项|决策|内容|对象|项目|范围|标准|判定|条件"


def role_header(header: str) -> str | None:
    """R12/R13: a column header is a role column only when it is short (at most four characters),
    names exactly one role class, names no decision item and is not negated."""
    compact = re.sub(r"[\s*（）()]", "", header or "")
    # One-character role headers may use the first character of the declared
    # Chinese role. "起" is the common abbreviation of 起草.
    single = {"拟": "draft", "起": "draft", "审": "review", "决": "final", "批": "final"}
    if compact in single:
        return single[compact]
    if not compact or len(compact) > 4 or re.search(NEGATED_HEADER, compact) or find_items(compact, None)[0] \
            or re.fullmatch(r"(?:审批|决策)?(?:事项|内容|对象|项目|范围|标准|判定|条件)", compact):
        return None
    roles = {role for _s, _e, role in find_roles(compact)}
    return next(iter(roles)) if len(roles) == 1 else None


def expand_codes(text: str, codes: dict[str, str]) -> str:
    """N08: a standalone legend code inside a table cell becomes its role word (并/与/和/及 may touch it)."""
    if not codes:
        return text
    cjk = "".join(code for code in codes if not code.isascii())
    latin = "".join(code for code in codes if code.isascii())
    if cjk:
        pattern = "(?:(?<![一-鿿])|(?<=[并与和及]))([" + cjk + "])(?:(?![一-鿿])|(?=[并与和及]))"
        text = re.sub(pattern, lambda m: LEGEND_ROLE_WORD[codes[m.group(1)]], text)
    if latin:
        # N08: a single uppercase Latin code counts only when no other Latin letter touches it
        text = re.sub("(?<![A-Za-z])([" + latin + "])(?![A-Za-z])", lambda m: LEGEND_ROLE_WORD[codes[m.group(1)]], text)
    return text


def document_aliases(spans: list[Span]) -> dict[str, str]:
    """N10: a subject phrase followed by a bracketed lowercase alias of one or two letters (（n）) defines that
    alias; uppercase brackets such as (BU) are unit labels, not aliases."""
    aliases: dict[str, str] = {}
    for span in spans:
        for match in re.finditer(r"([一-鿿]{2,12})\s*[（(]\s*([a-z]{1,2})\s*[）)]", span.text):
            phrase, alias = match.group(1), match.group(2)
            if any(re.fullmatch(pattern, phrase) for _kind, pattern in SUBJECT_TOKENS) and alias not in aliases:
                aliases[alias] = phrase
    return aliases


def expand_aliases(text: str, aliases: dict[str, str]) -> str:
    for alias, phrase in aliases.items():
        text = re.sub("(?<![A-Za-z（(])" + re.escape(alias) + "(?![A-Za-z0-9+＋）)])", phrase, text)
    return text


def views(spans: list[Span]) -> list[View]:
    result = []
    codes = legend_codes(spans)
    aliases = document_aliases(spans)
    firsts = {span.headings[0] if span.headings else None for span in spans}
    title = next(iter(firsts)) if len(firsts) == 1 and None not in firsts and any(len(span.headings) > 1 for span in spans) else None
    for span in spans:
        if span.kind == "table_cell_line" and span.header_cells:
            # R12: a bare 决策 header after a column already read as a role column is the final-role column
            cells = list(span.header_cells)
            for position, header in enumerate(cells):
                if re.fullmatch(r"\s*决策\s*", header) and any(role_header(expand_codes(cells[q], codes)) for q in range(position)):
                    cells[position] = "最终决策"
            column = re.search(r"/col\[(\d+)\]", span.path)
            if column and int(column.group(1)) < len(cells):
                span.col_header = cells[int(column.group(1))]
            span.header_cells = tuple(cells)
        text, quoted = strip_quotes(expand_aliases(span.text, aliases))
        if span.kind == "table_cell_line":
            text = expand_codes(text, codes)
            span.col_header = expand_codes(span.col_header, codes)
        items, _, _ = find_items(text, None)
        mud = any(len({b[2] for b in find_bodies(c)[0]}) >= 3 and len(find_roles(c)) >= 3
                  for c in re.split(r"[,，;；。]", text))
        context_body = None
        for source in (span.col_header, span.row_header, span.lead_in, *reversed(span.headings)):
            if source:
                context_body = _single_body(source)
                if context_body:
                    break
        context_items: tuple[str, ...] = ()
        context_subject = None
        for source in (expand_aliases(span.row_header, aliases), span.lead_in, *reversed(span.headings)):
            if not source:
                continue
            found, _, _ = find_items(source, None)
            if found:
                context_items = tuple(item for _s, _e, item in found)
                break
            subject = subject_of(find_bodies(source)[1])
            if subject:
                context_subject = subject
                break
        body_column = span.kind == "table_cell_line" and bool(find_bodies(span.col_header)[0])
        if span.kind == "table_cell_line" and not context_items and (role_header(span.col_header) or body_column):
            row_subject = context_subject
            for position, cell in enumerate(span.row_cells):
                header = span.header_cells[position] if position < len(span.header_cells) else ""
                if role_header(expand_codes(header, codes)) or find_bodies(header)[0]:
                    continue
                cell = expand_aliases(cell, aliases)
                # R12: a cell changes the row subject only when it names a subject outside brackets
                cell_outside = re.sub(r"[（(][^）)]*[）)]", "", cell)
                subject = subject_of(find_bodies(cell_outside)[1]) if cell_outside.strip() else None
                scope_body = re.fullmatch(r"\s*(集团|股份公司|股份)(?:整体|层面|总部|本部)\s*", cell)
                if not subject and scope_body:
                    subject = "group" if scope_body.group(1) == "集团" else "gufen"
                bu_scope = re.fullmatch(r"\s*(?:(酒店|投资)\s*BU|(养老公司))\s*", cell)
                if not subject and bu_scope:
                    subject = "pension" if bu_scope.group(2) else ("hotel" if bu_scope.group(1) == "酒店" else "div")
                if subject and not find_items(cell, None)[0]:
                    row_subject = subject
                found, _, _ = find_items(cell, row_subject)
                if found:
                    context_items = tuple(item for _s, _e, item in found)
                    break
        arch = arch_of(span)
        section_headings = span.headings[1:] if title is not None else span.headings
        if arch is None and any(re.search(r"中远期|远期|长期", h) for h in section_headings) and \
                re.search(r"共同|两种|均适用|都适用", span.lead_in + text):
            arch = "common"
        result.append(View(
            span=span,
            text=text,
            excluded=any(re.search(EXCLUDED_HEADING, heading) for heading in span.headings),
            candidate=bool(re.search(CANDIDATE, re.sub(r"(?:无论|不论|不管)[^，,；;。]{0,10}是否|是否[^，,；;。]{0,12}由[^，,；;。]{0,10}(?:决定|决策|审批|批准)", "", text))),
            rejected=bool(re.search(REJECT, text)) or quoted,
            spray=(len(text) > SPAN_MAX_CHARS or len(items) > SPAN_MAX_ITEMS or mud),
            arch=arch,
            context_body=context_body,
            context_subject=context_subject,
            context_items=context_items,
            gap=any(marker in text for marker in GAP_MARKERS),
        ))
    return result


@dataclass
class Triple:
    item: str
    body: str
    role: str
    view: View


def _negated(text: str, start: int, end: int) -> bool:
    return bool(re.search(NEG, text[max(0, start - 3):end]))


def _coordinated(bodies: list[tuple[int, int, str]], index: int, text: str) -> list[tuple[int, int, str]]:
    group = [bodies[index]]
    cursor = index
    while cursor > 0 and re.fullmatch(r"[\s与和及、/或]*", text[bodies[cursor - 1][1]:bodies[cursor][0]]):
        cursor -= 1
        group.append(bodies[cursor])
    return group


def pair_roles(clause: str, inherited_body: str | None, context_role: str | None,
               table_body: bool = False) -> tuple[list[tuple[str, str, int]], str | None]:
    """R05: pair each role with the nearest preceding body (coordinated bodies share it), else the
    nearest following body, else the inherited body; negated pairs are dropped."""
    bodies, _ = find_bodies(clause)
    roles = find_roles(clause)
    pairs = []
    last_body = bodies[-1][2] if bodies else inherited_body
    if not roles and context_role:
        if bodies:
            brackets = [(m.start(), m.end()) for m in re.finditer(r"[（(][^）)]*(?:[）)]|$)", clause)]
            outside = [b for b in bodies if not any(a <= b[0] and b[1] <= z for a, z in brackets)]
            for start, end, name in (outside or bodies):
                if not _negated(clause, max(0, start - 3), end):
                    pairs.append((name, context_role, start))
        elif inherited_body:
            pairs.append((inherited_body, context_role, 0))
        return pairs, last_body
    for r_start, r_end, role in roles:
        preceding = [index for index, body in enumerate(bodies) if body[1] <= r_start]
        if preceding:
            group = _coordinated(bodies, preceding[-1], clause)
            if not _negated(clause, min(b[0] for b in group), r_end):
                for _b_start, _b_end, name in group:
                    pairs.append((name, role, r_start))
            continue
        following = [body for body in bodies if body[0] >= r_end and body[0] - r_end <= 8]
        if following and not (table_body and inherited_body):
            _b_start, b_end, name = following[0]
            if not _negated(clause, r_start, b_end):
                pairs.append((name, role, r_start))
            continue
        if inherited_body and not _negated(clause, 0, r_end):
            pairs.append((inherited_body, role, r_start))
    return pairs, last_body


BRACKET = r"[（(][^）)]*(?:[）)]|$)|^[^（(]*[）)]"
CONDITIONAL = r"(?<![同及适随届临])时(?![间期点效])"


OPENED = r"[（(][^）)]*(?:[）)]|$)"
# R12: a body that only supplies input to the drafter (股份公司与养老公司分别提供输入/建议/方案) does not take the column role
DECLINE = r"^[^；;。]{0,12}(?:不参与|不涉及|不介入|无权|不负责|不决定|不审批|授权)|^[^；;。，,]{0,10}(?:分别)?(?:提供|给出|报送)[^；;。，,]{0,6}(?:输入|建议|方案|意见|数据|资料|测算)"


def column_pairs(clause: str, inherited_body: str | None, context_role: str, tail: str = "") -> tuple[list[tuple[str, str, int]], str | None]:
    """R05/R12: in a role column, text outside brackets takes the column role unless it names its own role;
    bracketed notes pair only their own explicit roles; bodies in a negated or conditional clause do not
    take the column role, and bracket bodies are not carried to the next clause."""
    outside = re.sub(BRACKET, lambda m: "□" * len(m.group(0)), clause)
    if find_roles(outside):
        return pair_roles(clause, inherited_body, context_role)
    pairs: list[tuple[str, str, int]] = []
    bodies, _ = find_bodies(outside)
    conditional = bool(re.search(CONDITIONAL, outside))
    if conditional:
        return pairs, None
    spans_opened = [(m.start(), m.end()) for m in re.finditer(OPENED, clause)]
    inner_only = "".join(ch if any(a <= i < z for a, z in spans_opened) else "□" for i, ch in enumerate(clause))
    candidates = bodies or find_bodies(inner_only)[0]
    window_text = outside if bodies else inner_only
    for start, end, name in candidates:
        if bodies:
            after = re.sub(BRACKET, lambda m: "□" * len(m.group(0)), clause[end:]) + re.sub(BRACKET, lambda m: "□" * len(m.group(0)), tail)
        else:
            after = clause[end:] + tail  # bracket-only candidates: the decline may follow inside the same bracket
        if re.search(NEG, window_text[max(0, start - 3):end + 4]) or re.match(DECLINE, after):
            continue
        pairs.append((name, context_role, start))
    if not candidates and inherited_body and not re.search(NEG, outside):
        pairs.append((inherited_body, context_role, 0))
    for match in re.finditer(BRACKET, clause):
        inner = match.group(0).strip("（()）")
        if find_roles(inner):
            inner_pairs, _ = pair_roles(inner, None, None)
            pairs.extend((name, role, match.start() + position) for name, role, position in inner_pairs)
    return pairs, (bodies[-1][2] if bodies else inherited_body)


def decision_triples(all_views: list[View]) -> list[Triple]:
    triples = []
    for view in all_views:
        if not view.adopted or view.arch is not None:
            continue
        text = view.text
        if re.fullmatch(LABEL + r"\s*$", text) or re.fullmatch(r"[\s—\-–/无]*", text):
            continue
        if view.span.kind == "table_cell_line" and re.search(NEGATED_HEADER, view.span.col_header):
            continue
        context_role = None
        header_role = False
        for source in (view.span.col_header, view.span.row_header):
            role = role_header(source)
            if role:
                context_role = role
                header_role = True
                break
        if view.span.kind == "table_cell_line" and not find_roles(text):
            prefix = view.span.path.rsplit("/line", 1)[0]
            for previous in reversed(all_views[:view.span.index]):
                if previous.span.path.rsplit("/line", 1)[0] != prefix:
                    break
                match = re.match(LABEL, previous.text)
                if match:
                    context_role = next(role for role, pattern in ROLE_TOKENS if re.fullmatch(pattern, match.group(1)))
                    break
        inherited_subject = view.context_subject
        # R05: in a role-column table the body must be named in the cell itself
        inherited_body = None if header_role else view.context_body
        scope_items: list[str] = []
        cursor = 0
        # R05: 发展策略由集团决定、竞争策略由股份公司决定 is two clauses, each with its own body
        for clause in re.split(r"(?<=[;；。])|[,，→]|、(?=[^、，,；;。]{2,14}由[^、，,；;。]{1,12}(?:决定|决策|审批|批准|终审|审定))", text):
            located = text.find(clause, cursor)
            cursor = located + len(clause) if located >= 0 else cursor
            tail = re.split(r"[;；。]", text[cursor:])[0] if not re.search(r"[;；。]$", clause) else ""
            if not clause.strip():
                continue
            if re.search(r"[;；。]$", clause):
                clause = clause[:-1]
                reset_after = True
            else:
                reset_after = False
            items, masked, inherited_subject = find_items(clause, inherited_subject)
            if items:
                scope_items = [item for _s, _e, item in items]
            elif not scope_items:
                scope_items = list(view.context_items)
            # R05: 在集团授权内决策 names the scope of the column body's decision, not a second decider
            masked = re.sub(r"在\s*(?:集团|股份(?:公司)?)[^，,；;。]{0,6}(?:授权|权限|批准)(?:的)?(?:范围)?(?:内|之内)",
                            lambda m: "□" * len(m.group(0)), masked)
            if re.search(CONDITIONAL, masked) and re.search(r"超(?:出|过)?(?:授权|权限|额度)", masked) and find_roles(masked):
                # R12: an escalation condition (超授权或涉及…时决策) says when a matter goes up, not who holds it
                continue
            if header_role and context_role:
                pairs, inherited_body = column_pairs(masked, inherited_body, context_role, tail)
            else:
                pairs, inherited_body = pair_roles(masked, inherited_body, context_role,
                                                   view.span.kind == "table_cell_line" and view.context_body is not None
                                                   and inherited_body == view.context_body)
            for body, role, _position in pairs:
                for item in scope_items:
                    triples.append(Triple(item, body, role, view))
            if reset_after:
                scope_items = []
    return triples


@dataclass
class Target:
    issuer: str
    receivers: set[str]
    view: View
    rule_clause: bool


def _receivers(clause: str) -> set[str]:
    found = set()
    work = clause
    for name, pattern in RECEIVER_TOKENS:
        for match in re.finditer(pattern, work):
            found.add(name)
            work = _mask(work, match.start(), match.end())
    return found


def target_pairs(all_views: list[View]) -> list[Target]:
    """R06: issuer and receivers of annual targets and budgets."""
    targets = []
    for view in all_views:
        if not view.adopted or view.arch is not None:
            continue
        span = view.span
        header_target = bool(re.search(TARGET_WORD, span.row_header + span.col_header))
        in_context = header_target or bool(re.search(TARGET_WORD, view.text)) or any(
            re.search(TARGET_WORD, heading) for heading in span.headings[-1:]) or (
            span.kind == "table_cell_line" and any(re.search(r"下达方|下达主体", h) for h in span.header_cells))
        if not in_context:
            continue
        headers = span.header_cells if span.kind == "table_cell_line" else ()
        issuer_table = any(re.search(r"下达方|下达主体", h) for h in headers) and any(re.search(r"接收方|接收", h) for h in headers)
        if issuer_table:
            # R06: issuer-row target table; receivers come from the receiver and content cells of the row only
            if re.search(r"编制|跟踪|承办|证据|依据|说明|备注", span.col_header):
                continue
            issuer = _single_body(span.row_header)
            if issuer and re.search(r"接收|内容", span.col_header):
                bodies, masked = find_bodies(view.text)
                receivers = _receivers(masked) | {name for b_start, b_end, name in bodies if name != issuer
                                                  and not re.match(EXECUTOR, view.text[b_end:])}
                if not re.search(r"接收", span.col_header):
                    # the content cell names what is issued; unit receivers come only from the receiver cell
                    receivers &= {"hotel_agg", "pension_agg", "div_agg"}
                if issuer == "集团" and "养老公司" in receivers:
                    receivers.add("pension_agg")
                if receivers:
                    targets.append(Target(issuer, receivers, view, bool(re.search(r"不再|不向|不对|不(?:另行|单独|再)?下达", view.text))))
            continue
        for clause in re.split(r"[;；。]", view.text):
            if not clause.strip() or re.search(r"由谁|给谁|谁来|向谁", clause):
                continue
            arrow_line = re.match(r"^\s*(?:─*[→▶►⇒]|->)\s*(.*)$", clause)
            if span.kind == "table_cell_line" and arrow_line and view.context_body:
                cell_bodies, cell_masked = find_bodies(arrow_line.group(1))
                cell_receivers = _receivers(cell_masked) | {name for _s, _e, name in cell_bodies if name != view.context_body}
                if view.context_body == "集团" and "养老公司" in cell_receivers:
                    cell_receivers.add("pension_agg")
                if cell_receivers:
                    targets.append(Target(view.context_body, cell_receivers, view, bool(re.search(r"不再|不向|不对|不(?:另行|单独|再)?下达", clause))))
                continue
            rule_clause = bool(re.search(r"按[其照]?[^，,]{0,2}管理(?:关系|架构)|去法人|管理关系[^；;。，,]{0,6}(?:已)?(?:转入|划入|归入|转至)", clause)) or bool(
                re.search(r"不(?:再)?(?:越级)?(?:直接)?(?:向|对|给)[^；;。]{0,40}(?:下达|下发|发指令|发出指令)", clause)) or bool(
                re.search(r"(?:不再|不)[^，,]{0,6}(?:由集团)?[^，,]{0,4}(?:下达|下发|分解)", clause))
            bodies, masked = find_bodies(clause)
            _items, masked, _ = find_items(masked, None)
            verb = re.search(r"(?:" + TARGET_VERB + r")(?!关系|路径|方式|体系|机制|流程)", masked)
            issuer = None
            if verb and re.search(r"不|并非|无需|无须|未", masked[:verb.start()]):
                rule_clause = True
            receiving: set[int] = set()
            for index, body in enumerate(bodies):
                if re.search(r"(?:向|对|给|至|到|为)\s*$", clause[max(0, body[0] - 2):body[0]]) or (
                        index - 1 in receiving and re.fullmatch(r"[\s、和与及/]*", clause[bodies[index - 1][1]:body[0]])):
                    receiving.add(index)
            if verb:
                led = [b for b in bodies if re.search(r"由\s*$", clause[max(0, b[0] - 1):b[0]])]
                before = [b for index, b in enumerate(bodies) if b[1] <= verb.start() and index not in receiving
                          and not re.match(EXECUTOR, clause[b[1]:])]
                if led:
                    issuer = led[-1][2]
                elif before:
                    issuer = before[-1][2]
                elif view.context_body and (not bodies or all(index in receiving for index, b in enumerate(bodies) if b[1] <= verb.start())):
                    issuer = view.context_body
            elif span.kind == "table_cell_line" and re.search(r"下达方|下达主体|由谁下达|下达单位", span.col_header) and bodies:
                if len({b[2] for b in bodies}) == 1 and _single_body(span.row_header):
                    targets.append(Target(bodies[0][2], {_single_body(span.row_header)}, view, rule_clause))
                continue
            elif header_target and span.kind == "table_cell_line" and view.context_body and (
                    _single_body(span.col_header) or _single_body(span.row_header)
                    or any(re.search(TARGET_VERB, h) and _single_body(h) == view.context_body for h in span.headings[-1:])):
                # R06: the implicit issuer of a target cell is the body its column or row names, or its own heading
                # when that heading is about issuing (集团下达什么); a body named only in a general heading is not an issuer
                issuer = _single_body(span.col_header) or _single_body(span.row_header) or view.context_body
            if issuer is None:
                continue
            receivers = _receivers(masked) | {name for b_start, b_end, name in bodies if name != issuer
                                              and not re.match(EXECUTOR, clause[b_end:])}
            if not receivers and span.kind == "table_cell_line" and re.search(TARGET_WORD, span.row_header) \
                    and (verb or any(role == "final" for _s, _e, role in find_roles(clause))) \
                    and _single_body(span.col_header) == issuer:
                row_bodies, row_masked = find_bodies(span.row_header)
                receivers = _receivers(row_masked) | {name for _s, _e, name in row_bodies if name != issuer}
            # R06: the pension company is the pension aggregate's receiver in prose too, as in the table and arrow paths
            if issuer == "集团" and "养老公司" in receivers:
                receivers.add("pension_agg")
            if receivers:
                targets.append(Target(issuer, receivers, view, rule_clause))
    targets.extend(arrow_targets(all_views))
    return targets


def arrow_targets(all_views: list[View]) -> list[Target]:
    """R10: a fenced tree line with an arrow and a target word issues from the body named before
    the arrow, else from the nearest shallower fenced line naming exactly one body."""
    found = []
    for position, view in enumerate(all_views):
        span = view.span
        tree_text = re.sub(r"─*[▶►⇒]|->", "→", view.text)
        if "→" not in tree_text or not view.adopted or view.arch is not None:
            continue
        if span.kind != "code_line":
            lead = tree_text.split("→", 1)[0]
            if span.kind not in ("list_item", "paragraph_sentence") or len(lead.strip()) > 12 or not _single_body(lead):
                continue
        if not (re.search(TARGET_WORD, view.text) or any(re.search(TARGET_WORD, h) for h in span.headings)):
            continue
        left, right = tree_text.split("→", 1)
        if not re.search(TARGET_WORD, right) and not re.search(TARGET_VERB, right) and not (
                span.kind != "code_line" and any(re.search(TARGET_WORD, h) for h in span.headings[-1:])):
            continue
        issuer = _single_body(left)
        block = span.path.split("/")[0]
        if issuer is None and not left.strip(" ─-(（)）"):
            for previous in reversed(all_views[:position]):
                if previous.span.kind != "code_line" or previous.span.path.split("/")[0] != block:
                    break
                if previous.span.depth < span.depth:
                    previous_text = re.sub(r"─*[▶►⇒]|->", "→", previous.text)
                    candidate = _single_body(previous_text.split("→")[-1] if "→" in previous_text else previous_text)
                    if candidate:
                        issuer = candidate
                        break
        elif issuer is None:
            for previous in reversed(all_views[:position]):
                if previous.span.kind != "code_line" or previous.span.path.split("/")[0] != block:
                    break
                if previous.span.depth < span.depth and _single_body(previous.text):
                    issuer = _single_body(previous.text)
                    break
        if issuer is None:
            continue
        bodies, masked = find_bodies(right)
        receivers = _receivers(masked) | {name for _s, _e, name in bodies if name != issuer}
        if issuer == "集团" and "养老公司" in receivers:
            receivers.add("pension_agg")
        if receivers:
            found.append(Target(issuer, receivers, view, bool(re.search(r"不再|不", right))))
    return found


# ---------------------------------------------------------------------------
# Layer 3: decisions
# ---------------------------------------------------------------------------

class Ledger:
    """Turn spans into locators and runtime-registered observations."""

    def __init__(self, judge: ProgramJudge, artifact: Path):
        self.judge = judge
        self.artifact = artifact.as_posix()
        self.counter = 0

    def span_locator(self, view: View, object_key: str, field_name: str) -> Locator:
        return Locator(
            locator_id=f"L{view.span.index}", artifact_path=self.artifact, container_type=view.span.kind,
            container_path=" > ".join(view.span.headings) + " :: " + view.span.path, object_key=object_key,
            field=field_name, observed=view.span.text[:240],
        )

    def doc_locator(self, object_key: str) -> Locator:
        return Locator(locator_id="L-doc", artifact_path=self.artifact, container_type="document",
                       container_path="document", object_key=object_key, field="whole_document", observed="")

    def observe(self, prefix: str, state: str, views_used: list[View], object_key: str, field_name: str,
                derivation: str | None = None, observed: str = "") -> str:
        self.counter += 1
        identity = f"{prefix}#{self.counter}"
        locators: list[Locator] = []
        seen = set()
        for view in views_used:
            locator = self.span_locator(view, object_key, field_name)
            if locator.locator_id not in seen:
                seen.add(locator.locator_id)
                locators.append(locator)
        if not locators:
            locators = [self.doc_locator(object_key)]
        elif derivation and state == "identified":
            locators.append(Locator(
                locator_id=f"D-{identity}", artifact_path=self.artifact, container_type="derived",
                container_path="derived", object_key=object_key, field=field_name, observed=observed[:240],
                evidence_origin="deterministically_derived",
                source_locator_ids=tuple(locator.locator_id for locator in locators), derivation_rule_id=derivation,
            ))
        return self.judge.observe(identity, state, locators)


def fmt(value) -> str:
    """Deterministic rendering of role slots (sets sorted) for ledger text."""
    if value is None:
        return "None"
    return "{" + ", ".join(f"{key}: {sorted(val)}" for key, val in value.items()) + "}"


def _highest(bodies: set[str]) -> str | None:
    if not bodies:
        return None
    top = max(RANK.get(body, 0) for body in bodies)
    names = {body for body in bodies if RANK.get(body, 0) == top}
    return next(iter(names)) if len(names) == 1 else None


def _clause_hits(view: View, pattern: str) -> bool:
    return adopted_match(view.text, pattern)


def adopted_match(text: str, pattern: str) -> bool:
    """R03: a statement match counts only when its own comma clause does not negate it before the match."""
    for sentence in re.split(r"[;；。]", text):
        if re.match(r"\s*(?:并非|并不|不是|并没有|没有|不应|不宜|无需)", sentence):
            continue
        for match in re.finditer(pattern, sentence):
            prefix = re.split(r"[,，]", sentence[:match.start()])[-1]
            if not re.search(r"不|非|没有|未|无|取消|区别于|不同于", prefix):
                return True
    return False


def _chars(text: str) -> int:
    return len(re.findall(CHARS, re.sub(r"<br\s*/?>", "", text)))


def section_chars(text: str, pattern: str, other: str) -> int:
    """R08: characters under the heading naming one architecture variant, heading line included."""
    total, active, level, in_fence = 0, False, 0, False
    for line in text.split("\n"):
        heading = None if in_fence else re.match(r"^(#{1,6})\s+(.*)$", line.strip())
        if line.strip().startswith("```"):
            in_fence = not in_fence
        if heading:
            depth = len(heading.group(1))
            if active and depth <= level:
                active = False
            if re.search(pattern, heading.group(2)) and not re.search(other, heading.group(2)):
                active, level = True, depth
        if active:
            total += _chars(line)
    return total


def evaluate_document(raw: dict, judge: ProgramJudge) -> None:
    contract = judge.contract
    ledger = Ledger(judge, raw["artifact"])
    state = raw["state"]
    if state != "identified":
        for item in contract["positive_items"]:
            obs = ledger.observe(item["id"], state, [], item["object_key"], "document")
            judge.positive(item["id"], 0.0, obs, f"artifact {state}",
                           "missing" if state == "confirmed_missing" else "different")
        for item in contract["deduction_items"]:
            obs = ledger.observe(item["id"], state, [], item["object_key"], "document")
            judge.deduction(item["id"], "parse_failure" if state == "parse_failure" else "not_applicable",
                            [obs], f"artifact {state}")
        return

    all_views = views(raw["spans"])
    from semantic_judge import adjudicate
    try:
        semantic = adjudicate(Path(raw["artifact"]).read_text(encoding="utf-8"))
    except Exception as exc:
        sys.stderr.write("Required semantic judgement failed; no score published\n")
        raise SystemExit(2)
    judge.semantic_verdict=semantic

    triples = decision_triples(all_views)
    targets = target_pairs(all_views)
    doc_obs = ledger.observe("doc", "identified", [], "document", "whole_document")

    roles: dict[str, dict[str, set[str]]] = {}
    support: dict[tuple[str, str, str], list[View]] = {}
    for triple in triples:
        roles.setdefault(triple.item, {"draft": set(), "review": set(), "final": set()})[triple.role].add(triple.body)
        support.setdefault((triple.item, triple.role, triple.body), []).append(triple.view)

    def slot(item: str, role: str) -> set[str]:
        return roles.get(item, {}).get(role, set())

    def final_top(item: str) -> str | None:
        return _highest(slot(item, "final"))

    def views_for(*keys: tuple[str, str, str]) -> list[View]:
        found = []
        for key in keys:
            found.extend(support.get(key, []))
        return found

    def ambiguous(item: str) -> bool:
        return any(len(slot(item, role)) >= 3 for role in ("draft", "review", "final"))

    def touched_items(*items: str) -> list[View]:
        return [t.view for t in triples if t.item in items]

    def positive_fraction_now(item_id: str) -> float:
        return judge._positive_results.get(item_id, {}).get("fraction", 0.0)

    def semantic_views(item_id: str) -> tuple[float, list[View]]:
        decision = semantic["items"][item_id]
        selected = [
            view for view in all_views
            if any(
                view.text in unicodedata.normalize("NFKC", quote)
                or unicodedata.normalize("NFKC", quote) in view.text
                or view.span.text in unicodedata.normalize("NFKC", quote)
                for quote in decision["quotes"]
            )
        ]
        if decision["fraction"] and not selected:
            raise ValueError("semantic evidence not bound to parsed artifact spans: " + item_id)
        return float(decision["fraction"]), selected

    def emit_positive(item_id: str, parts: list[tuple[float, bool, list[View]]], note: str,
                      touched: list[View], is_ambiguous: bool = False) -> None:
        if item_id in ("P11", "P12", "P13", "P14"):
            weights = {
                "P11": [("P11_POSITION", .35), ("P11_CAPITAL", .20),
                         ("P11_SUPERVISION", .25), ("P11_INVESTMENT_REVIEW", .20)],
                "P12": [("N1_LEVELS", .20), ("N1_DESTINATIONS", .30),
                         ("N1_NEW_BU", .15), ("N1_ENTITY", .15), ("N1_FUNCTIONS", .20)],
                "P13": [("TWO_PLATFORMS", .10), ("TWO_LISTED", .10),
                         ("TWO_PARK_BU", .15), ("TWO_PENSION_BU", .15),
                         ("TWO_LEVELS", .20), ("TWO_FUNCTIONS", .30)],
                "P14": [("TARGET_GROUP", .20), ("TARGET_LISTED", .20),
                         ("TARGET_DIVERSIFIED", .20), ("TARGET_INVESTMENT_PROCESS", .20),
                         ("TARGET_HOTELS", .20)],
            }[item_id]
            parts=[]
            for key,weight in weights:
                fraction, selected = semantic_views(key)
                parts.append((weight * fraction, bool(fraction), selected))
            note="Unified gpt-5.6-sol source-bound semantic adjudication"
            touched=[v for _,_,vs in parts for v in vs]
            is_ambiguous=False
        spec = judge.positives[item_id]
        fraction = round(sum(share for share, ok, _v in parts if ok), 6)
        used = [view for _share, ok, vs in parts if ok for view in vs]
        if is_ambiguous:
            obs = ledger.observe(item_id, "ambiguous", touched, spec["object_key"], "decision")
            judge.positive(item_id, 0.0, obs, note + "; conflicting allocations", "different")
        elif fraction <= 0:
            if touched:
                obs = ledger.observe(item_id, "identified", touched, spec["object_key"], "decision", "R07", note)
                judge.positive(item_id, 0.0, obs, note, "different")
            else:
                obs = ledger.observe(item_id, "confirmed_missing", [], spec["object_key"], "decision")
                judge.positive(item_id, 0.0, obs, note, "missing")
        else:
            full = fraction >= 0.999
            obs = ledger.observe(item_id, "identified", used or touched, spec["object_key"], "decision", "R07", note)
            judge.positive(item_id, 1.0 if full else fraction, obs, note, "equivalent" if full else "partial")

    # P03 unit-level competitive strategy approved by the directly managing BU
    emit_positive("P03", [
        (0.5, final_top("hotel_unit_comp") == "酒店BU", views_for(("hotel_unit_comp", "final", "酒店BU"))),
        (0.5, final_top("div_unit_comp") == "投资BU", views_for(("div_unit_comp", "final", "投资BU"))),
    ], f"unit comp roles={fmt(roles.get('hotel_unit_comp'))},{fmt(roles.get('div_unit_comp'))}",
        touched_items("hotel_unit_comp", "div_unit_comp"),
        ambiguous("hotel_unit_comp") or ambiguous("div_unit_comp"))

    # P04 pension strategy held at group
    emit_positive("P04", [
        (0.5, "集团" in slot("pension_dev", "draft") and final_top("pension_dev") == "集团",
         views_for(("pension_dev", "draft", "集团"), ("pension_dev", "final", "集团"))),
        (0.5, final_top("pension_comp") == "集团", views_for(("pension_comp", "final", "集团"))),
    ], f"pension roles={fmt(roles.get('pension_dev'))},{fmt(roles.get('pension_comp'))}",
        touched_items("pension_dev", "pension_comp"), ambiguous("pension_dev") or ambiguous("pension_comp"))

    # P07 incubation strategy decided at the listed company
    incub_dev_owner = slot("incub_dev", "draft") | slot("incub_dev", "final")
    emit_positive("P07", [
        (0.5, "股份" in slot("incub_dev", "draft") and final_top("incub_dev") == "股份" and "投资BU" not in incub_dev_owner,
         views_for(("incub_dev", "draft", "股份"), ("incub_dev", "final", "股份"))),
        (0.5, final_top("incub_comp") == "股份", views_for(("incub_comp", "final", "股份"))),
    ], f"incubation roles={fmt(roles.get('incub_dev'))},{fmt(roles.get('incub_comp'))}",
        touched_items("incub_dev", "incub_comp"), ambiguous("incub_dev") or ambiguous("incub_comp"))

    # BU final approvals over investments or asset changes (R09), charged by D08
    bu_approvals: list[tuple[str, View]] = []
    for view in all_views:
        if not view.adopted or view.arch is not None:
            continue
        table_cell = view.span.kind == "table_cell_line"
        if table_cell and re.search(NEGATED_HEADER, view.span.col_header):
            continue
        role_column = bool(role_header(view.span.col_header)) if table_cell else False
        matter_cells = [cell for position, cell in enumerate(view.span.row_cells)
                        if position < len(view.span.header_cells) and re.search(MATTER_HEADER, view.span.header_cells[position])]
        row_text = view.span.row_header + ("|" + "|".join(matter_cells) if role_column else "")
        row_invest = bool(re.search(INVEST_WORD, re.sub(NEGATED_INVEST, "", clause_masked_items(find_bodies(row_text)[1]))))
        if role_column:
            row_text += "|" + "|".join(header for header in view.span.header_cells if re.search(MATTER_HEADER, header))
            # R09: an approval table under a heading that names investment or asset-change approval
            heading = view.span.headings[-1] if view.span.headings else ""
            if re.search(r"(?:投资|资产变更)[^，,；;。]{0,8}(?:审批|决策|权限)", heading):
                row_text += "|" + heading
            row_invest = bool(re.search(INVEST_WORD, re.sub(NEGATED_INVEST, "", clause_masked_items(find_bodies(row_text)[1]))))
        for sentence in re.split(r"[;；。]", view.text):
            inherited = view.context_body if table_cell and not role_column else None
            sentence_invest = False
            for clause in re.split(r"[,，]", sentence):
                masked = clause_masked_items(find_bodies(clause)[1])
                clause_invest = bool(re.search(INVEST_WORD, re.sub(NEGATED_INVEST, "", masked)))
                sentence_invest = sentence_invest or clause_invest
                header_role = role_header(view.span.col_header) if role_column else None
                pairs, inherited_next = pair_roles(clause_masked_items(clause), inherited, header_role,
                                                   table_cell and inherited == view.context_body)
                inherited = inherited_next
                if not (clause_invest or sentence_invest or row_invest) or not pairs:
                    continue
                if re.search(r"(?:审批|决策)?权限(?:之外|以外)|除外", clause):
                    continue
                finals = {body for body, role, _p in pairs if role == "final"}
                reviews = {body for body, role, _p in pairs if role == "review"}
                denied = {name for name in ("酒店BU", "投资BU")
                          for m in [re.search(r"(?:没有|无|不享有|不具有)[^，,；;。:：]{0,6}(?:投资|资产)[^，,；;。:：]{0,6}(?:决策|审批|决定)权", view.text)
                                    or re.search(r"(?:不持有?|不拥有|不享有|不具有|没有|无)[^，,；;。:：]{0,4}(?:审批|终审|决策|批准)权"
                                                 r"|不(?:向|给|对)[^；;。]{0,30}(?:新增|授予|赋予|下放)[^；;。]{0,20}(?:审批|终审|决策|批准)权", view.text)]
                          if m and name in {b[2] for b in find_bodies(view.text[:m.end()])[0]}}
                for body in (finals & {"酒店BU", "投资BU"}) - denied:
                    if body not in reviews:
                        bu_approvals.append((body, view))

    # P11 is open business semantics: exact duties and equivalent expressions are
    # adjudicated once by the unified source-bound model, not by vocabulary lists.
    emit_positive("P11", [], "source-bound Investment BU responsibility", all_views)

    n1_views = [v for v in all_views if v.adopted and v.arch in ("n1", "common")]
    two_views = [v for v in all_views if v.adopted and v.arch in ("two", "common")]

    def hits(pool: list[View], pattern: str) -> list[View]:
        return [view for view in pool if _clause_hits(view, pattern)]

    # P12 N+1 architecture
    def level_row(pool: list[View], digits: str) -> list[View]:
        return [view for view in pool if view.span.kind == "table_cell_line" and re.search(r"管控层级|管控层次", view.span.row_header)
                and re.match(r"\s*(?:" + digits + r")\s*(?:级|层)", view.text)]
    n1_levels = level_row(n1_views, "三|3") + hits(n1_views, r"管控层级[:：为是]\s*(?:三|3)\s*(?:级|层)|3\s*级管控|三级管控|三层管控|三级管理模式|管控(?:层级|模式)(?:保持)?不变|(?:保持|沿用|维持|延续)[^，,；;。]{0,6}(?:三级|三层)?管控(?:模式|架构|体系)|管控层(?:级)?(?:为|是)[^；;。]{0,30}(?:三|3)\s*级|(?:三|3)\s*个\s*(?:控制|管控)层(?:级|次)?|管控层(?:级)?\s*(?:三|3)\s*级")
    n1_levels += [view for view in n1_views if view not in n1_levels
                  and adopted_match(view.text, r"管控[^；;。]{0,8}与近期(?:架构)?(?:一致|相同)")]
    # R11: the table's first header may name the group (近期仍由集团直接管理的对象 | N+1型归宿)
    n1_moves = [view for view in n1_views if "集团" in (view.span.row_header + view.text + "".join(view.span.header_cells[:1]))
                and not re.search(r"由集团直管|不纳入股份", view.text) and adopted_match(view.span.row_header + "：" + view.text,
        r"(?:其他|其余|除酒店|之外|以外|非酒店|直管)[^；;。]{0,12}(?:产业|企业|业务|公司|利润中心|单位)[^；;。]{0,12}(?:转入|划入|并入|归入|纳入|注入|移交|划转|划归|转至|装入|转移至|交由|进入)[^；;。]{0,6}(?:股份|养老)|集团(?:最终)?只(?:持有|保留|直管)[^，,；;。]{0,8}(?:平台|股份公司|两个)|集团直管(?:企业|单位|经营单位|公司)[^，,；;。]{0,4}清零|集团不再直管(?:任何)?(?:经营单位|企业)")]
    n1_new_bu = hits(n1_views, r"(?:孵化成功|成功孵化|孵化成熟|培育成功|培育成熟|成熟|规模化|做大|壮大)[^；;。]{0,30}(?:形成|设立|成立|升级|升为|升格|上升为|成为|转为|设为|单设|增设|各设|组建)[^；;。]{0,10}(?:BU|事业部|业务单元)|孵化业务[^，,；;。]{0,6}(?:升为|升级为|升格为|转为|设为)[^，,；;。]{0,4}BU")
    upgraded = [view for view in n1_views if adopted_match(view.text, r"由(?:原)?孵化(?:业务|产业|项目)?[^，,；;。]{0,4}(?:升级|升为|转为|发展)")
                and ("BU" in view.text or any("BU" in cell for cell in view.span.row_cells))]
    n1_new_bu = n1_new_bu + [view for view in upgraded if view not in n1_new_bu]
    # R11: a variant table row naming the matured BU, whose cell makes it an entity (新成熟主产业BU | 分别设为实体)
    n1_new_bu += [view for view in n1_views if view not in n1_new_bu and view.span.kind == "table_cell_line"
                  and re.search(r"(?:成熟|孵化成功|成功孵化|规模化)[^；;。|]{0,12}BU", view.span.row_header)
                  and adopted_match(view.text, r"(?:设为|设立|成为|升为|升级为|做实为?)[^，,；;。]{0,4}实体")]
    # R11: an upgrade to a BU in one sentence of a list item whose item states the incubation trigger elsewhere
    item_text: dict[str, str] = {}
    for view in n1_views:
        if view.span.kind in ("list_item", "table_cell_line"):
            key = view.span.path.split("/sentence")[0]
            item_text[key] = item_text.get(key, "") + view.text
    n1_new_bu += [view for view in n1_views if view not in n1_new_bu and view.span.kind in ("list_item", "table_cell_line")
                  and adopted_match(view.text, r"(?:升为|升级为|升格为|转为|设为|成为)[^，,；;。]{0,4}(?:实体)?\s*BU")
                  and re.search(r"孵化成功|成功孵化|孵化成熟|规模化|形成规模", item_text[view.span.path.split("/sentence")[0]])]

    def entity_context(view: View) -> bool:
        sentences = [part for part in re.split(r"[;；。]", view.text) if re.search(r"BU|事业部|业务单元", part)]
        if any("实体" in part and "虚拟" not in part for part in sentences):
            return True
        cells = view.span.row_cells
        return any("实体" in cell for cell in cells) and not any("虚拟" in cell for cell in cells) and "虚拟" not in view.text
    n1_entity = [view for view in n1_new_bu if entity_context(view)]
    emit_positive("P12", [
        (1 / 3, bool(n1_levels), n1_levels),
        (1 / 3, bool(n1_moves), n1_moves),
        (1 / 6, bool(n1_new_bu), n1_new_bu),
        (1 / 6, bool(n1_entity), n1_entity),
    ], f"N+1 levels={len(n1_levels)} moves={len(n1_moves)} new_bu={len(n1_new_bu)} entity={len(n1_entity)}", n1_views)

    def three_level_views(pool: list[View]) -> list[View]:
        level_count = r"管控层级[:：为是]\s*(?:三|3|四|4|五|5)\s*(?:级|层)|(?:三|3|四|4|五|5)\s*(?:级|层)管控|管控(?:仍|依然|还)?(?:为|是)\s*(?:三|3|四|4|五|5)\s*(?:级|层)|(?:三|3|四|4|五|5)\s*个\s*(?:控制|管控)层(?:级|次)?|管控层(?:级)?\s*(?:三|3|四|4|五|5)\s*级"
        found = []
        for v in pool:
            # R02: a sentence that states a conditional exception (只有/仅当/若…时/才) is not the variant's stated count
            # D04: a sentence contrasting the N+1 variant (N+1型…保持三级管控；2型…两级) states the other variant's count
            sentences = [part for part in re.split(r"[;；。]", v.text)
                         if not re.search(r"(?:只有|仅当|仅在|除非)[^；;。]{0,40}(?:时|才)", part) and not re.search(ARCH_N1, part)]
            for clause in re.split(r"[,，]", "；".join(sentences)):
                match = re.search(level_count, clause)
                if match and not re.search(r"(?:由|从|原|不再|取代|区别于|不同于|相比|而非|不是|改变)[^，,；;。]{0,6}$", clause[:match.start()]) \
                        and not re.search(r"^[^，,；;。]{0,4}(?:变为|转为|改为|减为|简化为)", clause[match.end():]) \
                        and not re.search(r"两级|两层|二级", clause):
                    found.append(v)
                    break
        return found

    # P13 2型 group level
    hotel_life = [view for view in two_views if adopted_match(view.text, r"酒店生活")]
    pension_park = [view for view in two_views if adopted_match(view.text, r"养老园区")]
    two_both = hotel_life + pension_park if hotel_life and pension_park else []
    def block_of(view: View) -> str:
        return view.span.path.split("/sentence")[0].split("/line")[0]
    segment_blocks = {block_of(view) for view in two_views if re.search(r"板块|酒店生活|养老园区", view.text)}
    two_listed = [view for view in two_views if adopted_match(view.text, r"上市(?:公司|平台)") and block_of(view) in segment_blocks]
    park_bu = hits(two_views, r"园区[^，,；;。\s|]{0,6}\s?(?:BU|事业部|业务单元)")
    pension_bu = hits(two_views, r"养老(?!园区)[^，,；;。\s|]{0,4}\s?(?:BU|事业部|业务单元)")
    both_lines = hits(two_views, r"养老[^，,；;。]{0,6}(?:与|和|、)园区[^，,；;。]{0,12}业务线[^，,；;。]{0,4}设为[^，,；;。]{0,4}单元")
    both_lines += hits(two_views, r"养老[、和与]园区[^，,；;。]{0,4}两个[^，,；;。]{0,4}(?:业务单元|单元|BU)")
    park_bu, pension_bu = park_bu + both_lines, pension_bu + both_lines
    two_levels = level_row(two_views, "两|二|2") + hits(two_views, r"管控层级[:：为是]\s*(?:两|二|2)\s*(?:级|层)|2\s*级管控|两级管控|两层管控|二级管控|两级管理模式|(?:变为|简化为|调整为|减为|减少为|压缩为|改为)(?:两|二)(?:级|层)|(?:两|二|2)\s*个\s*(?:控制|管控)层(?:级|次)?|管控层(?:级)?\s*(?:两|二|2)\s*级")
    segment_scoped = r"(?:板块|平台|一线)[^，,；;。]{0,4}(?:为|是|实行|采用)?\s*(?:两|二|2)\s*(?:级|层)"
    line_scoped = r"(?:板块|平台|线)[^；;。]{0,40}(?:两|二|2)\s*个?\s*(?:级|层|控制层|管控层)"
    if three_level_views(two_views) and all(re.search(segment_scoped, view.text) or re.search(line_scoped, view.text)
                                            for view in two_levels):
        two_levels = []
    emit_positive("P13", [
        (0.1, bool(two_both), two_both),
        (0.1, bool(two_listed), two_listed),
        (0.2, bool(park_bu), park_bu),
        (0.2, bool(pension_bu), pension_bu),
        (0.4, bool(two_levels), two_levels),
    ], f"2型 segments={len(two_both)} listed={len(two_listed)} park={len(park_bu)} pension={len(pension_bu)} levels={len(two_levels)}", two_views)

    # P14 distinguishes formal issuance, preparation/decomposition and process
    # correction. The specific material overrides the general management-chain
    # default for diversified businesses.
    emit_positive("P14", [], "source-bound target and budget responsibility chain", all_views)

    # ------------------------------------------------------------------ deductions
    def emit_deduction(item_id: str, occurrences: list[tuple[str, str, list[View], str]], note: str) -> None:
        if not occurrences:
            judge.deduction(item_id, "not_triggered", [doc_obs], note)
            return
        spec = judge.deductions[item_id]
        observation_ids, rendered = [], []
        for key, root, used, reason in occurrences:
            obs = ledger.observe(item_id, "identified", used, spec["object_key"], "adopted_error")
            observation_ids.append(obs)
            rendered.append({"damage_instance_key": key, "causal_root_id": root,
                             "manifestation_id": f"{item_id}:{key}:{obs}", "observation_id": obs, "reason": reason})
        judge.deduction(item_id, "triggered", observation_ids, note, rendered)

    # D01 decision authority misallocation
    occ = []
    if "集团" in slot("hotel_comp", "final") and not ambiguous("hotel_comp"):
        occ.append(("authority:hotel_industry", "hotel_industry", views_for(("hotel_comp", "final", "集团")),
                    "group approves hotel competitive strategy"))
    if slot("hotel_dev", "final") and "集团" not in slot("hotel_dev", "final") and not ambiguous("hotel_dev"):
        wrong = sorted(slot("hotel_dev", "final"))
        occ.append(("authority:hotel_industry", "hotel_industry", views_for(*[("hotel_dev", "final", b) for b in wrong]),
                    "hotel development strategy approved below group"))
    for item in ("div_dev", "div_invfin", "div_portfolio"):
        finals = slot(item, "final")
        if ambiguous(item):
            continue
        if "集团" in finals:
            occ.append(("authority:diversified", "diversified", views_for((item, "final", "集团")), f"group approves {item}"))
        elif "投资BU" in finals and "股份" not in finals:
            occ.append(("authority:diversified", "diversified", views_for((item, "final", "投资BU")), f"investment BU approves {item}"))
    for item in ("pension_dev", "pension_comp"):
        wrong = (slot(item, "draft") | slot(item, "final")) & {"股份", "酒店BU", "投资BU"}
        if wrong and not ambiguous(item):
            occ.append(("authority:pension", "pension",
                        views_for(*[(item, r, b) for r in ("draft", "final") for b in wrong]), f"{item} placed under {sorted(wrong)}"))
    emit_deduction("D01", occ, "decision authority allocation check")

    # D02 is a subject-relation-object decision. The source-bound judge keeps
    # parallel listed-company-direct objects outside the Investment BU scope.
    d02_fraction, d02_views = semantic_views("D02_SCOPE_ERROR")
    occ = [] if not d02_fraction else [(
        "investment_bu_scope:misassigned", "investment_bu_scope", d02_views,
        semantic["items"]["D02_SCOPE_ERROR"]["reason"],
    )]
    emit_deduction("D02", occ, "investment BU scope check")

    # D03 likewise distinguishes aggregate platform targets from a true bypass.
    d03_fraction, d03_views = semantic_views("D03_GROUP_BYPASS_ERROR")
    occ = [] if not d03_fraction else [(
        "target:group->units", "target_routing", d03_views,
        semantic["items"]["D03_GROUP_BYPASS_ERROR"]["reason"],
    )]
    emit_deduction("D03", occ, "target routing check")

    transition = r"由|从|原|不再|改变|取代|区别于|不同于|相比|较|与近期|而非|不是|变为|转为|不能|不得|不应|不宜"

    def affirmed(pool: list[View], pattern: str, conflict: str) -> list[View]:
        found = []
        for view in pool:
            # D05: a sentence about one branch (支路/分支/支线) or contrasting the other variant is not the variant's count
            sentences = [part for part in re.split(r"[;；。]", view.text)
                         if not re.search(r"支路|分支|支线", part) and not re.search(ARCH_TWO, part)]
            for clause in re.split(r"[,，]", "；".join(sentences)):
                if re.search(pattern, clause) and not re.search(conflict, clause) and not re.search(transition, clause):
                    found.append(view)
                    break
        return found

    # D04 2型 keeps three levels or an entity hotel BU
    occ = [("arch2:control_levels", "arch2_model", [v], "2型 stated with a control-level count other than two")
           for v in three_level_views(two_views)]
    # D04 (M02): 2型 organised as four or more layers with a business-unit layer between segment and operating entities
    layered = r"(?:四|4|五|5)\s*(?:层|级)(?:组织)?(?:结构|架构)"
    occ += [("arch2:control_levels", "arch2_model", [v], "2型 stated as a four-layer structure with a business-unit layer")
            for v in two_views if adopted_match(v.text, layered) and re.search(r"业务单元|BU|事业部", v.text)
            and not re.search(r"(?:由|从|原|不再|而非|不是)[^，,；;。]{0,8}(?:四|4|五|5)\s*(?:层|级)", v.text)
            and not any(v is o[2][0] for o in occ)]
    occ += [("arch2:control_levels", "arch2_model", [v], "2型 level row states more than two control levels")
            for v in level_row(two_views, "三|3|四|4|五|5")]

    def hotel_entity(v: View) -> bool:
        if re.search(r"酒店\s*BU\s*[:：]\s*(?:为|是)?\s*实体|酒店\s*BU[^，,；;。]{0,10}(?:仍为|保持|保留|继续作为|设为|为)[^，,；;。]{0,4}实体|酒店\s*BU[^，,；;。]{0,10}(?:保留|继续设|设置|设有)[^，,；;。]{0,6}部门", v.text) \
                and not re.search(r"不再|不设|取消|撤销|虚拟", v.text) \
                and not re.search(r"酒店\s*BU[^，,；;。]{0,12}不[^，,；;。]{0,10}(?:保留|设|设置)[^，,；;。]{0,6}部门", v.text):
            # D04: 酒店BU不因规模大而保留部门 / 酒店BU的规模不构成保留部门的理由 deny the entity form
            return True
        if re.search(r"酒店\s*BU\s*[（(][^）)]{0,8}实体", v.text) and not re.search(r"酒店\s*BU\s*[（(][^）)]{0,8}虚拟", v.text):
            return True
        cells = v.span.row_cells
        return (v.span.kind == "table_cell_line" and v.text.startswith("实体")
                and any(re.fullmatch(r"(?:L\d\s*)?酒店\s*BU", cell) for cell in cells))
    occ += [("arch2:hotel_bu_entity", "arch2_model", [v], "2型 keeps hotel BU as entity") for v in two_views if hotel_entity(v)]
    emit_deduction("D04", occ, "2型 architecture check")

    # D05 N+1 written as two levels or all-virtual BUs
    occ = [("archN1:control_levels", "archN1_model", [v], "N+1 level row states two control levels")
           for v in level_row(n1_views, "两|二|2")]
    same_as_near_term = r"与近期(?:架构)?(?:一致|相同)|之间[^；;。]{0,20}之间"
    occ += [("archN1:control_levels", "archN1_model", [v], "N+1 stated as two-level control")
           for v in affirmed(n1_views, r"管控层级[:：为是]\s*(?:两|二|2)\s*(?:级|层)|2\s*级管控|两级管控|两层管控|二级管控", r"三级|三层")
           if not re.search(same_as_near_term, v.text)]
    all_virtual = (r"(?:所有|全部)[^，,；;。]{0,4}(?:BU|业务单元)[^，,；;。]{0,6}虚拟|"
                   r"(?:BU|业务单元)[^，,；;。]{0,8}(?:全部|均为|均是)[^，,；;。]{0,4}虚拟")
    occ += [("archN1:all_virtual", "archN1_model", [v], "N+1 makes all BUs virtual")
            for v in affirmed(n1_views, all_virtual, r"实体")]
    emit_deduction("D05", occ, "N+1 architecture check")

    # D06 settled positioning types rewritten
    occ = []
    for view in all_views:
        if not view.adopted or view.arch is not None:
            continue
        for clause in re.split(r"[,，;；。]", view.text):
            if "养老" in clause:
                continue
            types = re.findall(TYPE_WORDS, clause)
            if not types:
                continue
            names = [b[2] for b in find_bodies(clause)[0]]
            if not names and view.span.kind == "table_cell_line" and re.search(r"管控模式|定位|总部类型", view.span.row_header):
                names = [view.context_body] if view.context_body else []
            if len(set(names)) != 1:
                continue
            name = names[0]
            if name in WRONG_TYPES and re.search(WRONG_TYPES[name], clause) and not re.search(NEG + r"|区别于|不同于", clause):
                occ.append((f"positioning:{name}", "positioning", [view], f"{name} typed as {types}"))
    emit_deduction("D06", occ, "positioning type check")

    # D07 near-term investment BU written as entity BU or headquarters
    occ = []
    for view in all_views:
        if not view.adopted or view.arch is not None:
            continue
        for clause in re.split(r"[,，;；。]", view.text):
            if re.search(r"投资\s*BU[^，,；;。]{0,10}(?:实体BU|实体化|(?:设|下设|设立|设置|设有)[^，,；;。]{0,4}(?:职能)?部门|(?:下设|设立|设置|设有)[^，,；;。]{0,16}(?:职能)?部门|下设[一-鿿]{2,8}部|独立总部|型总部)", clause) \
                    and not re.search(NEG + r"|虚拟|借力", clause):
                occ.append(("investment_bu:entity", "investment_bu_form", [view], "investment BU given departments or headquarters status"))
                break
    emit_deduction("D07", occ, "investment BU form check")

    # D08 BU given final approval over investments or asset changes
    occ = [(f"investment_approval:{body}", "investment_approval", [view], f"{body} approves investments")
           for body, view in bu_approvals]
    emit_deduction("D08", occ, "investment approval authority check")

    # Shape counts are exposed only as diagnostics for audits. They do not
    # create a deduction or affect the lenient lens.
    text = raw["text"]
    measures = {
        "S01": _chars(text),
        "S04": section_chars(text, ARCH_N1_HEADING, ARCH_TWO_HEADING),
        "S05": section_chars(text, ARCH_TWO_HEADING, ARCH_N1_HEADING),
    }
    judge.shape_diagnostics = measures

    # D10 uses source-bound fact tuples rather than document-wide number lookup:
    # subject, metric, value, unit and scope/time must belong together.
    d10_fraction, d10_views = semantic_views("D10_UNSUPPORTED_FACT_ERROR")
    occ = [] if not d10_fraction else [(
        "fabricated:unsupported_fact", "fabricated_fact", d10_views,
        semantic["items"]["D10_UNSUPPORTED_FACT_ERROR"]["reason"],
    )]
    emit_deduction("D10", occ, "source-bound unsupported fact check")

    # D11 required-unit gate (R26): each unit the brief requires that is absent is one instance (x coefficient,
    # compounding). The variant units also count when the variant item earns credit, so a section headed
    # 远期A/远期B that states the variant's content is not absent.
    allocated_items = {triple.item for triple in triples}
    units_present = {
        "variant_n1": bool(re.search(ARCH_N1_HEADING, text)) or positive_fraction_now("P12") > 0,
        "variant_two": bool(re.search(ARCH_TWO_HEADING, text)) or positive_fraction_now("P13") > 0,
        "hq_departments": len({name for name in HQ_DEPARTMENTS if name in text}) >= HQ_DEPARTMENTS_MIN,
        "target_issuing": positive_fraction_now("P14") > 0,
        "decision_allocation": len(allocated_items) >= DECISION_ITEMS_MIN,
    }
    emit_deduction("D11", [(f"required_unit:{unit}", "required_unit", [], f"required unit {unit} absent")
                           for unit, present in units_present.items() if not present],
                   "required units " + json.dumps(units_present))

    # D12 extra deliverable files (R27): each regular, non-hidden file beside the deliverable is one instance
    artifact = Path(raw["artifact"])
    delivered_in_output = artifact.parent.name in DELIVERY_DIRS
    # Fix batch 3 (C-VER-005): the harness's own collection manifest (manifest.json) and byte-code caches are
    # not files the agent hands back; they are allow-listed exactly. Hidden files were already exempt.
    extras = sorted(entry.name for entry in artifact.parent.iterdir()
                    if delivered_in_output and entry.is_file() and entry != artifact and not entry.name.startswith(".")
                    and entry.name not in HARNESS_ALLOWLIST and entry.suffix not in (".pyc", ".pyo")) \
        if artifact.parent.is_dir() else []
    emit_deduction("D12", [(f"extra_file:{name}", "extra_file", [], f"second file {name} beside the deliverable")
                           for name in extras], "files beside the deliverable " + json.dumps(extras, ensure_ascii=False))

    # D13 non-Chinese section (R28): a section whose own body lines are mostly Latin letters is one instance
    latin_sections: dict[str, list[View]] = {}
    for view in all_views:
        latin = len(re.findall(r"[A-Za-z]", view.span.text))
        cjk = len(re.findall(r"[一-鿿]", view.span.text))
        if latin >= LATIN_SPAN_MIN and latin > cjk:
            latin_sections.setdefault(" > ".join(view.span.headings) or "document", []).append(view)
    emit_deduction("D13", [(f"language:{section}", "language", used[:1], f"section {section} written in a language other than Chinese")
                           for section, used in latin_sections.items()], f"non-Chinese sections {len(latin_sections)}")


def clause_masked_items(clause: str) -> str:
    """Mask decision-item names so words inside them are not read as investment roles or bodies."""
    return find_items(clause, None)[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--contract", type=Path, default=CANONICAL_CONTRACT)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    contract_path = args.contract.resolve()
    judge = ProgramJudge(load_contract(contract_path), args.artifact.resolve(), sha256(contract_path))
    evaluate_document(extract_raw(args.artifact.resolve()), judge)
    result = judge.finish()
    if hasattr(judge,"semantic_verdict"):
        result["semantic_judge"]=judge.semantic_verdict
    if hasattr(judge, "shape_diagnostics"):
        result["shape_diagnostics"] = judge.shape_diagnostics
    core = (
        all(float(judge._positive_results.get(i, {}).get("fraction", 0)) >= .999 for i in ("P04", "P07"))
        and all(float(judge._positive_results.get(i, {}).get("fraction", 0)) >= .75
                for i in ("P11", "P12", "P13", "P14"))
    )
    result["rewards"]["lenient"] *= float(core)
    result["lenient_core_responsibilities_complete"] = core
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
