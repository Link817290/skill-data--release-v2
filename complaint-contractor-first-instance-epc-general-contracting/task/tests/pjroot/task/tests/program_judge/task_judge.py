#!/usr/bin/env python3
"""Program Judge adapter for the EPC contractor (承包方) civil complaint task.

Three explicit layers:
  extract_raw()  carrier text only (Markdown lines, or DOCX body paragraphs and table rows
                 walked in document order)
  normalize()    registered rules N01-N09 turn lines into canonical observations
                 (party block, request items, facts paragraphs and sentences, gap markers)
  evaluate()     one positive() call per P and one deduction() call per D, using the
                 registered derivation rules R01-R09.

No model judgement is embedded. Every fact, alias and threshold comes from
rubric-contract.json and the frozen Golden.
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

# Frozen task constants.
DESIGN_FEE = "1680000"
TEMP_FACILITIES = "2583218.16"
SERVICE_FEE_SHARE = "8487.5"
GOLDEN_PROFIT = "13722526.21"
NOTICE_DATE = "2024-07-08"
MAX_REASONABLE_ANNUAL_RATE = Decimal("3.65")

GAP_MARKERS = [
    "[待补充]", "【待补充】", "[待填写]", "【待填写】", "[待核实]", "【待核实】", "[待计算]", "【待计算】",
    "[placeholder]", "材料未提供", "未提供", "待补充", "待填写", "待核实", "待计算", "unspecified", "TBD",
    "【待补】", "[待补]", "待补",
]
GAP_TOKEN = "⟦GAP⟧"

REQUEST_HEADINGS = ("诉讼请求", "诉讼请求事项", "请求事项", "诉请")
FACTS_HEADINGS = ("事实和理由", "事实与理由", "事实及理由", "事实、理由", "事实理由")
TITLE_RE = re.compile(r"^(民事)?起诉(状|书)$")
TAIL_RE = re.compile(r"^(此致|具状人|起诉人:|附:|附件|证据(清单|目录)$)")

PAY_VERBS = "支付|给付|偿还|清偿|付清|偿付|赔偿|赔付"
REQ_VERBS = "判令|判决|请求|要求|责令|确认"
NEG = "不|未|没有|并非|无需|无须|否认|拒绝|免除|无权|不再|撤回|放弃|无"
REQ_NEG = re.compile(r"(不|无需|无须|未|没有|撤回|放弃|不再)(" + REQ_VERBS + ")")
JOINT_REQ = re.compile(r"(C公司|被告二|被告2|第二被告|被告\(二\))[^;。]{0,40}?(承担|负)[^;。]{0,12}?连带")
# 可能 inside the Civil Code art. 584 foreseeability clause (…预见到的因违约可能造成的损失) is statutory
# wording, not a hedge.
CANDIDATE = re.compile(r"尚未采纳|未予采纳|并非本方主张|不属于本方主张|(?<!违约)(?<!违反合同)可能(?!造成的损失)|或许|也许|待定|候选|备选|假设|倘若|是否|暂定|二选一|(或者|或|抑或|/)(¥|@|[A-E]公司|§)")
QUOTE_REJECT = re.compile(
    r"(被告|对方|[BCDE]公司)(、[BCDE]公司)?[^。;,]{0,6}(辩称|声称|抗辩|认为|称:|称,|主张:)|"
    r"不予认可|不能成立|不成立|驳回|不属实|不予采信|站不住脚|系错误|是错误的|有误|反驳")
CONDITIONAL = re.compile(r"如果|若|倘若|假如")

QUOTE_RE = re.compile(r"“([^”]{13,})”|「([^」]{13,})」")
DATE_CN = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")
DATE_NUM = re.compile(r"(?<![\d.@¥])(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})日?(?![\d.])")
MONEY = re.compile(r"(?:人民币|RMB)?(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(万元|元)|¥(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(万元|元)?")
ARTICLE = re.compile(r"第([零〇一二两三四五六七八九十百千0-9]+)条")
CLAUSE = re.compile(r"第([零〇一二两三四五六七八九十0-9]+)款")
CN_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CN_UNITS = {"十": 10, "百": 100, "千": 1000}
LAWS = (
    ("contract_interp", re.compile(r"合同编通则[^》§。;]{0,14}解释")),
    ("civil_code", re.compile(r"民法典")),
    ("company_law", re.compile(r"公司法")),
    ("contract_law", re.compile(r"合同法")),
    ("civil_procedure", re.compile(r"民事诉讼法")),
)

PROFIT = r"预期可得利益|预期利润|可得利益|可得利润|预期收益|利润损失|履行后可以获得的利益|履行后可获得的利益"
LOSS_CONTEXT = re.compile(r"损失|赔偿|赔付")
ENUMERATED = re.compile(r"^(\d+|[一二三四五六七八九十]+)[.、)]|^\((\d+|[一二三四五六七八九十]+)\)")
UNORDERED = re.compile(r"^\s*[-*+•]\s+")


# ---------------------------------------------------------------------------
# Layer 1: raw carrier extraction
# ---------------------------------------------------------------------------
def _extract_raw_unguarded(artifact: Path) -> dict:
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
                        cells = []
                        for cell in row.cells:
                            if not cells or cells[-1] != cell.text:
                                cells.append(cell.text)
                        raw["records"].append({"locator": f"docx:body/tbl[{t_index}]/tr[{r}]", "text": "|" + "|".join(cells) + "|"})
                    t_index += 1
        except Exception as exc:
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



# Withdrawn / candidate / disowning carriers ("以下并非本方主张：…",
# "疑似（待核，尚未采纳）：…", quote-and-reject) are blanked at the extraction layer, before any item
# predicate runs.  Sentence-level negation stops at the colon, so the prefix would otherwise be invisible.
from adversarial_guards import blank_withdrawn, negated_before  # noqa: E402


def _guard_record_text(text: str) -> str:
    if text.startswith("|") and text.endswith("|"):   # a docx table row: guard each cell on its own
        return "|" + "|".join(blank_withdrawn(c) for c in text[1:-1].split("|")) + "|"
    return blank_withdrawn(text)


def extract_raw(artifact: Path) -> dict:
    raw = _extract_raw_unguarded(artifact)
    for record in raw.get("records", []):
        record["text"] = _guard_record_text(record["text"])
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
    # HTML presentation tags (<p align="center">…</p>, <center>, <div>, <br>) are carrier, not content
    text = re.sub(r"</?(p|div|center|span|b|strong|u|br|h[1-6])(\s[^<>]*)?/?>", "", text, flags=re.I)
    text = re.sub(r"^\s*#{1,6}\s*", "", text)
    text = re.sub(r"^\s*>\s*", "", text)
    text = re.sub(r"^\s*[-*+]\s+", "", text)
    text = text.replace("**", "").replace("__", "").replace("`", "")
    return re.sub(r"\s+", "", text)


def n06_gap(text: str) -> str:
    """N06: fold every declared gap marker into one gap token."""
    for marker in sorted(GAP_MARKERS, key=len, reverse=True):
        text = text.replace(unicodedata.normalize("NFKC", marker), GAP_TOKEN)
    # A bracketed value slot remains a gap when it uses an ordinary drafting
    # variation such as “待补证核定并填写具体金额”.  Fold the complete bracket so
    # numbers used only to describe a formula inside it cannot become claims.
    text = re.sub(r"[\[【][^\]】]{0,60}(?:待|补证|核定|核实|填写|补充|计算)[^\]】]{0,60}[\]】]", GAP_TOKEN, text)
    return re.sub(r"_{3,}|×{2,}|X{3,}", GAP_TOKEN, text)


def n02_n03_n05(text: str) -> str:
    """N03 dates, N02 money, N05 statute article and paragraph numbers into canonical tokens."""
    text = DATE_CN.sub(lambda m: f"@{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}", text)
    text = DATE_NUM.sub(lambda m: f"@{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}", text)

    def money(m: re.Match) -> str:
        if m.group(1) is not None:
            return money_token(m.group(1), m.group(2), m.group(3))
        return money_token(m.group(4), m.group(5), m.group(6))

    cn_money = re.compile(r"(?:人民币|RMB)?([零〇一二两三四五六七八九壹贰叁肆伍陆柒捌玖][零〇一二两三四五六七八九十百千万亿壹贰叁肆伍陆柒捌玖拾佰仟萬億]*)(万元|元)")

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

    def clause(m: re.Match) -> str:
        number = cn_number(m.group(1))
        return f"¶{number}" if number is not None else m.group(0)

    return CLAUSE.sub(clause, ARTICLE.sub(article, text))


def n07_quotes(text: str) -> str:
    """N07: quoted propositions (13+ characters) are not the author's own assertion."""
    text = QUOTE_RE.sub("“…”", text)
    parts = text.split('"')
    out = [parts[0]]
    for k in range(1, len(parts), 2):
        if k + 1 < len(parts):
            out.append("“…”" if len(parts[k]) >= 13 else '"' + parts[k] + '"')
            out.append(parts[k + 1])
        else:
            out.append('"' + parts[k])
    return "".join(out)


def n04_heading(clean: str) -> tuple[str | None, str]:
    """N04: resolve section headings by alias plus whole-line structure."""
    body = re.sub(r"^([一二三四五六七八九十]+[、.]|\d+[.、)]|\([一二三四五六]\))", "", clean)
    for kind, aliases in (("request", REQUEST_HEADINGS), ("facts", FACTS_HEADINGS)):
        for alias in sorted(aliases, key=len, reverse=True):
            if body in (alias, alias + ":"):
                return kind, ""
            if body.startswith(alias + ":") and len(body) > len(alias) + 1:
                return kind, body[len(alias) + 1:]
    return None, ""


def split_sentences(text: str) -> list[str]:
    return [part for part in re.split(r"[。;!?]", text) if part]


def split_request_items(text: str) -> list[str]:
    parts = re.split(r"(?<=[;。])(?=(?:\d+|[一二三四五六七八九十]+)[.、)])", text)
    return [part for part in parts if part.strip(";。")]


def raw_token_soup(raw_text: str) -> bool:
    """R01: a raw line made of eight or more whitespace- or comma-separated short tokens is keyword soup.

    Whitespace next to digits or ASCII punctuation is collapsed first so spaced numbers
    such as `2024 年 7 月 8 日` or `1,680,000 元` stay one legitimate phrase.
    """
    text = unicodedata.normalize("NFKC", raw_text).replace("**", "").strip()
    text = re.sub(r"^\s*(#{1,6}|[-*+>]|\d+[.)])\s+", "", text)
    text = re.sub(r"\s*([\d.,:;()%/])\s*", r"\1", text)
    text = re.sub(r"(\d)\s+(?=[年月日万元条款])", r"\1", text)
    if not re.search(r"\S\s+\S", text):
        text = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", text)  # In punctuated prose 4,271,705.66 is one amount
    text = re.sub(r"(?<=[年月第])\s+(?=\d)", "", text)
    fragments = [frag for frag in re.split(r"[\s、,]+", text) if frag]
    short = [frag for frag in fragments if len(frag) <= 8]
    return len(fragments) >= 8 and len(short) >= 0.7 * len(fragments)


def is_list_spray(text: str) -> bool:
    """R01: six or more short enumerated fragments are a keyword list, not a proposition."""
    fragments = re.split(r"[、,]", text)
    short = [frag for frag in fragments if len(frag) <= 8]
    return len(fragments) >= 6 and len(short) >= 0.7 * len(fragments)


def too_dense(text: str) -> bool:
    """R01: one sentence asserting more than four amounts or three dates is candidate spraying."""
    return len(set(re.findall(r"¥[\d.]+", text))) > 4 or len(set(re.findall(r"@\d{4}-\d{2}-\d{2}", text))) > 3


def neg_before(text: str, position: int) -> bool:
    """R02: negation inside the clause carrying the key verb, before that verb."""
    clause_start = max(text.rfind(",", 0, position), text.rfind(":", 0, position)) + 1
    return re.search(NEG, text[clause_start:position]) is not None


def excluded_context(text: str) -> str | None:
    """R02: candidate, quoted or rejected, conditional, keyword-list and dense-spray spans cannot be adopted."""
    if CANDIDATE.search(text):
        return "candidate"
    if QUOTE_REJECT.search(text):
        return "quoted_or_rejected"
    if CONDITIONAL.search(text):
        return "conditional"
    if is_list_spray(text):
        return "keyword_list"
    if too_dense(text):
        return "dense_spray"
    return None


PARTY_RE = re.compile(r"^(原告|第[一二三四1234]被告|被告[一二三四1234]?|被告\([一二三四1234]\)|第三人[一二三1234]?)(\([^)]{0,16}\))?:(.*)$")


class Doc:
    """Normalized complaint: lines, sections (party block, requests, facts) and their states."""

    PARTY_LABEL_ONLY = re.compile(r"^(原告|第[一二三四1234]被告|被告[一二三四1234]?|被告\([一二三四1234]\)|第三人[一二三1234]?)(\([^)]{0,16}\))?$")

    def _n09_party_label_lines(self):
        """N09: a party label that stands on its own line names the entity on the next line.

        `PARTY_RE` reads `被告一:B公司`; an output that puts the label in a heading and the entity
        beneath it states the same party, so the two lines are read as one before any decision."""
        for index, line in enumerate(self.lines):
            if not self.PARTY_LABEL_ONLY.match(line["assert"]):
                continue
            follower = next((self.lines[j] for j in range(index + 1, len(self.lines))
                             if self.lines[j]["assert"] and self.lines[j]["heading"] is None), None)
            if follower is None or PARTY_RE.match(follower["assert"]):
                continue
            line["assert"] = f"{line['assert']}:{follower['assert']}"
            line["canon"] = f"{line['canon']}:{follower['canon']}"

    def __init__(self, raw: dict):
        self.raw = raw
        self.artifact = str(raw["artifact"])
        self.lines: list[dict] = []
        for record in raw["records"]:
            clean = n01_clean(record["text"])
            if not clean:
                continue
            canon = n02_n03_n05(n06_gap(clean))
            kind, inline = n04_heading(clean)
            asserted = n07_quotes(canon)
            if kind is None and raw_token_soup(record["text"]):
                asserted = "⟦SPRAY⟧"
            line = {"locator": record["locator"], "raw": record["text"], "clean": clean,
                    "canon": canon, "assert": asserted, "heading": kind}
            if kind and inline:
                line["inline"] = inline
                line["inline_assert"] = n07_quotes(n02_n03_n05(n06_gap(inline)))
            self.lines.append(line)
        self._n09_party_label_lines()
        request_heads = [i for i, line in enumerate(self.lines) if line["heading"] == "request"]
        facts_heads = [i for i, line in enumerate(self.lines) if line["heading"] == "facts"]
        tails = [i for i, line in enumerate(self.lines) if line["heading"] is None and TAIL_RE.match(line["clean"])]
        self.section_state: dict[str, str] = {}
        self.sections: dict[str, list[dict]] = {"party": [], "request": [], "facts": []}
        boundaries = sorted(request_heads + facts_heads)
        for name, heads in (("request", request_heads), ("facts", facts_heads)):
            self.section_state[name] = ("confirmed_missing" if not heads else "ambiguous" if len(heads) > 1 else "identified")
            if self.section_state[name] != "identified":
                continue
            start = heads[0]
            following = [b for b in boundaries + tails if b > start]
            end = min(following) if following else len(self.lines)
            members = []
            head = self.lines[start]
            if head.get("inline"):
                members.append({**head, "heading": None, "clean": head["inline"], "assert": head["inline_assert"]})
            members.extend(self.lines[start + 1:end])
            self.sections[name] = members
        if boundaries and boundaries[0] > 0:
            self.section_state["party"] = "identified"
            self.sections["party"] = [l for l in self.lines[:boundaries[0]] if not TITLE_RE.fullmatch(l["clean"])]
        else:
            self.section_state["party"] = "confirmed_missing"
        self.labels = self._n08_labels()
        if self.labels:
            for name in ("request", "facts"):
                for line in self.sections[name]:
                    line["assert"] = self._apply_labels(line["assert"])

    def _n08_labels(self) -> dict[str, str]:
        """N08: party labels (被告一, 第一被告, 被告(1) ...) that name exactly one entity map to that entity."""
        mapping: dict[str, str] = {}
        for line in self.sections["party"]:
            match = PARTY_RE.match(line["assert"])
            if not match or match.group(1) in ("原告", "被告", "第三人"):
                continue
            entities = re.findall(r"([A-E])公司", re.split(r"[,;。]", match.group(3), maxsplit=1)[0])
            if len(set(entities)) == 1:
                mapping[match.group(1)] = entities[0]
        return mapping

    def _apply_labels(self, text: str) -> str:
        for label, entity in sorted(self.labels.items(), key=lambda kv: -len(kv[0])):
            text = re.sub(re.escape(label) + r"(\([^)]{0,6}\))?(?![A-E]公司|\d)", f"被告{entity}公司", text)
        return text

    def loc(self, line: dict, object_key: str, field: str, prefix: str) -> Locator:
        return Locator(locator_id=f"{prefix}:{line['locator']}", artifact_path=self.artifact,
                       container_type=self.raw["carrier"] or "unknown", container_path=line["locator"],
                       object_key=object_key, field=field, observed=line["raw"][:400])

    def canon_loc(self, source: Locator, line: dict, rule: str) -> Locator:
        return Locator(locator_id=source.locator_id + ":canon", artifact_path=self.artifact,
                       container_type=source.container_type, container_path=source.container_path,
                       object_key=source.object_key, field=source.field + ".canonical",
                       observed=line["assert"][:400], evidence_origin="lossless_canonicalized",
                       source_locator_ids=(source.locator_id,), normalization_rule_id=rule)

    def section_loc(self, section: str, object_key: str, prefix: str) -> Locator:
        return Locator(locator_id=f"{prefix}:section:{section}", artifact_path=self.artifact,
                       container_type=self.raw["carrier"] or "unknown", container_path=f"section:{section}",
                       object_key=object_key, field="section_state", observed=self.section_state.get(section, "unresolved"))


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
                          "artifact", "complaint", "carrier", raw_registry["parse_error"])
        judge.observe("obs.parse_failure", "parse_failure", [locator])
        return {"parse_failure": True}
    doc = Doc(raw_registry)
    for section in ("party", "request", "facts"):
        state = doc.section_state[section]
        if state == "identified" and doc.sections[section]:
            observe_lines(judge, doc, f"obs.scan.{section}", doc.sections[section], f"section.{section}", "section_text", "N01")
        else:
            judge.observe(f"obs.scan.{section}", "ambiguous" if state == "ambiguous" else "confirmed_missing",
                          [doc.section_loc(section, f"section.{section}", f"obs.scan.{section}")])
    return {"parse_failure": False, "doc": doc}


# ---------------------------------------------------------------------------
# Layer 3: P/D decisions
# ---------------------------------------------------------------------------
def party_entries(doc: Doc) -> list[dict]:
    """R03: party lines resolved to role and entity keys (N08 aliases)."""
    entries = []
    for line in doc.sections["party"]:
        match = PARTY_RE.match(line["assert"])
        if not match:
            continue
        label = match.group(1)
        role = "plaintiff" if label == "原告" else "third_party" if label.startswith("第三人") else "defendant"
        head = re.split(r"[,;。]", match.group(3), maxsplit=1)[0]
        if re.search(NEG, head):
            continue
        entries.append({"role": role, "entities": re.findall(r"([A-E])公司", head), "line": line})
    return entries


def request_items(doc: Doc) -> list[dict]:
    if doc.section_state["request"] != "identified":
        return []
    return [{"text": text, "line": line} for line in doc.sections["request"] for text in split_request_items(line["assert"])]


def facts_paragraphs(doc: Doc) -> list[dict]:
    if doc.section_state["facts"] != "identified":
        return []
    return [{"text": line["assert"], "line": line, "sentences": split_sentences(line["assert"])} for line in doc.sections["facts"]]


HEADING_NUM = re.compile(r"^([一二三四五六七八九十]+[、.]|\([一二三四五六七八九十]+\))")


def is_heading_line(line: dict) -> bool:
    """R11: subsection separators inside the facts section (Markdown heading, whole-bold line, short numbered title)."""
    raw = line["raw"].strip()
    if re.match(r"^#{1,6}\s", raw):
        return True
    if len(raw) > 4 and raw.startswith("**") and raw.endswith("**"):
        return True
    return len(line["clean"]) <= 60 and bool(HEADING_NUM.match(line["clean"]))


def facts_units(doc: Doc, max_lines: int = 4, max_chars: int = 700) -> list[dict]:
    """R11: every single facts line, plus blocks of 2-4 consecutive non-heading facts lines inside one
    subsection whose joined text is at most 700 characters (a proposition split into list items or
    adjacent paragraphs). Lines are joined with a sentence stop so no pattern spans two lines."""
    units = [{**para, "lines": [para["line"]]} for para in facts_paragraphs(doc)]
    if doc.section_state["facts"] != "identified":
        return units
    runs, current = [], []
    for line in doc.sections["facts"]:
        if is_heading_line(line):
            if current:
                runs.append(current)
            current = []
        else:
            current.append(line)
    if current:
        runs.append(current)
    for run in runs:
        for size in range(2, max_lines + 1):
            for start in range(0, len(run) - size + 1):
                window = run[start:start + size]
                text = "。".join(l["assert"].rstrip("。") for l in window)
                if len(text) > max_chars:
                    continue
                units.append({"text": text, "line": window[0], "lines": window, "sentences": split_sentences(text)})
    return units


def unresolved(doc: Doc, section: str) -> str | None:
    state = doc.section_state[section]
    if state == "identified" and doc.sections[section]:
        return None
    return "ambiguous" if state == "ambiguous" else "missing"


def credit(judge, doc, item_id, section, fraction, comparison, reason, lines, object_key, rule="N03"):
    obs = f"obs.{item_id}"
    first = section.split("+")[0]
    if comparison == "missing":
        states = {doc.section_state[s] for s in section.split("+")}
        state = "ambiguous" if states == {"ambiguous"} else "confirmed_missing"
        judge.observe(obs, state, [doc.section_loc(first, object_key, obs)])
        judge.positive(item_id, 0.0, obs, reason, "missing" if state == "confirmed_missing" else "different")
        return
    if comparison == "ambiguous":
        evidence = [doc.loc(line, object_key, "candidate_span", obs) for line in {l["locator"]: l for l in lines}.values()]
        judge.observe(obs, "ambiguous", evidence or [doc.section_loc(first, object_key, obs)])
        judge.positive(item_id, 0.0, obs, reason, "different")
        return
    observe_lines(judge, doc, obs, lines, object_key, "proposition_span", rule)
    judge.positive(item_id, fraction, obs, reason, comparison)


def adopted(text: str, position: int) -> bool:
    return not neg_before(text, position) and not excluded_context(text)


# ----- request items ----------------------------------------------------------
OBJECT_MARK = re.compile(r"(向|对|给|与|致|通知|和|及|同|作为|独立于|区别于|区分于|混同于)(原告|被告)?(\d|[一二三四])?$")


def subject_entities(zone: str) -> list[str]:
    """R05: entities in a span that are not grammatical objects (向/对/给/与/致/通知 <entity>)."""
    return [m.group(1) for m in re.finditer(r"([A-E])公司", zone) if not OBJECT_MARK.search(zone[:m.start()])]


def nearest_subject(text: str, position: int) -> str | None:
    """R05: the closest non-object entity before a predicate."""
    subjects = subject_entities(text[:position])
    return subjects[-1] if subjects else None


def comp_b(text: str) -> bool:
    """R05: some compensation predicate (赔偿/赔付) in the span has B公司 as its nearest non-object subject."""
    for m in re.finditer(r"赔偿|赔付", text):
        if not neg_before(text, m.start()) and nearest_subject(text, m.start()) == "B":
            return True
    return False


def multiplier_above_one(text: str) -> bool:
    for m in re.finditer(r"(LPR|贷款市场报价利率)[^,;。]{0,6}?([\d.]+|[一二两三四五])倍|([\d.]+|[一二两三四五])倍[^,;。]{0,4}(LPR|贷款市场报价利率)", text):
        raw_value = m.group(2) or m.group(3)
        try:
            value = Decimal(CN_DIGITS[raw_value]) if raw_value in CN_DIGITS else Decimal(raw_value)
        except InvalidOperation:
            continue
        if value > 1:
            return True
    return False


def payer_is(text: str, start: int, end: int, entity: str) -> bool:
    subjects = subject_entities(text[start:end])
    return bool(subjects) and subjects[0] == entity


TERMINATION = re.compile(r"合同》?[^;。]{0,60}?解除(?!通知|权|之日|日|时起|生效(之日|日|时))|解除[^;。]{0,4}(与原告[^;。]{0,12})?《?[^;。]{0,16}合同|"
                         r"解除(原告)?(与|和)(被告[一二三四1234]?)?B公司[^;。]{0,40}?合同")


def termination_items(doc: Doc) -> list[dict]:
    """R04: request items asking the court to terminate (or confirm termination of) the EPC contract."""
    found = []
    for item in request_items(doc):
        text = item["text"]
        req = re.search(REQ_VERBS, text)
        m = TERMINATION.search(text)
        if not req or not m or req.start() > m.start():
            continue
        pos = m.start() + m.group(0).find("解除")
        # A money request that mentions the termination only as the cause or the
        # start of what it claims ("赔偿因其违约解除合同造成的损失", "自合同解除生效之次日起…支付利息") is not a
        # termination request.  The item is a termination request only when it carries no payment predicate, or when
        # 解除 is itself the object of the request verb ("判令解除…合同并赔偿…").
        pay = re.search("(" + PAY_VERBS + r")|资金占用费|资金占用利息|利息|违约金", text)
        if pay and not re.search("(" + REQ_VERBS + r")(依法)?解除", text):
            continue
        if REQ_NEG.search(text) or neg_before(re.sub(r"(?:尚未|未)履行", lambda m: "待" * len(m.group()), text), pos) or excluded_context(text):
            continue
        if re.search(r"(不发生|无)[^;。,]{0,4}效力|无效", text):
            continue
        service = re.search(r"起诉状(副本)?[^;。,]{0,6}送达", text) is not None
        dates = set(re.findall(r"@(\d{4}-\d{2}-\d{2})(?!(?:签订|订立|签署|签约|签定))", text))
        # R04: record scope without rejecting a supported phase-II-only request.
        partial_scope = PARTIAL_SCOPE.search(text) is not None
        found.append({"item": item, "service": service, "dates": dates, "partial_scope": partial_scope})
    return found


# Supported whole-contract and unperformed-phase scopes are both accepted.
PARTIAL_SCOPE = re.compile(r"中关于[^;。]{0,30}(二期|第二期)|(二期|第二期)(工程)?(的|建立的|所涉的?|项下的?)[^;。]{0,20}合同关系|合同》?[^;。]{0,6}(中|内|项下)?[^;。]{0,6}(关于|有关|涉及)?[^;。]{0,24}(二期|第二期|部分工程|未履行)[^;。]{0,12}部分|部分解除|解除[^;。]{0,20}(二期|第二期)(工程)?(部分|内容)")


def eval_p02(judge, doc, argued: bool = True):
    """P02 termination request. A request that the facts section does not argue at all (P10, P12 and P13 all
    unearned) is half a claim: the full termination request then earns 0.5."""
    z = unresolved(doc, "request")
    if z:
        return credit(judge, doc, "P02", "request", 0, z, "request section unresolved", [], "request.termination")
    items = termination_items(doc)
    lines = [i["item"]["line"] for i in items]
    if not items:
        return credit(judge, doc, "P02", "request", 0, "missing", "no contract termination request", [], "request.termination")
    signatures = {("service" if i["service"] else "") + "|" + ",".join(sorted(i["dates"])) for i in items}
    if len(signatures) > 1:
        return credit(judge, doc, "P02", "request", 0, "ambiguous", "conflicting termination dates", lines, "request.termination")
    info = items[0]
    if info["service"] and not info["dates"]:
        if not argued:
            return credit(judge, doc, "P02", "request", 0.5, "partial", "termination as of service requested, but the facts section argues none of the losses or the shareholder liability", lines, "request.termination")
        return credit(judge, doc, "P02", "request", 1.0, "exact", "contract terminated as of service of the complaint copy", lines, "request.termination")
    if not info["dates"]:
        return credit(judge, doc, "P02", "request", 0, "different", "termination requested without the service-date effect (no half tier)", lines, "request.termination")
    return credit(judge, doc, "P02", "request", 0, "different", "termination dated to another day (e.g. the employer's notice)", lines, "request.termination")


def damages_items(doc: Doc, entity: str = "B") -> list[dict]:
    """R05: request items ordering a payer to compensate losses."""
    found = []
    for item in request_items(doc):
        text = item["text"]
        req = re.search(REQ_VERBS, text)
        if not req or REQ_NEG.search(text) or excluded_context(text):
            continue
        for m in re.finditer(r"(赔偿|赔付|支付|给付)[^;。,]{0,20}?(损失|赔偿金|赔偿款|损害赔偿|可得利益|预期利润|设计费|临时设施)", text):
            if m.start() < req.start() or neg_before(text, m.start()):
                continue
            if payer_is(text, req.start(), m.start(), entity):
                found.append(item)
                break
    return found


def money_items(doc: Doc, entity: str = "B") -> list[dict]:
    """R08 request scope for the loss slots P10/P12: a request item ordering `entity` to pay
    or compensate (赔偿/赔付/支付/给付) - the slot pattern itself names the head, so the head need not sit within
    20 characters of the verb (赔偿因二期合同被解除而发生的中标服务费分摊损失 / 支付…初步设计价款)."""
    found = []
    for item in request_items(doc):
        text = item["text"]
        req = re.search(REQ_VERBS, text)
        if not req or REQ_NEG.search(text) or excluded_context(text):
            continue
        for m in re.finditer(r"赔偿|赔付|支付|给付", text):
            if m.start() < req.start() or neg_before(text, m.start()):
                continue
            if payer_is(text, req.start(), m.start(), entity):
                found.append(item)
                break
    return found


def occupation_items(doc: Doc) -> list[dict]:
    """R06: capital-occupation request clauses: start, rate standard, end phrase."""
    found = []
    for item in request_items(doc):
        text = item["text"]
        if not re.search(REQ_VERBS, text) or REQ_NEG.search(text):
            continue
        for clause in re.split(r"(?=并(?:判令|判决|请求|要求)?[^;。]{0,4}(?:自|从))", text):
            if not clause or not re.search(r"资金占用(费|损失)?|利息|逾期付款损失|迟延付款损失", clause):
                continue
            if excluded_context(clause):
                continue
            if re.search(r"(不|无需|无须|未|没有|放弃)[^,;。]{0,4}(计算|计付|支付)?(利息|资金占用|逾期付款损失|迟延付款损失)", clause):
                continue
            if "B公司" not in text or re.search(r"向(被告)?B公司(支付|给付)", clause):
                continue
            start_ok = re.search(r"(自|从)(?:(?!通知|单方|被告|[A-E]公司|函|宣布)[^,;。起@]){0,16}?(解除(生效)?之次?日|解除(生效)?日|解除(生效)?时|被?判决解除之日|起诉状(副本)?[^;。,]{0,6}送达[^;。,]{0,8}?(之次日|次日|之日|日|时))", clause)
            start_date = re.search(r"(自|从)@(\d{4}-\d{2}-\d{2})|@(\d{4}-\d{2}-\d{2})(起|之日起)", clause)
            end = re.search(r"(至|到|直至|直到)[^,;。]{0,10}(实际|全部)?(清偿|支付|付清|给付|履行|还清|偿还)(完毕)?(之日|日|时)", clause)
            rate = re.search(r"LPR|贷款市场报价利率", clause) and not multiplier_above_one(clause)
            found.append({"item": item, "start_ok": start_ok is not None,
                          "start_date": (start_date.group(2) or start_date.group(3)) if start_date else None,
                          "end": end is not None, "rate": bool(rate)})
    return found


JOINT_SCOPE = re.compile(r"在[^,;。]{0,60}?(范围内|情况下|限度内|前提下)|证明[^,;。]{0,40}?独立(于[^,;。]{0,20}?财产)?|"
                         r"(为|是|系|作为)[^,;。]{0,6}[A-E]公司的?(唯一|全资|独资|控股)?股东")


def joint_c(text: str) -> bool:
    """R09: a joint-liability predicate (承担/负 连带…责任) whose subject is C公司. When a 对 opens the
    object phrase (对…承担连带责任) in the same clause, the subject is the nearest non-object entity before that 对.
    就 opens the object phrase like 对 (就B公司的债务承担连带清偿责任), and a scope/condition
    adverbial 在…(范围内|情况下|限度内|前提下), the object of 证明…财产独立 and the company in (为|作为)B公司的唯一股东
    are dropped before locating the subject,
    so the entity inside them (在B公司应承担的债务范围内 / 不能证明B公司的财产独立于其自己的财产) is not read as the subject."""
    for m in re.finditer(r"(承担|负|负担)连带(清偿|赔偿|给付)?责任", text):
        if neg_before(text, m.start()):
            continue
        if re.search(r"C公司[^。;]{0,100}(?:如|若)?其不能证明", text[:m.start()]):
            return True
        head = JOINT_SCOPE.sub("", text[:m.start()])
        clause_start = max(head.rfind(c) for c in ",;。") + 1
        opens = [i for i in (head.find("对", clause_start), head.find("就", clause_start)) if i >= 0]
        k = min(opens) if opens else -1  # the first object opener of the clause (C公司就B公司对原告所负的…)
        subject = None
        if k >= 0:
            before = subject_entities(head[:k])
            subject = before[-1] if before else None
        if subject is None:
            before = subject_entities(head)
            subject = before[-1] if before else None
        if subject == "C":
            return True
    # Equivalent direct wording: “由C公司连带清偿B公司的债务”.  It states
    # the same subject, direction and object without the auxiliary “承担…责任”.
    direct = re.search(r"(?:由|为)?C公司[^。;,]{0,20}?连带(清偿|赔偿|给付)", text)
    if direct and not neg_before(text, direct.start()):
        return True
    return False


# ----- facts ----------------------------------------------------------------


NO_RIGHT_NEGATED = re.compile(r"(并非|不是|否认|不能认为|不应认定)[^。;,]{0,6}$")


def para_window(doc: Doc, para: dict) -> str:
    """R07 scope: a statute paragraph and the paragraph right after it, when that paragraph is
    not a heading, carry one proposition - a draft that quotes the article in one paragraph and applies it to the
    party in the next (依照…第二十三条第三款之规定："…" / 被告二C公司…应承担连带清偿责任) relies on the article for it."""
    lines = doc.sections["facts"]
    for n, line in enumerate(lines):
        if line is para["line"]:
            if n + 1 < len(lines) and not is_heading_line(lines[n + 1]):
                return para["text"] + "\n" + lines[n + 1]["assert"]
            break
    return para["text"]


def cited_articles(doc: Doc, law: str, number: int):
    """R07: article tokens attributed to the law whose name ends nearest before them in the paragraph."""
    for para in facts_paragraphs(doc):
        text = para["text"]
        if len(text) > 800:
            continue
        offset = 0
        for sentence in para["sentences"]:
            start = text.find(sentence, offset)
            offset = start + len(sentence)
            if QUOTE_REJECT.search(sentence) or CANDIDATE.search(sentence) or is_list_spray(sentence):
                continue
            for m in re.finditer(r"§" + str(number) + r"(?!\d)", sentence):
                absolute = start + m.start()
                best = None
                for name, pattern in LAWS:
                    for lm in pattern.finditer(text[:absolute]):
                        if best is None or lm.end() > best[1]:
                            best = (name, lm.end())
                if not best or best[0] != law:
                    continue
                yield para, sentence, m, neg_before(sentence, m.start())


def loss_context(para_text: str, sentence: str) -> bool:
    """R08: a sentence states a compensable loss when it carries a loss word, or is an enumerated
    entry of a paragraph that carries one."""
    return bool(LOSS_CONTEXT.search(sentence)) or (bool(ENUMERATED.match(sentence.lstrip(",:"))) and bool(LOSS_CONTEXT.search(para_text)))


SLOTS = {
    # (a) the head may be named 设计价款/设计损失/设计工作价款/设计成果结算款 and 中标交易服务费 (the
    # name on evidence 10); (b) a trailing amount is not bound to the NEXT head across a list connector
    # (¥2583218.16及二期初步设计费¥1680000 / ¥1680000、二期中标服务费…¥8487.5); (c) 中标服务费¥17500,其中(二期)分摊¥8487.5
    # binds the share.
    "design": re.compile(r"(?:初步)?设计(?:工作|成果)?(?:费|费用|成果费|价款|损失|结算款)[^¥。;,]{0,8}?¥([\d.]+)|¥([\d.]+)[^¥。;,及和与、]{0,4}?的?(?:二期)?(?:初步)?设计(?:费|费用)"),
    "temp": re.compile(r"临时设施(?:费|费用)?[^¥。;,]{0,8}?¥([\d.]+)|临设(?:费|费用)[^¥。;,]{0,8}?¥([\d.]+)|¥([\d.]+)[^¥。;,及和与、]{0,4}?的?(?:二期)?临时设施(?:费|费用)"),
    "fee": re.compile(r"中标(?:交易)?服务费[^¥。;,]{0,24}?分摊(?:的|部分为|部分)?[^¥。;,]{0,6}?¥([\d.]+)|中标(?:交易)?服务费[^¥。;,]{0,8}?¥([\d.]+)|¥([\d.]+)[^¥。;,及和与、]{0,4}?的?(?:二期)?(?:分摊的?)?中标(?:交易)?服务费"),
}
GOLDEN_SLOT = {"design": DESIGN_FEE, "temp": TEMP_FACILITIES, "fee": SERVICE_FEE_SHARE, "profit": GOLDEN_PROFIT}


def slot_value(m: re.Match) -> str:
    return next(g for g in m.groups() if g)


def loss_blocks(doc: Doc) -> list[dict]:
    """R08: a facts paragraph where B公司 compensates, plus the enumerated lines that directly follow it."""
    blocks, current = [], None
    for para in facts_paragraphs(doc):
        first = para["sentences"][0] if para["sentences"] else ""
        raw_line = para["line"].get("raw", "")
        # n01_clean intentionally strips Markdown bullets and numbering from
        # the canonical text.  Keep the carrier prefix as the structural
        # signal so an unordered or Chinese-enumerated loss list remains part
        # of its preceding B-company block.
        list_prefix = bool(
            ENUMERATED.match(raw_line.lstrip())
            or UNORDERED.match(raw_line)
            or re.match(r"^\s*[一二三四五六七八九十]+[、.)]", raw_line)
        )
        if current is not None and (list_prefix or ENUMERATED.match(first)) and len(para["text"]) <= 300:
            current["entries"].append(para)
            continue
        current = None
        if len(para["text"]) <= 700 and comp_b(para["text"]):
            current = {"lead": para, "entries": []}
            blocks.append(current)
    return blocks


def loss_slot_hits(doc: Doc, slot: str) -> list[tuple[dict, str, str]]:
    """R08: adopted loss items (facts loss blocks where B compensates, or request items against B)."""
    found = []
    pattern = SLOTS[slot]
    for block in loss_blocks(doc):
        lead_text = block["lead"]["text"]
        for para in [block["lead"]] + block["entries"]:
            context = para["text"] if para is block["lead"] else lead_text
            for sentence in para["sentences"]:
                if excluded_context(sentence) or GAP_TOKEN in sentence:
                    continue
                if not (loss_context(context, sentence) or (para is not block["lead"] and LOSS_CONTEXT.search(lead_text))):
                    continue
                for m in pattern.finditer(sentence):
                    if slot == "fee" and re.search(r"分摊[^¥。;]{0,12}¥", sentence[m.end():]):
                        continue
                    c0 = max(sentence.rfind(",", 0, m.start()), sentence.rfind(":", 0, m.start())) + 1
                    c1 = sentence.find(",", m.end())
                    clause = sentence[c0:c1 if c1 >= 0 else len(sentence)]
                    if re.search(r"报价|合同价|中标价|价款|投标", clause) and not LOSS_CONTEXT.search(clause):
                        continue  # price recital, not a loss item
                    if not neg_before(sentence, m.start()):
                        found.append((para["line"], slot_value(m), "facts"))
    damage_lines = {i["line"]["locator"] for i in damages_items(doc, "B") + money_items(doc, "B")}
    carried, parent = [], None
    for item in request_items(doc):
        # Verb-less sub-lines under a money request that ends in 其中: itemise that request
        if item["line"]["locator"] in damage_lines:
            parent = item if re.search(r"其中[:：]?$", item["text"].rstrip("。;")) and "基数" not in item["text"] else None
            carried.append(item)
        elif parent is not None and not re.search(REQ_VERBS, item["text"]):
            carried.append({"text": item["text"], "line": item["line"], "sub": True})
        else:
            parent = None
    for item in carried:
        if excluded_context(item["text"]):
            continue
        # An amount labelled in a trailing parenthesis (¥2583218.16(二期临时设施费)) names that head
        text = re.sub(r"¥([\d.]+)元?\(([^()]{2,16})\)", r"\2¥\1", item["text"])
        for clause in re.split(r"[,;。、()]", text):
            if GAP_TOKEN in clause:
                continue
            if clause.lstrip().startswith("其中") and "基数" in item["text"]:
                continue  # itemised base, not a loss item
            for m in pattern.finditer(clause):
                if not neg_before(clause, m.start()):
                    found.append((item["line"], slot_value(m), "request"))
    return found


def both_unresolved(doc: Doc) -> str | None:
    a, b = unresolved(doc, "facts"), unresolved(doc, "request")
    if a and b:
        return "ambiguous" if "ambiguous" in (a, b) else "missing"
    return None


def eval_p10(judge, doc):
    z = both_unresolved(doc)
    if z:
        return credit(judge, doc, "P10", "facts+request", 0, z, "facts and request sections unresolved", [], "loss.reliance_items")
    design = loss_slot_hits(doc, "design")
    temp = loss_slot_hits(doc, "temp")
    lines = [h[0] for h in design + temp]
    if not design and not temp:
        return credit(judge, doc, "P10", "facts+request", 0, "missing", "no reliance loss items", [], "loss.reliance_items")
    dv, tv = {h[1] for h in design}, {h[1] for h in temp}
    if len(dv) > 1 or len(tv) > 1:
        return credit(judge, doc, "P10", "facts+request", 0, "ambiguous", "mixed candidate amounts for one loss item", lines, "loss.reliance_items")
    good = int(dv == {DESIGN_FEE}) + int(tv == {TEMP_FACILITIES})
    if good == 2:
        return credit(judge, doc, "P10", "facts+request", 1.0, "exact", "phase II preliminary design fee 1,680,000 and temporary facilities 2,583,218.16 claimed as losses", lines, "loss.reliance_items", "N02")
    if good == 1:
        return credit(judge, doc, "P10", "facts+request", 0.5, "partial", "only one reliance loss item carries the correct amount", lines, "loss.reliance_items", "N02")
    return credit(judge, doc, "P10", "facts+request", 0, "different", "reliance loss items carry other amounts", lines, "loss.reliance_items", "N02")


def eval_p12(judge, doc):
    z = both_unresolved(doc)
    if z:
        return credit(judge, doc, "P12", "facts+request", 0, z, "facts and request sections unresolved", [], "loss.service_fee_share")
    hits = loss_slot_hits(doc, "fee")
    lines = [h[0] for h in hits]
    values = {h[1] for h in hits}
    if not hits:
        return credit(judge, doc, "P12", "facts+request", 0, "missing", "no bid service fee loss item", [], "loss.service_fee_share")
    if len(values) > 1:
        return credit(judge, doc, "P12", "facts+request", 0, "ambiguous", "mixed bid service fee amounts", lines, "loss.service_fee_share")
    if values == {SERVICE_FEE_SHARE}:
        return credit(judge, doc, "P12", "facts+request", 1.0, "exact", "phase II share 8,487.5 of the bid service fee claimed as a loss", lines, "loss.service_fee_share", "N02")
    return credit(judge, doc, "P12", "facts+request", 0, "different", "bid service fee loss carries another amount", lines, "loss.service_fee_share", "N02")


# The registry wording (B公司的企业类型为“有限责任公司(非自然人投资或控股的法人独资)”) and
# C公司为其唯一股东 state the one-person premise too.
ONE_PERSON = re.compile(r"B公司[^。;,]{0,8}(是|系|为|属于|属)[^。;,]{0,24}(一人(有限责任|有限)?公司|法人独资|全资子公司)|"
                        r"B公司[^。;]{0,60}?(股东仅(有|为)|唯一(的)?股东(为|是|系))(被告[一二三四1234]?)?C公司|"
                        r"C公司[^。;,]{0,8}(是|系|为)[^。;,]{0,6}(B公司|其)[^。;,]{0,4}(的)?(唯一|全资|独资)股东|"
                        r"(B公司|(?P<pron>其))[^。;,]{0,6}(唯一|全资|独资)股东(为|是|系)(被告[一二三四1234]?)?C公司|"
                        r"B公司[^。;,]{0,10}(全部股权|全部股份|全部出资份额)[^。;,]{0,10}(由|为|归)(被告[一二三四1234]?)?C公司(持有|享有)|"
                        r"C公司[^。;,]{0,10}(持有|享有)B公司[^。;,]{0,10}(全部股权|全部股份|全部出资份额)|"
                        r"C公司[^。;,]{0,6}(的)?全资子公司B公司")


def eval_p13(judge, doc):
    z = unresolved(doc, "facts")
    if z:
        return credit(judge, doc, "P13", "facts", 0, z, "facts section unresolved", [], "facts.shareholder_liability")
    full, other = [], []
    for para in facts_units(doc):
        # a subsection title announces the argument; premise and conclusion are read from body lines only
        if len(para["text"]) > 700 or any(is_heading_line(line) for line in para["lines"]):
            continue
        premise = conclusion = False
        for sentence in para["sentences"]:
            if excluded_context(sentence):
                continue
            for p in ONE_PERSON.finditer(sentence):
                if p.group("pron") and nearest_subject(sentence, p.start("pron")) != "B":
                    continue
                if not neg_before(sentence, p.end() - 2):
                    premise = True
            if joint_c(sentence):
                conclusion = True
            elif re.search(r"其不能证明[^。;]{0,40}(承担|负|负担)连带(清偿|赔偿|给付)?责任", sentence) \
                    and re.search(r"C公司[^。;]{0,20}(B公司|其)[^。;]{0,8}(唯一|全资|独资)股东", para["text"]):
                conclusion = True
        if premise and conclusion:
            full.append(para)
        elif conclusion:
            other.append(para)
    if full:
        return credit(judge, doc, "P13", "facts", 1.0, "exact", "B公司 is a one-person company wholly owned by C公司, so C公司 is jointly liable", [l for p in full for l in p["lines"]], "facts.shareholder_liability")
    if other:
        return credit(judge, doc, "P13", "facts", 0, "different", "joint liability of C公司 argued without the one-person-company premise", [l for p in other for l in p["lines"]], "facts.shareholder_liability")
    return credit(judge, doc, "P13", "facts", 0, "missing", "no shareholder liability reasoning", [], "facts.shareholder_liability")


# ----- format, section and order items -------------
# Each item is all-or-nothing: every element must hold, otherwise 0 (no half tier).
PLACEHOLDER_NAME = re.compile(r"待|未|暂|无|不详")  # 待补/未定… are gap placeholders, not names


RULE_LINE = re.compile(r"[-*_=~—]{3,}")
COST_ITEM = re.compile(r"(诉讼费|受理费|保全费)[^;。]{0,30}(负担|承担)|(承担|负担)[^;。]{0,30}(诉讼费|受理费|保全费)")


def request_kinds(doc: Doc) -> list[dict]:
    """R13: every request line classified into request kinds, in document order (item index, kinds with offsets)."""
    key = lambda item: (item["line"]["locator"], item["text"])
    term = {key(i["item"]) for i in termination_items(doc)}
    money = {key(i) for i in damages_items(doc, "B")}
    fee = {key(i["item"]) for i in occupation_items(doc)}
    out = []
    items = [i for i in request_items(doc) if not RULE_LINE.fullmatch(i["line"]["clean"])]
    for n, item in enumerate(items):
        text, kinds = item["text"], {}
        if key(item) in term:
            kinds["termination"] = text.find("解除")
        if key(item) in money:
            m = re.search(r"(赔偿|赔付|支付|给付)", text)
            kinds["b_money"] = m.start() if m else 0
        if key(item) in fee:
            m = re.search(r"资金占用|利息|逾期付款损失|迟延付款损失", text)
            kinds["fee"] = m.start() if m else 0
        if joint_c(text):
            kinds["c_joint"] = text.find("连带")
        if COST_ITEM.search(text):
            kinds["costs"] = COST_ITEM.search(text).start()
        out.append({"n": n, "item": item, "kinds": kinds})
    return out


def eval_p19(judge, doc):
    """P19 request order: termination (if any) first, B公司's principal money before the capital occupation fee,
    both before C公司's joint liability, costs last; money, fee, joint liability and costs must all be present."""
    z = unresolved(doc, "request")
    if z:
        return credit(judge, doc, "P19", "request", 0, z, "request section unresolved", [], "format.request_order")
    rows = request_kinds(doc)
    lines = [r["item"]["line"] for r in rows]
    pos = {}
    for r in rows:
        for k, off in r["kinds"].items():
            pos.setdefault(k, []).append((r["n"], off))
    missing = [k for k in ("b_money", "fee", "c_joint", "costs") if k not in pos]
    if missing:
        return credit(judge, doc, "P19", "request", 0, "missing" if not rows else "different",
                      f"request kinds absent for an order check: {missing}", lines if rows else [], "format.request_order")
    problems = []
    last = max(r["n"] for r in rows if r["kinds"])
    if "termination" in pos:
        t = max(n for n, _ in pos["termination"])
        others = [n for k in ("b_money", "fee", "c_joint", "costs") for n, _ in pos[k]]
        if t >= min(others):
            problems.append("termination is not the first request")
    if max(pos["b_money"]) >= min(pos["fee"]):
        problems.append("capital occupation fee precedes a principal money request")
    b_side = [n for k in ("b_money", "fee") for n, _ in pos[k]]
    if max(b_side) >= min(n for n, _ in pos["c_joint"]):
        problems.append("C公司's joint liability precedes B公司's requests")
    if [n for n, _ in pos["costs"]] != [last] or any(n == last for k in ("b_money", "fee", "c_joint", "termination") for n, _ in pos.get(k, [])):
        problems.append("costs request is not the last, separate item")
    if problems:
        return credit(judge, doc, "P19", "request", 0, "different", "; ".join(problems), lines, "format.request_order")
    return credit(judge, doc, "P19", "request", 1.0, "exact", "requests ordered principal -> fee -> joint liability -> costs", lines, "format.request_order")


def eval_p21(judge, doc):
    """P21 statutes sit beside the propositions they support: at least two article citations in the facts section,
    with applicable case propositions; no standalone heading or closing statute list."""
    z = unresolved(doc, "facts")
    if z:
        return credit(judge, doc, "P21", "facts", 0, z, "facts section unresolved", [], "format.legal_basis_placement")
    cites, problems, lines = 0, [], []
    for line in doc.sections["facts"]:
        if re.search(r"法律依据|法律规定依据", line["clean"]) and is_heading_line(line):
            problems.append("separate 法律依据 heading")
        for sentence in split_sentences(line["assert"]):
            n = len(set(re.findall(r"§\d+", sentence)))
            # Citation count is not a defect; assess applicable proposition binding.
            if not n or excluded_context(sentence) or neg_before(sentence, sentence.find("§")):
                continue
            lines.append(line)
    # Count distinct citations tied to a case proposition, not paragraphs or a
    # mandatory set of article numbers. Multiple appropriate citations may share a sentence.
    bound = {article for line in lines if re.search(r"B公司|C公司|合同|损失|利息|资金占用", line["assert"])
             for article in re.findall(r"§\d+", line["assert"])}
    cites = len(bound)
    if re.search(r"《(中华人民共和国)?合同法》", "".join(l["assert"] for l in doc.sections["facts"])):
        problems.append("repealed Contract Law cited")
    if cites < 2:
        return credit(judge, doc, "P21", "facts", 0, "missing" if not lines else "different",
                      f"fewer than two of the carrying statutes sit beside their propositions: {bound}", lines, "format.legal_basis_placement")
    if problems:
        return credit(judge, doc, "P21", "facts", 0, "different", "; ".join(problems[:4]), lines, "format.legal_basis_placement")
    return credit(judge, doc, "P21", "facts", 1.0, "exact", "each statute cited beside its proposition", lines, "format.legal_basis_placement")


# ----- D13 verbatim material coverage ------------------------------------------------------
MATERIAL_NGRAM = 12
_MATERIAL_GRAMS: set | None = None


def _norm_copy(text: str) -> str:
    return re.sub(r"[\s\*#`>|_\-—()（）《》“”\"'‘’、,，。;；:：.!！?？【】\[\]]", "", unicodedata.normalize("NFKC", text))


def material_identity_text():
    import zipfile
    import xml.etree.ElementTree as ET
    root = PACKAGE_ROOT / "materials"
    texts = []
    for path in sorted(root.glob("*")):
        if path.suffix == ".docx":
            with zipfile.ZipFile(path) as z:
                for name in z.namelist():
                    if name.startswith("word/") and name.endswith(".xml"):
                        texts.append("".join(ET.fromstring(z.read(name)).itertext()))
        elif path.suffix in (".md", ".txt"):
            texts.append(path.read_text(encoding="utf-8"))
    return unicodedata.normalize("NFKC", "".join(texts)).replace(" ", "")


def supported_identity(segment):
    source = material_identity_text()
    values = re.findall(r"[0-9A-Z]{18}|(?<!\d)1[3-9]\d{9}(?!\d)|(?<!\d)0\d{2,3}-\d{7,8}(?!\d)", segment)
    if values: return all(value in source for value in values)
    value = re.sub(r"^(住所地?|地址|住址|住|法定代表人|负责人|法人代表):?", "", segment)
    return len(value) >= 2 and value in source


def material_grams() -> set | None:
    """R14: 12-character n-grams of every material text (evidence-list and evidence-bundle DOCX XML text and OCR)."""
    global _MATERIAL_GRAMS
    if _MATERIAL_GRAMS is not None:
        return _MATERIAL_GRAMS
    import zipfile
    root = PACKAGE_ROOT / "materials"
    if not root.is_dir():
        return None
    texts = []
    for path in sorted(root.iterdir()):
        if path.suffix == ".docx":
            with zipfile.ZipFile(path) as z:
                texts.append("".join(re.sub(r"<[^>]+>", "", z.read(n).decode("utf8", "ignore")) for n in z.namelist() if n.endswith(".xml")))
        elif path.suffix in (".md", ".txt"):
            texts.append(path.read_text(encoding="utf-8"))
    joined = _norm_copy("".join(texts))
    _MATERIAL_GRAMS = {joined[i:i + MATERIAL_NGRAM] for i in range(len(joined) - MATERIAL_NGRAM + 1)}
    return _MATERIAL_GRAMS


def copied_share(text: str, grams: set) -> tuple[int, int]:
    t = _norm_copy(text)
    covered = [False] * len(t)
    for i in range(len(t) - MATERIAL_NGRAM + 1):
        if t[i:i + MATERIAL_NGRAM] in grams:
            for j in range(i, i + MATERIAL_NGRAM):
                covered[j] = True
    return sum(covered), len(t)


FABRICATED_PROCEDURE = (
    (r"(初步设计|设计文件|设计成果)[^。;,《]{0,30}?(评审|审查|审核|审批|批复)(已经?)?(通过|合格|同意)(?!后|之后|以后|时)", "design_review_passed"),
    (r"付款条件(已经?|业已)?成就", "payment_condition_fulfilled"),
    (r"(金额|费用|数额|款项|欠款)[^。;,]{0,6}?(B公司|被告)[^。;,]{0,8}?(书面)?(确认|认可|签认|承认)", "opponent_confirmed_amount"),
    (r"(B公司|被告)[^。;,]{0,10}?(书面)?(确认|认可|签认|承认)[^。;,]{0,12}(金额|数额|欠款|应付)", "opponent_confirmed_amount"),
    (r"(多次|反复|屡次|一再)(催告|催促|催要|催收|催款|发函)|(催告|催收)[^。;,]{0,10}(未果|无果)", "reminders"),
    (r"协商未果|(经|多次)(双方)?协商[^。;,]{0,10}(未果|无果|不成|未能)", "negotiation_failed"),
    (r"二期[^。;,]{0,20}(竣工)?验收合格", "phase2_accepted"),
)
FABRICATION_GUARD = r"视为|无法|不能|未能|尚未|未经|再无|不可能|阻止|拟|待|是否|如能|能否|应当?(组织|进行)"
DRAFTING_NOTE = re.compile(r"输入材料|本案材料(中)?(未|没有|并未)(载明|提供|记载)|不在(本)?起诉状中|臆造|(证据目录|证据清单)中曾|"
                           r"本诉按[^。;]{0,30}(重新)?计算|\(?说明:|起草说明|起草人|本状起草|提交前[^。;]{0,20}(核实|核对|补充|填写)|核实事项|核对提示")
PROCEDURAL_EXTRA = re.compile(r"申请[^。;,]{0,12}(鉴定|审计|评估)|申请(人民)?法院(依法)?(委托|调取|调查)|将在举证期限内|"
                              r"贵院(对本案)?(依法)?(享有|具有)管辖权|由[^。;,]{0,16}人民法院管辖|级别管辖")
COPY_SHARE_LIMIT = 0.5
FOREIGN_LETTERS_MIN = 40


VERSION_NOTE = re.compile(r"(19|20)(9\d|0\d|1\d|2[0-2])年[^。;,《]{0,4}(修正|修订)[^。;,《]{0,2}《(中华人民共和国)?公司法》|修正前|修订前|(原|旧)《(中华人民共和国)?公司法》")


class Deductions:
    def __init__(self, judge: ProgramJudge, doc: Doc):
        self.judge, self.doc, self.counter = judge, doc, 0

    def decide(self, item_id, sections, manifestations, key, root, reason, object_key):
        scans = [f"obs.scan.{s}" for s in sections]
        if not manifestations:
            states = {self.doc.section_state[s] for s in sections}
            state = "ambiguous" if states == {"ambiguous"} else "not_triggered"
            self.judge.deduction(item_id, state, scans, "error proposition not asserted" if state == "not_triggered" else "section unresolved")
            return
        occurrences, obs_ids, seen = [], [], set()
        for entry in manifestations:
            lines, detail = entry[0], entry[1]
            damage_key = entry[2] if len(entry) > 2 else key
            cause = entry[3] if len(entry) > 3 else root
            manifestation = f"{item_id}:{lines[0]['locator']}:{detail}"
            if manifestation in seen:
                continue
            seen.add(manifestation)
            self.counter += 1
            obs = observe_lines(self.judge, self.doc, f"obs.{item_id}.m{self.counter}", lines, object_key, "error_span", "N03")
            obs_ids.append(obs)
            occurrences.append({"damage_instance_key": damage_key, "causal_root_id": cause, "manifestation_id": manifestation,
                                "observation_id": obs, "reason": detail})
        self.judge.deduction(item_id, "triggered", scans + obs_ids, reason, occurrences)


def shape_count(lines: list[dict]) -> int:
    """N09: non-whitespace characters of body lines, excluding headings, the title and gap-marked clauses."""
    total = 0
    for line in lines:
        if line.get("heading") or TITLE_RE.fullmatch(line["clean"]):
            continue
        for clause in re.split(r"[,;。]", n06_gap(line["clean"])):
            if GAP_TOKEN not in clause:
                total += len(clause)
    return total


PROFIT_NAME = re.compile(PROFIT)
PROFIT_AFTER = re.compile(r"([^¥。;,]{0,10}?)¥([\d.]+)")
PROFIT_BEFORE = re.compile(r"¥([\d.]+)([^¥。;,]{0,6}?)的?$")
OTHER_LOSS_NAME = re.compile(r"设计|临时设施|临设|服务费|资金占用|利息|诉讼费|受理费|保全费")


def profit_amounts(sentence: str) -> list[tuple[int, str]]:
    """R08 profit binding: every expected-profit name binds the first amount written after it (within 10
    characters) and an amount written right before it (within 6 characters). The span between name and
    amount may not name another loss item, and an amount before the name may not be joined to it by a
    list connector (中标服务费¥8487.5及预期可得利益损失¥11624599.41 binds ¥8487.5 to the service fee)."""
    hits = []
    for name in PROFIT_NAME.finditer(sentence):
        after = PROFIT_AFTER.match(sentence, name.end())
        if after and not OTHER_LOSS_NAME.search(after.group(1)):
            hits.append((name.start(), after.group(2)))
        before = PROFIT_BEFORE.search(sentence[:name.start()])
        if before and not OTHER_LOSS_NAME.search(before.group(2)) and not re.search(r"[及和与、]", before.group(2)):
            hits.append((before.start(), before.group(1)))
    return hits


def eval_deductions(judge: ProgramJudge, doc: Doc) -> None:
    d = Deductions(judge, doc)
    items = request_items(doc)
    paras = facts_paragraphs(doc)
    entries = party_entries(doc) if doc.section_state["party"] == "identified" else []

    # D01 wrong defendant: the affiliate tenderer D公司 or the new winner E公司 sued or ordered to pay.
    found = []
    for entry in entries:
        for entity in sorted({"D", "E"} & set(entry["entities"])):
            if entry["role"] == "defendant" and not CANDIDATE.search(entry["line"]["assert"]):
                found.append(([entry["line"]], f"party_line-{entity}"))
    for item in items:
        for entity in ("D", "E"):
            m = re.search(r"(" + REQ_VERBS + r")[^;。]{0,20}?(?<!向)(?<!对)" + entity + r"公司[^;。]{0,20}?(" + PAY_VERBS + r"|承担[^;。]{0,8}责任)", item["text"])
            if m and adopted(item["text"], m.start(2)) and "第三人" not in item["text"][:m.end()]:
                found.append(([item["line"]], f"request_item-{entity}"))
    d.decide("D01", ["party", "request"], found, "wrong_defendant_non_party", "R-party",
             "D公司 or E公司, which are not parties to A公司's EPC contract, are sued or ordered to pay", "party.defendants")

    # D02 fabricated expected-profit figure instead of a gap marker.
    found = []
    spans = [(s, p["line"]) for p in paras for s in p["sentences"]] + [(c, i["line"]) for i in items for c in re.split(r"[,;。]", i["text"])]
    for sentence, line in spans:
        if GAP_TOKEN in sentence or excluded_context(sentence):
            continue
        for start, value in profit_amounts(sentence):
            if not neg_before(sentence, start):
                found.append(([line], f"profit-{value}"))
    d.decide("D02", ["request", "facts"], found, "fabricated_expected_profit_amount", "R-fabrication-profit",
             "asserts an expected-profit amount that no material supports instead of marking the gap", "loss.expected_profit_amount")

    # D03 misstated reliance or fee loss amounts (each loss item is an independent damage).
    found = []
    for slot in ("design", "temp", "fee"):
        for line, value, _where in loss_slot_hits(doc, slot):
            if value != GOLDEN_SLOT[slot]:
                found.append(([line], f"{slot}-{value}", f"loss_item_amount_{slot}", f"R-amount-{slot}"))
    d.decide("D03", ["request", "facts"], found, "loss_item_amount", "R-amount",
             "a loss item carries an amount the evidence list does not support (e.g. the full design fee or the whole service fee)", "loss.items")

    # D04 fabricated party identifiers.
    found = []
    for line in doc.sections["party"] if doc.section_state["party"] == "identified" else []:
        for segment in re.split(r"[,;。]", line["assert"]):
            if GAP_TOKEN in segment or supported_identity(segment):
                continue
            if re.search(r"住所地?|地址|住址|住", segment) and re.search(r"\d+(号|路|栋|室|弄|幢|单元|楼)", segment):
                found.append(([line], "address_digits"))
            if re.search(r"(统一社会信用代码|信用代码):?[0-9A-Z]{18}", segment):
                found.append(([line], "credit_code"))
            if re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)|(?<!\d)0\d{2,3}-\d{7,8}(?!\d)", segment):
                found.append(([line], "phone"))
            m = re.search(r"(法定代表人|负责人|法人代表):?([一-鿿]{2,4})", segment)
            if m and not re.search(r"某|职务|同上|不详", m.group(2)) and not PLACEHOLDER_NAME.match(m.group(2)):
                found.append(([line], "representative_name"))
    d.decide("D04", ["party"], found, "fabricated_party_identifiers", "R-fabrication-party",
             "invented party identifiers not present in the materials instead of a gap marker", "party.identifiers")

    # D05 repealed or superseded statutory basis.
    found = []
    for para in paras:
        for sentence in para["sentences"]:
            if QUOTE_REJECT.search(sentence):
                continue
            if re.search(r"《(中华人民共和国)?合同法》", sentence) and not re.search(r"已废止|废止|失效|原《", sentence):
                found.append(([para["line"]], "contract_law_citation"))
    for para, sentence, m, neg in cited_articles(doc, "company_law", 63):
        if not neg and not VERSION_NOTE.search(sentence[max(0, m.start() - 30):m.start()]):
            found.append(([para["line"]], "company_law_art63"))
    d.decide("D05", ["facts"], found, "repealed_law_basis", "R-law",
             "relies on the repealed Contract Law or the pre-2024 Company Law article 63 for a 2026 filing", "facts.legal_basis")

    # D06 concedes that B公司's notice validly terminated the contract.
    found = []
    spans = [(s, p["line"]) for p in paras for s in p["sentences"]] + [(i["text"], i["line"]) for i in items]
    for sentence, line in spans:
        if excluded_context(sentence):
            continue
        for pattern, label in (
            (r"(B公司|被告|发包人)[^。;,]{0,6}(依法|依约)?(享有|有权行使|具有|具备|行使了?)[^。;,]{0,4}(合同)?(法定|约定)?解除权", "employer_has_right"),
            (r"(B公司|被告|发包人)[^。;,]{0,6}有权(单方)?(部分)?解除", "employer_entitled"),
            (r"(于|自|在)@" + NOTICE_DATE + r"(起)?[^。;,]{0,6}(已经|已)?(解除|终止)", "terminated_on_notice_date"),
            (r"解除通知(书)?》?[^。;,]{0,6}(合法有效|依法有效|已生效|已经生效|发生(法律)?效力|产生(法律)?效力)", "notice_effective"),
        ):
            m = re.search(pattern, sentence)
            if m and not neg_before(sentence, m.end() - 2) and not NO_RIGHT_NEGATED.search(sentence[:m.start()]):
                found.append(([line], label))
    d.decide("D06", ["request", "facts"], found, "conceded_valid_termination", "R-termination-theory",
             "concedes that B公司 validly terminated the contract, destroying the breach theory", "facts.termination_validity")

    # D07 unsupported rate or penalty standard.
    found = []
    for item in items:
        text = item["text"]
        if not re.search(REQ_VERBS, text) or excluded_context(text) or REQ_NEG.search(text):
            continue
        hit = "lpr_multiplier" if multiplier_above_one(text) else None
        if not hit and re.search(r"日(万分之|千分之)", text):
            hit = "daily_penalty_rate"
        if not hit:
            for m in re.finditer(r"年(化)?(利)?率(为|按)?([\d.]+)%", text):
                try:
                    if Decimal(m.group(4)) > MAX_REASONABLE_ANNUAL_RATE:
                        hit = "annual_rate_above_lpr"
                except InvalidOperation:
                    pass
        if not hit:
            m = re.search(r"(" + PAY_VERBS + r")[^;。]{0,12}违约金", text)
            if m and adopted(text, m.start()):
                hit = "liquidated_damages"
        if hit:
            found.append(([item["line"]], hit))
    d.decide("D07", ["request"], found, "unsupported_rate_or_penalty", "R-rate",
             "interest, penalty or liquidated damages standard with no contractual or legal support in the materials", "request.rate")

    # D10 fabricated procedure or opponent acknowledgement (no material records it).
    found = []
    spans = [(s, p["line"]) for p in paras for s in p["sentences"]] + [(i["text"], i["line"]) for i in items]
    for sentence, line in spans:
        if GAP_TOKEN in sentence or CANDIDATE.search(sentence) or QUOTE_REJECT.search(sentence) or CONDITIONAL.search(sentence):
            continue
        for pattern, label in FABRICATED_PROCEDURE:
            for m in re.finditer(pattern, sentence):
                clause_start = max(sentence.rfind(",", 0, m.start()), sentence.rfind(":", 0, m.start())) + 1
                clause_end = min([x for x in (sentence.find(",", m.end()), len(sentence)) if x >= 0])
                clause = sentence[clause_start:clause_end]
                if re.search(FABRICATION_GUARD, clause):
                    continue
                found.append(([line], label))
                break
    d.decide("D10", ["request", "facts"], found, "fabricated_procedure", "R-fabrication-procedure",
             "asserts a procedural event or an acknowledgement by B公司 that no material records", "facts.procedure")

    # D11 drafting notes addressed to the drafter, not the court.  The filing
    # can leave such a note after the facts section (for example below the
    # signature or in an attachment list), so scan the complete carrier.
    found = []
    for line in doc.lines:
        for sentence in split_sentences(line["assert"]):
            m = DRAFTING_NOTE.search(sentence)
            if m:
                found.append(([line], "drafting_note"))
    d.decide("D11", ["party", "request", "facts"], found, "drafting_note_in_filing", "R-extra-drafting-note",
             "internal drafting notes (input materials, recomputation against the own evidence list, 'not invented here') left in the filing", "facts.extra_content")

    # D12 procedural sections or applications the complaint does not call for.
    found = []
    for para in paras:
        if is_heading_line(para["line"]) and re.search(r"管辖", para["line"]["clean"]):
            found.append(([para["line"]], "jurisdiction_section"))
            continue
        for sentence in para["sentences"]:
            m = PROCEDURAL_EXTRA.search(sentence)
            if m and not neg_before(sentence, m.start()):
                found.append(([para["line"]], "procedural_application"))
                break
    d.decide("D12", ["facts"], found, "unrequested_procedural_content", "R-extra-procedural",
             "a jurisdiction argument, an appraisal application or an evidence-submission plan inside the complaint", "facts.extra_content")

    # D13 is settled by the required source-bound semantic judge. There is no
    # source-derived n-gram/share threshold for “bulk” copying.
    judge.deduction("D13", "not_triggered", ["obs.scan.facts"],
                    "semantic owner: no local hard copy-share threshold")

    # D14 language gate: the complaint is filed in Chinese. A request or facts sentence of at least 40 Latin
    # letters that make up more than half of its characters is prose in another language (LPR, EPC or a
    # standard number such as GF-2017-0216 stay far below 40 letters).
    found = []
    for name in ("request", "facts"):
        if doc.section_state[name] != "identified":
            continue
        for line in doc.sections[name]:
            for sentence in split_sentences(line["clean"]):
                letters = len(re.findall(r"[A-Za-z]", sentence))
                if letters >= FOREIGN_LETTERS_MIN and letters > 0.5 * len(sentence):
                    found.append(([line], "non_chinese_sentence"))
                    break
    d.decide("D14", ["request", "facts"], found, "non_chinese_filing", "R-language",
             "request or facts prose written in a language other than Chinese", "filing.language")

    # Retired: Golden-relative length ratios had no source-derived legal
    # threshold. Missing substance loses positive credit; copied prose and
    # foreign-language padding have their own evidence-based deductions.
    judge.deduction("D08", "not_triggered", ["obs.scan.request", "obs.scan.facts"],
                    "retired: no source-derived hard length threshold")


def eval_d15(judge: ProgramJudge, doc: Doc) -> None:
    """Unsupported priority over termination losses, only when adopted as a request."""
    d = Deductions(judge, doc)
    found = []
    for item in request_items(doc):
        text = item["text"]
        priority = re.search("优先受偿", text)
        if (priority and re.search(REQ_VERBS, text) and not REQ_NEG.search(text)
                and not excluded_context(text) and not negated_before(text, priority.start())):
            found.append(([item["line"]], "priority_right_over_loss"))
            break  # one error instance per filing
    d.decide("D15", ["request"], found, "unsupported_priority_claim", "R-priority-loss",
             "priority over loss heads is unsupported", "request.priority")


def eval_g01(judge: ProgramJudge, doc: Doc) -> None:
    """An omitted request loses its positive points; no second deduction."""
    judge.deduction("G01", "not_triggered", ["obs.scan.request"], "ordinary omission assessed by positive credit only")


def evaluate(registry: dict, judge: ProgramJudge) -> None:
    """Call positive() once per P and deduction() once per D."""
    if registry.get("parse_failure"):
        for item_id in judge.positives:
            judge.positive(item_id, 0.0, "obs.parse_failure", "artifact could not be parsed", "different")
        for item_id in judge.deductions:
            judge.deduction(item_id, "parse_failure", ["obs.parse_failure"], "artifact could not be parsed")
        return
    doc = registry["doc"]
    eval_p10(judge, doc)
    eval_p12(judge, doc)
    eval_p13(judge, doc)
    argued = any(judge._positive_results[item_id]["fraction"] > 0 for item_id in ("P10", "P12", "P13"))
    eval_p02(judge, doc, argued)
    eval_p19(judge, doc)
    eval_p21(judge, doc)
    eval_deductions(judge, doc)
    eval_d15(judge, doc)
    eval_g01(judge, doc)


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
