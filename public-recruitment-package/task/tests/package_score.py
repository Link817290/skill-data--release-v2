#!/usr/bin/env python3
"""Deterministic structural scorer for Recruitment Package Rubric v3.4.

The scorer intentionally reports semantic candidates instead of turning an
unmechanizable suspicion into a deduction.  Every contracted P and D item is
present in the output ledger, including items with no occurrence.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import struct
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile


VERSION = "3.4"
NOTICE = "XX融资担保有限公司2026年公开招聘公告.doc"
SCHEDULE = "附件1某融资担保有限公司2026年公开招聘岗位明细表.xlsx"
DIRECTORY = "附件2 湖南省2026年考试录用公务员专业指导目录.xlsx"
COMMITMENT = "附件3某融资担保有限公司公开招聘诚信承诺书.docx"
REQUIRED = [NOTICE, SCHEDULE, DIRECTORY, COMMITMENT]
# P04 and P12 remain the two heaviest items because they carry the most substance, but
# not at two thirds of the total. At that share the score was decided almost entirely by
# two assertions outside the scope of the standing procedure this task supplies, so the
# items the procedure does cover could not move the result whether or not they were done.
# The freed weight is returned to those items in proportion, which leaves the ordering of
# the ledger unchanged and lets the whole ledger, rather than two rows of it, decide.
P_WEIGHTS = {"P01": 0.2192, "P02": 0.0900, "P03": 0.2193, "P04": 0.1189, "P12": 0.1087,
             "P05": 0.0172, "P06": 0.0218, "P07": 0.0158, "P08": 0.0454,
             "P09": 0.0232, "P10": 0.0591, "P11": 0.0614}
D_SCALES: dict[str, float | str] = {
    "D01": .25, "D02": .20, "D03": .15, "D04": .06, "D05": .04,
    "D06": .04, "D07": .12, "D08": .10, "D09": .08, "D10": .08,
    "D11": .10, "D12": .10, "D13": .08, "D14": .08, "D15": .08,
    "D16": .08, "D17": .07, "D18": .12, "D19": .10, "D20": .10,
    "D21": .07, "D22": .07, "D23": .08, "D24": .08,
    "D25": .05, "D26": .03, "D27": .04,
    "D28": .10, "D29": .08, "D30": .08, "D31": .08, "D32": .12,
}
SHAPES = {
    "S01": (386, "notice qualification section"),
    "S02": (483, "notice position rules section"),
    "S03": (1679, "notice recruitment procedure section"),
    "S04": (671, "schedule used range"),
    "S05": (138, "General Manager duties"),
    "S06": (210, "General Manager requirements"),
    "S07": (109, "Business Officer duties"),
    "S08": (55, "Business Officer requirements"),
}
# How far above the reference a section may run before it is charged as padding. The
# reference length is one correct answer, not the length a correct answer has to have:
# a notice that states the same rules more fully is not padded, and charging from a
# quarter above made the deduction a length-matching rule that fired on nearly every
# submission and floored scores whose content was sound. The band is therefore set where
# the extra text stops being elaboration and becomes filler, and S01 keeps the wider band
# it already had because the qualification section legitimately varies most in length.
UPPER_TOLERANCE = {sid: (2.0 if sid == "S01" else 1.0) for sid in SHAPES}
LOWER_RATIO = {"S01": .25, "S02": .15, "S03": .25}

PRIVATE = [
    ("candidate_1", "name", "曾彬"), ("candidate_1", "telephone", "15673346153"),
    ("candidate_1", "email", "1259105801@qq.com"), ("candidate_2", "name", "罗闪"),
    ("candidate_2", "identity_number", "430623197909130018"),
    ("candidate_2", "telephone", "15580883919"),
    ("candidate_2", "email", "361624321@qq.com"),
    ("candidate_2", "home_address", "湖南省长沙市桔园立交桥电力局宿舍楼"),
    ("candidate_3", "name", "达先生"), ("candidate_4", "home_location", "安徽铜陵"),
]
REFEREES = [("referee_1", "刘勇"), ("referee_2", "王晓龙"),
            ("referee_3", "李永亮"), ("referee_1", "18656618383"),
            ("referee_2", "18156038857"), ("referee_3", "13856265338"),
            ("referee_3", "05622562166")]
NARRATIVE = ["株洲金财小额贷款有限公司", "株洲动力谷产业投资发展集团有限公司",
             "湖南省中小企业融资担保有限公司", "江苏雨润集团",
             "华夏通银融资租赁有限公司", "海军38470部队"]
TRUTH_EXCLUSIONS = [
    # The directory file carries its source publisher's attachment number and year;
    # those identity tokens are not an applicant-facing eligibility proposition.
    {"unit_id": "U019", "scope": "professional directory attachment number and year identity"},
]
EXCLUDED_PROPOSITION_MARKERS = []


def n(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").casefold()
    value = value.translate(str.maketrans({"，": ",", "。": ".", "；": ";", "：": ":",
                                          "（": "(", "）": ")", "【": "[", "】": "]",
                                          "、": ",", "—": "-", "－": "-"}))
    return re.sub(r"\s+", "", value)


def present(text: str, *terms: str) -> bool:
    target = n(text)
    return all(n(x) in target for x in terms)


def any_present(text: str, terms: list[str]) -> bool:
    target = n(text)
    return any(n(x) in target for x in terms)

def date_present(text: str, year: int, month: int, day: int) -> bool:
    target = n(text)
    return any(token in target for token in (
        f"{year}年{month}月{day}日", f"{year}-{month:02d}-{day:02d}",
        f"{year}/{month:02d}/{day:02d}", f"{year}-{month}-{day}", f"{year}/{month}/{day}"
    ))


def clauses(text: str) -> list[str]:
    return [x for x in re.split(r"[。；;!?！？\n\x0b\x0c]", text) if n(x)]


NEG = ["不", "不设", "不设置", "没有", "不得", "不能", "未", "禁止", "无须", "无需", "不予", "非"]
REJECT = ["示例", "错误", "不采用", "不实行", "不作为", "仅供参考", "候选方案"]


def adopted_clause(text: str, required: list[list[str]], forbidden: list[str] | None = None) -> str:
    """Return one local adopted clause satisfying every synonym group.

    A rule is often written across a sentence pair: the condition in one clause and
    what follows from it in the next. Requiring every group inside a single clause
    would score that correct writing as absent, so an adjacent pair is also searched
    once no single clause carries the rule. The window stops at two: a wider one stops
    being one local statement and starts accepting terms scattered through the document.
    """
    windows = clauses(text)
    windows += [a + "，" + b for a, b in zip(windows, windows[1:])]
    for clause in windows:
        compact = n(clause)
        if any(n(x) in compact for x in REJECT):
            continue
        if all(any(n(term) in compact for term in group) for group in required):
            if forbidden and any(n(x) in compact for x in forbidden):
                continue
            return clause.strip()
    return ""


def affirmative_phrase(text: str, phrases: list[str]) -> str:
    for clause in clauses(text):
        compact = n(clause)
        if any(n(x) in compact for x in REJECT):
            continue
        for phrase in phrases:
            pos = compact.find(n(phrase))
            prefix = compact[:pos] if pos >= 0 else ""
            # Negation can govern a predicate through a copula: 不视为自动符合条件.
            negated = bool(re.search(r"(?:不|未|不能|不得|并非|不应)(?:直接|当然|自动)?(?:视为|认定为|等同于|认为|代表|意味着|属于)?$", prefix))
            if pos >= 0 and not negated and not any(prefix.endswith(n(x)) for x in NEG):
                return clause.strip()
    return ""


CN_NUM = {"一":1,"二":2,"两":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10}
DURATION = re.compile(r"(\d+|[一二两三四五六七八九十]+)\s*年\s*(?:及|\(含\)|（含）|或)?\s*以上|满\s*(\d+|[一二两三四五六七八九十]+)\s*年")


def years_stated(text: str, floor: int) -> bool:
    """Is a duration of at least `floor` years stated, in whatever form the writer used?

    Matching the literal "5年以上" charged a correct requirement written as "5年及以上",
    "5年(含)以上", "满5年" or "五年以上" with having dropped the duration, and the charge
    is a deduction, so the more careful phrasing cost more than the exact one. The
    requirement is a number of years, not a spelling of it.
    """
    for m in DURATION.finditer(n(text)):
        raw = m.group(1) or m.group(2)
        if raw is None:
            continue
        if raw.isdigit():
            value = int(raw)
        else:
            value = CN_NUM.get(raw[-1], 0) if len(raw) == 1 else sum(CN_NUM.get(c, 0) for c in raw)
        if value >= floor:
            return True
    return False


def xml_text(raw: bytes) -> str:
    value = raw.decode("utf-8", "ignore")
    value = re.sub(r"</(?:w:p|w:tr|row|c)[^>]*>", "\n", value)
    value = re.sub(r"<(?:w:tab|w:br)[^>]*/>", "\t", value)
    return html.unescape(re.sub(r"<[^>]+>", "", value))


def docx_parts(path: Path) -> tuple[str, str]:
    with ZipFile(path) as z:
        names = z.namelist()
        if "word/document.xml" not in names:
            raise ValueError("missing word/document.xml")
        visible_names = ["word/document.xml"] + [x for x in names if re.fullmatch(r"word/(?:header|footer)\d+\.xml", x)]
        visible = "\n".join(xml_text(z.read(x)) for x in visible_names)
        hidden_names = [x for x in names if re.fullmatch(r"word/(?:comments\d*|footnotes|endnotes)\.xml", x)]
        hidden_names += [x for x in ("docProps/core.xml", "docProps/app.xml") if x in names]
        hidden_names += [x for x in names if x.startswith("word/embeddings/")]
        hidden = "\n".join(xml_text(z.read(x)) if x.endswith(".xml") else z.read(x).decode("latin1", "ignore") for x in hidden_names)
        return visible, hidden


def xlsx_parts(path: Path) -> tuple[str, str, dict[str, str], str]:
    with ZipFile(path) as z:
        names = z.namelist()
        sheets = sorted(x for x in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", x))
        if not sheets:
            raise ValueError("missing worksheets")
        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            shared = ["".join(y.text or "" for y in x.iter() if y.tag.endswith("}t")) for x in root]
        cells: dict[str, str] = {}
        rows_out: list[str] = []
        for sheet_index, name in enumerate(sheets, 1):
            root = ET.fromstring(z.read(name))
            for row in (x for x in root.iter() if x.tag.endswith("}row")):
                row_values = []
                for cell in (x for x in row if x.tag.endswith("}c")):
                    ref = cell.attrib.get("r", "?")
                    vals = [y.text or "" for y in cell.iter() if y.tag.endswith("}v") or y.tag.endswith("}t")]
                    value = "".join(vals)
                    if cell.attrib.get("t") == "s" and value.isdigit() and int(value) < len(shared):
                        value = shared[int(value)]
                    cells[f"sheet{sheet_index}!{ref}"] = value
                    row_values.append(value.replace("\n", " ⏎ "))
                rows_out.append(" | ".join(row_values))
        hidden_names = [x for x in names if re.fullmatch(r"xl/comments\d+\.xml", x)]
        hidden_names += [x for x in ("xl/workbook.xml", "docProps/core.xml", "docProps/app.xml") if x in names]
        hidden_names += [x for x in names if x.startswith("xl/drawings/") or x.startswith("xl/embeddings/")]
        hidden = "\n".join(xml_text(z.read(x)) if x.endswith(".xml") else z.read(x).decode("latin1", "ignore") for x in hidden_names)
        used = max((int(re.sub(r"\D", "", key)) for key in cells if re.search(r"\d", key)), default=0)
        return "\n".join(rows_out), hidden, cells, f"rows:1-{used}"


FREE, END = 0xFFFFFFFF, 0xFFFFFFFE


def legacy_doc_text(path: Path) -> str:
    data = path.read_bytes()
    if data[:8] != bytes.fromhex("d0cf11e0a1b11ae1"):
        raise ValueError("not CFB")
    sector_size, mini_size = 1 << struct.unpack_from("<H", data, 30)[0], 1 << struct.unpack_from("<H", data, 32)[0]
    first_dir, cutoff, first_minifat = struct.unpack_from("<I", data, 48)[0], struct.unpack_from("<I", data, 56)[0], struct.unpack_from("<I", data, 60)[0]
    difat = list(struct.unpack_from("<109I", data, 76)); ds = struct.unpack_from("<I", data, 68)[0]
    for _ in range(struct.unpack_from("<I", data, 72)[0]):
        vals = struct.unpack_from(f"<{sector_size // 4}I", data, 512 + ds * sector_size); difat.extend(vals[:-1]); ds = vals[-1]
    fat: list[int] = []
    for sid in difat:
        if sid not in (FREE, END) and sid < 0xFFFFFFFA:
            fat.extend(struct.unpack_from(f"<{sector_size // 4}I", data, 512 + sid * sector_size))
    def chain(start: int, table: list[int]) -> list[int]:
        out, seen = [], set()
        while start not in (FREE, END) and start < 0xFFFFFFFA and start not in seen and start < len(table):
            seen.add(start); out.append(start); start = table[start]
        return out
    def big(start: int, size: int | None = None) -> bytes:
        raw = b"".join(data[512 + x * sector_size:512 + (x + 1) * sector_size] for x in chain(start, fat))
        return raw if size is None else raw[:size]
    entries = []
    directory = big(first_dir)
    for off in range(0, len(directory), 128):
        ent = directory[off:off + 128]
        if len(ent) < 128: break
        ln = struct.unpack_from("<H", ent, 64)[0]
        entries.append((ent[:max(0, ln - 2)].decode("utf-16le", "ignore"), ent[66], struct.unpack_from("<I", ent, 116)[0], struct.unpack_from("<Q", ent, 120)[0]))
    root = next(x for x in entries if x[1] == 5); mini_stream = big(root[2], root[3]); minifat = []
    for sid in chain(first_minifat, fat): minifat.extend(struct.unpack_from(f"<{sector_size // 4}I", data, 512 + sid * sector_size))
    streams = {}
    for name, kind, start, size in entries:
        if kind != 2 or not name: continue
        streams[name] = (b"".join(mini_stream[x * mini_size:(x + 1) * mini_size] for x in chain(start, minifat))[:size] if size < cutoff else big(start, size))
    word = streams["WordDocument"]; flags = struct.unpack_from("<H", word, 10)[0]; table = streams["1Table" if flags & 0x0200 else "0Table"]
    fc, size = struct.unpack_from("<II", word, 154 + 33 * 8); clx = table[fc:fc + size]; pos = 0
    while pos < len(clx) and clx[pos] == 1: pos += 3 + struct.unpack_from("<H", clx, pos + 1)[0]
    if pos >= len(clx) or clx[pos] != 2: raise ValueError("missing piece table")
    ln = struct.unpack_from("<I", clx, pos + 1)[0]; plc = clx[pos + 5:pos + 5 + ln]; count = (ln - 4) // 12
    cps = struct.unpack_from(f"<{count + 1}I", plc, 0); pcd = 4 * (count + 1); parts = []
    for i in range(count):
        chars = cps[i + 1] - cps[i]; raw = struct.unpack_from("<I", plc, pcd + i * 8 + 2)[0]; compressed = bool(raw & 0x40000000); off = raw & 0x3FFFFFFF
        if compressed: off //= 2
        parts.append(word[off:off + chars].decode("cp936", "ignore") if compressed else word[off:off + chars * 2].decode("utf-16le", "ignore"))
    return "".join(parts).replace("\r", "\n").replace("\x07", "\t").replace("\x0b", "\n").replace("\x0c", "\n")


def rtf_text(path: Path) -> str:
    source = path.read_bytes().decode("latin1", "ignore")
    if not source.startswith("{\\rtf"): raise ValueError("not RTF")
    def uni(match: re.Match[str]) -> str:
        value = int(match.group(1)); return chr(value + 65536 if value < 0 else value)
    value = re.sub(r"\\u(-?\d+)\??", uni, source)
    value = re.sub(r"\\(?:par|line|row)\b\s?", "\n", value); value = re.sub(r"\\(?:tab|cell)\b", "\t", value)
    value = re.sub(r"\\'[0-9A-Fa-f]{2}", "", value); value = re.sub(r"\\[A-Za-z]+-?\d*\s?", "", value); value = re.sub(r"\\[^A-Za-z]", "", value)
    return value.replace("{", "").replace("}", "")


@dataclass
class Artifact:
    name: str
    state: str = "confirmed_missing"
    text: str = ""
    hidden: str = ""
    cells: dict[str, str] = field(default_factory=dict)
    sha256: str | None = None
    error: str | None = None


_PARSE_CACHE: dict[tuple[str, str], Artifact] = {}


def html_text(raw: bytes) -> str:
    """Readable text out of an HTML-bodied document."""
    for encoding in ("utf-8", "gb18030", "latin1"):
        try:
            value = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    value = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", value)
    value = re.sub(r"(?i)<(br|/p|/div|/tr|/h[1-6]|/li)\s*/?>", "\n", value)
    value = re.sub(r"(?i)</t[dh]>", "\t", value)
    value = html.unescape(re.sub(r"<[^>]+>", "", value))
    return re.sub(r"[ \t]*\n[ \t]*", "\n", value)


def doc_text(path: Path) -> str:
    """Text of a .doc, whichever container the writer actually produced.

    A .doc is a name for a role, not for one binary format: writers emit OLE2, RTF, or
    HTML under it, and Word opens all three. Reading only the first two makes the whole
    document unparseable when a submission chose the third, which zeroes every content
    item at once and reports a complete answer as an empty one. The rubric holds a
    change of carrier to be score neutral, so the carrier is detected and the same
    content checks run on the text either way.
    """
    head = path.read_bytes()[:512]
    if head[:5] == b"{\\rtf":
        return rtf_text(path)
    if head[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return legacy_doc_text(path)
    stripped = head.lstrip()[:64].lower()
    if stripped.startswith((b"<!doctype html", b"<html", b"<?xml", b"<meta", b"<body")) or b"<html" in head.lower():
        return html_text(path.read_bytes())
    return legacy_doc_text(path)


# The organisation is masked in the supplied materials, and the mask is not written
# consistently: the notice carries XX while the attachment beside it carries 某. A
# submission that harmonises the two is making a reasonable consistency call, and
# resolving the deliverable by exact filename scored that call as a missing notice --
# every content item on the notice went to zero while the notice sat complete in the
# output directory. The mask is therefore treated as a placeholder when locating a
# file: everything outside it still has to match exactly.
MASKS = ("XX", "某", "X", "〇", "＊", "*")


def resolve_artifact(output: Path, name: str) -> Path:
    if (output / name).is_file():
        return output / name
    if not output.is_dir():
        return output / name

    def skeleton(value: str) -> str:
        out = n(value)
        for mask in MASKS:
            out = out.replace(n(mask), "")
        return out

    target = skeleton(name)
    for candidate in sorted(output.iterdir()):
        if candidate.is_file() and skeleton(candidate.name) == target:
            return candidate
    return output / name


def parse_artifact(path: Path, name: str) -> Artifact:
    if not path.is_file() or path.stat().st_size == 0:
        return Artifact(name=name, error="missing or empty")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    cache_key = (path.suffix.lower(), digest)
    cached = _PARSE_CACHE.get(cache_key)
    if cached is not None:
        return Artifact(name=name, state=cached.state, text=cached.text, hidden=cached.hidden,
                        cells=dict(cached.cells), sha256=digest, error=cached.error)
    result = Artifact(name=name, sha256=digest)
    try:
        if path.suffix.lower() == ".doc": result.text = doc_text(path)
        elif path.suffix.lower() == ".docx": result.text, result.hidden = docx_parts(path)
        elif path.suffix.lower() == ".xlsx": result.text, result.hidden, result.cells, _ = xlsx_parts(path)
        else: raise ValueError("unsupported extension")
        result.state = "identified"
    except (ValueError, KeyError, BadZipFile, ET.ParseError, struct.error, OSError) as exc:
        result.state = "parse_failure"; result.error = f"{type(exc).__name__}: {exc}"
    _PARSE_CACHE[cache_key] = Artifact(name=name, state=result.state, text=result.text,
                                      hidden=result.hidden, cells=dict(result.cells),
                                      sha256=digest, error=result.error)
    return result


def section(text: str, starts: list[str], stops: list[str], by_subject: bool = False) -> tuple[str, str]:
    # RTF producers may encode visual paragraph breaks without a form our
    # lightweight decoder preserves. Recover major Chinese section headings
    # before classifying functional sections.
    text = re.sub(r"(?<!\n)(?=[一二三四五六七八九十]+[、,.，．])", "\n", text)
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    heading = re.compile(r"^[一二三四五六七八九十]+[、,.，．]")
    # A heading is matched by what it is about, not by one spelling of it. The listed
    # forms are exact strings, so a section headed 报名基本条件 or 招聘岗位及条件 --
    # the same section, one word longer or with the subject folded in -- was read as
    # absent, and every clause item that lives in it went to zero while the section sat
    # in the document. The fallback therefore accepts a heading that names the same
    # subject: it must carry one of the section's own nouns and must not be one of the
    # stop sections, which are matched first so a later section cannot capture it.
    def names_section(line: str) -> bool:
        compact = n(line)[:20]
        if any(n(s) in compact for s in starts):
            return True
        if not by_subject:
            return False
        # A heading that names conditions is this section, whatever else it also names.
        # Writers fold the roster and the conditions into one heading (招聘岗位及条件),
        # and testing the stop terms first rejected exactly that: the conditions live in
        # the section so the section is the one wanted. A bare 基本条件 carries no actor
        # word and is equally unambiguous. What must not be captured is a process
        # section, which is excluded by name rather than by the absence of a subject.
        if any(n(w) in compact for w in ("程序", "流程", "监督", "咨询", "纪律",
                                         "公示", "体检", "考察", "聘用", "待遇")):
            return False
        return any(n(w) in compact for w in ("条件", "资格"))

    start_index = next((i for i, line in enumerate(lines)
                        if heading.match(unicodedata.normalize("NFKC", line))
                        and names_section(line)), None)
    if start_index is None: return "", "confirmed_missing"
    end = next((i for i in range(start_index + 1, len(lines))
                if heading.match(unicodedata.normalize("NFKC", lines[i]))), len(lines))
    content = "\n".join(lines[start_index:end])
    return content, "identified" if n(content) else "ambiguous"


def role_rows(text: str) -> tuple[str, str, str]:
    rows = [row for row in text.splitlines() if "|" in row]
    gm = [row for row in rows if any(n(cell) == n("总经理") for cell in row.split("|"))]
    officer = [row for row in rows if any(n(cell) in {n("业务员"), n("业务专员")} for cell in row.split("|"))]
    if len(gm) == len(officer) == 1: return gm[0], officer[0], "identified"
    if not gm or not officer: return gm[0] if gm else "", officer[0] if officer else "", "confirmed_missing"
    return gm[0], officer[0], "ambiguous"


def evidence_state(artifacts: dict[str, Artifact], needed: list[str], condition: bool) -> str:
    bad = [artifacts[x].state for x in needed if artifacts[x].state != "identified"]
    if "parse_failure" in bad: return "parse_failure"
    if "ambiguous" in bad: return "ambiguous"
    if "confirmed_missing" in bad: return "confirmed_missing"
    return "identified" if condition else "confirmed_missing"


def evaluate(workspace: Path, truth: dict[str, Any] | None = None) -> dict[str, Any]:
    # The self-hash record is descriptive and never feeds a score. The harness copies
    # the tests directory to the container root, where there is no package above it, so
    # the ancestor is resolved only when it exists: reaching past the filesystem root
    # raised IndexError and took the whole scoring run to zero while the submission sat
    # complete on disk, which reads as a model that produced nothing.
    parents = Path(__file__).resolve().parents
    package = parents[2] if len(parents) > 2 else None
    input_hashes = {}
    if package is not None:
        input_hashes = {name: hashlib.sha256((package / name).read_bytes()).hexdigest()
                        for name in ["RUBRIC.md", "task/instruction.md"]
                        if (package / name).is_file()}
    output = workspace / "output" if (workspace / "output").is_dir() else workspace
    a = {name: parse_artifact(resolve_artifact(output, name), name) for name in REQUIRED}
    notice, schedule, directory, commitment = (a[x].text for x in REQUIRED)
    qualification, qstate = section(notice, ["报考资格条件", "报考条件", "报名条件", "招聘条件", "资格条件", "应聘条件"], ["招聘计划", "招聘岗位", "招聘程序"], by_subject=True)
    position_rules, prstate = section(notice, ["招聘计划", "招聘岗位", "岗位及人数"], ["招聘程序", "应聘条件", "资格条件"])
    # A publication may legitimately combine role and qualification rules under
    # one functional heading. Reuse that section for S01 only when it contains
    # actual applicant-qualification propositions; a bare role heading is not enough.
    if qstate == "confirmed_missing" and prstate == "identified" and any_present(
        position_rules, ["报考", "资格条件", "工作经历", "所学专业"]
    ):
        qualification, qstate = position_rules, "identified"
    if prstate == "confirmed_missing" and qstate == "identified" and any_present(
        qualification, ["工作经历", "工作年限", "报考岗位", "招聘岗位", "所学专业"]
    ):
        # Functional role/application rules may be merged under 报考条件.
        position_rules, prstate = qualification, "identified"
    procedure, procstate = section(notice, ["招聘程序"], ["人员管理", "其他"])
    if procstate == "confirmed_missing":
        # Open structure: several major functional stage headings may implement
        # the recruitment procedure without a wrapper titled “招聘程序”.
        lines = [x.strip() for x in notice.splitlines() if x.strip()]
        major = re.compile(r"^[一二三四五六七八九十]+[、,.，．]")
        start = next((i for i, line in enumerate(lines)
                      if major.match(unicodedata.normalize("NFKC", line))
                      and any_present(line, ["信息发布", "发布信息", "网上报名"])), None)
        if start is not None:
            stop = next((i for i in range(start + 1, len(lines))
                         if major.match(unicodedata.normalize("NFKC", lines[i]))
                         and any_present(lines[i], ["其他事项", "其他"])), len(lines))
            procedure = "\n".join(lines[start:stop])
            procstate = "identified" if n(procedure) else "ambiguous"
    if procstate == "confirmed_missing":
        # Functional stages may be distributed under separate equivalent
        # headings.  A complete stage chain is the procedure even without a
        # wrapper titled 招聘程序 or 信息发布.
        stage_groups = [
            ("报名", "申请"), ("资格审核", "资格审查", "资格初审"),
            ("面试",), ("体检",), ("考察",), ("公示",), ("聘用", "录用"),
        ]
        stage_hits = sum(any_present(notice, list(group)) for group in stage_groups)
        if stage_hits >= 4:
            procedure = notice
            procstate = "identified"
    gm, officer, row_state = role_rows(schedule)
    all_parsed = all(x.state == "identified" for x in a.values())
    directory_payload = all(any_present(directory, [x]) for x in ["学科类别名称", "研究生专业目录", "本科专业目录", "经济和管理学大类"])
    commitment_ok = any_present(commitment, ["承诺"]) and any_present(commitment, ["真实", "准确"])
    schedule_ok = row_state == "identified"
    notice_ok = bool(notice and schedule_ok and any_present(notice, ["招聘", "岗位", "附件"]))
    gate = all_parsed and notice_ok and schedule_ok and directory_payload and commitment_ok

    pclauses: dict[str, tuple[float, list[str], str]] = {}
    qualification_rules = qualification + "\n" + position_rules
    p01_clause = adopted_clause(qualification_rules, [["毕业证", "学历", "学位"], ["专业"], ["填写", "认定", "依据", "按照"]])
    pclauses["P01"] = (1.0 if p01_clause else 0.0, [p01_clause] if p01_clause else [], "credential to professional identity adopted relation")
    role_scope = schedule_ok and present(gm, "经济和管理学大类") and present(officer, "经济和管理学大类")
    direct_directory_scope = any_present(qualification_rules, ["专业指导目录", "专业目录"])
    adopted_attachment_scope = (any_present(notice, ["岗位明细表", "岗位表"])
                                and any_present(notice, ["专业指导目录", "专业目录"]))
    notice_scope = present(qualification_rules, "专业") and (direct_directory_scope or adopted_attachment_scope)
    narrower = affirmative_phrase(qualification_rules, ["仅金融专业", "仅会计专业", "只限金融专业"])
    pclauses["P02"] = (1.0 if role_scope and notice_scope and not narrower else 0.0, ["schedule role rows", "notice qualification section"], "same directory hierarchy bound to both roles")
    unlisted = adopted_clause(qualification_rules, [["未列入", "未收录", "目录外", "未能直接认定", "不能直接认定", "无法直接认定"], # The recruiting entity is this notice's own author, so the natural way to name it
                                        # is the first person: 公司 / 我司 / 用人单位. Listing only the formal
                                        # third-person forms rejected the ordinary correct wording -- "所学专业未列入
                                        # 该目录的，由公司结合本人所学课程进行认定" states the rule exactly and was
                                        # scored as absent. The four groups still have to co-occur in one local window,
                                        # so a company name appearing elsewhere in the notice cannot satisfy this.
                                        ["招聘集团", "招聘单位", "招聘实体", "招聘工作组", "招录机关",
                                         "公司", "我司", "本单位", "用人单位", "招聘方", "集团",
                                         "招聘组织方", "组织方", "招聘工作组织"], ["材料", "课程", "学习证明"], ["认定", "审核", "复核"]])
    uncertain = unlisted and not affirmative_phrase(unlisted, ["直接符合", "自动符合", "一律不符合", "自动不符合"])
    fraction03 = 1.0 if uncertain and any_present(unlisted, ["材料", "课程", "学习证明"]) else (.5 if uncertain else 0.0)
    pclauses["P03"] = (fraction03, [unlisted] if unlisted else [], "bounded recruiting entity review for unlisted profession")
    # The rule is that a requirement naming one profession does not reach its class.
    # Both halves are keyed to what is being said, not to one wording of it: a notice
    # may name the antecedent as a specific, single or named profession, and may state
    # the consequence as only-that-profession, as no-expansion, or as the class not
    # counting. Keying to the reference answer's phrasing scores every other correct
    # way of writing the same rule as absent.
    p04_clause = adopted_clause(qualification_rules,
                                [["具体专业", "特定专业", "单个专业", "单一专业", "某一专业",
                                  "某个专业", "一个专业", "专业名称", "列明专业", "明确专业",
                                  "列明", "写明", "填写的是"],
                                 ["仅该专业", "只有该专业", "只该专业", "不包括专业类", "非某类专业",
                                  "不得扩大", "不能扩大", "不向上", "不扩展", "不扩大到",
                                  "不视为符合", "不属于符合", "不算符合", "不得以专业类",
                                  "不能以专业类", "不能以所属", "不得以所属", "完全一致", "须一致",
                                  "必须一致", "专业类不", "大类不"]])
    pclauses["P04"] = (1.0 if p04_clause else 0.0, [p04_clause] if p04_clause else [], "specific profession does not expand upward")
    # Being in the directory is not by itself qualifying; the profession must also sit
    # inside the role's own requirement. Same reason as P04 for the breadth here.
    p12_clause = adopted_clause(qualification_rules,
                                [["已列入", "目录内", "列入目录", "列入《", "收录", "目录中",
                                  "属于目录", "出现在目录", "目录中的", "目录所列"],
                                 ["未列入招聘岗位要求", "不在岗位专业范围", "不属于岗位专业范围",
                                  "未列入岗位", "不在岗位要求", "未列入招聘岗位", "不在招聘岗位",
                                  "未被岗位", "未出现在岗位", "岗位专业栏未", "不在岗位专业",
                                  "岗位未要求", "岗位要求之外", "岗位专业范围之外", "非岗位要求"],
                                 ["不符合", "不得报考", "不能报考", "不予", "不视为符合",
                                  "不算符合", "并不等于符合", "不等于符合"]])
    pclauses["P12"] = (1.0 if p12_clause else 0.0, [p12_clause] if p12_clause else [], "directory inclusion outside role scope is insufficient")
    visible = notice + "\n" + schedule + "\n" + directory + "\n" + commitment
    hidden = "\n".join(x.hidden for x in a.values())
    narrative_hits = [x for x in NARRATIVE if n(x) in n(visible)]
    visible_private = [(person, cls, value) for person, cls, value in PRIVATE if n(value) in n(visible)]
    hidden_private = [(person, cls, value) for person, cls, value in PRIVATE if n(value) in n(hidden)]
    hidden_referee = [(person, value) for person, value in REFEREES if n(value) in n(hidden)]
    pclauses["P05"] = (1.0 if gate and not narrative_hits else 0.0, [f"excluded narrative hits={len(narrative_hits)}"], "candidate source role separation; gated")
    pclauses["P06"] = (1.0 if gate and not visible_private else 0.0, [f"visible private hits={len(visible_private)}"], "visible identifier absence; gated")
    pclauses["P07"] = (1.0 if gate and not hidden_private and not hidden_referee else 0.0, [f"hidden identifier hits={len(hidden_private) + len(hidden_referee)}"], "hidden identifier absence; gated")
    prohibited = any(adopted_clause(commitment, [[x], ["填写", "号码", "邮箱", "电话"]]) for x in ["身份证", "联系电话", "电子邮箱", "邮箱"])
    comprehensive = (any_present(commitment, ["个人信息", "全部信息", "证明资料", "证明材料", "证件", "提交", "提供的材料"])
                     and any_present(commitment, ["材料", "资料", "信息", "证件"])
                     and any_present(commitment, ["全部", "完整", "所有"])
                     and any_present(commitment, ["真实", "准确"]))
    consequence = any_present(commitment, ["后果", "取消考试", "取消聘用", "责任"])
    signature = any_present(commitment, ["签名", "签字"])
    date = any_present(commitment, ["日期"]) or bool(re.search(r"[_＿—\-]{2,}年[_＿—\-]{2,}月[_＿—\-]{2,}日", commitment))
    f08 = 1.0 if gate and comprehensive and consequence and signature and date and not prohibited else (.5 if gate and comprehensive and consequence and not prohibited and (signature or date) else 0.0)
    pclauses["P08"] = (f08, ["commitment body and fields"], "minimal comprehensive signable commitment; gated")
    schedule_ref = any_present(notice, ["岗位明细表", "岗位表"]) and schedule_ok
    commitment_ref = any_present(notice, ["诚信承诺书", "诚信承诺"]) and commitment_ok and signature and date
    directory_ref = any_present(notice, ["专业指导目录", "专业目录"]) and directory_payload
    pclauses["P09"] = (1.0 if schedule_ref else 0.0, ["notice attachment reference", "two schedule role rows"], "schedule edge")
    pclauses["P10"] = (1.0 if commitment_ref else 0.0, ["notice attachment reference", "commitment fields"], "commitment edge")
    pclauses["P11"] = (1.0 if schedule_ref and commitment_ref and directory_ref else 0.0, ["typed edges: schedule, directory payload, commitment"], "complete nonidentity graph")

    positives = []
    for pid in P_WEIGHTS:
        fraction, locs, reason = pclauses[pid]
        needed = [NOTICE]
        if pid in {"P02", "P09"}: needed.append(SCHEDULE)
        if pid in {"P05", "P06", "P07", "P08", "P11"}: needed = REQUIRED.copy()
        if pid == "P10": needed.append(COMMITMENT)
        state = evidence_state(a, needed, fraction > 0)
        if row_state == "ambiguous" and pid in {"P02", "P05", "P06", "P07", "P08", "P09", "P11"}:
            state = "ambiguous"
        positives.append({"id": pid, "weight": P_WEIGHTS[pid], "fulfilled_fraction": fraction,
                          "earned": round(P_WEIGHTS[pid] * fraction, 6), "extraction_state": state,
                          "locations": locs, "normalized_assertion": reason,
                          "artifact_hashes": {x: a[x].sha256 for x in needed},
                          "copy_gate": "passed" if fraction and (pid not in {"P05", "P06", "P07", "P08"} or gate) else "not_satisfied"})

    occurrences: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    def add(did: str, root: str, unit: str, location: str, evidence: str, amount: float | None = None) -> None:
        occurrences.append({"id": did, "root_key": root, "harm_unit": unit, "location": location,
                            "evidence": evidence, "amount": float(D_SCALES[did]) if amount is None else float(amount)})
    def unresolved_item(did: str, location: str, proposition: str, reason: str) -> None:
        unresolved.append({"item_id": did, "extraction_state": "ambiguous", "location": location,
                           "normalized_assertion": proposition, "reason": reason,
                           "treatment": "semantic candidate only; no mechanical deduction"})

    for person, cls, value in visible_private:
        add("D01", f"privacy/direct/{person}/{cls}", f"{person}/{cls}", "visible public output", value)
    visible_referees = [(person, value) for person, value in REFEREES if n(value) in n(visible)]
    for person, value in visible_referees:
        add("D02", f"privacy/referee/{person}", person, "visible public output", value)
    for fact in narrative_hits:
        if any_present(notice + schedule, [fact]): add("D03", f"source_role/{n(fact)}", fact, "adopted public policy region", fact)
    for did, field, scale in [("D04", "身份证", .06), ("D05", "电话", .04), ("D06", "邮箱", .04)]:
        hit = adopted_clause(commitment, [[field], ["填写", "号码", "联系方式", "电子"]])
        if hit: add(did, {"D04":"overcollection/id", "D05":"overcollection/phone", "D06":"overcollection/email"}[did], field, COMMITMENT, hit, scale)
    for role, row in [("gm", gm), ("officer", officer)]:
        wrong_scope = affirmative_phrase(row, ["法学大类", "工学大类", "仅金融专业", "金融学大类"])
        if wrong_scope: add("D07", f"qualification/prof_scope/{role}", role, SCHEDULE, wrong_scope)
    auto_unlisted = adopted_clause(qualification_rules, [["未列入", "目录外"], ["自动符合", "直接符合", "一律不符合", "自动不符合"]])
    if auto_unlisted and affirmative_phrase(auto_unlisted, ["自动符合", "直接符合", "一律不符合", "自动不符合"]): add("D08", "qualification/unlisted_outcome", "unlisted profession rule", NOTICE, auto_unlisted)
    # Do not mistake a heading such as “年龄和工作经历计算” for a controlling
    # rule. D09 requires a clause that actually states a cutoff.
    exp_clause = adopted_clause(position_rules + procedure, [["工作年限", "工作经历"], ["截止"]])
    if exp_clause and (not date_present(exp_clause, 2026, 9, 15) or not any_present(exp_clause, ["足年足月", "完整月", "完整年和月"])):
        add("D09", "qualification/experience_clock", "controlling experience calculation", NOTICE, exp_clause)
    inclusion = adopted_clause(position_rules + qualification, [["实习", "兼职", "社会实践"], ["计入工作经历", "算作工作经历"]])
    if inclusion and not any_present(inclusion, ["不计入", "不能计算", "排除"]): add("D10", "qualification/study_experience", "study-period inclusion", NOTICE, inclusion)
    if schedule_ok:
        mgmt = n(gm)
        # Only the alternative management-experience block governs OR/AND. A later
        # business-skills list can legitimately require every listed skill.
        management = re.split(r"(?:业务能力|业务技能|专业能力|任职能力|岗位能力|其他条件|其他要求)", mgmt, maxsplit=1)[0]
        if "管理经历" in management and any(x in management for x in ["同时具备", "均须具备", "全部满足"]) and not any(x in management for x in ["任一", "之一", "或满足", "或者"]): add("D11", "gm_paths/and", "GM gate", SCHEDULE, "management alternatives changed to AND")
        # Each path is a lead term plus the conjuncts that must survive with it. The
        # duration is checked as a number of years rather than as one spelling of it.
        paths = [("a", "中层及以上", 5, []),
                 ("b", "核心业务岗位", 8, ["团队管理", "重大项目"])]
        for key, lead, floor, conjuncts in paths:
            if not any_present(gm, [lead]):
                continue
            if not years_stated(gm, floor) or not all(any_present(gm, [x]) for x in conjuncts):
                add("D12", f"gm_paths/weaken/{key}", key, SCHEDULE, "presented path omits internal conjunct")
        if any_present(gm, ["上述金融或类金融机构", "上述金融及类金融机构"]) and any_present(gm, ["保理"]):
            add("D12", "gm_paths/weaken/a", "a", SCHEDULE, "path 1 cross-reference admits factoring from a broader preceding institution list")
    for did, role_text, age_term, expected, root in [("D13", qualification_rules + "\n" + gm, "50周岁", "1976年9月1日", "age/gm"), ("D14", qualification_rules + "\n" + officer, "35周岁", "1991年9月1日", "age/officer")]:
        age_clause = adopted_clause(role_text, [[age_term], ["出生", "含", "以后"]])
        expected_date = (1976, 9, 1) if did == "D13" else (1991, 9, 1)
        if age_clause and not date_present(age_clause, *expected_date): add(did, root, root, NOTICE, age_clause)
        if age_clause and any_present(age_clause, ["不含", "之前出生", "以前出生"]): add(did, root, root, NOTICE, age_clause)
    # Keep each interval bound to the stage clause that names it.  Searching a two-
    # clause window allowed a correct time from one stage to mask a wrong date from
    # the other stage (for example, a review date beside the application time).
    def stage_clause(terms: list[str]) -> str:
        candidates = [c for c in clauses(procedure) if any_present(c, terms)]
        # The process intro may mention a stage without its interval. Prefer the
        # stage-local clause that carries a year/month or a clock value.
        return next((c for c in candidates if any_present(c, ["2026", "9月", "9:00", "16:30", "17:00"])),
                    candidates[0] if candidates else "")
    app_window = stage_clause(["报名时间", "网上报名"])
    if app_window and not (any_present(app_window, ["9月14日", "2026年9月14日", "2026-09-14", "2026-9-14"]) and
                           any_present(app_window, ["22日", "9月22日", "2026年9月22日", "2026-09-22", "2026-9-22"]) and
                           any_present(app_window, ["9:00", "09:00"]) and any_present(app_window, ["16:30"])):
        add("D15", "timeline/application", "application interval", NOTICE, app_window)
    rev_window = stage_clause(["线上资格初审", "网上资格审查", "资格初审时间"])
    if rev_window and not (any_present(rev_window, ["9月15日", "2026年9月15日", "2026-09-15", "2026-9-15"]) and
                           any_present(rev_window, ["23日", "9月23日", "2026年9月23日", "2026-09-23", "2026-9-23"]) and
                           any_present(rev_window, ["9:00", "09:00"]) and any_present(rev_window, ["17:00"])):
        add("D16", "timeline/online_review", "review interval", NOTICE, rev_window)
    later = adopted_clause(procedure, [["后续", "各招聘环节", "有关信息"], ["公布", "通知"]])
    if later and (any_present(later, ["湖南人才网", "长沙人才网", "报名系统", "另行通知"]) and not any_present(later, ["不再另行通知"])): add("D17", "channel/later_updates", "later update rule", NOTICE, later)
    exam_bad = affirmative_phrase(procedure, ["笔试", "书面考试", "初试采用半结构化", "复试采用结构化", "另行组织加试", "加试确定人选", "加试成绩"])
    if exam_bad: add("D18", "selection/exam_design", "selection funnel", NOTICE, exam_bad)
    threshold_errors = [
        ("initial_pass", ["初试合格线70分", "初试基准成绩线70分", "初试合格线80分"]),
        ("final_pass", ["复试合格线70分", "复试基准成绩线70分", "复试合格线80分"]),
        ("initial_advancement", ["按1:3进入复试", "按1:1进入复试"]),
        ("physical_entry", ["按1:2进入体检", "按1:3进入体检"]),
    ]
    for stage, patterns in threshold_errors:
        wrong = affirmative_phrase(procedure, patterns)
        if wrong: add("D19", f"selection/threshold/{stage}", stage, NOTICE, wrong)
    physical = "\n".join(c for c in clauses(procedure) if any_present(c, ["体检", "毒品", "复检"]))
    if affirmative_phrase(physical, ["不进行毛发毒品检测", "毒品阳性仍合格", "可复检两次", "多次复检"]): add("D20", "physical/drug_retest", "drug and retest cluster", NOTICE, "contradictory physical rule")
    for stage in ["体检", "考察"]:
        bad = adopted_clause(procedure, [[stage], ["递补", "替补"], ["两次", "多次", "不按成绩"]])
        if bad: add("D21", f"replacement/{stage}", stage, NOTICE, bad)
    for key, patterns in [("duration", ["公示5个工作日", "公示3个工作日"]), ("anonymous", ["匿名举报有效", "接受匿名举报"]), ("unresolved", ["未查清仍予录用", "未查清可以录用"])]:
        hit = affirmative_phrase(procedure, patterns)
        if hit: add("D22", f"publicity/{key}", key, NOTICE, hit)
    for practice, patterns in [("coaching", ["举办辅导班", "认可培训班"]), ("books", ["指定辅导用书", "推荐备考书"]), ("fee", ["收取报名费", "缴纳报名费"])]:
        hit = affirmative_phrase(procedure, patterns)
        if hit: add("D23", f"integrity/organizer/{practice}", practice, NOTICE, hit)
    blacklist = adopted_clause(procedure, [["考试违纪", "考试舞弊", "弄虚作假"], ["黑名单"], ["年"]])
    if blacklist and not any_present(blacklist, ["5年", "五年"]): add("D24", "integrity/blacklist", "blacklist duration", NOTICE, blacklist)

    section_data = {"S01": (qualification, qstate), "S02": (position_rules, prstate), "S03": (procedure, procstate)}
    for sid, (value, state) in section_data.items():
        if a[NOTICE].state == "identified" and state == "confirmed_missing": add("D25", f"shape/title/{sid}", sid, NOTICE, "required functional section missing")
    def bound_schedule_cell(role_terms: list[str], header_terms: list[str]) -> str:
        cells = a[SCHEDULE].cells
        role_refs = [ref for ref, value in cells.items() if any(n(value) == n(term) for term in role_terms)]
        role_row_number = int(re.search(r"\d+$", role_refs[0]).group()) if len(role_refs) == 1 else -1
        header_refs = [ref for ref, value in cells.items()
                       if any(n(term) in n(value) for term in header_terms)
                       and (row_match := re.search(r"\d+$", ref))
                       and int(row_match.group()) < role_row_number]
        if len(role_refs) != 1 or not header_refs: return ""
        role_row = str(role_row_number)
        header_col = re.search(r"!([A-Z]+)", header_refs[-1]).group(1)
        return cells.get(f"sheet1!{header_col}{role_row}", "")
    gm_duties = bound_schedule_cell(["总经理"], ["岗位职责"])
    gm_requirements = bound_schedule_cell(["总经理"], ["任职要求"])
    officer_duties = bound_schedule_cell(["业务员", "业务专员"], ["岗位职责"])
    officer_requirements = bound_schedule_cell(["业务员", "业务专员"], ["任职要求"])
    values = {"S01": len(n(qualification)), "S02": len(n(position_rules)), "S03": len(n(procedure)),
              "S04": sum(len(n(value)) for value in a[SCHEDULE].cells.values()),
              "S05": len(n(gm_duties)), "S06": len(n(gm_requirements)),
              "S07": len(n(officer_duties)), "S08": len(n(officer_requirements))}
    shape_ledger = []
    for sid, (gold, scope) in SHAPES.items():
        upper_tolerance = UPPER_TOLERANCE[sid]
        candidate = values[sid]; overrun = max(0.0, candidate / max(gold, 1) - (1 + upper_tolerance)); relative = abs(candidate - gold) / max(gold, 1)
        shape_ledger.append({"id": sid, "scope": scope, "metric": "non_whitespace_characters", "golden": gold,
                             "candidate": candidate, "relative_gap": round(relative, 6), "overrun": round(overrun, 6),
                             "lower_boundary": LOWER_RATIO.get(sid, .25) * gold,
                             "upper_boundary": (1 + upper_tolerance) * gold})
        if overrun > 1e-12: add("D26", f"shape/overrun/{sid}", sid, scope, f"C={candidate}, G={gold}", .03 * min(3.0, overrun / .25))
        if sid in LOWER_RATIO and 0 < candidate < LOWER_RATIO[sid] * gold:
            add("D27", f"shape/underload/{sid}", sid, scope,
                f"C={candidate} below {LOWER_RATIO[sid]:.0%} of G={gold}")
    if row_state == "ambiguous" or (a[SCHEDULE].state == "identified" and (not gm or not officer)):
        add("D28", "schedule/structure", "workbook usability", SCHEDULE, "role records ambiguous or missing")
    if a[SCHEDULE].state == "parse_failure": unresolved_item("D28", SCHEDULE, "workbook unavailable", "local parser failure is not business guilt")
    if a[SCHEDULE].state != "parse_failure" and a[NOTICE].state != "parse_failure" and not schedule_ref: add("D29", "closure/schedule", "schedule edge", NOTICE, "usable schedule edge absent or wrong")
    if a[COMMITMENT].state != "parse_failure" and a[NOTICE].state != "parse_failure" and not commitment_ref: add("D30", "closure/commitment", "commitment edge", NOTICE, "usable commitment edge absent or wrong")
    if a[DIRECTORY].state != "parse_failure" and a[NOTICE].state != "parse_failure" and not directory_ref: add("D31", "closure/directory_payload", "directory edge", NOTICE, "nonidentity directory payload edge absent or wrong")
    # These propositions were present in the old Golden or in the old H6 role row,
    # but are not authorized by the current instruction.  They are material
    # eligibility/process changes, so a candidate adopting one gets an independent
    # semantic damage item instead of being silently protected by a Golden waiver.
    unsupported_patterns = ["仅限男性报考", "仅限本地户籍", "必须持有注册会计师证", "体检费用自理", "增加笔试", "缴纳保证金",
                            "法律法规及国资监管规定不得担任国有企业管理人员",
                            "因无法联系或者未按要求参加招聘环节造成的后果",
                            "具有2年以上融资担保、银行信贷、金融或类金融业务等相关工作经历",
                            "工作经历应为全职", "工作经历必须为全职", "岗位所要求的工作经历应为全职",
                            "无故不参加现场资格审查或考试者将被列为失信黑名单",
                            "无故不参加现场资格审查或考试者列为失信黑名单",
                            "入围面试所有考生均纳入集团储备人才库",
                            "有良好的沟通能力", "具备风险控制意识",
                            "有银行信贷、担保、小贷等公司工作经验优先",
                            "2023年公开招聘外包人员", "xxxx人力资源服务有限公司2023年公开招聘外包人员"]
    for phrase in unsupported_patterns:
        hit = affirmative_phrase(notice + "\n" + schedule + "\n" + commitment, [phrase])
        if hit: add("D32", f"unsupported/{n(phrase)}", phrase, "adopted public output", hit)
    # The source limits this disqualification to the General Manager role. A
    # notice-wide clause silently broadens the affected applicant cohort.
    judgment_bar = adopted_clause(qualification, [["失信被执行人"]])
    if judgment_bar and not any_present(judgment_bar, ["总经理岗位", "仅限总经理", "仅适用于总经理"]):
        add("D32", "unsupported/gm_only_disqualification_broadened",
            "General Manager-only disqualification applied generally", NOTICE, judgment_bar)
    # A source-role-like proposition not in the registered fingerprints is not
    # deterministically resolvable.  Surface it without fabricating a charge.
    for c in clauses(notice + "\n" + schedule):
        if any_present(c, ["优先", "必须", "仅限"]) and len(n(c)) > 180 and not any_present(c, unsupported_patterns + EXCLUDED_PROPOSITION_MARKERS):
            unresolved_item("D32", "public policy clause", n(c)[:160], "material support requires independent semantic source comparison")

    # Local parser failures stay local and never create a business deduction.
    for name, artifact in a.items():
        if artifact.state == "parse_failure": unresolved_item("package", name, "", artifact.error or "parse failure")

    dedup: dict[tuple[str, str], dict[str, Any]] = {}
    for item in occurrences:
        key = (item["root_key"], item["harm_unit"])
        if key not in dedup or item["amount"] > dedup[key]["amount"]: dedup[key] = item
    applied = sorted(dedup.values(), key=lambda x: (x["id"], x["root_key"], x["harm_unit"]))
    dledger = []
    for did in D_SCALES:
        hits = [x for x in applied if x["id"] == did]
        parse_deps = {"D01": REQUIRED, "D02": REQUIRED, "D03": [NOTICE, SCHEDULE], "D04": [COMMITMENT], "D05": [COMMITMENT], "D06": [COMMITMENT],
                      "D07": [NOTICE, SCHEDULE], "D08": [NOTICE], "D09": [NOTICE], "D10": [NOTICE], "D11": [SCHEDULE], "D12": [SCHEDULE],
                      "D13": [NOTICE, SCHEDULE], "D14": [NOTICE, SCHEDULE], "D15": [NOTICE], "D16": [NOTICE], "D17": [NOTICE], "D18": [NOTICE],
                      "D19": [NOTICE], "D20": [NOTICE], "D21": [NOTICE], "D22": [NOTICE], "D23": [NOTICE], "D24": [NOTICE], "D25": [NOTICE],
                      "D26": [NOTICE, SCHEDULE], "D27": [NOTICE], "D28": [SCHEDULE], "D29": [NOTICE, SCHEDULE], "D30": [NOTICE, COMMITMENT],
                      "D31": [NOTICE, DIRECTORY], "D32": [NOTICE, SCHEDULE, COMMITMENT]}[did]
        bad = [a[x].state for x in parse_deps if a[x].state != "identified"]
        state = "parse_failure" if "parse_failure" in bad else ("confirmed_missing" if "confirmed_missing" in bad else ("identified" if hits else "confirmed_missing"))
        dledger.append({"id": did, "scale": D_SCALES[did], "extraction_state": state,
                        "triggered": bool(hits), "occurrence_count": len(hits),
                        "deducted": round(sum(x["amount"] for x in hits), 6), "occurrences": hits,
                        "root_keys": [x["root_key"] for x in hits]})
    positive = round(sum(x["earned"] for x in positives), 6); deducted = round(sum(x["amount"] for x in applied), 6)
    raw = round(positive - deducted, 6); final = round(max(0.0, raw), 6)
    return {"schema": "recruitment-rubric-v3-mechanical-ledger", "rubric_version": VERSION,
            "scoring_version": VERSION, "view": "mechanical", "formula": "max(0, positive_earned - deduplicated_deductions)",
            "input_hashes": input_hashes,
            "reward": final, "final": final, "raw": raw, "raw_score": raw,
            "positive_earned": positive, "deduplicated_deductions": deducted,
            "positive_items": positives, "deduction_items": dledger, "deductions": applied,
            "shape_units": shape_ledger, "artifact_ledger": [vars(a[x]) | {"text": None, "hidden": None, "cells": None} for x in REQUIRED],
            "unresolved_semantic_candidates": unresolved, "unresolved_checks": unresolved,
            "truth_exclusions": [{**item, "treatment": "symmetric exclusion applied before scoring"} for item in TRUTH_EXCLUSIONS],
            "release_status": "evidence_insufficient" if unresolved or any(x.state != "identified" for x in a.values()) else "scored",
            "invariants": {"positive_item_count": len(positives), "deduction_item_count": len(dledger),
                           "positive_weight_total": round(sum(P_WEIGHTS.values()), 6), "deduction_cap": None,
                           "ordinary_omission": "positive loss only except frozen structural D25/D27/D28/D29/D30/D31"}}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("workspace", nargs="?", default="/workspace")
    parser.add_argument("--output"); parser.add_argument("--output-dir"); args = parser.parse_args()
    result = evaluate(Path(args.workspace).resolve())
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output: Path(args.output).write_text(payload + "\n", encoding="utf-8")
    if args.output_dir:
        out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
        (out / "reward_detail.json").write_text(payload + "\n", encoding="utf-8")
        (out / "verify_result.json").write_text(payload + "\n", encoding="utf-8")
        # The hand-off contract asks whether the package could be taken up downstream,
        # which four files that parse but say the wrong thing cannot. Testing only the
        # containers made the lens constant: every submission that produced the four
        # artefacts earned it, including ones whose content earned almost nothing, so the
        # second view reported the same value for every run and distinguished nothing. A
        # floor on the positive side is required as well, set at half so the lens stays
        # materially wider than the strict view.
        handed_over = (result["release_status"] == "scored"
                       and float(result.get("positive_earned", 0.0)) >= 0.5)
        compact = {"reward": result["final"], "reward_strict": result["final"],
                   "reward_lenient": 1.0 if handed_over else 0.0}
        (out / "reward.json").write_text(json.dumps(compact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (out / "reward.txt").write_text(f'{result["final"]:.6f}\n', encoding="utf-8")
        (out / "reward_strict.txt").write_text(f'{result["final"]:.6f}\n', encoding="utf-8")
        (out / "reward_lenient.txt").write_text(f'{compact["reward_lenient"]:.6f}\n', encoding="utf-8")
    print(payload); return 0


if __name__ == "__main__": sys.exit(main())
