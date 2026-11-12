#!/usr/bin/env python3
"""Program Judge adapter for the defendant's civil appeal petition (装饰装修合同纠纷, 下沉式广场).

Three explicit layers:
  extract_raw()  carrier text only (Markdown lines, or DOCX body paragraphs and table rows)
  normalize()    registered rules N01-N09 turn lines into canonical observations
                 (header, appeal requests, facts-and-reasons body with heading chains,
                 closing block, quoted spans, asserted clauses, gap markers)
  evaluate()     one positive() call per P and one deduction() call per D, using the
                 registered derivation rules R01-R10 for adoption, spans, objects, conflicts and shape.

No model judgement is embedded. Every fact, alias and threshold comes from
rubric-contract.json and the Golden.
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

# Task constants, each visible in the first-instance judgment.
AWARD = "¥193440"                     # judgment item 1, 下沉式广场 装修款
QUOTE_TOTAL = "¥194970"               # plaintiff's pre-construction quotation
DOOR_FEE = "¥1530"                    # folding-door labour deducted by the court
CONSENTED = ("¥1222.19", "¥371750")   # G/B 硬装 interest the defendant agreed to pay
MATERIAL_NAMES = set("丙丁戊己庚辛壬癸")  # anonymised persons present in the judgment

GAP_MARKERS = [
    "[待补充]", "【待补充】", "[待填写]", "【待填写】", "[待核实]", "【待核实】", "[待定]", "【待定】",
    "[placeholder]", "材料未提供", "未提供", "待补充", "待填写", "待核实", "unspecified", "TBD",
]
GAP = "⟦GAP⟧"
Q = "⟦Q⟧"

TITLE_RE = re.compile(r"^(民事)?上诉(状|书)$")
PARTY_LABEL = re.compile(r"^(上诉人|被上诉人|原审原告|原审被告|一审原告|一审被告)(\([^)]{0,20}\))?:(.*)$")
PARTY_CONT = re.compile(r"^(法定代表人|负责人|住所地?|地址|住址|委托(诉讼)?代理人|统一社会信用代码|联系(电话|方式)|电话|职务)")
REQ_HEAD = re.compile(r"^(上诉请求(事项)?|请求事项|上诉事项)(如下)?:?(?P<rest>.*)$")
REA_HEAD = re.compile(r"^(事实(与|和|及)理由|上诉(的)?(事实(与|和|及))?理由|理由)(如下)?:?(?P<rest>.*)$")
NUMBERING = re.compile(r"^([一二三四五六七八九十]+[、.]|\([一二三四五六七八九十]+\)|\d{1,2}[.、](?!\d)|\(\d{1,2}\))")
L1_RE = re.compile(r"^[一二三四五六七八九十]+[、.]")
L2_RE = re.compile(r"^\([一二三四五六七八九十]+\)")
L3_RE = re.compile(r"^\d{1,2}[.、](?!\d)")
L4_RE = re.compile(r"^\(\d{1,2}\)")

APPELLANT = r"(?<!被)上诉人|D公司|一审被告|原审被告|我方|本公司"
APPELLEE = r"被上诉人|B公司|一审原告|原审原告|原告|承包人"
WRONG_OBJ = re.compile(r"G栋|B栋|硬装|补充协议|¥371750|¥1222\.19|¥743500")
RIGHT_OBJ = re.compile(r"下沉式广场|广场|¥193440|¥194970|报价清单")

CANDIDATE = re.compile(r"可能|或许|也许|抑或|要么|备选|候选|待定|倾向于|不排除|二选一")
GENERIC_VIEW = re.compile(r"有观点|有人认为|有意见认为|一种观点|另一种观点|有说法|或(有|可)认为")
VIEW_REJECTED = re.compile(r"(该|此|上述|这一|这种|前述)(观点|说法|看法|意见|主张|理由)[^。;]{0,6}?(不能成立|不成立|不予采纳|不能采纳|错误|站不住脚|缺乏依据|难以成立)")
ATTRIB = re.compile(r"(被上诉人|B公司|一审原告|原审原告|原告|对方(当事人)?|原审(法院|判决)?|一审(法院|判决)|原判(决)?|判决(书)?|本院|法院)"
                    r"(?P<gap>(?:(?!作为)[^,;。:的“”]){0,6}?)(坚持认为|认为|认定|称|主张|辩称|诉称|载明|确定|指出|提出)(?!的)")
REBUT = re.compile(r"错误|不当|失当|不能成立|不成立|缺乏(事实(和|与|及)?法律)?依据|没有(事实(和|与)?法律)?依据|依据不足|基础不足|"
                   r"矛盾|不符|相悖|不清|站不住脚|不应(予以)?(采纳|支持)|不足以|难以成立")
CONCESSIVE = re.compile(r"^(尽管|虽然|虽|即使|即便|哪怕|纵使|退一步(讲|说|而言)?|假设|假如|如果|若|倘若|如(?!前|上|下|此|实))")
TURN = re.compile(r"^(但|但是|然而|可是|却|事实上|实际上|对此|而|该(主张|观点|说法|认定)|上述)")

QUOTE_RE = re.compile(r"“([^”]{13,})”|「([^」]{13,})」|『([^』]{13,})』")
# N03: a date written in Chinese numerals (二〇二五年四月二十一日, the judgment's own 二○二六年五月 style) is the
# same date; it is folded to the Arabic form before DATE_CN/MONTH_CN read it, so an equivalent correct date earns
# the same credit and a wrong date written that way is charged the same way.
CN_YEAR_DIGITS = {"零": "0", "〇": "0", "○": "0", "0": "0", "一": "1", "二": "2", "三": "3", "四": "4", "五": "5",
                  "六": "6", "七": "7", "八": "8", "九": "9"}
DATE_CN_NUMERAL = re.compile(r"([零〇○一二三四五六七八九]{4})年([一二三四五六七八九十]{1,3})月(?:([一二三四五六七八九十]{1,3})日)?")


def fold_cn_numeral_date(text: str) -> str:
    def fold(m: re.Match) -> str:
        year = "".join(CN_YEAR_DIGITS[c] for c in m.group(1))
        month = cn_number(m.group(2))
        day = cn_number(m.group(3)) if m.group(3) else None
        if month is None or not 1 <= month <= 12 or (m.group(3) and (day is None or not 1 <= day <= 31)):
            return m.group(0)
        return f"{year}年{month}月" + (f"{day}日" if m.group(3) else "")
    return DATE_CN_NUMERAL.sub(fold, text)


DATE_CN = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")
MONTH_CN = re.compile(r"(\d{4})年(\d{1,2})月(?![\d份])")
MD_CN = re.compile(r"(?<![\d年@-])(\d{1,2})月(\d{1,2})日")
M_CN = re.compile(r"(?<![\d年@-])(\d{1,2})月(?=左右|底|初|中旬|上旬|下旬|间|份)")
DATE_NUM = re.compile(r"(?<![\d.@¥])((?:19|20)\d{2})[-/.](\d{1,2})[-/.](\d{1,2})日?(?![\d.])")
MONTH_NUM = re.compile(r"(?<![\d.@¥§])((?:19|20)\d{2})[-/.](\d{1,2})(?![\d.])")
RANGE_WAN = re.compile(r"(\d+(?:\.\d+)?)(万元|万)?(?:元)?(?:-|~|—|–|至|到)(\d+(?:\.\d+)?)(万元|万)")
RANGE_CN = re.compile(r"七八万元?|七至八万元?|七到八万元?")
RANGE_YUAN = re.compile(r"(?<![\d.@¥])(\d{1,3}(?:,\d{3})+|\d{4,})元?(?:-|~|—|–|至|到)(\d{1,3}(?:,\d{3})+|\d{4,})元")
MONEY = re.compile(r"(?:人民币|RMB)?(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(万元|元)|¥(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(?:元)?")
ARTICLE = re.compile(r"第([零〇一二两三四五六七八九十百千0-9]+)条")
CLAUSE = re.compile(r"第([一二三四五六七八九十0-9]+)款")
ITEM = re.compile(r"第\(?([一二三四五六七八九十0-9]+)\)?项")
CN_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CN_UNITS = {"十": 10, "百": 100, "千": 1000}
AMOUNT_KW = re.compile(r"工程款|结算|报价|施工范围|工程量|举证|价款|¥193440|未施工|自认")
INTEREST_KW = re.compile(r"利息|交付|起算|验收|质量")


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
        except Exception as exc:  # corrupt container
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


def yuan(integer: str, fraction: str | None, unit: str | None) -> str:
    try:
        value = Decimal(integer.replace(",", "") + (fraction or ""))
    except InvalidOperation:
        return integer
    if unit and unit.startswith("万"):
        value *= 10000
    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "¥" + text


def n01_clean(text: str) -> tuple[str, int, bool]:
    """N01: NFKC fold, drop zero-width characters, Markdown decoration and table pipes, remove whitespace."""
    text = unicodedata.normalize("NFKC", text)
    for invisible in ("​", "‌", "‍", "﻿", "­"):
        text = text.replace(invisible, "")
    stripped = text.strip()
    depth = 0
    if stripped.startswith("|"):
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", cell or "--") for cell in cells):
            return "", 0, False
        text = ":".join(cell.rstrip(":") for cell in cells if cell)
    m = re.match(r"^\s*(#{1,6})\s*", text)
    if m:
        depth = len(m.group(1))
        text = text[m.end():]
    text = re.sub(r"^\s*>\s*", "", text)
    text = re.sub(r"^\s*[-*+]\s+", "", text)
    bold = bool(re.fullmatch(r"\s*(\*\*|__)[^*_]+(\*\*|__)[:：]?\s*", text))
    text = text.replace("**", "").replace("__", "").replace("`", "")
    return re.sub(r"\s+", "", text), depth, bold


def n06_gap(text: str) -> str:
    """N06: fold every declared gap marker (and blank runs such as ____ or ××) into one gap token."""
    for marker in sorted(GAP_MARKERS, key=len, reverse=True):
        text = text.replace(unicodedata.normalize("NFKC", marker), GAP)
    return re.sub(r"_{3,}|×{2,}|X{3,}|\*{3,}(?!\*)", GAP, text)


def n02_n03_n05(text: str) -> str:
    """N03 dates, N02 money (with 7-8万 ranges), N05 statute article/paragraph/item numbers into canonical tokens."""
    text = fold_cn_numeral_date(text)
    text = DATE_CN.sub(lambda m: f"@{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}", text)
    text = MONTH_CN.sub(lambda m: f"@{int(m.group(1)):04d}-{int(m.group(2)):02d}", text)
    text = DATE_NUM.sub(lambda m: f"@{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}", text)
    text = MONTH_NUM.sub(lambda m: f"@{int(m.group(1)):04d}-{int(m.group(2)):02d}", text)
    text = MD_CN.sub(lambda m: f"@--{int(m.group(1)):02d}-{int(m.group(2)):02d}", text)
    text = M_CN.sub(lambda m: f"@--{int(m.group(1)):02d}", text)

    def rng(m: re.Match) -> str:
        low_unit = m.group(2) or m.group(4)
        return yuan(m.group(1), None, low_unit) + "~" + yuan(m.group(3), None, m.group(4))

    text = RANGE_WAN.sub(rng, text)
    text = RANGE_CN.sub("¥70000~¥80000", text)
    text = RANGE_YUAN.sub(lambda m: yuan(m.group(1), None, None) + "~" + yuan(m.group(2), None, None), text)

    def money(m: re.Match) -> str:
        if m.group(1) is not None:
            return yuan(m.group(1), m.group(2), m.group(3))
        return yuan(m.group(4), m.group(5), None)

    text = MONEY.sub(money, text)
    text = ARTICLE.sub(lambda m: f"§{cn_number(m.group(1))}" if cn_number(m.group(1)) is not None else m.group(0), text)
    text = CLAUSE.sub(lambda m: f"¶{cn_number(m.group(1))}" if cn_number(m.group(1)) is not None else m.group(0), text)
    return ITEM.sub(lambda m: f"#{cn_number(m.group(1))}" if cn_number(m.group(1)) is not None else m.group(0), text)


def n07_quotes(text: str) -> str:
    """N07: quoted propositions of 13+ characters are not the author's own assertion; a quote whose text
    ends a sentence keeps that sentence boundary so the author's next sentence stays separate.
    ASCII straight double quotes carry no direction, so they pair left to right inside the line (1st with
    2nd, 3rd with 4th) and only a pair of 13+ characters folds; a lone trailing quote stays literal.
    Curly and corner quotes keep their own direction."""
    def folded(inner: str) -> str:
        return "“…”。" if inner.rstrip().endswith(("。", "!", "?", ";")) else "“…”"
    text = QUOTE_RE.sub(lambda m: folded(next(g for g in m.groups() if g is not None)), text)
    parts = text.split('"')
    if len(parts) < 3:
        return text
    out, i = [parts[0]], 1
    while i < len(parts):
        if i + 1 < len(parts):
            out.append(folded(parts[i]) if len(parts[i]) >= 13 else '"' + parts[i] + '"')
            out.append(parts[i + 1])
            i += 2
        else:
            out.append('"' + parts[i])
            i += 1
    return "".join(out)


def r02_asserted(sentence: str) -> str:
    """R02: drop non-adopted content. Candidate sentences, generic or rejected views become Q; clauses that
    open with a concessive/conditional marker are dropped; an attribution to the appellee or the court drops
    the attributed text up to the first rebuttal marker later in the sentence, or, without one, until a
    clause opens with a turn marker."""
    if CANDIDATE.search(sentence) or GENERIC_VIEW.search(sentence) or VIEW_REJECTED.search(sentence):
        return Q
    clauses = re.split(r"(?<=[,:])", sentence)
    out: list[str] = []
    i = 0
    while i < len(clauses):
        body = clauses[i]
        if CONCESSIVE.match(body):
            out.append(Q)
            i += 1
            continue
        m = ATTRIB.search(body)
        if not m or re.search(r"不|未|没有|并非", m.group("gap")):
            out.append(body)
            i += 1
            continue
        r = REBUT.search(body, m.end())
        if r:
            out.append(body[:m.start()] + Q + body[r.start():])
            i += 1
            continue
        out.append(body[:m.start()] + Q)
        j = i + 1
        while j < len(clauses) and not TURN.match(clauses[j]):
            r = REBUT.search(clauses[j])
            if r:
                out.append(clauses[j])
                break
            out.append(Q)
            j += 1
        else:
            j -= 1
        i = j + 1
    return "".join(out)


def split_sentences(text: str) -> list[str]:
    return [part for part in re.split(r"[。;!?]", text) if part]


def raw_token_soup(raw_text: str) -> bool:
    """R01: a raw line whose words are separated by whitespace (four or more fragments, 70 percent of them
    at most eight characters) or by list separators (eight or more short fragments) is keyword soup.
    Whitespace inside a date or amount (`2025 年 4 月 21 日`, `193, 440 元`) is collapsed first so it stays one phrase."""
    text = unicodedata.normalize("NFKC", raw_text).replace("**", "").strip()
    text = re.sub(r"^\s*(#{1,6}|[-*+>]|\d+[.)])\s+", "", text)
    text = re.sub(r"(\d)\s+(?=[\d年月日元万号条款项%,.])|(?<=[年月,.])\s+(?=\d)|(?<=[第])\s+|\s+(?=[条款项])", r"\1", text)
    words = [frag for frag in re.split(r"\s+", text) if frag]
    if len(words) >= 4 and sum(len(w) <= 8 for w in words) >= 0.7 * len(words):
        return True
    fragments = [frag for frag in re.split(r"[\s、,，/|]+", text) if frag]
    short = [frag for frag in fragments if len(frag) <= 8]
    return len(fragments) >= 8 and len(short) >= 0.7 * len(fragments)


def is_list_spray(sentence: str) -> bool:
    """R01: six or more short enumerated fragments in one sentence are a keyword list, not a proposition."""
    fragments = re.split(r"[、,/]", sentence)
    short = [frag for frag in fragments if len(frag) <= 8]
    return len(fragments) >= 6 and len(short) >= 0.7 * len(fragments)


def too_dense(sentence: str) -> bool:
    """R01: one sentence with more than four distinct amounts or four distinct dates is candidate spraying."""
    return len(set(re.findall(r"¥[\d.]+", sentence))) > 4 or len(set(re.findall(r"@[\d-]+", sentence))) > 4


def heading_level(clean: str, depth: int, bold: bool) -> int:
    """N04: numbered, Markdown or bold short lines resolve to a heading level; multi-sentence paragraphs do not."""
    numbered = 1 if L1_RE.match(clean) else 2 if L2_RE.match(clean) else 3 if L3_RE.match(clean) else 4 if L4_RE.match(clean) else 0
    if depth:
        return numbered or min(depth, 4)
    if bold and len(clean) <= 80:
        return numbered or 3
    if numbered and len(clean) <= 100 and clean.rstrip("。").count("。") == 0:
        return numbered
    return 0


class Doc:
    """Normalized petition: header, requests, reasons (with heading chains), closing."""

    def __init__(self, raw: dict):
        self.raw = raw
        self.artifact = str(raw["artifact"])
        self.lines: list[dict] = []
        for record in raw["records"]:
            clean, depth, bold = n01_clean(record["text"])
            if not clean:
                continue
            canon = n02_n03_n05(n06_gap(clean))
            self.lines.append({"locator": record["locator"], "raw": record["text"], "clean": clean, "canon": canon,
                               "quoted": n07_quotes(canon), "soup": raw_token_soup(record["text"]),
                               "depth": depth, "bold": bold})
        # N08 zones
        self.req_heads = [l for l in self.lines if self._req_match(l)]
        self.rea_heads = [l for l in self.lines if self._rea_match(l)]
        zone = "header"
        chain: dict[int, dict] = {}
        for line in self.lines:
            if zone != "closing" and line["clean"].startswith("此致"):
                zone = "closing"
            elif zone != "closing" and self._req_match(line):
                zone = "requests"
                rest = self._req_match(line).group("rest")
                if rest:
                    line["zone"] = "requests"
                    line["canon"] = n02_n03_n05(n06_gap(rest))
                    line["quoted"] = n07_quotes(line["canon"])
                    self._sentences(line)
                else:
                    line["zone"] = "requests_heading"
                continue
            elif zone != "closing" and self._rea_match(line):
                zone = "reasons"
                line["zone"] = "reasons_heading"
                chain = {}
                continue
            if zone == "header" and not (TITLE_RE.fullmatch(line["clean"]) or PARTY_LABEL.match(line["clean"]) or PARTY_CONT.match(line["clean"])):
                zone = "intro"
            line["zone"] = zone
            if zone == "reasons":
                level = heading_level(line["clean"], line["depth"], line["bold"])
                line["level"] = level
                if level:
                    chain = {k: v for k, v in chain.items() if k < level}
                    chain[level] = line
                line["chain"] = [chain[k] for k in sorted(chain) if chain[k] is not line]
                line["l1"] = chain.get(1)
            self._sentences(line)
        self.header = [l for l in self.lines if l.get("zone") == "header"]
        self.intro = [l for l in self.lines if l.get("zone") == "intro"]
        self.requests = [l for l in self.lines if l.get("zone") == "requests"]
        self.reasons = [l for l in self.lines if l.get("zone") == "reasons"]
        self.closing = [l for l in self.lines if l.get("zone") == "closing"]
        self.req_state = self._state(self.req_heads, self.requests)
        self.rea_state = self._state(self.rea_heads, self.reasons)
        self.spans = self._spans() if self.rea_state == "identified" else []

    @staticmethod
    def _req_match(line: dict):
        """N08: an appeal-request heading (optionally numbered, optionally with inline request text)."""
        m = REQ_HEAD.match(NUMBERING.sub("", line["clean"]))
        return m

    @staticmethod
    def _rea_match(line: dict):
        """N08: a facts-and-reasons heading line with no body text after it."""
        m = REA_HEAD.match(NUMBERING.sub("", line["clean"]))
        return m if m and not m.group("rest") else None

    @staticmethod
    def _state(heads: list, lines: list) -> str:
        if len(heads) > 1:
            return "ambiguous"
        return "identified" if heads and lines else "confirmed_missing"

    @staticmethod
    def _sentences(line: dict) -> None:
        out = []
        attributed = False
        for sentence in split_sentences(line["quoted"]):
            spray = line["soup"] or is_list_spray(sentence) or too_dense(sentence)
            body = NUMBERING.sub("", sentence) if not out else sentence
            continuation = attributed and re.match(r"^(故|因此|所以|据此|由此|因而)", body)
            asserted = r02_asserted(body)
            if continuation and not REBUT.search(body): asserted = Q
            out.append({"canon": sentence, "a": Q if spray else asserted})
            if ATTRIB.search(body): attributed = True
            if REBUT.search(body) or re.match(r"^(但|然而|对此|上诉人认为|我方认为)", body): attributed = False
        line["sentences"] = out

    def _spans(self) -> list[dict]:
        """R03: local spans = one reasons line (<=900 chars) with its heading chain, and one lowest-level
        heading block (heading plus following body lines until the next heading) of at most 1600 chars."""
        spans = []
        for line in self.reasons:
            if len(line["quoted"]) <= 900:
                spans.append({"lines": [line], "chain": line.get("chain", [])})
        current = None
        for line in self.reasons:
            if line.get("level"):
                if current and len(current["lines"]) > 1:
                    spans.append(current)
                current = {"lines": [line], "chain": line.get("chain", [])}
            elif current is not None:
                current["lines"].append(line)
        if current and len(current["lines"]) > 1:
            spans.append(current)
        result = []
        for span in spans:
            if len(span["lines"]) > 1 and sum(len(l["quoted"]) for l in span["lines"]) > 1600:
                continue
            span["sentences"] = [s for l in span["lines"] for s in l["sentences"]]
            span["ctx"] = "".join(h["canon"] for h in span["chain"]) + "".join(l["canon"] for l in span["lines"])
            result.append(span)
        return result

    def loc(self, line: dict, object_key: str, field: str, prefix: str) -> Locator:
        return Locator(locator_id=f"{prefix}:{line['locator']}", artifact_path=self.artifact,
                       container_type=self.raw["carrier"] or "unknown", container_path=line["locator"],
                       object_key=object_key, field=field, observed=line["raw"][:400])

    def canon_loc(self, source: Locator, line: dict, rule: str) -> Locator:
        return Locator(locator_id=source.locator_id + ":canon", artifact_path=self.artifact,
                       container_type=source.container_type, container_path=source.container_path,
                       object_key=source.object_key, field=source.field + ".canonical",
                       observed=line["quoted"][:400], evidence_origin="lossless_canonicalized",
                       source_locator_ids=(source.locator_id,), normalization_rule_id=rule)

    def section_loc(self, section: str, object_key: str, prefix: str, state: str) -> Locator:
        return Locator(locator_id=f"{prefix}:section:{section}", artifact_path=self.artifact,
                       container_type=self.raw["carrier"] or "unknown", container_path=f"section:{section}",
                       object_key=object_key, field="section_state", observed=state)


def observe_lines(judge: ProgramJudge, doc: Doc, obs_id: str, lines: list[dict], object_key: str, field: str, rule: str) -> str:
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
                          "artifact", "appeal_petition", "carrier", raw_registry["parse_error"])
        judge.observe("obs.parse_failure", "parse_failure", [locator])
        return {"parse_failure": True}
    doc = Doc(raw_registry)
    for name, lines in (("header", doc.header), ("intro", doc.intro), ("requests", doc.requests),
                        ("reasons", doc.reasons), ("closing", doc.closing)):
        if lines:
            observe_lines(judge, doc, f"obs.scan.{name}", lines, f"section.{name}", "section_text", "N01")
        else:
            judge.observe(f"obs.scan.{name}", "confirmed_missing",
                          [doc.section_loc(name, f"section.{name}", f"obs.scan.{name}", "confirmed_missing")])
    return {"parse_failure": False, "doc": doc}


# ---------------------------------------------------------------------------
# Layer 3: P/D decisions
# ---------------------------------------------------------------------------
NEG_BEFORE = re.compile(r"(并非|不是|并不是|没有|并无|不存在|谈不上|并不|否认)[^。;,]{0,4}$")
NEG_SPEECH = re.compile(r"(并不|并非|不是|没有|并没有|无意|不再|未曾|不)(请求|主张|认为|认可|援引|要求|提出|同意|认同)")
DOUBLE_NEG = re.compile(r"(并非|并不是|不是|并无|并没有|不存在)(不|未|无)(?![当妥])")


def adopted_matches(pattern: re.Pattern, text: str, object_bound: bool = True):
    """R04: every candidate match that is not negated: no negation frame in the eight characters before it,
    no negated speech/request verb earlier in its clause, and no double negation (并非不/并非未) in the
    pre-window or inside the match; when object bound (R05), a match whose 20-character window names the
    G/B 硬装 object without also naming 下沉式广场 is the wrong object."""
    pos = 0
    while pos <= len(text):
        m = pattern.search(text, pos)
        if not m:
            return
        pos = m.start() + 1
        pre = text[max(0, m.start() - 8):m.start()]
        clause_start = max(text.rfind(",", 0, m.start()), text.rfind(":", 0, m.start())) + 1
        if NEG_BEFORE.search(pre) or NEG_SPEECH.search(text[clause_start:m.start()]) or DOUBLE_NEG.search(pre + m.group(0)):
            continue
        if object_bound:
            window = text[max(0, m.start() - 20):m.end()]
            if WRONG_OBJ.search(window) and not RIGHT_OBJ.search(window):
                continue
        yield m


def has(pattern: re.Pattern, text: str, object_bound: bool = True) -> bool:
    return next(adopted_matches(pattern, text, object_bound), None) is not None


def credit(judge, doc, item_id, fraction, comparison, reason, lines, object_key, section, rule="N01"):
    obs = f"obs.{item_id}"
    if comparison == "missing":
        state = doc.req_state if section == "requests" else doc.rea_state
        judge.observe(obs, "confirmed_missing", [doc.section_loc(section, object_key, obs, state)])
        judge.positive(item_id, 0.0, obs, reason, "missing")
        return
    if comparison == "ambiguous":
        evidence = [doc.loc(line, object_key, "candidate_span", obs) for line in {l["locator"]: l for l in lines}.values()]
        judge.observe(obs, "ambiguous", evidence or [doc.section_loc(section, object_key, obs, "ambiguous")])
        judge.positive(item_id, 0.0, obs, reason, "different")
        return
    observe_lines(judge, doc, obs, lines, object_key, "proposition_span", rule)
    judge.positive(item_id, fraction, obs, reason, comparison)


def settle(judge, doc, item_id, object_key, section, best, best_lines, conflicts, full_reason, partial_reason, rule="N01"):
    if conflicts and best == 0:
        return credit(judge, doc, item_id, 0, "ambiguous", "proposition asserted together with its contrary", conflicts, object_key, section)
    if best == 1.0:
        mode = judge.positives[item_id]["comparison_mode"]
        return credit(judge, doc, item_id, 1.0, "exact" if mode == "exact" else "equivalent", full_reason, best_lines, object_key, section, rule)
    if best > 0:
        return credit(judge, doc, item_id, best, "partial", partial_reason, best_lines, object_key, section, rule)
    return credit(judge, doc, item_id, 0, "missing", "proposition not asserted in any local span", [], object_key, section)


def decide_requests(judge, doc, item_id, object_key, scorer, full_reason, partial_reason, conflict=None):
    """R06 for the request section: each request line is one local span; an over-scope request line blocks credit."""
    if doc.req_state != "identified":
        if doc.req_state == "ambiguous":
            return credit(judge, doc, item_id, 0, "ambiguous", "several appeal-request headings", doc.req_heads, object_key, "requests")
        return credit(judge, doc, item_id, 0, "missing", "appeal-request section not found", [], object_key, "requests")
    best, best_lines, conflicts = 0.0, [], []
    for line in doc.requests:
        fraction = scorer(line)
        if fraction and conflict and conflict(line):
            conflicts.append(line)
            continue
        if fraction > best:
            best, best_lines = fraction, [line]
    return settle(judge, doc, item_id, object_key, "requests", best, best_lines, conflicts, full_reason, partial_reason)


def decide_reasons(judge, doc, item_id, object_key, scorer, full_reason, partial_reason, conflict=None, ctx=None, rule="N01"):
    """R06 for the reasons section: best local span wins; a span that also adopts the contrary cannot earn."""
    if doc.rea_state != "identified":
        if doc.rea_state == "ambiguous":
            return credit(judge, doc, item_id, 0, "ambiguous", "several facts-and-reasons headings", doc.rea_heads, object_key, "reasons")
        return credit(judge, doc, item_id, 0, "missing", "facts-and-reasons section not found", [], object_key, "reasons")
    best, best_lines, conflicts = 0.0, [], []
    for span in doc.spans:
        if ctx and not ctx.search(span["ctx"]):
            continue
        fraction = scorer(span)
        if fraction and conflict and any(conflict(s["a"]) for s in span["sentences"]):
            conflicts.extend(span["lines"])
            continue
        if fraction > best:
            best, best_lines = fraction, span["lines"]
    return settle(judge, doc, item_id, object_key, "reasons", best, best_lines, conflicts, full_reason, partial_reason, rule)


# ---- D02 over-scope request test (also the P01 conflict) --------------------------------------
QUALIFIER = re.compile(r"中涉及|中关于|中有关|中的|部分|下沉式广场|广场|¥193440|以外|除外")
WHOLE = re.compile(r"#2(?!\d)|第一、二项|第1、2项|全部")


def overscope_clauses(a: str) -> list[str]:
    """R07: a revoke/改判/驳回 clause that reaches the consented G/B interest or the whole judgment."""
    hits = []
    remand = bool(re.search(r"发回(原审(法院)?|一审法院)?重审", a))
    for clause in re.split(r"[,:]", a):
        visible = clause.replace(Q, "")
        if not re.search(r"撤销|驳回|改判|不予支付|无需支付|无须支付|不应支付|不承担", visible):
            continue
        if any(tok in visible for tok in CONSENTED) and not re.search(r"维持|不持异议|同意支付|予以认可|无异议", visible):
            hits.append("consented_interest")
            continue
        if "撤销" in visible and not QUALIFIER.search(visible):
            bare = re.search(r"撤销[^,]{0,30}?(判决|原判)(书)?$", visible)
            if WHOLE.search(visible) or (bare and not remand):
                hits.append("revoke_beyond_plaza")
                continue
        if "驳回" in visible and "诉讼请求" in visible:
            scoped = re.search(r"关于[^,]{0,40}?(下沉式广场|广场|¥193440|¥194970)|(下沉式广场|广场|¥193440|¥194970)[^,]{0,40}?全部诉讼请求", visible)
            if ("全部诉讼请求" in visible and not scoped) or not re.search(r"关于|下沉式广场|广场|¥193440|第一项|工程款|部分|以外|除外", visible):
                hits.append("dismiss_all_claims")
    return hits


def line_overscope(line: dict) -> bool:
    return any(overscope_clauses(s["a"]) for s in line["sentences"])


# ---- P01 revocation scope limited to 下沉式广场 award and its interest --------------------------
REVOKE = re.compile(r"撤销|改判")
PLAZA = re.compile(r"下沉式广场|¥193440")
PRESERVATION_FEE = re.compile(r"(财产)?保全(申请)?费[^。;]{0,12}?¥1543|¥1543[^。;]{0,12}?(财产)?保全(申请)?费")


def eval_p01(judge, doc):
    def score(line):
        best = 0.0
        for s in line["sentences"]:
            a = s["a"]
            if has(REVOKE, a) and has(PLAZA, a):
                core = "利息" in a
                fee = any(has(PRESERVATION_FEE, other["a"]) for line2 in doc.requests for other in line2["sentences"])
                best = max(best, 1.0 if core and fee else 0.5)
        return best
    decide_requests(judge, doc, "P01", "request.revocation_scope", score,
                    "revocation limited to the 下沉式广场 award of 193,440 and its interest",
                    "revocation limited to the 下沉式广场 award without its interest",
                    lambda line: any(line_overscope(other) for other in doc.requests))


# ---- P03 fallback relief: a determinate remand request when the record cannot fix quantity/date ----
P03_REMAND = re.compile(r"(?:撤销|改判)[^。;]{0,30}(?:发回|发还)[^。;]{0,12}(?:重审|审理)|"
                        r"基本事实[^。;]{0,20}(?:不清|未查明)[^。;]{0,20}(?:发回|重审)")
P03_FACT_REMAND = re.compile(r"(?:发回|发还)[^。;]{0,12}(?:重审|审理)[^。;]{0,50}?(?:查明|审查|核实)[^。;]{0,40}?(?:施工范围|工程量|质量|价款|交付时间|交付日期)|"
                              r"(?:施工范围|工程量|质量|价款|交付时间|交付日期)[^。;]{0,50}?(?:不能查明|无法查明|基本事实不清)[^。;]{0,30}?(?:发回|重审)")
P03_QTY = re.compile(r"(按|依|以|根据)(照|据)?[^。;]{0,6}?实际(完成|施工)[^。;]{0,6}?(的)?(工程量|工程|项目|部分)[^。;]{0,10}?(结算|确定|计算|核定|认定)")
P03_INT = re.compile(r"利息[^。;]{0,10}?(自|从)[^。;]{0,12}?(实际交付|交付使用|实际使用|验收合格|@(?:2025|-)-05)[^。;]{0,10}?(之日|时|日)?[^。;]{0,4}?(起算|起计|开始计算|计算|计付)")


def eval_p03(judge, doc):
    def score(line):
        if any(has(P03_FACT_REMAND, s["a"]) for s in line["sentences"]):
            return 1.0
        return 0.5 if any(has(P03_REMAND, s["a"]) for s in line["sentences"]) else 0.0
    decide_requests(judge, doc, "P03", "request.alternative_actual_quantities", score,
                    "request to revoke the unsupported portion and remand for retrial when quantity/date cannot be determined",
                    "direction-only quantity/interest alternative is not a determinate fallback")


# ---- D03 concessions on the merits (P conflicts) -----------------------------------------------
D03_AMOUNT = [
    re.compile(r"(" + APPELLANT + r")[^。;]{0,10}?(应当|应该|理应|应|须|需要)[^。;]{0,12}?(按照?|依照?|以)[^。;]{0,6}?(报价|¥194970|¥193440)[^。;]{0,10}?(支付|结算|付款)"),
    re.compile(r"(以|按照?)[^。;]{0,6}?报价[^。;]{0,10}?(确定|作为)[^。;]{0,10}?(结算价|工程款|结算依据)[^。;]{0,10}?(正确|并无不当|合理|于法有据|无误|恰当)"),
    re.compile(r"(被上诉人|B公司|承包人|原告)[^。;]{0,10}?已经?(全部)?完成[^。;]{0,4}?(了)?(全部|所有)[^。;]{0,10}?(施工|工程|项目)"),
]
D03_DATE = [
    re.compile(r"@(?:2025|-)-04-21[^。;]{0,20}?(为|作为|是)?[^。;]{0,10}?交付[^。;]{0,20}?(正确|并无不当|合理|无误|符合事实|恰当)"),
    re.compile(r"利息[^。;]{0,6}?(应当|应该|应)[^。;]{0,6}?(自|从)@(?:2025|-)-04-21[^。;]{0,6}?(起算|开始计算|计算)"),
]
# The rejection vocabulary that follows a recited finding (缺乏事实依据, 缺乏充分的证据支持, 证据不足) and, in the
# sentence after the recital, 该认定不能成立 / 上述事实…不能证明.
RECT = re.compile(r"错误|不当|失当|不能成立|不成立|缺乏(事实|证据|法律)?(和|与|及)?(事实|法律)?依据|缺乏[^。;,]{0,8}?证据(支持|证明)|证据不足|"
                  r"依据不足|基础不足|矛盾|不符|相悖|不清|站不住脚|有误|难以(相符|成立)")
NEXT_SENTENCE_REJECTS = re.compile(r"^(该认定|上述认定|此认定|该等认定|该推论|该论证|该结论)|^上述事实[^。]{0,10}?不能")
# Three recital frames R02's clause-level ATTRIB cannot see, applied to the D03 text only (the positive items
# keep R02's own view of the sentence):
#  (a) 一审以X为由，认定Y      - the finding clause after a 以…为由 frame belongs to the court
#  (b) 原审关于X的认定        - a nominalised finding
#  (c) …的认定是：X；Y；Z。该认定不能成立 - a colon recital runs to the sentence that turns on it
ATTRIB_FRAME = re.compile(r"(一审|原审|原判)(法院|判决|判决书)?(以|依据|根据|仅凭|基于)[^。;:]{0,40}?(为由|为据|为依据|为基础),?(即|径行|直接|便|就|遂|而)?"
                          r"(认定|确定|判令|判决|推定|支持|驳回)")
ATTRIB_NOUN = re.compile(r"(一审|原审|原判)(法院|判决|判决书)?(关于|对于|对)[^。;,]{0,40}?的(认定|判断|结论|推定)")
RECITAL_OPEN = re.compile(r"(认定|理由|逻辑|推理|依据|结论)(是|为|如下)?:")
RECITAL_CLOSE = re.compile(r"^(该|上述|此|前述|这一)(认定|推论|论证|结论|理由|逻辑|推理|事实)|^(但|但是|然而|可是|事实上|实际上|对此|上诉人认为)")


def drop_attributed(text: str, start: int, verb_end: int) -> str:
    """Blank an attributed span the way R02 does: up to the first rebuttal marker later in the clause, or,
    without one, clause by clause until a clause opens with a turn marker or carries a rebuttal."""
    r = REBUT.search(text, verb_end)
    clause_end = text.find(",", verb_end)
    if r and (clause_end == -1 or r.start() < clause_end):
        return text[:start] + Q + text[r.start():]
    head, tail = text[:start], text[verb_end:]
    clauses = re.split(r"(?<=[,:])", tail)
    kept = []
    for index, clause in enumerate(clauses):
        if index and TURN.match(clause):
            kept.extend(clauses[index:])
            break
        r = REBUT.search(clause)
        if r:
            kept.append(clause[r.start():])
            kept.extend(clauses[index + 1:])
            break
    return head + Q + "".join(kept)


def d03_texts(line: dict) -> list[str]:
    """The D03 view of each sentence of a line: R02's adopted text with the three recital frames removed."""
    out = []
    recital = False
    for s in line["sentences"]:
        a = s["a"]
        canon = s["canon"]
        if recital and (RECITAL_CLOSE.match(canon) or TURN.match(canon)):
            recital = False
        if recital:
            out.append(Q)
            continue
        m = RECITAL_OPEN.search(canon)
        if m:
            recital = True
            cut = a.find(":")
            a = a[:cut + 1] + Q if cut != -1 else Q
        a = ATTRIB_NOUN.sub(Q, a)
        while True:
            m = ATTRIB_FRAME.search(a)
            if not m:
                break
            a = drop_attributed(a, m.start(), m.end())
        out.append(a)
    return out


def rejected_after(text: str, end: int, following: str = "") -> bool:
    """R08: a rejection token in the rest of the matched clause or the next clause (at most 30 characters), or in the
    next sentence when that sentence opens by turning on the recital (该认定不能成立, 上述事实…不能证明)."""
    window = ",".join(text[end:].split(",")[:2])[:30]
    if any(not re.search(r"(并无|没有|无|不存在|并非|不是)$", window[max(0, m.start() - 3):m.start()]) for m in RECT.finditer(window)):
        return True
    if following and NEXT_SENTENCE_REJECTS.match(following):
        return bool(RECT.search(following[:30]) or re.match(r"^上述事实[^。]{0,10}?不能", following))
    return False


def concession_hits(a: str, groups=("amount", "date"), following: str = "") -> list[str]:
    hits = []
    table = {"amount": D03_AMOUNT, "date": D03_DATE}
    for group in groups:
        for pattern in table[group]:
            if any(not rejected_after(a, m.end(), following) for m in adopted_matches(pattern, a, object_bound=False)):
                hits.append(group)
                break
    return hits


def concedes_amount(a: str) -> bool:
    return bool(concession_hits(a, ("amount",)))


def concedes_date(a: str) -> bool:
    return bool(concession_hits(a, ("date",)))


# ---- P04 quotation is not settlement; transaction habit / no contract or settlement ----------
# Equivalent phrasings of the same proposition: 不能当然取代…结算, 混同了“施工报价”与“最终结算价”, 将…报价直接作为/认定为
# 最终结算价…认定不清, 与…交易惯例不一致, 合作惯例.
# The reverse decision (报价可以作为结算依据) earns nothing: every limb keeps its negation or its error verdict.
P04_A = re.compile(r"报价(清单)?[^。;]{0,16}?(不能|不应|不得|并不|不|无法)(当然|直接|简单)?(等同于?|等于|视为|作为|代替|替代|取代|当然成为)[^。;]{0,16}?(结算|结算价|结算结果|结算金额|结算依据)|"
                   r"(?<![应可得])(?<!应当|可以|有权)以报价(确认)?[^。;]{0,4}?(替代|代替|取代)[^。;]{0,4}?结算|报价[^。;]{0,6}?(并非|而非|不是|不等于|不同于|有别于|区别于)[^。;]{0,12}?结算|混淆(了)?报价(清单)?(与|和)结算|"
                   r"(混淆|混同)(了)?[^。;]{0,6}?报价[^。;]{0,12}?(与|和)[^。;]{0,8}?结算|"
                   r"报价[^。;]{0,40}?结算[^。;]{0,30}?(二者|两者)(不能|不应|不可)(等同|混同)|"
                   r"(将|把)[^。;]{0,10}?报价[^。;]{0,6}?(等同于?|视为|当作|作为|认定为|确定为)[^。;]{0,10}?结算[^。;]{0,60}?(?<!并无)(?<!并非)(?<!没有)(?<!无)(错误|不当|缺乏依据|混淆|混同|有误|认定不清|事实不清)|"
                   r"报价[^。;]*?(不能|不足以|不当然|并非|不是|不等于)[^。;]*?(最终)?结算")
P04_B = re.compile(r"(交易习惯|合作习惯|交易惯例|合作惯例|交易模式|合作方式)[^。;]{0,40}?(先施工|相悖|不符|违背|矛盾|施工完成后|不一致|相抵触|抵触)|"
                   r"(未|没有|既未|并未|从未|均未|亦未|也未)[^。;]{0,10}?签订[^。;]{0,20}?(施工合同|结算协议|结算书|结算单|合同)|"
                   r"(未|没有|并未|从未|亦未|也未|既未)(进行|办理|完成)?(过)?结算")


def eval_p04(judge, doc):
    def score(span):
        a_hit = any(has(P04_A, s["a"]) for s in span["sentences"])
        b_hit = any(has(P04_B, s["a"]) for s in span["sentences"])
        return 1.0 if a_hit and b_hit else 0.5 if a_hit else 0.0
    decide_reasons(judge, doc, "P04", "amount.quotation_not_settlement", score,
                   "quotation is not settlement, contrary to the confirmed habit of contract and settlement after works",
                   "quotation is not settlement without the habit/no-settlement limb", concedes_amount,
                   re.compile(r"下沉式广场|广场|报价"))


# ---- P05 'no objection' finding contradicts the defence; actual scope not examined -----------
P05_CONTRA = re.compile(r"异议[^。;]{0,40}?(相互矛盾|自相矛盾|矛盾|明显不符|不符|相悖)|(矛盾|不符|相悖)[^。;]{0,30}?异议")
P05_UNEX = re.compile(r"(未|没有|并未|均未|既未|亦未|未予|未能)(予以)?(查明|审查|审理|核实|回应|调查|查清)[^。;]{0,30}?(施工(项目)?范围|实际(完成|施工)|工程量|第三方|收尾|未施工|施工项目)|"
                      r"(施工(项目)?范围|实际(完成|施工)的?(工程|项目|范围)?|工程量|未施工|第三方[^。;]{0,6}?收尾)[^。;]{0,30}?(未|没有|并未|未予)(予以)?(查明|审查|查清|核实)|"
                      r"(未|没有|并未|均未|既未|亦未)(组织|进行)(任何)?(的)?(实际)?(工程量|施工范围|完成量)(的)?(核对|核实|核查|审查|鉴定)|"
                      r"(未充分查明|未作出明确认定|未对[^。;]{0,20}?作出具体说明|跳过[^。;]{0,12}?(核对|核验))[^。;]{0,35}?(施工(项目)?范围|实际(完成|施工)|工程量|第三方|收尾|未施工|施工项目)|"
                      r"(施工(项目)?范围|实际(完成|施工)|工程量|第三方|收尾|未施工|施工项目)[^。;]{0,35}?(未充分查明|未作出明确认定|未作具体说明|跳过[^。;]{0,12}?(核对|核验))")


def eval_p05(judge, doc):
    def score(span):
        contra = any(has(P05_CONTRA, s["a"]) and re.search(r"未施工|第三方|收尾|答辩|抗辩|辩称|施工范围|提出", s["a"]) for s in span["sentences"])
        unex = any(has(P05_UNEX, s["a"]) for s in span["sentences"])
        return 1.0 if contra and unex else 0.5 if contra or unex else 0.0
    decide_reasons(judge, doc, "P05", "amount.defence_ignored_scope_unexamined", score,
                   "the 'no objection' finding contradicts the recorded defence and the actual scope was not examined",
                   "only one limb (contradiction or unexamined scope)", concedes_amount,
                   re.compile(r"下沉式广场|广场|报价|施工|工程款"))


# ---- the admitted value of the completed work (7-8万), as N02 writes the range ---------------
ADMITTED_RANGE = re.compile(r"¥7\d{4}~¥8\d{4}|¥70000~¥80000")


# ---- P09 4-21 delivery presumption unsupported; 4-16 chat shows unfinished door/window -------
# The contract's P09 relation_predicate names 不符/依据不足/错误 as examples of the rejection, not as the
# closed list; these are the equivalent ways one span rejects the court's 2025-04-21 delivery finding.
MISMATCH = r"(不符|不相符|难以相符|并不相符|不一致|矛盾|相悖|抵触|冲突|依据不足|基础不足|证据不足|缺乏证据|缺少证据|不能证明|无法证明|不能支撑|无法支撑|不足以支撑|不能并存|不能同时成立|不能成立|并不存在|错误|不当|不成立|缺乏(事实)?依据|没有依据|有误)"
# A rejection may also precede the date ("利息起算日亦不应为2025年4月21日"); the rejection and the date
# still have to sit in the same sentence.
P09_REJ_BEFORE = r"(不应|不能|不得|不宜|难以)[^。;]{0,6}?(为|是|认定为|确定为|定为|采用|采信|作为|早于)"
P09_DATE = re.compile(r"@(?:2025|-)-04-21[^。;]{0,40}?" + MISMATCH + r"|(推定|认定|确定)[^。;]{0,20}?@(?:2025|-)-04-21[^。;]{0,30}?" + MISMATCH
                      + r"|" + P09_REJ_BEFORE + r"[^。;]{0,6}?@(?:2025|-)-04-21")
P09_CHAT = re.compile(r"(折叠门|下拉窗)[^。;]{0,20}?(均?未完成|未安装|尚未|要?等几天|仍需|仍未|没有完成|未完工)")


def eval_p09(judge, doc):
    def score(span):
        date = any(has(P09_DATE, s["a"]) and re.search(r"交付|利息|起算", s["a"] + span["ctx"]) for s in span["sentences"])
        chat = any(has(P09_CHAT, s["a"]) for s in span["sentences"])
        return 1.0 if date and chat else 0.5 if date else 0.0
    decide_reasons(judge, doc, "P09", "interest.delivery_date_unsupported", score,
                   "2025-04-21 delivery presumption contradicts the 04-16 chat that door and window were unfinished",
                   "2025-04-21 delivery finding rejected without the chat facts", concedes_date,
                   re.compile(r"交付|利息|起算"))


# ---- P11 interest from delivery/acceptance about May 2025 per Interpretation (I) art.27/9 ----
P11_START = re.compile(r"@(?:2025|-)-05(?:-\d\d)?[^。;]{0,40}?利息[^。;]{0,20}?(起算|起计|计付|开始计算|计算)|利息[^。;]{0,20}?(自|从)@(?:2025|-)-05(?:-\d\d)?[^。;]{0,16}?(起算|起计|计付|开始计算|计算)")
P11_RULE = re.compile(r"(建设工程施工合同纠纷案件适用法律问题的解释\((一|1)\)|建工(司法)?解释\((一|1)\)|(建设工程)?司法解释\((一|1)\)|法释〔2020〕25号|法释\[2020\]25号)[^。;]{0,20}?§(27|9)(?!\d)|交付之日[^。;]{0,10}?(起算|开始计付|计付|起计)")


def eval_p11(judge, doc):
    def score(span):
        start = any(not re.search(r"不应|不能|不得|并非|不是|无需", m.group(0))
                    for s in span["sentences"] for m in adopted_matches(P11_START, s["a"]))
        rule = any(has(P11_RULE, s["a"], object_bound=False) for s in span["sentences"])
        verified = any(re.search(r"(实际|查明|核实|确认)[^。;]{0,22}?(交付|移交)|交付[^。;]{0,22}?(查明|核实|确认)", s["a"]) for s in span["sentences"])
        distinction = any(re.search(r"验收[^。;]{0,35}?(不等于|不能等同|未必|尚需|不当然|并不当然)|交付[^。;]{0,35}?(核实|查明|证明|证据)", s["canon"]) for s in span["sentences"])
        return 1.0 if rule and (verified or (start and distinction)) else 0.5 if start or verified else 0.0
    decide_reasons(judge, doc, "P11", "interest.actual_delivery_verified", score,
                   "interest runs from verified actual delivery; May acceptance alone does not establish the handover date",
                   "May 2025 start stated without the legal rule", concedes_date, re.compile(r"交付|利息|验收"),
                   rule="N05")


# ---- P13 burden of proving completion lies on the appellee; the court shifted it / photos cannot prove it ----
# Golden p[23]-p[24] and its equivalent phrasings (举证责任 / 举证证明责任 / 证明责任; 转移/转由/倒置/减轻/免除;
# 主张工程款的一方…所负的证明责任). Only body lines count - a heading such
# as 「举证责任分配失当」 earns nothing - and each limb is bound to the completion object (完成/工程量/施工
# 范围/清单所列…), so a burden argued only about the price agreement or the delivery date is a different
# proposition and earns nothing here.
BURDEN = r"(举证(证明)?|证明)责任"
P13_OBJ = re.compile(r"完成|完工|工程量|施工范围|实际施工|施工内容|工作内容|履行内容|施工项目|报价项目|清单所列|全部项目|全部工程|实际履行")
P13_OTHER_OBJ = re.compile(r"交付|起算|利息|合意|价款约定")
P13_BEARER = r"(" + APPELLEE + r"|其|施工方|(主张|请求)[^。;,]{0,16}?一方)"
MODAL = r"(应当|应该|理应|应|须|负有)"
P13_ALLOC = re.compile(P13_BEARER + r"[^。;]{0,60}?" + MODAL + r"[^。;]{0,60}?(承担|负担|负)?[^。;]{0,4}?" + BURDEN + r"|"
                       + MODAL + r"(就|对)[^。;]{0,60}?(承担|负担|负)[^。;]{0,4}?" + BURDEN + r"|"
                       + BURDEN + r"[^。;]{0,10}?(应当|应)?[^。;]{0,4}?(由|在)(" + APPELLEE + r")|"
                       + P13_BEARER + r"[^。;]{0,60}?所负的?" + BURDEN + r"|"
                       r"(本应|应当|应)由(" + APPELLEE + r")[^。;]{0,6}?承担的" + BURDEN + r"|"
                       r"(减轻|免除)(了)?(" + APPELLEE + r")[^。;]{0,30}?的?" + BURDEN + r"|"
                       + BURDEN + r"[^。;]{0,12}?(转由|转移给|转嫁给|转给|转至|倒置给)(" + APPELLANT + r")|"
                       r"(证明|举证)[^。;]{0,24}?(的)?责任[^。;]{0,6}?(转由|转移给|转嫁给)(" + APPELLANT + r")")
P13_SHIFT = re.compile(BURDEN + r"[^。;]{0,12}?(转移|转由|转嫁|倒置|转给|转至|转而由)|"
                       r"(转移|转嫁|倒置)(了)?" + BURDEN + r"|"
                       r"(减轻|免除|变相免除)(了)?[^。;]{0,30}?" + BURDEN + r"|"
                       r"举证(证明)?责任(的)?分配(错误|不当|失当|倒置)|"
                       r"(证明|举证)[^。;]{0,24}?(的)?责任[^。;]{0,6}?(转由|转移给|转嫁给)")
P13_PHOTO = re.compile(r"照片[^。;]{0,40}?(仅能|只能|不足以|不能|无法)(当然|完整)?(证明|反映|替代|等同)")
P13_ALL = re.compile(r"全部|所有|清单|各分项|每一|隐蔽|均已")
APPELLANT_RE = re.compile(APPELLANT)
# R04 for P13: NEG_BEFORE does not list 并未/未, and the shift is usually a 将…转移 construction whose
# negation sits at the head of the clause (原审并未将…举证责任转移给上诉人).
P13_NEG = re.compile(r"(并未|未曾|从未|没有|并没有|未|并非|不是|并无|不存在)(将|把)|(并未|未曾|从未|没有|并没有|未)$")


def p13_negated(a: str, m: re.Match) -> bool:
    clause_pre = a[max(a.rfind(",", 0, m.start()), a.rfind(":", 0, m.start())) + 1:m.start()]
    return bool(P13_NEG.search(clause_pre))


def p13_bound(a: str, m: re.Match, span_object: bool = False) -> bool:
    """R05-style object binding for P13: the completion object sits in or right around the match, and a
    burden whose own object is the delivery date or the price agreement (交付事实的举证责任) is not it.
    With span_object, a shift sentence may take its object from the allocation sentence of the same span
    (「应就其已完成的工程量…承担举证责任 … 将本应由被上诉人承担的举证责任转由上诉人承担」)."""
    if P13_OBJ.search(m.group(0)):
        return True
    burden = re.search(BURDEN, m.group(0))
    lead = a[max(0, m.start() + (burden.start() if burden else 0) - 12):m.start() + (burden.start() if burden else 0)]
    if P13_OTHER_OBJ.search(lead):
        return False
    return span_object or bool(P13_OBJ.search(a[max(0, m.start() - 24):m.end() + 24]))


def p13_alloc(a: str) -> bool:
    """The appellee (or the party claiming the price) bears the burden on completion. A clause whose own
    subject before the modal is the appellant (上诉人应当承担举证责任) is the contrary allocation."""
    for m in adopted_matches(P13_ALLOC, a):
        if p13_negated(a, m):
            continue
        modal = re.search(MODAL, m.group(0))
        if modal:
            at = m.start() + modal.start()
            pre = a[a.rfind(",", 0, at) + 1:at]
            if APPELLANT_RE.search(pre) and not re.search(APPELLEE, pre):
                continue
        if p13_bound(a, m):
            return True
    return False


def p13_shift(a: str, span_object: bool = False) -> bool:
    return any(not p13_negated(a, m) and p13_bound(a, m, span_object) for m in adopted_matches(P13_SHIFT, a))


def p13_photo(a: str) -> bool:
    return has(P13_PHOTO, a) and bool(P13_ALL.search(a)) and bool(P13_OBJ.search(a))


def eval_p13(judge, doc):
    def score(span):
        body = [s["a"] for line in span["lines"] if not line.get("level") for s in line["sentences"]]
        alloc = any(p13_alloc(a) for a in body)
        second = any(p13_shift(a, alloc) or p13_photo(a) for a in body)
        return 1.0 if alloc and second else 0.5 if alloc or second else 0.0
    decide_reasons(judge, doc, "P13", "amount.completion_burden_shifted", score,
                   "the appellee bears the burden of proving completion of the quoted items, and the court shifted it by presumption or photos cannot carry it",
                   "only one limb (the appellee's burden on completion, or the court's shifting / the photos' insufficiency)",
                   concedes_amount, re.compile(r"下沉式广场|广场|报价|施工|工程款"))


# ---- P14 quality defence rejected without substantive examination; quality bears on the price ------
# Golden p[34]-p[35] (既未审查质量问题是否存在 … 质量问题如成立,依法影响工程价款的支付, 原审对该项抗辩未予
# 实质审理即径行否定) and its equivalent phrasings (未就质量瑕疵…作任何查明, 未就质量争议组织鉴定, 质量…抗辩,
# 一审未予实质审理, 质量抗辩…径行驳回, 有权请求减少价款). Body lines only.
P14_UNEX = re.compile(r"质量[^。;]{0,30}?(未(予|作|经|进行)?实质(性)?(审理|审查)|(未|没有)(予|作|经)?(审查|审理|查明)|未作任何(查明|审查|认定)|未予回应|回应不全|一笔带过|"
                      r"(径行|直接|简单|一概)[^。;]{0,16}?(否定|驳回|排除|不予认定)|未(组织|委托)[^。;]{0,6}?(鉴定|勘验|质证))|"
                      r"(未(予|作|经|进行)?实质(性)?(审理|审查)|(未|没有)(予|作|经)?(审查|审理|查明))[^。;,]{0,20}?质量|"
                      r"(未|没有|并未)(对|就)[^。;,]{0,12}?质量[^。;]{0,30}?(进行|予以|作|组织|委托)?(任何)?(实质)?(审查|审理|查明|调查|鉴定|勘验)")
P14_EFFECT = re.compile(r"质量[^。;]{0,30}?(影响|抵扣|扣减|减少|直接关系|关系到)[^。;]{0,10}?(价款|工程款|付款|支付|报酬)|"
                        r"(有权|可以|应当|应)[^。;]{0,8}?(请求|要求|主张)?[^。;]{0,4}?(减少|降低|扣减|抵扣)[^。;]{0,4}?(价款|报酬|工程款)")


def eval_p14(judge, doc):
    def score(span):
        body = [s["a"] for line in span["lines"] if not line.get("level") for s in line["sentences"]]
        unex = any(has(P14_UNEX, a) for a in body)
        eff = any(has(P14_EFFECT, a) and re.search(r"质量|瑕疵|不符合约定", a) for a in body)
        return 1.0 if unex and eff else 0.5 if unex else 0.0
    decide_reasons(judge, doc, "P14", "quality.defence_rejected_unexamined", score,
                   "the quality defence was rejected without substantive examination although quality bears on the price",
                   "unexamined quality defence without the price effect", None, re.compile(r"质量"))


# ---- deductions --------------------------------------------------------------------------------
class Deductions:
    def __init__(self, judge: ProgramJudge, doc: Doc):
        self.judge, self.doc, self.counter = judge, doc, 0

    def decide(self, item_id, sections, manifestations, key_fn, root, reason, object_key):
        scans = [f"obs.scan.{s}" for s in sections]
        if not manifestations:
            self.judge.deduction(item_id, "not_triggered", scans, "error proposition not asserted")
            return
        occurrences, obs_ids, seen = [], [], set()
        for lines, detail in manifestations:
            manifestation = f"{item_id}:{lines[0]['locator']}:{detail}"
            if manifestation in seen:
                continue
            seen.add(manifestation)
            self.counter += 1
            obs = observe_lines(self.judge, self.doc, f"obs.{item_id}.m{self.counter}", lines, object_key, "error_span", "N01")
            obs_ids.append(obs)
            occurrences.append({"damage_instance_key": key_fn(detail), "causal_root_id": root, "manifestation_id": manifestation,
                                "observation_id": obs, "reason": detail})
        self.judge.deduction(item_id, "triggered", scans + obs_ids, reason, occurrences)


def sentences_of(lines):
    for line in lines:
        for s in line.get("sentences", []):
            yield line, s


GOLDEN_CLOSING_CHARS = 78   # N09 count of Golden p[37], the one unheaded closing paragraph before 此致
CLOSING_RESTATE_FACTOR = 2   # a closing block past twice Golden's own closing paragraph restates; a heading over Golden p[37] itself is 1.0x
CLOSING_OVERLAP = 0.6


def char_ngrams(text: str, n: int = 3) -> set[str]:
    return {text[i:i + n] for i in range(len(text) - n + 1)}


def closing_restates(doc: Doc, head_index: int) -> str | None:
    """R-closing: the block under a closing heading (to the next heading of the same or a higher level, or
    the end of the reasons) restates the grounds when at least two of its sentences repeat an earlier reasons
    sentence (character 3-gram overlap >= 0.6) or when it runs past twice Golden's closing paragraph.
    A heading over a paragraph equivalent to Golden p[37] is format and never triggers."""
    head = doc.reasons[head_index]
    level = head.get("level") or 1
    body = []
    for line in doc.reasons[head_index + 1:]:
        if line.get("level") and line["level"] <= level:
            break
        body.append(line)
    if not body:
        return None
    count = shape_count(body)
    if count > CLOSING_RESTATE_FACTOR * GOLDEN_CLOSING_CHARS:
        return f"restated-{count}-chars-over-{CLOSING_RESTATE_FACTOR}x{GOLDEN_CLOSING_CHARS}"
    earlier = [char_ngrams(s["canon"]) for line in doc.reasons[:head_index] for s in line.get("sentences", []) if len(s["canon"]) >= 12]
    restated = 0
    for line in body:
        for s in line.get("sentences", []):
            grams = char_ngrams(s["canon"]) if len(s["canon"]) >= 12 else set()
            if grams and max((len(grams & e) / len(grams) for e in earlier), default=0.0) >= CLOSING_OVERLAP:
                restated += 1
    if restated >= 2:
        return f"restated-{restated}-sentences"
    return None


def shape_count(lines: list[dict]) -> int:
    """N09: non-whitespace characters of measured lines (punctuation , ; 。 excluded), skipping clauses with a gap token."""
    total = 0
    for line in lines:
        for clause in re.split(r"[,;。]", n06_gap(line["clean"])):
            if GAP not in clause:
                total += len(clause)
    return total


def shape_groups(doc: Doc):
    """R10: reasons lines grouped by their level-1 heading; the first keyword decides amount vs interest/quality."""
    if not any(l.get("level") == 1 for l in doc.reasons):
        return None
    groups = {"amount": [], "interest": []}
    unclassified: dict[str, list] = {}
    for line in doc.reasons:
        head = line.get("l1")
        if head is None:
            continue
        canon = head["canon"]
        p, q = AMOUNT_KW.search(canon), INTEREST_KW.search(canon)
        if p and (not q or p.start() < q.start()):
            groups["amount"].append(line)
        elif q:
            groups["interest"].append(line)
        else:
            unclassified.setdefault(head["locator"], []).append(line)
    if any(shape_count(v) > 150 for v in unclassified.values()):
        return None
    return groups


INCLUSION_FRAME = re.compile(r"计入|包含|含于|总额|总价|合计|之中|其中|以内|范围内")
PAY_MORE = re.compile(r"(判令|改判)[^。;]{0,10}?(D公司|(?<!被)上诉人)[^。;]{0,12}?(支付|给付)[^。;]{0,20}?(工程款|装修款|利息)")
# R02 for the request section: the appealed disposition recited right after the judgment reference it is
# attached to (no clause boundary in between) is attributed text, not an adopted request.
RECITED_DISPOSITION = re.compile(r"(撤销|变更|发回|不服|驳回)[^。;,:]{0,24}(判决|判项|原判|主文)[^。;,:]{0,10}$")


# D11/D12: content the petition appends beyond the operative filing the instruction asks for.
# N01 has already stripped Markdown marks, whitespace and folded punctuation to ASCII.
CLOSING_HEAD = re.compile(r"^(第?[一二三四五六七八九十]{1,3}\s*[、.)]\s*)?(结语|结束语|结论|综上|综上所述|小结)\s*:?$")
ATTACH_HEAD = re.compile(r"^(附件|附录|附|随附材料|随附文件|证据(清单|目录|材料))\s*:?")
ENTRY_NUM = re.compile(r"^(\(?[0-9一二三四五六七八九十]{1,3}\)?\s*[、.)])\s*")
OWN_COPY = re.compile(r"上诉状(的)?(副本|复印件)|本状副本")
ENCLOSURE_NOUN = re.compile(r"[0-9一二三四五六七八九十]{1,3}(份|套|册|本|页)|复印件|副本|原件|清单|目录|材料|证据|附件")


# D13: a legal basis bound to the wrong article, or a legal basis the judgment never relied on but the petition
# says the court applied. Everything here is read on the canonical line (N05 has folded article numbers to §N),
# one 。-sentence at a time so that a citation such as 第九条、第二十七条 followed by both propositions
# (…竣工日期；…利息自交付之日开始计付) stays one unit.
STATUTE_RE = re.compile(r"(?P<interp1>建设工程施工合同纠纷案件适用法律问题的解释|建工(司法)?解释|建设工程施工合同司法解释|解释\((一|1)\)|法释(〔|\[)2020(〕|\])25号)"
                        r"|(?P<cpl_interp>适用[〈《]?(中华人民共和国)?民事诉讼法[〉》]?的解释|民诉(法)?解释)"
                        r"|(?P<cpl>民事诉讼法|民诉法)"
                        r"|(?P<civil>民法典)")
ART_TOKEN = re.compile(r"§(\d+)")
# proposition -> the articles the judgment's appendix / Golden bind it to (statute by statute). Kept to the
# propositions whose article is settled by the appendix text or by Golden; anything outside the table is never
# read as a mis-citation.
PROPOSITION_ARTICLES = {
    "interp1": [
        (re.compile(r"竣工日期|竣工验收合格之日|转移占有"), {9}),
        (re.compile(r"擅自使用"), {9, 14}),
        (re.compile(r"利息(计付|计算)?标准|计息标准|同期同类贷款|贷款市场报价利率"), {26}),
        (re.compile(r"利息[^。]{0,16}?(起算|开始计付|计付|起计|开始计算)|应付(工程)?(价)?款(之日|时间|日)|交付之日|起诉之日|(提交)?竣工结算文件之日"), {27}),
        (re.compile(r"工程量有争议|签证"), {20}),
        (re.compile(r"逾期不答复|不予答复|视为认可|结算文件[^。]{0,20}?(答复|认可)"), {21}),
    ],
    "cpl": [
        (re.compile(r"改判|发回重审|认定基本事实不清|基本事实不清|适用法律错误"), {177}),
        (re.compile(r"迟延履行|加倍支付"), {264}),
    ],
    "civil": [
        (re.compile(r"沉默"), {140}),
    ],
}
# D15: drafting notes to the lawyer inside the filing (skill references/filing-types.md: a petition carries no
# notes on deadlines, weaknesses or next steps). D16: the petition contradicts its own client's recorded
# first-instance position (judgment p2 被告辩称: 案涉工程在2025年5月左右验收合格并投入使用; Golden p[12] p[33] argue
# interest from that delivery) by asserting the works were never delivered, by asking for interest from the date of
# suit, or by pleading that the very claim it is appealing has already been satisfied in full and the parties'
# obligations extinguished - the record carries payment of the G/B 硬装 settlement only (judgment p2: 371,750 paid
# twice; Golden 该部分款项已付清) and says nothing about the 下沉式广场 sum being paid, so such a clause both asserts
# a fact the materials do not establish and concedes away the petition's own requests (撤销/改判驳回 193,440 及利息).
# D14: a procedural fact the record does not carry (an appraisal application at first instance).
NOT_FILING_TEXT = re.compile(r"非上诉状正文|不属于上诉状正文|非正文|非本状正文|供(承办)?律师|律师核改|供内部|内部备注")
NOTE_HEAD = re.compile(r"说明|提示|备注|注意事项|核对|注意|Note|待办")
NOTE_BODY = re.compile(r"律师|定稿|提交前|核对|替换|脱敏|填写|补充|建议|复核|核实|删除本")
NOT_DELIVERED = re.compile(r"(未|没有|从未|尚未|并未)(办理|完成|经|进行)?(任何)?(正式)?(的)?(竣工验收[、,]?)?(交付|交接)(?!之日|时间|日期|凭|证|事实|情况|的事实)")
DELIVERY_OBJECT_PART = re.compile(r"(折叠门|下拉窗|显示屏|材料|资料|凭证|文件|记录|单据)[^。;,]{0,12}$")
RULE_STATEMENT = re.compile(r"§\d+|规定|下列时间|视为应付款")
CASE_BOUND = re.compile(r"本案|案涉|下沉式广场|广场工程")
SUIT_DATE_START = re.compile(r"(自|从|以|为)[^。;,]{0,12}?起诉之日|起诉之日[^。;,]{0,8}?(起算|起计|计息|计算|为应付款|作为应付款)")
SUIT_DATE_NEG = re.compile(r"(不应|不能|不得|并非|而非|不是|无需|不宜)[^。;,]{0,10}?起诉之日")
INTEREST_CONTEXT = re.compile(r"利息|计息|起算|应付款|利率")
# D16 third form: the claim is pleaded as already satisfied / the obligations as extinguished. The totality
# quantifier is what separates it from Golden's own true record fact (该部分款项已付清 for the G/B settlement),
# which carries no quantifier and names the paid-off 硬装 objects instead.
CLAIM_SATISFIED = re.compile(r"(全额|足额|悉数|如数|全部|一次性)[^。;,]{0,6}?(清偿完毕|清偿|付清|结清|偿付|支付完毕|给付完毕|履行完毕)|"
                             r"(债权债务|债务关系|债权债务关系)[^。;,]{0,10}?(消灭|终止|了结|清结)")
SATISFIED_OBJECT = re.compile(r"本案|案涉|下沉式广场|广场工程|¥193440|债权债务|债务关系|(全部|所有|悉数)[^。;,]{0,2}?(款项|工程款|价款|债务|债权)")
SATISFIED_DONE = re.compile(r"已|业已|早已|均已|完毕|了结|清结")
SATISFIED_NEG = re.compile(r"(未|没有|无|非|不|是否|若|如|拟|将|应|须|需|请求|要求|能否)[^。;,]{0,2}$")
SATISFIED_INNER_NEG = re.compile(r"未|没有|无|非|不|是否")
CONDITIONAL_OPEN = re.compile(r"^(如果|如|若|倘若|倘|假如|假设|即使|即便|纵使|哪怕|一旦|除非|退一步|设若|万一)(?!前述|前所述|上述|上所述|此|实)")
APPRAISAL_NOUN = re.compile(r"(对|就|针对)?(?<!被)(上诉人|我方|D公司)(在一审中|一审|原审|于一审)?(提出|提交)?的?鉴定申请")
APPRAISAL_VERB = re.compile(r"(?<!被)(上诉人|我方|D公司)(在一审中|一审|原审|于一审|已|曾|明确|书面|亦|也){0,3}(提出|提交|申请)(了|过)?[^。;,]{0,8}?鉴定")
APPRAISAL_NEG = re.compile(r"(未|没有|并未|从未|亦未|是否|尚未|不曾|拟|建议|将|应当|应|可以|请求)$")


def own_clauses(line: dict) -> list[str]:
    """R02-lite for D16/D14: the line's 。-sentences that are not bare rule statements, split into clauses; in the
    reasons section a clause opening with a concessive/conditional marker is dropped (the alternative request in
    the request section is the appellant's own adopted request and stays); attributed clauses are dropped."""
    out = []
    for sentence in line["quoted"].split("。"):
        if RULE_STATEMENT.search(sentence) and not CASE_BOUND.search(sentence):
            continue
        for clause in re.split(r"(?<=[,:;])", sentence):
            if line.get("zone") == "reasons" and CONCESSIVE.match(clause):
                continue
            m = ATTRIB.search(clause)
            if m and not re.search(r"不|未|没有|并非", m.group("gap")):
                continue
            out.append(clause)
    return out


# the legal bases the first-instance judgment actually invoked (judgment p4 综上，依照…; p5 迟延履行 §264)
COURT_RELIED_ON = {"civil": {577, 579}, "interp1": {9, 26, 27}, "cpl": {264}, "cpl_interp": set()}
COURT_APPLIED = re.compile(r"(一审|原审)(法院|判决|判决书)?(所|正是|径行|直接|也|又|已)?(援引|适用|依据|依照|引用|援用|运用)(了|的)?")
COURT_APPLIED_NOT = re.compile(r"(应当|应|本应|理应|未|并未|没有|拒绝|规避|不|可|须|需|得|错误地)$")
EVALUATIVE = re.compile(r"实质(上)?(是|为)|相当于|等于|无异于|变相|实际上(是|系)|等同于|同于")
REF_ARTICLE = re.compile(r"§(\d+)|该条(?!聊天|记录|证据|微信|款项|信息)|该项|该款|该解释|上述规定|该规定|前述规定|上述条文")
APPELLEE_CLAIM_DEEMED = re.compile(r"(被上诉人|原告|B公司)[^。;]{0,16}?(主张|诉称|称|辩称|认为|提出)[^。]{0,60}?(未答复|未予答复|未提出异议|未提出不同意见|未置可否|未回复|不予答复)"
                                   r"[^。]{0,12}?(故|即|则|因此|就)?(应|即|应当)?视为(认可|同意|接受|承诺|确认)")


def cited_articles(sentence: str) -> list[tuple[str, int, int]]:
    """(statute, article, position) for every §N that follows a statute name in this sentence, the statute being the
    nearest name before it (a new 《 or another statute name closes the scope)."""
    out = []
    matches = list(STATUTE_RE.finditer(sentence))
    for index, m in enumerate(matches):
        statute = m.lastgroup
        end = matches[index + 1].start() if index + 1 < len(matches) else len(sentence)
        stop = sentence.find("《", m.end())
        if stop != -1:
            end = min(end, stop)
        for a in ART_TOKEN.finditer(sentence, m.end(), end):
            out.append((statute, int(a.group(1)), a.start()))
    return out


def law_miscites(sentence: str) -> list[str]:
    """D13(a): a proposition the appendix binds to a known article is cited under another article of the same
    statute - a substitution, not an extra citation: the sentence states a tabled proposition whose article is
    not cited at all, and it cites an article of that statute that none of its tabled propositions explains.
    Citing 第九条、第二十七条 for a delivery-based interest start is therefore never charged (art.27 is there,
    art.9 is the judgment's own companion citation); 第九条、第二十六条 for the same proposition is."""
    hits = []
    cited = cited_articles(sentence)
    for statute in {c[0] for c in cited}:
        table = PROPOSITION_ARTICLES.get(statute)
        if not table:
            continue
        articles = {c[1] for c in cited if c[0] == statute}
        if statute == "cpl":
            articles -= {169, 170}  # D07 already charges the superseded numbering
        allowed: set = set()
        missing = False
        for pattern, expected in table:
            if pattern.search(sentence):
                allowed |= expected
                if not articles & expected:
                    missing = True
        if not allowed or not missing:
            continue
        for article in sorted(articles - allowed):
            hits.append(f"miscite:{statute}:§{article}")
    return hits


def law_misattributions(line_canon: str) -> list[str]:
    """D13(b): the petition says the first-instance court applied/relied on an article the judgment never invoked."""
    hits = []
    seen_articles: list[tuple[str, int]] = []
    for sentence in line_canon.split("。"):
        cited = cited_articles(sentence)
        for m in COURT_APPLIED.finditer(sentence):
            pre = sentence[max(0, m.start() - 4):m.start()]
            if COURT_APPLIED_NOT.search(pre):
                continue
            clause_start = max(sentence.rfind(",", 0, m.start()), sentence.rfind(":", 0, m.start())) + 1
            clause_end = min([x for x in (sentence.find(",", m.end()), sentence.find(":", m.end()), len(sentence)) if x != -1])
            if EVALUATIVE.search(sentence[clause_start:clause_end]):
                continue
            window = sentence[m.end():m.end() + 60]
            ref = REF_ARTICLE.search(window)
            if not ref:
                continue
            if ref.group(1):
                at = m.end() + ref.start()
                before = [c for c in cited if c[2] <= at]
                statute = before[-1][0] if before else None
                article = int(ref.group(1))
            else:
                at = m.end() + ref.start()
                before = [c for c in cited if c[2] <= at]
                if before:
                    statute, article = before[-1][0], before[-1][1]
                elif seen_articles:
                    statute, article = seen_articles[-1]
                else:
                    continue
            if statute is None or statute not in COURT_RELIED_ON:
                continue
            if article in COURT_RELIED_ON[statute]:
                continue
            hits.append(f"misattributed:{statute}:§{article}")
        seen_articles.extend((statute, article) for statute, article, _ in cited)
    return hits



def eval_deductions(judge: ProgramJudge, doc: Doc) -> None:
    d = Deductions(judge, doc)
    body = doc.intro + doc.requests + doc.reasons

    # D01 party roles inverted
    found = []
    for line in doc.header + doc.intro:
        m = PARTY_LABEL.match(line["quoted"])
        if not m:
            continue
        label, value = m.group(1), re.split(r"[,(]", m.group(3), maxsplit=1)[0]
        if re.match(r"^(不是|并非|非)", value):
            continue
        ents = set(re.findall(r"([BD])公司", value))
        if label in ("上诉人", "原审原告", "一审原告") and "B" in ents and "D" not in ents:
            found.append(([line], f"{label}-B"))
        if label in ("被上诉人", "原审被告", "一审被告") and "D" in ents and "B" not in ents:
            found.append(([line], f"{label}-D"))
        if label == "上诉人" and m.group(2) and "原告" in m.group(2):
            found.append(([line], "appellant-as-plaintiff"))
    for line, s in sentences_of(doc.requests):
        if re.search(r"不|无需|无须|驳回", s["a"]):
            continue
        for m in adopted_matches(PAY_MORE, s["a"], False):
            # A payment order recited inside the request that asks to revoke it ("撤销一审判决第一项
            # (判令上诉人支付…)") is the disposition under appeal, not the appellant's own request.
            if RECITED_DISPOSITION.search(s["a"][:m.start()]):
                continue
            found.append(([line], "request_increases_payment"))
            break
    d.decide("D01", ["header", "intro", "requests"], found, lambda _: "party_role_inverted", "R-role",
             "petition drafted from the plaintiff's side (roles inverted or asks the defendant to pay)", "party.roles")

    # D02 appeal scope reaches consented G/B interest or the whole judgment
    found = []
    for line, s in sentences_of(doc.requests):
        for hit in overscope_clauses(s["a"]):
            found.append(([line], hit))
    for line, s in sentences_of(doc.reasons):
        a = s["a"]
        if any(tok in a for tok in CONSENTED) and "利息" in a and re.search(r"(不应|无需|无须|不予|不承担|不负)[^。;]{0,8}?(支付|给付|承担)", a):
            if not re.search(r"同意|认可|无异议|不持异议|不上诉|不在上诉范围", a):
                found.append(([line], "body_disputes_consented_interest"))
    d.decide("D02", ["requests", "reasons"], found, lambda _: "scope_overreach", "R-scope",
             "appeal reaches the G/B interest the defendant agreed to pay, or the whole judgment", "request.scope")

    # D03 concessions on the merits (recital frames removed, next-sentence rejection honoured)
    found = []
    for line in body:
        texts = d03_texts(line)
        canons = [s["canon"] for s in line.get("sentences", [])]
        for index, text in enumerate(texts):
            following = canons[index + 1] if index + 1 < len(canons) else ""
            for hit in concession_hits(text, following=following):
                found.append(([line], hit))
    d.decide("D03", ["intro", "requests", "reasons"], found, lambda detail: f"concede_{detail}", "R-concession",
             "adopts the plaintiff/court position on the award, full completion or the 2025-04-21 delivery date", "merits.concession")

    # D04 misstated record facts
    found = []
    for line, s in sentences_of(body):
        # record figures are judged on the canonical sentence: attributing a figure to the court is the claim itself
        a = s["canon"] if not CANDIDATE.search(s["canon"]) else ""
        for m in re.finditer(r"(判决|判令|原审|一审|法院)[^。;]{0,20}?(认定|确定|判令|判决|支持)[^。;¥]{0,24}?(工程款|装修款|结算价)[^。;¥]{0,8}?(¥[\d.]+)", a):
            value = m.group(4)
            if value != AWARD and not (value == QUOTE_TOTAL and "报价" in a) and re.search(r"下沉式广场|广场|第一项", a):
                try:
                    if Decimal(value[1:]) >= 10000:
                        found.append(([line], f"award:{value}"))
                except InvalidOperation:
                    pass
        for m in re.finditer(r"(自认|陈述|辩称|认可|承认)[^。;]{0,40}?(¥[\d.]+)~(¥[\d.]+)", a):
            if not ADMITTED_RANGE.search(m.group(2) + "~" + m.group(3)):
                found.append(([line], f"admission:{m.group(2)}~{m.group(3)}"))
        for m in re.finditer(r"(原审|一审|判决|法院)[^。;]{0,20}?(确定|认定|推定)[^。;]{0,10}?@(?:2025|-)-04-(\d\d)[^。;]{0,10}?交付", a):
            if m.group(3) != "21":
                found.append(([line], f"delivery:04-{m.group(3)}"))
        for m in re.finditer(r"折叠门[^。;¥]{0,16}?(安装费|人工费?|费用|价款)[^。;¥]{0,8}?(¥[\d.]+)", a):
            if m.group(2) == DOOR_FEE:
                continue
            # An amount the fee is said to be part of ("材料价款计入194,970元的总额之中") is the total,
            # not the door fee; and per the D04 trigger 194,970 is only an error when not framed as the quotation.
            if INCLUSION_FRAME.search(a[m.end(1):m.start(2)]) or (m.group(2) == QUOTE_TOTAL and "报价" in a):
                continue
            found.append(([line], f"door:{m.group(2)}"))
    d.decide("D04", ["intro", "requests", "reasons"], found, lambda detail: "misstated_" + detail.split(":")[0], "R-record",
             "misstates a judgment record figure (award, admitted value, delivery date or folding-door fee)", "record.figures")

    # D05 wrong appellate court
    found = []
    filing_route = re.compile(r"(通过|经由|向)[^。;]{0,12}?基层(人民)?法院[^。;]{0,10}?(提交|递交|转交)|基层(人民)?法院[^。;]{0,10}?(提交|递交|转交)")
    for line in doc.closing[:3]:
        if filing_route.search(line["clean"]):
            continue
        if re.search(r"基层(人民)?法院|高级人民法院|高级法院|最高人民法院|(区|县)人民法院", line["clean"]) and "中级" not in line["clean"]:
            found.append(([line], "addressee"))
    for line, s in sentences_of(doc.intro):
        if re.search(r"上诉(于|至|到)[^。;]{0,10}?(基层|高级|最高|区人民|县人民)", s["a"]):
            found.append(([line], "intro_court"))
    d.decide("D05", ["closing", "intro"], found, lambda _: "wrong_appellate_court", "R-court",
             "addresses the appeal to a court other than 某中级法院", "procedure.court")

    # D06 fabricated identifiers or dates instead of a gap marker
    found = []
    for line in doc.lines:
        for segment in re.split(r"[,;。]", line["quoted"]):
            if GAP in segment:
                continue
            if re.search(r"民终第?\d+号|民初\d+号", segment):
                found.append(([line], "case_number_digits"))
            if re.search(r"(统一社会信用代码|信用代码):?[0-9A-Z]{18}", segment):
                found.append(([line], "credit_code"))
            if re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)|(?<!\d)0\d{2,3}-\d{7,8}(?!\d)", segment):
                found.append(([line], "phone"))
            if re.search(r"(送达|收到|签收)[^。;,]{0,20}?@2026-\d\d-\d\d|@2026-\d\d-\d\d[^。;,]{0,10}?(送达|收到|签收)", segment):
                found.append(([line], "service_date"))
            if re.search(r"@2026-05-\d\d[^。;,]{0,12}?(作出|判决)|判决[^。;,]{0,6}?@2026-05-\d\d", segment):
                found.append(([line], "judgment_day"))
            if line.get("zone") == "closing" and re.search(r"^(日期:)?@20\d\d-\d\d-\d\d$", segment):
                found.append(([line], "filing_date"))
            if line.get("zone") == "header":
                if re.search(r"住所地?|地址|住址", segment) and re.search(r"\d+(号|路|栋|幢|室|弄|单元|楼)", segment):
                    found.append(([line], "address_digits"))
                m = re.search(r"(法定代表人|负责人|委托(诉讼)?代理人):?([一-鿿]{1,4})", segment)
                if m and m.group(3)[0] not in MATERIAL_NAMES and not re.search(r"某|同上|不详", m.group(3)):
                    found.append(([line], "person_name"))
    d.decide("D06", ["header", "intro", "requests", "reasons", "closing"], found, lambda _: "fabricated_identifiers", "R-fabrication",
             "invents a case number, identifier, service/judgment/filing date or person not in the materials instead of a gap marker", "party.identifiers")

    # D07 repealed or outdated legal basis
    found = []
    for line, s in sentences_of(doc.requests + doc.reasons):
        c = s["canon"]
        if s["a"] == Q or re.search(r"已废止|废止|失效|原《", c):
            continue
        if re.search(r"(民事诉讼法|民诉法)[^。;]{0,20}?§(170|169)(?!\d)", c):
            found.append(([line], "cpl_old_numbering"))
        if re.search(r"《(中华人民共和国)?合同法》", c):
            found.append(([line], "contract_law"))
        if re.search(r"关于审理建设工程施工合同纠纷案件适用法律问题的解释(\((二|2)\))?》", c) or re.search(r"法释(〔|\[)(2004|2018)(〕|\])(14|20)号", c):
            found.append(([line], "repealed_interpretation"))
    d.decide("D07", ["requests", "reasons"], found, lambda _: "outdated_legal_basis", "R-law",
             "relies on repealed law or superseded article numbering", "law.basis")

    # D13 legal basis mis-cited or mis-attributed to the court / the appellee
    found = []
    for line in doc.requests + doc.reasons:
        canon = line["canon"]
        if CANDIDATE.search(canon):
            continue
        details = []
        for sentence in canon.split("。"):
            details.extend(law_miscites(sentence))
        details.extend(law_misattributions(canon))
        if APPELLEE_CLAIM_DEEMED.search(canon):
            details.append("misattributed_claim:appellee-deemed-acceptance")
        seen_line: set[str] = set()
        for detail in details:
            if detail not in seen_line:
                seen_line.add(detail)
                found.append(([line], detail))
    found = [([lines[0]], f"m{index + 1}:{detail}") for index, (lines, detail) in enumerate(found[:2])]
    d.decide("D13", ["requests", "reasons"], found, lambda detail: "law_misattribution_" + detail.split(":")[0], "R-law-attribution",
             "binds a proposition to the wrong article, or says the court relied on a legal basis the judgment never invoked", "law.attribution")

    # D14 a procedural fact the record does not carry: an appraisal application at first instance
    found = []
    for line in doc.requests + doc.reasons:
        if CANDIDATE.search(line["quoted"]):
            continue
        if not re.search(r"一审|原审", line["quoted"]):
            continue
        for clause in own_clauses(line):
            hit = None
            for pattern in (APPRAISAL_NOUN, APPRAISAL_VERB):
                for m in pattern.finditer(clause):
                    # 未对上诉人的鉴定申请作出处理 negates the court's handling, not the application it presupposes
                    presupposed = pattern is APPRAISAL_NOUN and m.group(1) is not None
                    if not presupposed and APPRAISAL_NEG.search(clause[max(0, m.start() - 6):m.start()]):
                        continue
                    if re.search(r"二审|拟申请|建议|请求[^。;,]{0,6}?二审|是否", clause):
                        continue
                    hit = "first-instance-appraisal-application"
            if hit:
                found.append(([line], hit))
                break
    d.decide("D14", ["requests", "reasons"], found[:1], lambda _: "unrecorded_procedural_fact", "R-record-procedure",
             "asserts that the appellant applied for an appraisal at first instance; the judgment records no such application", "record.procedure")

    # D15 drafting notes to the lawyer carried inside the filing
    found = []
    for line in doc.lines:
        if NOT_FILING_TEXT.search(line["clean"]):
            found.append(([line], "not-filing-text-marker"))
            break
    if not found:
        closing = doc.closing
        for index, line in enumerate(closing):
            text = line["clean"]
            is_head = bool(line["depth"] or line["bold"] or len(text) <= 40)
            if not (is_head and NOTE_HEAD.search(text)):
                continue
            body = []
            for follower in closing[index + 1:]:
                if follower["depth"] or (follower["bold"] and len(follower["clean"]) <= 40):
                    break
                body.append(follower["clean"])
            if body and NOTE_BODY.search("".join(body)):
                found.append(([line], "note-block-after-signature"))
                break
    d.decide("D15", ["header", "intro", "requests", "reasons", "closing"], found, lambda _: "drafting_notes_in_filing", "R-filing-content",
             "the filing carries drafting notes addressed to the lawyer (deadlines, weaknesses, next steps, items to replace) that a petition must not contain", "filing.notes")

    # D16 contradicts the appellant's own position: delivery / interest start, or the claim pleaded as satisfied
    found = []
    for line in doc.requests + doc.reasons:
        if CANDIDATE.search(line["quoted"]):
            continue
        for clause in own_clauses(line):
            detail = None
            for m in NOT_DELIVERED.finditer(clause):
                pre = clause[max(0, m.start() - 20):m.start()]
                if DELIVERY_OBJECT_PART.search(pre) or DOUBLE_NEG.search(pre[-8:] + m.group(0)):
                    continue
                detail = "works-not-delivered"
                break
            if detail is None and INTEREST_CONTEXT.search(clause) and SUIT_DATE_START.search(clause) and not SUIT_DATE_NEG.search(clause):
                detail = "interest-from-date-of-suit"
            if detail is None and not CONDITIONAL_OPEN.match(clause):
                m = CLAIM_SATISFIED.search(clause)
                # the totality of the satisfaction (全额/足额/全部…清偿 or 债权债务…消灭) must be affirmed, in the
                # perfect, about this case's own money; a negated, modal, requested or G/B-settlement clause is not
                pre = clause[max(0, m.start() - 8):m.start()] if m else ""
                if (m and not SATISFIED_INNER_NEG.search(m.group(0)) and SATISFIED_OBJECT.search(clause)
                        and SATISFIED_DONE.search(clause) and not SATISFIED_NEG.search(pre)
                        and not DOUBLE_NEG.search(pre[-8:] + m.group(0))
                        and not (WRONG_OBJ.search(clause) and not RIGHT_OBJ.search(clause))):
                    detail = "claim-already-satisfied"
            if detail:
                found.append(([line], detail))
                break
    d.decide("D16", ["requests", "reasons"], found, lambda _: "contradicts_own_record_position", "R-own-position",
             "asserts the plaza works were never delivered, asks for interest from the date of suit, or pleads that the claim under appeal has already been satisfied in full and the obligations extinguished, against the appellant's own recorded position and its own requests", "position.own")

    # D17 filing skeleton incomplete: a petition that names no appellant or appellee, addresses no
    # court, or has no request / no reasons section is not a filing; each absence is one instance, capped at two.
    found = []
    labels = [m.group(1) for line in doc.header + doc.intro for m in [PARTY_LABEL.match(line["quoted"])] if m]
    if not any(label in ("上诉人",) for label in labels):
        found.append(([doc.lines[0]] if doc.lines else [], "no-appellant-party-line"))
    if not any(label in ("被上诉人",) for label in labels):
        found.append(([doc.lines[0]] if doc.lines else [], "no-appellee-party-line"))
    if not any(re.search(r"法院", line["clean"]) for line in doc.closing[:3]):
        found.append(([doc.closing[0]] if doc.closing else ([doc.lines[-1]] if doc.lines else []), "no-addressee-court"))
    if doc.req_state == "confirmed_missing":
        found.append(([doc.lines[0]] if doc.lines else [], "no-request-section"))
    if doc.rea_state == "confirmed_missing":
        found.append(([doc.lines[0]] if doc.lines else [], "no-reasons-section"))
    found = [(lines, f"m{index + 1}:{detail}") for index, (lines, detail) in enumerate(found[:2]) if lines]
    d.decide("D17", ["header", "intro", "requests", "reasons", "closing"], found, lambda detail: "filing_skeleton_" + detail.split(":")[0], "R-filing-skeleton",
             "the document lacks a part without which it is not an appeal petition (appellant, appellee, addressee court, request section, reasons section)", "filing.skeleton")

    # D11 a closing section that restates the grounds (the charge is the restatement, not the heading)
    found = []
    for index, line in enumerate(doc.reasons):
        if CLOSING_HEAD.match(line["clean"].strip()):
            detail = closing_restates(doc, index)
            if detail:
                found.append(([line], detail))
    d.decide("D11", ["reasons"], found, lambda _: "appended_closing_summary", "R-closing",
             "a closing section restates the grounds after they have been argued", "reason.closing")

    # D12 tail inventory asserting enclosures other than the petition's own copy
    found = []
    inventory = False
    for line in doc.closing:
        text = line["clean"].strip()
        head = ATTACH_HEAD.match(text)
        if head:
            inventory = True
            rest = text[head.end():]
        elif inventory and ENTRY_NUM.match(text):
            rest = text
        else:
            continue
        for entry in re.split(r"[;。]", rest):
            entry = ENTRY_NUM.sub("", entry.strip()).strip()
            if GAP in entry or not re.search(r"[一-鿿]", entry):
                continue
            if OWN_COPY.search(entry) or not ENCLOSURE_NOUN.search(entry):
                continue
            found.append(([line], "extra-enclosure"))
            break
    d.decide("D12", ["closing"], found, lambda _: "asserted_attachment_inventory", "R-attachments",
             "the tail lists enclosures other than the petition's own copy that the filing does not carry", "tail.attachments")

    # D10 request-section shape (S00), then D08/D09 reasons shape
    shapes = {s["id"]: s for s in judge.contract.get("shape_units", [])}
    if doc.req_state != "identified":
        judge.deduction("D10", "not_triggered", ["obs.scan.requests"], "request section missing or ambiguous; omission only loses positive credit")
    else:
        shape_deduction(judge, doc, "D10", shapes["S00"], doc.requests, ["obs.scan.requests"])
    groups = shape_groups(doc) if doc.rea_state == "identified" else None
    for item_id, shape_id, group in (("D08", "S01", "amount"), ("D09", "S02", "interest")):
        scans = ["obs.scan.reasons"]
        if doc.rea_state != "identified":
            judge.deduction(item_id, "not_triggered", scans, "reasons section missing or ambiguous; omission only loses positive credit")
            continue
        if groups is None:
            judge.deduction(item_id, "ambiguous", scans, "level-1 blocks cannot be attributed to the amount or interest unit")
            continue
        members = groups[group]
        shape_deduction(judge, doc, item_id, shapes[shape_id], members, scans, doc.reasons)


OVERRUN_STEP, OVERRUN_CAP = 1.0, 2      # one more instance per further 1.0x Golden past the band, at most 2
UNDERRUN_STEP, UNDERRUN_CAP = 0.15, 3   # one more instance per further 15 percent missing, at most 3


def shape_deduction(judge, doc, item_id, shape, members, scans, section_lines=None):
    """Length is diagnostic only. Omission loses positive credit once; no Golden-relative penalty."""
    judge.deduction(item_id, "not_triggered", scans, "retired length proxy; assess substantive propositions")


def evaluate(registry: dict, judge: ProgramJudge) -> None:
    """Call positive() once per P and deduction() once per D."""
    if registry.get("parse_failure"):
        for item_id in judge.positives:
            judge.positive(item_id, 0.0, "obs.parse_failure", "artifact could not be parsed", "different")
        for item_id in judge.deductions:
            judge.deduction(item_id, "parse_failure", ["obs.parse_failure"], "artifact could not be parsed")
        return
    doc = registry["doc"]
    for fn in (eval_p01, eval_p03, eval_p04, eval_p05, eval_p09, eval_p11, eval_p13, eval_p14):
        fn(judge, doc)
    eval_deductions(judge, doc)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--contract", type=Path, default=CANONICAL_CONTRACT)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    contract_path = args.contract.resolve()
    judge = ProgramJudge(load_contract(contract_path), args.artifact.resolve(), sha256(contract_path))
    evaluate(normalize(extract_raw(args.artifact.resolve()), judge), judge)
    rendered = json.dumps(judge.finish(), ensure_ascii=False, indent=2)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
