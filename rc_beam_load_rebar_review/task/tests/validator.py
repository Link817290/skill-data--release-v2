#!/usr/bin/env python3
"""Deterministic, content-driven scorer for the beam review workbook (pd-ledger-v1).

Usage: validator.py <beam_review.xlsx | directory holding it>  (rollout artifacts/ or task golden/; the container
passes the file, default /workspace/beam_review.xlsx).

The strict score is settled in the standard form:

  final = positive_earned * retention
  positive_earned = sum(weight[P] * completion[P])      (weights from scoring_params.json or $SCORING_PARAMS)
  retention = prod over damage instances of min(coefficient[D] for D in the instance)

The positive items are the review's own capabilities, each carrying the *proportional* factors that
scale it (a coverage fraction is not damage):
  P01 evidence ledger x source-anchor agreement
  P02/P03 load: derivation and reported actions / the PDF's Table 5.3.1 factors
  P04/P05/P06 flexure: equilibrium chain / reported capacities / strain and the two comparisons
  P07/P08/P09 shear: candidates and sheet / recomputed capacities / the spacing relations
  P10 findings, P11 closure columns
  P12-P16 the evidence ledger's own rows, grouped by what the quantity is

The deduction items are the discrete gates: each costs a coefficient the retention product applies,
rather than an all-or-nothing multiplier folded into one item's completion, and each fires as an
independent damage instance. Coefficients come from the same params file.

The reference workbook replays to positive_earned = 1, retention = 1 and final 1.0. An unreadable
workbook returns a ledger with every completion 0.
"""
from __future__ import annotations
import json, math, os, re, sys
import html as htmlmod
import subprocess
from pathlib import Path

import openpyxl

# --- disowned-unit guard ---------------------------------------------------------------------------
# A unit the submission itself withdraws is not an assertion. The withdrawal must GOVERN THE WHOLE
# UNIT, so the cue is anchored at the start of the unit (after any bullet, quote or table marker) or
# is a quote-and-reject wrapper around it. An unanchored match would charge correct work: a sentence
# such as "it is expressly not asserted as structuring on the present record" is a careful, correct
# finding about a different allegation, not a withdrawal of the whole value. Domain words such as "rejected",
# "withdrawn", "superseded" or "hypothetical" are never cues: they describe the subject matter.
_DISOWN_LEAD = r"^[\s>|*\-–—•·\d.、)）\]】\"'“”‘’]{0,12}"
_DISOWN_RE = re.compile(
    _DISOWN_LEAD + r"(?:"
    r"the following is not asserted(?: here)?|not asserted here\b|"
    r"tentative,?\s*not adopted|not adopted\s*[:：]|unadopted\s*[:：]|"
    r"the draft (?:asserted|stated)\b|"
    r"candidate only\s*[:：]|filed as (?:a )?candidate\b|for discussion only\s*[:：]|"
    r"以下(?:内容)?(?:并非|不是)本方(?:主张|结论)|以下并非|以下不主张|"
    r"疑似(?=[^\n]{0,80}(?:尚未采纳|待核))|"
    r"原稿(?:主张|记载|曾称)|"
    r"并非(?=\S)|"
    r"暂定[，,：:]|候选[，,：:]|未采纳[，,：:]"
    r")", re.I)


def _guard_workbook(wb):
    """Blank every string cell the submission disowns; numbers, formulas and identifiers are untouched."""
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and _DISOWN_RE.search(cell.value):
                    cell.value = ""
    return wb



# ==========================================================================
# Lenient lens: the handful of conclusions this review cannot be delivered
# without.  It reuses the per-atom results the strict scorer already computes
# (`load_parts` / `fx_parts` / `sh_parts`, the identity gate and the open-verdict
# tally) - nothing is re-parsed and nothing weighted is consulted.  Each item is
# binary; the lens is 1 only when all of them hold.
#
# Why these six:
#   inputs_are_this_beam          the brief says "Using only the materials available
#                                 under /workspace ... Do not use information that is
#                                 not supplied under /workspace"; a workbook whose
#                                 resolved inputs are not this beam reviews nothing
#                                 (the same condition strict charges as D01).
#   factored_actions_reproduced   the brief: the workbook "must cover the supplied
#                                 beam's gravity load combination"; RUBRIC P02 - the
#                                 factored midspan moment `Mu_reported` and the shear
#                                 demand `Vu_reported` reproduced within one per cent.
#                                 Every later check hangs off these two numbers.
#   flexural_capacity_reproduced  the brief: "flexural reinforcement"; RUBRIC P05 -
#                                 recomputed capacities agree with `Mn_reported` and
#                                 `phiMn_reported`. An independent check that does not
#                                 reproduce the reported capacity has not checked it.
#   governing_shear_candidate     the brief: "shear reinforcement and detailing
#                                 implications"; RUBRIC P07 - keep all three
#                                 concrete-shear candidates and identify the governing
#                                 one. Picking the governing candidate is the shear
#                                 conclusion the review exists to state.
#   section_capacity_reproduced   the design must close the Formula 15 section
#                                 ceiling against Vu, including the governing Vc.
#   open_verdicts_intact          RUBRIC, verdict coherence: "The two open verdicts ...
#                                 are what the review exists to produce"; D07's
#                                 rationale: "The exceptions are the substance of an
#                                 independent review". Reversing one turns the review
#                                 into a rubber stamp.
#   formula15_vc_term             the supplied Formula 15 explicitly includes Vc;
#                                 a review that copies the printed result while
#                                 omitting that term has not independently checked
#                                 the section ceiling.
#
# Deliberately NOT gates: sheet counts, formula counts, cross-sheet-reference
# counts, ledger field counts, register row counts and register closure share.
# Those are volume/format measures - a workbook can carry all of them and still
# have the beam wrong, and a leaner workbook can still be a usable review.
LENIENT_REQUIRED_ITEMS = [
    "inputs_are_this_beam",          # D01 condition, inverted: identity gate holds
    "factored_actions_reproduced",   # P02 atoms: Mu_reported and Vu_reported within 1%
    "flexural_capacity_reproduced",  # P05 atoms: Mn_reported and phiMn_reported within 3%
    "governing_shear_candidate",     # P07 atom: three candidates kept, governing one named
    "formula15_vc_term",              # P08 atom: complete section-ceiling formula
    "section_capacity_reproduced",    # SH-05 relation and published verdict
    "open_verdicts_intact",          # D07 condition, inverted: SH-02 / SH-04 not reversed
]


# ==========================================================================
# Reading a computed register.
#
# A review workbook may publish its verdicts as formulas - `='Shear'!I31`,
# `=IF(D9>=1,"PASS","FAIL")`, `=IF(COUNTIF(H6:H20,"FAIL")>0,"FAIL",...)`.  Reading
# the formula's TEXT would publish whichever controlled token the text spells
# first, which need not be the value the cell shows: a row whose own condition is
# true (4.71 / 4.46 >= 1) shows PASS however its branches are ordered.
#
# The value is therefore computed, from the workbook's own cells.  It is symmetric
# by construction, and it does not read the cached results openpyxl exposes with
# data_only=True: a workbook written programmatically carries no cache at all, a
# cache can disagree with the formula beside it, and crediting one would read
# deliverables by different rules depending on how each was produced.  A cell that
# already holds a value is never re-evaluated.
#
# A cell whose value IS an Excel error (#VALUE! and the like) stays unreadable - an
# error is not a status - as does any cell the resolver cannot decide.
# ==========================================================================
ERR = object()          # an Excel error value
UNRESOLVED = object()   # this resolver could not decide the cell

# --------------------------------------------------------------------------- #
# tokeniser
# --------------------------------------------------------------------------- #
TOKEN = re.compile(r"""
    (?P<ws>\s+)
  | (?P<str>"(?:[^"]|"")*")
  | (?P<sheet>(?:'(?:[^']|'')+'|[A-Za-z0-9_.À-￿]+)!)
  | (?P<colrange>\$?[A-Za-z]{1,3}\$?:\$?[A-Za-z]{1,3}\$?(?![0-9A-Za-z_]))
  | (?P<rowrange>\$?[0-9]{1,7}:\$?[0-9]{1,7}(?![0-9A-Za-z_.]))
  | (?P<ref>\$?[A-Za-z]{1,3}\$?[0-9]{1,7}(?![0-9A-Za-z_]))
  | (?P<num>(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][-+]?[0-9]+)?)
  | (?P<name>[A-Za-z_À-￿][A-Za-z0-9_.À-￿]*)
  | (?P<op><=|>=|<>|[-+*/^&=<>%])
  | (?P<punct>[(),:;{}])
""", re.X)


def tokenize(src):
    out, i, n = [], 0, len(src)
    while i < n:
        m = TOKEN.match(src, i)
        if not m:
            raise ValueError("token: %r" % src[i:i + 12])
        i = m.end()
        kind = m.lastgroup
        if kind == "ws":
            continue
        out.append((kind, m.group()))
    return out


# --------------------------------------------------------------------------- #
# parser -> tuple AST
# --------------------------------------------------------------------------- #
CMP = {"=", "<>", "<", ">", "<=", ">="}


class Parser:
    def __init__(self, toks):
        self.t, self.i = toks, 0

    def peek(self, k=0):
        return self.t[self.i + k] if self.i + k < len(self.t) else (None, None)

    def take(self):
        tok = self.peek(); self.i += 1; return tok

    def expect(self, text):
        kind, val = self.take()
        if val != text:
            raise ValueError("expected %r got %r" % (text, val))

    def parse(self):
        node = self.expr()
        if self.i != len(self.t):
            raise ValueError("trailing %r" % (self.t[self.i:],))
        return node

    def expr(self):
        left = self.concat()
        while self.peek()[1] in CMP:
            op = self.take()[1]
            left = ("cmp", op, left, self.concat())
        return left

    def concat(self):
        left = self.add()
        while self.peek()[1] == "&":
            self.take()
            left = ("cat", left, self.add())
        return left

    def add(self):
        left = self.mul()
        while self.peek()[1] in ("+", "-"):
            op = self.take()[1]
            left = ("bin", op, left, self.mul())
        return left

    def mul(self):
        left = self.pow_()
        while self.peek()[1] in ("*", "/"):
            op = self.take()[1]
            left = ("bin", op, left, self.pow_())
        return left

    def pow_(self):
        left = self.unary()
        while self.peek()[1] == "^":
            self.take()
            left = ("bin", "^", left, self.unary())
        return left

    def unary(self):
        if self.peek()[1] in ("-", "+"):
            op = self.take()[1]
            return ("neg", self.unary()) if op == "-" else self.unary()
        node = self.postfix()
        return node

    def postfix(self):
        node = self.atom()
        while self.peek()[1] == "%":
            self.take(); node = ("pct", node)
        return node

    def atom(self):
        kind, val = self.peek()
        if val == "(":
            self.take(); node = self.expr(); self.expect(")"); return node
        if val == "{":                     # array literal; not needed, refuse
            raise ValueError("array literal")
        if kind == "num":
            self.take(); return ("num", float(val))
        if kind == "str":
            self.take(); return ("str", val[1:-1].replace('""', '"'))
        if kind == "sheet":
            self.take()
            sheet = val[:-1]
            if sheet.startswith("'"):
                sheet = sheet[1:-1].replace("''", "'")
            return self.ref_tail(sheet)
        if kind in ("ref", "colrange", "rowrange"):
            return self.ref_tail(None)
        if kind == "name":
            if self.peek(1)[1] == "(":
                fname = self.take()[1].upper(); self.take()
                args = []
                if self.peek()[1] != ")":
                    args.append(self.expr())
                    while self.peek()[1] in (",", ";"):
                        self.take()
                        args.append(self.expr() if self.peek()[1] not in (",", ")") else ("empty",))
                self.expect(")")
                return ("call", fname, args)
            word = self.take()[1]
            up = word.upper()
            if up in ("TRUE", "FALSE"):
                return ("bool", up == "TRUE")
            return ("name", word)
        raise ValueError("atom %r" % (val,))

    def ref_tail(self, sheet):
        kind, val = self.take()
        if kind == "colrange":
            a, b = val.replace("$", "").split(":")
            return ("range", sheet, a + "1", b + "1048576")
        if kind == "rowrange":
            a, b = val.replace("$", "").split(":")
            return ("range", sheet, "A" + a, "XFD" + b)
        if kind != "ref":
            # 'Sheet'!Name  -> a sheet-scoped defined name; not supported
            raise ValueError("ref %r" % (val,))
        a = val.replace("$", "")
        if self.peek()[1] == ":" and self.peek(1)[0] == "ref":
            self.take(); b = self.take()[1].replace("$", "")
            return ("range", sheet, a, b)
        return ("cell", sheet, a)


def parse(formula):
    return Parser(tokenize(formula)).parse()


# --------------------------------------------------------------------------- #
# evaluation
# --------------------------------------------------------------------------- #
A1 = re.compile(r"^([A-Za-z]{1,3})([0-9]{1,7})$")


def col_index(letters):
    n = 0
    for ch in letters.upper():
        n = n * 26 + (ord(ch) - 64)
    return n


def col_letters(n):
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def num_of(v):
    if v is None:
        return 0.0
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip().replace(",", "")
        try:
            return float(s)
        except ValueError:
            return ERR
    return ERR


def text_of(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    return str(v)


CRIT = re.compile(r"^(<=|>=|<>|=|<|>)?(.*)$", re.S)


WILD = re.compile(r"[*?]")


def wildcard_re(pattern):
    """Excel COUNTIF wildcards: * any run, ? one character, ~ escapes."""
    out, i = [], 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "~" and i + 1 < len(pattern):
            out.append(re.escape(pattern[i + 1])); i += 2; continue
        out.append(".*" if ch == "*" else "." if ch == "?" else re.escape(ch))
        i += 1
    return re.compile("^" + "".join(out) + "$", re.S)


def match_criteria(value, crit):
    """Excel COUNTIF/COUNTIFS criteria: a bare value, or a comparison prefix."""
    if isinstance(crit, (int, float)) and not isinstance(crit, bool):
        return num_of(value) == float(crit)
    op, rhs = CRIT.match(str(crit)).groups()
    op = op or "="
    if op in ("=", "<>") and WILD.search(rhs):
        # "?*" is Excel's idiom for "any non-empty text"
        hit = bool(wildcard_re(rhs.upper()).match(text_of(value).upper())) \
            and not isinstance(value, (int, float))
        return hit if op == "=" else not hit
    rn = num_of(rhs)
    vn = num_of(value)
    numeric = rn is not ERR and rhs.strip() != "" and vn is not ERR and value is not None
    if numeric:
        a, b = vn, rn
    else:
        a, b = str(text_of(value)).strip().upper(), str(rhs).strip().upper()
    if op == "=":
        return a == b
    if op == "<>":
        return a != b
    if not numeric:
        return False
    return {"<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[op]


NUM_FMT = re.compile(r"^(?P<pre>[^0#]*)(?P<body>[0#,]*(?:\.(?P<dec>[0#]*))?)(?P<post>.*)$")


def apply_number_format(value, fmt):
    """Enough of Excel's number formats for the ones these workbooks use: 0, 0.0,
    0.00, #,##0.00, 0.0%, and a bare text format."""
    if fmt is None or not isinstance(fmt, str):
        return text_of(value)
    n = num_of(value)
    if n is ERR:
        return text_of(value)
    f = fmt.split(";")[0]
    pct = "%" in f
    if pct:
        n *= 100.0
        f = f.replace("%", "")
    m = NUM_FMT.match(f)
    if not m or not m.group("body"):
        return text_of(value)
    dec = len(m.group("dec") or "")
    body = ("{:,.%df}" if "," in m.group("body") else "{:.%df}") % dec
    out = body.format(n)
    return m.group("pre") + out + m.group("post") + ("%" if pct else "")


class Resolver:
    """Values of a workbook's formula cells, computed from the workbook's own cells."""

    MAX_RANGE = 20000

    def __init__(self, book):
        self.book = book
        self.sheets = {ws.title: ws for ws in book.worksheets}
        self.order = [ws.title for ws in book.worksheets]
        self.cache = {}
        self.busy = set()
        self.names = {}
        try:
            for name, dn in getattr(book, "defined_names", {}).items():
                try:
                    dests = list(dn.destinations)
                except Exception:
                    continue
                if len(dests) == 1:
                    self.names[str(name).upper()] = dests[0]
        except Exception:
            pass

    # -- cell access -------------------------------------------------------- #
    def raw(self, sheet, coord):
        ws = self.sheets.get(sheet)
        if ws is None:
            return None
        try:
            return ws[coord].value
        except Exception:
            return None

    def value(self, sheet, coord, depth=0):
        """The value this cell shows.  A stored value is returned untouched."""
        key = (sheet, coord)
        if key in self.cache:
            return self.cache[key]
        raw = self.raw(sheet, coord)
        if not (isinstance(raw, str) and raw.startswith("=")):
            return raw                      # already readable: never re-evaluated
        if key in self.busy or depth > 48:
            return UNRESOLVED               # circular or too deep
        self.busy.add(key)
        try:
            out = self.eval_formula(raw, sheet, depth + 1)
        except Exception:
            out = UNRESOLVED
        finally:
            self.busy.discard(key)
        self.cache[key] = out
        return out

    def eval_formula(self, text, sheet, depth):
        body = text[1:].lstrip()
        if body.startswith("+"):
            body = body[1:]
        node = parse(body)
        return self.ev(node, sheet, depth)

    # -- ranges ------------------------------------------------------------- #
    def cells_of(self, node, sheet, depth):
        """A (sheet, coord) list for a cell or range node, else None."""
        if node[0] == "cell":
            return [(node[1] or sheet, node[2])]
        if node[0] == "range":
            sh = node[1] or sheet
            m1, m2 = A1.match(node[2]), A1.match(node[3])
            if not (m1 and m2):
                return None
            c1, r1 = col_index(m1.group(1)), int(m1.group(2))
            c2, r2 = col_index(m2.group(1)), int(m2.group(2))
            ws = self.sheets.get(sh)
            if ws is None:
                return None
            # a whole-column range ($J:$J) arrives with row 1..1048576; clip it
            # a whole-column ($J:$J) or whole-row (1:1) range arrives at the sheet
            # bounds; clip it to what the sheet actually uses.
            r1 = min(r1, max(ws.max_row, 1)); r2 = min(r2, max(ws.max_row, 1))
            c1 = min(c1, max(ws.max_column, 1)); c2 = min(c2, max(ws.max_column, 1))
            lo_r, hi_r = min(r1, r2), max(r1, r2)
            lo_c, hi_c = min(c1, c2), max(c1, c2)
            if (hi_r - lo_r + 1) * (hi_c - lo_c + 1) > self.MAX_RANGE:
                return None
            return [(sh, "%s%d" % (col_letters(c), r))
                    for r in range(lo_r, hi_r + 1) for c in range(lo_c, hi_c + 1)]
        if node[0] == "name":
            dest = self.names.get(node[1].upper())
            if dest:
                sh, coord = dest
                return self.cells_of(("cell", sh, coord.replace("$", "")), sheet, depth)
        return None

    def values_of(self, node, sheet, depth):
        cells = self.cells_of(node, sheet, depth)
        if cells is None:
            return None
        return [self.value(s, c, depth) for s, c in cells]

    def scalars(self, node, sheet, depth):
        """Flatten a node to a list of scalars (a range contributes every cell)."""
        vals = self.values_of(node, sheet, depth)
        if vals is not None:
            return vals
        return [self.ev(node, sheet, depth)]

    # -- evaluator ---------------------------------------------------------- #
    def ev(self, node, sheet, depth):
        kind = node[0]
        if kind == "num":
            return node[1]
        if kind == "str":
            return node[1]
        if kind == "bool":
            return node[1]
        if kind == "empty":
            return None
        if kind == "cell":
            return self.value(node[1] or sheet, node[2], depth)
        if kind == "range":
            vals = self.values_of(node, sheet, depth)
            if vals is None:
                return UNRESOLVED
            return vals[0] if len(vals) == 1 else UNRESOLVED
        if kind == "name":
            dest = self.names.get(node[1].upper())
            if not dest:
                return UNRESOLVED
            sh, coord = dest
            return self.value(sh, coord.replace("$", ""), depth)
        if kind == "neg":
            v = self.ev(node[1], sheet, depth)
            if v is UNRESOLVED or v is ERR:
                return v
            n = num_of(v)
            return ERR if n is ERR else -n
        if kind == "pct":
            v = self.ev(node[1], sheet, depth)
            if v is UNRESOLVED or v is ERR:
                return v
            n = num_of(v)
            return ERR if n is ERR else n / 100.0
        if kind == "cat":
            a = self.ev(node[1], sheet, depth); b = self.ev(node[2], sheet, depth)
            if UNRESOLVED in (a, b):
                return UNRESOLVED
            if ERR in (a, b):
                return ERR
            return text_of(a) + text_of(b)
        if kind == "bin":
            return self.arith(node, sheet, depth)
        if kind == "cmp":
            return self.compare(node, sheet, depth)
        if kind == "call":
            return self.call(node[1], node[2], sheet, depth)
        return UNRESOLVED

    def arith(self, node, sheet, depth):
        op = node[1]
        a = self.ev(node[2], sheet, depth); b = self.ev(node[3], sheet, depth)
        if UNRESOLVED in (a, b):
            return UNRESOLVED
        if ERR in (a, b):
            return ERR
        x, y = num_of(a), num_of(b)
        if x is ERR or y is ERR:
            return ERR
        try:
            if op == "+":
                return x + y
            if op == "-":
                return x - y
            if op == "*":
                return x * y
            if op == "/":
                return ERR if y == 0 else x / y
            if op == "^":
                return x ** y
        except Exception:
            return ERR
        return UNRESOLVED

    def compare(self, node, sheet, depth):
        """Excel comparison: numbers compare as numbers, text as text, and a number
        is always less than any text.  A numeric-looking STRING is text - Excel
        coerces text in arithmetic, not in comparison, so "0" = 0 is FALSE.  That
        distinction decides a real status: =IF(D16=0,...) against a D16 holding
        the string "0" answers FAIL.
        """
        op = node[1]
        a = self.ev(node[2], sheet, depth); b = self.ev(node[3], sheet, depth)
        if UNRESOLVED in (a, b):
            return UNRESOLVED
        if ERR in (a, b):
            return ERR

        def kind(v):
            if v is None:
                return "blank"
            if isinstance(v, bool):
                return "bool"
            if isinstance(v, (int, float)):
                return "num"
            return "text"

        ka, kb = kind(a), kind(b)
        if "blank" in (ka, kb):
            other = kb if ka == "blank" else ka
            if other == "text":
                ka = kb = "text"
                a = "" if ka == "text" and kind(a) == "blank" else a
                b = "" if kind(b) == "blank" else b
                a = a if a is not None else ""
                b = b if b is not None else ""
            elif other == "bool":
                a = False if kind(a) == "blank" else a
                b = False if kind(b) == "blank" else b
                ka = kb = "bool"
            else:
                a = 0.0 if kind(a) == "blank" else a
                b = 0.0 if kind(b) == "blank" else b
                ka = kb = "num"
        if ka == kb == "num":
            x, y = float(a), float(b)
        elif ka == kb == "text":
            x, y = str(a).upper(), str(b).upper()
        elif ka == kb == "bool":
            x, y = bool(a), bool(b)
        else:
            # mixed types never compare equal; Excel orders number < text < boolean
            rank = {"num": 0, "text": 1, "bool": 2}
            x, y = rank[ka], rank[kb]
        if op == "=":
            return x == y
        if op == "<>":
            return x != y
        try:
            return {"<": x < y, ">": x > y, "<=": x <= y, ">=": x >= y}[op]
        except TypeError:
            return ERR

    # -- functions ---------------------------------------------------------- #
    def call(self, fname, args, sheet, depth):
        ev = lambda i: self.ev(args[i], sheet, depth)

        if fname == "IF":
            cond = ev(0)
            if cond is UNRESOLVED:
                return UNRESOLVED
            if cond is ERR:
                return ERR
            truthy = bool(cond) if isinstance(cond, bool) else (num_of(cond) not in (0.0, ERR))
            if truthy:
                return ev(1) if len(args) > 1 else True
            return ev(2) if len(args) > 2 else False
        if fname == "IFERROR":
            v = ev(0)
            if v is UNRESOLVED:
                return UNRESOLVED
            return ev(1) if v is ERR else v
        if fname in ("AND", "OR"):
            vals = []
            for a in args:
                vals += self.scalars(a, sheet, depth)
            if any(v is UNRESOLVED for v in vals):
                return UNRESOLVED
            if any(v is ERR for v in vals):
                return ERR
            flags = [bool(v) if isinstance(v, bool) else (num_of(v) not in (0.0, ERR))
                     for v in vals if v is not None]
            return all(flags) if fname == "AND" else any(flags)
        if fname == "NOT":
            v = ev(0)
            if v is UNRESOLVED or v is ERR:
                return v
            return not (bool(v) if isinstance(v, bool) else num_of(v) not in (0.0, ERR))
        if fname == "ISNUMBER":
            v = ev(0)
            if v is UNRESOLVED:
                return UNRESOLVED
            return isinstance(v, (int, float)) and not isinstance(v, bool)
        if fname in ("ISBLANK",):
            v = ev(0)
            return UNRESOLVED if v is UNRESOLVED else (v is None)
        if fname == "ISTEXT":
            v = ev(0)
            return UNRESOLVED if v is UNRESOLVED else isinstance(v, str)
        if fname == "PI":
            return math.pi
        if fname == "HYPERLINK":
            v = ev(1) if len(args) > 1 else ev(0)
            return v
        if fname == "TEXT":
            v = ev(0)
            if v is UNRESOLVED:
                return UNRESOLVED
            if v is ERR:
                return ERR
            fmt = ev(1) if len(args) > 1 else None
            return apply_number_format(v, fmt)

        # -- aggregates over ranges ---------------------------------------- #
        if fname in ("SUM", "MIN", "MAX", "AVERAGE", "COUNT", "COUNTA", "COUNTBLANK", "PRODUCT"):
            vals = []
            for a in args:
                vals += self.scalars(a, sheet, depth)
            if any(v is UNRESOLVED for v in vals):
                return UNRESOLVED
            if fname == "COUNTA":
                return float(sum(1 for v in vals if v is not None and v != ""))
            if fname == "COUNTBLANK":
                return float(sum(1 for v in vals if v is None or (v is not ERR and v == "")))
            if any(v is ERR for v in vals):
                # MIN/SUM/MAX over a range holding an error IS that error in Excel;
                # dropping it silently would turn #VALUE! shear candidates into a
                # governing Vc the workbook does not have.
                if fname not in ("COUNT", "COUNTA", "COUNTBLANK"):
                    return ERR
            nums = [num_of(v) for v in vals
                    if v is not None and v != "" and not isinstance(v, bool) and v is not ERR]
            nums = [n for n in nums if n is not ERR]
            if fname == "COUNT":
                return float(len(nums))
            if not nums:
                return 0.0 if fname in ("SUM", "PRODUCT") else 0.0
            if fname == "SUM":
                return float(sum(nums))
            if fname == "MIN":
                return float(min(nums))
            if fname == "MAX":
                return float(max(nums))
            if fname == "AVERAGE":
                return float(sum(nums) / len(nums))
            if fname == "PRODUCT":
                p = 1.0
                for n in nums:
                    p *= n
                return p
        if fname in ("COUNTIF", "COUNTIFS", "SUMIF", "SUMIFS"):
            return self.countifs(fname, args, sheet, depth)
        if fname == "SUMPRODUCT":
            cols = [self.scalars(a, sheet, depth) for a in args]
            if any(v is UNRESOLVED for col in cols for v in col):
                return UNRESOLVED
            if not cols or len({len(c) for c in cols}) != 1:
                return UNRESOLVED
            total = 0.0
            for row in zip(*cols):
                p = 1.0
                for v in row:
                    n = num_of(v)
                    p *= 0.0 if n is ERR else n
                total += p
            return total

        # -- scalar maths --------------------------------------------------- #
        if fname in ("ABS", "SQRT", "INT", "ROUND", "ROUNDDOWN", "ROUNDUP", "FLOOR",
                     "CEILING", "LN", "LOG10", "EXP", "TRUNC", "SIGN", "POWER", "MOD"):
            vals = [ev(i) for i in range(len(args))]
            if any(v is UNRESOLVED for v in vals):
                return UNRESOLVED
            if any(v is ERR for v in vals):
                return ERR
            nums = [num_of(v) for v in vals]
            if any(n is ERR for n in nums):
                return ERR
            x = nums[0]
            try:
                if fname == "ABS":
                    return abs(x)
                if fname == "SQRT":
                    return ERR if x < 0 else math.sqrt(x)
                if fname == "INT":
                    return float(math.floor(x))
                if fname == "TRUNC":
                    return float(math.trunc(x))
                if fname == "SIGN":
                    return float((x > 0) - (x < 0))
                if fname == "LN":
                    return math.log(x)
                if fname == "LOG10":
                    return math.log10(x)
                if fname == "EXP":
                    return math.exp(x)
                if fname == "POWER":
                    return x ** nums[1]
                if fname == "MOD":
                    return math.fmod(x, nums[1]) if nums[1] else ERR
                if fname in ("ROUND", "ROUNDDOWN", "ROUNDUP"):
                    d = int(nums[1]) if len(nums) > 1 else 0
                    f = 10.0 ** d
                    if fname == "ROUND":
                        return math.floor(abs(x) * f + 0.5) / f * (1 if x >= 0 else -1)
                    if fname == "ROUNDDOWN":
                        return math.floor(abs(x) * f) / f * (1 if x >= 0 else -1)
                    return math.ceil(abs(x) * f) / f * (1 if x >= 0 else -1)
                if fname in ("FLOOR", "CEILING"):
                    step = nums[1] if len(nums) > 1 else 1.0
                    if step == 0:
                        return ERR
                    q = x / step
                    return (math.floor(q) if fname == "FLOOR" else math.ceil(q)) * step
            except Exception:
                return ERR
        if fname in ("SEARCH", "FIND"):
            vals = [ev(i) for i in range(min(2, len(args)))]
            if any(v is UNRESOLVED for v in vals):
                return UNRESOLVED
            needle, hay = text_of(vals[0]), text_of(vals[1])
            if fname == "SEARCH":
                needle, hay = needle.upper(), hay.upper()
            pos = hay.find(needle)
            return ERR if pos < 0 else float(pos + 1)
        return UNRESOLVED

    def countifs(self, fname, args, sheet, depth):
        summing = fname in ("SUMIF", "SUMIFS")
        if fname == "COUNTIF":
            pairs = [(args[0], args[1])]
            total_src = None
        elif fname == "COUNTIFS":
            pairs = [(args[i], args[i + 1]) for i in range(0, len(args) - 1, 2)]
            total_src = None
        elif fname == "SUMIF":
            pairs = [(args[0], args[1])]
            total_src = args[2] if len(args) > 2 else args[0]
        else:
            total_src = args[0]
            pairs = [(args[i], args[i + 1]) for i in range(1, len(args) - 1, 2)]
        cols, crits = [], []
        for rng, crit in pairs:
            vals = self.values_of(rng, sheet, depth)
            if vals is None:
                return UNRESOLVED
            c = self.ev(crit, sheet, depth)
            if c is UNRESOLVED:
                return UNRESOLVED
            cols.append(vals); crits.append(c)
        if any(v is UNRESOLVED for col in cols for v in col):
            return UNRESOLVED
        if len({len(c) for c in cols}) != 1:
            return UNRESOLVED
        totals = None
        if summing:
            totals = self.values_of(total_src, sheet, depth)
            if totals is None or len(totals) != len(cols[0]):
                return UNRESOLVED
        out = 0.0
        for i in range(len(cols[0])):
            if all(match_criteria(cols[j][i], crits[j]) for j in range(len(cols))):
                if summing:
                    n = num_of(totals[i])
                    out += 0.0 if n is ERR else n
                else:
                    out += 1.0
        return out


# A cell may begin with "=" and not be a formula at all: "= 0.90 x 5122.69." may
# be typed as a note, and a formula-lineage sheet may print "=D6" in its "Formula"
# column as documentation.  The file itself records which
# is which (data_type "f"), so that is the test; the "=" prefix is not.
def is_formula_cell(cell):
    return cell.data_type == "f" and isinstance(cell.value, str) and cell.value.startswith("=")


def resolved_map(book, stats=None):
    """{(sheet, coord): value} for every formula cell this resolver can decide."""
    r = Resolver(book)
    out = {}
    n_formula = n_prose = n_err = 0
    for ws in book.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                v = cell.value
                if not (isinstance(v, str) and v.startswith("=")):
                    continue
                if not is_formula_cell(cell):
                    n_prose += 1
                    continue
                n_formula += 1
                got = r.value(ws.title, cell.coordinate)
                if got is UNRESOLVED:
                    continue
                if got is ERR:
                    n_err += 1
                    continue
                out[(ws.title, cell.coordinate)] = got
    if stats is not None:
        stats.update(formulas=n_formula, prose=n_prose, errors=n_err, resolved=len(out))
    return out


# The resolved values of the workbook being scored: {(sheet, coord): value}.
SHOWN = {}


def install_resolver(book):
    global SHOWN
    try:
        SHOWN = resolved_map(book)
    except Exception:
        SHOWN = {}


def shown(ws_title, cell):
    """What the workbook shows in this cell.

    A stored value is returned as it stands.  A formula is returned as its resolved
    value, or as None when the resolver declines it - a cell whose value cannot be
    decided (including one that evaluates to an Excel error) publishes nothing
    readable, so its source text is not read in its place.
    """
    v = cell.value
    if cell.data_type == "f" and isinstance(v, str) and v.startswith("="):
        return SHOWN.get((ws_title, cell.coordinate))
    return v


HERE = Path(__file__).resolve().parent
PARAMS = Path(os.environ.get("SCORING_PARAMS", HERE / "scoring_params.json"))
GROUND = json.loads((HERE / "ground_truth.json").read_text(encoding="utf-8"))

STATUS = {"PASS", "FAIL", "REVIEW"}
STATUS_CELL_CHARS = 40
# A row label is short; past this a cell is a sentence, i.e. commentary.
LABEL_CELL_CHARS = 80
# Front matter: a cover, read-me, legend, control or index page states the review's
# scope and its controlled vocabulary.  It is not where a check's verdict is
# published, so the wording fallback does not look there.
FRONT_MATTER = ("readme", "cover", "titlepage", "control", "legend",
                "index", "contents", "instructions", "about")
OPEN = {"FAIL", "REVIEW"}

def norm(x):
    return re.sub(r"[^a-z0-9]+", "", str(x or "").lower())

def num(x):
    if isinstance(x, bool): return None
    if isinstance(x, (int, float)): return float(x)
    if isinstance(x, str):
        m = re.search(r"[-+]?\d+(?:\.\d+)?", x.replace(",", ""))
        return float(m.group(0)) if m else None
    return None

# RUBRIC: "status checks accept leading controlled terms and equivalent professional
# qualifiers". A register may declare its own controlled
# vocabulary on a legend row - "PASS / FAIL / OPEN / INFO", or "Verified - conforms
# / Qualified - conforms with comment / Non-conformance / Open - information
# required / Not verifiable from supplied materials" - and enforce it with list
# validation. Those are the same three decisions in professional wording: the
# requirement is met, the requirement is not met, or the evidence does not license a
# conclusion. Reading only the bare tokens makes a whole register invisible, which
# is not a presentation tolerance the rubric claims.
REVIEW_TERMS = re.compile(r"^(REVIEW|HOLD|OPEN|PENDING|OUTSTANDING|UNRESOLVED|"
                          r"NOT[ _-]?VERIF|UNVERIF|INDETERMIN|INCONCLUS)")
FAIL_TERMS = re.compile(r"^(FAIL|REJECT|NON[ _-]?CONFORM|NONCOMPLIAN|NON[ _-]?COMPLIAN)")
PASS_TERMS = re.compile(r"^(PASS|OK|ACCEPT|CONFORM|VERIFIED)")


def leading_status(x):
    t = str(x or "").strip().upper()
    if not t: return None
    if REVIEW_TERMS.match(t) or "UNDECID" in t: return "REVIEW"
    if FAIL_TERMS.match(t): return "FAIL"
    if PASS_TERMS.match(t): return "PASS"
    if t.startswith("NOT "): return "FAIL"
    # A controlled status is a short label, not a sentence.  Every status reader in
    # this file caps a status cell at 40 characters, so a sheet subtitle ("... -
    # source-bound review only") or a concise-conclusion paragraph cannot publish a
    # REVIEW verdict for a check the register decides elsewhere.
    if len(t) > STATUS_CELL_CHARS: return None
    # "Verified - conforms", "Qualified - conforms with comment": the qualifier
    # leads, the decision follows. A negated form is caught by FAIL_TERMS above.
    if re.search(r"\bCONFORMS?\b", t) and not re.search(r"\bNON[ _-]?CONFORM", t): return "PASS"
    for s in ("REVIEW", "FAIL", "PASS"):
        if s in t: return s
    return None

def exact_status(x):
    """A cell that IS a controlled status, not a label that merely contains one."""
    if not isinstance(x, str) or x.startswith("="): return None
    t = x.strip().upper()
    return t if t in STATUS else None

def rows(ws):
    """Every row as the workbook shows it, formulas resolved."""
    return [[shown(ws.title, c) for c in r] for r in ws.iter_rows()]


def raw_rows(ws):
    """Every row as written: a formula cell keeps its formula text."""
    return [[c.value for c in r] for r in ws.iter_rows()]


def has_formula(row):
    return any(isinstance(c, str) and c.startswith("=") for c in row)

def find_sheet(wb, aliases):
    """Find a calculation sheet by title or by its declared column/content role.

    Workbook tab names are presentation choices.  A reviewer may call the load
    sheet ``Loads`` or ``Gravity actions`` while retaining the same quantities;
    relying on a short alias here made an otherwise valid workbook score as if
    the calculation were absent.  Title aliases still win, then a conservative
    signature match is used for the three calculation roles.
    """
    for ws in wb.worksheets:
        n = norm(ws.title)
        if any(a in n or n in a for a in aliases): return ws
    # Flatten only the small header/label prefix.  Values and prose later in a
    # workbook are deliberately ignored so a summary page cannot impersonate a
    # calculation sheet merely by mentioning its result.
    sigs = {
        "load": ("dead_factor", "live_factor", "w_u", "m_u_calc", "v_at_d", "gravity", "load combination"),
        "flex": ("neutral axis", "compression steel", "tension strain", "nominal moment", "phimn", "equilibrium"),
        "shear": ("vc candidate", "trial spacing", "adopted spacing", "vs", "vn", "effective depth", "shear"),
    }
    def role_for(requested):
        joined = " ".join(norm(a) for a in aliases)
        if any(k in joined for k in ("load", "action")): return "load"
        if any(k in joined for k in ("flex", "moment", "bend")): return "flex"
        if any(k in joined for k in ("shear", "stirrup")): return "shear"
        return None
    role = role_for(aliases)
    if role is None: return None
    scored = []
    for ws in wb.worksheets:
        text = []
        for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 12)):
            for cell in row:
                if cell.value is not None:
                    text.append(norm(str(cell.value)))
        joined = " ".join(text)
        hits = sum(1 for token in sigs[role] if norm(token) in joined)
        # Require at least two independent role signals.  This permits renamed
        # tabs while preventing a generic cover/summary page from being selected.
        if hits >= 2:
            scored.append((hits, -wb.worksheets.index(ws), ws))
    if scored:
        scored.sort(reverse=True)
        return scored[0][2]
    return None

# --------------------------------------------------------------------------
# Reading the evidence ledger.
#
# The request asks for "the input evidence" with "traceable evidence locations";
# it does not prescribe a tab name, a column order, a row label vocabulary or a
# unit system. The reference solution happens to key its ledger on the
# verifier's own field names in column A, but a reviewer who writes a Symbol
# column with d' , f'c and A's, keeps the source value in ksi beside a
# normalised value in psi, or puts the locator in column J is delivering the
# same evidence. This reader therefore:
#   * accepts any tab whose title reads as an input / evidence register;
#   * finds the value, unit, state, locator and quote columns from the header
#     row instead of assuming A..F;
#   * identifies a row by its exact field name first, then by an alias, then by
#     the engineering symbol or quantity name written anywhere in its label
#     cells;
#   * converts the number to the unit the calculation chain works in, using the
#     unit the row itself declares.
# It does not guess: a row that names no recognisable quantity is skipped, and a
# value carrying no usable unit is taken at face value only when the field has
# no alternative unit.
# --------------------------------------------------------------------------

EVIDENCE_TITLES = ("sourceinput", "input", "evidence", "inventory", "register", "ledger", "data")

UNIT_CANON = {"span": "ft", "h": "in", "bw": "in", "d_flexure": "in", "d_shear": "in", "d_prime": "in",
              "s_trial": "in", "s_adopted": "in", "smax_reported": "in", "c_solution": "in",
              "fc": "psi", "fy": "psi", "fyt": "psi", "Es": "psi",
              "dead_load": "kip/ft", "live_load": "kip/ft",
              "Mu_reported": "kip-in", "Mn_reported": "kip-in", "phiMn_reported": "kip-in",
              "Vu_reported": "kip", "Vc_a_reported": "kip", "Vc_b_reported": "kip", "Vc_c_reported": "kip",
              "Vs_trial_reported": "kip", "Vs_adopted_reported": "kip", "Vn_adopted_reported": "kip",
              "Vn_max_reported": "kip", "Vn_max_source_reported": "kip",
              "As_tension": "in2", "As_comp": "in2", "As_required_reported": "in2", "Av": "in2"}

UNIT_ALIASES = {
    "in": "in", "inch": "in", "inches": "in", "": "", "-": "", "—": "",
    "ft": "ft", "feet": "ft", "foot": "ft",
    "psi": "psi", "lb/in2": "psi", "lbf/in2": "psi", "ksi": "ksi", "kip/in2": "ksi",
    "kip": "kip", "kips": "kip", "k": "kip", "lb": "lb", "lbs": "lb", "pound": "lb",
    "kipft": "kip-ft", "kip-ft": "kip-ft", "kipft.": "kip-ft", "k-ft": "kip-ft",
    "kipin": "kip-in", "kip-in": "kip-in", "k-in": "kip-in", "kip*in": "kip-in",
    "lb-in": "lb-in", "lbin": "lb-in",
    "in2": "in2", "in^2": "in2", "sq in": "in2", "in²": "in2",
    "kip/ft": "kip/ft", "k/ft": "kip/ft", "kips/ft": "kip/ft", "lb/ft": "lb/ft",
    "in/in": "", "strain": "", "unitless": "", "none": "", "dimensionless": "",
}
UNIT_SCALE = {("ksi", "psi"): 1000.0, ("psi", "ksi"): .001, ("ft", "in"): 12.0, ("in", "ft"): 1 / 12.0,
              ("kip", "lb"): 1000.0, ("lb", "kip"): .001,
              ("kip-ft", "kip-in"): 12.0, ("kip-in", "kip-ft"): 1 / 12.0,
              ("lb-in", "kip-in"): .001, ("kip-in", "lb-in"): 1000.0,
              ("lb/ft", "kip/ft"): .001, ("kip/ft", "lb/ft"): 1000.0}


def unit_of(text):
    t = re.sub(r"\s+", "", str(text or "")).lower().replace("（", "(").strip()
    t = re.sub(r"^\((.*)\)$", r"\1", t)
    return UNIT_ALIASES.get(t)


def convert(value, from_unit, to_unit):
    """None when the declared unit cannot be reconciled with the one needed."""
    if value is None: return None
    if not to_unit: return value
    if from_unit is None: return value          # nothing declared: take at face value
    if from_unit == to_unit: return value
    scale = UNIT_SCALE.get((from_unit, to_unit))
    return None if scale is None else value * scale


# One entry per field: patterns that must hit, patterns that must not.
FIELD_PATTERNS = {
 "span":        ([r"\bspan\b"], [r"effective|clear cover"]),
 "h":           ([r"overall depth", r"total depth", r"\bh\b.*depth", r"^h$", r"\bh\b.{0,4}overall", r"overall.*section"], [r"effective", r"web", r"flange"]),
 "bw":          ([r"\bbw\b", r"web width", r"beam width", r"^b$", r"\bwidth\b"], [r"crack|flange"]),
 "d_flexure":   ([r"(effective depth|^d$|\bd\b).{0,40}(flexur|moment|bending|tension steel)",
                  r"(flexur|moment|bending).{0,40}(effective depth|\bd\b)"], [r"shear|d'|prime|compression"]),
 "d_shear":     ([r"(effective depth|\bd\b).{0,40}shear", r"shear.{0,40}(effective depth|\bd\b)"], [r"flexur|d'|prime"]),
 "d_prime":     ([r"d'", r"d prime", r"dprime", r"compression steel depth",
                  r"(centroid|depth).{0,30}compression"], []),
 "fc":          ([r"f'c", r"\bfc\b", r"concrete.{0,20}(compress|strength)"], [r"strain|sqrt|root|beta"]),
 "fy":          ([r"\bfy\b", r"yield strength", r"yield stress"], [r"\bfyt\b|stirrup|transverse|shear|strain"]),
 "fyt":         ([r"\bfyt\b", r"yield.{0,25}(stirrup|transverse|shear)", r"(stirrup|transverse|shear).{0,25}yield"], []),
 "Es":          ([r"\bes\b", r"modulus of elasticity", r"elastic modulus", r"steel modulus", r"young"], []),
 "epscu":       ([r"eps.?cu", r"\becu\b", r"ultimate concrete strain", r"concrete.{0,20}strain"], [r"tension|tensile|steel"]),
 "beta1":       ([r"beta.?1", r"β1", r"stress block factor"], []),
 "As_comp":     ([r"a'\s?s\b", r"\ba's\b", r"compression.{0,25}(steel|reinforc).{0,25}area",
                  r"compression reinforcement.{0,20}area", r"^compression reinforcement$"],
                 [r"requir", r"ratio", r"rho", r"depth", r"centroid"]),
 "As_tension":  ([r"\bas\b.{0,40}(tension|tensile).{0,25}provid", r"(tension|tensile).{0,30}(steel|reinforc).{0,25}provid",
                  r"provided.{0,25}(tension|tensile)", r"\bas\b.{0,20}(tension|tensile)",
                  r"(tension|tensile).{0,20}steel.{0,15}area.{0,10}\bas\b",
                  r"(tension|tensile).{0,20}steel.{0,15}\bas\b.{0,10}area"],
                 [r"requir|minimum|min\b|compression|a's|ratio|rho|depth|centroid"]),
 "As_required_reported": ([r"(requir|minimum|min).{0,30}(tension|tensile|reinforc|\bas\b)",
                           r"\bas\b.{0,25}(requir|minimum)"], [r"provid|shear|stirrup|\bav\b"]),
 "Av":          ([r"\bav\b", r"shear reinforcement.{0,25}area", r"stirrup.{0,25}area"], [r"/s|per|ratio|requir"]),
 "dead_load":   ([r"dead load", r"dead.{0,20}line load", r"unfactored.{0,25}dead.{0,15}load", r"\bd\b.{0,20}dead"], [r"load factor", r"combination"]),
 "live_load":   ([r"live load", r"\bl\b.{0,20}live"], [r"load factor", r"combination", r"roof"]),
 "dead_factor": ([r"dead.{0,15}(?<!un)factor", r"(?<!un)factor.{0,15}dead", r"1\.2.{0,25}dead"], [r"unfactored"]),
 "live_factor": ([r"live.{0,15}(?<!un)factor", r"(?<!un)factor.{0,15}live", r"1\.6.{0,25}live"], [r"unfactored"]),
 "phi_flex":    ([r"phi.{0,25}(flexur|moment|bending)", r"(flexur|moment|bending).{0,25}phi",
                  r"φ.{0,25}(flexur|moment)", r"strength reduction.{0,25}(flexur|moment)"], [r"mn|shear"]),
 "phi_shear":   ([r"phi.{0,25}shear", r"shear.{0,25}phi", r"φ.{0,25}shear",
                  r"strength reduction.{0,25}shear"], [r"\bvn\b|\bvc\b"]),
 "Mu_reported": ([r"\bmu\b", r"flexur(?:al|e).{0,20}(demand|action)", r"(demand|action).{0,20}flexur"], [r"critical section|at d\b|phi|\bmn\b|delta|ratio"]),
 "Vu_reported": ([r"\bvu\b"], [r"phi|\bvn\b|\bvc\b|\bvs\b|ratio|delta"]),
 "Mn_reported": ([r"\bmn\b"], [r"phi|φ|requir|design"]),
 "phiMn_reported": ([r"phi.?\*?\s?mn", r"φmn", r"design flexural strength"], []),
 "eps_t_reported": ([r"eps.?t\b", r"εt", r"tension strain", r"tensile strain", r"net strain"], [r"concrete|cu"]),
 "c_solution":  ([r"neutral axis", r"\bc.?na\b", r"\bc\b.{0,25}neutral"], [r"block|^a\b"]),
 "Vc_a_reported": ([r"vc.?[-_ ]?a\b", r"vc.{0,12}\(a\)", r"22\.5\.5\.1a"], []),
 "Vc_b_reported": ([r"vc.?[-_ ]?b\b", r"vc.{0,12}\(b\)", r"22\.5\.5\.1b"], []),
 "Vc_c_reported": ([r"vc.?[-_ ]?c\b", r"vc.{0,12}\(c\)", r"22\.5\.5\.1c"], []),
 "Vs_trial_reported": ([r"vs.{0,30}(trial|s ?= ?14|14 in)", r"(trial|14 in).{0,30}vs"], [r"requir|demand|adopt"]),
 "Vs_adopted_reported": ([r"vs.{0,30}(adopt|s ?= ?11|11 in)", r"(adopt|11 in).{0,30}vs"], [r"requir|demand|trial"]),
 "Vn_adopted_reported": ([r"(phi.?\*?\s?)?vn.{0,30}(adopt|s ?= ?11|11 in)", r"(adopt|11 in).{0,30}vn"], [r"max|ceiling|trial"]),
 "Vn_max_reported": ([r"independent.{0,20}(section|shear).{0,20}(ceiling|capacity|limit)", r"22\.5\.1\.2", r"ceiling", r"vn.?max", r"max.{0,20}vn", r"section.{0,20}(capacity|limit)"], [r"source|article.{0,20}print"]),
 "Vn_max_source_reported": ([r"source.{0,20}(section|shear).{0,20}(ceiling|capacity|limit)", r"article.{0,20}(print|reports?).{0,20}(105\.04|ceiling)", r"printed.{0,20}(section|shear).{0,20}(ceiling|capacity|limit)"], []),
 "s_trial":     ([r"trial.{0,20}spacing", r"spacing.{0,20}trial", r"\bs\b.{0,15}trial"], [r"vs\b|max|adopt|theor"]),
 "s_adopted":   ([r"adopt.{0,20}spacing", r"spacing.{0,20}adopt", r"\bs\b.{0,15}adopt"], [r"vs\b|max|trial"]),
 "smax_reported": ([r"s.?max", r"maximum.{0,25}spacing", r"spacing.{0,25}(maximum|ceiling|limit)"],
                   [r"trial|theor|vs\b|adopt"]),
}
LABEL_STOP = re.compile(r"locator|quote|verbatim|note|interpret|rationale|conversion|state|category|"
                        r"reference|source|status|id\b|basis|evidence", re.I)
VALUE_HEAD = re.compile(r"value|result|magnitude|quantity value|number", re.I)
UNIT_HEAD = re.compile(r"\bunit", re.I)
LOC_HEAD = re.compile(r"locator|location|source|reference|evidence|locus|clause", re.I)
QUOTE_HEAD = re.compile(r"quote|verbatim|text relied|excerpt", re.I)
STATE_HEAD = re.compile(r"state|basis|status|condition", re.I)


def label_text(row, skip_cols, limit=90):
    parts = []
    for i, v in enumerate(row):
        if i in skip_cols or v is None: continue
        if isinstance(v, str):
            if v.startswith("=") or len(v) > limit: continue
            parts.append(v)
    return re.sub(r"\s+", " ", " ".join(parts).lower())


# Fields are resolved in this order so that a broad symbol cannot steal a row a
# more specific one owns (h before d', fy before Es, the required area before the
# provided one).
FIELD_ORDER = ["h", "bw", "span", "d_prime", "d_shear", "d_flexure",
               "fc", "fy", "fyt", "Es", "epscu", "beta1",
               "As_comp", "As_required_reported", "As_tension", "Av",
               "dead_factor", "live_factor", "dead_load", "live_load",
               "phi_flex", "phi_shear", "Mu_reported", "Vu_reported",
               "phiMn_reported", "Mn_reported", "eps_t_reported", "c_solution",
               "Vc_a_reported", "Vc_b_reported", "Vc_c_reported",
               "Vs_trial_reported", "Vs_adopted_reported", "Vn_adopted_reported", "Vn_max_reported",
               "Vn_max_source_reported",
               "smax_reported", "s_trial", "s_adopted"]


def header_roles(rws):
    """(header index, {role: [col,...]}) from the first row that names columns."""
    best = (None, {})
    for i, r in enumerate(rws[:8]):
        roles = {}
        for c, v in enumerate(r):
            if not isinstance(v, str) or not v.strip(): continue
            for role, pat in (("value", VALUE_HEAD), ("unit", UNIT_HEAD), ("loc", LOC_HEAD),
                              ("quote", QUOTE_HEAD), ("state", STATE_HEAD)):
                if pat.search(v): roles.setdefault(role, []).append(c)
        if len(roles) > len(best[1]): best = (i, roles)
    return best


def evidence_sheets(wb):
    out = [ws for ws in wb.worksheets if any(a in norm(ws.title) for a in EVIDENCE_TITLES)]
    return out or ([wb.worksheets[0]] if wb.worksheets else [])


def input_rows(ws_or_list):
    """{field: record} resolved from one or more evidence registers."""
    sheets = ws_or_list if isinstance(ws_or_list, list) else ([ws_or_list] if ws_or_list is not None else [])
    entries = []
    for ws in sheets:
        rws = rows(ws)
        hdr, roles = header_roles(rws)
        skip = set(sum(roles.values(), []))
        # Columns whose header says they hold commentary, provenance or an id are
        # not where a quantity is named; they are read only as a fallback.
        wide_skip = set(skip)
        if hdr is not None:
            for c, v in enumerate(rws[hdr]):
                if isinstance(v, str) and LABEL_STOP.search(v): wide_skip.add(c)
        for i, r in enumerate(rws, start=1):
            if hdr is not None and i <= hdr + 1: continue
            if not r or all(x in (None, "") for x in r): continue
            text = label_text(r, skip)
            key = label_text(r, wide_skip, limit=60)
            if not text: continue
            pairs = []
            for c, v in enumerate(r):
                if roles.get("value") and c not in roles["value"]:
                    continue
                n = num(v) if not isinstance(v, str) or not v.startswith("=") else None
                if n is None: continue
                if isinstance(v, str) and not re.fullmatch(r"\s*[-+]?[\d,]*\.?\d+\s*", v): continue
                u = None
                for cc in roles.get("unit", []):
                    if cc > c and (u is None):
                        u = unit_of(r[cc]) if cc < len(r) else None
                if u is None:
                    for cc in (c + 1, c + 2):
                        if cc < len(r) and isinstance(r[cc], str):
                            u = unit_of(r[cc])
                            if u is not None: break
                pairs.append((n, u))
            pick = lambda cols: next((str(r[c]) for c in cols if c < len(r) and str(r[c] or "").strip()), "")
            entries.append({"sheet": ws.title, "row": i, "text": text, "key": key, "pairs": pairs, "raw": r,
                            "unit": pick(roles.get("unit", [2])), "state": pick(roles.get("state", [3])),
                            "loc": pick(roles.get("loc", [4])), "quote": pick(roles.get("quote", [5])),
                            "label": norm(r[0] if r else "")})
    return entries


ALIASES = {
    "astension": ["asprovided", "tensionsteel", "astensionprovided"],
    "ascomp": ["ascompression", "compressionsteel"],
    "dflexure": ["dflex", "effectiveflexuraldepth"],
    "dshear": ["dshear", "sheareffectivedepth"],
    "bw": ["width", "beamwidth"], "fc": ["fcprime", "concretestrength"], "fy": ["fybar", "steelstrength"],
    "mureported": ["mu", "designmoment"], "vureported": ["vu", "designshear"],
}


def resolve_inputs(entries):
    """{field: record}. Exact label first, then alias, then symbol/name patterns."""
    out = {}
    by_label = {}
    for e in entries:
        by_label.setdefault(e["label"], e)
    for field in UNIT_CANON.keys() | set(FIELD_PATTERNS) | {"phi_flex", "phi_shear", "beta1", "epscu", "Es",
                                                            "dead_factor", "live_factor"}:
        k = norm(field)
        hit = by_label.get(k)
        if hit is None:
            for a in ALIASES.get(k, []):
                if a in by_label: hit = by_label[a]; break
        if hit is not None:
            out[field] = hit
    taken = {(e["sheet"], e["row"]) for e in out.values()}
    # Pass 1 reads only the naming columns; pass 2 falls back to the whole row for
    # registers that name the quantity in a note instead of a symbol column.
    for source in ("key", "text"):
        for field in FIELD_ORDER:
            if field in out: continue
            pos, neg = FIELD_PATTERNS[field]
            for e in entries:
                if not e["pairs"] or (e["sheet"], e["row"]) in taken: continue
                t = e[source]
                if not t: continue
                # The exclusions exist so two neighbouring quantities cannot steal
                # each other's row (the flexural depth and the shear depth, the
                # required area and the provided one). They are read against where
                # the row names its own subject: a shear-depth row whose note says
                # it "differs from flexure branch" is still the shear depth, and
                # rejecting it loses the quantity altogether. An exclusion therefore
                # disqualifies the row only when it appears at or before the name.
                at_pos = min((m.start() for p in pos for m in [re.search(p, t)] if m), default=None)
                if at_pos is None: continue
                at_neg = min((m.start() for n in neg if n for m in [re.search(n, t)] if m), default=None)
                if at_neg is not None and at_neg <= at_pos: continue
                if True:
                    # A row whose label reads like the field but whose own declared
                    # unit cannot carry that quantity is not that field: "required
                    # factored shear at section d" in kip is the shear demand, not
                    # the shear effective depth. Binding it anyway consumes the row
                    # the real quantity would have used, so the quantity is lost.
                    if source == "key" and field_value(field, e) is None: continue
                    out[field] = e
                    taken.add((e["sheet"], e["row"]))
                    break
    # The maximum permitted stirrup spacing is a governing minimum, not a single
    # printed number: the article writes it as "smax = min(24 in, d/2)" and reports
    # the governing value ("the maximum shear spacing is determined to be 11.25
    # inches"). A ledger that also records the 24 in operand, or a separate
    # strength-derived spacing, must not have one of those read as the limit, so the
    # smallest candidate governs - the same rule governing_vc() already applies to
    # the three concrete-shear candidates.
    # Table 5.3.1 carries two gravity combinations and a ledger may record both:
    # "Eq. 5.3.1a - dead factor 1.4" beside "Eq. 5.3.1b - dead factor 1.2". Taking
    # whichever row comes first would read 1.4 as the governing dead factor, and the
    # workbook's own numbers would then not reproduce its reported moment. The
    # gravity combination that governs a beam carrying both dead and live load is the
    # one that carries both terms, so a factor row whose own text quotes a
    # dead-and-live combination outranks one quoting the dead-only case.
    COMBINED = re.compile(r"\+\s*[0-9.]*\s*l\b|1\.6\s*l\b|d\s*\+\s*[0-9.]*\s*l|5\.3\.1b", re.I)
    DEAD_ONLY = re.compile(r"1\.4\s*d\b|5\.3\.1a|dead[- ]only", re.I)
    for field in ("dead_factor", "live_factor"):
        pos, neg = FIELD_PATTERNS[field]
        chosen = out.get(field)
        if chosen is None: continue
        chosen_text = " ".join(str(x) for x in chosen["raw"] if x is not None)
        if COMBINED.search(chosen_text) and not DEAD_ONLY.search(chosen_text): continue
        for e in entries:
            if not e["pairs"]: continue
            t = e["key"] or e["text"]
            if not t or any(re.search(n, t) for n in neg if n): continue
            if not any(re.search(pat, t) for pat in pos): continue
            row_text = " ".join(str(x) for x in e["raw"] if x is not None)
            if COMBINED.search(row_text) and not DEAD_ONLY.search(row_text):
                out[field] = e
                break

    spos, sneg = FIELD_PATTERNS["smax_reported"]
    for source in ("key", "text"):
        cands = []
        for e in entries:
            if not e["pairs"]: continue
            t = e[source]
            if not t or any(re.search(n, t) for n in sneg if n): continue
            if not any(re.search(p, t) for p in spos): continue
            v = field_value("smax_reported", e)
            if v is not None and v > 0: cands.append((v, e))
        if cands:
            out["smax_reported"] = min(cands, key=lambda x: x[0])[1]
            break
    return out


def field_value(field, record):
    if record is None: return None
    want = UNIT_CANON.get(field, "")
    best = None
    for value, unit in record.get("pairs", []):
        converted = convert(value, unit, want)
        if converted is None: continue
        if best is None: best = converted
    return best


def get_input(inp, field):
    rec = inp.get(field) if isinstance(inp, dict) else None
    if rec is None: return None
    return {"raw": rec["raw"], "value": field_value(field, rec), "unit": rec["unit"],
            "state": rec["state"], "loc": rec["loc"], "quote": rec["quote"], "row": rec["row"],
            "sheet": rec["sheet"]}

def all_formula_cells(wb):
    out=[]
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith("="):
                    out.append((ws.title, c.coordinate, c.value))
    return out

def rel(a, b):
    if a is None or b is None or b == 0: return 0.0
    return abs(a-b)/abs(b)

def agrees(a, b, tol):
    """A missing number is not a match. rel() returns 0.0 for None, so comparing it
    against a tolerance would score an empty cell as a perfect agreement."""
    if a is None or b is None or b == 0: return False
    return abs(a-b)/abs(b) <= tol

def populated_rows(rws):
    """Rows carrying something beside their label. A lone row heading is a placeholder."""
    return [r for r in rws if sum(1 for x in r if x not in (None, "")) >= 2]

def solve_c(v):
    def f(c):
        eps = v["epscu"]*(c-v["d_prime"])/c
        return v["As_tension"]*v["fy"] - v["As_comp"]*v["Es"]*eps - .85*v["fc"]*v["beta1"]*c*v["bw"]
    lo, hi = v["d_prime"]+1e-7, v["d_flexure"]
    for _ in range(100):
        mid=(lo+hi)/2
        if f(lo)*f(mid)<=0: hi=mid
        else: lo=mid
    return (lo+hi)/2

def source_anchors():
    """Read independent anchors from the supplied material, not the workbook."""
    root = Path("/workspace/materials") if Path("/workspace/materials/beam_design_article.html").exists() else HERE.parent / "environment" / "workspace" / "materials"
    article = root / "beam_design_article.html"
    raw = article.read_text(encoding="utf-8", errors="replace")
    raw = re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", raw, flags=re.I|re.S)
    t = re.sub(r"\s+", " ", htmlmod.unescape(raw)).strip()
    def g(p):
        m=re.search(p,t,re.I|re.S)
        return float(m.group(1).replace(",","").replace(" ","")) if m else None
    factors = None
    pdf = root / "load_combinations_excerpt.pdf"
    try:
        txt=subprocess.run(["pdftotext","-layout",str(pdf),"-"],capture_output=True,text=True,check=True).stdout
        m=re.search(r"U\s*=\s*([0-9.]+)D\s*\+\s*([0-9.]+)L",txt)
        if m: factors=(float(m.group(1)),float(m.group(2)))
    except Exception:
        factors=None
    return {
      "dead_load": g(r"uniform dead load and live load of\s*([0-9.]+)\s*kip/ft"),
      "live_load": g(r"uniform dead load and live load of\s*[0-9.]+\s*kip/ft and\s*([0-9.]+)\s*kip/ft"),
      "span": g(r"(20)\s*ft\s*beam"), "h": g(r"overall cross-section of\s*([0-9.]+)\s*inches"), "bw": g(r"overall cross-section of\s*[0-9.]+\s*inches.*?([0-9.]+)\s*inches"),
      "fc": g(r"compression strength.*?([0-9,]+)\s*psi"), "fy": g(r"yield strength.*?([0-9,]+)\s*psi"),
      "As_comp": g(r"compression reinforcement.*?total area of\s*([0-9.]+)\s*in"), "d_prime": g(r"centroid distance \(d'\) of\s*([0-9.]+)\s*inches"),
      "As_tension": g(r"tensile reinforcement.*?total area of\s*([0-9.]+)\s*in"), "d_flexure": g(r"centroid distance \(d\) of\s*([0-9.]+)\s*inches"),
      "d_shear": g(r"effective depth \(d\) for the shear design calculations is taken as\s*([0-9.]+)\s*inches"), "Av": g(r"shear reinforcement \(A[^)]*v\s*\).*?area of\s*([0-9.]+)\s*in"),
      "Mu_reported": g(r"required nominal moment.*?found to be\s*([0-9,.]+)\s*kip-in"), "Vu_reported": g(r"V\s*u\s*=\s*([0-9.]+)\s*kips"),
      "s_trial": g(r"spacing of\s*([0-9.]+)\s*inches for the shear reinforcement"), "s_adopted": g(r"([0-9.]+)\s*inches should be used"), "smax_reported": g(r"maximum shear spacing is determined to be\s*([0-9.]+)\s*inches"),
      "dead_factor": factors[0] if factors else None, "live_factor": factors[1] if factors else None,
    }

def row_text(r): return " ".join(str(x or "") for x in r)

# --------------------------------------------------------------------------
# Recomputation of the review's conclusions.
#
# Every controlled status this workbook publishes describes a relation between
# quantities the workbook itself carries on its evidence sheet. The verifier
# reproduces each of those relations from those quantities and derives the
# status the relation supports. Nothing here reads a stored answer key, and
# nothing here depends on wording: a register can be rephrased freely, but it
# cannot call a spacing acceptable while its own inputs put that spacing beyond
# the maximum it reports.
# --------------------------------------------------------------------------

FLEX_NEEDS = ["epscu", "d_prime", "As_tension", "fy", "As_comp", "Es", "fc", "beta1", "bw", "d_flexure", "phi_flex"]

def flex_chain(v):
    """Neutral axis, forces, nominal and reduced moment, tension strain."""
    if any(v.get(k) is None for k in FLEX_NEEDS): return None
    if v["d_flexure"] <= v["d_prime"] or v["fc"] <= 0 or v["bw"] <= 0 or v["beta1"] <= 0: return None
    try:
        c = solve_c(v)
    except Exception:
        return None
    if not (v["d_prime"] < c < v["d_flexure"]): return None
    a = v["beta1"] * c
    eps_c = v["epscu"] * (c - v["d_prime"]) / c
    fs = min(v["Es"] * eps_c, v["fy"])
    T = v["As_tension"] * v["fy"]
    Cs = v["As_comp"] * fs
    Cc = .85 * v["fc"] * a * v["bw"]
    Mn = Cs * (a / 2 - v["d_prime"]) / 1000 + T * (v["d_flexure"] - a / 2) / 1000
    return {"c": c, "a": a, "T": T, "Cs": Cs, "Cc": Cc, "resid": T - Cs - Cc,
            "Mn": Mn, "phiMn": v["phi_flex"] * Mn,
            "eps_t": v["epscu"] * (v["d_flexure"] - c) / c}

def governing_vc(v):
    cands = [v.get(k) for k in ("Vc_a_reported", "Vc_b_reported", "Vc_c_reported")]
    cands = [x for x in cands if x is not None]
    return (min(cands) if len(cands) >= 3 else None), len(cands)

def shear_chain(v):
    vc, ncand = governing_vc(v)
    out = {"Vc": vc, "n_candidates": ncand}
    if all(v.get(k) is not None for k in ("Av", "fyt", "d_shear")):
        if v.get("s_trial"): out["Vs_trial"] = v["Av"] * v["fyt"] * v["d_shear"] / v["s_trial"] / 1000
        if v.get("s_adopted"): out["Vs_adopted"] = v["Av"] * v["fyt"] * v["d_shear"] / v["s_adopted"] / 1000
    if vc is not None and v.get("phi_shear") and out.get("Vs_adopted") is not None:
        out["Vn_adopted"] = v["phi_shear"] * (vc + out["Vs_adopted"])
    if vc is not None and v.get("phi_shear") and v.get("Vu_reported") is not None:
        out["Vs_required"] = (v["Vu_reported"] - v["phi_shear"] * vc) / v["phi_shear"]
    if all(v.get(k) is not None for k in ("phi_shear", "fc", "bw", "d_shear")) and v["fc"] > 0 and vc is not None:
        # ACI 318-14 Sec. 22.5.1.2 is Vu <= phi (Vc + 8 sqrt(fc') bw d).
        # The supplied article's displayed 105.04 kip omits Vc; the review must
        # retain that source value as an observation but use the complete formula
        # for the independent check.
        out["Vn_ceiling"] = v["phi_shear"] * (vc + 8 * math.sqrt(v["fc"]) * v["bw"] * v["d_shear"] / 1000)
    return out

# --- what the written finding says, read against what the relation supports ---
#
# The status token is not the only place a review states its conclusion: the
# rationale beside it is what a reader acts on, and a register whose statuses
# are right while every rationale says the opposite is not a review of this
# beam.  The reading below is deliberately narrow.  A sentence only counts when
# it puts a comparison word next to the kind of thing being compared against --
# a cap ("exceeds the reported maximum", "within the limit") or a demand
# ("remains above the required shear", "falls below the minimum required
# area") -- or uses a plain verdict word.  The same comparison word means
# opposite things on either side of that distinction, which is why a bare word
# list cannot do this.  Anything else reads as silent and costs nothing.
CAP = r"(?:maximum|max\b|limit|cap\b|ceiling|allowable|permitted|range|band)"
DEMAND = r"(?:demand\w*|required|requirement|needed|minimum|capacity required)"
UNDER = r"(?:with(?:in)?|inside|below|under|less than|no greater than|not exceed\w*|at or below)"
OVER = r"(?:exceed\w*|greater than|above|over|beyond|outside|past|more than|clear of|covers?)"

POS_PATTERNS = [
    re.compile(r"\b(?:is|sits|lies|falls|stays|remains|kept|held)\s+(?:with)?in\b[^.;]{0,40}\b" + CAP),
    re.compile(r"\b" + UNDER + r"\b[^.;]{0,40}\b" + CAP),
    re.compile(r"\b" + OVER + r"\b[^.;]{0,40}\b" + DEMAND),
    # "supports" and "carries" are nouns and load verbs in this
    # domain - "support face", "support details", "carries the load" - so they are
    # not verdict words here; they read a factual sentence as a pass. A completed
    # verification ("confirms", "confirmed") is a pass; the outstanding form
    # ("confirm the convention", "pending confirmation") stays in NEG_PATTERNS.
    re.compile(r"\b(?:satisf\w+|meets?|complies|compliant|acceptab\w+|adequate|sufficient|"
               r"reproduce\w*|returns?|matches?|agrees?|retain\w*|confirms|confirmed|"
               r"governs?|rules?|controls?|passe?[sd]?)\b"),
    re.compile(r"\bnothing\s+(?:outstanding|further|more|left|to\s+\w+)\b"),
    re.compile(r"\bno\s+(?:further|additional|outstanding|remaining)\b"),
]
NEG_PATTERNS = [
    re.compile(r"\b" + OVER + r"\b[^.;]{0,40}\b" + CAP),
    re.compile(r"\b(?:below|under|short of|less than|inside)\b[^.;]{0,40}\b" + DEMAND),
    re.compile(r"\b(?:fails?|failing|does not|do not|cannot|can not|will not|insufficient|"
               r"inadequate|unsupported|unacceptable|non.?compliant|disagree\w*|unresolved|"
               r"outstanding|pending)\b"),
    re.compile(r"\b(?:confirm|confirming|confirmation|review\w*|replace\w*|swap\w*|"
               r"revise\w*|resolve\w*|rework\w*)\b"),
    # A disposition that names a defect, a correction it demands, or an acceptance
    # it qualifies is not an unqualified pass, whatever verb it uses.
    re.compile(r"\b(?:defect\w*|deficien\w*|discrepanc\w*|non.?conservative|"
               r"must be (?:corrected|resolved|revised|reissued)|require\w* correction|"
               r"accept\w* with (?:comment|qualification|condition)|conditional accept\w*)\b"),
]
CLAIM_FOLLOW = re.compile(r"\b(?:neither|nor)\b")
CLAIM_NEG = re.compile(r"\b(?:not|no|never|nothing|without|cannot|can not|fails? to|nor|neither)\b")


# Counting bare verdict words over a register rationale is defeated by engineering
# prose: "the other applicable combination, 1.4D, does not govern", "the
# compression steel does not yield", "the ACI minimum of 0.80 in2 is not what
# governs here" are all correct PASS rationales whose words count as negative.
# RUBRIC, written findings: "a comparison is read only where the sentence
# names what is being compared against, because exceeding a cap and exceeding a
# demand are opposite results." So a register row's sentence is read only through
# the patterns that carry that anchor - a cap or a demand - and the bare word
# lists are kept for the closing page, where the claim being tested is the page's
# own overall disposition rather than one check's relation.
ANCHORED_POS = POS_PATTERNS[:3]
ANCHORED_NEG = NEG_PATTERNS[:2] + NEG_PATTERNS[4:]


def claim_polarity(text, anchored=False):
    """"meets", "fails" or None for one written finding."""
    s = re.sub(r"[^a-z0-9;.]+", " ", str(text or "").lower())
    pos = neg = 0
    pos_set = ANCHORED_POS if anchored else POS_PATTERNS
    neg_set = ANCHORED_NEG if anchored else NEG_PATTERNS
    for clause in re.split(r"[.;]| but | however | although ", s):
        if not clause.strip():
            continue
        for patterns, sign in ((pos_set, 1), (neg_set, -1)):
            for pattern in patterns:
                for m in pattern.finditer(clause):
                    # A negator normally stands before the word it turns over, but
                    # "matches neither the shear d nor the flexural d" puts it after.
                    # Only neither/nor are read forward: a trailing "is not acceptable"
                    # belongs to the next assertion, not to the comparison just made.
                    negated = bool(CLAIM_NEG.search(clause[max(0, m.start() - 28):m.start()])) \
                        or bool(CLAIM_FOLLOW.search(clause[m.end():m.end() + 20]))
                    value = -sign if negated else sign
                    if value > 0:
                        pos += 1
                    else:
                        neg += 1
    if pos > neg:
        return "meets"
    if neg > pos:
        return "fails"
    return None


def claim_agrees(polarity, verdict):
    """None means the sentence said nothing decidable, which costs nothing."""
    if polarity is None or verdict is None:
        return True
    return (polarity == "meets") == (verdict == "PASS")


def recomputed_verdicts(v, fx, sc):
    """The status each check's own relation supports. Missing inputs -> no verdict."""
    E = {}
    if all(v.get(k) is not None for k in ("dead_factor", "live_factor", "dead_load", "live_load", "span", "Mu_reported")):
        wu = v["dead_factor"] * v["dead_load"] + v["live_factor"] * v["live_load"]
        E["LC-01"] = "PASS" if agrees(wu * v["span"] ** 2 / 8 * 12, v["Mu_reported"], .01) else "FAIL"
    if fx and v.get("Mu_reported") is not None:
        E["FX-01"] = "PASS" if fx["phiMn"] >= v["Mu_reported"] else "FAIL"
    if fx:
        E["FX-02"] = "PASS" if fx["eps_t"] >= .005 else "FAIL"
    if v.get("As_tension") is not None and v.get("As_required_reported") is not None:
        E["FX-03"] = "PASS" if v["As_tension"] >= v["As_required_reported"] else "FAIL"
    if sc.get("n_candidates", 0) >= 3 and sc.get("Vc") is not None:
        E["SH-01"] = "PASS"
    if v.get("s_trial") is not None and v.get("smax_reported") is not None:
        E["SH-02"] = "FAIL" if v["s_trial"] > v["smax_reported"] else "PASS"
    if v.get("s_adopted") is not None and v.get("smax_reported") is not None and sc.get("Vn_adopted") is not None and v.get("Vu_reported") is not None:
        E["SH-03"] = "PASS" if (v["s_adopted"] <= v["smax_reported"] and sc["Vn_adopted"] >= v["Vu_reported"]) else "FAIL"
    if v.get("d_shear") is not None and v.get("d_flexure") is not None:
        E["SH-04"] = "REVIEW" if abs(v["d_shear"] - v["d_flexure"]) > 1e-9 else "PASS"
    if sc.get("Vn_ceiling") is not None and v.get("Vu_reported") is not None:
        E["SH-05"] = "PASS" if sc["Vn_ceiling"] >= v["Vu_reported"] else "FAIL"
    return E

CHECKS = [
  ("LC-01", ["load", "combination"]), ("FX-01", ["flexure"]), ("FX-02", ["tension", "strain"]),
  ("FX-03", ["provided", "required"]), ("SH-01", ["concrete", "candidate"]), ("SH-02", ["trial", "spacing"]),
  ("SH-03", ["adopted", "spacing"]), ("SH-04", ["depth", "convention"]), ("SH-05", ["section", "capacity"])]

# A register row is recognised by what the row is about, not by the reference
# solution's own finding ids or its exact wording. Each entry is a list of
# alternative term sets; a row matches when it contains every term of one set.
CHECK_TERMS = {
  "LC-01": [["load", "combination"], ["governing", "combination"], ["1.2d", "1.6l"],
            ["factored", "moment"], ["gravity", "load"], ["mu", "midspan"]],
  "FX-01": [["flexural", "capacity"], ["flexure", "capacity"], ["moment", "capacity"],
            ["phi", "mn"], ["flexural", "strength"], ["flexure"]],
  "FX-02": [["tension", "strain"], ["strain", "control"], ["eps_t"], ["epst"], ["tension-controlled"]],
  "FX-03": [["provided", "required"], ["as", "required"], ["required", "reinforcement"],
            ["minimum", "reinforcement"], ["tension steel", "required"]],
  "SH-01": [["concrete", "candidate"], ["vc", "candidate"], ["vc", "govern"], ["vc", "minimum"],
            ["concrete shear"]],
  "SH-02": [["trial", "spacing"], ["spacing", "14"]],
  "SH-03": [["adopted", "spacing"], ["spacing", "11 in"], ["adopted", "11"]],
  "SH-04": [["depth", "convention"], ["effective depth", "shear"], ["depth", "split"],
            ["20.5", "22.5"], ["depth", "flexure", "shear"]],
  "SH-05": [["section", "capacity"], ["22.5.1.2"], ["ceiling"], ["maximum", "vn"], ["section", "limit"]],
}
STATUS_HEAD = re.compile(r"status|disposition|verdict|conclusion|outcome|result of check", re.I)
RATIONALE_HEAD = re.compile(r"rationale|reason|basis|comment|note|\bfinding(?![_ -]?(?:id|code|key))\b|effect|action|recommend|"
                            r"justification|remark|margin|limit", re.I)


# --- binding a register row to the reference check it computes -------------
#
# CHECK_TERMS binds a check to a register row by keyword match.  A register that
# decomposes into fifteen or more rows has several rows matching one check's words,
# and the first of them wins whatever it is about: "trial spacing s = 14 in
# satisfies strength" is a strength branch, not the spacing limit, and a row whose
# rationale mentions that "the spacing branch fails" is not the spacing branch.
# A review row states a relation between two quantities, so bind it by the
# quantities it actually carries - literally, or through a reference into the
# evidence ledger - and fall back to the words only when nothing computes the check.
NUMBER = re.compile(r"\(?\s*[-+\u2212\u2013]?\s*\d[\d,]*(?:\.\d+)?\s*\)?")


# A row is bound to a check by the quantities it states, so what counts as a
# quantity has to be a number the row states.  Scraping every digit out of every
# cell would also harvest cell addresses ($P$11), the register's own finding ids
# (F-026, read as -26), locator line numbers (HTML L3296) and bar designations
# (#8), and one of those is enough to bind a check: a row reading "Official code
# provisions absent" would answer the adopted-spacing check because $P$11 gives 11.
# A digit welded to a letter, a $ or a # is part of an identifier, not a value.
IDENT_LEFT = re.compile(r"(?:[A-Za-z$#]|[A-Za-z][-_])$")


def row_numbers(cells):
    out = []
    for v in cells:
        if v is None: continue
        if isinstance(v, bool): continue
        if isinstance(v, (int, float)):
            out.append(float(v)); continue
        t = str(v).replace("\u2212", "-").replace("\u2013", "-")
        if t.startswith("="): continue
        for m in NUMBER.finditer(t):
            if IDENT_LEFT.search(t[:m.start()]): continue
            raw = m.group(0).strip()
            neg = raw.startswith("(") and raw.endswith(")")
            n = num(raw.strip("()").replace(",", ""))
            if n is not None: out.append(-n if neg else n)
    return out


def row_fields(cells, inp_title, rowfields):
    """Evidence fields the row's formulas point at."""
    if not inp_title: return set()
    pat = re.compile(r"'?" + re.escape(inp_title) + r"'?!\$?[A-Z]{1,3}\$?(\d+)")
    out = set()
    for v in cells:
        if isinstance(v, str):
            for m in pat.finditer(v):
                f = rowfields.get(int(m.group(1)))
                if f: out.add(f)
    return out


# Each check is the relation between two quantities the supplied article states.
# A row computes the check when it carries both, as a number within 3% or as a
# reference to the evidence row that holds it. Values come from the article, not
# from the workbook, because the question is which reference check the row answers.
CHECK_OPERANDS = {
  "LC-01": [("Mu_reported",), ("dead_factor", "live_factor", "span", "dead_load", "live_load")],
  "FX-01": [("phiMn_reported",), ("Mu_reported",)],
  "FX-02": [("eps_t_reported",), ("strain_limit",)],
  "FX-03": [("As_tension",), ("As_required_reported",)],
  "SH-01": [("Vc_a_reported", "Vc_b_reported"), ("Vc_c_reported",)],
  "SH-02": [("s_trial",), ("smax_reported",)],
  "SH-03": [("s_adopted",), ("smax_reported",)],
  "SH-04": [("d_shear",), ("d_flexure",)],
  "SH-05": [("Vn_max_reported",), ("Vu_reported",)],
}


def operand_binding(cells, anchors, inp_title, rowfields):
    """The checks this row computes, by the quantities it carries.

    Matching each operand group independently against the same pool of numbers
    would let ONE number stand for BOTH sides of a relation.  The adopted spacing is
    11 in and the maximum spacing is 11.25 in - 2.3% apart, inside the 3% match band
    - and the beam width is also 11 in, so any row that mentions the width would
    "compute" the adopted-spacing check, and a reinforcement-ratio row
    (4.71/(11 x 22.5)) would answer both spacing checks at once.
    A row states a relation between two quantities only if it carries two of them,
    so the groups are matched injectively, and a number counts for a group only
    when it is nearer that group's anchor than any other group's anchor.
    """
    nums = row_numbers(cells)
    fields = row_fields(cells, inp_title, rowfields)
    out = []
    for k, groups in CHECK_OPERANDS.items():
        wants = [[anchors.get(f) for f in g] for g in groups]
        # a group is satisfied outright when a formula on the row points at the
        # evidence row holding one of its fields; that needs no number.
        by_ref = [any(f in fields for f in g) for g in groups]
        used = set()
        ok = True
        for gi, g in enumerate(groups):
            if by_ref[gi]:
                continue
            other = [w for gj, ws in enumerate(wants) if gj != gi for w in ws if w]
            pick = None
            for ni, n in enumerate(nums):
                if ni in used: continue
                for want in wants[gi]:
                    if want is None or want == 0: continue
                    if abs(n - want) > abs(want) * .03: continue
                    if any(abs(n - o) < abs(n - want) for o in other): continue
                    pick = ni; break
                if pick is not None: break
            if pick is None:
                ok = False; break
            used.add(pick)
        if ok: out.append(k)
    return out


def finding_header_roles(rws):
    """Return the actual finding-table header and its semantic columns.

    Titles and preamble notes often contain words such as ``finding`` or
    ``status``.  They are not table headers.  A valid candidate must declare at
    least two column roles on the same row, including a status column, and is
    ranked by the controlled status values and populated evidence/rationale
    cells beneath it.  This keeps layout freedom while grounding the choice in
    the table's data rather than the first matching word.
    """
    candidates = []
    for i, r in enumerate(rws[:12]):
        roles = {"status": [], "locator": [], "rationale": []}
        nonempty = 0
        for c, v in enumerate(r):
            if not isinstance(v, str) or not v.strip() or len(v.strip()) > 60:
                continue
            nonempty += 1
            if STATUS_HEAD.search(v):
                roles["status"].append(c)
            if LOC_HEAD.search(v):
                roles["locator"].append(c)
            if RATIONALE_HEAD.search(v):
                roles["rationale"].append(c)
        role_count = sum(bool(cols) for cols in roles.values())
        if not roles["status"] or role_count < 2 or nonempty < 2:
            continue
        below = rws[i + 1:]
        token_counts = {
            c: sum(1 for row in below if c < len(row) and leading_status(row[c]))
            for c in roles["status"]
        }
        best_status = max(roles["status"], key=lambda c: (token_counts[c], -c))
        roles["status"] = [best_status]
        status_hits = token_counts[best_status]
        loc_hits = sum(1 for row in below if any(c < len(row) and str(row[c] or "").strip()
                                                for c in roles["locator"]))
        rat_hits = sum(1 for row in below if any(c < len(row) and str(row[c] or "").strip()
                                                for c in roles["rationale"]))
        candidates.append(((status_hits, min(loc_hits, rat_hits), role_count, nonempty, i), i, roles))
    if not candidates:
        return None, {}
    _, i, roles = max(candidates, key=lambda item: item[0])
    return i, roles


def register_rows(book, skip_titles):
    """Candidate finding rows, findings register first, then the closing page, then the rest.

    Each entry is (row text, declared status, rationale text). Only rows that
    actually carry a controlled status are candidates, so a calculation line
    without a verdict cannot be mistaken for a register row.
    """
    fd = find_sheet(book, ["findings", "reviewfindings", "issues", "register"])
    summ = find_sheet(book, ["summary", "disposition", "overall", "conclusion", "verdict", "closeout", "closure"])
    ordered = [w for w in (fd, summ) if w is not None]
    ordered += [w for w in book.worksheets if w not in ordered and norm(w.title) not in skip_titles]
    out = []
    for ws in ordered:
        rws = rows(ws)
        header_idx, roles = finding_header_roles(rws)
        status_cols = roles.get("status", [])
        rationale_cols = roles.get("rationale", [])
        start = header_idx + 1 if header_idx is not None else 1
        for r in rws[start:]:
            if not r: continue
            declared = None
            for c in status_cols:
                if c < len(r):
                    declared = exact_status(r[c]) or leading_status(r[c])
                    if declared: break
            if declared is None:
                declared = next((s for s in (exact_status(c) for c in r) if s), None)
            if declared is None: continue
            text = row_text(r).lower()
            if rationale_cols:
                rationale = " ".join(str(r[c]) for c in rationale_cols if c < len(r) and r[c] is not None)
            else:
                rationale = " ".join(str(x) for x in r[3:] if x is not None)
            # What the row is *about* is its own label cells; the rationale beside it
            # often names neighbouring checks ("do not adopt: the spacing branch
            # fails F-14"), and matching a check's terms there binds the verdict to
            # the wrong row - here, to the strength branch at the trial spacing
            # rather than to the trial spacing itself.
            subject = " ".join(str(x) for c, x in enumerate(r)
                               if x is not None and c not in rationale_cols).lower()
            # What a row is ABOUT is its label cells.  A register also carries a
            # conclusion column, and matching a check's words there binds the
            # verdict to whatever the sentence mentions in passing: an "Alternate
            # effective depths" row whose conclusion reads "... by provided versus
            # required steel" would answer the provided-versus-required steel check
            # that another row of the same register decides.  A label is short; a
            # conclusion is a sentence.
            label = " ".join(str(x) for c, x in enumerate(r)
                             if x is not None and c not in rationale_cols
                             and len(str(x).strip()) <= LABEL_CELL_CHARS).lower()
            out.append((text, declared, rationale, ws.title, subject, r, label))
    return out, fd
DIMENSION_CHECKS = {"load_combination": ["LC-01"], "flexure": ["FX-01", "FX-02", "FX-03"],
                    "shear": ["SH-01", "SH-02", "SH-03", "SH-04", "SH-05"]}

# Relation rows: a calculation row that puts these evidence fields side by side is
# asserting the relation between them, so the status it carries has to match the
# relation. Rows are recognised by the evidence cells they reference, not by their
# label, so renaming or reordering the sheet changes nothing.
def relation_expectation(refs, v):
    """(check id, status the relation supports) or (None, None)."""
    R = lambda *ks: all(k in refs for k in ks)
    if R("s_trial", "smax_reported") and "s_adopted" not in refs:
        if v.get("s_trial") is None or v.get("smax_reported") is None: return None, None
        return "SH-02", ("FAIL" if v["s_trial"] > v["smax_reported"] else "PASS")
    if R("s_adopted", "smax_reported") and "s_trial" not in refs:
        if v.get("s_adopted") is None or v.get("smax_reported") is None: return None, None
        return "SH-03", ("PASS" if v["s_adopted"] <= v["smax_reported"] else "FAIL")
    if R("d_shear", "d_flexure") and not (refs & {"As_tension", "Mn_reported", "fc"}):
        if v.get("d_shear") is None or v.get("d_flexure") is None: return None, None
        return "SH-04", ("REVIEW" if abs(v["d_shear"] - v["d_flexure"]) > 1e-9 else "PASS")
    if R("As_tension", "As_required_reported"):
        if v.get("As_tension") is None or v.get("As_required_reported") is None: return None, None
        return "FX-03", ("PASS" if v["As_tension"] >= v["As_required_reported"] else "FAIL")
    if R("dead_load", "live_load", "span", "Mu_reported"):
        if any(v.get(k) is None for k in ("dead_factor", "live_factor", "dead_load", "live_load", "span", "Mu_reported")): return None, None
        wu = v["dead_factor"] * v["dead_load"] + v["live_factor"] * v["live_load"]
        return "LC-01", ("PASS" if agrees(wu * v["span"] ** 2 / 8 * 12, v["Mu_reported"], .01) else "FAIL")
    return None, None

def sheet_relation_audit(book, inp_ws, rowfields, v, skip_titles):
    """Every status published on a calculation sheet, against its own referenced inputs."""
    if inp_ws is None: return 0, 0, [], {}
    pat = re.compile(r"'?" + re.escape(inp_ws.title) + r"'?!\$?[A-Z]{1,3}\$?(\d+)")
    recognised = contradicted = 0
    detail = []
    sheet_declared = {}
    for ws in book.worksheets:
        if norm(ws.title) in skip_titles: continue
        for r in ws.iter_rows():
            raw = [c.value for c in r]
            cells = [shown(ws.title, c) for c in r]
            refs = set()
            # which evidence rows this row refers to is a property of its formulas,
            # so the references are read from the formula text; the status it
            # publishes is read from the resolved value.
            for cv in raw:
                if isinstance(cv, str):
                    for m in pat.finditer(cv):
                        f = rowfields.get(int(m.group(1)))
                        if f: refs.add(f)
            if not refs: continue
            declared = next((s for s in (exact_status(cv) for cv in cells) if s), None)
            if declared is None: continue
            key, exp = relation_expectation(refs, v)
            if exp is None: continue
            recognised += 1
            sheet_declared.setdefault(key, declared)
            if declared != exp:
                contradicted += 1
                detail.append({"sheet": ws.title, "row": r[0].row, "check": key, "declared": declared, "expected": exp})
    return recognised, contradicted, detail, sheet_declared

DISPOSITION_LABELS = ("disposition", "overall", "conclusion", "verdict", "closeout",
                      "closure", "recommendation", "requiredaction", "mandatorycorrection")


def summary_disposition(book, skip_titles):
    """Controlled statuses the closing page declares as its own verdict."""
    ws = find_sheet(book, ["summary", "disposition", "overall", "conclusion", "verdict", "closeout", "closure"])
    if ws is None:
        cands = [w for w in book.worksheets if norm(w.title) not in skip_titles]
        ws = cands[-1] if cands else None
    if ws is None: return None, set(), set()
    rws = rows(ws)
    declared = {s for r in rws[1:] for s in (exact_status(c) for c in r) if s}
    # RUBRIC: "status checks accept leading controlled terms and equivalent
    # professional qualifiers", and the closing disposition is read "from the rows
    # labelled as the disposition". A page that writes "NOT FIT TO BE RELIED UPON AS
    # ISSUED" beside its Overall-disposition label has declared a non-PASS
    # disposition; reading only cells spelled exactly PASS/FAIL/REVIEW would record
    # that page as declaring nothing but the PASS token it prints elsewhere.
    for r in rws[1:]:
        label = norm(r[0] if r else "")
        if not any(w in label for w in DISPOSITION_LABELS): continue
        for c in r:
            if not isinstance(c, str) or c.startswith("=") or len(c.strip()) > 80: continue
            got = leading_status(c)
            if got: declared.add(got)
    if not declared:
        # No cell is a bare status token: fall back to the leading controlled term of
        # narrative rows, ignoring rows whose value is a formula (count roll-ups).
        for r in rws[1:]:
            for c in r:
                s = leading_status(c)
                if s: declared.add(s)
    mentioned = {s for r in rws for c in r if isinstance(c, str) for s in STATUS if s in c.upper()}
    return ws, declared, mentioned

# --------------------------------------------------------------------------
# Evidence traceability over the whole reference ledger.
#
# The brief asks for a workbook that "must retain traceable evidence locations for
# each material conclusion", and the reference Source_Inputs sheet carries all 41
# of its quantities that way - value, unit, state, Source_locator and Source_quote,
# e.g. row 34 "Vc_a_reported | 44.96 | kip | reported concrete shear candidate a |
# Shear Strength > Equation a | Vc-a". P01 applies that test to the 23
# `required_fields`; the items below apply it to the rest of the ledger - the
# reported results, the derivation constants, the section and material inputs, and
# the shear-spacing trail.
#
# They are those rows grouped by what the quantity is. Each scores the fraction of
# its group the workbook carries with the reference's value (unit-converted, within
# one per cent), a source locator and a verbatim quote, on the row that names the
# quantity.
# --------------------------------------------------------------------------
GOLDEN_LEDGER = {
  "P12": [
      ('dead_load', 2.0),
      ('live_load', 3.2),
      ('dead_factor', 1.2),
      ('live_factor', 1.6),
      ('span', 20.0),
  ],
  "P13": [
      ('Mn_reported', 5122.69),
      ('phiMn_reported', 4610.42),
      ('eps_t_reported', 0.00755),
      ('Mu_at_d_reported', 1533.38),
      ('rho_reported', 0.01992),
      ('Vc_a_reported', 44.96),
      ('Vc_b_reported', 46.26),
      ('Vc_c_reported', 61.25),
      ('Vn_adopted_reported', 70.54),
      ('Vn_max_reported', 138.73),
      ('As_required_reported', 4.46),
      ('As_provided_reported', 4.72),
  ],
  "P14": [
      ('Es', 29000000.0),
      ('fyt', 60000.0),
      ('epscu', 0.003),
      ('beta1', 0.8),
      ('phi_flex', 0.9),
      ('phi_shear', 0.75),
      ('c_solution', 5.794757224742744),
  ],
  "P15": [
      ('h', 25.0),
      ('bw', 11.0),
      ('d_prime', 3.0),
      ('d_flexure', 20.5),
      ('d_shear', 22.5),
      ('As_comp', 1.57),
      ('As_tension', 4.71),
      ('Av', 0.4),
  ],
  # RUBRIC, with-skill profile: the workbook "records the intermediate 14-inch
  # spacing failure before the 11-inch adoption". The reference ledger carries that
  # trail as five bound rows - s_trial 14 in ("A spacing of 14 inches ... is
  # used"), smax_reported 11.25 in ("the maximum shear spacing is determined to
  # be 11.25 inches"), s_adopted 11 in ("11 inches should be used"), and the two
  # steel-shear values Vs = 38.57 kip and Vs = 49.09 kip that go with them.
  "P16": [
      ('s_trial', 14.0),
      ('smax_reported', 11.25),
      ('s_adopted', 11.0),
      ('Vs_trial_reported', 38.57),
      ('Vs_adopted_reported', 49.09),
  ],
}

QUOTE_MIN = 8
LEDGER_SCALES = (1.0, 1000.0, .001, 12.0, 1 / 12.0)
LEDGER_GENERIC = {"reported", "value", "solution"}
LEDGER_LOCATOR = re.compile(r"beam_design_article|load_combinations_excerpt|\.html|\.pdf|"
                            r"moment strength|shear strength|description|results|table 5\.3\.1|"
                            r"formula \d|equation [abc]|section", re.I)


def ledger_terms(field):
    """How the reference ledger's row for this quantity may be named."""
    pats = FIELD_PATTERNS.get(field, ([], []))[0]
    toks = [t for t in re.split(r"[_\W]+", field.lower()) if t and t not in LEDGER_GENERIC]
    out = []
    if pats: out.append(("__re__", pats))
    if toks: out.append(tuple(toks))
    return out


def ledger_names(text, term_sets):
    for ts in term_sets:
        if ts and ts[0] == "__re__":
            if any(re.search(pat, text) for pat in ts[1]): return True
        elif ts and all(t in text for t in ts): return True
    return False


def ledger_carries(entry, want):
    """The declared number is the reference value, in the unit the row itself states."""
    for value, _unit in entry["pairs"]:
        for scale in LEDGER_SCALES:
            if want and abs(value * scale - want) <= abs(want) * .01: return True
    return False


def ledger_evidence(entries, group):
    """Fraction of one group of reference ledger rows carried with value, locator and quote."""
    want_rows = GOLDEN_LEDGER[group]
    good = 0
    for field, want in want_rows:
        term_sets = ledger_terms(field)
        for e in entries:
            if not e["pairs"] or not ledger_names(e["text"], term_sets): continue
            if not ledger_carries(e, want): continue
            row_text = " ".join(str(x) for x in e["raw"] if x is not None)
            if not LEDGER_LOCATOR.search(row_text): continue
            if not any(isinstance(x, str) and not x.startswith("=") and len(x.strip()) >= QUOTE_MIN
                       for x in e["raw"]): continue
            good += 1
            break
    return good / len(want_rows) if want_rows else 0.0


class SemanticInfrastructureError(RuntimeError):
    pass


def score_book(book):
    install_resolver(book)
    ev_sheets = evidence_sheets(book)
    inp_ws = find_sheet(book, ["sourceinputs", "inputs", "evidence"]) or (ev_sheets[0] if ev_sheets else None)
    ledger_entries = input_rows(ev_sheets)
    inp = resolve_inputs(ledger_entries)
    required = GROUND["required_fields"]
    complete = 0
    src = source_anchors()
    for f in required:
        q = get_input(inp, f)
        if q and q["value"] is not None and str(q["unit"]).strip() and str(q["loc"]).strip() and str(q["quote"]).strip(): complete += 1
    evidence = complete / len(required) if required else 0.0

    def iv(f):
        q=get_input(inp,f); return q["value"] if q else None
    FIELDS = ["dead_load","live_load","dead_factor","live_factor","span","h","bw","d_shear","Mu_reported","Vu_reported","fc","Av","fyt","s_trial","s_adopted","smax_reported","phi_shear","As_tension","As_required_reported","d_flexure","As_comp","fy","Es","beta1","epscu","d_prime","phi_flex","Mn_reported","phiMn_reported","eps_t_reported","c_solution","Vc_a_reported","Vc_b_reported","Vc_c_reported","Vs_trial_reported","Vs_adopted_reported","Vn_adopted_reported","Vn_max_reported","Vn_max_source_reported"]
    vals = {k: iv(k) for k in FIELDS}
    # A review that states one yield strength and uses it for stirrups too has not
    # omitted fyt; the supplied article gives a single fy.
    if vals.get("fyt") is None: vals["fyt"] = vals.get("fy")
    source_match = [k for k,v in src.items() if v is not None and vals.get(k) is not None and rel(vals[k],v) <= .01]
    evidence *= len(source_match) / max(1, len([k for k,v in src.items() if v is not None]))

    # The relations behind every published conclusion, recomputed from the
    # workbook's own evidence sheet.
    fx_chain = flex_chain(vals)
    sh_chain = shear_chain(vals)
    expected = recomputed_verdicts(vals, fx_chain, sh_chain)

    ev_titles = {norm(w.title) for w in ev_sheets}
    rowfields = {}
    if inp_ws is not None:
        for f, rec in inp.items():
            if f in FIELDS and rec.get("sheet") == inp_ws.title:
                rowfields.setdefault(rec["row"], f)
    # The quantities each reference check relates, read from the supplied article
    # rather than from the workbook: the question a binding answers is which of
    # the reference's checks a row computes, and that is fixed by the source.
    bind_anchors = dict(src)
    bind_anchors["d_flexure"] = src.get("d_flexure")
    bind_anchors["strain_limit"] = .005
    for k in ("phiMn_reported", "eps_t_reported", "As_required_reported",
              "Vc_a_reported", "Vc_b_reported", "Vc_c_reported", "Vn_max_reported", "Vn_max_source_reported"):
        bind_anchors.setdefault(k, None)
    bind_anchors["phiMn_reported"] = 4610.42
    bind_anchors["eps_t_reported"] = .00755
    bind_anchors["As_required_reported"] = 4.46
    bind_anchors["Vc_a_reported"] = 44.96
    bind_anchors["Vc_b_reported"] = 46.26
    bind_anchors["Vc_c_reported"] = 61.25
    bind_anchors["Vn_max_reported"] = 138.73
    candidates, fd = register_rows(book, ev_titles)
    fdr = rows(fd)[1:] if fd else []

    matched_rows = {}

    def finding_status(key, terms):
        # The reference solution's finding ids are only meaningful inside the
        # register itself; a calculation sheet may number its own rows the same way.
        #
        # Matching an id as a bare substring of the whole row would let a
        # cross-reference token bind the check: a row citing the calculation range
        # "SH-02:SH-05" would answer SH-02 and SH-05 although other rows of the same
        # register decide them. An id is a whole token, and a token inside a range
        # or a list is a citation of another row, not this row's own id.
        idpat = re.compile(r"(?<![0-9A-Za-z:.-])" + re.escape(key.lower()) + r"(?![0-9A-Za-z:.-])")
        for text, declared, why, sheet, subject, cells, label in candidates:
            if fd is not None and sheet == fd.title and idpat.search(text):
                return declared, why, "%s:id" % sheet
        inp_title = inp_ws.title if inp_ws is not None else None
        on_register = [c for c in candidates if fd is not None and c[3] == fd.title]
        # A concrete finding row outranks a broad operand match. Otherwise a
        # different row that happens to carry the same two quantities can supply
        # the verdict for this finding.
        # The wording fallback does not scan every sheet: a cover page, a read-me
        # legend or a source index states the review's scope in prose and names
        # every check in passing, so its own overall disposition would otherwise
        # answer a check the register itself carries.
        wordable = [c for c in candidates if not any(w in norm(c[3]) for w in FRONT_MATTER)]
        for field, tag in ((6, "label"), (4, "subject"), (0, "row")):
            for term_set in CHECK_TERMS.get(key, [terms]):
                for cand in wordable:
                    if all(t.lower() in cand[field] for t in term_set):
                        return cand[1], cand[2], "%s:%s:%s" % (cand[3], tag, "+".join(term_set))
        # Only when no register row names the finding does its formula/operand
        # relation identify the row.
        for cand in on_register:
            if key in operand_binding(cand[5], bind_anchors, inp_title, rowfields):
                return cand[1], cand[2], "%s:operands" % cand[3]
        # Last, a row anywhere that computes the check: a workbook may carry its
        # verdicts on the calculation sheets instead of a separate register.
        for cand in candidates:
            if key in operand_binding(cand[5], bind_anchors, inp_title, rowfields):
                return cand[1], cand[2], "%s:operands" % cand[3]
        return None, None, None

    def all_answers(key, terms):
        """Every status published by a row that answers this check.

        A register may decompose one reference check into several rows - "D+L
        factored line load" PASS beside "Full supplied gravity combination
        completeness" REVIEW, or a tension-area comparison PASS beside a REVIEW on
        the local detailing geometry.  Taking the first row that matches and
        charging its status would say the workbook contradicted a relation it has in
        fact published correctly.  A review has contradicted a check only when NO
        row answering it
        carries the verdict the relation supports; the caveats it adds alongside are
        not contradictions.
        """
        out = set()
        inp_title = inp_ws.title if inp_ws is not None else None
        idpat = re.compile(r"(?<![0-9A-Za-z:.-])" + re.escape(key.lower()) + r"(?![0-9A-Za-z:.-])")
        wordable = [c for c in candidates if not any(w in norm(c[3]) for w in FRONT_MATTER)]
        for cand in candidates:
            text, declared, why, sheet, subject, cells, label = cand
            if declared is None:
                continue
            hit = (fd is not None and sheet == fd.title and idpat.search(text))
            if not hit:
                hit = key in operand_binding(cells, bind_anchors, inp_title, rowfields)
            if not hit and cand in wordable:
                for field in (6, 4, 0):
                    for term_set in CHECK_TERMS.get(key, [terms]):
                        if all(t.lower() in cand[field] for t in term_set):
                            hit = True; break
                    if hit: break
            if hit:
                out.add(declared)
        return out

    skip_titles = {norm(inp_ws.title) if inp_ws is not None else "", norm(fd.title) if fd is not None else ""}
    recognised, sheet_contradicted, sheet_detail, sheet_declared = sheet_relation_audit(book, inp_ws, rowfields, vals, skip_titles)

    published = {}
    rationale = {}
    for key, terms in CHECKS:
        got, why, where = finding_status(key, terms)
        # Preserve the actual public register answer. An agreeing calculation row
        # cannot overwrite a contradictory published verdict.
        published[key] = got
        rationale[key] = why or ""
        matched_rows[key] = where

    # findings: a status is credited only when the workbook's own inputs reproduce
    # the relation behind it AND the published status is the one that relation
    # supports AND the sentence written beside it does not say the opposite. A
    # register of statuses with nothing behind them earns nothing, and neither
    # does a register whose written findings contradict the statuses they sit
    # next to - that is the version of the review a reader actually acts on.
    narrative = {k: claim_polarity(rationale.get(k), anchored=True) for k, _ in CHECKS}
    narrative_ok = {k: claim_agrees(narrative.get(k), expected.get(k)) for k, _ in CHECKS}
    hits = sum(1 for k, _ in CHECKS if expected.get(k) and published.get(k) == expected[k] and narrative_ok[k])
    findings = hits / len(CHECKS)
    # A deduction is charged only where the workbook's own recomputation agrees
    # with the reference's verdict for that check.  Where a workbook's own inputs
    # make a relation come out differently from the reference's, the disagreement is
    # about the inputs - which P01 and P12-P16 already score - and not about a review
    # contradicting itself: a ledger whose Vc makes its own relation read FAIL would
    # otherwise be charged for publishing the reference's own verdict.
    REFERENCE = GROUND.get("findings", {})
    # A charge also needs the row it charges to BE the row that answers the check.
    # Binding by wording is how a register's verdict is found when nothing else
    # identifies it, and it is good enough to credit a verdict but not to charge
    # one: a sheet subtitle, a read-me disposition, a scope caveat beside the
    # arithmetic it qualifies, or a depth finding whose narrative happens to carry
    # the words "provided versus required" all match that way, and a match inside a
    # conclusion sentence is not an identification.  So a deduction is charged only
    # where the row was found by the check's own quantities, by its own finding id,
    # or by the check's terms in its own label.
    def soundly_bound(k):
        tag = matched_rows.get(k) or ""
        return ":operands" in tag or ":id" in tag or ":label:" in tag
    # LC-01 is credited but not chargeable.  A register that answers it splits it
    # into an arithmetic row and a scope row, and the scope row is what any binder
    # selects: "Full supplied gravity combination completeness" (REVIEW, because the
    # PDF combination's Lr/S/R term has no supplied value) sits beside the same
    # register's "D+L factored line load" PASS and "Reported action effects" PASS,
    # which are the reference's verdict.
    NOT_CHARGEABLE = {"LC-01"}
    chargeable = {k for k, _ in CHECKS
                  if expected.get(k) and REFERENCE.get(k) == expected[k]
                  and soundly_bound(k) and k not in NOT_CHARGEABLE}
    register_wrong = [k for k, _ in CHECKS
                      if k in chargeable and published.get(k) and published[k] != expected[k]]
    register_contradicted = len(register_wrong)
    register_factor = 1.0 - register_contradicted / len(CHECKS)
    narrative_wrong = [k for k, _ in CHECKS if expected.get(k) and not narrative_ok[k]]
    narrative_contradicted = len(narrative_wrong)
    narrative_factor = 1.0 - narrative_contradicted / len(CHECKS)

    sheet_factor = 1.0 - sheet_contradicted / recognised if recognised else 1.0
    # The register and the calculation sheet are two statements of the same
    # verdict. A workbook that clears a check in the register while its own
    # sheet still fails it has not reviewed anything; it has two reviews.
    coherent_keys = [k for k in sheet_declared if k and published.get(k)]
    incoherent = [k for k in coherent_keys if k != "LC-01" and sheet_declared[k] and sheet_declared[k] != published[k]]
    coherence_factor = 1.0 - len(incoherent) / len(coherent_keys) if coherent_keys else 1.0
    # The same goes for a register row against the sentence printed beside it. A
    # row that carries PASS next to "exceeds the reported maximum and is not
    # acceptable as detailed" has not decided anything, and moving only the token
    # must not be cheaper than moving the token and the sentence together.
    row_keys = [k for k, _ in CHECKS if published.get(k) and narrative.get(k)]
    row_conflict = [k for k in row_keys if (narrative[k] == "meets") != (published[k] == "PASS")]
    row_coherence = 1.0 - len(row_conflict) / len(row_keys) if row_keys else 1.0
    coherence_factor *= row_coherence

    summary_ws, declared, mentioned = summary_disposition(book, skip_titles)
    # The review's open items are a fact of the supplied beam, not of what the
    # workbook happened to write down. The article states a trial spacing of 14
    # inches against a maximum shear spacing "determined to be 11.25 inches", and a
    # shear effective depth "taken as 22.5 inches opposed to the 20.5 inches set
    # forth in the problem statement"; the reference register carries those as SH-02 FAIL
    # and SH-04 REVIEW. A workbook that leaves those inputs out of its own ledger
    # still has to account for the exceptions on its closing page: omitting the
    # input is not a way to close the finding, and a closing page that declares an
    # unqualified pass is no more defensible for having recorded less.
    src_open = set()
    if (src.get("s_trial") is not None and src.get("smax_reported") is not None
            and src["s_trial"] > src["smax_reported"]):
        src_open.add("FAIL")
    if (src.get("d_shear") is not None and src.get("d_flexure") is not None
            and abs(src["d_shear"] - src["d_flexure"]) > 1e-9):
        src_open.add("REVIEW")
    truth_open = {s for s in expected.values() if s in OPEN} | src_open
    # A closing page must state a controlled disposition, and that disposition may
    # not be a clean pass while the recomputed relations still hold an open item.
    # Nor may the sentence beside it: a page whose status cell says REVIEW while
    # its own words say nothing is outstanding has not closed anything, and the
    # words are what gets read. Silence on the closing page still costs nothing.
    # Read the disposition statement, not the whole page. A close-out sheet also
    # carries scope notes, a check table and corrective actions; folding all of
    # that into one polarity turns a thorough summary into a claim it never made.
    # The sentence that matters is the one printed beside the declared
    # disposition, so only rows carrying a controlled status or labelled as the
    # disposition are read.
    summary_text = ""
    if summary_ws is not None:
        named, fallback = [], []
        # With the values resolved, a computed disposition IS the sentence the page
        # prints - a close-out may state "HOLD PENDING EVIDENCE CLOSE-OUT." through
        # an IF - so the rows are read as shown.  A count roll-up contributes
        # nothing: only string cells longer than 12 characters are read.
        for r in rows(summary_ws)[1:]:
            label = norm(r[0] if r else "")
            is_disposition = any(w in label for w in DISPOSITION_LABELS)
            text = [str(c) for c in r if isinstance(c, str) and not c.startswith("=") and len(c) > 12]
            if is_disposition:
                named += text
            elif any(exact_status(c) for c in r):
                fallback += text
        # A closing page usually restates the whole check table; reading all of it
        # would drown the disposition in per-check phrasing. Use the rows that are
        # labelled as the disposition when the page has any, and fall back to the
        # status-bearing rows only when it does not.
        summary_text = ". ".join(named or fallback)
    summary_claim = claim_polarity(summary_text)
    # RUBRIC, D06: the close-out fails when "it declares an unqualified pass,
    # carries no open disposition, or never mentions the open status".  Both facts
    # are decidable from the controlled statuses the page declares and mentions, so
    # those are what decide it.  Whether the page's prose sounds like a pass is not
    # decidable that way, so summary_claim is reported in the detail and does not
    # enter the score.
    summary_ok = (not truth_open) or bool(declared & truth_open)
    verdict_factor = (register_factor * sheet_factor * narrative_factor * coherence_factor
                      * (1.0 if summary_ok else 0.0))
    # RUBRIC, shear: "treats the failed trial spacing as a real finding"; findings:
    # "decide ... when the depth change or missing detailing support requires a
    # conditional status". The exceptions are what the review exists to produce,
    # so a dimension whose own open verdict the workbook reverses does not keep a
    # proportional share of that dimension - the capability it is scored for was
    # not exercised. Checks that the relations show as PASS cost their share only.
    # The same evidence standard decides withholding credit as decides charging.
    # `wrong` drives D07 and the proportional factors below, so a check that is not
    # sound enough to charge is not sound enough to withhold credit either.
    wrong = {k for k, _ in CHECKS
             if k in chargeable and (published.get(k) != expected[k] or not narrative_ok[k])}
    open_keys = [k for k, _ in CHECKS if expected.get(k) in OPEN]
    open_kept = sum(1 for k in open_keys if k not in wrong)
    open_fidelity = open_kept / len(open_keys) if open_keys else 1.0
    findings *= open_fidelity

    lc = find_sheet(book, ["loadcombinations", "loadcombo", "actions"])
    lrows = rows(lc) if lc else []
    lraws = raw_rows(lc) if lc else []
    li = next((i for i in range(1, len(lrows)) if "uls" in row_text(lrows[i]).lower()
               or "gravity" in row_text(lrows[i]).lower()), 1 if len(lrows) > 1 else None)
    lrow = lrows[li] if li is not None else []
    # how the row is written is a property of the formula text, so the trace is read
    # from the raw grid, not from the resolved values.
    lraw = lraws[li] if li is not None and li < len(lraws) else []
    lform = " ".join(str(x) for x in lraw if isinstance(x,str) and x.startswith("="))
    wu = (vals["dead_factor"] or 0)*(vals["dead_load"] or 0)+(vals["live_factor"] or 0)*(vals["live_load"] or 0)
    expected_mu = wu*(vals["span"] or 0)**2/8*12
    v_at_d = (wu*(vals["span"] or 0)/2 - wu*(vals["d_shear"] or 0)/12) if vals["span"] and vals["d_shear"] else None
    load_parts = [
      bool(populated_rows([lrow] if lrow else [])),
      bool(re.search(r"Source_Inputs!", lform)) or bool(re.search(r"!\$?[A-Z]", lform)),
      # Equivalent square forms (B5^2, B5*B5, or a named span) are all valid;
      # the independently recomputed Mu check below remains authoritative.
      bool(re.search(r"\^2|span|\b[A-Z]{1,3}\$?\d+\s*\*\s*[A-Z]{1,3}\$?\d+", lform, re.I)),
      agrees(expected_mu, vals["Mu_reported"], .01),
      agrees(vals["dead_factor"], src.get("dead_factor"), 1e-6),
      agrees(vals["live_factor"], src.get("live_factor"), 1e-6),
      agrees(v_at_d, vals["Vu_reported"], .01),
    ]

    # Flexure and shear are scored on quantities, not on vocabulary. Every atom
    # below is a number the verifier recomputes from the evidence sheet and
    # compares with what the workbook reports; a sheet that merely carries the
    # words "equilibrium", "nominal moment" or "strain" earns nothing for them.
    identity_gate_value = 1.0 if len(source_match) >= 4 else 0.0
    fx = find_sheet(book, ["flexure", "momentstrength", "bending"]); frows = populated_rows(rows(fx)) if fx else []
    fform = [x for x in all_formula_cells(book) if x[0] == (fx.title if fx else "")]
    fx_parts = [
      len(fform) >= 8,
      any("!" in f[2] for f in fform),
      bool(fx_chain) and agrees(vals["c_solution"], fx_chain["c"], .02),
      bool(fx_chain) and abs(fx_chain["resid"]) <= .01*abs(fx_chain["T"]),
      bool(fx_chain) and agrees(fx_chain["Mn"], vals["Mn_reported"], .03),
      bool(fx_chain) and agrees(fx_chain["phiMn"], vals["phiMn_reported"], .03),
      bool(fx_chain) and agrees(fx_chain["eps_t"], vals["eps_t_reported"], .03),
      bool(fx_chain) and vals["Mu_reported"] is not None and fx_chain["phiMn"] >= vals["Mu_reported"],
      vals["As_tension"] is not None and vals["As_required_reported"] is not None and vals["As_tension"] >= vals["As_required_reported"],
    ]

    sh = find_sheet(book, ["shear", "shearstrength", "stirrups"]); srows = populated_rows(rows(sh)) if sh else []
    sraw = raw_rows(sh) if sh else []
    sform = [x for x in all_formula_cells(book) if x[0] == (sh.title if sh else "")]
    # Formula 15 must carry the governing concrete contribution into the
    # section ceiling.  Checking only the resolved number would let a workbook
    # copy the article's erroneous 105.04-kip arithmetic while claiming an
    # independent verification.  Accept a direct Vc cell reference (the
    # reference workbook uses B5) or a named Vc/concrete term.
    vc_rows = []
    for field in ("Vc_a_reported", "Vc_b_reported", "Vc_c_reported"):
        rec = inp.get(field)
        if rec and rec.get("sheet") == inp_ws.title:
            vc_rows.append(rec.get("row"))
    vc_refs = [f"source_inputs!$b${r}" for r in vc_rows if r]
    vc_source_rows = {
        (norm(rec.get("sheet")), int(rec.get("row")))
        for rec in ledger_entries
        if rec.get("row") and re.search(
            r"\bvc\b|governing.{0,20}(?:concrete|shear)|concrete.{0,20}(?:contribution|shear)",
            str(rec.get("text", "")), re.I)
    }
    def formula_references_vc(formula):
        for sheet, row in re.findall(r"'?([^'!]+)'?!\$?[A-Z]{1,3}\$?(\d+)", formula):
            if (norm(sheet), int(row)) in vc_source_rows:
                return True
        return False
    ceiling_formulas = []
    for raw in sraw:
        label = " ".join(str(x or "") for x in raw[:2]).lower()
        if re.search(r"ceiling|section.*capacity|22\.5\.1\.2|max.*shear", label):
            ceiling_formulas.extend(str(x) for x in raw if isinstance(x, str) and x.startswith("="))
    ceiling_has_vc = any(
        re.search(r"\bvc\b|concrete", f, re.I)
        or any(ref in f.lower() for ref in vc_refs)
        or formula_references_vc(f)
        or any(field.startswith("Vc_") for field in row_fields(
            [f], inp_ws.title if inp_ws is not None else None, rowfields))
        for f in ceiling_formulas
    )
    sh_parts = [
      len(srows) >= 8,
      len(sform) >= 7,
      sh_chain.get("n_candidates", 0) >= 3 and sh_chain.get("Vc") is not None,
      agrees(sh_chain.get("Vs_trial"), vals["Vs_trial_reported"], .03),
      agrees(sh_chain.get("Vs_adopted"), vals["Vs_adopted_reported"], .03),
      agrees(sh_chain.get("Vn_adopted"), vals["Vn_adopted_reported"], .03),
      ceiling_has_vc and agrees(sh_chain.get("Vn_ceiling"), vals["Vn_max_reported"], .03),
      vals["s_trial"] is not None and vals["smax_reported"] is not None and vals["s_trial"] > vals["smax_reported"],
      vals["s_adopted"] is not None and vals["smax_reported"] is not None and vals["s_adopted"] <= vals["smax_reported"],
      sh_chain.get("Vs_required") is not None and sh_chain.get("Vs_adopted") is not None and sh_chain["Vs_adopted"] >= sh_chain["Vs_required"],
    ]

    formulas = all_formula_cells(book); cross=[f for f in formulas if "!" in f[2]]; external=[f for f in formulas if "[" in f[2] or "http" in f[2].lower()]

    fd_rows = rows(fd) if fd is not None else []
    fd_header, fd_roles = finding_header_roles(fd_rows)
    closure_source = fd_rows[(fd_header + 1 if fd_header is not None else 1):]
    closure_rows = populated_rows([r for r in closure_source if r and len(r) >= 3])
    # RUBRIC: "status checks accept leading controlled terms and equivalent
    # professional qualifiers", so a register that writes Accepted / Rejected /
    # Held for review closes just as well as one that writes the bare tokens.
    #
    # RUBRIC, presentation tolerance: "The request names the deliverable and its
    # content, not a tab vocabulary, a column order, a row-label vocabulary or a unit
    # system, so none of those is scored ... Synonym and layout variants should
    # preserve the score." A register that puts its status second and its rationale
    # last is closing out just as completely, so the three columns are found from the
    # header row, as the evidence ledger's already are.
    cl_status = fd_roles.get("status", [])
    cl_loc = fd_roles.get("locator", [])
    cl_rat = fd_roles.get("rationale", [])
    cl_status = cl_status or [2]
    cl_loc = cl_loc or [4]
    cl_rat = cl_rat or [5]

    def filled(r, cols):
        return any(c < len(r) and str(r[c] or "").strip() for c in cols)

    def closed(r):
        got = next((s for s in (leading_status(r[c]) for c in cl_status if c < len(r)) if s), None)
        return got in STATUS and filled(r, cl_loc) and filled(r, cl_rat)

    import semantic_judge as sj
    candidates = [(i,r) for i,r in enumerate(closure_rows) if closed(r)]
    rationale_verdict = None
    fractions = {}
    if candidates:
        sj.RULES = {"ROW_%03d"%i:
            "Binary: this register row contains an actual explanatory rationale linking its identified engineering check, evidence or calculation to the stated disposition, action or unresolved boundary. A Finding_ID, check name, status, source locator, generic 'checked' statement or empty text alone is NOT a reason. Accept concise professional equivalents and formulas explained by the row. Judge this row only against supplied beam evidence, do not borrow another row's explanation."
            for i,r in candidates}
        candidate = "\n".join("ROW_%03d: "%i + json.dumps(r,ensure_ascii=False,default=str) for i,r in candidates)
        try:
            rationale_verdict = sj.adjudicate(candidate,(Path(__file__).parent/"semantic_source.json").read_text())
        except Exception as exc:
            raise SemanticInfrastructureError("required rationale adjudication failed") from exc
        fractions={i:rationale_verdict["items"]["ROW_%03d"%i]["fraction"] for i,r in candidates}
    closure = sum(fractions.values())/max(1,len(closure_rows))
    # How completely the register closes out, before the two conditions below decide
    # whether the close-out itself stands.
    closure_complete = closure
    # The closing page has to account for every open status the review leaves behind.
    if truth_open and not truth_open <= mentioned:
        closure = 0.0
    # RUBRIC, delivery closure: "whether the summary is defensible given non-PASS
    # rows". A close-out that no longer carries one of the exceptions is not.
    if open_kept < len(open_keys):
        closure = 0.0

    # ----------------------------------------------------------------------
    # pd-ledger-v1 settlement.
    #
    # Positive completion carries the *proportional* factors that scale each item -
    # a coverage fraction is not damage. Every discrete gate is a deduction item
    # instead, so what a gate costs is a coefficient rather than an all-or-nothing
    # multiplier folded into one item's completion.
    # ----------------------------------------------------------------------
    external = [f for f in all_formula_cells(book) if "[" in f[2] or "http" in f[2].lower()]
    dim_prop = {}
    for dim, keys in DIMENSION_CHECKS.items():
        live = [k for k in keys if expected.get(k)]
        dim_prop[dim] = 1.0 if not live else 1.0 - sum(1 for k in live if k in wrong) / len(live)
    # The three calculation groups are split along the reference's own anchors
    # (RUBRIC: the load group reconciles the combination *and* checks the
    # factor-weighted actions; flexure decides the strain state, resolves the
    # reported capacity and decides whether the reinforcement comparison applies;
    # shear preserves the candidates, recomputes the capacities and decides the
    # spacing). Each item is the mean of the atoms that state its part of that
    # chain, scaled by the proportional factor of the group it belongs to.
    def group(atoms, idx):
        return sum(1.0 for i in idx if atoms[i]) / len(idx)
    lp, fp, sp = load_parts, fx_parts, sh_parts
    ledger_completion = {
        "P01": evidence,
        "P02": group(lp, (0, 1, 2, 3, 6)) * dim_prop["load_combination"],
        "P03": group(lp, (4, 5)) * dim_prop["load_combination"],
        "P04": group(fp, (0, 1, 2, 3)) * dim_prop["flexure"],
        "P05": group(fp, (4, 5)) * dim_prop["flexure"],
        "P06": group(fp, (6, 7, 8)) * dim_prop["flexure"],
        "P07": group(sp, (0, 1, 2)) * dim_prop["shear"],
        "P08": group(sp, (3, 4, 5, 6)) * dim_prop["shear"],
        "P09": group(sp, (7, 8, 9)) * dim_prop["shear"],
        "P10": findings,
        "P11": closure_complete,
        "P12": ledger_evidence(ledger_entries, "P12"),
        "P13": ledger_evidence(ledger_entries, "P13"),
        "P14": ledger_evidence(ledger_entries, "P14"),
        "P15": ledger_evidence(ledger_entries, "P15"),
        "P16": ledger_evidence(ledger_entries, "P16"),
    }
    damage = []
    if identity_gate_value == 0.0:
        damage.append({"key": "workbook:inputs_are_not_this_beam", "item_ids": ["D01"]})
    for k in register_wrong:
        damage.append({"key": "check:%s:register_contradicts_relation" % k, "item_ids": ["D02"]})
    for k in incoherent:
        # Same decision as D02: the published status contradicts the workbook's own
        # arithmetic; the calculation sheet is simply where the arithmetic is shown.
        damage.append({"key": "check:%s:register_contradicts_calculation_sheet" % k, "item_ids": ["D05"]})
    if not summary_ok:
        damage.append({"key": "summary:disposition_not_defensible", "item_ids": ["D06"]})
    for k in sorted(k for k in open_keys if k in wrong and k in chargeable):
        damage.append({"key": "check:%s:open_verdict_reversed" % k, "item_ids": ["D07"]})
    if truth_open and not truth_open <= mentioned:
        # Same decision as D06: the close-out does not account for the exceptions the
        # review leaves behind, whether by declaring a clean pass or by silence.
        damage.append({"key": "summary:open_status_unmentioned", "item_ids": ["D06"]})
    # The brief: "Using only the materials available under /workspace ... Do not use
    # information that is not supplied under /workspace", and RUBRIC, delivery
    # closure: "whether the workbook is usable offline". A formula that links to
    # another workbook or fetches a URL breaks both.
    for cell in external:
        damage.append({"key": "formula:%s!%s:external_reference" % (cell[0], cell[1]), "item_ids": ["D10"]})

    # Closure columns are reusable by any beam-review workbook. They count as closed
    # out only once the workbook carries THIS beam's geometry, materials and reported
    # actions, taken from the supplied article and PDF, and only to the extent the
    # conclusions drawn from the calculations agree with them.
    identity_gate = identity_gate_value
    closure *= identity_gate * verdict_factor

    # Lenient lens (see LENIENT_REQUIRED_ITEMS at the top of this file): the few
    # must-do conclusions, each read from the atom the strict scorer already
    # decided, each binary, all of them required.
    lenient_items = {
        "inputs_are_this_beam": bool(identity_gate_value),
        "factored_actions_reproduced": bool(load_parts[3]) and bool(load_parts[6]),
        "flexural_capacity_reproduced": bool(fx_parts[4]) and bool(fx_parts[5]),
        "governing_shear_candidate": bool(sh_parts[2]),
        "formula15_vc_term": bool(sh_parts[6]),
        "section_capacity_reproduced": bool(sh_parts[6]) and expected.get("SH-05") == "PASS" and published.get("SH-05") == "PASS",
        "open_verdicts_intact": open_kept == len(open_keys),
    }
    lenient = 1.0 if all(lenient_items[k] for k in LENIENT_REQUIRED_ITEMS) else 0.0
    detail = {"rationale_semantic_judge":rationale_verdict,"ledger_completion":ledger_completion,"ledger_damage":damage,
              "dimension_proportional_factor":dim_prop,"lenient":lenient,
              "lenient_required_items":LENIENT_REQUIRED_ITEMS,"lenient_items":lenient_items,
              "formula_counts":{"total":len(formulas),"cross_sheet":len(cross),"external":len(external)},
              "input_complete":complete,"source_anchor_matches":len(source_match),"identity_gate":identity_gate,
              "inputs_resolved":{k:v for k,v in vals.items()},"source_anchors_matched":sorted(source_match),
              "finding_hits":hits,"finding_total":len(CHECKS),
              "recomputed_verdicts":expected,"published_verdicts":published,"register_rows_matched":matched_rows,
              "verdict_factor":verdict_factor,"register_factor":register_factor,"sheet_factor":sheet_factor,
              "narrative_factor":narrative_factor,"written_findings":narrative,"summary_claim":summary_claim,"summary_text":summary_text[:900],
              "coherence_factor":coherence_factor,"register_vs_sheet_conflicts":incoherent,
              "register_vs_rationale_conflicts":row_conflict,
              "open_verdicts_kept":open_kept,"open_verdicts":open_keys,
              "register_contradicted":register_contradicted,"relation_rows_recognised":recognised,
              "relation_rows_contradicted":sheet_contradicted,"relation_row_detail":sheet_detail,
              "summary_declared":sorted(declared),"summary_mentioned":sorted(mentioned),
              "open_items":sorted(truth_open),"summary_consistent":summary_ok,
              "atoms":{"load":[bool(p) for p in load_parts],"flexure":[bool(p) for p in fx_parts],"shear":[bool(p) for p in sh_parts]}}
    return lenient, detail

def main(path):
    try:
        wb=_guard_workbook(openpyxl.load_workbook(path, data_only=False, read_only=False))
        lenient,detail=score_book(wb)
    except Exception as exc:
        if isinstance(exc, SemanticInfrastructureError):
            sys.stderr.write("Required semantic judgement failed; no score published\n")
            raise SystemExit(2)
        lenient=0.0; detail={"error":str(exc)}
    return {"rewards":{"lenient":lenient},"detail":detail}


def deliverable(arg):
    """The contract passes a directory (rollout artifacts/ or task golden/); the container passes the file."""
    p = Path(arg)
    if not p.is_dir():
        return p
    named = p / "beam_review.xlsx"
    if named.is_file():
        return named
    found = sorted(p.rglob("beam_review.xlsx")) or sorted(p.rglob("*.xlsx"))
    return found[0] if found else named


def settle(result):
    """Settle the scored detail into the pd-ledger-v1 strict score."""
    params = json.loads(PARAMS.read_text(encoding="utf-8"))
    weights, coefficients = params["positive_weights"], params["deduction_coefficients"]
    led = result["detail"].get("ledger_completion", {})
    completion = {k: min(1.0, max(0.0, float(led.get(k, 0.0) or 0.0))) for k in weights}
    instances = [d for d in result["detail"].get("ledger_damage", []) if
                 all(i in coefficients for i in d["item_ids"])]
    earned = sum(weights[k] * completion[k] for k in weights)
    retention = math.prod(min(coefficients[i] for i in inst["item_ids"]) for inst in instances)
    final = earned * retention
    result["reward"] = final
    result["rewards"]["strict"] = final
    result["reward_formulas"] = {
        "strict": "positive_earned * retention (pd-ledger-v1; weights and coefficients from scoring_params.json)",
        "lenient": "1 only if every must-do item in LENIENT_REQUIRED_ITEMS holds "
                   "(inputs bound to this beam, factored actions reproduced, reported "
                   "flexural capacity reproduced, governing shear candidate identified, "
                   "open verdicts not reversed); each item binary, read from the strict "
                   "scorer's own per-atom results"}
    result["scoring_ledger"] = {"schema_version": "pd-ledger-v1", "positive_completion": completion,
                                "damage_instances": instances, "positive_earned": earned,
                                "retention": retention, "final_score": final}
    return result


if __name__ == "__main__":
    print(json.dumps(settle(main(deliverable(sys.argv[1] if len(sys.argv)>1 else "/workspace/beam_review.xlsx"))), indent=2))
