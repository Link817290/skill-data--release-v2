#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mechanical scorer for the parking barrier quotation task.

Deliverable under test: output/quotation.xlsx, a customer quotation for a parking
entrance barrier and plate recognition job.

The executable checks are the implementation of the public ``RUBRIC.md``.

    positive_earned = sum(weight_i * fraction_i)   B1 B2 A1 A2 A3 F1 F2, sum 1.0
    deductions      = sum over root cause keys      D03 D04 D06 mechanical
    raw             = positive_earned - deductions
    final           = max(0, raw)

B1 scope grouping and B2 physical scope, actual-settlement meaning and site
estimate basis use required evidence-bound semantic adjudication. Formula
coverage, positive quantities and all other mechanical checks remain local.
A required judge failure aborts with exit 2 and publishes no score. D01 D02
D05 and F2 description content retain the existing review-only proxies; this
scorer never subtracts a semantic deduction.

Every predicate returns one of identified / confirmed_missing / ambiguous /
parse_failure.  ambiguous and parse_failure earn nothing and charge nothing.

Formulas are evaluated here.  Workbooks written by openpyxl carry no cached
values, and an absent cached value is never read as missing or as a constant.

Usage:  python3 mechanical_score.py <quotation.xlsx> [--json out.json]
"""

from __future__ import annotations
from pathlib import Path

import argparse
import json
import math
import os
import re
import sys
import traceback

# ---------------------------------------------------------------------------
# 0.  Rubric constants
# ---------------------------------------------------------------------------

RUBRIC_ID = "RUBRIC.md"

WEIGHTS = {"B1": 0.45, "B2": 0.40, "A1": 0.03, "A2": 0.04, "A3": 0.03, "F1": 0.01, "F2": 0.04}
CLASS_OF = {"B1": "B", "B2": "B", "A1": "A", "A2": "A", "A3": "A", "F1": "F", "F2": "F"}
DEDUCTION_AMOUNT = {"D01": 0.05, "D02": 0.05, "D03": 0.04, "D04": 0.06, "D05": 0.04, "D06": 0.04}
MECHANICAL_DEDUCTIONS = ("D03", "D04", "D06")

STATE_IDENTIFIED = "identified"
STATE_MISSING = "confirmed_missing"
STATE_AMBIGUOUS = "ambiguous"
STATE_PARSE = "parse_failure"

MONEY_TOL = 0.005
ROUNDING_TOL = 1.0

# Goods the scoping sheet records, as permitted constants from the materials.
# A1 price families (six) and the A2 scope units (five).
A1_PRICES = {"barrier": 2400.0, "plate": 2000.0, "radar": 500.0,
             "island": 500.0, "controller": 2500.0, "sign": 600.0}
A2_UNITS = ("bracket", "plate_qty", "barrier_qty", "radar_qty", "software",
            "sign_qty", "island_qty", "monitoring_qty")
PLATE_QTY = 4.0
BARRIER_QTY = 3.0
RADAR_QTY = 3.0
SIGN_QTY = 2.0
ISLAND_QTY = 3.0
MONITORING_QTY = 1.0
BRACKET_PRICE = 500.0

# Handed facts (guardrails, D06 only).
QUOTE_DATE = (2026, 7, 21)
VAT_PERCENT = 1.0
CHARGE_RATE = 0.10

# Site-work component vocabularies. Quantities require stated site measurement/settlement, not hidden bands.
DATA_WORDS = ["网线", "超五类", "六类", "双绞线", "数据线", "通讯线", "通信线", "cat5", "cat6", "utp", "network", "data cable"]
POWER_WORDS = ["电源", "供电", "power"]
SIGNAL_WORDS = ["信号线", "控制线", "signal", "control cable"]
TRENCH_WORDS = ["开沟", "开小沟", "沟槽", "开槽", "切槽", "切割", "破路", "trench", "slot cut", "saw cut"]
# --- open vocabularies -------------------------------------------------------
# Families are open sets in Chinese and English.  A row is scored against every
# family and assigned to the strongest match, ties kept.
FAMILY_VOCAB = {
    "barrier": ["道闸", "闸机", "挡车器", "栏杆机", "起落杆", "车闸", "闸杆",
                "barrier", "boom gate", "boomgate", "boom barrier"],
    "plate": ["车牌识别", "牌识", "车牌", "号牌识别", "车辆识别", "识别一体机", "识别相机",
              "plate recognition", "license plate", "licence plate", "anpr", "lpr"],
    "radar": ["雷达", "防砸", "车检器", "车辆检测器", "地感", "线圈",
              "radar", "loop detector", "vehicle detector", "anti-smash", "anti smash"],
    "island": ["安全岛", "导向岛", "隔离岛", "岛体", "safety island", "traffic island", "kerb island"],
    "controller": ["电脑", "主机", "工控机", "管理机", "服务器", "加密", "加密狗", "软件", "管理系统",
                   "computer", "pc", "server", "software", "dongle", "licence", "license"],
    "installation": ["安装费", "安装调试费", "施工费", "人工费", "安装",
                     "installation", "install", "labour", "labor"],
    "cable": ["线材", "网线", "电源线", "信号线", "电缆", "线缆", "护套线", "双绞线", "rvv", "cat5", "cat6", "超五类",
              "cable", "cabling", "wire", "wiring"],
    "conduit": ["管线", "穿线管", "线管", "pvc管", "pe管", "软管", "波纹管", "镀锌管", "桥架", "管材",
                "conduit", "duct", "pipe", "trunking", "hose"],
    "civil": ["开沟", "开小沟", "小沟", "沟槽", "开挖", "开槽", "切槽", "破路", "回填", "土建", "混凝土", "挖沟", "路面",
              "trench", "trenching", "slot cut", "saw cut", "backfill", "civil", "concrete", "excavat"],
    "monitoring": ["监控", "摄像机", "摄像头", "枪机", "球机", "录像机", "硬盘录像", "云台",
                   "camera", "cctv", "surveillance", "nvr", "dvr"],
    "bracket": ["支杆", "支架", "立杆", "立柱", "抱杆", "安装支架", "摄像机支架", "摄像机安装支架", "监控支架", "安装立杆", "监控立杆", "监控支杆",
                "bracket", "pole", "mounting pole", "camera pole", "mounting post", "mount"],
    "sign": ["标示牌", "标识牌", "公示牌", "标识标牌", "标牌", "指示牌", "告示牌",
             "sign", "signage", "signboard", "notice board", "price board"],
}

TRADE_OF = {
    "barrier": "lane", "plate": "lane", "radar": "lane",
    "controller": "control", "monitoring": "control", "bracket": "control",
    "cable": "works", "conduit": "works", "civil": "works", "island": "works",
    "sign": None, "installation": None,
}

HEADER_HINTS = {
    "qty": ["数量", "台数", "套数", "个数", "工程量", "qty", "quantity", "count"],
    "price": ["单价", "单位价格", "价格", "unitprice", "unit price", "price", "rate"],
    "amount": ["金额", "合价", "总价", "价款", "amount", "line total", "extended"],
    "name": ["名称", "品名", "项目", "设备", "系统配置", "内容", "item", "name", "product"],
    "desc": ["规格", "说明", "配置", "描述", "参数", "备注", "spec", "description", "configuration", "remark", "note"],
    "unit": ["单位", "计量单位", "unit", "uom"],
}

SUBTOTAL_WORDS = ["小计", "分项合计", "分部合计", "subtotal", "sub total", "section total", "block total"]
TOTAL_WORDS = ["合计", "总计", "共计", "总价", "报价总计", "工程造价", "total", "grand total"]
CHARGE_WORDS = ["运输", "调试", "维护", "维保", "运维", "transport", "commissioning", "maintenance"]
TAX_WORDS = ["含税", "增值税", "普通发票", "普票", "vat", "tax", "invoice"]
TITLE_WORDS = ["报价单", "报价表", "报价书", "报价", "配置清单及价格", "价格清单", "报价清单", "quotation", "quote", "price list"]
SYSTEM_WORDS_A = ["道闸", "barrier"]
SYSTEM_WORDS_B = ["车牌", "识别", "plate", "recognition", "anpr", "lpr"]

LENGTH_UNITS = ["米", "延米", "m", "metre", "meter", "metres", "meters", "lm"]
LUMP_UNITS = ["项", "批", "宗", "包干", "lot", "lump", "ls", "job"]
SETTLE_WORDS = ["按实", "据实", "实际", "实测", "结算", "暂定", "暂估", "预估", "估算", "以现场", "多退少补",
                "provisional", "actual", "as built", "as-built", "remeasur", "settled", "estimate"]
SITE_TIE_WORDS = ["车道", "岗亭", "大门", "侧门", "出入口", "闸口", "值班", "管理处", "至", "到",
                  "lane", "gate", "booth", "entrance", "exit", "run", "between"]
PLACEMENT_ONLY_RE = re.compile(r"^[\s，,、；;:：]*((大门|侧门|入口|出口|进|出|每条车道|每台道闸|各)[^一-鿿]*[一-鿿]{0,3}\d*[台个套只根处]?[\s，,、；;:：]*)+$")

# ---------------------------------------------------------------------------
# 1.  Text helpers
# ---------------------------------------------------------------------------

def _fullwidth_to_half(s: str) -> str:
    out = []
    for ch in s:
        o = ord(ch)
        if o == 0x3000:
            out.append(" ")
        elif 0xFF01 <= o <= 0xFF5E:
            out.append(chr(o - 0xFEE0))
        else:
            out.append(ch)
    return "".join(out)


def norm(value) -> str:
    """Normalised text for matching: half width, lower case, no whitespace."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float) and value == int(value):
        value = int(value)
    s = _fullwidth_to_half(str(value)).lower()
    return re.sub(r"\s+", "", s)


def loose(value) -> str:
    """Normalised text that keeps single spaces (for English phrase matching)."""
    if value is None:
        return ""
    s = _fullwidth_to_half(str(value)).lower()
    return re.sub(r"\s+", " ", s).strip()


def is_cjk(ch: str) -> bool:
    return "一" <= ch <= "鿿"


def token_weight(token: str) -> float:
    """CJK characters carry more discriminating power per character than ascii."""
    return sum(2.0 if is_cjk(c) else 0.6 for c in token)


def token_hit(token: str, packed: str, spaced: str) -> bool:
    if any(is_cjk(c) for c in token):
        return token in packed
    tok = token.strip()
    if " " in tok:
        return tok in spaced
    if len(tok) <= 4:
        return re.search(r"(?<![a-z0-9])" + re.escape(tok) + r"(?![a-z])", spaced) is not None
    return tok in packed or tok in spaced


def any_word(text_packed: str, text_spaced: str, words) -> bool:
    return any(token_hit(w, text_packed, text_spaced) for w in words)


def numbers_in(text: str):
    """All numeric literals in a string, thousands separators tolerated."""
    out = []
    for m in re.finditer(r"\d[\d,]*(?:\.\d+)?", _fullwidth_to_half(str(text))):
        try:
            out.append(float(m.group(0).replace(",", "")))
        except ValueError:
            pass
    return out


def close(a, b, tol=MONEY_TOL) -> bool:
    return a is not None and b is not None and abs(a - b) <= max(tol, abs(b) * 1e-9)


# ---------------------------------------------------------------------------
# 2.  EXTRACT - workbook model, formula evaluation, column roles, families
# ---------------------------------------------------------------------------

REF_RE = re.compile(
    r"(?:(?P<sheet>'[^']+'|[A-Za-z0-9_一-鿿]+)!)?"
    r"(?P<a>\$?[A-Za-z]{1,3}\$?[0-9]{1,7})"
    r"(?::(?P<b>\$?[A-Za-z]{1,3}\$?[0-9]{1,7}))?"
)

TOKEN_RE = re.compile(
    r"(?P<ws>\s+)"
    r"|(?P<str>\"(?:[^\"]|\"\")*\")"
    r"|(?P<func>[A-Za-z_][A-Za-z0-9_.]*\s*\()"
    r"|(?P<ref>(?:(?:'[^']+'|[A-Za-z0-9_一-鿿]+)!)?\$?[A-Za-z]{1,3}\$?[0-9]{1,7}"
    r"(?::\$?[A-Za-z]{1,3}\$?[0-9]{1,7})?)"
    r"|(?P<name>[A-Za-z_][A-Za-z0-9_.]*)"
    r"|(?P<num>[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)"
    r"|(?P<op>[-+*/^%&(),<>=:!])"
)


def col_letters_to_index(letters: str) -> int:
    n = 0
    for ch in letters.upper():
        n = n * 26 + (ord(ch) - 64)
    return n


def index_to_col_letters(idx: int) -> str:
    s = ""
    while idx > 0:
        idx, rem = divmod(idx - 1, 26)
        s = chr(65 + rem) + s
    return s


def split_ref(ref: str, current_sheet: str):
    """'Sheet1'!$B$4 -> (sheet, 'B4').  Returns (sheet, coord) or None."""
    m = REF_RE.fullmatch(ref.strip())
    if not m:
        return None
    sheet = m.group("sheet") or current_sheet
    sheet = sheet.strip("'") if sheet else current_sheet
    a = m.group("a").replace("$", "").upper()
    b = m.group("b")
    if b:
        return (sheet, a, b.replace("$", "").upper())
    return (sheet, a, None)


def coord_parts(coord: str):
    m = re.fullmatch(r"([A-Za-z]{1,3})([0-9]{1,7})", coord)
    if not m:
        return None
    return col_letters_to_index(m.group(1)), int(m.group(2))


def expand_range(sheet, a, b, cap=4000):
    ca, ra = coord_parts(a)
    cb, rb = coord_parts(b)
    cells = []
    for r in range(min(ra, rb), max(ra, rb) + 1):
        for c in range(min(ca, cb), max(ca, cb) + 1):
            cells.append((sheet, index_to_col_letters(c) + str(r)))
            if len(cells) >= cap:
                return cells
    return cells


class WorkbookModel:
    """Both readings of the workbook, plus merged-cell aware access."""

    def __init__(self, path):
        import openpyxl
        self.path = path
        self.wb_f = openpyxl.load_workbook(path, data_only=False)
        try:
            self.wb_v = openpyxl.load_workbook(path, data_only=True)
        except Exception:
            self.wb_v = None
        self.sheetnames = list(self.wb_f.sheetnames)
        self.merged = {}     # sheet -> {coord: anchor_coord}
        self.dims = {}
        for name in self.sheetnames:
            ws = self.wb_f[name]
            mp = {}
            for rng in list(ws.merged_cells.ranges):
                anchor = index_to_col_letters(rng.min_col) + str(rng.min_row)
                for r in range(rng.min_row, rng.max_row + 1):
                    for c in range(rng.min_col, rng.max_col + 1):
                        mp[index_to_col_letters(c) + str(r)] = anchor
            self.merged[name] = mp
            self.dims[name] = (min(ws.max_row or 1, 500), min(ws.max_column or 1, 80))
        self._eval_cache = {}
        self._eval_stack = set()
        self.names = {}
        for defined in self.wb_f.defined_names.values():
            if defined.type != "RANGE":
                continue
            destinations = list(defined.destinations)
            if len(destinations) == 1:
                named_sheet, named_coord = destinations[0]
                self.names[defined.name.upper()] = (
                    named_sheet.strip("'"), named_coord.replace("$", "").upper())

    # -- raw access ---------------------------------------------------------
    def formula(self, sheet, coord):
        if sheet not in self.wb_f.sheetnames:
            return None
        try:
            return self.wb_f[sheet][coord].value
        except Exception:
            return None

    def cached(self, sheet, coord):
        if self.wb_v is None or sheet not in self.wb_v.sheetnames:
            return None
        try:
            return self.wb_v[sheet][coord].value
        except Exception:
            return None

    def anchor(self, sheet, coord):
        return self.merged.get(sheet, {}).get(coord, coord)

    def display(self, sheet, coord, follow_merge=True):
        """What a reader sees in a cell: cached value, else literal, else ''."""
        c = self.anchor(sheet, coord) if follow_merge else coord
        v = self.cached(sheet, c)
        if v is None:
            f = self.formula(sheet, c)
            v = f if not (isinstance(f, str) and f.startswith("=")) else None
        return v

    def text(self, sheet, coord, follow_merge=True):
        v = self.display(sheet, coord, follow_merge)
        if v is None:
            return ""
        if hasattr(v, "strftime"):
            return v.strftime("%Y-%m-%d %H:%M:%S")
        return str(v)

    # -- numeric resolution -------------------------------------------------
    def number(self, sheet, coord):
        """Numeric value of a cell: cached value, literal, or evaluated formula.

        Workbooks written by openpyxl carry no cached values, so formulas are
        evaluated here rather than trusted from the file.
        """
        key = (sheet, coord)
        if key in self._eval_cache:
            return self._eval_cache[key]
        if key in self._eval_stack:      # circular reference
            return None
        v = self.cached(sheet, coord)
        if isinstance(v, bool):
            v = None
        if isinstance(v, (int, float)):
            self._eval_cache[key] = float(v)
            return float(v)
        f = self.formula(sheet, coord)
        if isinstance(f, bool):
            f = None
        if isinstance(f, (int, float)):
            self._eval_cache[key] = float(f)
            return float(f)
        out = None
        if isinstance(f, str):
            s = f.strip()
            if s.startswith("="):
                self._eval_stack.add(key)
                try:
                    out = self.eval_formula(sheet, s[1:])
                except Exception:
                    out = None
                finally:
                    self._eval_stack.discard(key)
            else:
                s2 = _fullwidth_to_half(s).replace(",", "").replace("¥", "").replace("$", "").strip()
                s2 = re.sub(r"^(元|rmb|cny)|(元|rmb|cny)$", "", s2)
                try:
                    out = float(s2)
                except ValueError:
                    out = None
        self._eval_cache[key] = out
        return out

    # -- formula evaluation -------------------------------------------------
    def eval_formula(self, sheet, body):
        toks = self._tokenize(body)
        if toks is None:
            return None
        pos = [0]
        val = self._expr(toks, pos, sheet)
        if pos[0] != len(toks):
            return None
        return self._scalar(val)

    @staticmethod
    def _tokenize(body):
        toks, i = [], 0
        while i < len(body):
            m = TOKEN_RE.match(body, i)
            if not m or m.end() == i:
                return None
            i = m.end()
            if m.lastgroup == "ws":
                continue
            toks.append((m.lastgroup, m.group(0)))
        return toks

    @staticmethod
    def _scalar(v):
        if isinstance(v, list):
            return None
        return v

    def _expr(self, toks, pos, sheet):
        left = self._term(toks, pos, sheet)
        while pos[0] < len(toks) and toks[pos[0]] == ("op", "+") or \
              (pos[0] < len(toks) and toks[pos[0]] == ("op", "-")):
            op = toks[pos[0]][1]
            pos[0] += 1
            right = self._term(toks, pos, sheet)
            l, r = self._scalar(left), self._scalar(right)
            if l is None or r is None:
                left = None
            else:
                left = l + r if op == "+" else l - r
        return left

    def _term(self, toks, pos, sheet):
        left = self._power(toks, pos, sheet)
        while pos[0] < len(toks) and toks[pos[0]][0] == "op" and toks[pos[0]][1] in "*/":
            op = toks[pos[0]][1]
            pos[0] += 1
            right = self._power(toks, pos, sheet)
            l, r = self._scalar(left), self._scalar(right)
            if l is None or r is None or (op == "/" and r == 0):
                left = None
            else:
                left = l * r if op == "*" else l / r
        return left

    def _power(self, toks, pos, sheet):
        left = self._unary(toks, pos, sheet)
        while pos[0] < len(toks) and toks[pos[0]] == ("op", "^"):
            pos[0] += 1
            right = self._unary(toks, pos, sheet)
            l, r = self._scalar(left), self._scalar(right)
            left = None if l is None or r is None else l ** r
        return left

    def _unary(self, toks, pos, sheet):
        sign = 1.0
        while pos[0] < len(toks) and toks[pos[0]][0] == "op" and toks[pos[0]][1] in "+-":
            if toks[pos[0]][1] == "-":
                sign = -sign
            pos[0] += 1
        val = self._primary(toks, pos, sheet)
        while pos[0] < len(toks) and toks[pos[0]] == ("op", "%"):
            pos[0] += 1
            v = self._scalar(val)
            val = None if v is None else v / 100.0
        v = self._scalar(val)
        if isinstance(val, list):
            return val
        return None if v is None else sign * v

    def _primary(self, toks, pos, sheet):
        if pos[0] >= len(toks):
            return None
        kind, tok = toks[pos[0]]
        if kind == "num":
            pos[0] += 1
            return float(tok)
        if kind == "str":
            pos[0] += 1
            return None
        if kind == "ref":
            pos[0] += 1
            parsed = split_ref(tok, sheet)
            if not parsed:
                return None
            sh, a, b = parsed
            if b is None:
                return self.number(sh, a)
            return [self.number(s2, c2) for s2, c2 in expand_range(sh, a, b)]
        if kind == "name":
            pos[0] += 1
            named = self.names.get(tok.upper())
            if not named:
                return None
            sh, named_ref = named
            parsed = split_ref(named_ref, sh)
            if not parsed:
                return None
            sh, a, b = parsed
            if b is None:
                return self.number(sh, a)
            return [self.number(s2, c2) for s2, c2 in expand_range(sh, a, b)]
        if kind == "func":
            name = tok[:-1].strip().lower().lstrip("_")
            pos[0] += 1
            args = []
            if pos[0] < len(toks) and toks[pos[0]] == ("op", ")"):
                pos[0] += 1
            else:
                while True:
                    args.append(self._expr(toks, pos, sheet))
                    if pos[0] < len(toks) and toks[pos[0]] == ("op", ","):
                        pos[0] += 1
                        continue
                    if pos[0] < len(toks) and toks[pos[0]] == ("op", ")"):
                        pos[0] += 1
                    break
            return self._call(name, args)
        if kind == "op" and tok == "(":
            pos[0] += 1
            v = self._expr(toks, pos, sheet)
            if pos[0] < len(toks) and toks[pos[0]] == ("op", ")"):
                pos[0] += 1
            return v
        pos[0] += 1
        return None

    @staticmethod
    def _flat(args):
        out = []
        for a in args:
            if isinstance(a, list):
                out.extend(x for x in a if isinstance(x, (int, float)))
            elif isinstance(a, (int, float)):
                out.append(a)
        return out

    def _call(self, name, args):
        flat = self._flat(args)
        if name in ("sum", "sumproduct"):
            return float(sum(flat)) if flat else 0.0
        if name == "product":
            if not flat:
                return None
            p = 1.0
            for x in flat:
                p *= x
            return p
        if name == "subtotal":
            body = self._flat(args[1:])
            return float(sum(body)) if body else 0.0
        if name == "round":
            if len(args) >= 1 and isinstance(self._scalar(args[0]), (int, float)):
                nd = int(self._scalar(args[1])) if len(args) > 1 and isinstance(self._scalar(args[1]), (int, float)) else 0
                return round(self._scalar(args[0]), nd)
            return None
        if name in ("abs",) and flat:
            return abs(flat[0])
        if name in ("min",) and flat:
            return min(flat)
        if name in ("max",) and flat:
            return max(flat)
        if name in ("average", "mean") and flat:
            return sum(flat) / len(flat)
        return None


def formula_refs(formula, current_sheet, model=None):
    """Cells a formula reads.  Returns (singles, ranges) as (sheet, coord) sets."""
    singles, ranges = set(), []
    if not isinstance(formula, str) or not formula.startswith("="):
        return singles, ranges
    body = formula[1:]
    for kind, tok in (WorkbookModel._tokenize(body) or []):
        if kind == "name" and model is not None:
            named = model.names.get(tok.upper())
            if named:
                sh, named_ref = named
                parsed = split_ref(named_ref, sh)
                if parsed:
                    sh, a, b = parsed
                    if b is None:
                        singles.add((sh, a))
                    else:
                        ranges.append((sh, a, b))
            continue
        if kind != "ref":
            continue
        parsed = split_ref(tok, current_sheet)
        if not parsed:
            continue
        sh, a, b = parsed
        if b is None:
            singles.add((sh, a))
        else:
            ranges.append((sh, a, b))
    return singles, ranges


def formula_reads(formula, current_sheet, target):
    """True when the formula references `target` = (sheet, coord), directly or
    inside a referenced range."""
    singles, ranges = formula_refs(formula, current_sheet)
    if target in singles:
        return True
    for sh, a, b in ranges:
        if sh != target[0]:
            continue
        if target in set(expand_range(sh, a, b)):
            return True
    return False


def formula_multiplies_refs(formula, current_sheet, qty_cell, price_cell):
    """Require a real quantity-rate relationship, not mere references."""
    if not isinstance(formula, str) or not formula.startswith("="):
        return False
    compact = formula.upper().replace(" ", "")
    if "PRODUCT(" not in compact and "*" not in compact:
        return False
    return formula_reads(formula, current_sheet, (current_sheet, qty_cell)) and \
        formula_reads(formula, current_sheet, (current_sheet, price_cell))


def formula_has_ref(formula, current_sheet):
    s, r = formula_refs(formula, current_sheet)
    return bool(s or r)


# --- family matching ---------------------------------------------------------

def family_scores(text):
    packed, spaced = norm(text), loose(text)
    if not packed:
        return {}
    scores = {}
    for fam, vocab in FAMILY_VOCAB.items():
        best, hit = 0.0, None
        for tok in vocab:
            if token_hit(tok, packed, spaced):
                w = token_weight(tok)
                if w > best:
                    best, hit = w, tok
        if best > 0:
            scores[fam] = (best, hit)
    return scores


def families_of(text):
    """Families a row name belongs to: the strongest match, ties kept."""
    scores = family_scores(text)
    if not scores:
        return [], None
    top = max(v[0] for v in scores.values())
    fams = sorted([f for f, v in scores.items() if v[0] >= top - 1e-9])
    evidence = {f: scores[f][1] for f in fams}
    return fams, evidence

# ---------------------------------------------------------------------------
# 2b.  Table views (reused from the previous scorer)
# ---------------------------------------------------------------------------

class TableView:
    """A rectangular reading of a sheet.  orient='row' means one record per row;
    orient='col' means the table is transposed (one record per column)."""

    def __init__(self, model, sheet, orient):
        self.model = model
        self.sheet = sheet
        self.orient = orient
        nrows, ncols = model.dims[sheet]
        if orient == "row":
            self.n_rec, self.n_field = nrows, ncols
        else:
            self.n_rec, self.n_field = ncols, nrows

    def coord(self, rec, field):
        if self.orient == "row":
            return index_to_col_letters(field + 1) + str(rec + 1)
        return index_to_col_letters(rec + 1) + str(field + 1)

    def number(self, rec, field):
        return self.model.number(self.sheet, self.coord(rec, field))

    def text(self, rec, field):
        return self.model.text(self.sheet, self.coord(rec, field))


def detect_roles(view):
    """Find qty / price / amount fields by the relation amount ~= qty*price.

    Header synonyms are consulted only to break ties between candidate triples
    that the numeric relation supports equally well.
    """
    n_rec, n_field = view.n_rec, view.n_field
    nums = {}
    for r in range(n_rec):
        for f in range(n_field):
            v = view.number(r, f)
            if v is not None:
                nums[(r, f)] = v
    if not nums:
        return None
    dense = [f for f in range(n_field)
             if sum(1 for r in range(n_rec) if (r, f) in nums) >= 2]
    if len(dense) < 2:
        return None
    header_score = {}
    for f in range(n_field):
        blob = " ".join(view.text(r, f) for r in range(min(n_rec, 12)))
        p, s = norm(blob), loose(blob)
        header_score[f] = {role: any_word(p, s, words) for role, words in HEADER_HINTS.items()}

    cands = []
    for fq in dense:
        for fp in dense:
            if fp == fq:
                continue
            for fa in dense:
                if fa in (fq, fp):
                    continue
                hits, rows = 0, []
                for r in range(n_rec):
                    q, p, a = nums.get((r, fq)), nums.get((r, fp)), nums.get((r, fa))
                    if q is None or p is None or a is None:
                        continue
                    if q <= 0 or p <= 0:
                        continue
                    if abs(a - q * p) <= max(0.01, abs(a) * 5e-3):
                        hits += 1
                        rows.append(r)
                if hits >= 2:
                    tie = (2.0 * header_score[fq]["qty"] + 2.0 * header_score[fp]["price"]
                           + 2.0 * header_score[fa]["amount"]
                           - 1.0 * header_score[fq]["price"] - 1.0 * header_score[fp]["qty"])
                    # qty is normally the smaller magnitude of the pair
                    mag = sum(1 for r in rows if nums[(r, fq)] <= nums[(r, fp)])
                    cands.append({"qty": fq, "price": fp, "amount": fa,
                                  "hits": hits, "tie": tie, "mag": mag, "rows": rows})
    if not cands:
        return None
    cands.sort(key=lambda c: (c["hits"], c["tie"], c["mag"], -c["qty"]), reverse=True)
    best = cands[0]
    rival = None
    for c in cands[1:]:
        if (c["qty"], c["price"], c["amount"]) == (best["qty"], best["price"], best["amount"]):
            continue
        rival = c
        break
    ambiguous = bool(rival and rival["hits"] == best["hits"] and rival["tie"] == best["tie"]
                     and rival["mag"] == best["mag"]
                     and {rival["qty"], rival["price"]} != {best["qty"], best["price"]})
    best["ambiguous"] = ambiguous
    best["rival"] = None if not rival else {k: rival[k] for k in ("qty", "price", "amount", "hits")}
    return best


def detect_roles_by_header(view):
    """Fallback when no amount column exists: qty and price by header words."""
    n_rec, n_field = view.n_rec, view.n_field
    picks = {}
    for role in ("qty", "price"):
        for f in range(n_field):
            blob = " ".join(view.text(r, f) for r in range(min(n_rec, 12)))
            if any_word(norm(blob), loose(blob), HEADER_HINTS[role]):
                numeric = sum(1 for r in range(n_rec) if view.number(r, f) is not None)
                if numeric >= 2:
                    picks.setdefault(role, f)
    if "qty" in picks and "price" in picks and picks["qty"] != picks["price"]:
        return {"qty": picks["qty"], "price": picks["price"], "amount": None,
                "hits": 0, "ambiguous": False, "rival": None, "rows": []}
    return None


def pick_name_field(view, roles):
    """The field holding item names: most non-numeric text, left of qty."""
    n_rec, n_field = view.n_rec, view.n_field
    used = {roles.get("qty"), roles.get("price"), roles.get("amount")}
    best, best_score = None, 0.0
    for f in range(n_field):
        if f in used:
            continue
        score = 0.0
        for r in range(n_rec):
            t = view.text(r, f).strip()
            if not t:
                continue
            if view.number(r, f) is not None:
                continue
            if len(t) <= 1 and t.isdigit():
                continue
            score += min(len(t), 24) / 24.0
            if families_of(t)[0]:
                score += 1.5
        if roles.get("qty") is not None and f < roles["qty"]:
            score *= 1.15
        if score > best_score:
            best, best_score = f, score
    return best


def all_text_cells(model):
    out = []
    for sheet in model.sheetnames:
        nrows, ncols = model.dims[sheet]
        seen = set()
        for r in range(1, nrows + 1):
            for c in range(1, ncols + 1):
                coord = index_to_col_letters(c) + str(r)
                anc = model.anchor(sheet, coord)
                if anc in seen:
                    continue
                seen.add(anc)
                t = model.text(sheet, anc, follow_merge=False)
                if t and str(t).strip():
                    out.append({"sheet": sheet, "cell": anc, "text": str(t).strip()})
    return out


# ---------------------------------------------------------------------------
# 2c.  EXTRACT - row classes, blocks, charges, totals
# ---------------------------------------------------------------------------

STATE_PARSE_ERROR = STATE_PARSE
PLACEMENT_HEADER_WORDS = ["位置", "分配", "点位", "安装地点", "placement", "location", "allocation"]


def hit(text, words):
    return any_word(norm(text), loose(text), words)


def first_pos(text, words):
    """Position of the earliest occurrence of any word, or None."""
    packed, spaced = norm(text), loose(text)
    best = None
    for w in words:
        if any(is_cjk(c) for c in w):
            i = packed.find(w)
        else:
            m = re.search(r"(?<![a-z0-9])" + re.escape(w.strip()), spaced)
            i = -1 if m is None else len(norm(spaced[:m.start()]))
        if i >= 0 and (best is None or i < best):
            best = i
    return best


def display_units(text):
    """Length in reading units: one per CJK character, one per ascii word."""
    s = _fullwidth_to_half(str(text))
    return sum(1 for ch in s if is_cjk(ch)) + len(re.findall(r"[A-Za-z0-9]+", s))


def header_row_of(view):
    for r in range(min(view.n_rec, 60)):
        roles_hit = set()
        for f in range(view.n_field):
            t = view.text(r, f).strip()
            if not t or len(norm(t)) > 20 or view.number(r, f) is not None:
                continue
            for role in ("qty", "price", "amount", "name", "unit"):
                if hit(t, HEADER_HINTS[role]):
                    roles_hit.add(role)
        if len(roles_hit & {"qty", "price", "amount"}) >= 2:
            return r
    return None


INSTALL_WORDS = ["安装", "施工费", "人工费", "install", "labour", "labor"]
TRANSPORT_WORDS = ["运输", "运费", "transport"]
MAINT_WORDS = ["维护", "维保", "运维", "maintenance"]


def classify_label(label):
    """'charge' / 'subtotal' / 'total' / None, the earliest keyword wins.

    A label naming installation without naming transport or maintenance is an
    installation line, not a percentage charge: 安装调试费 is the lump sum the
    house rules forbid billing, and it must stay visible to D06."""
    pc = first_pos(label, CHARGE_WORDS)
    if pc is not None and hit(label, INSTALL_WORDS) and not (hit(label, TRANSPORT_WORDS) or hit(label, MAINT_WORDS)):
        pc = None
    ps, pt = first_pos(label, SUBTOTAL_WORDS), first_pos(label, TOTAL_WORDS)
    cands = [(p, k) for p, k in ((pc, "charge"), (ps, "subtotal"), (pt, "total")) if p is not None]
    if not cands:
        return None
    cands.sort()
    return cands[0][1]


def build_table(model, sheet):
    best_view, best_roles = None, None
    for orient in ("row", "col"):
        view = TableView(model, sheet, orient)
        roles = detect_roles(view)
        if roles and (best_roles is None or roles["hits"] > best_roles["hits"]):
            best_view, best_roles = view, roles
    if best_roles is None:
        view = TableView(model, sheet, "row")
        r2 = detect_roles_by_header(view)
        if r2:
            best_view, best_roles = view, r2
    if best_roles is None:
        return None
    view, roles = best_view, best_roles
    hdr = header_row_of(view)
    roles["name"] = pick_name_field(view, roles)
    if hdr is not None:
        role_fields = {roles.get("qty"), roles.get("price"), roles.get("amount")}
        named = [f for f in range(view.n_field) if f not in role_fields
                 and hit(view.text(hdr, f), HEADER_HINTS["name"]) and not hit(view.text(hdr, f), HEADER_HINTS["desc"])]
        if len(named) == 1:
            roles["name"] = named[0]
    used = {roles.get("qty"), roles.get("price"), roles.get("amount"), roles.get("name")}

    unit_f, desc_fs = None, []
    for f in range(view.n_field):
        if f in used:
            continue
        h = view.text(hdr, f).strip() if hdr is not None else ""
        if h and hit(h, HEADER_HINTS["unit"]) and not hit(h, HEADER_HINTS["price"]) and len(norm(h)) <= 8:
            if unit_f is None:
                unit_f = f
            continue
        if h and hit(h, PLACEMENT_HEADER_WORDS) and not hit(h, HEADER_HINTS["desc"]):
            continue
        desc_fs.append(f)

    known_rows = roles.get("rows") or []
    first_priced = min(known_rows) if known_rows else 0
    start = hdr + 1 if hdr is not None else 0
    lines, aggs, charges, headings, scope = [], [], [], [], []
    for r in range(start, view.n_rec):
        q = view.number(r, roles["qty"]) if roles.get("qty") is not None else None
        p = view.number(r, roles["price"]) if roles.get("price") is not None else None
        a = view.number(r, roles["amount"]) if roles.get("amount") is not None else None
        texts = [view.text(r, f).strip() for f in range(view.n_field)]
        name = texts[roles["name"]] if roles.get("name") is not None else ""
        label = name or next((t for i, t in enumerate(texts)
                              if t and view.number(r, i) is None and len(t) > 1), "")
        a_coord = view.coord(r, roles["amount"]) if roles.get("amount") is not None else None
        a_formula = model.formula(sheet, a_coord) if a_coord else None
        kind = classify_label(label) if label else None
        # zero quantity with a price is an option line: it keeps its price
        priced_shape = q is not None and p is not None and q >= 0 and p > 0
        anchors = {model.anchor(sheet, view.coord(r, f)) for f in range(view.n_field) if texts[f]}
        nonempty = len(anchors)

        if kind == "charge" and (a is not None or isinstance(a_formula, str)):
            charges.append({"sheet": sheet, "row": r, "label": label[:80], "cell": a_coord,
                            "formula": a_formula, "value": a,
                            "rate_cell": view.coord(r, roles["qty"]) if priced_shape else None})
            continue
        if kind in ("subtotal", "total") and not (priced_shape and first_pos(label, FAMILY_VOCAB_FLAT) == 0):
            val, coord = a, a_coord
            if val is None and not isinstance(a_formula, str):
                for f in range(view.n_field - 1, -1, -1):
                    v = view.number(r, f)
                    if v is not None:
                        val, coord = v, view.coord(r, f)
                        break
            if val is None and not isinstance(model.formula(sheet, coord) if coord else None, str):
                continue
            aggs.append({"sheet": sheet, "row": r, "label": label[:80], "kind": kind, "cell": coord,
                         "formula": model.formula(sheet, coord) if coord else None, "value": val})
            continue
        if priced_shape:
            fams, ev = families_of(label)
            unit = texts[unit_f] if unit_f is not None else ""
            desc = [texts[f] for f in desc_fs if texts[f] and view.number(r, f) is None]
            lines.append({"sheet": sheet, "row": r, "name": label[:80], "qty": q, "price": p, "amount": a,
                          "qty_cell": view.coord(r, roles["qty"]), "price_cell": view.coord(r, roles["price"]),
                          "amount_cell": a_coord, "amount_formula": a_formula,
                          "unit": unit, "desc": desc, "families": fams, "family_evidence": ev,
                          "option": q == 0})
            continue
        sparse = nonempty <= 3 and a is None and q is None and p is None
        if label and not sparse:
            fams, _ev = families_of(label)
            if fams:
                scope.append({"sheet": sheet, "row": r, "name": label[:80], "families": fams, "qty": q, "price": p,
                              "desc": [texts[f] for f in desc_fs if texts[f] and view.number(r, f) is None]})
                continue
        if sparse and label:
            before_first = hdr is None and r < first_priced - 1
            is_note = re.match(r"^\s*(注|说明|备注|note)", _fullwidth_to_half(label), re.I) is not None
            if display_units(label) <= 60 and not before_first and not is_note:
                headings.append({"sheet": sheet, "row": r, "label": label[:80]})
    if not lines:
        return None
    last_line = max(l["row"] for l in lines)
    headings = [h for h in headings if h["row"] < last_line]
    return {"sheet": sheet, "orient": view.orient, "roles": roles, "header_row": hdr,
            "unit_field": unit_f, "desc_fields": desc_fs, "lines": lines, "aggregates": aggs,
            "charges": charges, "headings": headings, "scope_rows": [s for s in scope if s["row"] < last_line]}


FAMILY_VOCAB_FLAT = sorted({w for ws in FAMILY_VOCAB.values() for w in ws}, key=len, reverse=True)


def build_blocks(table):
    """Walk rows in order.  A heading opens a named block; lines accumulate; a
    subtotal closes the open block, or attaches above it when it precedes the
    block's lines.  A total or a charge ends the walk of blocks."""
    events = ([("heading", h["row"], h) for h in table["headings"]]
              + [("line", l["row"], l) for l in table["lines"]]
              + [(a["kind"], a["row"], a) for a in table["aggregates"]]
              + [("charge", c["row"], c) for c in table["charges"]])
    events.sort(key=lambda e: e[1])
    blocks, cur, stray = [], None, []
    for kind, _row, obj in events:
        if kind == "heading":
            cur = {"sheet": table["sheet"], "name": obj["label"], "heading_row": obj["row"],
                   "lines": [], "subtotal": None, "subtotal_above": False}
            blocks.append(cur)
        elif kind == "line":
            if cur is None or (cur["subtotal"] is not None and not cur["subtotal_above"]):
                cur = {"sheet": table["sheet"], "name": None, "heading_row": None,
                       "lines": [], "subtotal": None, "subtotal_above": False}
                blocks.append(cur)
            cur["lines"].append(obj)
        elif kind == "subtotal":
            if cur is not None and cur["subtotal"] is None:
                cur["subtotal"] = obj
                cur["subtotal_above"] = not cur["lines"]
            else:
                stray.append(obj)
        else:
            cur = None
    blocks = [b for b in blocks if b["lines"]]
    return blocks, stray


# Worksheets that say they are not the quotation itself.
#
# A submission may add a reconciliation sheet that walks each handwritten reading back
# to the priced line it became, or a scope note that states what is and is not included.
# Those are working papers, and reading their rows as unblocked quotation lines marks
# every one of them misplaced, which takes the grouping item to zero however well the
# quotation sheet itself is organised. The quotation is the sheet that carries the
# priced lines and the charges; a sheet that announces itself as a check or a note is
# excluded from the grouping judgement, and only from that judgement.
ANCILLARY_SHEET_MARKERS = ("核对", "对照", "复核", "说明", "备注", "附录", "附注",
                           "工作底稿", "底稿", "check", "note", "appendix", "reconcil")


def is_ancillary_sheet(name, table=None):
    n = str(name or "").strip().lower()
    if any(m in n for m in ANCILLARY_SHEET_MARKERS):
        return True
    if table is not None:
        title = " ".join(str(x) for x in (table.get("title_cells") or []))[:120]
        if any(m in title for m in ANCILLARY_SHEET_MARKERS):
            return True
    return False


def extract(path):
    ex = {"path": path, "workbook": {"state": STATE_PARSE, "detail": None}, "sheets": [],
          "tables": [], "lines": [], "aggregates": [], "charges": [], "blocks": [],
          "stray_subtotals": [], "scope_rows": [], "text_cells": [], "notes": []}
    if not path or not os.path.exists(path):
        ex["workbook"] = {"state": STATE_MISSING, "detail": "file does not exist: %s" % path}
        return ex
    try:
        model = ex["model"] = WorkbookModel(path)
    except Exception as exc:
        ex["workbook"] = {"state": STATE_PARSE, "detail": "%s: %s" % (type(exc).__name__, exc)}
        return ex
    ex["workbook"] = {"state": STATE_IDENTIFIED, "detail": "sheets=%s" % model.sheetnames}
    ex["sheets"] = list(model.sheetnames)
    ex["ancillary_lines"] = []
    ex["text_cells"] = all_text_cells(model)
    built = []
    for sheet in model.sheetnames:
        try:
            t = build_table(model, sheet)
        except Exception as exc:
            ex["notes"].append({"sheet": sheet, "state": STATE_PARSE,
                                "detail": "%s: %s" % (type(exc).__name__, exc)})
            continue
        if not t:
            continue
        blocks, stray = build_blocks(t)
        t["blocks"] = blocks
        built.append((sheet, t, blocks, stray))

    # Which worksheet is the quotation, and which are working papers.
    #
    # Submissions routinely add a sheet that walks the handwritten readings back to the
    # priced lines, a scope note, a photo sheet, a rate catalogue. Their names do not
    # follow any pattern worth listing -- 现场记录整理, 记录转写与核对, Source_Register,
    # Assumptions_Checks all appeared. Reading their rows as quotation lines counted the
    # same equipment twice, so the roll-up check saw a subtotal of 26,800 where it had
    # summed 57,600, and charged a broken total against a workbook whose arithmetic was
    # correct. The quotation is instead identified by content: it is the sheet carrying
    # the two percentage charges, which the assignment makes part of the quotation
    # itself. Where no sheet carries them, the sheet with the most priced lines is taken,
    # and the name heuristic is the last resort.
    priced = [(s, t) for s, t, _, _ in built if t["lines"]]
    with_charges = [s for s, t, _, _ in built if t["charges"]]
    if with_charges:
        primary = set(with_charges)
    elif priced:
        primary = {max(priced, key=lambda x: len(x[1]["lines"]))[0]}
    else:
        primary = {s for s, _, _, _ in built if not is_ancillary_sheet(s, None)}

    for sheet, t, blocks, stray in built:
        t["ancillary"] = sheet not in primary
        ex["tables"].append(t)
        if t["ancillary"]:
            # Kept in ex["tables"] so other checks can still read it, but its rows are
            # not quotation lines and do not form an unnamed block.
            ex["ancillary_lines"].extend(t["lines"])
            ex["stray_subtotals"].extend(stray)
            continue
        ex["lines"].extend(t["lines"])
        ex["aggregates"].extend(t["aggregates"])
        ex["charges"].extend(t["charges"])
        ex["scope_rows"].extend(t["scope_rows"])
        ex["blocks"].extend(blocks)
        ex["stray_subtotals"].extend(stray)
    ex["primary_sheets"] = sorted(primary)
    # A worksheet whose lines form one unnamed block closed by its own subtotal
    # counts as a named block when the lines are spread over several worksheets.
    priced_tables = [t for t in ex["tables"] if t["lines"]]
    if len(priced_tables) >= 2:
        for t in priced_tables:
            if len(t["blocks"]) == 1 and t["blocks"][0]["name"] is None and t["blocks"][0]["subtotal"]:
                t["blocks"][0]["name"] = "[sheet] " + t["sheet"]
    if not ex["tables"]:
        ex["notes"].append({"state": STATE_MISSING, "detail": "no line item table found"})
    return ex


# ---------------------------------------------------------------------------
# 3.  DECIDE and MEASURE
# ---------------------------------------------------------------------------

WORKS_FAMS = ("cable", "conduit", "civil")
SOFTWARE_WORDS = ["软件", "加密", "software", "dongle", "licence", "license"]
D02_RE = re.compile(r"(质保|保修|warranty|交货期|供货期|工作日|付款|预付|首付|尾款|热线|服务电话|型号|品牌|brand|model)", re.I)
PLACEMENT_TOKENS_RE = re.compile(r"(大门|侧门|进口|出口|入口|混进混出|进方向|出方向|方向|每条车道|每个|每台|道闸点位|点位|车道|对应|各|进|出|条|台|个|套|只|根|处|[0-9]+|[\s，,、；;:：。.()（）])")


def cellset(ex, sheet, formula):
    singles, ranges = formula_refs(formula, sheet, ex["model"])
    out = set(singles)
    for sh, a, b in ranges:
        out.update(expand_range(sh, a, b))
    return out


def reach(ex, sheet, coord, depth=6, seen=None):
    """Cells a cell depends on, following references through formula cells."""
    model = ex["model"]
    seen = set() if seen is None else seen
    f = model.formula(sheet, coord)
    if depth <= 0 or not isinstance(f, str) or not f.startswith("="):
        return seen
    for sh, c in cellset(ex, sheet, f):
        if (sh, c) in seen:
            continue
        seen.add((sh, c))
        reach(ex, sh, c, depth - 1, seen)
    return seen


def amount_of(line):
    return line["amount"] if line["amount"] is not None else line["qty"] * line["price"]


def pre_levy(ex):
    aggs = [a for a in ex["aggregates"] if a["cell"]]
    charges = [c for c in ex["charges"] if isinstance(c["formula"], str)]
    if charges:
        reaches = [reach(ex, c["sheet"], c["cell"]) for c in charges]
        cands = [a for a in aggs if all((a["sheet"], a["cell"]) in r for r in reaches)]
        if not cands:
            return None
        return max(cands, key=lambda a: len(reach(ex, a["sheet"], a["cell"]) & {(b["sheet"], b["cell"]) for b in aggs}))
    total = sum(amount_of(l) for l in ex["lines"])
    cands = [a for a in aggs if a["value"] is not None and close(a["value"], total, ROUNDING_TOL)]
    return max(cands, key=lambda a: (a["sheet"], a["row"])) if cands else None


def final_total(ex, base):
    charges = [c for c in ex["charges"] if c["cell"]]
    need = {(c["sheet"], c["cell"]) for c in charges}
    if base:
        need.add((base["sheet"], base["cell"]))
    cands = [a for a in ex["aggregates"] if a["kind"] == "total" and a["cell"]
             and (a is not base) and need <= reach(ex, a["sheet"], a["cell"])]
    if cands:
        return max(cands, key=lambda a: a["row"])
    return base if not charges else None


def trade_of_line(line):
    trades = {TRADE_OF.get(f) for f in line["families"]} - {None}
    return trades.pop() if len(trades) == 1 else None


def block_of_row(ex, sheet, row):
    """Index of the block whose row span (heading or first line, to subtotal or last line) holds the row."""
    for i, b in enumerate(ex["blocks"]):
        if b["sheet"] != sheet or not b["lines"]:
            continue
        lo = b["heading_row"] if b["heading_row"] is not None else min(l["row"] for l in b["lines"])
        hi = max([l["row"] for l in b["lines"]] + ([b["subtotal"]["row"]] if b["subtotal"] and not b["subtotal_above"] else []))
        if lo <= row <= hi:
            return i
    return None


def placement_failures(ex):
    items = ex["lines"] + ex.get("scope_rows", [])
    where = {}
    for it in items:
        bi = block_of_row(ex, it["sheet"], it["row"])
        for f in it["families"]:
            where.setdefault(f, set()).add(bi)
    def trade(bi):
        if bi is None:
            return None
        known = [trade_of_line(l) for l in ex["blocks"][bi]["lines"]]
        known = [k for k in known if k]
        return max(set(known), key=known.count) if known else None
    fails = []
    lane = where.get("barrier", set()) | where.get("plate", set()) | where.get("radar", set())
    if len(lane) != 1 or None in lane or trade(next(iter(lane))) != "lane":
        fails.append("a")
    ctl = where.get("controller", set())
    if not ctl or None in ctl or any(trade(b) not in ("control",) for b in ctl):
        fails.append("b")
    mon = where.get("monitoring", set()) | where.get("bracket", set())
    if len(mon) != 1 or None in mon or trade(next(iter(mon))) not in ("control",):
        fails.append("c")
    isl = where.get("island", set())
    works_blocks = {bi for f in ("cable", "conduit", "civil") for bi in where.get(f, set())}
    if not isl or None in isl or not isl <= works_blocks:
        fails.append("d")
    sg = where.get("sign", set())
    if not sg or None in sg or sg & works_blocks:
        fails.append("e")
    return fails


def judge_b1(ex):
    blocks = ex["blocks"]
    named = [b for b in blocks if b["name"]]
    parts = {"t1": 0.0, "t2": False, "t3": False}
    ev = {"blocks": [{"name": b["name"], "lines": [l["row"] for l in b["lines"]],
                      "subtotal": b["subtotal"]["cell"] if b["subtotal"] else None} for b in blocks]}
    if len(named) >= 2:
        # Judge the submitted scope, not the reference's grouping taxonomy.
        from semantic_judge import adjudicate
        candidate = json.dumps(ev["blocks"],ensure_ascii=False) + "\n" + json.dumps(
            [{"sheet":b["sheet"],"block":b["name"],"lines":[{"row":l["row"],"name":l["name"],"description":l["desc"]} for l in b["lines"]]} for b in blocks],ensure_ascii=False)
        verdict = adjudicate(
            candidate, (Path(__file__).parent / "semantic_source.json").read_text(),
            ("COHERENT_GROUPS",))
        parts["t1"] = verdict["items"]["COHERENT_GROUPS"]["fraction"]
        ev["grouping_adjudication"] = verdict
    all_amount = {(l["sheet"], l["amount_cell"]) for l in ex["lines"]}
    base = pre_levy(ex)
    ev["pre_levy"] = base["cell"] if base else None
    base_formula = base["formula"] if base and isinstance(base.get("formula"), str) else None
    direct = cellset(ex, base["sheet"], base_formula) if base_formula else set()

    # The assignment asks for amounts and totals that recalculate in the workbook and
    # for the two percentage charges to rest on the total of everything quoted before
    # them. It does not ask for a subtotal under every group -- that is how the
    # reference happens to be laid out. A quotation that groups its lines and then
    # rolls them into one pre-charge total satisfies what was asked, so both routes
    # are accepted: per-group subtotals that each cover their own lines, or a single
    # pre-charge total that covers every priced line exactly once.
    per_block = False
    if named:
        per_block = True
        for b in named:
            st = b["subtotal"]
            if not st or not isinstance(st["formula"], str):
                per_block = False
                break
            covered = cellset(ex, st["sheet"], st["formula"]) & all_amount
            if covered != {(l["sheet"], l["amount_cell"]) for l in b["lines"]}:
                per_block = False
                break
    single_total = bool(base_formula) and bool(all_amount) and (direct & all_amount) == all_amount
    formula_lines_ok = all(isinstance(line.get("amount_formula"), str)
                           and line["amount_formula"].startswith("=")
                           for line in ex["lines"])
    parts["t2"] = (per_block or single_total) and formula_lines_ok
    ev["rollup_route"] = ("per_block_subtotals" if per_block
                          else ("single_pre_charge_total" if single_total else "none"))

    if base_formula:
        subs = {(b["subtotal"]["sheet"], b["subtotal"]["cell"]) for b in named if b["subtotal"]}
        via_subtotals = bool(subs) and len(subs) == len(named) and subs <= direct and not (direct & all_amount)
        # Reaching the pre-charge total through the subtotals is one correct way to build
        # it; summing the priced lines directly is another, and the assignment prefers
        # neither. What must hold either way is that the total is computed, not typed.
        parts["t3"] = via_subtotals or single_total

    tier = parts["t1"]
    # t2 and t3 unlock in proportion to t1 rather than only at the top tier. A grouping
    # with one line in the wrong group is a grouping that a reader can still follow and
    # that rolls up correctly; hard-gating it discarded the rest of the item's evidence
    # over a single row.
    frac = (tier + tier * (parts["t2"] + parts["t3"])) / 3.0
    return frac, parts, ev, {"t1": True, "t2": False, "t3": False}


def unit_kind(line):
    u = norm(line["unit"])
    if not u:
        return "unknown"
    if u in [norm(x) for x in LENGTH_UNITS]:
        return "length"
    if u in [norm(x) for x in LUMP_UNITS]:
        return "lump"
    return "count"


def judge_b2(ex):
    works = [l for l in ex["lines"] if set(l["families"]) & set(WORKS_FAMS)]
    measured = []
    for l in works:
        f = l["amount_formula"]
        if unit_kind(l) in ("length", "count") and formula_multiplies_refs(
                f, l["sheet"], l["qty_cell"], l["price_cell"]):
            measured.append(l)
    fams = set()
    for l in measured:
        fams |= set(l["families"]) & set(WORKS_FAMS)
    parts = {"t1": 0.0, "t2": False, "t3": False}
    length = [l for l in measured if unit_kind(l) == "length"]
    comp = {"data": [], "power": [], "signal": [], "conduit": [], "trench": []}
    for l in length:
        nm = l["name"]
        if "cable" in l["families"] and hit(nm, DATA_WORDS):
            comp["data"].append(l)
        elif "cable" in l["families"] and hit(nm, POWER_WORDS):
            comp["power"].append(l)
        elif "cable" in l["families"] and hit(nm, SIGNAL_WORDS):
            comp["signal"].append(l)
        if "conduit" in l["families"]:
            comp["conduit"].append(l)
        if "civil" in l["families"] and hit(nm, TRENCH_WORDS):
            comp["trench"].append(l)
    covered = [k for k in ("data", "power", "conduit", "trench") if comp[k]]
    # Component names are diagnostic only: the photographs do not prescribe the
    # reference workbook's four separate takeoff rows.
    from semantic_judge import adjudicate
    candidate = json.dumps({
        "site_work_lines":[{k:l[k] for k in ("sheet","row","name","desc","qty","unit","price","amount_formula")} for l in works],
        "headings":[b["name"] for b in ex["blocks"] if b["name"]],
        "quotation_text":[{"sheet":c["sheet"],"cell":c["cell"],"text":c["text"]} for c in ex["text_cells"]]
    },ensure_ascii=False,indent=2)
    verdict = adjudicate(
        candidate, (Path(__file__).parent/"semantic_source.json").read_text(),
        ("SITE_SCOPE","ACTUAL_SETTLEMENT","SITE_ESTIMATE_BASIS"))
    scope_ok = verdict["items"]["SITE_SCOPE"]["fraction"] == 1
    measured_share = len(measured)/len(works) if works else 0
    parts["t1"] = (1.0 if measured_share == 1 else .5 if measured_share >= .5 else 0.0) if scope_ok else 0.0
    works_vocab = [w for k in WORKS_FAMS for w in FAMILY_VOCAB[k]]
    rows = {(l["sheet"], l["row"]) for l in works}
    heads = [b for b in ex["blocks"] if b["name"] and set((l["sheet"], l["row"]) for l in b["lines"]) & rows]
    settle_text = [h["name"] for h in heads if hit(h["name"], SETTLE_WORDS)]
    settle_text += [d for l in works for d in l["desc"] if hit(d, SETTLE_WORDS)]
    windows = []
    for b in ex["blocks"]:
        if set((l["sheet"], l["row"]) for l in b["lines"]) & rows:
            lo = (b["heading_row"] if b["heading_row"] is not None else min(l["row"] for l in b["lines"])) - 3
            windows.append((b["sheet"], lo, max(l["row"] for l in b["lines"]) + 6))
    for tc in ex["text_cells"]:
        if not hit(tc["text"], SETTLE_WORDS):
            continue
        r0 = row_of(tc["cell"]) - 1
        if hit(tc["text"], works_vocab) or any(tc["sheet"] == s and lo <= r0 <= hi for s, lo, hi in windows):
            settle_text.append(tc["text"])
    parts["t2"] = verdict["items"]["ACTUAL_SETTLEMENT"]["fraction"] == 1
    # The photographs do not establish cable lengths. Positive provisional quantities
    # with an explicit actual-settlement basis are traceable estimates, not hidden
    # golden takeoff bands.
    positive_quantities = bool(works) and all(l["qty"] is not None and l["qty"] > 0 for l in works)
    tie_text = [d for l in measured for d in l["desc"]] + [h["name"] for h in heads] + settle_text
    site_bound = verdict["items"]["SITE_ESTIMATE_BASIS"]["fraction"] == 1
    parts["t3"] = positive_quantities and site_bound and parts["t2"]
    tier = parts["t1"]
    frac = (tier + tier * parts["t2"] + tier * parts["t3"]) / 3.0
    ev = {"works_rows": [l["row"] for l in works], "measured_rows": [l["row"] for l in measured],
          "units": {l["row"]: l["unit"] for l in works}, "settle_text": settle_text[:3],
          "components": {k: [(l["row"], l["qty"]) for l in v] for k, v in comp.items()}}
    ev["part_evidence"] = {
        "t1": {"covered_components":covered,"required_components":[],"scope_adjudication":verdict["items"]["SITE_SCOPE"],"measured_share":measured_share,
               "measured_cells":[{"sheet":l["sheet"],"row":l["row"],"quantity_cell":l["qty_cell"],"unit_rate_cell":l["price_cell"],"amount_cell":l["amount_cell"],"formula":l["amount_formula"]} for l in measured]},
        "t2": {"actual_settlement_stated":parts["t2"],"adjudication":verdict["items"]["ACTUAL_SETTLEMENT"],"statements":settle_text},
        "t3": {"positive_quantities":positive_quantities,"site_bound":site_bound,"provisional_actual_settlement":parts["t2"],"adjudication":verdict["items"]["SITE_ESTIMATE_BASIS"],"quantity_bands_used":False,"site_statements":tie_text}}
    ev["site_works_adjudication"] = verdict
    return frac, parts, ev, {"t1": True, "t2": True, "t3": True}


def judge_a1(ex):
    got, ev = 0, {}
    for fam, price in A1_PRICES.items():
        rows = [l for l in ex["lines"] if fam in l["families"] and abs(l["price"] - price) < ROUNDING_TOL]
        ev[fam] = [l["price_cell"] for l in rows]
        got += 1 if rows else 0
    return got / float(len(A1_PRICES)), ev


def judge_a2(ex):
    L = ex["lines"] + ex.get("scope_rows", [])
    checks = {
        "bracket": [l for l in L if "bracket" in l["families"]],
        "plate_qty": [l for l in L if "plate" in l["families"] and l["qty"] is not None and abs(l["qty"] - PLATE_QTY) < 1e-9],
        "barrier_qty": [l for l in L if "barrier" in l["families"] and l["qty"] is not None and abs(l["qty"] - BARRIER_QTY) < 1e-9],
        "radar_qty": [l for l in L if "radar" in l["families"] and l["qty"] is not None and abs(l["qty"] - RADAR_QTY) < 1e-9],
        "software": [l for l in L if "controller" in l["families"] and (hit(l["name"], SOFTWARE_WORDS) or any(hit(d, SOFTWARE_WORDS) for d in l["desc"]))],
        "sign_qty": [l for l in L if "sign" in l["families"] and l["qty"] is not None and abs(l["qty"] - SIGN_QTY) < 1e-9],
        "island_qty": [l for l in L if "island" in l["families"] and l["qty"] is not None and abs(l["qty"] - ISLAND_QTY) < 1e-9],
        "monitoring_qty": [l for l in L if "monitoring" in l["families"] and l["qty"] is not None and abs(l["qty"] - MONITORING_QTY) < 1e-9],
    }
    ev = {k: [l["row"] for l in v] for k, v in checks.items()}
    return sum(1 for v in checks.values() if v) / float(len(A2_UNITS)), ev


def judge_a3(ex):
    base = pre_levy(ex)
    charges = [c for c in ex["charges"] if isinstance(c["formula"], str)]
    def dynamic(formula):
        return isinstance(formula, str) and not re.search(r"\*0(?:\.0+)?(?![\d.])", formula.replace(" ", "").lower())
    half1 = bool(base and charges and all(dynamic(c.get("formula")) and
        (base["sheet"], base["cell"]) in reach(ex, c["sheet"], c["cell"]) for c in charges))
    top = final_total(ex, base)
    half2 = bool(half1 and top and dynamic(top.get("formula")) and isinstance(top["formula"], str) and top is not base)
    return 0.5 * half1 + 0.5 * half2, {"pre_levy": base["cell"] if base else None,
                                       "charges": [c["cell"] for c in charges],
                                       "final_total": top["cell"] if top else None}


def row_of(cell):
    cp = coord_parts(cell)
    return cp[1] if cp else 10 ** 6


def judge_f1(ex):
    for t in ex["tables"]:
        limit = (t["header_row"] + 1) if t["header_row"] is not None else 6
        blob = " ".join(c["text"] for c in ex["text_cells"] if c["sheet"] == t["sheet"] and row_of(c["cell"]) <= limit)
        if hit(blob, TITLE_WORDS) and hit(blob, SYSTEM_WORDS_A) and hit(blob, SYSTEM_WORDS_B):
            return 1.0, {"sheet": t["sheet"]}
    return 0.0, {}


def is_description(text, name):
    if not text or norm(text) == norm(name):
        return False
    rest = PLACEMENT_TOKENS_RE.sub("", _fullwidth_to_half(text))
    return sum(1 for ch in rest if is_cjk(ch) or ch.isalpha()) >= 2


def judge_f2(ex):
    L = ex["lines"]
    if not L:
        return 0.0, {}
    has_field = any(t["desc_fields"] for t in ex["tables"]) and any(l["desc"] for l in L)
    good = [l["row"] for l in L if any(is_description(d, l["name"]) for d in l["desc"])]
    if not has_field:
        return 0.0, {"described_rows": good}
    return len(good) / float(len(L)), {"described_rows": good, "lines": len(L)}


# ---------------------------------------------------------------------------
# 4.  Deductions, ledger, command line
# ---------------------------------------------------------------------------

D03_PRICES = dict(A1_PRICES, monitoring=2600.0, bracket=BRACKET_PRICE)
RECORDED_PRICES = sorted(set(D03_PRICES.values()))
SHEET_AMOUNTS = {"barrier": 7200.0, "plate": 8000.0, "radar": 1500.0, "island": 1500.0,
                 "controller": 2500.0, "sign": 1200.0, "monitoring": 2600.0, "bracket": 500.0}


def deductions(ex):
    fired, reported = [], []
    for l in ex["lines"]:
        if l.get("option"):
            continue
        exp = [f for f in l["families"] if f in D03_PRICES]
        if not exp or any(abs(l["price"] - D03_PRICES[f]) < ROUNDING_TOL for f in exp):
            continue
        # A named product has an unambiguous source price.  Coinciding with a
        # different product's rate or reverse-engineering the old amount is not
        # a basis for skipping the price-drift deduction.
        fired.append({"id": "D03", "key": "price_drift:" + exp[0], "cell": l["price_cell"], "value": l["price"]})
    base = pre_levy(ex)
    top = final_total(ex, base)
    checks = []
    for b in ex["blocks"]:
        if b["subtotal"] is not None and b["subtotal"] is not base:
            checks.append((b["subtotal"], sum(amount_of(l) for l in b["lines"])))
    if base is not None:
        checks.append((base, sum(amount_of(l) for l in ex["lines"])))
    if top is not None and top is not base and base is not None and base["value"] is not None:
        cv = [c["value"] for c in ex["charges"]]
        if not cv:
            reported.append({"id": "D04", "state": STATE_AMBIGUOUS, "cell": top["cell"],
                             "detail": "final total reads cells not identified as charges; not judged"})
        elif all(v is not None for v in cv):
            checks.append((top, base["value"] + sum(cv)))
    unevaluable = [l for l in ex["lines"] if l["amount"] is None and isinstance(l["amount_formula"], str)]
    for l in unevaluable:
        reported.append({"id": "D04", "state": STATE_PARSE, "cell": l["amount_cell"],
                         "detail": "line amount formula not evaluable; totals over it are not judged"})
    if unevaluable:
        checks = []
    for agg, expected in checks:
        if agg["value"] is None:
            reported.append({"id": "D04", "state": STATE_PARSE, "cell": agg["cell"]})
        elif abs(agg["value"] - expected) >= ROUNDING_TOL:
            fired.append({"id": "D04", "key": "broken_total:%s!%s" % (agg["sheet"], agg["cell"]),
                          "cell": agg["cell"], "stated": agg["value"], "expected": expected})
    texts = [c["text"] for c in ex["text_cells"]]
    dates = []
    for t in texts:
        for m in re.finditer(r"2026\D{0,3}(\d{1,2})\D{0,3}(\d{1,2})", _fullwidth_to_half(t)):
            dates.append((int(m.group(1)), int(m.group(2))))
    if dates and (QUOTE_DATE[1], QUOTE_DATE[2]) not in dates:
        fired.append({"id": "D06", "key": "handed:date", "detail": str(dates[:3])})
    vat = [float(x) for t in texts if hit(t, TAX_WORDS) and not hit(t, CHARGE_WORDS)
           for x in re.findall(r"(\d+(?:\.\d+)?)\s*%", _fullwidth_to_half(t))]
    if vat and not any(abs(v - VAT_PERCENT) < 1e-9 for v in vat):
        fired.append({"id": "D06", "key": "handed:vat", "detail": str(vat[:3])})
    if base is not None and base["value"]:
        for c in ex["charges"]:
            if c["value"] is None:
                continue
            groups = int(hit(c["label"], TRANSPORT_WORDS) or hit(c["label"], ["调试", "commissioning"])) + int(hit(c["label"], MAINT_WORDS))
            if abs(c["value"] / base["value"] - CHARGE_RATE * max(groups, 1)) > 1e-3:
                fired.append({"id": "D06", "key": "handed:rate", "cell": c["cell"]})
    for l in ex["lines"]:
        if l["families"] == ["installation"] and amount_of(l) > 0:
            fired.append({"id": "D06", "key": "handed:installation_billed", "row": l["row"]})
    for l in ex["lines"]:
        if not l["families"]:
            reported.append({"id": "D01", "state": "needs_semantic_review", "row": l["row"], "name": l["name"]})
    for t in texts:
        if D02_RE.search(t) and re.search(r"\d", t):
            reported.append({"id": "D02", "state": "needs_semantic_review", "text": t[:80]})
        if re.search(r"4,?000", t) and hit(t, INSTALL_WORDS):
            fired.append({"id": "D05", "key": "internal_cost:installation_4000", "text": t[:80]})
    by_key = {}
    for d in fired:
        by_key.setdefault(d["key"], d)
    total = sum(DEDUCTION_AMOUNT[d["id"]] for d in by_key.values())
    return total, list(by_key.values()), fired, reported


def score(path):
    ex = extract(path)
    items, earned = [], 0.0
    ok = ex["workbook"]["state"] == STATE_IDENTIFIED and ex["lines"]
    state = STATE_IDENTIFIED if ok else (STATE_MISSING if ex["workbook"]["state"] == STATE_IDENTIFIED else ex["workbook"]["state"])
    judges = {"B1": judge_b1, "B2": judge_b2, "A1": judge_a1, "A2": judge_a2, "A3": judge_a3, "F1": judge_f1, "F2": judge_f2}
    covered = 0.0
    for iid in ("B1", "B2", "A1", "A2", "A3", "F1", "F2"):
        rec = {"item": iid, "class": CLASS_OF[iid], "weight": WEIGHTS[iid], "state": state}
        frac = 0.0
        if ok:
            try:
                out = judges[iid](ex)
            except Exception as exc:
                if iid in ("B1", "B2"):
                    raise RuntimeError("required quotation adjudication failed for "+iid) from exc
                rec["state"] = STATE_PARSE
                rec["detail"] = "%s: %s" % (type(exc).__name__, exc)
                out = None
            if out is not None and iid in ("B1", "B2"):
                frac, parts, ev, semantic = out
                rec.update({"parts": parts, "evidence": ev, "semantic_parts": [k for k, v in semantic.items() if v]})
                covered += WEIGHTS[iid] * sum(1 for v in semantic.values() if not v) / 3.0
            elif out is not None:
                frac, ev = out
                rec["evidence"] = ev
                if iid == "F2":
                    rec["semantic_parts"] = ["content"]
                else:
                    covered += WEIGHTS[iid]
        rec["fraction"] = frac
        rec["earned"] = WEIGHTS[iid] * frac
        rec["needs_semantic_review"] = bool(rec.get("semantic_parts"))
        earned += rec["earned"]
        items.append(rec)
    ded, unique, raw_fired, reported = deductions(ex) if ok else (0.0, [], [], [])
    raw = earned - ded
    return {
        "rubric": RUBRIC_ID, "deliverable": path, "workbook": ex["workbook"],
        "extraction": {"tables": [{"sheet": t["sheet"], "header_row": t["header_row"], "lines": len(t["lines"]),
                                   "blocks": len(t["blocks"]), "charges": len(t["charges"])} for t in ex["tables"]],
                       "notes": ex["notes"]},
        "items": items, "deductions_applied": unique, "deductions_detected": raw_fired,
        "deductions_reported_not_applied": reported,
        "positive_earned": round(earned, 10), "deduplicated_deductions": round(ded, 10),
        "raw": round(raw, 10), "final": round(max(0.0, raw), 10),
        "mechanical_coverage_of_weight": round(covered, 10),
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx")
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)
    try:
        ledger = score(args.xlsx)
    except Exception:
        traceback.print_exc()
        return 2
    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(ledger, fh, ensure_ascii=False, indent=2)
    for it in ledger["items"]:
        print("%-3s %-2s w=%.2f frac=%.4f earned=%.4f %s%s" % (it["item"], it["class"], it["weight"], it["fraction"],
              it["earned"], it["state"], " semantic" if it["needs_semantic_review"] else ""))
    print("positive_earned=%.4f deductions=%.4f raw=%.4f final=%.4f coverage=%.4f" % (
        ledger["positive_earned"], ledger["deduplicated_deductions"], ledger["raw"], ledger["final"],
        ledger["mechanical_coverage_of_weight"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
