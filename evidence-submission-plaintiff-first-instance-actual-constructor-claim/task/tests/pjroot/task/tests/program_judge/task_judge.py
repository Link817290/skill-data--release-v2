#!/usr/bin/env python3
"""Program Judge adapter for the plaintiff evidence-submission opinion (actual-constructor dispute).

Three explicit layers:
  extract_raw()  carrier records only (Markdown lines, or DOCX body paragraphs and table rows in order)
  normalize()    registered rules N01-N08 turn records into zoned, canonical, copy-masked sentences
  evaluate()     one positive() call per P and one deduction() call per D, using registered
                 derivation rules R01-R05 for adoption, contrary claims, replay and shape.

Substantive criteria require source-bound semantic adjudication. Facts come from rubric-contract.json,
the frozen Golden and the frozen materials (copy mask only).
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
MATERIALS_DIR = PACKAGE_ROOT / "materials"

# Frozen amounts as canonical yuan tokens.
Y_TOTAL = "97463000"         # 9,746.30 万元 actual completed-quantity price
Y_PAID = "39423000"          # 3,942.30 万元 paid
Y_OWED = "58040000"          # 5,804.00 万元 owed (Golden)
Y_OWED_ADDBACK = "64766000"  # 5,804.00 + 672.60 when the disputed wage payment is added back
Y_WAGE_DISPUTED = "6726000"  # 672.60 万元 not to be offset
Y_C_ARREARS = "24120000"     # 2,412.00 万元 C owes B
Y_WAGES_OWED = "6138000"     # 613.80 万元 unpaid migrant-worker wages
Y_WAGE_ADVANCE = "12864000"  # 1,286.40 万元 B's wage advance
Y_MGMT_FEE = "9912000"       # 991.20 万元 12% management fee
WRONG_BASIS = ("72688000", "82600000", "48600000")  # 88% internal, B-recognised base, nominal price
FILING_DATE = "2024-07-22"
OWED_REPLAY_SET = {Y_OWED, Y_OWED_ADDBACK}

GAP_MARKERS = [
    "[待补充]", "【待补充】", "[待填写]", "【待填写】", "[待核实]", "【待核实】", "[待定]", "【待定】",
    "[placeholder]", "材料未提供", "未提供", "待补充", "待填写", "待核实", "unspecified", "TBD",
]
GAP_TOKEN = "⟦GAP⟧"

CN_DIGITS = {"零": 0, "〇": 0, "○": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CN_UNITS = {"十": 10, "百": 100, "千": 1000}

NEG_NEAR = re.compile(r"不|未|没有|并非|非|无法|难以|否认|拒绝|无需|无须|无从")
CANDIDATE = re.compile(r"(?<!高度)可能(?!性明显大于)|或许|也许|大概|是否|假设|待定|候选|备选|二选一|抑或|或者说|存疑|尚难确定|不确定")
CONDITIONAL = re.compile(r"如果|倘若|假如|如若|(?<!若)若(?!干)")
ATTRIBUTED = re.compile(r"(?<![向对与致给和及])(被告[一二]?|二被告|[BCD]公司|对方|第三人)([^,:;。向对]{0,6}(主张|认为|辩称|声称|抗辩|提出|称)|(关于|所称|提出的|所主张的|主张的)[^,:;。]{0,60}(抗辩|主张|观点|说法|意见|理由))")
REBUT_VERB = re.compile(r"阻却|反驳|驳斥|排除|击穿|对抗|推翻|回应|否定")
ATTRIBUTED_QUOTED = re.compile(r"(?:(?<=针对)|(?<![向对与致给和及]))(被告[一二]?|二被告|[BCD]公司|对方|第三人)[^,:;。]{0,4}[\"“「『‘][^\"”」』’]{0,60}[\"”」』’]的(抗辩|主张|观点|说法|意见|理由|定性|认定|定位)")  # a quoted opponent characterisation, including 定性/认定/定位
ARGUED = re.compile(r"(?<![原告A公司])(?<!原告)(以[^,:;。]{1,16}为(据|由|依据)|据此)主张")  # subjectless argued claim
BURDEN_OBJECT = re.compile(r"(应当?|须|需)?由(被告[一二]?|二被告|两被告|[BC]公司|对方)([、,和与及](被告[一二]?|[BC]公司))*[^,:;。]{0,2}(举证)?证明")
REJECTED = re.compile(r"不能成立|不成立|不予采信|不予认可|站不住脚|不属实|系错误|是错误的|有误|予以驳回|应予驳回|不应采纳|不予采纳|不足采信")
MONEY = re.compile(r"(?:人民币|RMB)?(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(万元|万|元)|¥(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(万元|万|元)?")
DATE_NUM = re.compile(r"(?<![\d.@¥])(\d{4})(?:年|[-/.])(\d{1,2})(?:月|[-/.])(\d{1,2})日?(?![\d])")
DATE_CN = re.compile(r"([〇零○一二三四五六七八九]{4})年([一二三四五六七八九十]{1,3})月([一二三四五六七八九十]{1,3})日")

HEADING_PREFIX = re.compile(r"^(第?[一二三四五六七八九十]+[、.]|\([一二三四五六七八九十]+\)|\d+(\.\d+)*[、.)]?|[IVX]+\.)")
TITLE_RE = re.compile(r"^(关于[^,。]{0,30})?(原告)?[^,。]{0,12}举证意见")
GROUP_RE = re.compile(r"第[一二三四五六七八九十\d]+组|证据组|G\d+-G?\d+|^[^,。]{2,20}类证据(材料)?$")
HEADING_CLASSES = [
    ("catalogue", re.compile(r"^附(:|件)?|证据目录|目录总表|证据清单总表|证据汇总表")),
    ("excluded", re.compile(r"案件概要|案情概要|工程与项目概况|合同链与法律关系|大事记|施工过程详述|争议焦点|双方主张|利益测算|和解区间|风险提示|风险分析|办案思路|法律关系图|时间轴|适用法律索引|当事人与代理人|被告抗辩|对方观点|对方主张|质证意见")),
    ("burden", re.compile(r"举证责任")),
    ("relation", re.compile(r"关联性|证明体系|证据链|相互印证|综合分析|证据之间|证明逻辑|组间印证|印证关系|组间关系")),
    ("request", re.compile(r"请求事项|诉讼请求|请求|恳请|结论|结语")),
    ("overview", re.compile(r"举证总述|总述|概述|一般陈述|举证说明|证明主线|举证目的|引言|前言|证明思路|举证思路"
                             r"|总体|整体|目标结构|举证结构|证明结构|举证框架|证明框架|举证概况|总论|^总证明")),  # 总论 and 总证明 open an overview section too
    ("parent", re.compile(r"分组举证|证据清单|证据及证明|证明目的|举证内容|证据内容|证据明细|证据说明")),
]
ELIGIBLE_ZONES = {"front", "overview", "parent", "group", "relation", "burden", "request"}
PARTY_COLUMN = re.compile(r"主张方|提出方|抗辩方|举证责任(人|方|主体|归属)|责任(人|方|主体)|举证方")
OPPONENT_PARTY_CELL = re.compile(r"^(被告[一二]?|二被告|两被告|[BCD]公司|对方|第三人)([、,和与及]?(被告[一二]?|[BCD]公司))*$|^主张[^,。]{1,20}的(一方|当事人)$")  # the burden cell may name the party by its claim
ATTRIBUTED_COLUMN = re.compile(r"(被告|对方|二被告)?的?(抗辩|主张)(事项|内容|理由|主张|点)?|争议(事项|焦点)|(应|需|需要|须|待)?(证明|举证)的?(积极)?事实|待证(积极)?事实")
LABEL_LINE = re.compile(r"^(致|案号|原告|被告[一二]?|第三人|委托(诉讼)?代理人|代理人|诉讼代理人|日期|提交日期|举证人|具状人|提交人|此致|合计|附件|附|盖章)(:|\(|$)|盖章\)?$")
# a group heading may carry a parenthetical range with a count suffix, e.g. 第一组主体资格(G1—G7,共7项)
GROUP_COUNT_SUFFIX = re.compile(r"\((G\d+[^()]{0,24})\)$")
# sub-headings that only label the explanation inside the current evidence group keep the group zone
GROUP_SUBHEADING = re.compile(r"^(举证说明|证明说明|本组说明|说明|本组综合证明目的|综合证明目的|本组证明目的|证明目的|证明内容|证明小结|本组证明小结|质证要点|分析|组内分析):?$")
# an own evidence-mapping heading that names 争议焦点 is not the dossier's 争议焦点 zone
OWN_MAPPING = re.compile(r"证据(对应|对照|索引|映射)|对应(证据|索引|关系)|索引|举证(对应|安排|计划)|待证事实")
EVIDENCE_ROW = re.compile(r"^(证据)?G\d+|^证据[\d一二三四五六七八九十]+[:、.]|^\d+[.、]G\d+")
PROSE_PUNCT = re.compile(r"[。!?]")
ROW_LABEL = re.compile(r"^(G\d+(-G?\d+)?[:,.、]?)?(证据名称|证据来源|证据形式|页数|证明对象|证明目的|证明内容|来源|形式)?:?(拟|用以|用于)?(证明)?")
FILLER = re.compile(r"[\d.页份项]+|书证|物证|电子数据|视听资料|证人证言")


# ---------------------------------------------------------------------------
# Layer 1: raw carrier extraction
# ---------------------------------------------------------------------------
def extract_raw(artifact: Path) -> dict:
    """Return raw carrier records with structural locators; never interprets business meaning."""
    raw = {"artifact": artifact, "carrier": None, "records": [], "parse_error": None}
    if not artifact.is_file():
        raw["parse_error"] = "artifact file is missing"
        return raw
    if artifact.suffix.lower() == ".docx":
        raw["carrier"] = "docx"
        try:
            raw["records"] = docx_records(artifact)
        except Exception as exc:  # carrier-level failure only
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
        if in_fence:
            continue
        stripped = line.strip()
        if stripped.startswith("|") and stripped.count("|") >= 2:
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", cell or "--") for cell in cells):
                continue
            raw["records"].append({"locator": f"md:line[{number}]", "text": line, "table": True, "cells": cells})
        else:
            raw["records"].append({"locator": f"md:line[{number}]", "text": line, "table": False, "cells": []})
    return raw


def docx_records(path: Path) -> list[dict]:
    """DOCX body children in document order; table rows keep their cells (merged cells once)."""
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    document = docx.Document(str(path))
    records = []
    p_index = t_index = 0
    for child in document.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            paragraph = Paragraph(child, document)
            try:
                style = (paragraph.style.name if paragraph.style is not None else "") or ""
            except Exception:
                style = ""
            records.append({"locator": f"docx:body/p[{p_index}]", "text": paragraph.text, "table": False,
                            "cells": [], "heading_style": style.lower().startswith(("heading", "标题"))})
            p_index += 1
        elif tag == "tbl":
            for r, row in enumerate(Table(child, document).rows):
                cells, previous = [], None
                for cell in row.cells:
                    if cell._tc is previous:
                        continue
                    previous = cell._tc
                    cells.append(cell.text)
                records.append({"locator": f"docx:body/tbl[{t_index}]/tr[{r}]", "text": "|" + "|".join(cells) + "|",
                                "table": True, "cells": cells})
            t_index += 1
    return records


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


def n01_clean(text: str) -> str:
    """N01: NFKC fold, drop zero-width characters and Markdown decoration, remove whitespace."""
    text = unicodedata.normalize("NFKC", text or "")
    for invisible in ("​", "‌", "‍", "﻿", "­"):
        text = text.replace(invisible, "")
    text = re.sub(r"^\s*#{1,6}\s*", "", text)
    text = re.sub(r"^\s*>\s*", "", text)
    text = re.sub(r"^\s*[-*+]\s+(?=\S)", "", text)
    text = text.replace("**", "").replace("__", "").replace("`", "")
    return re.sub(r"\s+", "", text)


def n02_money(text: str) -> str:
    """N02: amounts with 元/万元/万/人民币/¥ and thousands separators to one canonical yuan token."""
    def token(integer: str, fraction: str | None, unit: str | None) -> str:
        try:
            value = Decimal(integer.replace(",", "") + (fraction or ""))
        except InvalidOperation:
            return integer
        if unit in ("万元", "万"):
            value *= 10000
        rendered = format(value.normalize(), "f")
        if "." in rendered:
            rendered = rendered.rstrip("0").rstrip(".")
        return "¥" + rendered

    def repl(m: re.Match) -> str:
        if m.group(1) is not None:
            return token(m.group(1), m.group(2), m.group(3))
        return token(m.group(4), m.group(5), m.group(6))

    text = text.replace("百分之八十八", "88%").replace("百分之十二", "12%")
    return MONEY.sub(repl, text)


def n03_dates(text: str) -> str:
    """N03: dates in Arabic or Chinese numerals to one ISO token."""
    def cn(m: re.Match) -> str:
        year = "".join(str(CN_DIGITS[c]) for c in m.group(1))
        month, day = cn_number(m.group(2)), cn_number(m.group(3))
        if month is None or day is None:
            return m.group(0)
        return f"@{year}-{month:02d}-{day:02d}"

    text = DATE_CN.sub(cn, text)
    return DATE_NUM.sub(lambda m: f"@{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}", text)


def n04_evidence_ids(text: str) -> str:
    """N04: evidence identifiers and ranges (G27—G64, G27至G64) to one G-token form."""
    text = re.sub(r"G(\d+)[—–―~\-]+G?(\d+)", r"G\1-G\2", text)
    return re.sub(r"G(\d+)(至|到)G?(\d+)", r"G\1-G\3", text)


def n05_gap(text: str) -> str:
    """N05: fold every declared gap marker (and blank fill lines) into one gap token."""
    for marker in sorted(GAP_MARKERS, key=len, reverse=True):
        text = text.replace(unicodedata.normalize("NFKC", marker), GAP_TOKEN)
    return re.sub(r"_{3,}|×{2,}|X{3,}", GAP_TOKEN, text)


def canon(text: str) -> str:
    """N01, N05, N04, N03, N02 in that order."""
    return n02_money(n03_dates(n04_evidence_ids(n05_gap(n01_clean(text)))))


def split_sentences(text: str) -> list[str]:
    return [part for part in re.split(r"[。;!?]", text) if part]


def raw_token_soup(raw_text: str) -> bool:
    """R01: a raw line made of eight or more whitespace-separated short tokens is keyword soup.

    Whitespace inside numbers and between a number and its date/amount unit is collapsed first,
    so spaced numbers such as `2024 年 7 月 22 日` or `9,746.30 万元` stay one phrase; thousands
    separators never split a fragment.
    """
    text = unicodedata.normalize("NFKC", raw_text or "").replace("**", "").strip()
    text = re.sub(r"^\s*(#{1,6}|[-*+>]|\d+[.)])\s+", "", text)
    text = re.sub(r"(\d)\s*([.,:/])\s*(\d)", r"\1\2\3", text)
    text = re.sub(r"(\d)\s+(?=[年月日万元名人份期%号])", r"\1", text)
    text = re.sub(r"([年月])\s+(?=\d)", r"\1", text)
    fragments = [frag for frag in re.split(r"(?:\s|、|(?<!\d),|,(?!\d))+", text) if frag]
    short = [frag for frag in fragments if len(frag) <= 8]
    return len(fragments) >= 8 and len(short) >= 0.7 * len(fragments)


def is_spray(sentence: str) -> bool:
    """R01: enumerated short fragments, more than four distinct amounts, or an over-long span."""
    fragments = [f for f in re.split(r"[、,/]", sentence) if f]
    short = [f for f in fragments if len(f) <= 8]
    if len(fragments) >= 6 and len(short) >= 0.7 * len(fragments):
        return True
    if len(set(re.findall(r"¥(\d+)", sentence))) > 4:
        return True
    return len(sentence) > 400


class MaterialMask:
    """N06: verbatim material copy mask built from the frozen materials (prose sentences and table cells)."""

    def __init__(self) -> None:
        units: list[str] = []
        cells: list[str] = []
        files = sorted(MATERIALS_DIR.glob("*.docx")) + sorted(MATERIALS_DIR.glob("*.md"))
        if not files:
            raise RuntimeError("frozen materials are required to build the copy mask")
        for path in files:
            if path.suffix == ".docx":
                records = docx_records(path)
            else:
                records = [{"text": line, "table": False, "cells": []} for line in path.read_text(encoding="utf-8").splitlines()]
            for record in records:
                for piece in (record["cells"] if record["table"] else [record["text"]]):
                    units.extend(split_sentences(canon(piece)))
                    if record["table"]:
                        cells.append(canon(piece))
        self.blob = "\n".join(units)
        self.cell_blob = "\n".join(cells)

    def copied(self, fragment: str) -> bool:
        return len(fragment) >= 4 and fragment in self.blob

    def copied_cell_fragment(self, fragment: str) -> bool:
        return len(fragment) >= 4 and fragment in self.cell_blob


def strip_row_label(fragment: str) -> str:
    return ROW_LABEL.sub("", fragment, count=1).strip(":,、()")


def heading_kind(record: dict, clean: str) -> tuple[str | None, str]:
    """N07: resolve headings by alias class plus whole-line structure; unknown short lines stay body text."""
    probe = GROUP_COUNT_SUFFIX.sub("", clean) if re.match(r"^(#*\s*)?第[一二三四五六七八九十\d]+组", clean) else clean
    raw = unicodedata.normalize("NFKC", record["text"]).strip()
    declared = (not record.get("table")) and (raw.startswith("#") or bool(record.get("heading_style")))
    if record.get("table") or not clean or (not declared and (len(clean) > 40 or re.search(r"[。;,]", probe))):
        return None, ""
    if declared and re.search(r"[。!?]", clean):
        return None, ""
    body = HEADING_PREFIX.sub("", clean.split(":", 1)[0] if declared and ":" in clean else clean)
    structural = (raw.startswith("#") or (raw.startswith("**") and raw.endswith("**")) or bool(HEADING_PREFIX.match(clean))
                  or bool(record.get("heading_style")) or bool(GROUP_RE.search(n04_evidence_ids(body))) or len(body) <= 20)
    if not structural:
        return None, ""
    if TITLE_RE.match(body) and not HEADING_PREFIX.match(clean):
        return "title", body
    if not re.match(r"^第[一二三四五六七八九十\d]+组", body) and re.search(r"证据.*(印证关系|组间关系|关联性|证明体系)|证据组之间", body):
        return "relation", body
    if GROUP_RE.search(n04_evidence_ids(body)) and not re.search(r"证据目录|目录总表|^附", body):
        return "group", n04_evidence_ids(body)
    if GROUP_SUBHEADING.match(body):
        return "subheading", body
    for kind, pattern in HEADING_CLASSES:
        if pattern.search(body):
            if kind == "excluded" and OWN_MAPPING.search(body):
                return "overview", body
            # '被告抗辩(事项)的举证责任分配' is the author's own burden section, not a dossier/opponent zone
            if kind == "excluded" and HEADING_CLASSES[2][1].search(body):
                return "burden", body
            return kind, body
    return None, ""


def split_row(text: str, mask: MaterialMask) -> tuple[list[str], list[str]]:
    """N06 for evidence rows: a wholly copied cell is masked; otherwise only fragments copied from material cells."""
    whole = strip_row_label(text)
    if whole and mask.copied(whole):
        return [], [whole]
    kept, masked = [], []
    for frag in re.split(r"[,;。()]", text):
        core = strip_row_label(frag)
        if not core or FILLER.fullmatch(core):
            continue
        (masked if mask.copied_cell_fragment(core) else kept).append(core)
    return kept, masked


DEFENCE_ASSERTOR = re.compile(r"^由(被告[一二]?|二被告|两被告|[BC]公司)([、,和与及](被告[一二]?|[BC]公司))*(一并)?(主张|提出|抗辩)$")
OPPONENT_DEFENCE_HEADER = re.compile(r"(被告[一二]?|二被告|对方|[BC]公司)(的)?(主要)?(抗辩|主张|反驳)(事项|内容|理由|要点)?")


def attributed_columns(header, cells):
    """Columns whose cells state the opponent's own defence, identified by a party column."""
    named = {i for i, h in enumerate(header) if i < len(cells) and OPPONENT_DEFENCE_HEADER.fullmatch(h)}
    party = next((i for i, h in enumerate(header) if PARTY_COLUMN.search(h)), None)
    if party is None or party >= len(cells) or not OPPONENT_PARTY_CELL.match(cells[party]):
        return named
    return named | {i for i, h in enumerate(header) if i < len(cells) and ATTRIBUTED_COLUMN.fullmatch(h)}


class Doc:
    """Normalized opinion: zoned lines and copy-masked sentences."""

    def __init__(self, raw: dict, mask: MaterialMask):
        self.raw = raw
        self.mask = mask
        self.artifact = str(raw["artifact"])
        self.lines: list[dict] = []
        zone, group = "front", ""
        self.heading_count = 0
        self.zeroed: dict[str, list[dict]] = {}   # contrary spans that zeroed a P item
        self.p16_missing: set[str] = set()        # request elements missing when P16 is 0
        header: list[str] = []
        table_run = False
        for record in raw["records"]:
            if not record["table"]:
                table_run = False
            clean = n01_clean("".join(record["cells"])) if record["table"] else n01_clean(record["text"])
            if not clean:
                continue
            kind, body = heading_kind(record, clean)
            line = {"locator": record["locator"], "raw": record["text"], "zone": zone, "group": group,
                    "heading": None, "table": record["table"], "units": [], "masked": [], "label": False}
            if kind == "title":
                line.update(heading="title", label=True)
                self.lines.append(line)
                continue
            if kind == "subheading":
                self.heading_count += 1
                if zone == "group":
                    line.update(heading="subheading")
                    self.lines.append(line)
                    continue
                kind = "overview"
            if kind:
                self.heading_count += 1
                zone, group = kind, (body if kind == "group" else "")
                line.update(heading=kind, zone=zone, group=group)
                self.lines.append(line)
                continue
            if record["table"]:
                if not table_run:
                    header = [canon(cell) for cell in record["cells"]]
                    table_run = True
                drop = attributed_columns(header, [canon(cell) for cell in record["cells"]])
                kept, masked = [], []
                for index, cell in enumerate(record["cells"]):
                    if index in drop:
                        continue
                    k, m = split_row(canon(cell), mask)
                    kept.extend(k)
                    masked.extend(m)
                line["masked"] = masked
                if kept:
                    line["units"] = [",".join(kept)]
            else:
                c = canon(record["text"])
                line["label"] = bool(LABEL_LINE.match(c)) or bool(re.fullmatch(r"(日期|提交日期|落款日期)?:?@\d{4}-\d{2}-\d{2}", c))
                if raw_token_soup(record["text"]):
                    line["units"] = ["⟦SPRAY⟧"]
                elif EVIDENCE_ROW.match(c) and not PROSE_PUNCT.search(c):
                    kept, masked = split_row(c, mask)
                    line["masked"] = masked
                    if kept:
                        line["units"] = [",".join(kept)]
                else:
                    parts = split_sentences(c)
                    for k, sentence in enumerate(parts):
                        (line["masked"] if mask.copied(sentence) else line["units"]).append(sentence)
                        if k + 1 < len(parts) and DEFENCE_ASSERTOR.match(parts[k + 1]):
                            line.setdefault("attributed", set()).add(sentence)
            self.lines.append(line)
        self.sentences = [{"text": "" if unit in line.get("attributed", ()) else adopted_prefix(unit), "full": unit, "line": line} for line in self.lines
                          if line["heading"] is None and line["zone"] in ELIGIBLE_ZONES
                          for unit in line["units"] if unit != "⟦SPRAY⟧"]

    def loc(self, line: dict, object_key: str, field: str, prefix: str, n: int = 0) -> Locator:
        return Locator(locator_id=f"{prefix}:{line['locator']}:{n}", artifact_path=self.artifact,
                       container_type=self.raw["carrier"] or "unknown", container_path=line["locator"],
                       object_key=object_key, field=field, observed=(line["raw"] or "")[:400])

    def canon_loc(self, source: Locator, observed: str, rule: str) -> Locator:
        return Locator(locator_id=source.locator_id + ":canon", artifact_path=self.artifact,
                       container_type=source.container_type, container_path=source.container_path,
                       object_key=source.object_key, field=source.field + ".canonical",
                       observed=observed[:400], evidence_origin="lossless_canonicalized",
                       source_locator_ids=(source.locator_id,), normalization_rule_id=rule)

    def doc_loc(self, object_key: str, prefix: str) -> Locator:
        return Locator(locator_id=f"{prefix}:document", artifact_path=self.artifact,
                       container_type=self.raw["carrier"] or "unknown", container_path="document",
                       object_key=object_key, field="eligible_sentences",
                       observed=f"{len(self.sentences)} eligible sentences; {self.heading_count} resolved headings")


def observe_spans(judge: ProgramJudge, doc: Doc, obs_id: str, spans: list[dict], object_key: str,
                  field: str, rule: str) -> str:
    evidence: list[Locator] = []
    for n, span in enumerate(spans):
        source = doc.loc(span["line"], object_key, field, obs_id, n)
        evidence.extend([source, doc.canon_loc(source, span["text"], rule)])
    return judge.observe(obs_id, "identified", evidence)


def normalize(raw_registry: dict, judge: ProgramJudge) -> dict:
    """Register carrier-independent observations; the runtime owns their states."""
    if raw_registry.get("parse_error"):
        locator = Locator("parse:artifact", str(raw_registry["artifact"]), raw_registry.get("carrier") or "unknown",
                          "artifact", "evidence_opinion", "carrier", raw_registry["parse_error"])
        judge.observe("obs.parse_failure", "parse_failure", [locator])
        return {"parse_failure": True}
    doc = Doc(raw_registry, MaterialMask())
    judge.observe("obs.scan.document", "identified" if doc.sentences else "confirmed_missing",
                  [doc.doc_loc("document", "obs.scan.document")])
    return {"parse_failure": False, "doc": doc}


# ---------------------------------------------------------------------------
# Layer 3: P/D decisions
# ---------------------------------------------------------------------------
def neg_near(text: str, position: int, window: int = 8) -> bool:
    """R02: negation within the same clause and a short window before the key predicate."""
    clause_start = max(text.rfind(",", 0, position), text.rfind(":", 0, position)) + 1
    return NEG_NEAR.search(text[max(clause_start, position - window):position]) is not None


def adopted_prefix(sentence: str) -> str:
    """R02: text before the clause that attributes a proposition to the defendants or rejects one."""
    cut = len(sentence)
    for pattern in (ATTRIBUTED_QUOTED, ATTRIBUTED, ARGUED, REJECTED, BURDEN_OBJECT):
        for m in pattern.finditer(sentence):
            start = max(sentence.rfind(",", 0, m.start()), sentence.rfind(":", 0, m.start()), 0)
            # '阻却/反驳/驳斥…C公司的…抗辩' is the plaintiff rebutting a defence, not the defence itself
            if pattern is ATTRIBUTED and REBUT_VERB.search(sentence[start:m.start()]):
                continue
            cut = min(cut, start)
            break
    return sentence[:cut]


def generic_excluded(sentence: str) -> bool:
    """R02: candidate, conditional or spray spans are never adopted; attributed or rejected clauses are cut off first."""
    return bool(CANDIDATE.search(sentence) or CONDITIONAL.search(sentence) or is_spray(sentence))


def clauses(sentence: str) -> list[str]:
    return [c for c in re.split(r"[,:]", sentence) if c]


def credit(judge, doc, item_id, fraction, comparison, reason, spans, object_key, rule="N01"):
    obs = f"obs.{item_id}"
    if comparison == "missing":
        judge.observe(obs, "confirmed_missing", [doc.doc_loc(object_key, obs)])
        judge.positive(item_id, 0.0, obs, reason, "missing")
        return
    if comparison == "ambiguous":
        evidence = [doc.loc(s["line"], object_key, "candidate_span", obs, n) for n, s in enumerate(spans)]
        judge.observe(obs, "ambiguous", evidence or [doc.doc_loc(object_key, obs)])
        judge.positive(item_id, 0.0, obs, reason, "different")
        return
    observe_spans(judge, doc, obs, spans, object_key, "proposition_span", rule)
    judge.positive(item_id, fraction, obs, reason, comparison)


def settle(judge, doc, item_id, object_key, full, partial, contrary, reason_full, reason_partial, rule="N01",
           partial_fraction=0.5, full_result="equivalent"):
    """R03: adopted hits against contrary assertions; both present is ambiguous, never first-hit."""
    if contrary:
        doc.zeroed[item_id] = list(contrary)  # the contrary assertion is what zeroes the item
    if (full or partial) and contrary:
        return credit(judge, doc, item_id, 0, "ambiguous", "proposition asserted and contradicted", full + partial + contrary, object_key)
    if full:
        return credit(judge, doc, item_id, 1.0, full_result, reason_full, full, object_key, rule)
    if partial:
        return credit(judge, doc, item_id, partial_fraction, "partial", reason_partial, partial, object_key, rule)
    if contrary:
        return credit(judge, doc, item_id, 0, "different", "only the contrary proposition is asserted", contrary, object_key)
    return credit(judge, doc, item_id, 0, "missing", "proposition not found in adopted opinion text", [], object_key)


def group3_zone(span: dict) -> bool:
    heading = span["line"]["group"]
    return span["line"]["zone"] == "group" and bool(re.search(r"第三组|第3组|实际施工|G17(?!\d)", heading))


P01_DEPENDENCY = re.compile(r"(其后|其余|其他|后续)各?组[^。]{0,8}(均|都|皆)?(依附|依赖|建立在|取决于|以[^。]{0,12}为(基础|前提))|第[四五六七]组[^。]{0,8}在第三组[^。]{0,12}基础上"
                            r"|第[四五六七]组[^。]{0,8}以第三组[^。]{0,40}为(基础|前提)")
P01_OWN_GROUP_DEPENDENCY = re.compile(r"^本组[^。]{0,8}(以第三组[^。]{0,40}为(基础|前提)|在第三组[^。]{0,40}基础上)")  # '本组' inside groups 4-7
P01_COMPLETION = re.compile(r"(证明|证实|锁定|确认|确立|所证)(的是|了)?[^,:]{0,4}(原告|A公司)[^,:]{0,30}实际(完成|组织[^,:]{0,20}完成|投入[^,:]{0,6}完成)[^,:]{0,20}(工程|施工)")


def eval_p01(judge, doc):
    """Only the increment counts - the group-3 actual-constructor proof AND the dependency of the other groups on it
    in one sentence; proof alone restates the dossier (§六 p[39]/p[41], §九 p[94]) and earns nothing (no half tier)."""
    verb = re.compile(r"(锁定|证明|确认|印证|认定|确立|证实|夯实)[^,:]{0,12}实际施工人|(原告|A公司)[^,:]{0,4}构成(《[^》]{1,30}》第[^,:]{1,12}(所称|规定)的?)?实际施工人|实际施工人(身份|地位)[^,:]{0,6}(确凿|成立|得以确认|毋庸置疑)|(而是|即为|就是)[^,:]{0,16}实际施工人")
    full, contrary = [], []
    for s in doc.sentences:
        t = s["text"]
        if generic_excluded(t):
            continue
        if not (group3_zone(s) or s["line"]["zone"] == "relation" or re.search(r"第三组|第3组|G17-G\d+|实际施工(的)?(事实)?证据", t)):
            continue
        m = verb.search(t) or P01_COMPLETION.search(t)
        if not m:
            continue
        if re.search(r"(B公司|C公司|D公司|徐某)(的|系|为|是)?实际施工人", t[max(0, m.start() - 12):m.end()]):
            continue
        if m.group(0).startswith(("而是", "即为", "就是")) and not re.search(r"原告|A公司", t[:m.start()]):
            continue
        if neg_near(t, m.start()):
            if not re.search(r"(不作为|不能作为|不是|并非|不能|不)[^,:]{0,4}(独立|单独|唯一)[^,:]{0,16}(认定|证明)|唯一(依据|根据|证据)", t[max(0, m.start() - 16):m.end() + 12]):
                contrary.append(s)
            continue
        own_later_group = s["line"]["zone"] == "group" and re.match(r"第[四五六七]组", s["line"]["group"] or "")
        if P01_DEPENDENCY.search(t) or (own_later_group and P01_OWN_GROUP_DEPENDENCY.search(t)):
            full.append(s)
    settle(judge, doc, "P01", "group3.actual_constructor_foundation", full, [], contrary,
           "group 3 locks A's actual-constructor status and the other groups depend on it", "")


REBUTTED_NP = re.compile(r"(排除|反驳|驳斥|否定|推翻|不能成立的?)[^。]{0,12}关于[^。]{0,12}$")
VALID_INTERNAL = re.compile(r"(内部承包(关系)?|责任书)[^,:]{0,6}(真实|合法)?(有效|成立)")


def internal_valid_adopted(t: str, m: re.Match) -> bool:
    ends = [p for p in (t.find(",", m.end()), t.find(":", m.end())) if p != -1]
    clause_end = min(ends) if ends else len(t)
    return not (neg_near(t, m.end() - 2, 10)
                or re.search(r"须|需|前提|是否|要件|条件|取决于", t[m.start():max(clause_end, m.end() + 6)])
                or re.match(r"[,:]?以[^。]{0,40}为(前提|条件|要件)", t[m.end():]))  # '…的成立，以…为前提' states the test


ANAPHOR_VOID = re.compile(r"(上述|前述|上列|该(责任书|合同|协议|安排|文件))[^,:]{0,8}(均|依法|应当?|应认定为?)?[^,:]{0,4}无效")


def anaphora_joined(doc) -> list[dict]:
    """Sentence k and k+1 of one numbered point (one raw line, not a table) when k+1 voids k's object by anaphor."""
    out = []
    for line in doc.lines:
        if line["heading"] or line["table"] or line["zone"] not in ELIGIBLE_ZONES:
            continue
        units = [u for u in line["units"] if u != "⟦SPRAY⟧"]
        for first, second in zip(units, units[1:]):
            if ANAPHOR_VOID.search(second) and not ANAPHOR_VOID.search(first):
                joined = first + "," + second
                out.append({"text": adopted_prefix(first) + "," + adopted_prefix(second), "full": joined, "line": line, "joined": True})
    return out


LIST_ITEM = re.compile(r"^\s*(\d+[.、)）]|[-*+]\s|[（(][一二三四五六七八九十\d]+[)）])")


def point_joined(doc) -> list[dict]:
    """All sentences of one numbered/bulleted list item (one raw line, not a table) as one local span."""
    out = []
    for line in doc.lines:
        if line["heading"] or line["table"] or line["zone"] not in ELIGIBLE_ZONES or not LIST_ITEM.match(line["raw"]):
            continue
        units = [u for u in line["units"] if u != "⟦SPRAY⟧"]
        if len(units) >= 2:
            # joined with ; so the spray test still sees the individual sentence fragments
            out.append({"text": ";".join(adopted_prefix(u) for u in units), "full": ";".join(units), "line": line, "joined": True})
    return out


def eval_p02(judge, doc):
    transfer = re.compile(r"实为转包|认定为转包|(认定为|构成|属于)[^,:]{0,12}将[^,:]{0,12}转包(给|予|于)|构成转包|属于转包|系转包|转包性质|属转包|为转包|(实质|本质)上?(是|为|系|构成|属于)(违法)?转包|实际上?是转包")
    reason = re.compile(r"(缺乏|欠缺|无|没有|不存在|并无|未(建立|签订|缴纳|发放))[^,:]{0,8}(劳动|社保|社会保险|工资|从属|人事)|聘任文件[^,:]{0,8}(无|未|没有)[^,:]{0,2}签收")
    full, partial, contrary = [], [], []
    for s in doc.sentences + anaphora_joined(doc):
        t = s["text"]
        if generic_excluded(t) or not re.search(r"责任书|内部承包|G10(?!\d)", t):
            continue
        v = VALID_INTERNAL.search(t)
        if v and internal_valid_adopted(t, v):
            contrary.append(s)
            continue
        m = transfer.search(t)
        if not m:
            continue
        if neg_near(t, m.start(), 6):
            contrary.append(s)
            continue
        i = re.compile(r"无效").search(t, m.start())
        if not i or neg_near(t, i.start(), 6):
            continue
        (full if reason.search(t) else partial).append(s)
    settle(judge, doc, "P02", "contract_chain.internal_contract_nature", full, partial, contrary,
           "internal contracting agreement is a disguised transfer and void for lack of a real employment relation",
           "disguised transfer and void without the employment-relation reason")


def adopted_wrong_basis(t: str) -> re.Match | None:
    """R05: a clause adopting 88%, 7,268.80, 8,260.00 or 4,860 as the basis of compensation or settlement."""
    pattern = re.compile(r"(应|应当|宜|按|按照|以|参照|依照|依据)[^,:]{0,12}(88%|¥(" + "|".join(WRONG_BASIS) + r")(?!\d))[^,:]{0,12}(折价补偿|结算|计价|计付|补偿)")
    for m in pattern.finditer(t):
        start = max(t.rfind(",", 0, m.start()), t.rfind(":", 0, m.start())) + 1
        if re.search(r"而非|并非|不是|非|不应|不能|不得|不予|拒绝|否认|无效|不产生效力|不构成|无签认|名义|反驳|排除|而不是|不以|不按|从未|并未|未曾|没有", t[start:min(len(t),m.end()+180)]):
            continue
        if re.search(r"(G\d+|证据|该(文件|文书|报告|合同|协议))[^,:]{0,20}(证明|载明|记载|显示|表明)|"
                     r"(B公司|D公司|徐某|双方|各方|两方)[^,:]{0,14}(约定|签订|签署|确认)", t[start:m.start()]):
            continue
        if re.search(r"(约定|载明|记载|写明|规定|所定|订明)的?[\"“”「」『』'‘’]?$|》[\"“”「」『』'‘’]$", t[start:m.start()]):  # 所定/订明
            continue  # the instrument's term as written ('约定的…', '《…》"…"'), not the author's basis
        if re.match(r"[^,:]{0,16}的(约定|口径|条款|安排)[^,:]{0,12}(不能|不得|不应|不作为|不属于|不适用|无效|对原告不)", t[m.end():]):
            continue  # the instrument's term named and rejected after the match
        return m
    return None


def eval_p03(judge, doc):
    basis = re.compile(r"折价补偿|计价依据|结算依据|计价基础|结算基础|据以结算|作为[^,:]{0,10}依据|据实结算|(以|按|按照|参照|依据)[^,:]{0,20}¥" + Y_TOTAL + r"[^,:]{0,6}(结算|计价|计算工程价款|确定工程价款)")
    full, partial, contrary = [], [], []
    for s in doc.sentences:
        t = s["text"]
        if generic_excluded(t) or not re.search(r"¥" + Y_TOTAL + r"(?!\d)", t):
            continue
        if adopted_wrong_basis(t):
            contrary.append(s)
            continue
        b = basis.search(t)
        if b and not neg_near(t, b.start(), 10):
            full.append(s)
        elif b:
            contrary.append(s)
        elif re.search(r"实际完成(的)?工程量", t) and re.search(r"证明|印证|确认|证实|对应|为", t):
            partial.append(s)
        elif (re.search(r"¥" + Y_TOTAL + r"(?!\d)的?(结算价|造价|工程价款)", t) and re.search(r"支撑|证明|印证|佐证|证实|支持", t)
              and re.search(r"工程量计算书|竣工图|工程量", t)):
            # quantity evidence supporting the 9,746.30 settlement price = proven actual-quantity price (partial tier)
            partial.append(s)
    settle(judge, doc, "P03", "price.compensation_basis", full, partial, contrary,
           "9,746.30 (actual completed quantity) is the basis of compensation",
           "9,746.30 proven as actual completed quantity price without the compensation-basis link")


OWED = re.compile(r"(尚欠|欠付|拖欠|仍欠|应付未付|欠款)(?P<gap>[^,:;¥]{0,10})¥(?P<amount>\d+)(?!\d)")
PAY_REQUEST = re.compile(r"(应当?|判令|请求|要求|责令)[^,:;¥]{0,14}(支付|给付|清偿|偿付)(?P<gap>[^,:;¥]{0,10})¥(?P<amount>\d+)(?!\d)")
OTHER_DEBT = re.compile(r"工资|薪|管理费|利息|违约金|范围|损失|费用")


def owed_assertions(t: str) -> list[tuple[str, re.Match]]:
    """R04: owed-amount assertions or payment requests whose debtor in the clause is B公司 (C's arrears to B excluded)."""
    found = []
    for pattern in (OWED, PAY_REQUEST):
        for m in pattern.finditer(t):
            if OTHER_DEBT.search(m.group("gap")):
                continue
            if pattern is PAY_REQUEST and not re.search(r"工程款|工程价款|价款|欠款|款项", m.group("gap")):
                continue
            start = max(t.rfind(",", 0, m.start()), t.rfind(":", 0, m.start()), t.rfind("(", 0, m.start()), t.rfind(";", 0, m.start())) + 1
            prefix = t[start:m.start()]
            if pattern is PAY_REQUEST:
                prefix = t[start:m.end()]
            if not re.search(r"B公司|被告一|被告B|C公司|被告二|发包人", prefix) and pattern is OWED and start > 0:
                # elided subject - the preceding clause of the same sentence is B公司 paying ('B公司已付X,尚欠Y')
                previous = t[max(t.rfind(",", 0, start - 1), t.rfind(":", 0, start - 1), t.rfind(";", 0, start - 1)) + 1:start - 1]
                if t[start - 1] == ";":
                    previous = ""
                if re.match(r"(\d+[.、])?(B公司|被告一|被告B)[^,:]{0,4}(已付|已支付|已向原告支付|累计支付|支付)", previous):
                    prefix = previous + prefix
            if re.search(r"C公司|被告二|发包人", prefix) or not re.search(r"B公司|被告一|被告B", prefix):
                continue
            if neg_near(t, m.start(), 4):
                continue
            found.append((m.group("amount"), m))
    return found


def eval_p04(judge, doc):
    hits, values = [], set()
    for s in doc.sentences + semicolon_joined(doc):
        t = s["text"]
        if generic_excluded(t):
            continue
        for value, _m in owed_assertions(t):
            values.add(value)
            hits.append((s, value))
    spans = [h[0] for h in hits]
    if not hits:
        return credit(judge, doc, "P04", 0, "missing", "no owed-amount assertion against B公司", [], "payment.owed")
    if len(values) > 1:
        return credit(judge, doc, "P04", 0, "ambiguous", "conflicting owed amounts", spans, "payment.owed")
    value = next(iter(values))
    if value not in OWED_REPLAY_SET:
        return credit(judge, doc, "P04", 0, "different", f"owed amount {value} is not replayable from 9,746.30 - 3,942.30", spans, "payment.owed", "N02")
    with_paid = [s for s, _v in hits if re.search(r"¥" + Y_PAID + r"(?!\d)", s["text"])]
    if with_paid:
        return credit(judge, doc, "P04", 1.0, "equivalent", "paid 3,942.30 and owed amount replayed by R04", with_paid, "payment.owed", "N02")
    return credit(judge, doc, "P04", 0.5, "partial", "owed amount replayed but paid amount not stated in the span", spans, "payment.owed", "N02")


def eval_p05(judge, doc):
    nonoffset = re.compile(r"(不应|不得|不能|不予|不应当|不可|无权|不宜)[^,:]{0,15}(抵扣|抵减|扣减|扣除|抵销|冲抵)|(不应|不得|不能|不予)(计入|认定为|列入)[^,:]{0,6}(已付|付款)|(不在|不属于|不具备|不构成|不在于)[^,:]{0,4}(抵扣|抵减|扣减|抵销|冲抵)的?(范围|基础|条件|对象)")
    offset = re.compile(r"(应|应当|可以|予以)(予以)?(全额)?(抵扣|抵减|扣减|扣除|抵销|冲抵)")
    full, contrary = [], []
    for s in doc.sentences:
        t = s["text"]
        if generic_excluded(t) or not re.search(r"¥" + Y_WAGE_DISPUTED + r"(?!\d)", t) or not re.search(r"代付|工资", t):
            continue
        if nonoffset.search(t):
            full.append(s)
            continue
        m = offset.search(t)
        if m and not neg_near(t, m.start(), 6):
            contrary.append(s)
    settle(judge, doc, "P05", "payment.disputed_wage_offset", full, [], contrary,
           "the disputed 672.60 wage payment is not offset against A's claim", "")


def eval_p06(judge, doc):
    entity = re.compile(r"C公司|被告二|发包人")
    wrong = re.compile(r"(B公司|被告一)[^,:]{0,6}(应)?(在|于)欠付[^,:]{0,10}(C公司|被告二)")
    full, contrary = [], []
    for s in doc.sentences:
        t = s["text"]
        if generic_excluded(t) or wrong.search(t):
            continue
        e = entity.search(t)
        a = re.search(r"¥" + Y_C_ARREARS + r"(?!\d)", t)
        r = re.search(r"范围内|限度内|为限", t)
        v = re.search(r"(承担|负)[^,:]{0,8}(责任|付款|支付)", t)
        if not (e and a and r and v and "欠付" in t and e.start() < a.start()):
            continue
        if neg_near(t, v.start(), 6) or re.search(r"不再|无需|无须|免除", t[e.start():v.start()]):
            contrary.append(s)
        else:
            full.append(s)
    settle(judge, doc, "P06", "employer.liability_range", full, [], contrary,
           "C公司 is liable within its 2,412.00 arrears to B公司", "", full_result="exact")


NOMINALISED_CLAIM = re.compile(r"[\"”」』’]?的?(主张|说法|抗辩|观点|理由|定性)")
PERFORMED = re.compile(r"以房抵债[^,:]{0,10}(已|已经)(实际)?(履行|履行完毕|完成|过户)")


def eval_p07(judge, doc):
    base = re.compile(r"(以房抵债|抵债协议|抵债)[^,:]{0,10}(尚未|未|没有|并未)(实际)?(履行|过户|交付|办理)|(抵债|G56)[^。]{0,30}履行[^。,:]{0,8}断裂")
    persist = re.compile(r"(欠付|¥" + Y_C_ARREARS + r")[^。]{0,20}(依旧|仍然|仍|依然|(并|尚)?未(因此)?消灭|不因此消灭|成立|存在)|(C公司|发包人|被告二)[^,:]{0,10}(仍|依然|仍然)[^,:]{0,10}(承担|欠付|负有)|欠付[^,:]{0,8}(认定为|应认定为)?存续|不能(免除|消灭)[^,:]{0,8}(C公司|发包人|被告二)[^,:]{0,6}(付款|支付)?(责任|债务|义务)")
    full, partial, contrary = [], [], []
    for s in doc.sentences + point_joined(doc):
        t = s["text"]
        if generic_excluded(t):
            continue
        p = PERFORMED.search(t)
        if p and not neg_near(t, p.start(1), 4):
            contrary.append(s)
            continue
        if not base.search(t):
            continue
        (full if persist.search(t) else partial).append(s)
    settle(judge, doc, "P07", "employer.offset_by_property", full, partial, contrary,
           "the property-offset agreement was not performed so C's 2,412 arrears persist",
           "property-offset agreement not performed, persistence of arrears not stated")


def eval_p08(judge, doc):
    owe = re.compile(r"拖欠|欠付|欠薪|被欠|未支付|未发放")
    confirm = re.compile(r"(劳动监察|监察大队|人社|劳动保障)[^,:]{0,12}(调查|确认|认定|核实|查实|查明)|调查确认|查证属实")
    full, partial, contrary = [], [], []
    for s in doc.sentences:
        t = s["text"]
        if generic_excluded(t) or not re.search(r"214(名|人)", t) or not re.search(r"¥" + Y_WAGES_OWED + r"(?!\d)", t):
            continue
        if re.search(r"不存在[^,:]{0,6}(拖欠|欠薪)|并未拖欠|没有拖欠|不拖欠|未被拖欠", t):
            contrary.append(s)
            continue
        if not owe.search(t):
            continue
        (full if confirm.search(t) else partial).append(s)
    settle(judge, doc, "P08", "wages.unpaid_confirmed", full, partial, contrary,
           "214 workers owed 613.80, confirmed by the labour inspection investigation",
           "214 workers owed 613.80 without the inspection confirmation")


def semicolon_joined(doc) -> list[dict]:
    """Clauses separated by ； inside one 。-sentence of one paragraph, joined when none of them was copy-masked."""
    out = []
    for line in doc.lines:
        if line["heading"] or line["table"] or line["zone"] not in ELIGIBLE_ZONES or line["masked"] or len(line["units"]) < 2:
            continue
        for whole in re.split(r"[。!?]", canon(line["raw"])):
            parts = [part for part in re.split(r";", whole) if part]
            if len(parts) >= 2 and all(part in line["units"] for part in parts):
                joined = ";".join(parts)
                out.append({"text": adopted_prefix(joined), "full": joined, "line": line, "joined": True})
    return out


def eval_p09(judge, doc):
    interrupt = re.compile(r"时效[^。]{0,12}中断|时效在[^。,:]{0,30}(多次|数次|先后|反复)?中断|中断[^,:]{0,6}时效")  # dates listed between
    not_barred = re.compile(r"未(超过|逾|罹于|过|届满|超出|经过)[^,:]{0,4}(诉讼)?时效|起诉未逾|在[^,:]{0,8}时效期间之?内|请求权未罹于"
                            r"|在[^,:]{0,8}三年的?(诉讼时效)?期间之?内|时效(期间)?(未|尚未)(经过|届满|超过)")
    barred = re.compile(r"(已|已经)(超过|逾|罹于|过)[^,:]{0,4}(诉讼)?时效|时效(已|已经)届满")
    cause = re.compile(r"催告|投诉|发函|主张权利|催收|G6[3-6](?!\d)")  # exhibit ids of the demand letters, notarised demands, letter to C and complaint receipt
    full, partial, contrary = [], [], []
    for s in doc.sentences + semicolon_joined(doc) + point_joined(doc):
        t = s["text"]
        if generic_excluded(t) or not re.search(r"原告|A公司|本案|起诉|请求权", t) or re.search(r"(?<![向对致给及和、])(B公司|C公司|D公司|被告)[^,:向对]{0,4}的?(催告|投诉|发函)", t):
            continue
        b = barred.search(t)
        if b and not neg_near(t, b.start(), 4):
            contrary.append(s)
            continue
        if not (interrupt.search(t) or (s.get("joined") and "时效" in t and re.search(r"中断事由", t))
                or ("时效" in t and re.search(r"(主张|催告|投诉|发函|催收)[^,:]{0,6}构成(诉讼时效)?中断", t))):
            continue
        if re.search(r"(未|不|没有|不能|不构成)[^,:]{0,4}中断", t):
            contrary.append(s)
            continue
        # not-barred conclusion + cause + a time anchor in the span; interruption + cause alone restates G66/G63
        if cause.search(t) and not_barred.search(t) and re.search(r"@\d{4}-\d{2}-\d{2}|\d{4}年", t):
            full.append(s)
    settle(judge, doc, "P09", "limitation.interrupted", full, partial, contrary,
           "demands and complaints interrupted limitation so the claim is not time-barred",
           "")


CORROBORATE = r"交叉印证|相互印证|互相印证|印证|吻合|相互对应|互相对应|相一致|相互一致|互相一致|彼此一致|互证|相互佐证|相互支撑|共同证明|对照使用|相互对照|互相对照|对照印证"


def cross_item(judge, doc, item_id, side_a, side_b, object_key, reason, extra_verb=None, structure=None):
    """R03 for cross-group corroboration: both evidence sides and a corroboration verb in one span."""
    verb = re.compile(CORROBORATE + ("|" + extra_verb if extra_verb else ""))
    full, contrary = [], []
    for s in doc.sentences:
        t = s["text"]
        if generic_excluded(t) or not re.search(side_a, t) or not re.search(side_b, t):
            continue
        # the comma clause that carries the corroboration verb must itself name one of the two sides
        # (the other side may be the sentence's carried subject); a verb whose clause names neither side binds other evidence
        m = None
        offset = 0
        first = clauses(t)[0]
        paired_first = re.search(f"({side_a})[^,:]{{0,40}}(与|和|及|同)[^,:]{{0,12}}({side_b})|({side_b})[^,:]{{0,40}}(与|和|及|同)[^,:]{{0,12}}({side_a})", first)
        for n, c in enumerate(clauses(t)):
            offset = t.find(c, offset)
            vm = verb.search(c)
            if vm and n > 0 and paired_first and not re.search(side_a, c) and not re.search(side_b, c) and not re.search(r"G\d+", c):
                m = verb.search(t, offset)  # the verb clause restates the paired exhibits of the first clause
                break
            if vm and (re.search(side_a, c) or re.search(side_b, c)):
                # the other side must be in the verb clause too, or be the sentence's carried subject (first clause)
                first = clauses(t)[0]
                if (re.search(side_a, c) or re.search(side_a, first)) and (re.search(side_b, c) or re.search(side_b, first)):
                    m = verb.search(t, offset)
                break
            offset += len(c)
        if not m:
            # parallel instruments '以A证明…，以B…' bound to one liability object combine the two evidences
            if structure and re.search(structure, t):
                full.append(s)
            continue
        (contrary if neg_near(t, m.start(), 6) else full).append(s)
    settle(judge, doc, item_id, object_key, full, [], contrary, reason, "")


def table_cells(raw: str) -> list[str]:
    return [cell.strip() for cell in raw.strip().strip("|").split("|")]


def burden_table(doc, target, wrong, topics):
    """A Markdown table with a 举证责任 column binds each row's burden cell to that row's defence topic;
    distinct topics whose burden cell places the burden on the defendants are aggregated over the table."""
    found, spans, run = set(), [], []
    runs = []
    for line in doc.lines + [{"table": False}]:
        if line.get("table") and line.get("zone") in ELIGIBLE_ZONES:
            run.append(line)
        else:
            if run:
                runs.append(run)
            run = []
    for rows in runs:
        header = [canon(c) for c in table_cells(rows[0]["raw"])]
        column = next((i for i, c in enumerate(header) if "举证责任" in c), None)
        if column is None:
            continue
        party_column = bool(re.search(r"举证责任(人|方|主体|归属|在)", header[column]))
        for line in rows[1:]:
            cells = table_cells(line["raw"])
            if column >= len(cells):
                continue
            cell = canon(cells[column])
            if doc.mask.copied(cell) or CANDIDATE.search(cell) or wrong.search(cell):
                continue
            m = target.search(cell)
            if m and (neg_near(cell, m.start(), 6) or re.search(r"不应|无需|无须|不承担|不负", cell[m.start():m.end()])):
                continue
            party_cells = [canon(c) for i, c in enumerate(cells) if i < len(header) and i != column and PARTY_COLUMN.search(header[i])]
            verb_cell = BURDEN_VERB_CELL.match(cell) or (ASSERTOR_VERB_CELL.match(cell) and any(OPPONENT_PARTY_CELL.match(c) for c in party_cells))
            if not m and not (party_column and OPPONENT_PARTY_CELL.match(cell)) and not BURDEN_CELL.match(cell) and not verb_cell:
                continue
            row = canon("".join(c for i, c in enumerate(cells) if i != column))
            hit = [n for n, topic in enumerate(topics) if re.search(topic, row)]
            if hit:
                found.update(hit)
                spans.append({"text": row + "|" + cell, "full": row + "|" + cell, "line": line})
    return found, spans


BURDEN_CELL = re.compile(r"^(应当?)?(由|在)(被告[一二]?|二被告|两被告|[BC]公司)([、,和与及](被告[一二]?|[BC]公司))*(承担|负担|负)?(举证责任)?$")
BURDEN_VERB_CELL = re.compile(r"^(应当?)?由(被告[一二]?|二被告|两被告|[BC]公司)([、,和与及](被告[一二]?|[BC]公司))*(举证)?证明")
ASSERTOR_VERB_CELL = re.compile(r"^(应当?)?由主张[^,:;。]{1,20}的(一方|当事人)(举证)?证明")
ASSERTOR = re.compile(r"由(主张方|主张者|主张的一方|主张该事实的一方)[^,:]{0,4}(承担|负担|负)[^,:]{0,4}举证责任")
ASSERTING_DEFENDANT = re.compile(r"(被告[一二]?|二被告|B公司|C公司)[^,:;]{0,6}就其?[^,:;]{0,4}主张")


BURDEN_LEAD = re.compile(r"(以下|下列|如下)[^。]{0,80}由(主张方|主张者|主张的一方|主张该事实的一方|二被告|两被告|被告[一二]?|B公司|C公司)[^,:;。]{0,4}(承担|负担|负)[^,:;。]{0,4}举证责任")


def burden_list(doc, wrong, topics):
    """The list form of a burden table - one lead sentence allocating the burden to the asserting party (and naming
    the defendants as the proposers), followed by list items each carrying one defence and its assertor '由B公司(、C公司)主张'."""
    found, spans = set(), []
    for i, line in enumerate(doc.lines):
        if line["zone"] != "burden" or line["heading"] or line["table"]:
            continue
        lead = canon(line["raw"])
        m = BURDEN_LEAD.search(lead)
        if not m or wrong.search(lead) or neg_near(lead, m.start(), 6) or not re.search(r"被告|B公司|C公司|对方", lead):
            continue
        for item in doc.lines[i + 1:]:
            if item["heading"] or item["zone"] != "burden" or item["table"] or not LIST_ITEM.match(item["raw"]):
                break
            text = canon(item["raw"])
            if not any(DEFENCE_ASSERTOR.match(u) for u in item["units"]) or wrong.search(text):
                continue
            hit = [n for n, topic in enumerate(topics) if re.search(topic, text)]
            if hit:
                found.update(hit)
                spans.append({"text": text, "full": text, "line": item})
        if spans:
            spans.insert(0, {"text": lead, "full": lead, "line": line})
            break
    return found, spans


def eval_p13(judge, doc):
    target = re.compile(r"举证责任[^,:]{0,8}(转移|转由|转至|应由|由|在于|在|归于|归)[^,:]{0,6}(二被告|被告|B公司|C公司)|(二被告|被告|B公司|C公司)[^,:]{0,12}(承担|负有|负担|负)[^,:]{0,6}举证责任")
    wrong = re.compile(r"举证责任[^,:]{0,8}(应由|由|转移至|在于)[^,:]{0,4}原告|原告[^,:]{0,8}(承担|负有)[^,:]{0,6}(上述抗辩|抗辩)[^,:]{0,6}举证责任")
    topics = [r"内部承包", r"管理费", r"代付|抵扣|抵销", r"质量", r"以房抵债|抵债"]
    # explicit 举证责任 only: a result-sense form is not read as an allocation
    full, partial, contrary = [], [], []
    for s in doc.sentences:
        t = s["full"]
        said = re.search(r"(主张|认为|称|声称|辩称)[^,:;]{0,20}举证责任", t)
        # '主张X的B公司负举证责任' names the burdened party by its claim; it is not an attribution
        if said and said.group(1) == "主张" and re.search(r"主张[^,:;]{0,16}的(二被告|被告[一二]?|B公司|C公司)", said.group(0)):
            said = None
        if said and re.match(r"主张(方|者|的一方|该事实的一方)", said.group(0)) and ASSERTOR.search(t) and ASSERTING_DEFENDANT.search(t):
            said = None
        if CANDIDATE.search(t) or REJECTED.search(t) or is_spray(t) or said:
            continue
        if wrong.search(t):
            contrary.append(s)
            continue
        m = target.search(t)
        if not m and ASSERTING_DEFENDANT.search(t):
            m = ASSERTOR.search(t)  # '由主张方承担举证责任' where the sentence names the asserting defendants
        if not m:
            continue
        if neg_near(t, m.start(), 6) or re.search(r"不应|无需|无须|不承担|不负", t[m.start():m.end()]):
            contrary.append(s)
            continue
        hit = {n for n, topic in enumerate(topics) if re.search(topic, t)}
        # >=3 defences and at least one beyond the two the dossier already hints (p[34] 内部承包, p[113] 管理费); no half tier
        if len(hit) >= 3 and hit & {2, 3, 4}:
            full.append(s)
    table_topics, table_spans = burden_table(doc, target, wrong, topics)
    if len(table_topics) >= 3 and table_topics & {2, 3, 4}:
        full.extend(table_spans)
    list_topics, list_spans = burden_list(doc, wrong, topics)
    if len(list_topics) >= 3 and list_topics & {2, 3, 4}:
        full.extend(list_spans)
    settle(judge, doc, "P13", "burden.defence_shift", full, partial, contrary,
           "burden of proof for the defendants' affirmative defences rests on the defendants",
           "")


P14_ELEMENTS = [r"实际施工人", r"(责任书|合同)[^。,]{0,12}无效|转包", r"工程量|¥97463000", r"已付|欠付金额|欠款|¥39423000|¥58040000|¥64766000",
                r"发包人|C公司|¥24120000", r"农民工", r"时效"]


P14_WORD_ELEMENTS = [r"实际施工人", r"(责任书|合同)[^。,]{0,12}无效|转包", r"工程量", r"已付|欠付金额|欠款|欠付", r"发包人|C公司", r"农民工", r"时效"]


def p14_excluded(t: str) -> bool:
    """R01 as generic_excluded, except that the >4-amount test is skipped when >=3 elements are named by word."""
    if CANDIDATE.search(t) or CONDITIONAL.search(t):
        return True
    if sum(1 for e in P14_WORD_ELEMENTS if re.search(e, t)) >= 3:
        fragments = [f for f in re.split(r"[、,/]", t) if f]
        short = [f for f in fragments if len(f) <= 8]
        return (len(fragments) >= 6 and len(short) >= 0.7 * len(fragments)) or len(t) > 400
    return is_spray(t)


def eval_p14(judge, doc):
    full, contrary = [], []
    for s in doc.sentences:
        t = s["text"]
        if p14_excluded(t):
            continue
        m = re.search(r"(达到|已达|满足|符合)[^,:]{0,6}高度(可能性|盖然性)|(按|依|依照|按照)[^,:]{0,60}高度(盖然性|可能性)的?(证明)?标准,?(证明|证实)", t)
        if not m:
            continue
        # the standard must be bound to >=3 named proven elements in the sentence; a bare boilerplate claim earns 0
        if not neg_near(t, m.start(), 6) and sum(1 for e in P14_ELEMENTS if re.search(e, t)) < 3:
            continue
        if neg_near(t, m.start(), 6):
            # a negated standard about the opponent's evidence ('仅凭…聘任文件…不能达到') is a different object
            if not re.search(r"仅凭|单凭|仅依|仅以|被告|B公司|C公司|对方", t):
                contrary.append(s)
        else:
            full.append(s)
    settle(judge, doc, "P14", "burden.standard_met", full, [], contrary,
           "plaintiff's proof reaches the high-probability standard", "", full_result="exact")


def eval_p15(judge, doc):
    nominal = re.compile(r"D公司[^。]{0,24}名义")
    incapable = re.compile(r"(无|不具备|不具有|没有|缺乏)[^,:]{0,4}(实际)?履约能力|未(实际)?(组织)?施工|并未实际(履行|施工)")
    capable = re.compile(r"D公司[^,:]{0,10}(具备|具有|有)[^,:]{0,4}履约能力|D公司[^,:]{0,6}(实际|组织)(履行|施工)")
    full, contrary = [], []
    for s in doc.sentences:
        t = s["text"]
        if generic_excluded(t) or "D公司" not in t:
            continue
        c = capable.search(t)
        if c and not NEG_NEAR.search(c.group(0)):
            contrary.append(s)
            continue
        if nominal.search(t) and incapable.search(t):
            full.append(s)
    settle(judge, doc, "P15", "parties.nominal_subcontractor", full, [], contrary,
           "D公司 is a nominal counterparty without performance capacity", "", full_result="exact")


# Format, section and order items; each all-or-nothing, bound to content.
REQ_PATTERNS = [
    ("admit", r"(质证|采信|采纳)[^。]{0,30}证据|证据[^。]{0,30}(予以)?(采信|采纳)"),
    ("constructor", r"认定[^。]{0,40}(原告|A公司)[^。]{0,30}实际施工人"),
    ("void", r"认定[^。]{0,60}(责任书|内部承包)[^。]{0,30}转包[^。]{0,60}(?<!不)(?<!非)无效"),
    ("b_pay", r"(B公司|被告一)[^。]{0,20}(支付|给付)[^。]{0,20}(工程款|欠款)[^。]{0,40}(¥97463000|实际完成工程量)[^。]{0,20}折价补偿"),
    ("c_range", r"(C公司|被告二)[^。]{0,30}欠付[^。]{0,30}¥24120000[^。]{0,10}(范围内|限度内)[^。]{0,10}承担"),
    ("workers", r"农民工[^。]{0,20}(优先|保护|保障)|(优先|保护|保障)[^。]{0,20}农民工|农民工[^。]{0,30}工资[^。]{0,40}先行清偿|先行清偿[^。]{0,30}农民工[^。]{0,6}工资"),
]


STATUTE_CITATION = re.compile(r"(依|依据|根据|按照)?《[^》]{1,40}》第[^,:;。《》]{1,12}条([、,和及]《[^》]{1,40}》第[^,:;。《》]{1,12}条)*")


def eval_p16(judge, doc):
    """Request set: all six Golden requests inside the request section, each executable with its object; B before C."""
    spans = [s for s in doc.sentences if s["line"]["zone"] == "request" and not s["line"]["table"] and not generic_excluded(s["text"])]
    text = STATUTE_CITATION.sub("", "。".join(s["text"] for s in spans))
    found = {k: re.search(p, re.sub(r"《[^》]*》", "", text) if k == "workers" else text) for k, p in REQ_PATTERNS}
    if not found["b_pay"]:  # payment order and compensation basis in two requests of the same request section
        pay = re.search(r"判令[^。]{0,20}(B公司|被告一)[^。]{0,30}(支付|给付)[^。]{0,30}(工程款|欠款|款项)", text)
        basis = re.search(r"折价补偿[^。]{0,20}(?<!不)(?<!非)(以|按|参照)[^。]{0,12}实际完成的?工程量|实际完成的?工程量[^。]{0,40}(折价补偿|计价依据)", text)
        if pay and basis:
            found["b_pay"] = pay
    if all(found.values()) and found["b_pay"].start() < found["c_range"].start():
        hits = [s for s in spans if any(re.search(p, s["text"]) for _k, p in REQ_PATTERNS)]
        return credit(judge, doc, "P16", 1.0, "exact", "six executable requests in the request section, B before C", hits, "requests.set")
    doc.p16_missing = {k for k, v in found.items() if not v} or {"order"}
    credit(judge, doc, "P16", 0, "missing", "request set incomplete, outside the request section, or C before B: "
           + ",".join(k for k, v in found.items() if not v), [], "requests.set")


def eval_p17(judge, doc):
    """Caption: title, 致 court, case number and all four parties with their procedural positions, before the body."""
    front = [l for l in doc.lines if l["zone"] == "front"]
    texts = [n01_clean(l["raw"]) for l in front]  # N01 only: the dossier's case number 'XXX' is not a gap marker here
    need = {"title": any(l["heading"] == "title" for l in front),
            "court": any(re.search(r"(?:致\s*[：:]?\s*)?[\u4e00-\u9fff某]{2,30}人民法院\s*[：:]?$", t) for t in texts),
            "case": any(re.search(r"案号\s*[：:]?\s*[（(]\d{4}[）)]\s*[\u4e00-\u9fff某]+\s*\w*号", t) for t in texts),
            "plaintiff": any(re.match(r"原告\s*[：:]?\s*A公司(?:[，,；;。\s]|$)", t) for t in texts),
            "defendant1": any(re.match(r"被告(?:一|1)\s*[：:]?\s*B公司(?:\s|$)", t) for t in texts),
            "defendant2": any(re.match(r"被告(?:二|2)\s*[：:]?\s*C公司(?:\s|$)", t) for t in texts),
            "third": any(re.match(r"第三人\s*[：:]?\s*D公司(?:\s|$)", t) for t in texts)}
    if all(need.values()):
        spans = [{"text": canon(l["raw"]), "line": l} for l in front]
        return credit(judge, doc, "P17", 1.0, "exact", "caption complete", spans, "format.caption", "N01")
    credit(judge, doc, "P17", 0, "missing", "caption element missing: " + ",".join(k for k, v in need.items() if not v), [], "format.caption")


GROUP_ORDINAL = re.compile(r"^(?:[（(][一二三四五六七1-7][）)]\s*)?(?:第)?([一二三四五六七]|[1-7])组")
PROOF_VERB = re.compile(r"确立|证明|证实|印证|锁定|确认|表明|显示|旨在|揭示|还原|承载的?(要素|要件)")


EXHIBIT_NAME = re.compile(r"《[^》]*》|(确认|证明)(单|书|表|函|文件|材料)|身份证明")
INVENTORY_SENTENCE = re.compile(r"^本组(证据)?(包括|包含|收录|计有|共有)(?![^。]*(用以|用于|旨在|拟)证明)")


def eval_p18(judge, doc):
    """Seven evidence groups in order 第一组..第七组, each with an unmasked adopted proof-purpose sentence."""
    order = [l for l in doc.lines if l["heading"] == "group" and GROUP_ORDINAL.match(l["group"])]
    ords = [("一二三四五六七".index(m.group(1)) if m.group(1) in "一二三四五六七" else int(m.group(1)) - 1)
            for l in order if (m := GROUP_ORDINAL.match(l["group"]))]
    spans = []
    ok = ords == list(range(7))
    if ok:
        for l in order:
            prose = [s for s in doc.sentences if s["line"]["group"] == l["group"] and s["line"]["zone"] == "group"
                     and not s["line"]["table"] and PROOF_VERB.search(EXHIBIT_NAME.sub("", s["text"])) and not generic_excluded(s["text"])
                     and not INVENTORY_SENTENCE.match(s["text"])]  # the verb is not read inside an exhibit name
            if not prose:
                ok = False
                break
            spans.append(prose[0])
    if ok:
        return credit(judge, doc, "P18", 1.0, "exact", "seven groups in order, each with its own proof purpose", spans, "format.group_order")
    credit(judge, doc, "P18", 0, "missing", f"group ordinals {ords} or a group without its own proof-purpose sentence", [], "format.group_order")


def eval_p19(judge, doc):
    """Section order 总述 -> 分组 -> 关联性 -> 举证责任 -> 请求事项, each section carrying adopted content."""
    kinds = {"overview": "overview", "parent": "groups", "group": "groups", "relation": "relation", "burden": "burden", "request": "request"}
    first, content = {}, {}
    for n, l in enumerate(doc.lines):
        if l["heading"] in kinds:
            first.setdefault(kinds[l["heading"]], n)
    for s in doc.sentences:
        k = kinds.get(s["line"]["zone"])
        if k:
            content.setdefault(k, s)
    seq = ["overview", "groups", "relation", "burden", "request"]
    ok = all(k in first and k in content for k in seq) and [first[k] for k in seq] == sorted(first[k] for k in seq)
    if ok:
        return credit(judge, doc, "P19", 1.0, "exact", "all five sections present in order with content", [content[k] for k in seq], "format.section_order")
    credit(judge, doc, "P19", 0, "missing", "missing or out-of-order section: " + ",".join(k for k in seq if k not in first or k not in content), [], "format.section_order")


def eval_p20(judge, doc):
    """Signature block closing the request section: A公司 as 原告/举证人 and 委托诉讼代理人 沈某, placed after at least one adopted
    request sentence. The date line is not an element: U19 is the gap unit (marker neither earns nor costs; a fabricated date is D08)."""
    close = [l for l in doc.lines if l["zone"] == "request" and not l["table"]]
    texts = [canon(l["raw"]) for l in close]
    party = next((n for n, t in enumerate(texts) if re.match(r"(原告|举证人)(\(盖章\))?:?A公司", t)), None)
    agents = [n for n,t in enumerate(texts) if re.match(r"(委托)?(诉讼)?代理人:",t)]
    agent_text = "".join(texts[n] for n in agents)
    named_agents = set(re.findall(r"(?:律师|代理人)?\s*([\u4e00-\u9fff]{1,3}某)", agent_text))
    # The dossier names two representatives. Their professional titles and
    # punctuation are open, but both supplied identities must be carried.
    agent = agents[0] if agents and {"沈某", "郑某"}.issubset(named_agents) else None
    body_lines = {id(s["line"]) for s in doc.sentences if s["line"]["zone"] == "request" and not s["line"]["label"] and not s["line"]["heading"]}
    first_request = next((n for n, l in enumerate(close) if id(l) in body_lines), None)
    need = {"party": party is not None, "agent": agent is not None,
            "after_request": first_request is not None and party is not None and first_request < party}
    if all(need.values()):
        spans = [{"text": texts[n], "line": close[n]} for n in (party, agent)]
        return credit(judge, doc, "P20", 1.0, "exact", "signature block after the requests", spans, "format.signature")
    credit(judge, doc, "P20", 0, "missing", "signature element missing: " + ",".join(k for k, v in need.items() if not v), [], "format.signature")


# An adopted error that already zeroed a weighted P item is not charged again. Contrary-assertion pairs: the D sentence is the
# contrary span that zeroed the P. Request pairs: the D sentence lies in the request section and the P16 element it corrupts is
# missing. Zero-weight P items never absorb.
ABSORB_CONTRARY = {"D11": ("P14",), "D03": ("P01",)}
ABSORB_REQUEST = {"D01": {"b_pay"}, "D03": {"constructor", "void"}, "D05": {"c_range"}, "D06": {"c_range"}}


def absorbed(judge, doc, item_id, span) -> str | None:
    for p in ABSORB_CONTRARY.get(item_id, ()):
        if float(judge.positives[p].get("weight", 0)) > 0 and any(
                c["line"] is span["line"] and (c.get("full", c["text"]) == span.get("full", span["text"]) or c["text"] == span["text"])
                for c in doc.zeroed.get(p, [])):
            return p
    need = ABSORB_REQUEST.get(item_id)
    if need and span["line"]["zone"] == "request" and float(judge.positives["P16"].get("weight", 0)) > 0 and need & doc.p16_missing:
        return "P16"
    return None


class Deductions:
    def __init__(self, judge: ProgramJudge, doc: Doc):
        self.judge, self.doc, self.counter = judge, doc, 0

    def decide(self, item_id, manifestations, key, root, reason, object_key):
        scans = ["obs.scan.document"]
        kept = [(span, detail) for span, detail in manifestations if not absorbed(self.judge, self.doc, item_id, span)]
        if manifestations and not kept:
            owners = sorted({absorbed(self.judge, self.doc, item_id, span) for span, _d in manifestations})
            self.judge.deduction(item_id, "not_triggered", scans, "error already zeroed " + "/".join(owners) + " (same damage counted once)")
            return
        manifestations = kept
        if not manifestations:
            self.judge.deduction(item_id, "not_triggered", scans, "error proposition not asserted")
            return
        occurrences, obs_ids, seen = [], [], set()
        for span, detail in manifestations:
            manifestation = f"{item_id}:{span['line']['locator']}:{detail}"
            if manifestation in seen:
                continue
            seen.add(manifestation)
            self.counter += 1
            obs = observe_spans(self.judge, self.doc, f"obs.{item_id}.m{self.counter}", [span], object_key, "error_span", "N01")
            obs_ids.append(obs)
            occurrences.append({"damage_instance_key": key, "causal_root_id": root, "manifestation_id": manifestation,
                                "observation_id": obs, "reason": detail})
        self.judge.deduction(item_id, "triggered", scans + obs_ids, reason, occurrences)


def shape_count(lines: list[dict]) -> int:
    """N08: characters of adopted opinion units, excluding headings, labels, copy-masked text and gap-marked clauses."""
    total = 0
    for line in lines:
        if line["heading"] or line["label"]:
            continue
        for unit in line["units"]:
            if unit == "⟦SPRAY⟧":
                total += len(n01_clean(line["raw"]))
                continue
            for clause in re.split(r"[,;。:]", unit):
                if GAP_TOKEN not in clause:
                    total += len(clause)
    return total


D14_REQUEST_INTEREST = re.compile(r"(判令|(?<!的)请求(?!权|未))[^。]{0,60}(支付|给付|计付|清偿)[^。]{0,40}利息")


def eval_deductions(judge: ProgramJudge, doc: Doc) -> None:
    d = Deductions(judge, doc)
    adopted = [s for s in doc.sentences if not generic_excluded(s["text"])]

    found = []
    for s in adopted:
        m = adopted_wrong_basis(s["text"])
        if m:
            found.append((s, "basis-" + m.group(2)))
    d.decide("D01", found, "valuation_basis_conceded", "R-valuation-basis",
             "adopts the 88% internal, B-recognised or nominal price as the compensation basis", "price.compensation_basis")

    concessive = re.compile(r"(即使|即便|纵使|就算|哪怕)[^。]{0,40}(按|依|以|参照)[^。]{0,24}(B公司|被告|对方)")
    found = [(s, "owed-" + value) for s in adopted if not concessive.search(s["text"])
             for value, _m in owed_assertions(s["text"]) if value not in OWED_REPLAY_SET]
    d.decide("D02", found, "owed_amount_misstated", "R-owed-amount",
             "states an amount owed by B公司 that is not replayable from 9,746.30 - 3,942.30", "payment.owed")

    found = []
    others = re.compile(
        r"(原告|A公司)[^,:]{0,6}(系|是|为|仅为)[^,:]{0,8}履行辅助人|"
        r"徐某[^,:]{0,6}(系|是|为)[^,:]{0,4}B公司(的)?(项目部)?(员工|职工|工作人员|人员)|"
        r"(原告|A公司)[^,:]{0,4}(不是|并非|不构成|不属于|不具备)[^,:]{0,8}实际施工人|"
        r"(不构成|并非|不属于)转包")
    for s in adopted:
        t = s["text"]
        v = VALID_INTERNAL.search(t)
        if v and internal_valid_adopted(t, v):
            found.append((s, "internal-contract-valid"))
            continue
        o = others.search(t)
        if o and REBUTTED_NP.search(t[max(0, o.start() - 24):o.start()]) and re.match(r"[^。]{0,40}的(抗辩|主张|说法|观点|理由)", t[o.end():]):
            o = None  # the conceded wording sits inside the defence the plaintiff rebuts
        if o and not (o.group(0).startswith(("原告", "A公司")) and "履行辅助人" in o.group(0) and neg_near(t, o.start(), 6)):
            found.append((s, "concession-" + o.group(0)[:8]))
    d.decide("D03", found, "contract_nature_conceded", "R-contract-nature",
             "concedes a valid internal contract, a non-transfer or A's non-constructor status", "contract_chain.internal_contract_nature")

    b_side = re.compile(
        r"管理费[^,:]{0,12}(应|应当|依约)(予以|予)?(扣减|扣除|扣|收取|抵扣)|"
        r"(代付|¥" + Y_WAGE_ADVANCE + r")[^,:]{0,14}(应|应当|可以|予以)?(全额|全部)(抵扣|扣减|抵销|冲抵)|"
        r"(扣减|扣除)[^,:]{0,6}管理费[^,:]{0,4}¥" + Y_MGMT_FEE + r"(?!\d)")
    found = []
    for s in adopted:
        m = b_side.search(s["text"])
        # a negation inside the match ('管理费无对价、不应扣') denies the deduction
        if m and not neg_near(s["text"], m.start() + len(m.group(0)) - 4, 8) and not re.search(
                r"(不|无需|无须|不再|并非)(应当?|予以|予|得|可以?)?(全额|全部)?(扣减|扣除|扣|收取|抵扣|抵销|冲抵)", m.group(0)):
            found.append((s, "b-deduction"))
    d.decide("D04", found, "b_deductions_conceded", "R-b-deductions",
             "concedes B's management-fee deduction or full wage-advance offset", "payment.deductions")

    released = re.compile(
        r"(C公司|发包人|被告二)[^,:]{0,10}(欠付|债务|工程款)[^,:]{0,6}(已|已经)(结清|消灭|清偿|付清)|"
        r"(C公司|被告二|发包人)[^,:]{0,6}(不再|无需|无须|不应|不)承担[^,:]{0,8}责任")
    found = []
    for s in adopted:
        t = s["text"]
        p = PERFORMED.search(t)
        # '以房抵债已履行的主张不能并存' names the opponent's claim, it does not adopt it
        if p and not neg_near(t, p.start(1), 4) and not NOMINALISED_CLAIM.match(t, p.end()):
            found.append((s, "offset-performed"))
            continue
        r = released.search(t)
        # '其不足以证明C公司的债务已消灭' negates the release (R02 negation window, as for the other D items)
        if r and not neg_near(t, r.start(), 8) and not NOMINALISED_CLAIM.match(t, r.end()):
            found.append((s, "c-released"))
    d.decide("D05", found, "employer_released", "R-employer-release",
             "concedes that the property offset discharged C公司 or that C公司 bears no liability", "employer.offset_by_property")

    c_entity = re.compile(r"C公司|被告二|发包人|二被告|两被告|被告一、被告二|B公司、C公司|B公司与C公司|B公司和C公司")
    full_amount = re.compile(r"¥(" + Y_OWED + "|" + Y_OWED_ADDBACK + "|" + Y_TOTAL + r")(?!\d)|全部(工程款|欠款)")
    found = []
    for s in adopted:
        for clause in clauses(s["text"]):
            e = c_entity.search(clause)
            if not e or "范围内" in clause or "限度内" in clause:
                continue
            tail = clause[e.end():]
            joint = re.search(r"(连带|共同)(清偿|支付|付款|赔偿|承担|责任)", tail)
            full = full_amount.search(tail) and re.search(r"支付|承担|清偿|给付", tail)
            hit = joint or full
            if hit and not NEG_NEAR.search(tail[:hit.start()][-8:] if joint else tail[-12:].replace("未付", "")):
                found.append((s, "c-overreach"))
                break
    d.decide("D06", found, "employer_liability_overreach", "R-employer-overreach",
             "asks C公司 to pay beyond its 2,412.00 arrears (joint, full or 5,804 liability)", "employer.liability_range")

    appraisal = re.compile(
        r"(司法鉴定|法院委托[^,:]{0,8}鉴定|鉴定机构)(意见|结论|报告)?[^,:]{0,12}(确认|认定|结论为|显示|证实|为)[^,:]{0,12}(¥" + Y_TOTAL + r"|工程造价|造价)|"
        r"(G45|G42|造价咨询报告|造价咨询意见)[^,:]{0,10}(系|为|属于|即)[^,:]{0,6}司法鉴定|"
        r"(造价|工程价款|¥" + Y_TOTAL + r")[^,:]{0,10}(已经|已|经)[^,:]{0,4}(司法鉴定|法院委托[^,:]{0,6}鉴定)[^,:]{0,4}(确认|认定|确定|证实)")
    found = []
    for s in adopted:
        t = s["text"]
        m = appraisal.search(t)
        if m and not neg_near(t, m.start(), 6) and not re.search(r"申请|启动|推动|拟|建议|尚未|未经|有待|待鉴定|应当进行|应进行", t):
            found.append((s, "appraisal"))
    d.decide("D07", found, "appraisal_fabricated", "R-appraisal",
             "describes a court appraisal or presents the unilateral cost report as a judicial appraisal", "price.appraisal_status")

    found = []
    for line in doc.lines:
        if line["heading"] or line["table"] or line["zone"] not in ELIGIBLE_ZONES:
            continue
        c = canon(line["raw"])
        if GAP_TOKEN in c:
            continue
        m = re.fullmatch(r"(日期|提交日期|落款日期)?:?@(\d{4}-\d{2}-\d{2})", c)
        # The dossier records the filing on 2024-07-22. Using that supported
        # filing date is not fabrication; any other definite signature date is.
        if m and m.group(2) != "2024-07-22":
            found.append(({"text": c, "line": line}, "date-" + m.group(2)))
    d.decide("D08", found, "submission_date_fabricated", "R-fabrication-date",
             "invents a concrete signature date the materials do not support instead of a gap marker", "signature.date")

    # Generic, symmetric error rules.
    everything = doc.sentences  # conditional and candidate sentences are scanned too: a conditional request or 待定 is itself the error
    opp = re.compile(r"被告|B公司|C公司|D公司|对方")

    found = []
    d11 = [r"(尚未|未能|没有|未)(达到|满足)[^。]{0,8}(证明)?标准", r"举证[^。]{0,8}薄弱", r"原告[^。]{0,12}(不请求|并不请求)[^。]{0,24}(认定|确定)",
           r"不将[^。]{0,24}表述为[^。]{0,4}(已经)?确定", r"(G\d+|该证据|本项)[^。]{0,40}(不能单独证明|不作为[^。]{0,10}(唯一|独立)[^。]{0,16}依据)", r"(视为|应视为)待定",
           r"(相对)?最为?薄弱", r"尚未证毕|未能证毕", r"(尚)?不足以单独(证明|推翻|对抗)"]  # contract trigger 'its weakest point', 'not proven', 'cannot alone prove'

    for s in everything:
        t = s["text"]
        for pat in d11:
            m = re.search(pat, t)
            if m and not opp.search(t[max(0, m.start() - 20):m.start()]):
                found.append((s, "adverse-" + m.group(0)[:6]))
                break
    d.decide("D11", found, "adverse_disclosure", "R-adverse-disclosure",
             "the plaintiff disclaims or downgrades its own core proof (not proven, 待定, weakest, not asked to be determined)", "adverse.disclosure")

    found = []
    d12 = re.compile(r"已(同步)?(提交|提供|附)[^。]{0,16}(原件|原始载体|载体原件|未剪辑|整理稿|存储介质)|附(有)?[^。,]{0,6}(盖章|签章)|倒签")
    for s in everything:
        m = d12.search(s["text"])
        if m and not neg_near(s["text"], m.start(), 6):
            found.append((s, "fabricated-" + m.group(0)[:6]))
    d.decide("D12", found, "procedure_fabricated", "R-fabrication-procedure",
             "asserts a submission, seal or backdating that no material records", "fabrication.procedure")

    found = []
    d13 = re.compile(r"(具有|存在|系|为|属于?|构成)[^。]{0,4}(通谋|串通)|明知[^。]{0,6}违法|为掩盖|知悉并接受|(完工|竣工)[^。]{0,6}质量合格")
    for s in adopted:
        m = d13.search(s["text"])
        if m and not re.search(r"不足以|不能|无法|并非|未|不", s["text"][max(0, m.start() - 12):m.start()]):
            found.append((s, "overclaim-" + m.group(0)[:6]))
    d.decide("D13", found, "qualifier_overclaimed", "R-overclaim",
             "turns a dossier qualifier (嫌疑, contested quality, unilateral notice) into an established fact", "overclaim.fact")

    found = []
    d14 = re.compile(r"(申请|请求(?!权))[^。]{0,16}(委托[^。]{0,8}鉴定|司法鉴定|造价鉴定|质量鉴定|调查取证|调取|责令[^。]{0,8}提交|出庭作证|证人出庭|证据保全|核验)|(提出|一并提出)[^。]{0,6}(下列|以下)?[^。]{0,4}申请|程序性申请")
    for s in everything:
        t = s["text"]
        m = d14.search(t)
        if m and not neg_near(t, m.start(), 6) and not re.search(r"(被告|B公司|C公司|对方)[^。,]{0,4}(申请|请求)", t[max(0, m.start() - 8):m.end()]):
            found.append((s, "extra-" + m.group(0)[:6]))
    d.decide("D14", found, "extra_or_conditional_requests", "R-extra-requests",
             "adds procedural applications outside the request set (appraisal, investigation, order to produce, witnesses, preservation, conditional requests)", "requests.extra")

    found = []
    d15 = re.compile(r"(不?认可|不否认|不持异议|无异议|有异议)[^。,]{0,10}(真实性|合法性|关联性)|(真实性|合法性|关联性)[^。,]{0,4}(不持异议|无异议|予以认可|不予认可)")
    for s in everything:
        m = d15.search(s["full"])
        if m:
            found.append((s, "three-properties"))
    d.decide("D15", found, "three_property_boilerplate", "R-three-properties",
             "issues 真实性/合法性/关联性 verdicts in an evidence-submission opinion (质证 rehearsal / 三性套话)", "scope.cross_examination")

    found = []
    for s in everything:
        m = re.search(r"(举证|办案|诉讼)策略|胜负(不在于|在于|的关键)", s["full"])
        if m:
            found.append((s, "strategy-note"))
    d.decide("D16", found, "internal_strategy_note", "R-strategy-note",
             "addresses an internal strategy note to the court", "scope.internal_note")

    masked = [(line, m) for line in doc.lines if not line["table"] and not line["heading"] and line["zone"] in ELIGIBLE_ZONES
              and not line["label"] and not EVIDENCE_ROW.match(canon(line["raw"])) for m in line["masked"] if len(m) >= 12]
    found = [({"text": m, "line": line}, "copy") for line, m in masked] if len(masked) >= 3 else []
    d.decide("D17", found, "bulk_material_copy", "R-bulk-copy",
             "three or more prose sentences copied verbatim from the dossier", "scope.material_copy")

    found = []
    for line in doc.lines:
        for token in re.findall(r"(?<![A-Za-z0-9])G(\d{1,4})(?!\d)", n01_clean(line["raw"]), flags=re.I):
            # The dossier overview says G1-G68, while its detailed third-group
            # table also carries the overlapping original identifiers through
            # G86. The supplied universe therefore includes G1-G86.
            if not 1 <= int(token) <= 86:
                found.append(({"text": "G" + token, "line": line}, "unauthorized-evidence-id"))
    d.decide("D18", found, "unauthorized_evidence_identifier", "R-evidence-universe",
             "introduces an evidence identifier outside the identifiers actually supplied in the dossier (G1-G86)", "evidence.identifier_universe")


SOURCE_ANCHORS = {
    "P01": (r"第三组|G17(?:\s*[-—至]\s*G?38)?", 1),
    "P02": (r"G(?:10|14)(?!\d)|项目内部承包责任书", 1),
    "P03": (r"9\s*,?\s*746\.30\s*万元|97463000", 1),
    "P04": (r"3\s*,?\s*942\.30\s*万元|39423000", 1),
    "P05": (r"672\.60\s*万元|6726000", 1),
    "P06": (r"2\s*,?\s*412(?:\.00)?\s*万元|24120000", 1),
    "P07": (r"G56|以房抵债", 1),
    "P08": (r"(?:214\s*名?|613\.80\s*万元|G5[7-9]|G60)", 1),
    "P09": (r"G6[3-6]|2023[-年]|2024[-年]", 1),
    "P10": (r"G(?:20|21|57|58)(?!\d)", 2),
    "P11": (r"G(?:27|43|44)(?!\d)|设计变更|签证|报审", 2),
    "P12": (r"G(?:16|56)(?!\d)|对账单|以房抵债", 2),
    "P13": (r"", 0),
    "P14": (r"", 0),
    "P15": (r"G(?:4|7|15)(?!\d)|D公司|第三人", 1),
    "P16": (r"5\s*,?\s*804(?:\.00)?\s*万元|58040000|6\s*,?\s*476\.60\s*万元|64766000|2\s*,?\s*412(?:\.00)?\s*万元|24120000", 2),
}


def source_anchor_fraction(item_id: str, quoted_spans: list[str]) -> float:
    """Deterministic evidence floor beneath the open semantic decision.

    The semantic judge decides legal equivalence. This floor independently
    requires the candidate evidence selected by that judge to carry dossier
    identifiers, figures or named instruments material to the proposition.
    """
    pattern, minimum = SOURCE_ANCHORS[item_id]
    if minimum == 0:
        return 1.0
    hits = {m.group(0) for text in quoted_spans for m in re.finditer(pattern, text, flags=re.I | re.S)}
    return 1.0 if len(hits) >= minimum else 0.0


def evaluate(registry: dict, judge: ProgramJudge, semantic=None) -> None:
    """Call positive() once per P and deduction() once per D."""
    if registry.get("parse_failure"):
        for item_id in judge.positives:
            judge.positive(item_id, 0.0, "obs.parse_failure", "artifact could not be parsed", "different")
        for item_id in judge.deductions:
            judge.deduction(item_id, "parse_failure", ["obs.parse_failure"], "artifact could not be parsed")
        return
    doc = registry["doc"]
    if semantic is None: raise RuntimeError("required source-bound semantic adjudication unavailable")
    for item_id,row in semantic["items"].items():
        spans=[{"text":q,"line":line} for q in row["quotes"] for line in doc.lines if q in line["raw"] or line["raw"] in q]
        fraction = min(float(row["fraction"]), source_anchor_fraction(item_id, row["quotes"]))
        reason = row["reason"] if fraction else row["reason"] + "; required dossier anchor absent from the cited candidate evidence"
        credit(judge,doc,item_id,fraction,"equivalent" if fraction==1 else "partial" if fraction else "missing",reason,spans,judge.positives[item_id]["object_key"])
    eval_p17(judge, doc)
    eval_p18(judge, doc)
    eval_p19(judge, doc)
    eval_p20(judge, doc)
    eval_deductions(judge, doc)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--contract", type=Path, default=CANONICAL_CONTRACT)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--debug", action="store_true", help="print zoned units instead of scoring")
    args = parser.parse_args()
    contract_path = args.contract.resolve()
    judge = ProgramJudge(load_contract(contract_path), args.artifact.resolve(), sha256(contract_path))
    registry = normalize(extract_raw(args.artifact.resolve()), judge)
    if args.debug:
        if not registry.get("parse_failure"):
            for line in registry["doc"].lines:
                print(line["zone"], line["heading"] or "-", line["locator"], "|", " || ".join(line["units"])[:200], "| masked", len(line["masked"]))
        return 0
    semantic=None
    if not registry.get("parse_failure"):
        import sys
        tests=next(p for p in Path(__file__).resolve().parents if (p/"semantic_judge.py").is_file())
        sys.path.insert(0,str(tests))
        from semantic_judge import adjudicate
        semantic=adjudicate("\n".join(line["raw"] for line in registry["doc"].lines),(tests/"semantic_source.json").read_text())
    evaluate(registry, judge, semantic)
    result=judge.finish()
    fractions={row["id"]:float(row["fraction"]) for row in result["items"]}
    essential={"P01","P02","P03","P04","P06","P09","P16","P17","P20"}
    disqualifying={"D01","D02","D03","D04","D05","D06","D07","D08","D11","D12","D13","D14","D15","D16","D17","D18"}
    damaged={item for instance in result.get("penalty_instances",[]) for item in instance.get("item_ids",[])}
    result["rewards"]={"strict":result["final_score"],
                       "lenient":float(all(fractions.get(item,0)>=.5 for item in essential) and not damaged.intersection(disqualifying))}
    result["score_breakdown"]={
        "substantive":{"items":"P01-P16","possible":0.90,
                       "earned":sum(float(row["earned"]) for row in result["items"] if int(row["id"][1:])<=16)},
        "filing_structure":{"items":"P17-P20","possible":0.10,
                            "earned":sum(float(row["earned"]) for row in result["items"] if int(row["id"][1:])>=17)},
        "retention":result["retention_multiplier"]}
    if semantic: result["semantic_judge"]=semantic
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
