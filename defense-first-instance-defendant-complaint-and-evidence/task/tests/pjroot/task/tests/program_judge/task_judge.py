#!/usr/bin/env python3
"""Program Judge adapter for the defendant's statement of defense (3D video production purchase contract).

Three explicit layers:
  extract_raw()  carrier text only (Markdown lines, or DOCX body paragraphs and table rows)
  normalize()    registered rules N01-N07 turn lines into canonical observations and
                 segment the document into title, party block, argument body and closing (R03)
  evaluate()     one positive() call per P and one deduction() call per D, using the
                 registered derivation rules R01-R17 for exclusions, predicates and shape.

Substantive criteria use source-bound semantic judgement; deterministic checks handle carrier, identifiers and explicit errors.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path

from program_judge_runtime import Locator, ProgramJudge, load_contract, sha256


PACKAGE_ROOT = Path(__file__).resolve().parents[3]
CANONICAL_CONTRACT = PACKAGE_ROOT / "rubric-contract.json"

# Frozen task constants (relation-matrix.md section 4 lists where each is visible).
CLAIM_PRINCIPAL = "1482040"
WRONG_PRINCIPALS = {"2814000", "1848182.76", "366142.76", "919240", "562800"}
CN_DIGITS = {"零": 0, "〇": 0, "一": 1, "壹": 1, "二": 2, "贰": 2, "两": 2,
             "三": 3, "叁": 3, "四": 4, "肆": 4, "五": 5, "伍": 5, "六": 6,
             "陆": 6, "七": 7, "柒": 7, "八": 8, "捌": 8, "九": 9, "玖": 9}

def chinese_amount(value: str) -> int | None:
    """Parse integer legal Chinese numerals used in claim amounts."""
    if not value or not any(ch in CN_DIGITS for ch in value):
        return None
    total = section = number = 0
    units = {"十": 10, "拾": 10, "百": 100, "佰": 100, "千": 1000, "仟": 1000,
             "万": 10000, "亿": 100000000}
    for ch in value:
        if ch in CN_DIGITS:
            number = CN_DIGITS[ch]
        elif ch in units:
            unit = units[ch]
            if unit < 10000:
                section += (number or 1) * unit
            else:
                total += (section + number) * unit
                section = number = 0
        elif ch not in "元圆整人民币":
            return None
    return total + section + number
DELIVERY_CLAUSES = {"7.1"}
PENALTY_CLAUSES = {"9.4"}

GAP_MARKERS = [
    "[待补充]", "【待补充】", "[待填写]", "【待填写】", "[待核实]", "【待核实】", "[待确认]", "【待确认】",
    "[placeholder]", "材料未提供", "未提供", "待补充", "待填写", "待核实", "unspecified", "TBD",
]
GAP_TOKEN = "⟦GAP⟧"

# N06 entity alias classes
# N06: 答辩人 must not match inside 被答辩人, which is the plaintiff. The two alias classes are
# meant to be disjoint, and a filing may address the plaintiff as 被答辩人 throughout.
ANSWERER = r"(?<!被)答辩人"
DEF = r"(?:被告|" + ANSWERER + r"|B公司|甲方|采购方|我方|我司|本公司)"
PLA = r"(?:原告|被答辩人|A公司|乙方|供应方|对方)"
OWNER = r"(?:C公司|建设单位|业主单位|业主方|业主)"
SELF = r"(?:被告|" + ANSWERER + r"|B公司|我方|我司|本公司)"

TITLE_RE = re.compile(r"^(民事)?答辩(状|书)(\(.{0,10}\))?$")
# R03 party labels: the class carries 联系电话/电话 but not 联系方式, and the
# contiguous-run scan therefore stopped inside a party block at "联系方式：电话4、电话6、电话1",
# leaving the opposing party's whole particulars in the argument body. Close the contact family.
PARTY_RE = re.compile(
    r"^(答辩人|被答辩人|原告|被告|法定代表人|负责人|住所地?|地址|住址|统一社会信用代码|组织机构代码|信用代码|"
    r"联系电话|联系方式|联系人|电话|传真|电子?邮箱|邮件地址|委托(诉讼)?代理人|诉讼代理人|代理人|职务|邮编|"
    r"通讯地址|送达地址)(\([^)]{0,12}\))?[:,]")
CASE_CAPTION_RE = re.compile(
    r"^(案号|案由|案件编号|案件案号|受理案号|审理程序|审理法院|受理法院|承办法院|致)"
    r"([(（][^)）]{0,12}[)）])?[:,]")
PARTY_TABLE_HEADER = re.compile(r"^(当事人|项目|身份|类别|角色|诉讼地位)(信息)?:(基本信息|信息|内容|名称|详情|情况)$")
CLOSING_RE = re.compile(r"^此致")
APPENDIX_RE = re.compile(r"^(附件|附:|附录|证据目录|证据清单|附证据)")
# R03: an appendix head is a LABEL line, not an argument sentence that happens
# to open with one of the label nouns. 证据目录/证据清单/附录 are ordinary noun phrases in this task
# ("证据目录就证据3记载的证明对象为…"), and matching one at the head of a 59-character prose sentence
# ended the argument body 83 lines early and moved 45% of one filing into the closing region, where
# no positive item can see it. R03 already caps a heading at 80 characters; every appendix head in
# this family is at most 14, so a label line is capped well below the heading cap.
APPENDIX_HEAD_MAX = 30


def appendix_head(clean: str) -> bool:
    """R03: this line is an appendix heading rather than a sentence that starts with the label."""
    return bool(APPENDIX_RE.match(clean)) and len(clean) <= APPENDIX_HEAD_MAX

NEG = r"(?:不|未|没有|并非|无需|无须|否认|免除|无权|不再|并不|从未|尚未|并未)"
DNEG = r"(?:并非|不是|不能认为|否认|不能说|不应认为|难以认为)"
CANDIDATE = re.compile(
    r"可能|或许|也许|大概|待定|待确认|候选|备选|是否|二选一|择一|抑或|"
    r"(或者|或|/)(¥|§|[A-F]公司|第|已|未)|(已|未)[^。;]{0,6}或(已|未)")
ATTRIB = re.compile(
    r"(原告|被答辩人|对方|A公司|有观点|有人|有意见|或有观点|另一种观点|反对观点)[^。;,]{0,8}?"
    r"(认为|声称|诉称|辩称|指出|主张|称)")
ATTRIB_THIRD = re.compile(r"(有观点|有人|有意见|或有观点|另一种观点|反对观点|原告|被答辩人|对方)[^。;,]{0,6}?(认为|声称|指出|辩称|诉称|称)")
REJECT_TAIL = re.compile(
    r"(说法|观点|意见|抗辩|理由|主张|看法|结论)[^。;]{0,8}?"
    r"(不能成立|不成立|站不住脚|不予认可|不予采纳|不予采信|系错误|是错误的|有误|不应采纳|缺乏(事实|法律)?(和|与|及)?(事实|法律)?依据|不应(得到|予以)?支持)")
SELF_ASSERT = re.compile(r"(?:答辩人|被告|我方|我司|本公司|B公司)(?:认为|请求|恳请|申请|提出|主张|据此|对此)")
QUANTITY_BOUND = re.compile(r"不(?:得)?(?:超过|低于|少于|高于|多于)")
# R02 noun-modifier exemption: "原告主张的X" is a noun phrase naming the
# opponent's claim object, not an attribution of the sentence's proposition. Its object class has to
# be the same claim-object vocabulary the judge declares elsewhere, or an alias recognised in one
# place is refused in another: PENALTY already reads 违约责任/逾期付款责任/逾期付款损失/逾期利息 as
# claim 2's object and PRINCIPAL_NOUN reads 服务费/制作费/视频款/合同费用 as claim 1's, so this
# list carries them too, and "如原告主张的累计违约责任明显超过…，答辩人依据《民法典》
# 第五百八十五条请求法院…予以调减" stays the defendant's own request.
CLAIM_OBJECT_NOUN = (r"(?:违约金|违约责任|逾期付款责任|逾期付款损失|逾期利息|迟延付款|"
                     r"合同款|合同价款|价款|货款|款项|服务费|制作费|视频款|合同费用|"
                     r"金额|数额|基数|诉讼请求|诉请|请求权?|利息|损失|计算标准|计算方式|起算日|起算点|"
                     # R02 object class: the relative-clause objects a filing
                     # writes after 原告主张的 / 被答辩人主张的 - a canonicalised amount or date token
                     # (N02/N03 fold them before R02 reads the sentence), the obligation itself, and
                     # the due date. The contract states the class open-endedly ("违约金/合同款/
                     # 诉讼请求…"); an object recognised as claim 1's or claim 2's everywhere else in
                     # the judge must not turn the rest of the sentence into the opponent's speech.
                     r"付款义务|给付义务|债务|债权|欠款|到期日期?|到期时间|秒数|工作量|"
                     r"¥[\d.]+|@\d{4}-\d{2}-\d{2})")
MODIFIED_CLAIM_OBJECT = re.compile(r"的[^。;,]{0,6}?" + CLAIM_OBJECT_NOUN)
# R12: subsidiary-request markers. 备位/预备 request and "如(人民)法院(经审理)认定" are the same
# alternative framing as 即便/如贵院; Golden's own alternative at p[11] is 即便法院认定.
ALTERNATIVE = re.compile(r"即便|即使|退一步|退一万步|纵然|就算|假设|假如|如果|倘若|若|"
                         r"如[^。;,]{0,6}?法院|如贵院|备位|预备性?(?:抗辩|请求)")
EMPHASIS_LINE = re.compile(r"^(?:[-*+]\s+|\d+[.)]\s*)?(?:\*\*[^*]+\*\*|__[^_]+__)[\s。.:：]*$")

# R19 author-originated interest-rate figure: the rate object class and the numeric rate token.
# The record binds no numeric value to any interest-rate object (materials token counts: 3.45 = 0,
# 3.65 = 0, 7.1 = 0; the only percentages are the 6%/13% tax rates and the LED contract's 30/40/27/3%
# payment shares), so a figure bound to a rate object is author-originated unless it is one of the
# SUPPORTED_RATE_FIGURES below.
RATE_OBJECT = (r"(?:LPR|贷款市场报价利率|市场报价利率|贷款利率|拆借利率|年化(?:利率|收益率)?|年利率|年率|月利率|日利率|"
               r"折合年(?:利率|息|化)?|资金(?:占用)?(?:利率|成本率)|利率|利息率)")
RATE_PCT = r"(?<![\d.])\d{1,3}(?:\.\d{1,3})?%"
RATE_FIGURE = re.compile(RATE_OBJECT + r"[^,:]{0,12}?(" + RATE_PCT + r")|(" + RATE_PCT + r")[^,:]{0,12}?" + RATE_OBJECT)
RATE_NON_INTEREST = re.compile(r"增值税|税率|退税|签约率|股权|持股")
# R19 supported figures: the record does carry one rate figure, written in Chinese words rather
# than as a percentage - 起诉材料 诉讼请求2 "按照日万分之一的标准", 合同 9.1 "每日按逾期交货部分
# 价款的万分之一", 合同 9.4 "以应付未付金额的万分之一". 万分之一 per day is 0.01% per day and
# 0.01% x 365 = 3.65% per year, so those two percentages restate a record figure instead of
# inventing one. The exemption is paragraph-scoped on RATE_SOURCE_TERM, so a bare "LPR 为 3.65%"
# in a paragraph that never names 万分之一 is still an author-originated market rate.
SUPPORTED_RATE_FIGURES: frozenset[str] = frozenset({"0.01%", "3.65%"})
RATE_SOURCE_TERM = re.compile(r"万分之一")
# R19 in-clause derivation: a figure printed next to the arithmetic that produces it is checkable
# against the record and is not an invented value (…=3.65%, or 3.0%(11.146%x365/1,356)).
RATE_OPERATOR = r"[x*×÷/+\-]"
RATE_DERIVED_BEFORE = re.compile(r"(?:\d[\d,.]*%?\s*" + RATE_OPERATOR + r"\s*\d[\d,.]*%?\s*)+[=＝]\s*$")
# The bracket may be cut short: clause_windows splits at every , so a thousands separator inside
# the expression ends the clause. Requiring the opening bracket and the first operator is enough.
RATE_DERIVED_AFTER = re.compile(r"^\s*[(（][^)）]{0,20}?\d[\d,.]*%?\s*" + RATE_OPERATOR + r"\s*\d")
# R19: the answer says in the same clause that this figure has no source in the record. That is a
# gap being marked, the opposite of the author-originated assertion D09 charges.
RATE_DISCLAIMED = re.compile(r"(?:无|没有|未见|不具备|缺乏|查无)[^。;,]{0,8}?(?:出处|依据|来源|记载|根据|可核验性)|无从(?:核验|查证|确定)")


def rate_figure_supported(line: dict, clause: str, match: re.Match, figure: str) -> bool:
    """R19: this figure restates a record figure, prints its own arithmetic, or is marked as unsourced."""
    if figure in SUPPORTED_RATE_FIGURES and RATE_SOURCE_TERM.search(line["canon"]):
        return True
    if RATE_DISCLAIMED.search(clause):
        return True
    start = match.start(1) if match.group(1) else match.start(2)
    end = start + len(figure)
    return bool(RATE_DERIVED_BEFORE.search(clause[:start]) or RATE_DERIVED_AFTER.match(clause[end:]))

RATE_ATTRIBUTED = re.compile(PLA + r"[^。;]{0,24}?(?:主张|诉请|诉称|请求|自认|援引|计取|采用|叠加|计算)")
DATE_CN = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")
DATE_NUM = re.compile(r"(?<![\d.@§])(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})日?(?![\d.])")
MONEY = re.compile(r"(?:人民币|RMB)?(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(万元|元)|¥(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(?:元)?")
CLAUSE = re.compile(r"第?(\d{1,2})\.(\d{1,2})(条|款|项)")
ARTICLE = re.compile(r"第([零〇一二两三四五六七八九十百千0-9]+)条")
CN_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CN_UNITS = {"十": 10, "百": 100, "千": 1000}


# ---------------------------------------------------------------------------
# Layer 1: raw carrier extraction
# ---------------------------------------------------------------------------
def extract_raw(artifact: Path) -> dict:
    """Return raw carrier lines with structural locators; never interprets business meaning."""
    raw = {"artifact": artifact, "carrier": None, "records": [], "parse_error": None}
    if not artifact.is_file():
        raw["parse_error"] = "artifact file is missing"
        return raw
    if artifact.suffix.lower() == ".docx":
        raw["carrier"] = "docx"
        try:
            import docx
            from docx.table import Table
            from docx.text.paragraph import Paragraph

            document = docx.Document(str(artifact))
            p_index = t_index = 0
            for child in document.element.body.iterchildren():
                tag = child.tag.rsplit("}", 1)[-1]
                if tag == "p":
                    raw["records"].append({"locator": f"docx:body/p[{p_index}]", "text": Paragraph(child, document).text})
                    p_index += 1
                elif tag == "tbl":
                    for r, row in enumerate(Table(child, document).rows):
                        cells = [cell.text for cell in row.cells]
                        raw["records"].append({"locator": f"docx:body/tbl[{t_index}]/tr[{r}]", "text": "|" + "|".join(cells) + "|"})
                    t_index += 1
        except Exception as exc:  # carrier failure is isolated as parse_failure
            raw["parse_error"] = f"docx parse failure: {type(exc).__name__}"
            raw["records"] = []
        return raw
    raw["carrier"] = "markdown"
    try:
        text = artifact.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        raw["parse_error"] = "artifact is not valid UTF-8"
        return raw
    in_fence = False
    for number, line in enumerate(text.lstrip("﻿").splitlines(), start=1):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            raw["records"].append({"locator": f"md:line[{number}]", "text": line})
    return raw


# ---------------------------------------------------------------------------
# Layer 2: registered normalization rules
# ---------------------------------------------------------------------------
def cn_number(token: str) -> int | None:
    if token.isdigit():
        return int(token)
    total, current = 0, 0
    for char in token:
        if char in CN_DIGITS:
            current = CN_DIGITS[char]
        elif char in CN_UNITS:
            total += (current or 1) * CN_UNITS[char]
            current = 0
        else:
            return None
    return total + current


def money_token(integer: str, fraction: str | None, unit: str | None) -> str:
    try:
        value = Decimal(integer.replace(",", "") + (fraction or ""))
    except InvalidOperation:
        return integer
    if unit == "万元":
        value *= 10000
    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "¥" + text


def n01_clean(text: str) -> str:
    """N01: NFKC fold, drop Markdown decoration and table pipes, remove whitespace."""
    text = unicodedata.normalize("NFKC", text)
    for invisible in ("​", "‌", "‍", "﻿", "­"):
        text = text.replace(invisible, "")
    stripped = text.strip()
    if stripped.startswith("|"):
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", cell or "--") for cell in cells):
            return ""
        text = ":".join(cell for cell in cells if cell)
    text = re.sub(r"^\s*#{1,6}\s*", "", text)
    text = re.sub(r"^\s*>\s*", "", text)
    text = re.sub(r"^\s*[-*+]\s+", "", text)
    # N01: `__` is Markdown emphasis only when it is not part of a longer underscore run; a run of
    # three or more underscores is a declared N05 gap marker (`_{3,}`) and must survive to n05_gap.
    text = text.replace("**", "")
    text = re.sub(r"(?<!_)__(?!_)", "", text)
    text = text.replace("`", "")
    text = re.sub(r"\s+", "", text)
    return text.replace("【", "[").replace("】", "]")


def n05_gap(text: str) -> str:
    """N05: fold every declared gap marker into one gap token."""
    for marker in sorted(GAP_MARKERS, key=len, reverse=True):
        folded = re.sub(r"\s+", "", unicodedata.normalize("NFKC", marker)).replace("【", "[").replace("】", "]")
        text = text.replace(folded, GAP_TOKEN)
    return re.sub(r"_{3,}|×{2,}|X{3,}|\*{3,}", GAP_TOKEN, text)


def n02_n03_n04(text: str) -> str:
    """N03 dates, N04 contract clause and statute article numbers, N02 money into canonical tokens."""
    text = DATE_CN.sub(lambda m: f"@{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}", text)
    text = DATE_NUM.sub(lambda m: f"@{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}", text)
    text = CLAUSE.sub(lambda m: f"§c{int(m.group(1))}.{int(m.group(2))}", text)

    def money(m: re.Match) -> str:
        if m.group(1) is not None:
            return money_token(m.group(1), m.group(2), m.group(3))
        return money_token(m.group(4), m.group(5), None)

    cn_money = re.compile(r"(?:人民币|RMB)?([零〇一二两三四五六七八九十百千万亿壹贰叁肆伍陆柒捌玖拾佰仟萬億]+)(万元|元)")

    def cn_amount(m: re.Match) -> str:
        digits = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
                  "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
                  "壹": 1, "贰": 2, "叁": 3, "肆": 4, "伍": 5, "陆": 6, "柒": 7, "捌": 8, "玖": 9}
        small = {"十": 10, "百": 100, "千": 1000, "拾": 10, "佰": 100, "仟": 1000}
        large = {"万": 10_000, "萬": 10_000, "亿": 100_000_000, "億": 100_000_000}
        total = section = number = 0
        for char in m.group(1):
            if char in digits:
                number = digits[char]
            elif char in small:
                section += (number or 1) * small[char]
                number = 0
            elif char in large:
                section += number
                total += section * large[char]
                section = number = 0
            else:
                return m.group(0)
        value = total + section + number
        if m.group(2) == "万元":
            value *= 10_000
        return f"¥{value}"

    text = cn_money.sub(cn_amount, text)
    text = MONEY.sub(money, text)

    def article(m: re.Match) -> str:
        number = cn_number(m.group(1))
        return f"§{number}" if number is not None else m.group(0)

    return ARTICLE.sub(article, text)


def raw_token_soup(raw_text: str) -> bool:
    """R01: a raw line made of eight or more whitespace/comma separated short tokens is keyword soup.

    Whitespace next to digits or ASCII punctuation is collapsed first so spaced numbers such as
    `2022 年 4 月 27 日` or `1,482,040 元` stay one legitimate phrase.
    """
    text = unicodedata.normalize("NFKC", raw_text).replace("**", "").strip()
    text = re.sub(r"^\s*(#{1,6}|[-*+>]|\d+[.)])\s+", "", text)
    text = re.sub(r"\s*([\d.,:;()%/])\s*", r"\1", text)
    text = re.sub(r"(?<=\d)\s*(年|月|日|元|万元|秒|条|款)\s*", r"\1", text)
    fragments = [frag for frag in re.split(r"[\s、,]+", text) if frag]
    short = [frag for frag in fragments if len(frag) <= 8]
    return len(fragments) >= 8 and len(short) >= 0.7 * len(fragments)


def is_list_spray(text: str) -> bool:
    """R01: six or more short enumerated fragments are a keyword list, not a proposition."""
    fragments = [frag for frag in re.split(r"[、,]", text) if frag]
    short = [frag for frag in fragments if len(frag) <= 8]
    return len(fragments) >= 6 and len(short) >= 0.7 * len(fragments)


def too_dense(text: str) -> bool:
    """R01: one sentence citing more than three distinct contract clauses or amounts is spraying."""
    clauses = set(re.findall(r"§c[\d.]+", text))
    amounts = set(re.findall(r"¥[\d.]+", text))
    return len(clauses) > 3 or len(amounts) > 3


class Doc:
    """Normalized statement of defense: canonical lines segmented into title, party, body and closing."""

    def __init__(self, raw: dict):
        self.raw = raw
        self.artifact = str(raw["artifact"])
        self.lines: list[dict] = []
        for record in raw["records"]:
            clean = n01_clean(record["text"])
            if not clean:
                continue
            canon = n02_n03_n04(n05_gap(clean))
            self.lines.append({"locator": record["locator"], "raw": record["text"], "clean": clean,
                               "canon": canon, "spray": raw_token_soup(record["text"]), "region": None})
        self.state = "identified"
        # R03 region segmentation: title, contiguous party block, body, closing from 此致/appendix
        index = 0
        if self.lines and (TITLE_RE.match(self.lines[0]["clean"]) or (len(self.lines[0]["clean"]) <= 12 and "答辩" in self.lines[0]["clean"])):
            self.lines[0]["region"] = "title"
            index = 1
        # R03: a case caption between the title and the party block - 案号：案号1,
        # 案由：…, 致：某基层法院 - is neither the title nor a party line; stopping on
        # it would leave the filing with no party block and read its party particulars as argument
        # body (out of D02's and D06's party-region scans, and into the S01 body measure). Step over at most two such caption lines, never past a party label, and only when a
        # party label really follows; the skipped lines belong to no region, exactly as the title does not
        # belong to the body.
        scan = index
        while (scan < len(self.lines) and scan - index < 2
               and not PARTY_RE.match(self.lines[scan]["clean"])
               and not PARTY_TABLE_HEADER.match(self.lines[scan]["clean"])
               and CASE_CAPTION_RE.match(self.lines[scan]["clean"])
               and len(self.lines[scan]["clean"]) <= 40):
            scan += 1
        if scan < len(self.lines) and (PARTY_RE.match(self.lines[scan]["clean"])
                                       or PARTY_TABLE_HEADER.match(self.lines[scan]["clean"])):
            index = scan
        while index < len(self.lines) and (PARTY_RE.match(self.lines[index]["clean"]) or PARTY_TABLE_HEADER.match(self.lines[index]["clean"])):
            self.lines[index]["region"] = "party"
            index += 1
        closing_heads = [i for i in range(index, len(self.lines)) if CLOSING_RE.match(self.lines[i]["clean"])]
        appendix_heads = [i for i in range(index, len(self.lines)) if appendix_head(self.lines[i]["clean"])]
        end = len(self.lines)
        if len(closing_heads) > 1:
            self.state = "ambiguous"
        stops = closing_heads[:1] + appendix_heads[:1]
        if stops:
            end = min(stops)
        else:
            tail = [i for i in range(index, len(self.lines)) if re.match(r"^(答辩人|具状人)(\([^)]*\))?:", self.lines[i]["clean"])]
            if tail:
                end = tail[-1]
        for i in range(index, len(self.lines)):
            self.lines[i]["region"] = "body" if i < end else "closing"
        self.body = [line for line in self.lines if line["region"] == "body"]
        # R03 sections: a Markdown heading line or a 一、/二、 numbered heading of at most 80 characters opens a section
        section = 0
        for line in self.body:
            if re.match(r"^\s*#{1,6}\s", line["raw"]) or (re.match(r"^[一二三四五六七八九十]+[、.]", line["clean"]) and len(line["clean"]) <= 80):
                section += 1
            line["section"] = section
        if self.state == "identified" and not self.body:
            self.state = "confirmed_missing"

    def loc(self, line: dict, object_key: str, field: str, prefix: str) -> Locator:
        return Locator(locator_id=f"{prefix}:{line['locator']}", artifact_path=self.artifact,
                       container_type=self.raw["carrier"] or "unknown", container_path=line["locator"],
                       object_key=object_key, field=field, observed=line["raw"][:400])

    def canon_loc(self, source: Locator, line: dict, rule: str) -> Locator:
        return Locator(locator_id=source.locator_id + ":canon", artifact_path=self.artifact,
                       container_type=source.container_type, container_path=source.container_path,
                       object_key=source.object_key, field=source.field + ".canonical",
                       observed=line["canon"][:400], evidence_origin="lossless_canonicalized",
                       source_locator_ids=(source.locator_id,), normalization_rule_id=rule)

    def body_loc(self, object_key: str, prefix: str) -> Locator:
        return Locator(locator_id=f"{prefix}:region:body", artifact_path=self.artifact,
                       container_type=self.raw["carrier"] or "unknown", container_path="region:body",
                       object_key=object_key, field="region_state", observed=self.state)


def observe_lines(judge: ProgramJudge, doc: Doc, obs_id: str, lines: list[dict], object_key: str,
                  field: str, rule: str) -> str:
    evidence: list[Locator] = []
    seen: set[str] = set()
    for line in lines:
        if line["locator"] in seen:
            continue
        seen.add(line["locator"])
        source = doc.loc(line, object_key, field, obs_id)
        evidence.extend([source, doc.canon_loc(source, line, rule)])
    return judge.observe(obs_id, "identified", evidence)


def normalize(raw_registry: dict, judge: ProgramJudge) -> dict:
    """Register carrier-independent observations; the runtime owns their states."""
    if raw_registry.get("parse_error"):
        locator = Locator("parse:artifact", str(raw_registry["artifact"]), raw_registry.get("carrier") or "unknown",
                          "artifact", "statement_of_defense", "carrier", raw_registry["parse_error"])
        judge.observe("obs.parse_failure", "parse_failure", [locator])
        return {"parse_failure": True}
    doc = Doc(raw_registry)
    if doc.state == "identified":
        observe_lines(judge, doc, "obs.scan.body", doc.body, "region.body", "region_text", "N01")
    else:
        judge.observe("obs.scan.body", doc.state, [doc.body_loc("region.body", "obs.scan.body")])
    if doc.lines:
        observe_lines(judge, doc, "obs.scan.all", doc.lines, "document", "all_text", "N01")
    else:
        judge.observe("obs.scan.all", "confirmed_missing", [doc.body_loc("document", "obs.scan.all")])
    return {"parse_failure": False, "doc": doc}


# ---------------------------------------------------------------------------
# Layer 3: P/D decisions
# ---------------------------------------------------------------------------
# R21: a negated head that introduces an enumeration with ":" governs every ;-item it lists
# ("原告未提交充分证据证明:A;B;C"), so each item inherits the head instead of losing its negation
# at the ; split. Only a head whose own clause carries the negation qualifies.
ENUM_HEAD = re.compile(r"^(?:[^,:]{0,10}?[,])?([^,:]{0,30}?(?:未|没有|不能|无法|未能|尚未|从未)[^,:]{0,24}?"
                       r"(?:证明|举证|提交|提供|说明|完成)[^,:]{0,12}?):")


def sentences(text: str) -> list[str]:
    parts = []
    for period in re.split(r"[。!?]", text):
        head = ""
        for clause in period.split(";"):
            if not clause:
                continue
            parts.append(head + clause if head else clause)
            match = ENUM_HEAD.match(clause)
            if match:
                head = match.group(1) + ":"
    return [part for part in parts if part]


def full_sentence(canon: str, clause: str) -> str:
    """R21: the 。-sentence of `canon` that contains `clause`.

    `sentences()` cuts at ； as well as 。 so that a rejection and its negation stay in one
    clause. The contract's P07 evidence span is "one sentence inside one body paragraph",
    and a ；-clause is not a sentence, so a ground written in an earlier clause of the same
    sentence is still the same sentence's ground. Falls back to the clause itself.
    """
    position = canon.find(clause)
    if position < 0:
        return clause
    start = max((canon.rfind(mark, 0, position) + 1) for mark in "。!?")
    ends = [index for index in (canon.find(mark, position + len(clause)) for mark in "。!?") if index >= 0]
    return canon[start: min(ends) + 1] if ends else canon[start:]


def sentence_scope(line: dict, clause: str, position: int) -> tuple[str, int]:
    """R19+R21: the enclosing 。-sentence of `clause`, and `position` mapped into it."""
    scope = full_sentence(line["canon"], clause)
    offset = scope.find(clause)
    return (scope, offset + position) if offset >= 0 else (clause, position)


def clause_start(text: str, position: int) -> int:
    return max(text.rfind(",", 0, position), text.rfind(":", 0, position)) + 1


def neg_before(text: str, position: int, pattern: str = NEG) -> bool:
    """R02: a negation inside the clause carrying the key verb, before that verb."""
    window = QUANTITY_BOUND.sub("", text[clause_start(text, position):position])
    return re.search(pattern, window) is not None


def excluded(sentence: str, position: int, claim_rejection: bool = False) -> str | None:
    """R02: candidate, attributed, rejected, list-spray and dense spans cannot be adopted."""
    if CANDIDATE.search(sentence):
        return "candidate"
    if is_list_spray(sentence) or too_dense(sentence):
        return "spray"
    attrib = ATTRIB_THIRD if claim_rejection else ATTRIB
    for m in attrib.finditer(sentence):
        if MODIFIED_CLAIM_OBJECT.match(sentence, m.end()):
            continue
        if m.start() < position and not SELF_ASSERT.search(sentence, m.end(), position):
            return "attributed"
    tail = REJECT_TAIL.search(sentence, position)
    if tail and not claim_rejection:
        return "rejected"
    if claim_rejection and tail and re.search(r"说法|观点|意见|看法|结论", tail.group(0)):
        return "rejected"
    return None


# Every deduction item declares the same negative_context_exclusions: "negation before the verb,
# candidate markers, attribution to the plaintiff (原告称/主张), later rejection, alternative framing
# (即便/即使/如法院认定) and ordinary omission never trigger". R02 owns the first four through
# excluded() and neg_before(); the alternative frame is the third arm, and the two functions below
# give every proposition-level D the same gate.
def alternative_framed(sentence: str, end: int) -> bool:
    """R12/R19 alternative frame, read up to the end of the matched error span.

    A frame governs what follows it and may sit inside the span itself (C公司即便已确认二期视频),
    which is why the span is included; a frame in a later clause is not read, because it would
    excuse an error already asserted before it.
    """
    head = sentence[:end]
    return bool(ALTERNATIVE.search(head) or CONCEDE_HYPOTHETICAL.search(head))


def deduction_excluded(sentence: str, start: int, end: int, neg: str | None = NEG) -> bool:
    """The full declared exclusion set for one deduction span.

    D09 keeps the wider sentence scope R19 declares for it, and D10's own contract text opts out of
    the alternative arm ("An alternative frame does NOT exclude"), so both call the parts they need
    directly rather than this gate.
    """
    if excluded(sentence, start):
        return True
    if neg and neg_before(sentence, start, neg):
        return True
    return alternative_framed(sentence, end)


def clause_windows(sentence: str) -> list[tuple[int, int]]:
    """R19: clause windows of one sentence, cut at the same , and : delimiters R02 reads negation in."""
    spans, start = [], 0
    for m in re.finditer(r"[,:]", sentence):
        spans.append((start, m.start()))
        start = m.end()
    spans.append((start, len(sentence)))
    return [(a, b) for a, b in spans if b > a]


def attributed_or_rejected(sentence: str, position: int) -> bool:
    """R19: the sentence-scoped half of R02 - the proposition belongs to the plaintiff or is retracted."""
    for m in ATTRIB.finditer(sentence):
        if MODIFIED_CLAIM_OBJECT.match(sentence, m.end()):
            continue
        if m.start() < position and not SELF_ASSERT.search(sentence, m.end(), position):
            return True
    return REJECT_TAIL.search(sentence, position) is not None


def cited_clauses(text: str) -> set[str]:
    return set(re.findall(r"§c(\d+\.\d+)", text))


def body_paragraphs(doc: Doc) -> list[dict]:
    """Return every substantive body paragraph.

    The brief has no 900-character publication limit.  Long paragraphs still
    participate in both positive and negative checks; otherwise a single long
    paragraph could hide an unsupported fact from all deductions.
    """
    return [line for line in doc.body if not line["spray"]]


def caption_line(line: dict) -> bool:
    """R20: the carrier marks this body line as a section label, not as argument text.

    Markdown heading syntax, the R03 numbered section opener, or a whole line made of a single
    emphasis span; the last two share the 80-character cap R03 already uses for a heading, so a
    fully emphasised argument paragraph stays a paragraph.
    """
    if re.match(r"^\s*#{1,6}\s", line["raw"]):
        return True
    if len(line["clean"]) > 80:
        return False
    if EMPHASIS_LINE.match(line["raw"].strip()):
        return True
    return bool(re.match(r"^[一二三四五六七八九十]+[、.]", line["clean"]))


def caption_depth(line: dict) -> int:
    """R20: the nesting depth of a caption line; a Markdown heading nests, a numbered opener does not."""
    stripped = line["raw"].lstrip()
    hashes = len(stripped) - len(stripped.lstrip("#"))
    if hashes and stripped[hashes: hashes + 1] in (" ", "\t"):
        return min(hashes, 6)
    return 7


def argued_sections(doc: Doc) -> set:
    """R20: R03 sections whose argument body carries at least one ordinary argument paragraph.

    A section's argument body is its own R03 section plus the sections nested under its caption -
    the ones opened by deeper captions before the next caption at the same or a shallower depth.
    R20's own statement of effect is that "a heading above real paragraphs is unaffected"; a `##`
    heading immediately followed by a `###` subheading opens an empty R03 section of its own, so the
    nesting step is what keeps such a heading from being read as a standalone label.
    """
    cached = getattr(doc, "_argued_sections", None)
    if cached is not None:
        return cached
    direct = {line.get("section") for line in doc.body if not line["spray"] and not caption_line(line)}
    captions = [line for line in doc.body if caption_line(line)]
    argued = set(direct)
    for position, line in enumerate(captions):
        if line.get("section") in argued:
            continue
        depth = caption_depth(line)
        for other in captions[position + 1:]:
            if caption_depth(other) <= depth:
                break
            if other.get("section") in direct:
                argued.add(line.get("section"))
                break
    doc._argued_sections = argued
    return argued


def find(doc: Doc, pattern: re.Pattern, neg: str | None = NEG, claim_rejection: bool = False,
         anchor: set[str] | None = None, key: re.Pattern | None = None) -> list[tuple[dict, str, re.Match]]:
    """R04: adopted sentence-level matches of one proposition pattern inside the argument body.

    R20: a caption line only carries a proposition when its R03 section also argues one.
    """
    hits = []
    argued = argued_sections(doc)
    for line in body_paragraphs(doc):
        if caption_line(line) and line.get("section") not in argued:
            continue
        for sentence in sentences(line["canon"]):
            for m in pattern.finditer(sentence):
                position = m.start()
                if key is not None:
                    inner = key.search(m.group(0))
                    position = m.start() + (inner.start() if inner else 0)
                if excluded(sentence, position, claim_rejection):
                    continue
                if neg and neg_before(sentence, position, neg):
                    continue
                if anchor is not None:
                    cited = cited_clauses(sentence)
                    if cited and not (cited & anchor):
                        continue
                hits.append((line, sentence, m))
                break
    return hits


def section_lines(doc: Doc, line: dict, pattern: re.Pattern) -> list[dict]:
    """R03: body lines of the same section as `line` whose canonical text matches `pattern` (line itself first)."""
    same = [other for other in body_paragraphs(doc) if other.get("section") == line.get("section")]
    matched = [other for other in same if pattern.search(other["canon"])]
    return sorted(matched, key=lambda other: other["locator"] != line["locator"])


def unresolved(doc: Doc) -> str | None:
    if doc.state == "identified":
        return None
    return "ambiguous" if doc.state == "ambiguous" else "missing"


def credit(judge, doc, item_id, fraction, comparison, reason, lines, object_key, rule="N01"):
    obs = f"obs.{item_id}"
    if comparison == "missing":
        state = "ambiguous" if doc.state == "ambiguous" else "confirmed_missing"
        judge.observe(obs, state, [doc.body_loc(object_key, obs)])
        judge.positive(item_id, 0.0, obs, reason, "missing" if state == "confirmed_missing" else "different")
        return
    if comparison == "ambiguous":
        evidence = [doc.loc(line, object_key, "candidate_span", obs) for line in {l["locator"]: l for l in lines}.values()]
        judge.observe(obs, "ambiguous", evidence or [doc.body_loc(object_key, obs)])
        judge.positive(item_id, 0.0, obs, reason, "different")
        return
    observe_lines(judge, doc, obs, lines, object_key, "proposition_span", rule)
    judge.positive(item_id, fraction, obs, reason, comparison)


def unique_lines(hits) -> list[dict]:
    return list({h[0]["locator"]: h[0] for h in hits}.values())


# R05 claim-1 rejection bound to the 1,482,040 contract-price claim
PRINCIPAL_NOUN = r"(?:合同款|合同价款|价款|货款|款项|服务费|制作费|视频款|合同费用)"
CLAIM_REJECT = (r"(?:缺乏(?:事实|法律|合同)?(?:和|与|及|、)?(?:事实|法律|合同)?(?:依据|基础)|不应(?:当)?(?:得到|予以|被)?支持|"
                r"不能成立|不成立|应(?:当)?(?:予以|予|依法)?驳回|依法驳回|不予支持|无(?:事实|法律)(?:和|与|及)?(?:事实|法律)?依据|"
                r"没有(?:事实|法律)(?:和|与|及)?(?:事实|法律)?依据)")
P01_FULL = re.compile(r"(?:" + PRINCIPAL_NOUN + r"[^。;]{0,20}?¥" + CLAIM_PRINCIPAL + r"(?![\d.])|¥" + CLAIM_PRINCIPAL + r"(?![\d.])[^。;]{0,6}?" + PRINCIPAL_NOUN +
                      r"|第(?:一|1)项(?:诉讼)?请求|诉讼请求(?:第)?(?:一|1)(?:项)?)[^。;]{0,40}?" + CLAIM_REJECT + r"|"
                      + r"(?:依法)?驳回[^。;,]{0,12}?(?:原告|被答辩人|A公司)?[^。;,]{0,12}?" + PRINCIPAL_NOUN + r"[^。;,]{0,6}?¥" + CLAIM_PRINCIPAL
                      + r"(?![\d.])[^。;,]{0,4}?(?:的)?(?:诉讼)?请求|"
                      # R05: the verb leads and the claim is named by its ordinal, the amount
                      # following in apposition - 驳回原告的第1项诉讼请求（支付合同款¥1482040）.
                      + r"(?:依法)?驳回[^。;,]{0,10}?(?:原告|被答辩人|A公司)?[^。;,]{0,6}?第(?:一|1)项(?:诉讼)?请求|"
                      + DEF + r"[^。;,]{0,6}?(?:不负有|无|没有|不承担)[^。;,]{0,6}?(?:支付|给付)[^。;,]{0,8}?¥" + CLAIM_PRINCIPAL + r"(?![\d.])[^。;,]{0,8}?(?:义务|责任)")
P01_PART = re.compile(r"驳回[^。;]{0,6}?(?:原告|被答辩人|A公司)[^。;]{0,4}?(?:的)?(?:全部|所有|各项|一切)(?:诉讼)?请求")
PARTIAL_CONCESSION = re.compile(DEF + r"[^。;,]{0,6}?(?:同意|认可|愿意|仅应|只应)[^。;,]{0,8}?(?:支付|付款|给付)")


def eval_p01(judge, doc):
    z = unresolved(doc)
    if z:
        return credit(judge, doc, "P01", 0, z, "argument body unresolved", [], "claim1.rejection")
    full = []
    for line, sentence, m in find(doc, P01_FULL, neg=None, claim_rejection=True):
        reject = re.search(CLAIM_REJECT, m.group(0))
        offset = reject.start() if reject else 0
        if neg_before(sentence, m.start() + offset, DNEG) or re.search(r"违约金|利息", m.group(0)[:offset]):
            continue
        if "驳回" in m.group(0)[:4] and (re.search(r"违约金|利息", m.group(0)) or
                                          re.search(r"(?:不应|不予|无需|无须|不得|不能|并非|不是)(?:依法)?$", sentence[:m.start()])):
            continue
        full.append((line, sentence, m))
    concessions = find(doc, PARTIAL_CONCESSION)
    if full and concessions:
        return credit(judge, doc, "P01", 0, "ambiguous", "full rejection mixed with a payment concession", unique_lines(full + concessions), "claim1.rejection")
    if full:
        return credit(judge, doc, "P01", 1.0, "equivalent", "claim 1 (contract price 1,482,040) is rejected in full", unique_lines(full), "claim1.rejection", "N02")
    part = [h for h in find(doc, P01_PART, neg=None, claim_rejection=True) if not neg_before(h[1], h[2].start(), DNEG + r"|不应|不予|无需")]
    if part and not concessions:
        return credit(judge, doc, "P01", 0.5, "partial", "all claims rejected without a claim-1 specific rejection", unique_lines(part), "claim1.rejection")
    return credit(judge, doc, "P01", 0, "missing", "no rejection bound to claim 1", [], "claim1.rejection")


def applied(doc: Doc, *patterns: re.Pattern) -> list[tuple[dict, str, re.Match]]:
    """R18: the contract term is applied to this dispute: an adopted body sentence asserts the case-specific consequence."""
    hits = []
    for pattern in patterns:
        # R08 carrier: P04A's proposition is whatever p04a_hits recognises, in every word order.
        source = p04a_hits(doc) if pattern is P04A_RE else find(doc, pattern, neg=DNEG)
        hits.extend(h for h in source
                    if re.search(r"视频|成果|成片|影片|二期|付款|支付|确认函|发票", h[1]) and "版权" not in h[1])
    return hits


# R07 duty to hand the owner's confirmation letter to the defendant (clause 7.1)
LETTER = r"(?:确认函|确认文件|确认书|确认单)"
P03_RE = re.compile(
    LETTER + r"[^。;,]{0,15}?(?:提交|递交|交付|提供|送交|交)(?:给|予|至)?[^。;,]{0,2}?" + DEF + r"|"
    r"(?:向|给)" + DEF + r"[^。;,]{0,10}?(?:提交|递交|交付|提供|送交)[^。;,]{0,15}?" + LETTER)
DUTY = re.compile(r"应|须|必须|负有|义务|约定|及时|需|§c7\.1")


def eval_p03(judge, doc):
    z = unresolved(doc)
    if z:
        return credit(judge, doc, "P03", 0, z, "argument body unresolved", [], "contract.letter_delivery_duty")
    hits = []
    for line, sentence, m in find(doc, P03_RE, anchor=DELIVERY_CLAUSES):
        start = max(0, clause_start(sentence, m.start()) - 30)
        window = sentence[start: m.end()]
        if re.search(OWNER, window) and DUTY.search(sentence[:m.end()]):
            hits.append((line, sentence, m))
    if hits and not applied(doc, P04A_RE, COND_NOT):
        return credit(judge, doc, "P03", 0, "different", "clause restated but never applied to the undelivered letter", unique_lines(hits), "contract.letter_delivery_duty")
    if hits:
        return credit(judge, doc, "P03", 1.0, "equivalent", "plaintiff must hand the owner's confirmation letter to the defendant (clause 7.1)", unique_lines(hits), "contract.letter_delivery_duty", "N04")
    return credit(judge, doc, "P03", 0, "missing", "letter delivery duty not stated", [], "contract.letter_delivery_duty")


# R08 no owner confirmation letter delivered; phase-2 video not confirmed by C公司
P04A_RE = re.compile(
    r"(?:既未|未能|从未|并未|尚未|均未|亦未|没有|未)[^。;,]{0,12}?(?:向" + DEF + r")?[^。;,]{0,6}?(?:提交|递交|提供|交付|出具|送交)[^。;,]{0,15}?"
    + OWNER + r"[^。;,]{0,8}?(?:书面)?" + LETTER + r"|"
    r"(?:无|没有|未能|不能|无法)[^。;,]{0,8}?证明[^。;,]{0,12}?(?:提交|递交|提供|交付|送交)(?:过)?[^。;,]{0,4}?"
    + OWNER + r"[^。;,]{0,8}?(?:书面)?" + LETTER + r"|"
    + DEF + r"[^。;,]{0,6}?(?:从未|并未|尚未|未|没有)[^。;,]{0,4}?(?:收到|接收到?|取得)[^。;,]{0,15}?" + OWNER + r"[^。;,]{0,8}?" + LETTER)
# R08: both branches read the same "has not proved" head with up to 8 characters between the
# negation and 证明 (无/未能/不能/无法…证明), and (b) binds OWNER to 确认 across a clause-length window
# rather than at Golden's own spacing ("已获得C公司的确认"). The object of the confirmation is a description, not part
# of the proposition: "尚未证明：C公司已对全部158秒最终成片作出符合合同要求的内容及质量确认" and
# "未提交充分证据证明：其取得了C公司对一期、二期最终成片及实际合格量的有效确认" are U08(b). Both
# windows are lazy and stay inside one clause, so the negation still cannot jump a 、or 。.
P04B_RE = re.compile(
    r"(?:无|没有|未能|不能|无法|未|尚未|从未|并未)[^。;,]{0,8}?(?:举证)?证明[^。;]{0,25}?" + OWNER + r"[^。;,]{0,30}?(?:确认|验收)|"
    r"(?:二期|视频|成果|成片|影片)[^。;,]{0,12}?(?:未|没有|并未|尚未|从未|未能)(?:得到|获得|取得|经过|经|通过)[^。;,]{0,6}?" + OWNER + r"[^。;,]{0,8}?(?:书面)?(?:确认|验收)|"
    + OWNER + r"[^。;,]{0,6}?(?:从未|并未|未|没有|尚未)[^。;,]{0,10}?(?:确认|验收)[^。;,]{0,10}?(?:二期|视频|成果|成片|影片)")


# R08 carrier: the same absence written in the 将/把 topicalised order, or with
# the letter named by its contractual description instead of by 建设单位/C公司. Golden writes the
# second form itself at p[8] - "原告未向被告提交符合合同要求的确认函" - so OWNER standing next to
# LETTER is a carrier property, not part of the proposition. The owner requirement is checked at the
# level of the sentence or its paragraph (in eval_p04), not by adjacency.
# R08: the same topicalised order as the 将/把 form above, written without the
# preposition - "未证明建设单位确认函已经提交", "尚未证明：相关确认函已提交答辩人". The letter leads
# and the delivery verb follows, which is a carrier property of the sentence, not the proposition.
P04A_ALT = re.compile(
    r"(?:既未|未能|从未|并未|尚未|均未|亦未|没有|未)[^。;,]{0,8}?(?:举证)?证明[^。;]{0,20}?" + LETTER
    + r"[^。;,]{0,8}?(?:已|业已|曾)?(?:提交|递交|交付|送交)|"
    r"(?:既未|未能|从未|并未|尚未|均未|亦未|没有|未)[^。;]{0,24}?(?:将|把)[^。;,]{0,20}?" + LETTER
    + r"[^。;,]{0,4}?(?:提交|递交|交付|送交)|"
    r"(?:既未|未能|从未|并未|尚未|均未|亦未|没有|未)[^。;,]{0,16}?(?:提交|递交|提供|交付|出具|送交)"
    r"[^。;,]{0,12}?(?:书面)?" + LETTER + r"|"
    + DEF + r"[^。;,]{0,6}?(?:从未|并未|尚未|未|没有)[^。;,]{0,6}?(?:收到|接收到?|取得)[^。;,]{0,12}?" + LETTER)


def p04a_hits(doc: Doc) -> list:
    """R08 (a): the owner's confirmation letter was never handed over, in any of its carriers."""
    hits = find(doc, P04A_RE, neg=DNEG)
    seen = {(h[0]["locator"], h[1]) for h in hits}
    for h in find(doc, P04A_ALT, neg=DNEG):
        if (h[0]["locator"], h[1]) in seen:
            continue
        if re.search(OWNER, h[1]) or re.search(OWNER, h[0]["canon"]):
            hits.append(h)
    return hits


def owner_confirmation_conceded(doc: Doc) -> list[tuple[dict, str]]:
    """R09: affirmative adopted statements that C公司 confirmed phase 2 or that its letter was delivered.

    D07 declares the alternative frame among its exclusions, and the P04 contradiction reads the
    same finding, so an alternative-framed sentence ("即便C公司已经确认二期视频，被告的付款条件亦未
    成就") is neither a concession for D07 nor a contradiction for P04: it is the one lawful way to
    hold an incompatible position, which is what the answering party is told to do.
    """
    patterns = [
        re.compile(OWNER + r"[^。;,]{0,10}?(?:已经|已)[^。;,]{0,6}?(?:书面)?(?:确认|验收)[^。;,]{0,10}?二期"),
        re.compile(r"二期[^。;,]{0,15}?(?:已经|已)(?:获得|得到|取得|经过|经|通过)?[^。;,]{0,6}?" + OWNER + r"[^。;,]{0,4}?(?:书面)?(?:确认|验收)"),
        re.compile(PLA + r"[^。;,]{0,4}?(?:已经|已)(?:向" + DEF + r")?[^。;,]{0,4}?(?:提交|交付|提供|递交)[^。;,]{0,10}?" + OWNER + r"[^。;,]{0,4}?" + LETTER),
    ]
    found = []
    for line in body_paragraphs(doc):
        for sentence in sentences(line["canon"]):
            for pattern in patterns:
                m = pattern.search(sentence)
                if not m or deduction_excluded(sentence, m.start(), m.end()):
                    continue
                if re.search(r"称|主张|认为|诉称|声称", sentence[clause_start(sentence, m.start()):m.start()]):
                    continue
                found.append((line, sentence))
                break
    return found


def eval_p04(judge, doc):
    z = unresolved(doc)
    if z:
        return credit(judge, doc, "P04", 0, z, "argument body unresolved", [], "evidence.owner_confirmation_absent")
    a = p04a_hits(doc)
    b = find(doc, P04B_RE, neg=DNEG)
    contrary = owner_confirmation_conceded(doc)
    lines = unique_lines(a + b)
    if (a or b) and contrary:
        return credit(judge, doc, "P04", 0, "ambiguous", "absence of confirmation asserted and conceded", lines + [c[0] for c in contrary], "evidence.owner_confirmation_absent")
    paragraphs_a = {h[0]["locator"] for h in a}
    both = [h for h in b if h[0]["locator"] in paragraphs_a]
    if both:
        return credit(judge, doc, "P04", 1.0, "equivalent", "no owner confirmation letter delivered and phase-2 video not confirmed by C公司", unique_lines(both), "evidence.owner_confirmation_absent")
    if a or b:
        return credit(judge, doc, "P04", 0.5, "partial", "only one of the two absence findings is stated within one paragraph", lines, "evidence.owner_confirmation_absent")
    return credit(judge, doc, "P04", 0, "missing", "absence of owner confirmation not stated", [], "evidence.owner_confirmation_absent")


# R10 joint phase-1/phase-2 settlement agreed between C公司 and the plaintiff
STAGES12 = r"(?:一期[^。;,]{0,6}?二期|一、二期|一二期|第一、二期|一至二期|两期)"
P05_RE = re.compile(STAGES12 + r"[^。;]{0,20}?(?:统筹结算|一并(?:评估|结算|确认|验收)|统一(?:确认|结算|盖章|验收|评估)|合并(?:结算|确认|验收)|整体(?:结算|确认|验收)|共同(?:统筹)?结算)|"
                    r"(?:统筹结算|一并(?:评估|结算|确认|验收)|统一(?:确认|结算|盖章|验收))[^。;]{0,6}?" + STAGES12)


def eval_p05(judge, doc):
    z = unresolved(doc)
    if z:
        return credit(judge, doc, "P05", 0, z, "argument body unresolved", [], "fact.joint_settlement")
    hits = []
    for h in find(doc, P05_RE):
        if not re.search(OWNER + r"|会议纪要|会谈纪要", h[1]) and not re.search(OWNER + r"|会议纪要|会谈纪要", h[0]["canon"]):
            continue
        if re.search(r"[DEF]公司[^。;,]{0,6}?(?:与|和)" + PLA, h[1]):
            continue
        hits.append(h)
    if hits and not applied(doc, P04A_RE, P04B_RE, COND_NOT, P07_GROUND):
        return credit(judge, doc, "P05", 0, "different", "joint settlement restated but never applied to payment", unique_lines(hits), "fact.joint_settlement")
    if hits:
        return credit(judge, doc, "P05", 1.0, "equivalent", "C公司 and the plaintiff agreed to settle phases 1 and 2 jointly", unique_lines(hits), "fact.joint_settlement")
    return credit(judge, doc, "P05", 0, "missing", "joint settlement agreement not stated", [], "fact.joint_settlement")


# R11 payment condition not satisfied, so no payment obligation yet
COND_NOT = re.compile(
    r"(?:付款|支付)(?:的)?(?:条件|前提)[^。;,]{0,6}?(?:尚未|并未|未|没有|不|均未)(?:成就|满足|具备|成立|达成|出现)|"
    + DEF + r"[^。;,]{0,6}?(?:不具备|不负有|尚不负有|不存在|没有|尚无|并无|不承担|无)[^。;,]{0,6}?(?:付款|支付)(?:的)?(?:义务|责任)|"
    r"(?:付款|支付)(?:义务|期限)[^。;,]{0,4}?(?:尚未|未|并未)(?:产生|届至|到期|届满)")


CONCEDE_HYPOTHETICAL = re.compile(r"如(?:法院|法庭|贵院|人民法院)?(?:经审理)?(?:认定|认为|判定|判令|判决)")
CONCEDE_BURDEN = re.compile(r"(?:须|需|应当?|应该|负责|不能|无法|未能|能否|是否)(?:举证)?(?:证明|证实|举证)")


def liability_conceded(doc: Doc) -> list[tuple[dict, str, str]]:
    """R12: affirmative adopted concession that payment is due (alternative arguments excluded)."""
    patterns = [
        ("condition_satisfied", re.compile(r"(?:付款|支付)(?:的)?(?:条件|前提)[^。;,]{0,4}?(?:已经|已|均已)(?:成就|满足|具备)")),
        ("agrees_to_pay", re.compile(SELF + r"[^。;,]{0,4}?(?:同意|认可|愿意|承认)[^。;,]{0,6}?(?:支付|付款|给付|承担[^。;,]{0,4}?(?:违约|付款))")),
        ("owes_payment", re.compile(SELF + r"[^。;,]{0,4}?(?:应当|应)[^。;,]{0,6}?(?:向(?:原告|A公司|被答辩人))?(?:支付|给付)[^。;,]{0,8}?(?:¥\d|合同款|价款|货款|款项|违约金)")),
        ("in_default", re.compile(SELF + r"[^。;,]{0,6}?(?:已经|已|确实)?构成(?:逾期付款|违约)")),
        ("obligation_exists", re.compile(SELF + r"[^。;,]{0,4}?(?:具备|负有|存在)[^。;,]{0,4}?(?:付款|支付)(?:的)?(?:义务|责任)")),
    ]
    found = []
    for line in body_paragraphs(doc):
        for sentence in sentences(line["canon"]):
            for name, pattern in patterns:
                m = pattern.search(sentence)
                if not m or excluded(sentence, m.start()) or neg_before(sentence, m.start()):
                    continue
                # The filler between the pattern's anchors decides: the condition noun itself (付款条件)
                # is part of the condition_satisfied anchor, so it is cut away before the check.
                filler = re.sub(r"^(?:付款|支付)(?:的)?(?:条件|前提)", "", m.group(0))
                if re.search(r"不|未|没有|无需|无须|无权|确认后|之后|以后|才|方可", filler):
                    continue
                if alternative_framed(sentence, m.end()):
                    continue
                # A proposition the plaintiff has to prove, or one quoted from its pleading, is not adopted.
                if CONCEDE_BURDEN.search(sentence[max(0, m.start() - 60):m.start()]):
                    continue
                if sum(sentence[:m.start()].count(q) for q in "“”\"「」") % 2 == 1:
                    continue
                if re.search(r"(?:从|自|在)$", sentence[:m.start()]) or re.match(r"[^。;,]{0,12}?中(?:扣除|抵扣|扣减)", sentence[m.end():]):
                    continue
                if re.search(r"(?:原告|对方|A公司|被答辩人)[^。;,]{0,10}?(?:要求|请求|主张|诉请|认为|称)", sentence[:m.start()]):
                    continue
                found.append((line, sentence, name))
                break
    return found


# R13 penalty claim fails because payment is not yet due
PENALTY = r"(?:违约金|逾期付款损失|逾期利息|逾期付款责任|迟延付款)"
# R13: the wider rejection vocabulary. 不产生/无从起算/不被触发/不发生迟延
# say the same thing as 不应承担, and 应 + a quantity adverb + 驳回 is the same request as 应驳回.
PENALTY_REJECT = (r"(?:" + CLAIM_REJECT + r"|不应(?:当)?承担|无需承担|无须承担|不承担|不负有|无权(?:主张|要求)|不存在逾期|不构成(?:任何)?逾期|"
                  r"不产生|无从(?:起算|计算|主张)|不被触发|不(?:发生|存在)(?:迟延|逾期)|"
                  r"应(?:当)?(?:予以|予|依法)?(?:全部|全额|一并|均|悉数)(?:予以|依法)?驳回)")
P07_RE = re.compile(PENALTY + r"[^。;]{0,30}?" + PENALTY_REJECT + r"|" + PENALTY_REJECT + r"[^。;]{0,20}?" + PENALTY + r"|"
                    r"不构成(?:任何)?(?:逾期|迟延)付款(?:违约|责任)")
P07_GROUND = re.compile(COND_NOT.pattern + r"|" + OWNER + r"[^。;,]{0,8}?(?:未|没有|并未|尚未|从未)[^。;,]{0,6}?(?:确认|验收)|"
                        r"(?:未|没有|并未|尚未)(?:得到|获得|经过?)[^。;,]{0,6}?" + OWNER + r"[^。;,]{0,6}?确认|不存在逾期(?:付款)?|"
                        # R13: the money itself is not yet due, the same ground COND_NOT
                        # already accepts for 付款义务/付款期限.
                        r"(?:价款|货款|款项|合同款|主债务|主债权)[^。;,]{0,4}?(?:尚未|未|并未)(?:到期|届至|届满|产生)")


def eval_p07(judge, doc):
    z = unresolved(doc)
    if z:
        return credit(judge, doc, "P07", 0, z, "argument body unresolved", [], "claim2.no_default")
    hits = []
    for line, sentence, m in find(doc, P07_RE, neg=None, claim_rejection=True):
        reject = re.search(PENALTY_REJECT, m.group(0))
        if reject and neg_before(sentence, m.start() + reject.start(), DNEG):
            continue
        scope = full_sentence(line["canon"], sentence)
        ground = P07_GROUND.search(scope)
        if ground and not neg_before(scope, ground.start(), DNEG):
            hits.append((line, sentence, m))
    if hits:
        return credit(judge, doc, "P07", 1.0, "equivalent", "penalty claim rejected because payment is not yet due", unique_lines(hits), "claim2.no_default")
    return credit(judge, doc, "P07", 0, "missing", "penalty claim not tied to the unsatisfied payment condition", [], "claim2.no_default")


# R15 clause 9.4 penalty requires non-payment attributable to the defendant; none here
NONATTR = re.compile(r"(?:非|不是|并非|不属于|不系)(?:因|由于)?" + DEF + r"(?:的|方)?(?:原因|过错|责任)|非因" + DEF + r"|"
                     + DEF + r"[^。;,]{0,6}?(?:不存在|没有|无|并无)(?:任何)?(?:主观)?过错|不可归责于" + DEF + r"|不能归责于" + DEF)
COND94 = re.compile(r"(?:因甲方原因|因被告原因|甲方原因|被告原因|可归责于(?:甲方|被告))[^。;]{0,25}?(?:条件|前提|适用)|(?:适用条件|前提|条件)[^。;]{0,25}?(?:因甲方原因|因被告原因)")


def eval_p09(judge, doc):
    z = unresolved(doc)
    if z:
        return credit(judge, doc, "P09", 0, z, "argument body unresolved", [], "contract.penalty_attribution")
    hits = [h for h in find(doc, NONATTR, neg=DNEG, anchor=PENALTY_CLAUSES) if section_lines(doc, h[0], re.compile(r"违约金|违约责任"))]
    if hits:
        return credit(judge, doc, "P09", 1.0, "equivalent", "late payment is not attributable to the defendant, so the clause 9.4 penalty does not apply", unique_lines(hits), "contract.penalty_attribution")
    cond = [h for h in find(doc, COND94, anchor=PENALTY_CLAUSES) if section_lines(doc, h[0], re.compile(r"违约金"))]
    if cond:
        return credit(judge, doc, "P09", 0.5, "partial", "clause 9.4 attribution condition identified without asserting non-attribution", unique_lines(cond), "contract.penalty_attribution")
    return credit(judge, doc, "P09", 0, "missing", "attribution condition of clause 9.4 not argued", [], "contract.penalty_attribution")


# R22 relief scope: a set-off of a penalty the plaintiff is said to owe, or a
# counterclaim, asked for in the answer itself. Golden's relief asks only for dismissal and, in the
# alternative, for the penalty CLAIMED to be reduced; the task skill states the rule outright
# ("You answer, you do not claim"), and names the lawful alternative - reserving the point.
COUNTER_RELIEF = re.compile(
    r"(?:抵销|抵扣|冲抵)[^。;,]{0,10}?(?:违约金|违约责任|赔偿|损失|价款|款项|合同款)|"
    r"(?:违约金|违约责任|赔偿|损失)[^。;,]{0,12}?(?:先行)?(?:抵销|抵扣|冲抵)|"
    r"(?:提起|提出|依法)?反诉")
RESERVED_RELIEF = re.compile(r"保留|另行(?:提起|主张|起诉|诉讼|请求)|另案|另行(?:向|就)")


# R23 statement-of-defense units: the answering party block, a response to each claim (the principal
# 1,482,040 and the penalty), a request for dismissal, and the closing 此致 / addressee court / signature.
FORM_PARTY = re.compile(r"^(?:(?:答辩人|被告)(?:[（(][^）)]{0,12}(?:答辩人|被告)[^）)]{0,12}[)）])?|" + ANSWERER + r")[：:,][^。;]{0,12}?B公司")
FORM_COURT = re.compile(r"^(?:致:?)?[^,;。:]{0,20}法院$")


def form_units_missing(doc: Doc) -> list[str]:
    lines = doc.lines
    party_idx = [i for i, line in enumerate(lines) if line["region"] == "party"]
    start = party_idx[-1] + 1 if party_idx else 0
    rest = lines[start:]
    units = {
        "party_block": any(FORM_PARTY.match(lines[i]["clean"]) for i in party_idx),
        "principal_claim": any(CLAIM_PRINCIPAL in line["canon"] for line in rest),
        "penalty_claim": any(re.search(PENALTY, line["canon"]) for line in rest),
        "dismissal_request": any("驳回" in line["canon"] for line in rest) or (getattr(doc, "source_supported_strategy", False) and any(re.search(r"请求|恳请", line["clean"]) for line in rest)),
    }
    return [unit for unit, present in units.items() if not present]


# D03: the statute is charged only where it is the author's own basis. The item's error_predicate
# already excludes "statements that it is repealed", and 不再有效/不再适用/已被《民法典》取代 say what
# 已废止 says. The clause-scoped negation window R02 reads catches 本案不应适用《合同法》的规定;
# 而非/而不是 is that same negation written as a contrast (应适用《民法典》而非《合同法》) and joins the
# window for this item only, because it only ever excludes when it stands immediately before the
# citation - 本案应适用《合同法》而非《民法典》 still charges. R02's ATTRIB wants a speech verb and so
# misses the plaintiff's own act of citing, 原告援引《合同法》第一百一十四条，属于适用法律错误, which
# is the plaintiff's legal basis being rejected rather than the defence's being asserted.
D03_DISPLACED = re.compile(r"废止|失效|不再(?:有效|适用|生效|具有效力)|已(?:被|由)[^。;,]{0,10}?(?:取代|替代)|原《|催收函")
D03_NEG = NEG + r"|而非|而不是"
D03_ATTRIBUTED = re.compile(PLA + r"[^。;,]{0,10}?(?:援引|引用|援用|所引|依据|根据|适用|诉称|声称|认为|主张|称)")


class Deductions:
    def __init__(self, judge: ProgramJudge, doc: Doc):
        self.judge, self.doc, self.counter = judge, doc, 0

    def decide(self, item_id, manifestations, key, root, reason, object_key, scan="obs.scan.body"):
        if not manifestations:
            state = "ambiguous" if self.doc.state == "ambiguous" and scan == "obs.scan.body" else "not_triggered"
            self.judge.deduction(item_id, state, [scan], "error proposition not asserted" if state == "not_triggered" else "body unresolved")
            return
        occurrences, obs_ids, seen = [], [], set()
        for line, detail in manifestations:
            manifestation = f"{item_id}:{line['locator']}:{detail}"
            if manifestation in seen:
                continue
            seen.add(manifestation)
            self.counter += 1
            obs = observe_lines(self.judge, self.doc, f"obs.{item_id}.m{self.counter}", [line], object_key, "error_span", "N01")
            obs_ids.append(obs)
            occurrences.append({"damage_instance_key": key, "causal_root_id": root, "manifestation_id": manifestation,
                                "observation_id": obs, "reason": detail})
        self.judge.deduction(item_id, "triggered", [scan] + obs_ids, reason, occurrences)


def shape_count(lines: list[dict]) -> int:
    """N07: non-whitespace characters of body lines, excluding clauses containing a gap token."""
    total = 0
    for line in lines:
        for clause in re.split(r"[,;。:]", n05_gap(line["clean"])):
            if GAP_TOKEN not in clause:
                total += len(clause)
    return total


def eval_deductions(judge: ProgramJudge, doc: Doc) -> None:
    d = Deductions(judge, doc)
    body_ok = doc.state == "identified"
    body = body_paragraphs(doc) if body_ok else []

    # D01 liability concession (R12)
    found = [(line, name) for line, _s, name in liability_conceded(doc)] if body_ok and not getattr(doc, "source_supported_strategy", False) else []
    d.decide("D01", found, "liability_conceded", "R-concession",
             "the defence concedes that payment is due or that the defendant is in default", "conclusion.payment_condition")

    # D02 wrong side
    found = []
    for line in doc.lines:
        if line["region"] == "party" and re.match(r"^答辩人(\([^)]*\))?:[^,;。]{0,6}?A公司", line["canon"]):
            found.append((line, "respondent_is_plaintiff"))
    for line in body:
        for sentence in sentences(line["canon"]):
            m = re.search(r"(?:请求|恳请|要求)[^。;,]{0,10}?(?:依法)?支持(?:原告|被答辩人|A公司)(?:的)?(?:全部|各项|所有)?(?:诉讼)?请求", sentence)
            # The negation window is read at the key verb 支持 (the last character of the span),
            # not at the span head, so 请求法院不予支持原告的诉讼请求 stays out.
            if (m and not getattr(doc, "source_supported_strategy", False) and not neg_before(sentence, m.start() + len(m.group(0)) - 1)
                    and not excluded(sentence, m.start())
                    and not alternative_framed(sentence, m.end())):
                found.append((line, "supports_plaintiff_claims"))
    d.decide("D02", found, "wrong_side", "R-side",
             "the document is written for the plaintiff or asks the court to uphold the plaintiff's claims", "party.respondent", scan="obs.scan.all")

    # D03 repealed Contract Law as basis
    found = []
    for line in body:
        for sentence in sentences(line["canon"]):
            m = re.search(r"《(?:中华人民共和国)?合同法》", sentence)
            if not m or D03_DISPLACED.search(sentence):
                continue
            if D03_ATTRIBUTED.search(sentence[:m.start()]):
                continue
            if deduction_excluded(sentence, m.start(), m.end(), neg=D03_NEG):
                continue
            found.append((line, "contract_law_basis"))
    d.decide("D03", found, "repealed_law_basis", "R-law",
             "relies on the repealed Contract Law for a 2022 contract governed by the Civil Code", "legal_basis")

    # D04 misidentified claim-1 amount
    found = []
    for line in body:
        for sentence in sentences(line["canon"]):
            if CANDIDATE.search(sentence):
                continue
            m = re.search(r"(?:原告|被答辩人|A公司|对方)[^。;]{0,12}?(?:请求|主张|诉请|要求)[^。;]{0,8}?(?:判令)?(?:被告|答辩人|B公司)?[^。;]{0,4}?(?:支付|给付)[^。;]{0,12}?" + PRINCIPAL_NOUN + r"[^。;]{0,6}?¥?([\d,]+(?:\.\d+)?|[零〇一二两三四五六七八九十百千万亿壹贰叁肆伍陆柒捌玖拾佰仟]+)|"
                          r"(?:第(?:一|1)项(?:诉讼)?请求|诉讼请求(?:第)?(?:一|1)项?)[^。;]{0,20}?¥?([\d,]+(?:\.\d+)?|[零〇一二两三四五六七八九十百千万亿壹贰叁肆伍陆柒捌玖拾佰仟]+)", sentence)
            amount = (m.group(1) or m.group(2)) if m else None
            # The contract trigger is open-ended: any asserted principal other
            # than the material's 1,482,040 amount is an error, not only a
            # historical list of five confusable constants.
            numeric_amount = amount.replace(',', '') if amount and amount[0].isdigit() else str(chinese_amount(amount) or '')
            if not m or numeric_amount == CLAIM_PRINCIPAL or "违约金" in m.group(0):
                continue
            # D04's own trigger is a sentence that attributes a claim to the plaintiff, so R02's
            # attribution arm cannot be applied to it without emptying the item; the two arms that
            # do apply are the negation before the span and the alternative frame.
            if neg_before(sentence, m.start()) or alternative_framed(sentence, m.end()):
                continue
            found.append((line, "claimed-" + (m.group(1) or m.group(2))))
    d.decide("D04", found, "claim_amount_misidentified", "R-claim-object",
             "the defence answers a principal claim amount the complaint does not make", "claim1.rejection")

    # D05 denies the contract relationship or validity
    found = []
    for line in body:
        for sentence in sentences(line["canon"]):
            for m in re.finditer(r"(?:双方|原被告|" + PLA + r"与" + DEF + r")[^。;,]{0,10}?(?:不存在|没有|无)[^。;,]{0,6}?合同(?:关系)?|"
                                 r"(?:采购合同|本案合同|涉案合同|案涉合同|该合同)[^。;,]{0,6}?(?:无效|不成立|未生效|未成立)", sentence):
                # D05's trigger is itself a negation (双方不存在合同关系), so the negation window uses
                # DNEG - a denial of that denial - rather than NEG, which the span would trip on.
                if (deduction_excluded(sentence, m.start(), m.end(), neg=DNEG)
                        or re.search(r"并非|不是|不属于", m.group(0))):
                    continue
                if re.search(r"(?:原告|对方)[^。;,]{0,8}?(?:称|主张|认为)", sentence[:m.start()]):
                    continue
                found.append((line, "contract_denied"))
                break
    d.decide("D05", found, "contract_relationship_denied", "R-contract",
             "denies the purchase contract that the defence itself must rely on", "contract.relationship")

    # D06 fabricated identifiers instead of gap markers
    # D06, D08 and D11 charge a field, a measurement and a missing unit, not a proposition asserted
    # in a body sentence, so the sentence-level exclusion gate has nothing to attach to: an
    # identifier segment carries no verb to negate and no clause to frame as an alternative.
    # Reading ALTERNATIVE over such a line would only mean that writing 即便 anywhere in it buys a
    # fabricated case number. What stands in for the gate here is N05: a value marked as a gap is
    # never charged, which is the exclusion the item's own error_predicate names.
    found = []
    for line in doc.lines:
        for segment in re.split(r"[,;。]", n05_gap(line["clean"])):
            if GAP_TOKEN in segment:
                continue
            if line["region"] in ("party", "closing", "title"):
                if re.search(r"住所地?|地址|住址", segment) and re.search(r"\d+(号|路|栋|室|弄|幢|单元|楼)", segment):
                    found.append((line, "address_digits"))
                if re.search(r"(统一社会信用代码|信用代码|组织机构代码):?[0-9A-Z]{9,18}", segment):
                    found.append((line, "credit_code"))
                if re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)|(?<!\d)0\d{2,3}-\d{7,8}(?!\d)", segment):
                    found.append((line, "phone"))
                # R-fabrication: only a filled field charges. The separator is required, because
                # without it the pattern reads a compound label (法定代表人或委托诉讼代理人,
                # 法定代表人身份证明书, 双方法定代表人签字) as if the following characters were a name.
                m = re.search(r"(法定代表人|负责人|委托(?:诉讼)?代理人|代理人):([一-鿿]{2,4})", segment)
                if m and not re.search(r"某|自然人|职务|同上|不详|董事|经理|律师|甲|乙|丙|丁|戊", m.group(2)):
                    found.append((line, "person_name"))
            if re.search(r"\(\d{4}\)[^()]{0,12}?\d+号", segment):
                found.append((line, "case_number"))
    d.decide("D06", found, "fabricated_identifiers", "R-fabrication",
             "invents case numbers or party identifiers that the materials do not contain", "party.identifiers", scan="obs.scan.all")

    # D07 concedes owner confirmation of phase 2 or delivery of the confirmation letter (R09)
    found = [(line, "confirmation_conceded") for line, _s in owner_confirmation_conceded(doc)] if body_ok else []
    d.decide("D07", found, "owner_confirmation_conceded", "R-confirmation",
             "concedes that C公司 confirmed the phase-2 video or that its confirmation letter was delivered", "evidence.owner_confirmation_absent")

    # D09 author-originated interest-rate figure the record does not carry (R19)
    found = []
    for line in body:
        for sentence in sentences(line["canon"]):
            if ALTERNATIVE.search(sentence):
                continue
            for start, end in clause_windows(sentence):
                clause = sentence[start:end]
                if CANDIDATE.search(clause) or is_list_spray(clause) or too_dense(clause):
                    continue
                if RATE_NON_INTEREST.search(clause):
                    continue
                for m in RATE_FIGURE.finditer(clause):
                    figure = m.group(1) or m.group(2)
                    if rate_figure_supported(line, clause, m, figure):
                        continue
                    position = start + m.start()
                    if neg_before(sentence, position):
                        continue
                    # R19 reads attribution and the rejection tail "over the whole sentence", and
                    # R21 settles what a sentence is in this contract: sentences() cuts at ；as well
                    # as 。, and a ；-clause is not a sentence. Both guards therefore run over the
                    # enclosing 。-sentence, which is where a defence puts the party it is quoting -
                    # "按被答辩人自己的计取方式，…；两项叠加后…，折合年化约6.65%".
                    scope, scope_position = sentence_scope(line, sentence, position)
                    if attributed_or_rejected(scope, scope_position):
                        continue
                    # R19/R02: a figure that characterises the plaintiff's own demand is that
                    # party's arithmetic, not the defence's own fact. R02's ATTRIB window is eight
                    # characters and wants a speech verb, so it misses the plaintiff's own
                    # stacked demand at nine: "被答辩人在已按一年期LPR主张利息的同时…合计年化约6.7%".
                    if RATE_ATTRIBUTED.search(scope[:scope_position]):
                        continue
                    found.append((line, "rate-" + figure))
    d.decide("D09", found, "unsupported_rate_figure", "R-unsupported-addition",
             "asserts a numeric interest rate as the defence's own fact although the record binds no figure to any rate object",
             "document.unsupported_additions")

    # D10 relief the defendant has not claimed (R22)
    # D10 is the one item whose contract text opts out of the alternative arm - "An alternative
    # frame does NOT exclude: Golden's own alternative asks only for the penalty claimed to be
    # reduced, so relief against the plaintiff is outside the filing's scope in the primary and the
    # alternative alike" - so it takes R02's two arms directly and not deduction_excluded().
    found = []
    for line in body:
        for sentence in sentences(line["canon"]):
            m = COUNTER_RELIEF.search(sentence)
            if not m or excluded(sentence, m.start()) or neg_before(sentence, m.start()):
                continue
            # The skill's own carve-out: reserving the point for separate proceedings is not
            # asking for it here. The reservation governs its whole sentence.
            if RESERVED_RELIEF.search(sentence):
                continue
            found.append((line, "setoff" if re.search(r"抵销|抵扣|冲抵", m.group(0)) else "counterclaim"))
            break
    d.decide("D10", found, "relief_not_claimed", "R-relief-scope",
             "asks the tribunal for relief against the plaintiff that the defendant has not claimed in "
             "the proceedings", "relief.scope")

    # D11 statement-of-defense units (R23): each unit the brief's "respond to the plaintiff's claims" in a
    # "civil statement of defense" requires is its own damage instance, so missing units compound.
    missing = form_units_missing(doc)
    if not doc.lines:
        judge.deduction("D11", "not_triggered", ["obs.scan.all"], "no deliverable text; omission only loses positive credit")
    elif not missing:
        judge.deduction("D11", "not_triggered", ["obs.scan.all"], "every statement-of-defense unit present")
    else:
        judge.deduction("D11", "triggered", ["obs.scan.all"], "statement-of-defense units missing: " + ", ".join(missing),
                        [{"damage_instance_key": f"form_unit_{unit}", "causal_root_id": f"R-form-{unit}",
                          "manifestation_id": f"D11:{unit}", "observation_id": "obs.scan.all",
                          "reason": f"{unit} missing"} for unit in missing])

    # D08 shape (R17)
    shapes = {s["id"]: s for s in judge.contract.get("shape_units", [])}
    if doc.state == "ambiguous":
        judge.deduction("D08", "ambiguous", ["obs.scan.body"], "body boundaries unresolved")
        return
    if doc.state != "identified":
        judge.deduction("D08", "not_triggered", ["obs.scan.body"], "body missing; omission only loses positive credit")
        return
    judge.deduction("D08", "not_applicable", ["obs.scan.body"], "reference length is diagnostic only; missing substantive content loses positive credit")
    return
    count = shape_count(doc.body)
    if count == 0:
        judge.deduction("D08", "not_applicable", ["obs.scan.body"], "body contains only gap-marked content")
        return
    shape = shapes["S01"]
    ratio = count / max(float(shape["golden_value"]), float(shape["declared_floor"]))
    # S01 carries an underrun arm always and an overrun arm only when the contract declares one. A null
    # overrun_tolerance_ratio means the task asked for no length ceiling: the instruction states none and
    # the Golden count is not visible to the answering model, so a longer brief is not chargeable damage.
    overrun_tolerance = shape.get("overrun_tolerance_ratio")
    over = -1.0 if overrun_tolerance is None else ratio - (1 + float(overrun_tolerance))
    under = (1 - float(shape["underrun_tolerance_ratio"])) - ratio
    if over <= 0 and under <= 0:
        judge.deduction("D08", "not_triggered", ["obs.scan.body"], f"length ratio {ratio:.3f} within tolerance")
        return
    detail = f"{'over' if over > 0 else 'under'}-{count}-of-{int(shape['golden_value'])}"
    obs = observe_lines(judge, doc, "obs.D08.shape", doc.body, "shape.S01", "shape_members", "N07")
    judge.deduction("D08", "triggered", ["obs.scan.body", obs], f"length ratio {ratio:.3f} outside tolerance",
                    [{"damage_instance_key": "shape_S01", "causal_root_id": "R-shape-S01",
                      "manifestation_id": f"D08:S01:{detail}", "observation_id": obs, "reason": detail}])


def evaluate(registry: dict, judge: ProgramJudge, semantic=None) -> None:
    """Call positive() once per P and deduction() once per D."""
    if registry.get("parse_failure"):
        for item_id in judge.positives:
            judge.positive(item_id, 0.0, "obs.parse_failure", "artifact could not be parsed", "different")
        for item_id in judge.deductions:
            judge.deduction(item_id, "parse_failure", ["obs.parse_failure"], "artifact could not be parsed")
        return
    doc = registry["doc"]
    if semantic is None: raise RuntimeError("substantive criteria require semantic adjudication")
    for item_id in judge.positives:
        row = semantic["items"][item_id]
        lines = [line for line in doc.lines if any(q in line["clean"] or line["clean"] in q for q in row["quotes"])]
        credit(judge, doc, item_id, row["fraction"],
               "equivalent" if row["fraction"] == 1 else "partial" if row["fraction"] else "missing",
               row["reason"], lines, judge.positives[item_id]["object_key"])
    doc.source_supported_strategy = semantic["items"]["STRATEGY"]["fraction"] == 1
    eval_deductions(judge, doc)
    strategy = semantic["items"]["STRATEGY"]
    already_charged = any(judge._deduction_results.get(item, {}).get("state") == "triggered"
                          for item in ("D01", "D02", "D04", "D07"))
    if strategy["fraction"] == 1 or already_charged:
        judge.deduction("D12", "not_triggered", ["obs.scan.body"], strategy["reason"])
    else:
        judge.deduction("D12", "triggered", ["obs.scan.body"], strategy["reason"],
                        [{"damage_instance_key": "unsupported_material_position",
                          "causal_root_id": "R-source-support",
                          "manifestation_id": "D12:semantic-source-support",
                          "observation_id": "obs.scan.body",
                          "reason": strategy["reason"]}])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--contract", type=Path, default=CANONICAL_CONTRACT)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    contract_path = args.contract.resolve()
    judge = ProgramJudge(load_contract(contract_path), args.artifact.resolve(), sha256(contract_path))
    registry = normalize(extract_raw(args.artifact.resolve()), judge)
    semantic = None
    if not registry.get("parse_failure"):
        import sys
        tests = Path(__file__).resolve().parents[4]
        sys.path.insert(0, str(tests))
        from semantic_judge import adjudicate
        semantic = adjudicate("\n".join(line["clean"] for line in registry["doc"].lines), (tests / "semantic_source.json").read_text())
    evaluate(registry, judge, semantic)
    result = judge.finish()
    if semantic: result["semantic_judge"] = semantic
    fractions = {item["id"]: item["fraction"] for item in result["items"]}
    triggered = {item_id for damage in result["penalty_instances"] for item_id in damage["item_ids"]}
    # A filing is ready for use without substantive redrafting only when both
    # claims are answered through the complete source-bound chain.  This is an
    # owner-presence gate, not a threshold over the continuous reward: each
    # named proposition may use any supported equivalent wording or valid
    # partial formulation, while an omitted link remains observable.
    required_legal_units = {"P01", "P03", "P04", "P05", "P07", "P09"}
    result["rewards"]["lenient"] = 1.0 if (
        all(fractions.get(item_id, 0) > 0 for item_id in required_legal_units)
        and semantic["items"]["STRATEGY"]["fraction"] == 1
        and not ({"D01", "D02", "D04", "D07", "D11", "D12"} & triggered)
    ) else 0.0
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
