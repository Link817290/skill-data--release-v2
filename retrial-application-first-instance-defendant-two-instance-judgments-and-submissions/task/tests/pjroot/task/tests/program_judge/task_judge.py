#!/usr/bin/env python3
"""Program Judge adapter: retrial application drafted for the first-instance defendant B公司.

Three explicit layers:
  extract_raw()  carrier records only (Markdown lines, or DOCX paragraphs with style names and table rows)
  normalize()    registered rules N00-N10: canonical tokens, gap folding, role aliases, quote masking,
                 region (front / request / grounds / closing) and grounds sub-topic (unseen / audit / adjust /
                 conclusion), sentence spans aligned between the canonical and the quote-masked text
  evaluate()     one positive() per P and one deduction() per D, using registered derivation rules R01-R09
                 for spray, adoption context, amount replay, conflicts and shape.

Targeted source-bound semantic judgement is required for the repaired propositions. Facts, aliases and thresholds come from rubric-contract.json
and the frozen Golden.
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

# Frozen task constants; each is visible in or derived from the case materials.
AMT_UNSEEN_TOTAL = Decimal("21404976.61")      # R04: sum of 13 item differences (甲路 selective 2-14) + 乙路 拦水埂
AMT_UNSEEN_JIA = Decimal("18829063.61")        # R04: 甲路 selective items 2-14, opinion 1 minus opinion 2
AMT_UNSEEN_JIA_TOTALS = Decimal("18533212")    # R04: report-total derivation (56380933-37184278-663443), partial
AMT_UNSEEN_TOTAL_TOTALS = Decimal("21109125")  # R04: report-total derivation plus 2575913, partial
AMT_LANSHUI = Decimal("2575913")
AMT_PRINCIPAL = Decimal("125806738.02")
AMT_FEE = Decimal("3544566.47")
AMT_AUDIT = Decimal("328446294.68")
AMT_JW_JIA, AMT_JW_YI = Decimal("5236264"), Decimal("5572253")
AMT_JW_SUM = AMT_JW_JIA + AMT_JW_YI
AMT_CW_JIA, AMT_CW_YI = Decimal("-2122630"), Decimal("-466942")
AMT_CW_SUM = AMT_CW_JIA + AMT_CW_YI
WRONG_UNSEEN = {Decimal("19196655"), Decimal("21772568")}          # includes 甲路 事项1 (挖除树根) already decided for B
WRONG_LANSHUI = {Decimal("5510870"), Decimal("6239007"), Decimal("5456461")}  # A公司-side quantities, not the adjudged item

GAP_MARKERS = [
    "[待补充]", "【待补充】", "[待填写]", "【待填写】", "[待核实]", "【待核实】", "[待定]", "【待定】",
    "[placeholder]", "材料未提供", "未提供", "待补充", "待填写", "待核实", "unspecified", "TBD",
]
GAP = "⟦GAP⟧"
MAX_PARAGRAPH = 700
FILL = "□"

REQUEST_ALIAS = re.compile(r"^(再审(申请)?请求(事项)?|(再审)?申请(再审)?(请求)?事项|请求事项|再审诉讼请求|申请请求)[:]?$")
GROUNDS_ALIAS = re.compile(r"^(申请再审的?)?(法定(事由|理由)|事实(与|和|及)理由(如下)?|再审(事由|理由)((及|与|和)(事实|理由))?|申请(再审)?(的)?(法定)?(理由|事由)((及|与|和)事实)?|理由(如下)?)[:]?$")
GROUND_CLASS = re.compile(r"缺乏证据证明|适用法律(确有)?错误|认定(基本)?事实|再审事由|§211")
REQUEST_VERB = re.compile(r"^(撤销|改判|判令|请求|依法|提审|指令|发回|本案|一审|二审|由|备位|核减|确认|驳回|变更)")
# D12: an inventory of documents said to accompany a filing that carries no attachments.
ATTACHMENT_HEAD = re.compile(
    r"^附(件|录|项)?\s*[:]|^(附件|附录|附项)[:]?$|"
    r"^(附件|附录|证据|材料)(及|和)?(提交前)?(核验事项|清单|目录|材料)|"
    r"^提交前(核验|检查)(事项|清单)?"
)
TOPIC_KEYS = {
    "unseen": re.compile(r"未见(拦水[埂梗])?实物|无实物|现场勘验|勘验|拦水[埂梗]|工程量"),
    "audit": re.compile(r"审计|结算依据|结算方式|启动鉴定|司法鉴定|鉴定程序|鉴定费|阻止条件"),
    "adjust": re.compile(r"调差|价格信息|造价信息|期刊|材料价格|信息价"),
    "conclusion": re.compile(r"^(结语|结论|综上.{0,20})$"),
}

NEG = r"不|未|没有|并非|非|无|否认|从未"
CANDIDATE = re.compile(r"可能|或许|也许|大概|不排除|抑或|存疑|有待|待定|倾向于|要么|二选一|或可|似乎")
CONDITIONAL = re.compile(r"如果|假如|倘若|假设|即便|即使|(?<![倘假])若(?!干)")
OTHER_ATTRIB = re.compile(
    r"(A公司|对方|有观点|有意见|有人|原判|原审|一审|二审|法院|判决|鉴定机构|鉴定人)[^,;:]{0,6}?"
    r"(认为|认定|主张|(?<![名简])称|辩称|声称|宣称|提出|表示|指出|所述|所称|以为)")
REJECT_AFTER = re.compile(r"(观点|主张|说法|理由|意见)[^,;。]{0,6}?(明显)?(不能成立|不成立|错误|有误|不应(予以)?采纳|不予采纳|站不住脚|缺乏依据|于法无据)")
REJECT_NEXT = re.compile(r"^(但|然而)?(该|此|上述|前述|这一|这种|以上)(观点|主张|说法|理由|意见)")

DATE_CN = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")
DATE_NUM = re.compile(r"(?<![\d.@¥])(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})日?(?![\d.])")
MONEY = re.compile(r"(负|-|−)?(?:人民币|RMB)?(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(亿元|万元|元)|(负|-|−)?¥(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(?:元)?")
MONEY_TOKEN = re.compile(r"¥(-?\d+(?:\.\d+)?)(w?)")
ARTICLE = re.compile(r"第([零〇一二两三四五六七八九十百千0-9]+)条")
ITEM = re.compile(r"第[(]?([一二三四五六七八九十]{1,3}|\d{1,2})[)]?项")
PERCENT_CN = re.compile(r"百分之([零〇一二两三四五六七八九十0-9.]+)")
CN_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CN_UNITS = {"十": 10, "百": 100, "千": 1000}

LEXICON = [
    "再审", "申请", "撤销", "改判", "核减", "未见实物", "无实物", "现场勘验", "勘验", "选择性意见", "意见一", "意见二",
    "拦水埂", "拦水梗", "甲路", "乙路", "推测", "推定", "证据", "质保期", "维护整改", "审计", "审计报告", "结算",
    "审核报告", "造价工程师", "资质", "土建", "法律依据", "阻止条件成就", "发包人", "鉴定费", "调差", "交委期刊",
    "建委期刊", "名称", "相近", "负值", "千万", "基本事实", "适用法律", "错误", "缺乏", "最高法", "发回重审",
    "事项", "差额", "合计", "判付", "本金", "比例", "水泥", "河沙", "石子", "钢筋", "混凝土", "通用", "材料",
    "§211", "item2", "item6",
]


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
            import docx
            from docx.table import Table
            from docx.text.paragraph import Paragraph

            document = docx.Document(str(artifact))
            p_index = t_index = 0
            for child in document.element.body.iterchildren():
                tag = child.tag.rsplit("}", 1)[-1]
                if tag == "p":
                    paragraph = Paragraph(child, document)
                    style = paragraph.style.name if paragraph.style is not None else ""
                    raw["records"].append({"locator": f"docx:body/p[{p_index}]", "text": paragraph.text, "md": False, "style": style})
                    p_index += 1
                elif tag == "tbl":
                    for r, row in enumerate(Table(child, document).rows):
                        cells = [cell.text for cell in row.cells]
                        raw["records"].append({"locator": f"docx:body/tbl[{t_index}]/tr[{r}]", "text": "|" + "|".join(cells) + "|", "md": False, "style": ""})
                    t_index += 1
        except Exception as exc:  # noqa: BLE001 - any carrier failure is a parse failure
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
            raw["records"].append({"locator": f"md:line[{number}]", "text": line, "md": True, "style": ""})
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


def money_token(sign: str | None, integer: str, fraction: str | None, unit: str | None) -> str:
    try:
        value = Decimal(integer.replace(",", "") + (fraction or ""))
    except InvalidOperation:
        return integer
    rounded = ""
    if unit == "万元":
        value *= 10000
        rounded = "w"
    elif unit == "亿元":
        value *= 100000000
        rounded = "w"
    if sign:
        value = -value
    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "¥" + text + rounded


def n01_clean(text: str) -> str:
    """N01: NFKC fold, drop zero-width characters, Markdown decoration and table pipes, remove whitespace."""
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
    text = re.sub(r"\*{3,}", "XXX", text)
    text = text.replace("**", "").replace("__", "").replace("`", "")
    text = text.replace("〔", "(").replace("〕", ")").replace("【", "[").replace("】", "]")
    return re.sub(r"\s+", "", text)


def n06_gap(text: str) -> str:
    """N06: fold declared gap markers and desensitised XXX / **** / ___ runs into one gap token."""
    for marker in sorted(GAP_MARKERS, key=len, reverse=True):
        text = text.replace(unicodedata.normalize("NFKC", marker).replace("【", "[").replace("】", "]"), GAP)
    return re.sub(r"_{3,}|×{2,}|X{3,}|x{3,}|Y{3,}|\*{3,}", GAP, text)


def n02_n05(text: str) -> str:
    """N03 dates, N02 money, N04 percentages, N05 statute articles and items into canonical tokens."""
    text = DATE_CN.sub(lambda m: f"@{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}", text)
    text = DATE_NUM.sub(lambda m: f"@{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}", text)
    text = re.sub(r"(\d{4})年(\d{1,2})月(?!\d)", lambda m: f"@{int(m.group(1)):04d}-{int(m.group(2)):02d}", text)

    def money(m: re.Match) -> str:
        if m.group(2) is not None:
            return money_token(m.group(1), m.group(2), m.group(3), m.group(4))
        return money_token(m.group(5), m.group(6), m.group(7), None)

    text = MONEY.sub(money, text)

    def percent(m: re.Match) -> str:
        token = m.group(1)
        number = token if re.fullmatch(r"[\d.]+", token) else cn_number(token)
        return f"{number}%" if number is not None else m.group(0)

    text = PERCENT_CN.sub(percent, text)

    def article(m: re.Match) -> str:
        number = cn_number(m.group(1))
        return f"§{number}" if number is not None else m.group(0)

    text = ARTICLE.sub(article, text)
    # "第(二)、(六)项" / "第二、六项" enumerations: expand to item tokens before single items
    text = re.sub(r"第[(]?([一二三四五六七八九十]{1,3}|\d{1,2})[)]?(?:项)?[、,和及与]第?[(]?([一二三四五六七八九十]{1,3}|\d{1,2})[)]?项",
                  lambda m: f"item{cn_number(m.group(1))}、item{cn_number(m.group(2))}", text)

    def item(m: re.Match) -> str:
        number = cn_number(m.group(1))
        return f"item{number}" if number is not None else m.group(0)

    return ITEM.sub(item, text)


def n08_alias(text: str) -> str:
    """N08: procedural role aliases fold to entity keys (再审申请人/申请人 -> B公司; 被申请人 -> A公司)."""
    text = re.sub(r"被申请人(\(A公司\)|A公司)?", "⁠PA⁠", text)
    text = re.sub(r"(再审)?申请人(\(B公司\)|B公司)?", "B公司", text)
    text = text.replace("⁠PA⁠", "A公司")
    text = text.replace("最高人民法院", "最高法").replace("最高院", "最高法")
    return text


def n07_mask_quotes(text: str) -> str:
    """N07: characters inside quotation marks are masked (same length) so quoted words are never the author's assertion."""
    out = list(text)
    inside_ascii = False
    depth = 0
    for index, char in enumerate(text):
        if char == '"':
            inside_ascii = not inside_ascii
            continue
        if char in "“「‘":
            depth += 1
            continue
        if char in "”」’":
            depth = max(0, depth - 1)
            continue
        if inside_ascii or depth > 0:
            out[index] = FILL
    return "".join(out)


def heading_level(record: dict, clean: str) -> int | None:
    """N09: heading level from DOCX heading styles, Markdown hashes, 一、 numbering, (一) numbering or a whole bold line."""
    raw = unicodedata.normalize("NFKC", record["text"])
    if len(clean) > 150:
        return None
    style = record.get("style") or ""
    m = re.match(r"^(Heading|标题)\s*(\d)$", style)
    if m:
        return int(m.group(2))
    if record.get("md"):
        m = re.match(r"^\s*(#{1,6})\s", raw)
        if m:
            return len(m.group(1))
    if re.match(r"^[一二三四五六七八九十]+[、.]", clean):
        return 10
    if re.match(r"^\([一二三四五六七八九十]+\)", clean):
        return 20
    if record.get("md") and re.fullmatch(r"\s*\*\*[^*]+\*\*\s*[:：]?\s*", raw):
        return 30
    return None


def strip_numbering(clean: str) -> str:
    return re.sub(r"^([一二三四五六七八九十]+[、.]|\([一二三四五六七八九十]+\)|\d+[.、])", "", clean)


def single_road(text: str) -> str | None:
    """R10: the one road name a heading or topic sentence declares; None when it names both or neither."""
    named = {name for name in ("甲路", "乙路") if name in text}
    return named.pop() if len(named) == 1 else None


def heading_topics(clean: str) -> set[str]:
    body = strip_numbering(clean)
    if TOPIC_KEYS["conclusion"].match(body):
        return {"conclusion"}
    return {name for name, rx in TOPIC_KEYS.items() if name != "conclusion" and rx.search(body)}


def raw_token_soup(raw_text: str) -> bool:
    """R01: eight or more whitespace/comma-separated short fragments are keyword soup (numbers with spaces merged first)."""
    text = unicodedata.normalize("NFKC", raw_text).replace("**", "").strip()
    text = re.sub(r"(?<=\d),(?=\d{3})", "", text)
    text = re.sub(r"^\s*(#{1,6}|[-*+>]|\d+[.)])\s+", "", text)
    text = re.sub(r"\s*([\d.,:;()%/¥-])\s*", r"\1", text)
    text = re.sub(r"(\d)\s+(年|月|日|元|万元|亿元|项|条)", r"\1\2", text)
    fragments = [frag for frag in re.split(r"[\s,，;；]+", text) if frag]
    short = [frag for frag in fragments if len(frag) <= 8]
    if len(fragments) >= 8 and len(short) >= 0.7 * len(fragments):
        return True
    listed = [frag for frag in re.split(r"[\s、,，;；]+", text) if frag]
    return len(listed) >= 12 and len([f for f in listed if len(f) <= 6]) >= 0.75 * len(listed)


def is_list_spray(text: str) -> bool:
    fragments = re.split(r"[、,]", text)
    short = [frag for frag in fragments if len(frag) <= 6]
    return len(fragments) >= 7 and len(short) >= 0.75 * len(fragments)


def lexicon_density(text: str) -> float:
    text = re.sub(r"[A-C]公司|" + FILL + "+|" + GAP + r"|¥-?\d+(?:\.\d+)?w?|\d+(?:\.\d+)?%|@[\d-]+", "", text)
    if len(text) < 12:
        return 0.0
    covered = [False] * len(text)
    for term in sorted(LEXICON, key=len, reverse=True):
        start = 0
        while True:
            pos = text.find(term, start)
            if pos < 0:
                break
            if not any(covered[pos:pos + len(term)]):
                for k in range(pos, pos + len(term)):
                    covered[k] = True
            start = pos + 1
    return sum(covered) / len(text)


def spray_sentence(canon: str, bare: str) -> bool:
    """R01: short-fragment list, lexicon-dense span, or more than four distinct amounts / three percentages cannot be adopted."""
    if is_list_spray(bare):
        return True
    if lexicon_density(bare) >= 0.6:
        return True
    return len(set(MONEY_TOKEN.findall(canon))) > 4 or len(set(re.findall(r"\d+(?:\.\d+)?%", canon))) > 3


def split_sentences(canon: str, bare: str) -> list[tuple[str, str]]:
    parts = []
    start = 0
    for index, char in enumerate(bare):
        if char in "。;!?":
            if index > start:
                parts.append((canon[start:index], bare[start:index]))
            start = index + 1
    if start < len(bare):
        parts.append((canon[start:], bare[start:]))
    return [p for p in parts if p[1]]


class Doc:
    """Normalized retrial application: paragraphs with region, grounds sub-topic, canonical and masked sentences."""

    def __init__(self, raw: dict):
        self.raw = raw
        self.artifact = str(raw["artifact"])
        merged = self._reflow(raw["records"])
        self.paras: list[dict] = []
        region = "front"
        stack: list[tuple[int, frozenset, str | None]] = []
        for record in merged:
            clean = n01_clean(record["text"])
            if not clean:
                continue
            canon = n08_alias(n02_n05(n06_gap(clean)))
            bare = n07_mask_quotes(canon)
            level = heading_level(record, clean)
            body = strip_numbering(clean).rstrip(":")
            is_heading = False
            if clean.startswith("此致"):
                region = "closing"
            elif region != "closing":
                if level is not None or len(body) <= 16:
                    if REQUEST_ALIAS.match(body):
                        region, stack, is_heading = "request", [], True
                    elif GROUNDS_ALIAS.match(body):
                        region, stack, is_heading = "grounds", [], True
                if not is_heading and level is not None:
                    if region == "request" and not REQUEST_VERB.match(strip_numbering(canon)):
                        styled = level < 10 or level == 30
                        if GROUND_CLASS.search(canon) or (styled and heading_topics(clean)):
                            region, stack = "grounds", []
                    if region == "grounds":
                        is_heading = True
                        own = heading_topics(clean)
                        while stack and stack[-1][0] >= level:
                            stack.pop()
                        parent = stack[-1][1] if stack else frozenset()
                        parent_road = stack[-1][2] if stack else None
                        topics = frozenset(own) if own else parent
                        stack.append((level, topics, single_road(clean) or parent_road))
            topics = stack[-1][1] if (region == "grounds" and stack) else frozenset()
            heading_road = stack[-1][2] if (region == "grounds" and stack) else None
            spray = raw_token_soup(record["text"]) or len(clean) > MAX_PARAGRAPH
            sentences = split_sentences(canon, bare)
            # R10: the paragraph's governing road is the one its topic sentence names, else the one its
            # enclosing grounds heading names. It binds tokens that carry no road name of their own.
            road = single_road(sentences[0][0]) if sentences else None
            self.paras.append({
                "locator": record["locator"], "raw": record["text"], "clean": clean, "canon": canon, "bare": bare,
                "region": region, "topics": topics, "heading": is_heading, "spray": spray,
                "road": road or heading_road, "sentences": sentences,
            })

    @staticmethod
    def _reflow(records: list[dict]) -> list[dict]:
        """N00: Markdown hard-wrapped lines join one paragraph when the previous line does not end a sentence or label."""
        merged: list[dict] = []
        for record in records:
            text = record["text"]
            previous = merged[-1] if merged else None
            if (record.get("md") and previous and previous.get("md") and previous["text"].strip() and text.strip()
                    and not re.search(r"([。!！?？:：;；|]|[。!！?？][」”\")）])\s*$", unicodedata.normalize("NFKC", previous["text"]))
                    and not re.match(r"^\s*(#{1,6}\s|[-*+>]\s|\||\d+[.、)]|[一二三四五六七八九十]+、|[（(][一二三四五六七八九十\d]+[)）]|此致|\*\*)", text)
                    and not re.match(r"^\s*(#{1,6}\s|\||[-*+>]\s|\*\*[^*]+\*\*\s*$)", previous["text"])):
                first = previous["locator"].split("-")[0].rstrip("]")
                last = record["locator"].split("[")[-1].rstrip("]")
                merged[-1] = {**previous, "text": previous["text"].rstrip() + text.strip(), "locator": f"{first}-{last}]"}
                continue
            merged.append(dict(record))
        return merged

    def loc(self, para: dict, object_key: str, field: str, prefix: str) -> Locator:
        return Locator(locator_id=f"{prefix}:{para['locator']}", artifact_path=self.artifact,
                       container_type=self.raw["carrier"] or "unknown", container_path=para["locator"],
                       object_key=object_key, field=field, observed=para["raw"][:400])

    def canon_loc(self, source: Locator, para: dict, rule: str) -> Locator:
        return Locator(locator_id=source.locator_id + ":canon", artifact_path=self.artifact,
                       container_type=source.container_type, container_path=source.container_path,
                       object_key=source.object_key, field=source.field + ".canonical",
                       observed=para["canon"][:400], evidence_origin="lossless_canonicalized",
                       source_locator_ids=(source.locator_id,), normalization_rule_id=rule)

    def doc_loc(self, object_key: str, prefix: str, observed: str) -> Locator:
        return Locator(locator_id=f"{prefix}:document", artifact_path=self.artifact,
                       container_type=self.raw["carrier"] or "unknown", container_path="document",
                       object_key=object_key, field="scan_state", observed=observed)


def observe_paras(judge: ProgramJudge, doc: Doc, obs_id: str, paras: list[dict], object_key: str,
                  field: str, rule: str, derived: tuple[str, str] | None = None) -> str:
    evidence: list[Locator] = []
    seen: set[str] = set()
    for para in paras:
        if para["locator"] in seen:
            continue
        seen.add(para["locator"])
        source = doc.loc(para, object_key, field, obs_id)
        evidence.extend([source, doc.canon_loc(source, para, rule)])
    if derived is not None:
        evidence.append(Locator(locator_id=f"{obs_id}:derived", artifact_path=doc.artifact,
                                container_type=doc.raw["carrier"] or "unknown", container_path="derived",
                                object_key=object_key, field=field + ".replay", observed=derived[1][:400],
                                evidence_origin="deterministically_derived",
                                source_locator_ids=tuple(loc.locator_id for loc in evidence),
                                derivation_rule_id=derived[0]))
    return judge.observe(obs_id, "identified", evidence)


def normalize(raw_registry: dict, judge: ProgramJudge) -> dict:
    """Register carrier-independent observations; the runtime owns their states."""
    if raw_registry.get("parse_error"):
        locator = Locator("parse:artifact", str(raw_registry["artifact"]), raw_registry.get("carrier") or "unknown",
                          "artifact", "retrial_application", "carrier", raw_registry["parse_error"])
        judge.observe("obs.parse_failure", "parse_failure", [locator])
        return {"parse_failure": True}
    doc = Doc(raw_registry)
    for region in ("front", "request", "grounds", "closing"):
        paras = [p for p in doc.paras if p["region"] == region]
        obs = f"obs.scan.{region}"
        if paras:
            observe_paras(judge, doc, obs, paras, f"document.{region}", "paragraph_text", "N09")
        else:
            judge.observe(obs, "confirmed_missing", [doc.doc_loc(f"document.{region}", obs, f"no {region} paragraphs")])
    return {"parse_failure": False, "doc": doc}


# ---------------------------------------------------------------------------
# Layer 3: P/D decisions
# ---------------------------------------------------------------------------
def amounts(text: str) -> list[tuple[Decimal, bool]]:
    out = []
    for m in MONEY_TOKEN.finditer(text):
        try:
            out.append((Decimal(m.group(1)), m.group(2) == "w"))
        except InvalidOperation:
            continue
    return out


def amount_is(text: str, target: Decimal) -> bool:
    """R04: amount replay; exact to one yuan, or to ten thousand yuan when written in 万元/亿元."""
    for value, rounded in amounts(text):
        if abs(value - target) <= (Decimal(10000) if rounded else Decimal(1)):
            return True
    return False


def neg_before(bare: str, position: int, window: int = 6) -> bool:
    """R02: a negation inside the clause and within `window` characters before the key token."""
    clause_start = max(bare.rfind(",", 0, position), bare.rfind(":", 0, position)) + 1
    start = max(clause_start, position - window)
    return re.search(NEG, bare[start:position]) is not None


def attributed(bare: str, position: int) -> bool:
    """R02: the clause holding the key (or a preceding clause ending in a reporting verb) is attributed to another speaker."""
    contrast = [m.end() for m in re.finditer(r"但是|但|然而|实际上|事实上|可见|故|因此|据此", bare) if m.end() <= position]
    seg_start = max(contrast, default=0)
    clause_start = max(bare.rfind(",", seg_start, position), bare.rfind(";", seg_start, position), seg_start - 1) + 1
    clause = bare[clause_start:position]
    if OTHER_ATTRIB.search(clause):
        return True
    if clause_start - 1 <= seg_start:
        return False
    previous_start = max(bare.rfind(",", seg_start, clause_start - 1), seg_start - 1) + 1
    previous = bare[previous_start:clause_start - 1]
    return re.search(r"(A公司|对方|原判|原审|一审|二审|法院|判决)[^,;]{0,6}(认为|认定|主张|称|辩称|指出|表示)[:]?$", previous) is not None


def excluded(sentences: list[tuple[str, str]], index: int, position: int, allow_conditional: bool = False) -> str | None:
    canon, bare = sentences[index]
    if CANDIDATE.search(bare):
        return "candidate"
    if not allow_conditional and CONDITIONAL.search(bare[:position]):
        return "conditional"
    if attributed(bare, position):
        return "attributed"
    if REJECT_AFTER.search(bare[position:]) or (index + 1 < len(sentences) and REJECT_NEXT.search(sentences[index + 1][1])):
        return "rejected"
    if spray_sentence(canon, bare):
        return "spray"
    return None


class Finding:
    def __init__(self):
        self.hits: list[tuple[dict, float]] = []
        self.contrary: list[dict] = []
        self.misplaced: list[dict] = []
        self.para: dict = {}


def scan(doc: Doc, allowed, span: int, test, finding: Finding) -> None:
    """R03: window test over sentences of each paragraph; spans outside the allowed region/topic only feed the misplaced list."""
    for para in doc.paras:
        if para["spray"]:
            continue
        in_scope = allowed(para)
        finding.para = para
        sentences = para["sentences"]
        for i in range(len(sentences)):
            window = sentences[i:i + span]
            outcome = test(sentences, i, window)
            if outcome is None:
                continue
            kind, fraction = outcome
            if not in_scope:
                if kind == "hit":
                    finding.misplaced.append(para)
                continue
            if kind == "hit":
                finding.hits.append((para, fraction))
            elif kind == "contrary":
                finding.contrary.append(para)


def settle(judge, doc, item_id, finding: Finding, object_key: str, rule: str, reason_full: str, reason_partial: str,
           replay: str | None = None) -> None:
    """R08: contrary adopted claims beside hits make the item ambiguous; otherwise the best fraction counts."""
    obs = f"obs.{item_id}"
    hits = finding.hits
    if hits and finding.contrary:
        paras = list({p["locator"]: p for p in [h[0] for h in hits] + finding.contrary}.values())
        judge.observe(obs, "ambiguous", [doc.loc(p, object_key, "candidate_span", obs) for p in paras])
        judge.positive(item_id, 0.0, obs, "adopted and contrary propositions both present", "different")
        return
    if hits:
        best = max(f for _, f in hits)
        paras = [h[0] for h in hits if h[1] == best]
        derived = (replay, f"{item_id} replay over {len(paras)} span(s)") if replay else None
        observe_paras(judge, doc, obs, paras, object_key, "proposition_span", rule, derived)
        if best >= 1.0:
            judge.positive(item_id, 1.0, obs, reason_full, "equivalent")
        else:
            judge.positive(item_id, best, obs, reason_partial, "partial")
        return
    if finding.contrary:
        observe_paras(judge, doc, obs, finding.contrary, object_key, "contrary_span", rule)
        judge.positive(item_id, 0.0, obs, "only the contrary proposition is adopted", "different")
        return
    if finding.misplaced:
        observe_paras(judge, doc, obs, finding.misplaced, object_key, "misplaced_span", "N09")
        judge.positive(item_id, 0.0, obs, "proposition appears only outside its section", "different")
        return
    judge.observe(obs, "confirmed_missing", [doc.doc_loc(object_key, obs, "proposition not found")])
    judge.positive(item_id, 0.0, obs, "proposition not found", "missing")


BRIDGE_LEAD = re.compile(r"^(在此基础上|基于上述|基于此|据此|由此)|"
                         r"^(该|此|上述|前述|这一)[^,;。]{0,8}(认定|归责|理由|结论|规则)")


class BridgedDoc:
    """R03b: two-paragraph argument blocks. A non-heading grounds paragraph that opens with a continuation connective
    is read together with the immediately preceding non-heading paragraph of the same region and sub-topic."""

    def __init__(self, doc: "Doc"):
        self.paras: list[dict] = []
        for prev, cur in zip(doc.paras, doc.paras[1:]):
            if (cur["region"] == prev["region"] == "grounds" and not cur["heading"] and not prev["heading"]
                    and cur["topics"] == prev["topics"] and BRIDGE_LEAD.match(cur["clean"])):
                self.paras.append({**cur, "locator": f"{prev['locator']}+{cur['locator']}", "raw": prev["raw"] + "\n" + cur["raw"],
                                   "canon": prev["canon"] + cur["canon"], "bare": prev["bare"] + cur["bare"],
                                   "spray": prev["spray"] or cur["spray"], "sentences": prev["sentences"] + cur["sentences"]})


def joined(window: list[tuple[str, str]]) -> tuple[str, str]:
    return "".join(c + "。" for c, _ in window), "".join(b + "。" for _, b in window)


def in_grounds(topic: str):
    def allowed(para: dict) -> bool:
        if para["region"] != "grounds":
            return False
        topics = para["topics"]
        if not topics:
            return True
        if len(topics) >= 3:
            return False
        return topic in topics
    return allowed


def in_request(para: dict) -> bool:
    return para["region"] == "request"


def adopted_at(window, rx: re.Pattern, allow_conditional=False, neg_window=6):
    """First adopted occurrence of a relation token (on masked text) in a window: ('ok', idx, pos);
    ('neg', None, None) when the only occurrences are negated; None otherwise."""
    negated = False
    for idx, (canon, bare) in enumerate(window):
        for m in rx.finditer(bare):
            if excluded(window, idx, m.start(), allow_conditional) is not None:
                continue
            if neg_window and neg_before(bare, m.start(), neg_window):
                negated = True
                continue
            return ("ok", idx, m.start())
    return ("neg", None, None) if negated else None


JIA = re.compile(r"甲路")
YI = re.compile(r"乙路")


def road_before(text: str, position: int, gap: int = 40, fallback: str | None = None) -> str | None:
    """R10: object binding: the nearest road name (甲路/乙路) within `gap` characters before a value or item token.
    When `fallback` is given and no road name occurs anywhere before the token, the paragraph's governing road
    (its topic sentence's or its section heading's road) binds it instead."""
    window = text[max(0, position - gap):position]
    best, road = -1, None
    for name in ("甲路", "乙路"):
        pos = window.rfind(name)
        if pos > best:
            best, road = pos, name
    if road is None and fallback is not None and not JIA.search(text[:position]) and not YI.search(text[:position]):
        return fallback
    return road


def bound_amount(text: str, target: Decimal, road: str | None, gap: int = 40) -> bool:
    """R04 + R10: an amount replay that is bound to the expected road when a road is required."""
    for m in MONEY_TOKEN.finditer(text):
        try:
            value, rounded = Decimal(m.group(1)), m.group(2) == "w"
        except InvalidOperation:
            continue
        if abs(value - target) <= (Decimal(10000) if rounded else Decimal(1)):
            masked = n07_mask_quotes(text)
            clause_start = max(masked.rfind(",", 0, m.start()), masked.rfind(";", 0, m.start()), masked.rfind("。", 0, m.start())) + 1
            if re.search(r"没有|并非|不是|并无|不存在|并不|不会|未使", masked[max(clause_start, m.start() - 40):m.start()]):
                continue
            if road is None or road_before(text, m.start(), gap) == road:
                return True
    return False


def bound_token(text: str, rx: str, road: str, gap: int = 40, fallback: str | None = None) -> bool:
    return any(road_before(text, m.start(), gap, fallback) == road for m in re.finditer(rx, text))


def eval_p01(judge, doc):
    """P01: items (2) and (6) of CPL art. 211, unioned over the application's adopted art. 211 citation sentences."""
    cited: dict[int, list[dict]] = {}
    contrary: list[dict] = []
    misplaced: list[dict] = []
    for para in doc.paras:
        if para["spray"]:
            continue
        in_scope = para["region"] in ("front", "grounds")
        sentences = para["sentences"]
        for i, (canon, bare) in enumerate(sentences):
            for m in re.finditer(r"§211(?!\d)", bare):
                if excluded(sentences, i, m.start()) is not None:
                    continue
                # R01: the spray rule counts every item the citation lists, so the window must reach the end of
                # the enumeration (it still stops at 规定/申请再审/为由 or the next article token).
                tail = re.split(r"规定|申请再审|为由|§", bare[m.end():m.end() + 240])[0]
                items = {int(x) for x in re.findall(r"item(\d+)", tail)}
                items |= {cn_number(x) for x in re.findall(r"\(([一二三四五六七八九十]{1,3})\)", tail)}
                if len(items) > 3 or not items & {2, 6}:
                    continue
                if not in_scope:
                    misplaced.append(para)
                    continue
                if neg_before(bare, m.start(), 30):
                    contrary.append(para)
                    continue
                for item in items & {2, 6}:
                    cited.setdefault(item, []).append(para)
    finding = Finding()
    finding.contrary = contrary
    finding.misplaced = misplaced
    if cited:
        fraction = 1.0 if set(cited) >= {2, 6} else 0.5
        for paras in cited.values():
            for para in paras:
                finding.hits.append((para, fraction))
    settle(judge, doc, "P01", finding, "grounds.statutory_basis", "N05",
           "retrial grounds cite CPL art. 211 items (2) and (6)", "only one of CPL art. 211 items (2) and (6) is cited")


def eval_p02(judge, doc):
    """P02: revocation of the second-instance judgment and first-instance item 1, unioned over adopted request sentences."""
    finding = Finding()
    second_paras, item1_paras = [], []
    for para in doc.paras:
        if para["spray"]:
            continue
        sentences = para["sentences"]
        for i, (canon, bare) in enumerate(sentences):
            keep = re.search(r"维持(原判|二审|一审)", bare)
            # R02 (same rule as D01): a request sentence whose own operative demand is 撤销/改判/变更/核减
            # only delimits the scope of that revision when it also says 维持; the contrary posture is not adopted.
            if keep and re.search(r"撤销|改判|变更|核减", bare[:keep.start()]):
                keep = None
            if keep and excluded(sentences, i, keep.start()) is None and not neg_before(bare, keep.start(), 4):
                if para["region"] == "request":
                    finding.contrary.append(para)
                continue
            m = re.search(r"撤销", bare)
            if not m or excluded(sentences, i, m.start()) is not None or neg_before(bare, m.start(), 4):
                continue
            tail = bare[m.end():]
            second = re.search(r"二审|民终|高级人民法院|终审", tail) is not None
            item1 = re.search(r"(一审|民初|中级人民法院|原审)[^;。]{0,40}item1|原判第一项|判决主文第一项", tail) is not None
            if not second and not item1:
                continue
            if para["region"] != "request":
                if second:
                    finding.misplaced.append(para)
                continue
            if second:
                second_paras.append(para)
            if item1:
                item1_paras.append(para)
    if second_paras:
        fraction = 1.0 if item1_paras else 0.5
        for para in second_paras + item1_paras:
            finding.hits.append((para, fraction))
    settle(judge, doc, "P02", finding, "request.revocation_scope", "N05",
           "request revokes the second-instance judgment and item 1 of the first-instance judgment",
           "request revokes the second-instance judgment without limiting the first-instance revocation to item 1")


def eval_p03(judge, doc):
    finding = Finding()
    verb = re.compile(r"改判|核减|减少|扣减|扣除|少付|少支付|不予支付|无需支付|不再支付|减去|减至|调减")

    def test(sentences, i, window):
        canon, bare = sentences[i]
        m = verb.search(bare)
        if not m or excluded(sentences, i, m.start()) is not None or neg_before(bare, m.start(), 4):
            return None
        if amount_is(canon, AMT_UNSEEN_TOTAL) or (re.search(r"减至|变更为|改判为|调整为", bare) and amount_is(canon, AMT_PRINCIPAL - AMT_UNSEEN_TOTAL)):
            return ("hit", 1.0)
        if amount_is(canon, AMT_UNSEEN_TOTAL_TOTALS):
            return ("hit", 0.5)
        if re.search(r"未见(拦水[埂梗])?实物|无实物", canon) and re.search(r"核减|扣减|扣除|减少", bare) and not amounts(canon):
            return ("hit", 0.5)
        return None

    scan(doc, in_request, 1, test, finding)
    settle(judge, doc, "P03", finding, "request.reduction_amount", "N02",
           "request asks to reduce the payable price by the 未见实物 difference 21,404,977",
           "request reduces the 未见实物 portion without the replayed amount, or with the report-total derivation",
           replay="R04")


def semantic_item(judge, doc, item_id, allowed, object_key):
    """Apply one request-bound semantic decision to exact in-scope candidate paragraphs."""
    decision = doc.semantic_verdict["items"][item_id]
    fraction = float(decision["fraction"])
    obs = f"obs.{item_id}"
    if fraction:
        paragraphs = [
            para for para in doc.paras if allowed(para)
            and any(quote in para["raw"] or para["raw"] in quote for quote in decision["quotes"])
        ]
        if not paragraphs:
            raise ValueError(f"{item_id} semantic evidence is not bound to its declared section")
        observe_paras(judge, doc, obs, paragraphs, object_key, "proposition_span", "N07")
        judge.positive(item_id, fraction, obs, decision["reason"],
                       "equivalent" if fraction == 1 else "partial")
        return
    judge.observe(obs, "confirmed_missing", [doc.doc_loc(object_key, obs, decision["reason"])])
    judge.positive(item_id, 0.0, obs, decision["reason"], "missing")


def eval_p04(judge, doc):
    semantic_item(judge, doc, "P04", in_request, "request.appraisal_fee")


def eval_p05(judge, doc):
    finding = Finding()
    anchor = re.compile(r"勘验|记载|载明|显示|选择性意见|意见二|鉴定(意见|机构|人)")

    def test(sentences, i, window):
        canon, bare = joined(window)
        if not re.search(r"未见(拦水[埂梗])?实物|无实物|未见.{0,4}实物", canon):
            return None
        for k, (c1, b1) in enumerate(window):
            for m in re.finditer(r"记载|载明|显示|出具|发现", b1):
                if neg_before(b1, m.start(), 3) and excluded(window, k, m.start()) is None:
                    return ("contrary", 0)
        hit = adopted_at(window, anchor, neg_window=0)
        if not hit or hit[0] != "ok":
            return None
        governing = finding.para.get("road")
        a = bound_token(canon, r"事项2[至到~\-—]14|2[至到~\-—]14项|事项二至十四|选择性(鉴定)?(意见)?事项", "甲路", fallback=governing)
        b = bound_token(canon, r"拦水[埂梗]", "乙路", fallback=governing)
        if a and b:
            return ("hit", 1.0)
        if a or b:
            return ("hit", 0.5)
        return None

    scan(doc, in_grounds("unseen"), 2, test, finding)
    settle(judge, doc, "P05", finding, "unseen.inspection_evidence", "N07",
           "on-site inspection recorded 未见实物 for 甲路 selective items 2-14 and 乙路 拦水埂 (selective opinion 2)",
           "on-site 未见实物 evidence bound to only one of the two objects")


def eval_p06(judge, doc):
    finding = Finding()
    relation = re.compile(r"差额|合计|核减|扣减|相差|共计|差")

    def test(sentences, i, window):
        canon, bare = joined(window)
        if not re.search(r"未见(拦水[埂梗])?实物|无实物|意见一|意见二|选择性意见", canon):
            return None
        hit = adopted_at(window, relation, neg_window=0)
        if not hit or hit[0] != "ok":
            return None
        jia = bound_amount(canon, AMT_UNSEEN_JIA, "甲路")
        total = amount_is(canon, AMT_UNSEEN_TOTAL)
        if jia and total:
            return ("hit", 1.0)
        if jia or total or amount_is(canon, AMT_UNSEEN_JIA_TOTALS) or amount_is(canon, AMT_UNSEEN_TOTAL_TOTALS):
            return ("hit", 0.5)
        return None

    scan(doc, in_grounds("unseen"), 2, test, finding)
    settle(judge, doc, "P06", finding, "unseen.difference_calculation", "N02",
           "甲路 selective items 2-14 difference 18,829,064 and total with 乙路 拦水埂 21,404,977 replayed",
           "only the total, only the 甲路 subtotal, or the report-total derivation is stated", replay="R04")


def eval_p07(judge, doc):
    finding = Finding()

    def test(sentences, i, window):
        canon, bare = sentences[i]
        pcts = [Decimal(x) for x in re.findall(r"(\d+(?:\.\d+)?)%", canon)]
        if not any(Decimal("16.5") <= p <= Decimal("17.5") for p in pcts):
            return None
        m = re.search(r"\d+(?:\.\d+)?%", bare)
        if not m or excluded(sentences, i, m.start()) is not None:
            return None
        if neg_before(bare, m.start(), 30):
            return ("contrary", 0)
        if amount_is(canon, AMT_PRINCIPAL) or re.search(r"(判付|判令支付|应付|欠付)[^,;。]{0,6}(工程款)?本金|工程款本金", bare):
            return ("hit", 1.0)
        return None

    scan(doc, in_grounds("unseen"), 1, test, finding)
    settle(judge, doc, "P07", finding, "unseen.share_of_principal", "N04",
           "the 未见实物 difference is about 17% of the adjudged principal 125,806,738.02", "", replay="R04")


def eval_p08(judge, doc):
    finding = Finding()
    obj = re.compile(r"可能(发生)?(改变|变化)|可能(被|遭)(村民)?(破坏|损毁)|情况可能|距[^。]{0,16}交付[^。]{0,12}(近一年|较长|一年)")
    guess = re.compile(r"推测|推定|臆测|猜测|主观(推断|臆断)|假定")
    lack = re.compile(r"(缺乏|没有|无)(任何)?(的)?(客观)?证据|无证据证明|证据不足|未(能)?举证")

    def test(sentences, i, window):
        canon, bare = joined(window)
        if not obj.search(canon):
            return None
        g = adopted_at(window, guess, neg_window=4)
        if g and g[0] == "neg":
            return ("contrary", 0)
        l_hit = adopted_at(window, lack, neg_window=0)
        g_ok = bool(g and g[0] == "ok")
        l_ok = bool(l_hit and l_hit[0] == "ok")
        if g_ok and l_ok:
            return ("hit", 1.0)
        if g_ok or l_ok:
            return ("hit", 0.5)
        return None

    scan(doc, in_grounds("unseen"), 2, test, finding)
    settle(judge, doc, "P08", finding, "unseen.speculation_rebuttal", "N07",
           "the court's 可能发生改变 reasoning is speculation replacing evidence, with no evidence the objects existed",
           "only one of the speculation characterisation and the lack-of-evidence point")


def eval_p09(judge, doc):
    finding = Finding()
    distinct = re.compile(r"性质(迥异|不同|有别)|不同(的)?(事实|问题|性质|情形)|混淆|并非同一|不能(等同|涵盖|替代|适用)|不属于|有本质区别|区别于|而非")

    def test(sentences, i, window):
        canon, bare = joined(window)
        if not re.search(r"质保|质量保修|保修期|缺陷责任期", canon):
            return None
        if not re.search(r"不存在|无实物|未见(拦水[埂梗])?实物|根本没有|并未(施工|实施)|未(施工|实施)|没有实物", canon):
            return None
        hit = adopted_at(window, distinct, neg_window=3)
        if hit and hit[0] == "ok":
            return ("hit", 1.0)
        if hit and hit[0] == "neg":
            return ("contrary", 0)
        return None

    scan(doc, in_grounds("unseen"), 2, test, finding)
    settle(judge, doc, "P09", finding, "unseen.warranty_distinction", "N07",
           "warranty-period repair concerns built but defective works, which differs from works that do not exist", "")


def eval_p10(judge, doc):
    finding = Finding()
    done = re.compile(r"(已|已经)(实际)?(完成|作出|出具)|(?<!审)核定|审定")  # R10b: 审核定案表 is a document name, not 核定
    rebut = re.compile(r"矛盾|不符|错误|并非(没有|无)|不能成立|有误|相悖")

    def test(sentences, i, window):
        canon, bare = joined(window)
        if not YI.search(canon) or not re.search(r"审计|审核报告", canon):
            return None
        if re.search(r"乙路[^。]{0,20}(未|没有|尚未)(完成|作出)(审计|审核)", bare):
            c = adopted_at(window, re.compile(r"(未|没有|尚未)(完成|作出)(审计|审核)"), neg_window=0)
            if c and c[0] == "ok":
                return ("contrary", 0)
        d = adopted_at(window, done, neg_window=3)
        if not (d and d[0] == "ok"):
            return None
        r = adopted_at(window, rebut, neg_window=0)
        r_ok = bool(r and r[0] == "ok")
        amt = bound_amount(canon, AMT_AUDIT, "乙路", 90)
        if amt and r_ok:
            return ("hit", 1.0)
        if amt or r_ok:
            return ("hit", 0.5)
        return None

    scan(doc, in_grounds("audit"), 3, test, finding)
    settle(judge, doc, "P10", finding, "audit.yilu_audit_completed", "N02",
           "乙路 audit completed with 核定 328,446,294.68, contradicting the court's 无审计结论 finding",
           "乙路 audit completion stated without either the replayed amount or the contradiction", replay="R04")


def eval_p11(judge, doc):
    finding = Finding()
    relation = re.compile(r"(缺乏|没有|无)(明确)?(的)?法律(依据|规定)|未(指明|列明|明确)[^,;。]{0,10}(条款|规定|依据)|"
                          r"不(当然)?(导致|影响|因)[^。]{0,16}(无效|效力|消灭)|不能(据此|因此)?(整体)?否定|独立(的)?审计(行为)?|混淆")

    def test(sentences, i, window):
        canon, bare = joined(window)
        # R03: the qualification and the report are coreferent terms of one proposition; a paragraph that
        # names both anywhere satisfies the gate even when its sentences state them apart.
        scope = canon + finding.para.get("canon", "")
        if not re.search(r"注册专业|造价工程师|造价师|资质", scope) or not re.search(r"审计报告|审核报告", scope):
            return None
        hit = adopted_at(window, relation, neg_window=0)
        if hit and hit[0] == "ok":
            return ("hit", 1.0)
        for k, (canon1, bare1) in enumerate(window):
            m = re.search(r"(资质|注册专业)[^。]{0,24}(导致|致使|因而|故)[^。]{0,12}(审计|审核)报告[^。]{0,8}(无效|不具有法律效力)", bare1)
            if m and excluded(window, k, m.start()) is None and not re.search(r"(不|未|并非)[^。]{0,3}(导致|致使)", bare1):
                return ("contrary", 0)
        return None

    scan(doc, in_grounds("audit"), 2, test, finding)
    settle(judge, doc, "P11", finding, "audit.engineer_qualification", "N07",
           "the cost engineer's registration specialty does not by law invalidate the audit report", "")


def eval_p12(judge, doc):
    finding = Finding()
    rule = re.compile(r"阻止条件成就|发包人原因|(该|上述|此|这一)规则")
    late = re.compile(r"A公司[^。]{0,24}(@2024-07|迟延|延迟|怠于|迟至|方才?|才)[^。]{0,16}(补充)?(移交|提交|送审|报送)")
    inapplicable = re.compile(r"不成立|不适用|不具备|不能适用|而非B公司|并非B公司|不能归(责|咎)于B公司|不应由B公司|错误")
    contrary_rx = re.compile(r"(B公司|发包人)[^。]{0,10}(原因|过错)[^。]{0,10}(导致|致使|造成)[^。]{0,10}甲路[^。]{0,10}未(能)?(完成)?(审计|审核)")

    def test(sentences, i, window):
        canon, bare = joined(window)
        has_late = False
        if JIA.search(canon):
            for k, (c1, b1) in enumerate(window):
                m = late.search(b1)
                if m and road_before(b1, m.start() + 1, 40, finding.para.get("road")) != "甲路" and "甲路" not in m.group(0):
                    m = None
                if m and excluded(window, k, m.start()) is None and not neg_before(b1, m.start(), 6):
                    has_late = True
                    break
        if not has_late:
            for k, (c1, b1) in enumerate(window):
                m = contrary_rx.search(b1)
                if m and excluded(window, k, m.start()) is None and not neg_before(b1, m.start(), 6):
                    return ("contrary", 0)
            return None
        r = adopted_at(window, inapplicable, neg_window=0)
        if rule.search(canon) and r and r[0] == "ok":
            return ("hit", 1.0)
        return ("hit", 0.5)

    scan(doc, in_grounds("audit"), 3, test, finding)
    scan(BridgedDoc(doc), in_grounds("audit"), 3, test, finding)
    settle(judge, doc, "P12", finding, "audit.obstruction_rule_inapplicable", "N08",
           "the 发包人不正当阻止条件成就 rule fails because A公司 itself supplemented 甲路 audit materials late",
           "A公司's late 甲路 submission is stated without tying it to the obstruction rule")


def eval_p13(judge, doc):
    semantic_item(judge, doc, "P13", in_grounds("audit"), "audit.fee_premise")


def eval_p14(judge, doc):
    semantic_item(judge, doc, "P14", in_grounds("adjust"), "adjust.periodical_name")


def reduced_amount(text: str, magnitude: Decimal, road: str | None, gap: int = 30) -> bool:
    """R10c: an unsigned amount whose sign is carried by a reduction verb (扣减/核减/调减/减少) within six characters before it."""
    for m in MONEY_TOKEN.finditer(text):
        try:
            value, rounded = Decimal(m.group(1)), m.group(2) == "w"
        except InvalidOperation:
            continue
        if abs(value - magnitude) <= (Decimal(10000) if rounded else Decimal(1)):
            if re.search(r"扣减|核减|调减|减少", text[max(0, m.start() - 6):m.start()]):
                if road is None or road_before(text, m.start(), gap) == road:
                    return True
    return False


def eval_p15(judge, doc):
    semantic_item(judge, doc, "P15", in_grounds("adjust"), "adjust.amount_comparison")


def eval_p16(judge, doc):
    finding = Finding()
    relation = re.compile(r"关联(有限|不大|甚微)|无(必然|直接)?(关联|关系)|并非公路(工程)?专用|不(因|以)[^,;。]{0,8}公路工程|与[^。]{0,12}公路工程[^。]{0,8}(无关|关系不大)")

    def test(sentences, i, window):
        canon, bare = joined(window)
        mats = len(set(re.findall(r"水泥|河沙|石子|钢筋|混凝土", canon)))
        if mats < 2 or not re.search(r"通用|一般|普通|常规", canon):
            return None
        hit = adopted_at(window, relation, neg_window=3)
        if hit and hit[0] == "ok":
            return ("hit", 1.0)
        if hit and hit[0] == "neg":
            return ("contrary", 0)
        return None

    scan(doc, in_grounds("adjust"), 2, test, finding)
    settle(judge, doc, "P16", finding, "adjust.general_materials", "N07",
           "the adjusted materials are general building materials with little link to the road-project character", "")


def eval_p17(judge, doc):
    finding = Finding()

    def test(sentences, i, window):
        canon, bare = sentences[i]
        if re.fullmatch(r"(此致)?(致)?(中华人民共和国)?最高法[:]?", bare):
            return ("hit", 1.0)
        return None

    scan(doc, lambda p: p["region"] == "closing" or (p["region"] == "front" and re.fullmatch(r"(致)?(中华人民共和国)?最高法[:]?", p["bare"]) is not None),
         1, test, finding)
    settle(judge, doc, "P17", finding, "closing.receiving_court", "N08",
           "the application is addressed to the Supreme People's Court, one level above the High Court", "")


# ------------------------------ deductions ---------------------------------
def adopted_hits(doc: Doc, rx: re.Pattern, regions=None, neg_window=6, allow_conditional=False):
    """Adopted (non-negated, non-attributed, non-candidate, non-spray) matches of rx over masked sentences."""
    out = []
    for para in doc.paras:
        if para["spray"] or (regions and para["region"] not in regions):
            continue
        sentences = para["sentences"]
        for i, (canon, bare) in enumerate(sentences):
            for m in rx.finditer(bare):
                if excluded(sentences, i, m.start(), allow_conditional) is not None:
                    continue
                if neg_window and neg_before(bare, m.start(), neg_window):
                    continue
                out.append((para, i, m))
                break
    return out


def charge(judge, doc, item_id, hits, object_key, reason, key_of, rule="N08", scan="grounds"):
    if not hits:
        judge.deduction(item_id, "not_triggered", [f"obs.scan.{scan}"], reason + ": not asserted")
        return
    obs_ids, occurrences = [], []
    for n, (para, i, m, detail) in enumerate(hits):
        obs = f"obs.{item_id}.{n}"
        observe_paras(judge, doc, obs, [para], object_key, "error_span", rule)
        obs_ids.append(obs)
        key = key_of(detail)
        occurrences.append({"damage_instance_key": key, "causal_root_id": f"root.{key}",
                            "manifestation_id": f"{item_id}:{para['locator']}:{n}", "observation_id": obs,
                            "reason": f"{reason}: {detail}"})
    judge.deduction(item_id, "triggered", obs_ids, reason, occurrences)


def eval_d01(judge, doc):
    hits = []
    for para in doc.paras:
        clean = para["clean"]
        if para["region"] in ("front", "closing"):
            if re.match(r"^再审申请人(\([^)]{0,20}\))?[:,]?(A公司|C公司)", clean) or re.match(r"^被申请人(\([^)]{0,20}\))?[:,]?B公司", clean):
                hits.append((para, 0, None, "party role reversed"))
    for para, i, m in adopted_hits(doc, re.compile(r"维持(原判|二审判决|一审判决)|驳回B公司(的)?再审申请"), regions=("request",), neg_window=4):
        # R02: a request sentence whose own operative demand is 撤销/改判/变更/核减 only delimits the
        # scope of that revision when it also says 维持; the reversed posture is not adopted.
        if re.search(r"撤销|改判|变更|核减", para["sentences"][i][1][:m.start()]):
            continue
        hits.append((para, i, m, "request adopts maintaining the judgment"))
    charge(judge, doc, "D01", hits, "document.posture", "application drafted for the wrong side", lambda d: "posture_reversed")


def eval_d12(judge, doc):
    hits = []
    for para in doc.paras:
        if para["region"] == "grounds" and "conclusion" in para["topics"]:
            hits.append((para, 0, None, "standalone-conclusion-after-completed-grounds"))
        elif para["region"] == "closing" and ATTACHMENT_HEAD.match(para["clean"]):
            hits.append((para, 0, None, "attachment-inventory"))
    charge(judge, doc, "D12", hits, "closing.attachments",
           "the filing adds a redundant conclusion or an enclosure/checklist outside the filing boundary",
           lambda d: "out_of_boundary_tail", scan="closing")


def eval_d02(judge, doc):
    hits = []
    for para in doc.paras:
        if para["region"] != "closing":
            continue
        line = para["bare"][2:] if para["clean"].startswith("此致") else para["bare"]
        if line and "法院" in line and "最高法" not in line and len(line) <= 30:
            hits.append((para, 0, None, line))
            break
    charge(judge, doc, "D02", hits, "closing.court", "retrial application addressed to a court other than the Supreme People's Court",
           lambda d: "wrong_receiving_court")


def eval_d03(judge, doc):
    hits = []
    for para, i, m in adopted_hits(doc, re.compile(r"§(200|207|198|179)(?!\d)"), neg_window=4):
        canon, bare = para["sentences"][i]
        if re.search(r"再审|民事诉讼法|民诉法", bare):
            hits.append((para, i, m, m.group(0)))
    charge(judge, doc, "D03", hits, "grounds.statutory_basis", "retrial ground cites a superseded CPL article number",
           lambda d: "superseded_retrial_article", rule="N05")


def eval_d04(judge, doc):
    hits = []
    for para in doc.paras:
        if para["spray"] or para["region"] not in ("request", "grounds"):
            continue
        sentences = para["sentences"]
        for i, (canon, bare) in enumerate(sentences):
            if not re.search(r"未见(拦水[埂梗])?实物|无实物|核减|扣减|应扣", canon) or amount_is(para["canon"], AMT_UNSEEN_JIA):
                continue
            m = re.search(r"核减|扣减|差额|合计|共计|应扣|相差", bare)
            if not m or excluded(sentences, i, m.start()) is not None:
                continue
            vals = {v for v, _ in amounts(canon)}
            if vals & WRONG_UNSEEN and not amount_is(canon, AMT_UNSEEN_JIA) and not amount_is(canon, AMT_UNSEEN_TOTAL):
                hits.append((para, i, m, "未见实物 reduction includes 甲路 事项1 already decided for B公司"))
            elif re.search(r"拦水[埂梗]", canon) and vals & WRONG_LANSHUI and not amount_is(canon, AMT_LANSHUI):
                hits.append((para, i, m, "乙路 拦水埂 reduction uses a quantity not adjudged"))
    charge(judge, doc, "D04", hits, "unseen.reduction_amount", "wrong 未见实物 reduction amount adopted",
           lambda d: "wrong_unseen_reduction_amount", rule="N02")


def eval_d05(judge, doc):
    hits = []
    rx = re.compile(r"(B公司|发包人|发包方)[^,;。]{0,10}(原因|过错|怠于|未及时|未能及时|迟延)[^。]{0,16}(甲路|审计|送审|结算)")
    for para, i, m in adopted_hits(doc, rx, regions=("grounds", "request"), neg_window=0):
        canon, bare = para["sentences"][i]
        before = bare[max(0, m.start() - 20):m.start()]
        if (re.search(r"(原判|原审|一审|二审|法院|判决|A公司)[^。]{0,10}(以|因|认为|认定|称|主张|判令|理由)", before)
                or re.search(r"(理由(是|为)|认为|认定|以|称|即)[:]?$", before) or re.search(r"为由|的理由|前提", bare[m.end():m.end() + 20])):
            continue
        lead = bare[max(0, m.start() - 8):m.start() + len(m.group(1)) + 12]
        if re.search(r"(并非|不是|不系|非|而非|不能归责于|不应归责于|不属于?|不存在|没有|无)", lead):
            continue
        hits.append((para, i, m, m.group(0)))
    charge(judge, doc, "D05", hits, "audit.delay_attribution", "applicant concedes it caused the audit delay",
           lambda d: "audit_delay_conceded")


def eval_d06(judge, doc):
    hits = []
    rx = re.compile(r"(应(当)?|应该|宜)(按|以|采用|适用|选用|依据)[^,;。]{0,4}(交委期刊|某市交通工程材料价格信息)|"
                    r"(交委期刊|某市交通工程材料价格信息)[^,;。]{0,14}(正确|并无不当|合理|为宜|更为妥当|符合合同(本意|约定))")
    for para, i, m in adopted_hits(doc, rx, regions=("grounds", "request"), neg_window=4):
        canon, bare = para["sentences"][i]
        if re.search(r"原判|法院|判决|径行|径取|错误|(?<!无)不当|未保持中立|A公司", bare[max(0, m.start() - 12):m.end() + 12]):
            continue
        hits.append((para, i, m, m.group(0)))
    charge(judge, doc, "D06", hits, "adjust.periodical_choice", "applicant endorses the 交委 periodical for price adjustment",
           lambda d: "periodical_choice_conceded")


def eval_d07(judge, doc):
    hits = []
    code = re.compile(r"(?<![0-9A-Z])[0-9]{8}[0-9A-Z]{10}(?![0-9A-Z])")
    for para in doc.paras:
        clean = para["clean"]
        if para["region"] in ("front", "closing") and code.search(clean):
            hits.append((para, 0, None, "invented unified social credit code"))
            continue
        if re.search(r"\(20\d{2}\)[^()]{0,6}民(终|初|申)\d+号", clean):
            hits.append((para, 0, None, "invented case-number digits"))
            continue
        if para["region"] == "front" and re.search(r"(住所地?|地址)[^。]{0,30}(路|街|道)\d+号", clean):
            hits.append((para, 0, None, "invented street number"))
    charge(judge, doc, "D07", hits, "document.fabricated_identifier", "value that the materials mask or do not provide was invented",
           lambda d: "fabricated_identifier", rule="N06")


def shape_count(paras: list[dict]) -> int:
    """N10: non-whitespace characters of region paragraphs (headings included), excluding sentences holding a declared gap marker
    (desensitised XXX/**** runs copied from the materials are ordinary text and are counted)."""
    markers = [unicodedata.normalize("NFKC", m).replace("【", "[").replace("】", "]") for m in GAP_MARKERS]
    total = 0
    for para in paras:
        clean = para["clean"]
        for canon, bare in split_sentences(clean, n07_mask_quotes(clean)):
            if any(marker in canon for marker in markers):
                continue
            total += len(canon)
    return total


def eval_d08(judge, doc, contract):
    hits = []
    notes = []
    for unit in contract.get("shape_units", []):
        region = unit["region"]
        paras = [p for p in doc.paras if p["region"] == region]
        if not paras:
            notes.append(f"{unit['id']}: region missing (omission, not charged)")
            continue
        value = shape_count(paras)
        base = max(unit["golden_value"], unit["declared_floor"])
        ratio = value / base
        over = ratio - (1 + unit["overrun_tolerance_ratio"])
        under = (1 - unit["underrun_tolerance_ratio"]) - ratio
        notes.append(f"{unit['id']}: {value}/{base} ratio {ratio:.3f}")
        if over > 0 or under > 0:
            hits.append((unit["id"], region, "overrun" if over > 0 else "underrun", round(ratio, 3)))
    if not hits:
        judge.deduction("D08", "not_triggered", ["obs.scan.grounds"], "shape within tolerance: " + "; ".join(notes))
        return
    obs_ids, occurrences = [], []
    for unit_id, region, direction, ratio in hits:
        obs = f"obs.D08.{unit_id}"
        region_paras = [p for p in doc.paras if p["region"] == region]
        observe_paras(judge, doc, obs, region_paras, f"shape.{unit_id}", "shape_span", "N10",
                      derived=("R09", f"{unit_id} {direction} ratio {ratio}"))
        obs_ids.append(obs)
        occurrences.append({"damage_instance_key": "document_shape_balance", "causal_root_id": "root.document_shape_balance",
                            "manifestation_id": f"D08:{unit_id}", "observation_id": obs,
                            "reason": f"{unit_id} {direction} (ratio {ratio})"})
    judge.deduction("D08", "triggered", obs_ids, "; ".join(notes), occurrences)


def eval_d09(judge, doc):
    hits = []
    for para in doc.paras:
        if para["region"] == "front" and re.match(r"^被申请人(\([^)]{0,20}\))?[:,]?C公司", para["clean"]):
            hits.append((para, 0, None, "C公司 named as respondent"))
    charge(judge, doc, "D09", hits, "front.parties", "B公司's wholly owning co-defendant C公司 is named as an adverse respondent",
           lambda d: "co_defendant_as_respondent")


# R-misquote, role-adjacent reading of the adjudged principal: a court-order verb hands the project
# price to exactly one amount, and that amount fills the principal's role whatever its magnitude. The
# band below identifies the principal by how close it is to the truth, which also lets a large enough
# misquote out of the band; the slot identifies it by its role, so the size of the error is irrelevant.
# An amount that merely shares the sentence does not fill the slot and is never read as the principal.
PRINCIPAL_SLOT = re.compile(r"(?:判付|判令[^,;。]{0,8}支付|判决[^,;。]{0,8}支付)[^,;。]{0,6}?"
                            r"(?:工程款本金|工程款|工程价款|本金)(?:合计|共计|约|计)?"
                            r"¥(-?\d+(?:\.\d+)?)(w?)")


def eval_d10(judge, doc):
    hits = []
    for para in doc.paras:
        if para["spray"] or para["region"] not in ("request", "grounds"):
            continue
        sentences = para["sentences"]
        for i, (canon, bare) in enumerate(sentences):
            if excluded(sentences, i, 0) is not None:
                continue
            for value, rounded in amounts(canon):
                tol = Decimal(10000) if rounded else Decimal(1)
                if "鉴定费" in bare and Decimal(3000000) <= value <= Decimal(4000000) and abs(value - AMT_FEE) > tol:
                    hits.append((para, i, None, f"appraisal fee {value}"))
                    break
                if re.search(r"判付|判令[^,;。]{0,6}支付|尚欠|工程款本金|欠付工程款", bare) and Decimal(120000000) <= value <= Decimal(130000000) and abs(value - AMT_PRINCIPAL) > tol:
                    hits.append((para, i, None, f"adjudged principal {value}"))
                    break
            else:
                slot = PRINCIPAL_SLOT.search(bare)
                if slot is not None:
                    value = Decimal(slot.group(1))
                    tol = Decimal(10000) if slot.group(2) == "w" else Decimal(1)
                    if abs(value - AMT_PRINCIPAL) > tol:
                        hits.append((para, i, None, f"adjudged principal {value}"))
    charge(judge, doc, "D10", hits, "judgment.adjudged_amounts", "adjudged amount misquoted",
           lambda d: "misquoted_" + ("fee" if d.startswith("appraisal") else "principal"), rule="N02")


def eval_d11(judge, doc):
    hits = []
    rx = re.compile(r"(已|确已|均已)(实际)?(施工|实施|建成)[^。]{0,16}(后)?(被|遭)(村民)?(破坏|损毁)|属(于)?(质保期|质量保修期|缺陷责任期)内?的?(维护|维修)?整改(问题|范围|事项)")
    for para, i, m in adopted_hits(doc, rx, regions=("grounds", "request"), neg_window=6):
        canon, bare = para["sentences"][i]
        if re.search(r"并非|不属|不是|而非|不能|不应|混淆", bare[max(0, m.start() - 12):m.end() + 6]):
            continue
        hits.append((para, i, m, m.group(0)))
    charge(judge, doc, "D11", hits, "unseen.existence_conceded", "applicant concedes the 未见实物 works were built and later damaged",
           lambda d: "unseen_existence_conceded")


# The controversy the filing exists to keep open, asserted closed. The materials stop at the effective
# second-instance judgment and record no performance of it, so a discharge, an extinguished claim or an
# undisputed case is a fact the record does not carry, and it defeats the request to revoke that
# judgment. Only the author's own assertion counts: negation, attribution and conditionals are excluded
# upstream, and a full-discharge verb needs its own quantifier (全额/全部/足额/如数) so that a paid
# instalment, 至实际付清之日 and 已实际履行完毕的结算合意 are not read as a discharge of the whole.
CASE_OVER = re.compile(
    r"本案[^,;。]{0,6}(?:已|业已|现已)[^,;。]{0,4}(?:无(?:任何)?争议|不存在(?:任何)?争议|了结|终结)"
    r"|(?:双方|两造|各方)[^,;。]{0,4}争议[^,;。]{0,4}(?:已|业已|现已)[^,;。]{0,4}(?:消除|消灭|解决|不复存在|化解)"
    r"|(?:债权债务|债务|给付义务|付款义务)[^,;。]{0,6}(?:已|业已|现已|均已)[^,;。]{0,6}(?:归于)?(?:消灭|消除|清结|了结|终止)"
    r"|(?:全额|全部|足额|如数)(?:清偿|清结|付清|支付完毕|履行完毕)"
    r"|(?:上述|全部|案涉|涉案)[^,;。]{0,6}(?:款项|工程款|价款|债务)[^,;。]{0,4}(?:已|业已|均已)[^,;。]{0,4}(?:全额|全部)?(?:清偿|清结|付清|结清)")


def eval_d13(judge, doc):
    hits = []
    for para, i, m in adopted_hits(doc, CASE_OVER, regions=("request", "grounds", "closing"), neg_window=6):
        canon, bare = para["sentences"][i]
        if re.search(r"并非|并未|尚未|仍未|而非|不属|不能|不应|一旦", bare[max(0, m.start() - 12):m.end() + 6]):
            continue
        hits.append((para, i, m, m.group(0)))
    charge(judge, doc, "D13", hits, "case.live_controversy",
           "the filing asserts the adjudged debt discharged and the case no longer in dispute",
           lambda d: "controversy_declared_over")


def evaluate(registry: dict, judge: ProgramJudge) -> None:
    """Call judge.positive and judge.deduction exactly once for every contracted item."""
    if registry.get("parse_failure"):
        for item_id in judge.positives:
            judge.positive(item_id, 0.0, "obs.parse_failure", "artifact could not be parsed", "different")
        for item_id in judge.deductions:
            judge.deduction(item_id, "parse_failure", ["obs.parse_failure"], "artifact could not be parsed")
        return
    doc = registry["doc"]
    from semantic_judge import adjudicate
    candidate="\n".join(r["text"] for r in doc.raw["records"])
    golden_path = Path(__file__).resolve().parents[4] / "golden/retrial-application.md"
    doc.semantic_verdict = adjudicate(
        candidate,
        (Path(__file__).parent / "semantic_source.json").read_text(encoding="utf-8"),
        judge.contract,
        golden_path.read_text(encoding="utf-8"),
    )
    judge.semantic_verdict=doc.semantic_verdict
    for fn in (eval_p01, eval_p02, eval_p03, eval_p04, eval_p05, eval_p06, eval_p07, eval_p08, eval_p09,
               eval_p10, eval_p11, eval_p12, eval_p13, eval_p14, eval_p15, eval_p16, eval_p17):
        fn(judge, doc)
    for fn in (eval_d01, eval_d02, eval_d03, eval_d04, eval_d05, eval_d06, eval_d07):
        fn(judge, doc)
    eval_d08(judge, doc, judge.contract)
    for fn in (eval_d09, eval_d10, eval_d11, eval_d12, eval_d13):
        fn(judge, doc)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--contract", type=Path, default=CANONICAL_CONTRACT)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    contract_path = args.contract.resolve()
    judge = ProgramJudge(load_contract(contract_path), args.artifact.resolve(), sha256(contract_path))
    evaluate(normalize(extract_raw(args.artifact.resolve()), judge), judge)
    result = judge.finish()
    result["semantic_judge"]=getattr(judge,"semantic_verdict",None)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json:
        args.json.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
