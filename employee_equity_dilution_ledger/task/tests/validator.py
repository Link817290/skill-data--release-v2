#!/usr/bin/env python3
"""Semantic verifier for the employee equity dilution workbook (pd-ledger-v1).

Usage: validator.py <path>  (the workbook employee_equity_dilution_ledger.xlsx, as test.sh passes it, or a directory
holding it, such as rollout artifacts/ or task golden/).

The strict score is settled in the standard form

  final = positive_earned * retention
  positive_earned = sum(weight[i] * completion[i]) over the positive items R01-R16
                                                        (weights from scoring_params.json or $SCORING_PARAMS)
  retention = prod over damage instances of min(coefficient[D] for D in the instance)

completion[i] is the share of the Golden cells item i stands for that the workbook carries on a row the
item itself names; the item set is SCORED_ITEMS below. Damage instances: D01 the structure gate,
one instance when a required sheet (inputs, awards, exercise, dilution summary, checks) is missing, after
which the dimensions are computed anyway with an empty sheet in place of each missing one; D02-D05 one
instance each for a judgment the workbook states in the inverted direction; D06-D11 the brief-level checks
in brief_damage (one D06 instance per give-away unit missing, D07 external source, D08 non-English text,
D09 units or reporting date missing, D10 deliverable under another name,
D11 no cross-sheet formula).

The lenient lens is the must-do contract (LENIENT_REQUIRED_ITEMS): 1 when every listed positive item is
complete and no listed deduction item is charged, otherwise 0.
"""
from __future__ import annotations
import json, math, re, sys, unicodedata
from pathlib import Path
import os
from openpyxl import Workbook, load_workbook

# --- disowned-unit guard (2026-09-22 audit repair, narrowed 2026-09-23) --------------------------
# A unit the submission itself withdraws is not an assertion. The withdrawal must GOVERN THE WHOLE
# UNIT, so the cue is anchored at the start of the unit (after any bullet, quote or table marker) or
# is a quote-and-reject wrapper around it. An unanchored match charges correct work: one AML review
# wrote "it is expressly not asserted as structuring on the present record" — a careful, correct
# finding about a different allegation — and an unanchored guard blanked the whole value, costing
# three rollouts real points (opus_ws 0.4942 -> 0.3451). Domain words such as "rejected",
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


ROOT = Path(__file__).resolve().parent
GT = json.loads((ROOT / "ground_truth.json").read_text())
TOL = 0.015

def norm(v):
    return re.sub(r"[^a-z0-9]+", " ", str(v or "").lower()).strip()

def num(v):
    if isinstance(v, bool) or v is None or v == "": return None
    if isinstance(v, (int, float)): return float(v)
    s = str(v).strip().replace(",", "").replace("$", "").replace("(", "-").replace(")", "")
    try: return float(s.rstrip("%")) / (100 if str(v).strip().endswith("%") else 1)
    except Exception: return None

def sheet_like(wb, words):
    for ws in wb.worksheets:
        if any(w in norm(ws.title) for w in words): return ws
    return None

HEADER_WORDS = ["field","value","award class","beginning","population","options exercised","metric","base",
                "maximum","units","formula","check","status","difference","issue","decision","evidence",
                "rationale","class","opening","ending","closing","grant","exercis","forfeit","expir","price",
                "movement","control","source","locator","note","name","item","id","amount","shares","unit"]

def header_row_score(cells):
    """How much a row looks like a header row rather than a data row.

    A header row is short labels: mostly text, few numbers, nothing sentence-length; a data row read
    as a header would have every value below it measured against a "header" that is itself a value.
    Rows are scanned in order and the first row that both clears the keyword bar and looks like
    labels wins."""
    filled = [c for c in cells if c not in (None, "")]
    if len(filled) < 2: return -1
    labels = [c for c in filled if isinstance(c, str)]
    if len(labels) < 2 or len(labels) < 0.6 * len(filled): return -1
    if sum(1 for c in labels if len(c) > 60) > 0: return -1
    hits = sum(any(k in norm(c) for k in HEADER_WORDS) for c in labels)
    if hits < 2: return -1
    return hits

def table(ws):
    best = None
    for row in ws.iter_rows():
        raw = [c.value for c in row]
        score = header_row_score(raw)
        if score < 0: continue
        headers = {v: i for i, v in enumerate(norm(c) for c in raw) if v}
        return row[0].row, headers
    return 1, {}

def col(headers, candidates, default=None, strict=False):
    """The column a candidate name points at.

    Two rules, both from the instruction's wording rather than from Golden's spelling. (1) An exact
    field name beats a longer alias that merely contains it, and among partial matches the shortest
    header wins, so 'Normalized value' is not beaten by 'Raw reported value' standing to its left,
    and 'Calculated 12/31/24' is not beaten by 'WA closing'. (2) With `strict`, a positional default
    is used only when no header row was found at all; a detected header row that names no such column
    means the column is absent, instead of silently reading whichever column happens to sit at the
    default index."""
    if headers:
        exact = [i for h, i in headers.items() if h in candidates]
        if exact: return min(exact)
        ranked = cols_ranked(headers, candidates)
        if ranked: return ranked[0]
        if strict: return None
    return default

def cols_ranked(headers, candidates):
    """Every column a candidate name points at, best first.

    Candidates are ordered by specificity by their caller, and that order decides: 'normalized value'
    beats a bare 'value', and both beat 'raw reported value' standing to their left. Within one
    candidate a header that *starts* with it beats one that merely contains it, then the shorter
    header, then the leftmost column."""
    out = []
    for rank, cand in enumerate(candidates):
        for h, i in headers.items():
            if cand in h and i not in [x[-1] for x in out]:
                out.append((rank, 0 if h.startswith(cand) else 1, len(h), i))
    return [i for *_, i in sorted(out)]

def exercise_share_column(headers):
    """Identify exercise units; a bare 'shares' must not select a vesting column."""
    aliases=["options exercised", "option exercise shares", "shares exercised", "exercise shares", "exercised options", "options exercise"]
    eligible={h:i for h,i in headers.items()
              if re.search(r"\bexercis(?:e|ed|es|ing)\b", h)
              and re.search(r"\b(?:shares?|options?)\b", h)
              and not re.search(r"\b(?:price|prices|proceeds|withheld|withholding|tax|vested|vesting|value|dollar|usd)\b", h)}
    ranked=cols_ranked(eligible,aliases)
    if ranked:return ranked[0]
    return next(iter(eligible.values())) if len(eligible)==1 else None


def rows(ws):
    head, headers = table(ws)
    return head, headers, list(ws.iter_rows(min_row=head+1, values_only=False))

class Eval:
    def __init__(self, wb):
        self.wb = wb; self.cache = {}; self.stack = set()
    def cell(self, ws, coord):
        key=(ws.title,coord)
        if key in self.cache: return self.cache[key]
        c=ws[coord]; v=c.value
        if isinstance(v,str) and v.startswith("="):
            v=self.formula(ws,v[1:])
        else: v=num(v) if isinstance(v,str) and re.match(r"^[($\-\d]",v) else v
        self.cache[key]=v; return v
    def formula(self, ws, f):
        f=f.replace('"PASS"','1').replace('"FAIL"','0')
        # Resolve same-sheet SUM ranges before resolving individual cells.
        def sum_range(m):
            start, end = m.group(1), m.group(2)
            ma, mb = re.match(r"([A-Z]+)(\d+)", start), re.match(r"([A-Z]+)(\d+)", end)
            if not (ma and mb and ma.group(1) == mb.group(1)): return "0"
            return str(sum((num(self.cell(ws, ma.group(1)+str(r))) or 0) for r in range(int(ma.group(2)), int(mb.group(2))+1)))
        f=re.sub(r"SUM\(\s*([A-Z]+\d+)\s*:\s*([A-Z]+\d+)\s*\)", sum_range, f, flags=re.I)
        # Resolve simple sheet/range references before evaluating arithmetic.
        def ref(m):
            sh, co=m.group(1),m.group(2); return repr(self.cell(self.wb[sh],co) or 0)
        f=re.sub(r"(?:'([^']+)'|([A-Za-z_][A-Za-z0-9_ ]*))!\$?([A-Z]+)\$?(\d+)", lambda m: repr(self.cell(self.wb[m.group(1) or m.group(2)],m.group(3)+m.group(4)) or 0), f)
        f=re.sub(r"\b([A-Z]+)\$?(\d+)\b", lambda m: repr(self.cell(ws,m.group(1)+m.group(2)) or 0), f)
        def rewrite_call(expr, name, render):
            """Rewrite balanced calls, including nested IF(...,MAX(...),...)."""
            needle = name.upper() + "("
            while True:
                start = expr.rfind(needle)
                if start < 0: return expr
                depth = 0; end = None
                for i in range(start + len(name), len(expr)):
                    if expr[i] == "(": depth += 1
                    elif expr[i] == ")":
                        depth -= 1
                        if depth == 0:
                            end = i; break
                if end is None: return expr
                body = expr[start + len(needle):end]
                args=[]; mark=0; depth=0
                for i,ch in enumerate(body):
                    if ch == "(": depth += 1
                    elif ch == ")": depth -= 1
                    elif ch == "," and depth == 0:
                        args.append(body[mark:i]); mark=i+1
                args.append(body[mark:])
                replacement = render(args)
                if replacement is None: return expr
                expr = expr[:start] + replacement + expr[end+1:]
        f=rewrite_call(f,"MAX",lambda a: "max("+",".join(a)+")" if a else None)
        f=rewrite_call(f,"ABS",lambda a: "abs("+a[0]+")" if len(a)==1 else None)
        f=rewrite_call(f,"IF",lambda a: f"({a[1]} if ({a[0]}) else {a[2]})" if len(a)==3 else None)
        try: return eval(f, {"__builtins__":{}}, {"max":max,"abs":abs})
        except Exception: return None
    def value(self, ws, c):
        v=c.value
        if isinstance(v,str) and v.startswith("="): return self.formula(ws,v[1:])
        return num(v) if isinstance(v,str) else v

def close(a,b,tol=TOL):
    a,b=num(a),num(b)
    return a is not None and b is not None and abs(a-b) <= max(tol, abs(b)*1e-6)

def available_pool_close(value):
    """Accept the exact plan-table figure and its disclosed rounded 13.1 million form."""
    return close(value, 13059834, 0.5) or close(value, 13100000, 0.5)

def main(path):
    try: wbv=_guard_workbook(load_workbook(path, data_only=False))
    except Exception as e: return {"reward":0.0,"rewards":{"strict":0.0,"lenient":0.0},"reward_formulas":{"strict":"weighted dimensions","lenient":"contract"},"error":f"unreadable workbook: {e}"}
    wb=_guard_workbook(load_workbook(path, data_only=True)); ev=Eval(wbv)
    detail={"dimensions":{},"missing":[],"notes":[]}
    inputs=sheet_like(wbv,["input","source"]); awards=sheet_like(wbv,["award","roll","equity"]); ex=sheet_like(wbv,["exercise","vesting"]); summ=sheet_like(wbv,["dilution","summary"]); checks=sheet_like(wbv,["check","control"])
    structure=all([inputs,awards,ex,summ,checks]); detail["dimensions"]["structure"]=1.0 if structure else 0.0
    gate_result=None
    if not structure:
        gate_result={"reward":0.0,"rewards":{"strict":0.0,"lenient":0.0},"reward_formulas":{"strict":"weighted dimensions","lenient":"contract"},"details":json.loads(json.dumps(detail))}
        # Settlement guard (pd-ledger-v1): the dimensions are computed below, with an empty sheet
        # standing in for each missing one, so the D01 gate coefficient acts on real earned credit.
        _blank=Workbook().active
        inputs=inputs or _blank; awards=awards or _blank; ex=ex or _blank; summ=summ or _blank

    # The instruction publishes no column-header contract, so the descriptive
    # column is located by meaning: any header that names a fact/description
    # column, else the first non-empty text column.
    LABEL_HEADERS=["field","item","name","fact","description","label","metric","measure","parameter","line","input","movement"]
    # The fact is the normalized, exact-share figure. `equity-award-rollforward` 1.2
    # binds the reader: "Keep exact shares separate from values reported in millions; record the scale
    # explicitly in the input sheet." So a column that names the normalized or exact value is read
    # before a bare "value", and both before the raw, as-reported column that carries the source's own
    # scale ("Raw reported value" = 13.1 for $13.1 million). Where the preferred column is empty on a
    # row, the next-ranked value column answers for it.
    VALUE_HEADERS=["normalized value","normalised value","normalized fact","exact value","exact shares",
                   "value","amount","figure"]
    def input_map(ws):
        head,hdr,rr=rows(ws); lc=col(hdr,LABEL_HEADERS,0)
        vcs=cols_ranked(hdr,VALUE_HEADERS) or ([1] if not hdr else [])
        out={}
        def value(rrw):
            first=True
            for i in vcs:
                if i>=len(rrw): continue
                v=ev.value(ws,rrw[i])
                if v in (None,""): continue
                # the best-named column answers whatever it holds; a lower-ranked one stands in only
                # when it carries a figure, so a units or note column never becomes the value
                if first or num(v) is not None: return v
                first=False
            return None
        for rrw in rr:
            v=value(rrw)
            label=norm(rrw[lc].value if lc is not None and lc < len(rrw) else "")
            if label: out.setdefault(label, v)
            # a short identifier column ("Key", "Ref") is not the descriptive one;
            # index every text cell on the row against the same value so either
            # presentation resolves.
            for i,c in enumerate(rrw):
                if i in vcs or not isinstance(c.value,str): continue
                lab=norm(c.value)
                if lab and len(lab)>=8: out.setdefault(lab, v)
        return out
    im=input_map(inputs)
    aliases={"authorized_pool":["authorized pool","maximum number","max pool"],"available_pool":["available for future","available pool"],"basic_shares":["basic weighted","weighted average shares"],"closing_price":["closing price","market price"],"psu_max_factor":["psu maximum","maximum factor"],"option_pool_multiplier":["option pool"],"full_value_pool_multiplier":["full value pool","full value multiplier"],"aggregate_options_exercised":["aggregate options exercised","options exercised"],"aggregate_cash":["aggregate option cash","cash proceeds"],"aggregate_intrinsic":["aggregate option intrinsic","intrinsic value"],"maximum_outstanding_securities":["maximum outstanding securities","maximum number of securities"]}
    got=0
    for key, names in aliases.items():
        found=next((v for lab,v in im.items() if any(n in lab for n in names)),None)
        if close(found,GT["inputs"][key],0.03): got+=1
    detail["dimensions"]["source_facts"]=got/len(aliases)

    head,hdr,rr=rows(awards); lc=col(hdr,["award class","class","instrument"],0)
    # ---- Roll-forward column resolution ------------------------------------------
    # `equity-award-rollforward` 2.1 asks for "distinct state columns for beginning balance, grants,
    # exercises or settlements, vesting, forfeitures, expirations, and ending balance", and 1.4 for the
    # reporting date. The reader recognises the columns by those states, however the ledger spells
    # them, rather than by Golden's own header text:
    #   * a header that names a price ("weighted average", "WA ...", "fair value", "strike") is a price
    #     column and can never stand in for a unit column;
    #   * the two balances may be named by the reporting date alone ("Opening 12/31/23",
    #     "Calculated 12/31/24"), the form the class-in-column reader below already accepts;
    #   * where a ledger splits one reference movement over several columns ("Exercises" and "Vested",
    #     "Grants" and "Other additions"), the movement is read from whichever of them the class row
    #     actually fills, because Golden states them as one movement ("Exercises/vests").
    UNIT_ALIASES={
        "beginning":["beginning","opening","balance at","outstanding at december 31 2023",
                     "unvested at december 31 2023","12 31 23","12 31 2023","2023 12 31"],
        "grants":["grant","granted","additions","award"],
        "exercises":["exercis","vest","settle","release"],
        "forfeitures":["forfeit","cancel"],
        "expirations":["expir","lapse"],
        "ending":["ending","closing","calculated","recomputed","outstanding at december 31 2024",
                  "unvested at december 31 2024","12 31 24","12 31 2024","2024 12 31"],
    }
    PRICE_WORDS=("weighted average","weighted avg","wtd avg","weighted","fair value","price","strike")
    def is_price_header(h):
        return any(w in h for w in PRICE_WORDS) or h.startswith("wa ") or h == "wa" or h.startswith("w a ")
    unit_headers={h:i for h,i in hdr.items() if not is_price_header(h)}
    price_headers={h:i for h,i in hdr.items() if is_price_header(h)}
    def matches(headers,aliases):
        """Column indexes whose header names one of the aliases, ordered by alias specificity then
        by how squarely the header is that alias (prefix first, then shortest, then leftmost)."""
        out=[]
        for rank,a in enumerate(aliases):
            for h,i in headers.items():
                if a in h and i not in [x[-1] for x in out]:
                    out.append((rank, 0 if h.startswith(a) else 1, len(h), i))
        return [i for *_ ,i in sorted(out)]
    colsets={fld:matches(unit_headers,al) for fld,al in UNIT_ALIASES.items()}
    price_cols=matches(price_headers,["closing","ending","weighted average","weighted","fair value","price","strike"])
    if not price_cols: price_cols=sorted(price_headers.values())
    colsets["price"]=price_cols
    DEFAULTS={"beginning":1,"grants":2,"exercises":3,"forfeitures":4,"expirations":5,"ending":6,"price":7}
    if not hdr:  # no header row at all: fall back to the positional reading
        colsets={fld:[i] for fld,i in DEFAULTS.items()}
    def row_value(rw, fld, ws=None):
        """The first value the row actually carries in any column naming this movement."""
        for i in colsets.get(fld) or []:
            if i >= len(rw): continue
            v=num(ev.value(ws if ws is not None else awards, rw[i]))
            if v is not None: return v if fld in ("beginning","ending","price") else abs(v)
        return None
    # `cols` is kept for the shape the rest of the scorer expects; the readers use colsets.
    cols={fld:(idx[0] if idx else None) for fld,idx in colsets.items()}
    amap={}
    # Classes are named by abbreviation as often as in the plural ("OPT", "RSU", "PSU"). Match the
    # class as a word, not as the plural substring, so rows labelled OPT / RSU / PSU are found.
    CLASS_WORDS={"options":("option","options","opt","ssar","ssars"),
                 "rsus":("rsu","rsus","restricted stock","restricted share","time based"),
                 "psus":("psu","psus","performance share","performance unit","performance stock","performance based")}
    def names_class(lab,k):
        words=set(re.split(r"[^a-z0-9]+",lab))
        return any(a in words for a in CLASS_WORDS[k] if " " not in a) or any(a in lab for a in CLASS_WORDS[k] if " " in a)
    for rw in rr:
        lab=norm(rw[lc].value if lc is not None and lc < len(rw) else "")
        if not lab:
            lab=" ".join(norm(c.value) for c in rw[:3] if isinstance(c.value,str))
        for k in ("options","rsus","psus"):
            if names_class(lab,k): amap.setdefault(k,rw)

    # A roll-forward laid out with the award classes across the header and the
    # movements down the rows is the same statement; read it as well.  Movement
    # magnitudes are compared unsigned because presenting decreases as negative
    # is a presentation choice, not a different number.
    MOVE={"beginning":["beginning","opening","outstanding at december 31 2023","unvested at december 31 2023","balance at"],
          "grants":["grant","award","additions"],
          "exercises":["exercis","vest","settle","release"],
          "forfeitures":["forfeit","cancel"],
          "expirations":["expir","lapse"],
          "ending":["ending","closing","outstanding at december 31 2024","unvested at december 31 2024"],
          "price":["weighted average","weighted-average","price","fair value"]}
    CLASS={"options":["option","ssar"],"rsus":["rsu","restricted stock"],"psus":["psu","performance share","performance unit","performance stock"]}
    def transposed(k):
        """{movement: value} read from a class-in-column layout, or {}."""
        out={}
        for ws in wbv.worksheets:
            for row in ws.iter_rows():
                cells=[norm(c.value) for c in row]
                hits=[i for i,v in enumerate(cells) if any(a in v for a in CLASS[k])]
                if not hits: continue
                # one class per section is as ordinary as all three on one header
                # row; the `len(block)>=4` test below is what confirms the rows
                # underneath really are a roll-forward.
                unit_cols=[i for i in hits if "price" not in cells[i] and "fair value" not in cells[i] and "weighted" not in cells[i]]
                price_cols=[i for i in hits if i not in unit_cols]
                block={}
                for rw in ws.iter_rows(min_row=row[0].row+1):
                    lab=" ".join(norm(c.value) for c in rw[:3] if isinstance(c.value,str))
                    if not lab: continue
                    for fld,pats in MOVE.items():
                        if fld in block: continue
                        if not any(p in lab for p in pats): continue
                        src=price_cols if fld=="price" else unit_cols
                        for i in src:
                            if i<len(rw):
                                v=num(ev.value(ws,rw[i]))
                                if v is not None:
                                    block[fld]=v if fld in ("beginning","ending","price") else abs(v)
                                    break
                if len(block)>=4:
                    if len(block)>len(out): out=block
        return out
    def stacked(k):
        """{movement: value} read from a movement-per-row ledger, or {}.

        A movement-per-row ledger states the same roll-forward: one row per movement instead of one
        column. `equity-award-rollforward` 2.1 asks for distinct states, not for states in columns,
        so this is the same ledger and is read as one. The class is taken from the sheet title, from
        a class column on the row, or from the nearest heading above it."""
        out={}
        for ws in wbv.worksheets:
            title=norm(ws.title)
            current = k if any(a in title for a in CLASS[k]) else None
            block={}
            for rw in ws.iter_rows():
                texts=[norm(c.value) for c in rw if isinstance(c.value,str)]
                lab=" ".join(texts)
                if not lab: continue
                if any(a in lab for a in CLASS[k]): current=k
                elif any(any(a in lab for a in CLASS[o]) for o in CLASS if o!=k): current=None
                if current!=k: continue
                for fld,pats in MOVE.items():
                    if fld in block: continue
                    if not any(p in lab for p in pats): continue
                    for c in rw:
                        v=num(ev.value(ws,c))
                        if v is None or isinstance(c.value,str) and not re.match(r"^[($\-\d=]",str(c.value)): continue
                        if fld=="price" and abs(v)>1000: continue
                        if fld!="price" and abs(v)<1000 and v!=0: continue
                        block[fld]=v if fld in ("beginning","ending","price") else abs(v)
                        break
            if len(block)>len(out) and len(block)>=4: out=block
        return out
    def award_score(k):
        rw=amap.get(k); exp=GT["awards"][k]
        best=0.0
        if rw is not None:
            # A movement printed as a negative is the same movement; the class-in-column reader below
            # already compares magnitudes and the two paths must agree. Balances and prices stay signed.
            ok=sum(1 for fld in exp if close(row_value(rw,fld),exp[fld],0.03))
            best=ok/len(exp)
        if best>=0.999: return best
        for block in (transposed(k), stacked(k)):
            if not block: continue
            ok=sum(1 for fld in exp if fld in block and close(block[fld],exp[fld],0.03))
            # a movement the layout legitimately omits (no grants, no expirations)
            # is credited when the report says so and the expected value is zero
            ok+=sum(1 for fld in exp if fld not in block and exp[fld]==0)
            best=max(best, ok/len(exp))
            if best>=0.999: break
        return best
    def award_read(k):
        """The {movement: value} block the workbook actually presents for a class.

        Whichever of the two layouts resolves more of the disclosed movements wins,
        so the roll-forward can be interrogated as numbers (used below to see what a
        withholding decision did to the option ledger) and not only scored."""
        exp=GT["awards"][k]; best={}; score=-1
        rw=amap.get(k)
        if rw is not None:
            b={fld:row_value(rw,fld) for fld in exp}
            s=sum(1 for fld in exp if b.get(fld) is not None and close(b[fld],exp[fld],0.03))
            if s>score: best,score=b,s
        for t in (transposed(k), stacked(k)):
            if not t: continue
            s=sum(1 for fld in exp if fld in t and close(t[fld],exp[fld],0.03))
            if s>score: best,score=t,s
        return best
    detail["dimensions"]["option_rollforward"]=award_score("options")
    detail["dimensions"]["full_value_rollforwards"]=(award_score("rsus")+award_score("psus"))/2

    # ---- Reading a labelled figure wherever the workbook writes it ---------------
    # instruction.md fixes no sheet or column names, so a metric is located by its label and read from
    # the figures on its own row. The named sheet is read first; the workbook-wide pass only answers
    # labels the named sheet does not carry.
    def row_figures(ws, rw):
        return [num(ev.value(ws,c)) for c in rw if num(ev.value(ws,c)) is not None]
    def labelled_rows(skip=()):
        """{normalised row label: [figures on that row]} over every sheet."""
        out={}
        for ws in wbv.worksheets:
            if ws.title in skip: continue
            for rw in ws.iter_rows():
                labs=[norm(c.value) for c in rw if isinstance(c.value,str) and not str(c.value).startswith("=")]
                labs=[l for l in labs if l]
                if not labs: continue
                figs=row_figures(ws,rw)
                if not figs: continue
                for l in labs[:3]:
                    out.setdefault(l, figs)
        return out
    head,hdr,rr=rows(ex); lc=col(hdr,["population","employee","name"],0); sc=exercise_share_column(hdr); emap={}
    for rw in rr:
        lab=str(rw[lc].value or "").strip() if lc is not None and lc < len(rw) else ""
        if lab: emap[norm(lab)]=ev.value(ex,rw[sc]) if sc is not None and sc < len(rw) else None
    wide=labelled_rows()
    for lab,figs in wide.items():
        if lab not in emap: emap[lab]=figs[0]
    direct=sum(close(emap.get(norm(k)),v,0.03) for k,v in GT["exercise"].items() if k in {"Jeffrey Niew","John Anderson","Raymond Cabrera","Daniel Giesecke","Robert Perna"})
    subtotal=next((v for lab,v in emap.items() if "subtotal" in lab),None)
    residual=next((v for lab,v in emap.items() if "residual" in lab or "other employee" in lab),None)
    aggregate=next((v for lab,v in emap.items() if "annual" in lab and "aggregate" in lab),None)
    got_names=direct + close(subtotal,GT["exercise"]["named_subtotal"],0.03) + close(residual,GT["exercise"]["residual"],0.03) + close(aggregate,GT["exercise"]["aggregate"],0.03)
    detail["dimensions"]["exercise_reconciliation"]=got_names/8

    head,hdr,rr=rows(summ); lc=col(hdr,["metric","measure","item"],0)
    bc=col(hdr,["base target","base","target","current"],1); mc=col(hdr,["maximum upside","maximum","upside","max"],2); smap={}
    for rw in rr:
        lab=norm(rw[lc].value if lc is not None and lc < len(rw) else "")
        if lab: smap[lab]=(ev.value(summ,rw[bc]) if bc is not None and bc < len(rw) else None,
                           ev.value(summ,rw[mc]) if mc is not None and mc < len(rw) else None)
    # A scenario pair written anywhere else in the workbook is the same pair: the base case is the
    # first figure on the row and the maximum case the second, which is the order Golden prints them.
    for lab,figs in wide.items():
        if lab not in smap: smap[lab]=(figs[0], figs[1] if len(figs)>1 else None)
    # The instruction publishes no vocabulary for the summary metrics, so each one accepts the
    # ordinary synonyms its own reference uses: `dilution-ledger-controls` 2 ("treasury-stock
    # approach", "incremental shares", "potential shares"), 4 ("plan's share-counting multipliers",
    # "disclosed available balance") and 5 ("share counts and dilution percentages"). Golden's own
    # spelling is first in every list.
    salias={"option_incremental":["option incremental","incremental option","option tsm","tsm option"],
            "rsu_potential":["unvested rsu","rsu","restricted stock unit"],
            "psu_target":["psu target","unvested psu","psu at target","target psu","psu"],
            "psu_maximum":["psu target","unvested psu","psu at maximum","maximum psu","psu"],
            "total_potential_base":["total potential","potential shares","total incremental","total dilutive","total award"],
            "total_potential_maximum":["total potential","potential shares","total incremental","total dilutive","total award"],
            "tsm_incremental_base":["tsm diluted","diluted incremental","treasury stock","tsm","incremental shares","potential incremental"],
            "tsm_incremental_maximum":["tsm diluted","diluted incremental","treasury stock","tsm","incremental shares","potential incremental"],
            "denominator":["denominator","basic weighted","weighted average shares","basic shares"],
            "dilution_base":["potential dilution","dilution percent","dilution rate","percent dilution","dilution"],
            "dilution_maximum":["potential dilution","dilution percent","dilution rate","percent dilution","dilution"],
            "grant_pool_charge_base":["grant pool charge","pool charge","pool consumption","capacity charge","pool usage","shares consumed"],
            "grant_pool_charge_maximum":["grant pool charge","pool charge","pool consumption","capacity charge","pool usage","shares consumed"],
            "available_pool":["available future pool","available pool","available for future","remaining pool"]}
    # A scenario pair is not necessarily two columns of one row.
    # `dilution-ledger-controls` 1.3 asks to "Keep a scenario row for the base case and, when
    # performance awards have a disclosed payout range, a separate maximum case", and 2.3 to "Keep
    # target and maximum columns visible" - the reference admits both presentations, and Golden uses
    # the column one. A scenario row is therefore read as the scenario side it names, so a workbook
    # that gives the maximum case a row of its own is read on both sides.
    SCEN={1:("maximum","max ","upside","stretch","ceiling","at max","high case"),
          0:("base","target","current","expected","low case")}
    def scenario_side(lab, side):
        """True when the row label itself names this scenario side and not the other."""
        mine=any(w in lab+" " for w in SCEN[side]); other=any(w in lab+" " for w in SCEN[1-side])
        return mine and not other
    def smap_value(key, side):
        """The figure a summary metric names, taking the most specific label that matches.

        Aliases are ordered by specificity, and a label matching an earlier alias beats one matching
        a later one however the rows are ordered ("PSU target" before a bare "PSU"); within one alias
        the metric's own sheet is read before the workbook-wide pass. When the matched row carries
        nothing on the side asked for, a row of its own that names both the metric and that scenario
        answers instead."""
        best=None; best_rank=None
        for lab,v in smap.items():
            for rank,a in enumerate(salias[key]):
                if a in lab:
                    if best_rank is None or rank<best_rank: best,best_rank=v[side],rank
                    break
        if best is not None: return best
        alt=None; alt_rank=None
        for lab,v in smap.items():
            if not scenario_side(lab, side): continue
            for rank,a in enumerate(salias[key]):
                if a in lab:
                    if (alt_rank is None or rank<alt_rank) and v[0] is not None: alt,alt_rank=v[0],rank
                    break
        return alt
    pairs=[("option_incremental",0), ("rsu_potential",0), ("psu_target",0), ("psu_maximum",1), ("total_potential_base",0), ("total_potential_maximum",1), ("tsm_incremental_base",0), ("tsm_incremental_maximum",1), ("denominator",0), ("dilution_base",0), ("dilution_maximum",1), ("grant_pool_charge_base",0), ("grant_pool_charge_maximum",1), ("available_pool",0)]
    denominator=smap_value("denominator",0)
    accepted_denominator=next((v for v in (GT["summary"]["denominator"],87358659.0) if close(denominator,v,0.03)),None)
    def summary_ok(key,side):
        candidate=smap_value(key,side)
        if key=="denominator":return accepted_denominator is not None
        if key in ("dilution_base","dilution_maximum") and accepted_denominator:
            numerator=smap_value("tsm_incremental_base" if side==0 else "tsm_incremental_maximum",side)
            return numerator is not None and close(candidate,float(numerator)/accepted_denominator,1e-7)
        return close(candidate,GT["summary"][key],0.03 if "dilution" not in key else 1e-7)
    sg=0
    for key,side in pairs:
        cand=smap_value(key,side)
        if summary_ok(key,side): sg+=1
    detail["dimensions"]["dilution_mechanics"]=sum(summary_ok(key,side) for key,side in pairs[:10])/10
    detail["dimensions"]["performance_scenarios"]=sum(close(smap_value(key,side),GT["summary"][key],0.03) for key,side in pairs[2:8])/6
    detail["dimensions"]["pool_capacity"]=sum(close(smap_value(key,side),GT["summary"][key],0.03) for key,side in pairs[11:])/3

    formulas=[]; cross=[]
    for ws in wbv.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value,str) and c.value.startswith("="):
                    formulas.append(c.value); cross.append(c.value) if "!" in c.value else None
    detail["dimensions"]["formula_traceability"]=1.0 if len(formulas)>=10 and len(cross)>=5 else (0.5 if formulas else 0.0)
    # Controls must be computed, not asserted: each accepted check needs a difference cell
    # that is a cross-sheet formula and a status that resolves to a passing outcome.
    if checks:
        _,ch,cr=rows(checks); sc=col(ch,["status","result"],2); dcol=col(ch,["difference","value","delta"],1); valid=0
        for rw in cr:
            if sc is None or sc >= len(rw) or dcol is None or dcol >= len(rw): continue
            draw=rw[dcol].value
            if not (isinstance(draw,str) and draw.startswith("=") and "!" in draw): continue
            dval=num(ev.value(checks,rw[dcol]))
            if dval is None: continue
            sraw=rw[sc].value
            if sraw in (None,""): continue
            sres=ev.value(checks,rw[sc]); stxt=str(sraw).lower()
            passed = (num(sres) not in (None,0.0)) if num(sres) is not None else ("pass" in stxt or "ok" in stxt)
            if passed: valid+=1
        detail["dimensions"]["controls"]=1.0 if valid>=4 else (0.5 if valid>=1 else 0.0)
    else: detail["dimensions"]["controls"]=0.0

    # ---- Interpretive judgment: score direction of the decision, not vocabulary ----
    # Each of the four required issues is credited only when (a) the stated decision takes the
    # defensible direction, (b) it cites a locator and explains itself, and (c) the workbook's own
    # numbers actually implement that decision. Re-worded but equivalent prose scores the same;
    # a reversed decision, or a decision with no numeric consequence, scores zero.
    NEG = re.compile(r"(\bnot\b|\bno\b|\bnever\b|n't\b|\bcannot\b|\brather than\b|\binstead of\b|\bavoid\w*\b|\bwithout\b|\bexclud\w*\b|double[- ]count\w*|\boverstat\w*|\bmisstat\w*|\binflat\w*|\bduplicat\w*|\bincorrect\w*|\berroneous\b|\bwrong\b|\bneither\b|\bnor\b|\bnothing\b|\bnone\b|\bdo not\b|\bdoes not\b|\bmust not\b|\bshould not\b|\bwould be\b)", re.I)
    # A clause in the irrealis mood - "adding both would double count", "recognising
    # both would count the same award twice" - names an outcome that is being ruled
    # out. It is not an assertion that the outcome was adopted, and reading it as one
    # is what turns an ordinary audit sentence into a false reversal. Irrealis clauses
    # may therefore support a direction but can never establish the opposite one.
    IRREALIS = re.compile(r"\b(would|could|might|risk\w*|otherwise|were we to|if we|hypothetical\w*)\b", re.I)
    def clauses(text):
        out=[]
        for p in re.split(r"[.;:\n|]+", text or ""):
            out.extend(re.split(r",\s*(?:so|and|but|while|whereas|because|since|therefore|which)\s+", p))
        return [c for c in out if c.strip()]
    def stance(text, anti, pos):
        inverted=False; positive=False
        for cl in clauses(text):
            soft=bool(NEG.search(cl)) or bool(IRREALIS.search(cl))
            ha=any(re.search(p,cl,re.I) for p in anti)
            hp=any(re.search(p,cl,re.I) for p in pos)
            if ha and not soft: inverted=True
            if hp or (ha and soft): positive=True
        return -1 if inverted else (1 if positive else 0)

    sv=lambda key,side: smap_value(key,side)
    anchor={
        # maximum PSU case is an alternative scenario: it is separately reported, larger than
        # target, and the maximum total equals the disclosed plan maximum rather than a sum.
        "psu_scenario": close(sv("psu_target",0),GT["summary"]["psu_target"],0.03) and close(sv("psu_maximum",1),GT["summary"]["psu_maximum"],0.03) and close(sv("total_potential_maximum",1),GT["summary"]["total_potential_maximum"],0.03),
        # the named-person rows are reconciled to the filing aggregate through a residual line.
        "residual": close(subtotal,GT["exercise"]["named_subtotal"],0.03) and close(residual,GT["exercise"]["residual"],0.03) and close(aggregate,GT["exercise"]["aggregate"],0.03),
        # the pool multiplier shows up in the capacity charge and stays out of the diluted count.
        "pool_multiplier": close(sv("grant_pool_charge_base",0),GT["summary"]["grant_pool_charge_base"],0.03) and close(sv("tsm_incremental_base",0),GT["summary"]["tsm_incremental_base"],0.03) and close(sv("available_pool",0),GT["summary"]["available_pool"],0.03),
        # withheld shares stay inside the exercise event: the option ledger closes on the
        # disclosed exercises and expirations without an extra grant line.
        "withholding": award_score("options")>=0.999,
    }
    # ---- The arithmetic each judgment call commits the workbook to ---------------
    # Every one of the four calls moves a number the published materials determine, and
    # the inverted treatment produces a *different* recomputable number, not merely a
    # wrong one:
    #   psu_scenario     target-only vs target-plus-maximum -> the plan total carries the
    #                    target units once or twice
    #   residual         named-officer rows reconciled to the company aggregate through a
    #                    balancing line, or asserted to be the aggregate themselves
    #   pool_multiplier  the full-value share-counting factor consumed by plan capacity
    #                    only, or also multiplied into the treasury-stock share count
    #   withholding      shares kept back for tax stay inside the exercise, or re-enter
    #                    the option ledger as an issuance the filing never reports
    # `anchor` is the defensible arithmetic, `opposite` the exact inverse of it; anything
    # else - wrong, partial, absent - is neither, and registers as 0 below.
    inp=GT["inputs"]; gs=GT["summary"]; gx=GT["exercise"]; fv=inp["full_value_pool_multiplier"]
    opts=award_read("options")
    def any_close(v,*targets):
        return any(close(v,t,max(0.03,abs(t)*0.001)) for t in targets)
    tot_m=sv("total_potential_maximum",1); psu_m=sv("psu_maximum",1)
    tsm_m=sv("tsm_incremental_maximum",1); tsm_b=sv("tsm_incremental_base",0)
    pool_b=sv("grant_pool_charge_base",0)
    opposite={
        "psu_scenario": any_close(tot_m, gs["total_potential_maximum"]+gs["psu_target"])
                        or any_close(psu_m, gs["psu_target"]+gs["psu_maximum"])
                        or any_close(tsm_m, gs["tsm_incremental_maximum"]+gs["psu_target"]),
        "residual": bool(num(subtotal)) and (
                        any_close(aggregate, gx["named_subtotal"])
                        or (num(residual) is not None and abs(num(residual))<=0.5
                            and close(subtotal,aggregate,0.5))),
        "pool_multiplier": any_close(tsm_b, gs["tsm_incremental_base"]*fv,
                                     gs["option_incremental"]+fv*(gs["rsu_potential"]+gs["psu_target"]))
                           or any_close(pool_b, gs["grant_pool_charge_base"]/fv),
        "withholding": (num(opts.get("grants")) or 0)>0.5
                       and close(opts.get("beginning"),GT["awards"]["options"]["beginning"],0.03)
                       and close(opts.get("exercises"),GT["awards"]["options"]["exercises"],0.03),
    }
    order=["psu_scenario","residual","pool_multiplier","withholding"]
    implied={k:(1 if anchor[k] else (-1 if opposite[k] else 0)) for k in order}
    ISSUES={
      "psu_scenario":{
        "topic":[r"(psu|performance[ -]?(unit|share|award|condition))", r"(maximum|\bmax\b|upside|target|stretch)"],
        # the inverted treatment is "the maximum is added to the target"; the list
        # covers that relation however it is phrased, not one author's phrasing
        "anti":[r"additional (grant|award|issuance)", r"incremental (grant|award|issuance)", r"separate (grant|award|issuance)", r"\badd\w*\b[^,]{0,30}(target|both)", r"sum\w*\b[^,]{0,30}(target|both)", r"on top of", r"in addition to", r"combin\w+[^,]{0,25}target", r"stack\w*", r"both[^.]{0,30}(count|award|grant|recognis|recogniz|includ|issu|add)", r"layer\w*\s+(on|onto|over|upon)", r"alongside", r"accumulat\w+", r"aggregat\w+[^.]{0,30}(target|both|two)", r"arithmetic (total|sum)", r"(total|sum)\w*[^.]{0,30}\bplus\b", r"\btwice\b", r"(a )?second time", r"in parallel with", r"side by side", r"(plan )?total[^.]{0,45}target[^.]{0,35}(and|plus|together with)[^.]{0,35}(stretch|maximum|upside)", r"each[^.]{0,25}(tranche|level|case|scenario)[^.]{0,30}(recognis|recogniz|count|includ|entitl)"],
        # crediting the defensible direction needs the *relation* stated - one
        # population, counted once, not a further award - so that a decision cannot
        # earn the point by borrowing the topic nouns while asserting the opposite
        "pos":[r"(same|one|single)\s+(award|units?|population|grant|instrument)", r"only once", r"mutually exclusive", r"(alternative|upside|stretch|maximum|scenario)[^.]{0,45}(not|rather than|instead of|never)[^.]{0,35}(grant|award|issuance|addition)", r"(not|rather than|instead of)[^.]{0,30}(additional|further|separate|second|extra|new)\s+(grant|award|issuance)", r"in (place|lieu) of", r"alternative (case|outcome|state|scenario)[^.]{0,45}(same|one|single|not)", r"ceiling (on|for) the (same|target)", r"upper (bound|limit) (on|of|for) the (same|target)"]},
        "residual":{
        "topic":[r"(named|neo|executive|proxy|officer)", r"(exercis|population|residual|subset|aggregate|census)"],
        "anti":[r"\b(complete|entire|full|whole|total)\b (?:(?:exercise|exercising) )?\b(population|census|set|group)\b", r"\bcensus\b", r"\ball employees\b", r"\balready capture\w*\b", r"\b(equals?|is|are)\b[^,]{0,20}\bthe (company|aggregate|total)\b", r"\bno (residual|remainder|balancing)\b", r"\bnothing (further|else|remains)\b", r"\bexhaust\w*\b", r"\breproduc\w+\b[^.]{0,45}\b(exactly|entirely|in full|figure|total|aggregate|number|activity)\b", r"\baccount\w*\s+for\s+(the\s+)?(entire|whole|full|company)\b", r"\b(no|zero)\s+(further|other|remaining)\s+(employees|activity|exercises)\b", r"\b(reach\w*|equal\w*|match\w*|arrive\w*\s+at)\b[^.]{0,35}\bthe (company|aggregate|annual[- ]report|total|wider)\b", r"\bon its own\b", r"\bneeds? no (further|additional|other|balancing)\b"],
        # the defensible direction is a *relation* - the named rows are a part of a
        # larger population and a balancing line carries the difference - so a decision
        # cannot earn the point by reusing the topic nouns while asserting the opposite
        "pos":[r"\bsubset\b", r"(portion|part|some|fraction)\s+of", r"(retain|add|includ|carr|keep|insert|show|report|leav)\w*[^.]{0,45}(residual|remainder|balancing|unassigned|other employees|non[- ]neo)", r"(residual|remainder|balancing (line|figure|row))[^.]{0,45}(to|reconcil|tie|bridge|brings?|close)", r"(reconcil|tie|bridge)\w*[^.]{0,45}(aggregate|company|annual[- ]report|total)", r"only (five|four|part|some|the named)", r"(smaller|narrower|fewer|less)[^.]{0,35}(than|subset|population)", r"non[- ]neo"]},
      "pool_multiplier":{
        # the instruction publishes no vocabulary for this issue, so the topic gate
        # accepts the ordinary synonyms for the share-counting factor
        "topic":[r"\b(multiplier|fungible|reserved?|pool|ratio|weighting|share[- ]count\w*|full[- ]value)\b", r"\b(dilut\w*|capacity|eps|treasury|denominator|per[- ]share|consum\w*)\b"],
        "anti":[r"(multiplier|factor|ratio|multiple)[^,]{0,60}(dilut|eps|treasury|denominator|diluted share)", r"(also|as well|both|equally)[^,]{0,50}(dilut|eps|treasury)", r"appl\w+[^,]{0,60}(dilut|eps|treasury[- ]stock|diluted share)", r"scal\w+[^,]{0,50}(dilut|eps|treasury)", r"multipl\w+[^,]{0,40}(potential|incremental) shares", r"(carr\w+|flow\w*|feed\w*|pass\w*|extend\w*|travel\w*|move\w*)[^.]{0,55}(dilut|eps|treasury|denominator|diluted (share|count)|per[- ]share)", r"(dilut\w*|treasury|denominator)[^.]{0,45}(times|x)\s*1\.75", r"1\.75[^.]{0,45}(diluted|dilution|denominator|treasury)", r"(weighted|multiplied) potential shares"],
        # the defensible direction is that the factor stops at plan capacity; bare
        # topic words ("reserved share", "consumes", "future issuance") say nothing
        # about where it stops, so they do not carry the point on their own
        "pos":[r"only[^.]{0,45}(capacity|pool|reserve)", r"(capacity|pool|reserve)[^.]{0,30}\bonly\b", r"(confine|limit|restrict|appl(y|ies|ied) only|used only)\w*[^.]{0,45}(capacity|pool|reserve)", r"(not|never|rather than|instead of|no)[^.]{0,50}(dilut|eps|treasury|denominator|diluted share|per[- ]share)", r"separate\w*[^.]{0,55}(dilut|eps|treasury|denominator|per[- ]share|capacity)", r"(capacity|pool|reserve)[^.]{0,45}(not|rather than|instead of)[^.]{0,35}(dilut|eps|treasury)", r"does not (affect|enter|change|reach|apply)[^.]{0,45}(dilut|eps|denominator|treasury)"]},
      "withholding":{
        "topic":[r"(withh[eo]ld\w*|net[ -]exercise|net[ -]settle\w*|statutory tax|shares? withheld|tax withhold\w*)"],
        "anti":[r"separate (grant|award|issuance|event)", r"\badd\w*\b[^,]{0,20}back", r"\bcount\w*\b[^,]{0,20}\bagain\b", r"additional (grant|issuance|shares|award)", r"gross\w*[ -](up|back)", r"new (grant|award)", r"re[- ]?issue\w*", r"(recognis|recogniz|record|report|includ)\w*[^.]{0,25}(again|a second time|twice)", r"(second time|\btwice\b)", r"restor\w+[^.]{0,25}(to|into)[^.]{0,25}(ledger|roll)", r"return\w*[^.]{0,25}to the (pool|plan|ledger)", r"re[- ]?(enter|introduc|inject|instate)\w*", r"as an issuance", r"issue\w*\s+them\s+out", r"arriv\w+[^.]{0,40}(issuance|grant|addition)"],
        # the defensible direction is that the withheld shares stay inside the exercise
        # event; "includes", "inside" and "net of" only carry the point when they are
        # said *of* that event, not as loose vocabulary
        "pos":[r"(inside|within|part of)[^.]{0,35}(exercise|vest|settle|event|count|figure|number|total)", r"already (net|reflected|counted|included|deducted|reduced)", r"net of[^.]{0,35}(withh|tax|exercise price|shares)", r"no (adjustment|add[- ]?back|further|separate|additional|second)", r"(not|never|rather than|instead of)[^.]{0,50}(separate|additional|further|new|second|re[- ]?issu|extra)", r"same (event|transaction|exercise|settlement)", r"(count|recognis|recogniz)\w*\s+(only\s+)?once", r"(exercised|vested) (counts?|shares?|numbers?)[^.]{0,35}(includ|net|already)"]},
    }
    # ---- Where a decision may be written ----------------------------------------
    # instruction.md publishes no sheet-name or column contract - it asks only that the workbook be
    # "usable by another analyst to trace inputs to the roll-forwards ... without reopening the source
    # files", and `equity-award-rollforward` 4 asks that footnote decisions be "carried into Notes or
    # assumptions". A decision is therefore read wherever it is written: any row of any sheet whose
    # text names the issue. The substance required is the same either way - the defensible direction,
    # a source locator, a reasoned rationale, and numbers that implement it.
    LOCATOR=re.compile(r"(\bp{1,2}\.?\s*\d|page\s*\d|\bpp\b|\.pdf|\.html|proxy|annual report|note\s*\d+|item\s*\d+|section|exhibit|schedule|column\s*\(?[a-c]\)?)", re.I)
    issue_full={k:False for k in order}; issue_rationale={k:False for k in order}
    seen={k:False for k in order}; spoken={k:0 for k in order}
    for ws in wbv.worksheets:
        for rw in ws.iter_rows():
            texts=[str(c.value).strip() for c in rw if isinstance(c.value,str) and str(c.value).strip()]
            if len(texts)<2: continue
            blob=" | ".join(texts)
            if len(blob)<40: continue
            # The row's own title cell is not a claim: "Pool multiplier versus dilution" names the
            # issue and, read as prose, trips the very anti-pattern it heads; a locator cell is a
            # citation, not a claim either. The topic is therefore taken from the whole row and the
            # *stance* only from the row's remaining sentences - what the workbook asserts, not what
            # it is filing the assertion under.
            sentences=[t for i,t in enumerate(texts)
                       if i>0 and len(t)>=20 and not t.startswith("=")
                       and not re.match(r"^[A-Z]\s*=", t)
                       and not (len(t)<60 and LOCATOR.search(t))]
            if not sentences: continue
            prose=max(sentences, key=len)
            locator=any(LOCATOR.search(t) for t in texts)
            for k in order:
                spec=ISSUES[k]
                if not all(re.search(t,blob,re.I) for t in spec["topic"]): continue
                seen[k]=True
                st=stance(" . ".join(sentences), spec["anti"], spec["pos"])
                if st==-1: spoken[k]=-1
                elif st==1 and spoken[k]==0: spoken[k]=1
                if st!=1: continue
                if not (locator and len(prose)>=20): continue
                if implied[k]!=1: continue
                issue_full[k]=True
                if len(prose)>=40: issue_rationale[k]=True
    detail["dimensions"]["evidence_binding"]=sum(issue_full.values())/4
    detail["dimensions"]["exception_judgment"]=sum(issue_full[k] for k in ("residual","pool_multiplier","withholding"))/3
    detail["dimensions"]["scenario_interpretation"]=1.0 if issue_full["psu_scenario"] else 0.0
    detail["dimensions"]["reviewer_rationale"]=sum(issue_rationale.values())/4

    # ---- Stating the opposite of your own records -------------------------------
    # Reversing the conclusions leaves every quantity-only dimension at full marks, so a
    # systematic reversal otherwise scores like a partly-right answer. Two families are
    # measured on their own denominators - pooling them would let one dilute the other:
    #   numeric  the workbook's own figures realise the inverted treatment
    #   prose    the log asserts the inverted treatment over figures that are right
    # Only exact inversions register. An answer that is wrong, incomplete, silent on an
    # issue, or that uses its own field names produces no slot at all, so the quantity
    # dimensions of a merely-incorrect answer are untouched.
    MIN_REVERSAL_SLOTS=3
    numeric_slots=[implied[k]==-1 for k in order if implied[k]!=0]
    prose_slots=[spoken[k]==-1 for k in order if seen[k] and implied[k]==1]
    def family_rate(slots):
        if len(slots)<MIN_REVERSAL_SLOTS: return 0.0
        return sum(1 for s in slots if s)/len(slots)
    reversal_rate=max(family_rate(numeric_slots),family_rate(prose_slots))
    # These dimensions read quantities and bookkeeping only; no decision direction
    # enters them, so a reversal leaves them intact. Credit for records that contradict
    # the report's own stated conclusions is withdrawn in proportion to how systematic
    # the contradiction is - a continuous reducer, not a gate.
    # `formula_traceability` and `controls` state one decision - the workbook computes its figures
    # rather than asserting them (`dilution-ledger-controls` 5: "Use formulas that a reviewer can
    # inspect, not a pasted scalar"; 6.4: controls must show a computed status). `computed_not_asserted`
    # reports the two as one dimension, the average of their completions.
    detail["dimensions"]["computed_not_asserted"]=(detail["dimensions"].get("formula_traceability",0.0)
                                                   +detail["dimensions"].get("controls",0.0))/2
    REVERSAL_IMMUNE=("structure","source_facts","option_rollforward","full_value_rollforwards","exercise_reconciliation","dilution_mechanics","performance_scenarios","pool_capacity","formula_traceability","controls","computed_not_asserted")
    reducer=0.30+0.70*(1.0-reversal_rate)
    for nm in REVERSAL_IMMUNE:
        detail["dimensions"][nm]=detail["dimensions"].get(nm,0.0)*reducer
    detail["notes"].append({"judgment_issues":{k:bool(issue_full[k]) for k in order},
                            "judgment_anchors":{k:bool(anchor[k]) for k in order},
                            "judgment_implied":{k:implied[k] for k in order},
                            "judgment_spoken":{k:spoken[k] for k in order},
                            "conclusion_reversal_rate":round(reversal_rate,6),
                            "conclusion_reversal_detail":{"numeric":[len(numeric_slots),sum(1 for s in numeric_slots if s)],
                                                          "prose":[len(prose_slots),sum(1 for s in prose_slots if s)]}})
    weights={"structure":.02,"source_facts":.03,"option_rollforward":.03,"full_value_rollforwards":.03,"exercise_reconciliation":.04,"dilution_mechanics":.04,"performance_scenarios":.04,"pool_capacity":.02,"formula_traceability":.02,"controls":.03,"evidence_binding":.25,"exception_judgment":.25,"scenario_interpretation":.15,"reviewer_rationale":.05}
    strict=sum(weights[k]*detail["dimensions"].get(k,0) for k in weights)
    contract=all(detail["dimensions"].get(k,0)>=1 for k in ["structure","source_facts","option_rollforward","full_value_rollforwards","exercise_reconciliation","dilution_mechanics","performance_scenarios","pool_capacity","formula_traceability","controls","evidence_binding","exception_judgment","scenario_interpretation","reviewer_rationale"])
    detail["group_points"]={k:detail["dimensions"].get(k,0) for k in weights}
    strict_out=round(strict,6); lenient_out=1.0 if contract else 0.0
    # Settlement parts (pd-ledger-v1): completion per positive item; D01 = the structure gate.
    # ---- Damage instances -------------------------------------------------------
    # Each charges an affirmative error the workbook adopts, quoted from the reference.
    # `spoken[k] == -1` is the workbook stating the inverted treatment in its own sentences.
    DAMAGE_ITEMS={"psu_scenario":("D02","PSU maximum treated as additional to the target population rather than an alternative scenario"),
                  "residual":("D03","named-officer exercises asserted to be the whole population, with no reconciliation residual"),
                  "pool_multiplier":("D04","the plan's share-counting multiplier described as a dilution factor"),
                  "withholding":("D05","shares withheld for tax re-entered as a new issuance")}
    damage=[]
    if gate_result is not None:
        damage.append(("structure gate: required sheet(s) missing: "+", ".join(
            n for n,w in (("inputs",sheet_like(wbv,["input","source"])),("awards",sheet_like(wbv,["award","roll","equity"])),
                          ("exercise",sheet_like(wbv,["exercise","vesting"])),("summary",sheet_like(wbv,["dilution","summary"])),
                          ("checks",checks)) if w is None),["D01"]))
    for k,(item,why) in DAMAGE_ITEMS.items():
        if spoken[k]!=-1: continue
        damage.append((f"judgment:{k}:{why}", [item]))
    damage.extend(brief_damage(Path(path), wbv, ev))
    parts={"completion":item_completions(wbv,ev),"damage":damage}
    # The lenient lens is settled from the very same parts the strict score is settled from
    # (see lenient_lens below); it replaces the older fourteen-dimension contract reading,
    # which was 0 for every submission and therefore separated nothing. `strict_out` and the
    # dimension weights above are untouched.
    lenient_out, lenient_detail = lenient_lens(parts)
    if gate_result is not None:
        gate_result["_parts"]=parts
        gate_result["rewards"]["lenient"]=lenient_out
        gate_result["reward_formulas"]["lenient"]=LENIENT_FORMULA
        gate_result["lenient_detail"]=lenient_detail
        return gate_result
    return {"_parts":parts,"reward":strict_out,"rewards":{"strict":strict_out,"lenient":lenient_out},"reward_formulas":{"strict":"weighted sum of fourteen anchored workbook dimensions","lenient":LENIENT_FORMULA},"lenient_detail":lenient_detail,"details":detail,"group_points":detail["group_points"]}



# ---------------------------------------------------------------------------
# Scored item set
#
# One item per substantive leaf of Golden's own deliverable. Each item names the Golden cells it stands
# for by *sheet, row label and column header*, and an output earns it only when the value appears on a
# row whose label matches the reference's, or whose column header does. "The figure is somewhere in the
# deliverable" is a different question and it is the one that fails. Prose leaves are earned by a line
# sharing the reference's wording.
#
# Unicode minus (U+2212), en- and em-dashes, non-breaking spaces and accounting parentheses are
# normalised on *both* sides before a number is parsed: "-6,914" written with U+2212 would otherwise
# parse as +6914 and silently miss.

SCORED_ITEMS = {
"R01": [
{
"sheet": "Inputs",
"row_label": "Full-value pool multiplier",
"column": "Value",
"kind": "figure",
"value": 1.75
},
{
"sheet": "Inputs",
"row_label": "Aggregate options exercised",
"column": "Value",
"kind": "figure",
"value": 589516.0
},
{
"sheet": "Award_Ledger",
"row_label": "Options",
"column": "Beginning",
"kind": "figure",
"value": 2104356.0
},
{
"sheet": "Award_Ledger",
"row_label": "Options",
"column": "Exercises / vests",
"kind": "figure",
"value": 589516.0
},
{
"sheet": "Award_Ledger",
"row_label": "Options",
"column": "Forfeitures",
"kind": "figure",
"value": 8349.0
},
{
"sheet": "Award_Ledger",
"row_label": "Options",
"column": "Expirations",
"kind": "figure",
"value": 345154.0
}
],
"R02": [
{
"sheet": "Award_Ledger",
"row_label": "RSUs",
"column": "Beginning",
"kind": "figure",
"value": 2075007.0
},
{
"sheet": "Award_Ledger",
"row_label": "RSUs",
"column": "Exercises / vests",
"kind": "figure",
"value": 1051631.0
},
{
"sheet": "Award_Ledger",
"row_label": "PSUs",
"column": "Beginning",
"kind": "figure",
"value": 864749.0
},
{
"sheet": "Award_Ledger",
"row_label": "PSUs",
"column": "Exercises / vests",
"kind": "figure",
"value": 258680.0
},
{
"sheet": "Dilution_Summary",
"row_label": "Unvested PSUs at target",
"column": "Base / target",
"kind": "figure",
"value": 842866.0
}
],
"R03": [
{
"sheet": "Award_Ledger",
"row_label": "RSUs",
"column": "Grants / additions",
"kind": "figure",
"value": 1549795.0
},
{
"sheet": "Award_Ledger",
"row_label": "RSUs",
"column": "Ending (formula)",
"kind": "figure",
"value": 1819308.0
},
{
"sheet": "Award_Ledger",
"row_label": "PSUs",
"column": "Grants / additions",
"kind": "figure",
"value": 428500.0
},
{
"sheet": "Award_Ledger",
"row_label": "PSUs",
"column": "Ending (formula)",
"kind": "figure",
"value": 842866.0
},
{
"sheet": "Checks",
"row_label": "Exercise reconciliation",
"column": "Control rationale",
"kind": "prose",
"text": "Named subtotal + residual = aggregate"
}
],
"R04": [
{
"sheet": "Inputs",
"row_label": "Basic weighted-average shares",
"column": "Value",
"kind": "figure",
"value": 88900000.0
},
{
"sheet": "Dilution_Summary",
"row_label": "Basic weighted-average denominator",
"column": "Base / target",
"kind": "figure",
"value": 88900000.0
},
{
"sheet": "Dilution_Summary",
"row_label": "Basic weighted-average denominator",
"column": "Maximum / upside",
"kind": "figure",
"value": 88900000.0
}
],
"R05": [
{
"sheet": "Inputs",
"row_label": "Aggregate option cash proceeds",
"column": "Value",
"kind": "figure",
"value": 5800000.0
},
{
"sheet": "Inputs",
"row_label": "Aggregate option intrinsic value",
"column": "Value",
"kind": "figure",
"value": 2300000.0
},
{
"sheet": "Exercise_Ledger",
"row_label": "Annual-report aggregate",
"column": "Value realized ($)",
"kind": "figure",
"value": 5800000.0
}
],
"R06": [
{
"sheet": "Exercise_Ledger",
"row_label": "Other employees / unassigned aggregate",
"column": "Options exercised",
"kind": "figure",
"value": 282626.0
},
{
"sheet": "Dilution_Summary",
"row_label": "Option incremental shares (treasury-stock)",
"column": "Base / target",
"kind": "figure",
"value": 136353.6668339187
},
{
"sheet": "Dilution_Summary",
"row_label": "Option incremental shares (treasury-stock)",
"column": "Maximum / upside",
"kind": "figure",
"value": 136353.6668339187
}
],
"R07": [
{
"sheet": "Checks",
"row_label": "Options roll-forward",
"column": "Control rationale",
"kind": "prose",
"text": "Beginning + movements = ending"
},
{
"sheet": "Checks",
"row_label": "RSU roll-forward",
"column": "Control rationale",
"kind": "prose",
"text": "Beginning + movements = ending"
},
{
"sheet": "Checks",
"row_label": "PSU roll-forward",
"column": "Control rationale",
"kind": "prose",
"text": "Beginning + movements = ending"
}
],
"R08": [
{
"sheet": "Inputs",
"row_label": "Aggregate options exercised",
"column": "Source locator / note",
"kind": "prose",
"text": "Annual report, stock option activity"
},
{
"sheet": "Award_Ledger",
"row_label": "Options",
"column": "Source locator",
"kind": "prose",
"text": "Annual report, stock option activity"
}
],
"R09": [
{
"sheet": "Inputs",
"row_label": "Authorized pool",
"column": "Source locator / note",
"kind": "prose",
"text": "Annual report, Equity Incentive Program"
},
{
"sheet": "Inputs",
"row_label": "Available for future awards",
"column": "Source locator / note",
"kind": "prose",
"text": "Annual report, Equity Incentive Program"
}
],
"R10": [
{
"sheet": "Dilution_Summary",
"row_label": "Available future pool",
"column": "Base / target",
"kind": "figure",
"value": 13059834.0
},
{
"sheet": "Dilution_Summary",
"row_label": "Available future pool",
"column": "Maximum / upside",
"kind": "figure",
"value": 13059834.0
}
],
"R11": [
{
"sheet": "Dilution_Summary",
"row_label": "Unvested PSUs at target",
"column": "Maximum / upside",
"kind": "figure",
"value": 1896452.0
},
{
"sheet": "Dilution_Summary",
"row_label": "TSM diluted incremental shares",
"column": "Maximum / upside",
"kind": "figure",
"value": 3852113.6668339185
}
],
"R12": [
{
"sheet": "Dilution_Summary",
"row_label": "TSM diluted incremental shares",
"column": "Base / target",
"kind": "figure",
"value": 2798527.6668339185
},
{
"sheet": "Dilution_Summary",
"row_label": "Potential dilution %",
"column": "Maximum / upside",
"kind": "figure",
"value": 0.04333086239408232
}
],
"R13": [
{
"sheet": "Inputs",
"row_label": "Aggregate option cash proceeds",
"column": "Source locator / note",
"kind": "prose",
"text": "Annual report, option exercise information"
},
{
"sheet": "Inputs",
"row_label": "Aggregate option intrinsic value",
"column": "Source locator / note",
"kind": "prose",
"text": "Annual report, option exercise information"
}
],
"R14": [
{
"sheet": "Award_Ledger",
"row_label": "RSUs",
"column": "Forfeitures",
"kind": "figure",
"value": 753863.0
},
{
"sheet": "Award_Ledger",
"row_label": "PSUs",
"column": "Forfeitures",
"kind": "figure",
"value": 191703.0
}
],
"R15": [
{
"sheet": "Judgment_Log",
"row_label": "Performance-unit maximum",
"column": "Evidence locator",
"kind": "prose",
"text": "Annual report, Equity Compensation Plans footnote"
},
{
"sheet": "Judgment_Log",
"row_label": "Pool multiplier versus dilution",
"column": "Evidence locator",
"kind": "prose",
"text": "Annual report, Equity Compensation Plans footnote"
}
],
"R16": [
{
"sheet": "Inputs",
"row_label": "Maximum outstanding securities (plan table)",
"column": "Source locator / note",
"kind": "prose",
"text": "Annual report, equity compensation plan footnote"
},
{
"sheet": "Dilution_Summary",
"row_label": "Option incremental shares (treasury-stock)",
"column": "Formula note",
"kind": "prose",
"text": "Only in-the-money options contribute"
}
]
}

ITEM_STOPWORDS = {"the","a","an","of","and","or","to","at","in","for","on","is","as","by","per","with","from","no","not"}


def uninorm(value) -> str:
    text = unicodedata.normalize("NFKC", str(value))
    for bad, good in (("\u2212", "-"), ("\u2013", "-"), ("\u2014", "-"), ("\u2010", "-"), ("\u00a0", " ")):
        text = text.replace(bad, good)
    return text


def unitoks(value):
    raw = uninorm(value).lower()
    tokens = [t for t in re.split(r"[^a-z0-9]+", raw) if t and t not in ITEM_STOPWORDS]
    # The rubric explicitly permits these compact labels for the same ledger
    # concepts as the longer Golden headings.
    aliases = {
        "residual": ("other", "employees", "unassigned", "aggregate"),
        "nonneo": ("other", "employees"),
        "max": ("maximum", "upside"),
    }
    expanded = list(tokens)
    if re.search(r"\bnon[- ]neo\b", raw):
        expanded.extend(("nonneo", "other", "employees"))
    for token in tokens:
        expanded.extend(aliases.get(token, ()))
    return expanded


def uninum(value):
    """A number, with accounting parentheses and Unicode dashes honoured."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = uninorm(value).strip().replace(",", "").replace("$", "").replace("%", "")
    negated = text.startswith("(") and text.endswith(")")
    if negated:
        text = text[1:-1]
    try:
        number = float(text)
    except Exception:
        return None
    return -number if negated else number


def scored_item_rows(wb, ev):
    """Every row of every sheet as (tokens of the sheet title plus the row's text, numbers, texts).

    Formula cells are evaluated, never read as a cached value: a submission that computed a figure with
    the library the task image ships has no cached value to read, and scoring the writing library
    instead of the analysis is the defect this cohort names."""
    rows = []
    for ws in wb.worksheets:
        title = unitoks(ws.title)
        for row in ws.iter_rows():
            texts, numbers = [], []
            for c in row:
                raw = c.value
                if isinstance(raw, str) and raw.startswith("="):
                    n = uninum(ev.value(ws, c))
                    if n is not None:
                        numbers.append(n)
                    continue
                n = uninum(raw)
                if n is not None:
                    numbers.append(n)
                elif isinstance(raw, str) and uninorm(raw).strip():
                    texts.append(uninorm(raw).strip())
            if not texts and not numbers:
                continue
            tokens = set(title)
            for t in texts:
                tokens.update(unitoks(t))
            rows.append((tokens, numbers, texts))
    return rows


def item_completions(wb, ev):
    """{item id: share of its Golden cells the workbook carries, bound to their objects}."""
    rows = scored_item_rows(wb, ev)

    def share(needed, tokens):
        needed = set(needed)
        return (sum(1 for t in needed if t in tokens) / len(needed)) if needed else 0.0

    def bound_figure(cell):
        label, column = unitoks(cell["row_label"]), unitoks(cell["column"])
        want = cell["value"]
        tol = max(0.03, abs(want) * 0.001)
        for tokens, numbers, _ in rows:
            if not numbers:
                continue
            by_label = share(label, tokens) >= 0.5 and any(len(t) >= 4 and t in tokens for t in label)
            by_column = bool(column) and share(column, tokens) >= 0.5 and any(len(t) >= 4 and t in tokens for t in column)
            if not (by_label or by_column):
                continue
            if any((available_pool_close(n) if "available future pool" in str(cell["row_label"]).lower()
                    else abs(n - want) <= tol or abs(abs(n) - abs(want)) <= tol) for n in numbers):
                return True
        return False

    def bound_prose(cell):
        needed = [t for t in unitoks(cell["text"]) if len(t) >= 4]
        if not needed:
            return False
        for _, _, texts in rows:
            for t in texts:
                if share(needed, set(unitoks(t))) >= 0.5:
                    return True
        return False

    out = {}
    for item, cells in SCORED_ITEMS.items():
        earned = sum(1 for c in cells if (bound_figure(c) if c["kind"] == "figure" else bound_prose(c)))
        out[item] = round(earned / len(cells), 10)
    accepted_denominators=(88900000.0,87358659.0)
    denominator_hits=0
    for tokens,numbers,_texts in rows:
        context=("denominator" in tokens or ({"year","end","outstanding"} <= tokens)) and "shares" in tokens
        if context:
            denominator_hits += sum(any(abs(abs(n)-value)<=max(.03,value*.001) for value in accepted_denominators) for n in numbers)
    if denominator_hits>=3:
        out["R04"]=1.0
    return out


# ---------------------------------------------------------------------------
# Brief-level damage instances (D06-D11)
#
# D06  Give-away unit gate. Each unit below is a disclosed fact the brief requires the ledger to
#      carry (the source inputs, the three award classes' roll-forward movements, the named
#      exercise population and its subtotal, the computed ending balances). Every submitted ledger
#      carries all of them; each one missing anywhere in the workbook is one D06 instance, so a
#      ledger with half its rows removed loses several units. A figure counts in shares, thousands
#      or millions (19.93 and the multipliers only as written); formula cells are evaluated, with
#      the cached value as fallback.
# D07  External source: a text cell that cites a source outside /workspace (a data vendor, a web
#      address, a press release, analyst or broker research), unless the cell negates it.
# D08  Language: any text cell in Chinese, Japanese or Korean script (the workbook must be English).
# D09  Units and dates: the workbook must state the reporting date 31 December 2024 and carry both
#      share and dollar units; one instance when either is missing.
# D10  Deliverable name: the scored workbook is not named employee_equity_dilution_ledger.xlsx.
# D11  Formula-driven with cross-sheet references: no formula in the workbook refers to another sheet.
GIVEAWAY_FIGURES = [23400000, 19.93, 2.25, 1.75, 589516, 5800000, 2300000, 4877097,
                    2104356, 8349, 345154, 17.59, 2075007, 1549795, 1051631, 753863, 864749, 428500,
                    258680, 191703, 157699, 86575, 27829, 34787,
                    # 739099/349733/89888/176022 are the R05 value-realized
                    # figures; R05 has no positive weight and must not become a
                    # hidden D06 cliff.
                    1161337, 1819308, 842866]
GIVEAWAY_NAMES = ["niew", "anderson", "cabrera", "giesecke", "perna"]
EXTERNAL_SOURCE = re.compile(r"press release|broker|analyst report|research note|bloomberg|reuters|factset|"
                             r"capital iq|yahoo|website|https?://|www\.|sec\.gov|edgar|"
                             r"outside (?:the )?(?:supplied )?materials|not (?:provided )?in /workspace", re.I)
EXTERNAL_NEGATOR = re.compile(r"\b(?:no|not|without|never|none|excluded?)\b", re.I)
CJK = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")
REPORT_DATE = re.compile(r"2024-12-31|12/31/2024|31/12/2024|31(?:st)?\s+dec(?:ember)?\.?,?\s+2024|"
                         r"dec(?:ember)?\.?\s+31(?:st)?,?\s+2024", re.I)


def brief_damage(path, wbv, ev):
    """[(key, [item id])] for D06-D11."""
    try:
        wbc = load_workbook(path, data_only=True)
    except Exception:
        wbc = None
    numbers, texts, dated, cross_sheet = [], [], False, 0
    for ws in wbv.worksheets:
        texts.append(ws.title)
        for row in ws.iter_rows():
            for c in row:
                raw = c.value
                if isinstance(raw, str) and raw.startswith("="):
                    cross_sheet += "!" in raw
                    try:
                        n = uninum(ev.value(ws, c))
                    except Exception:
                        n = None
                    if n is None and wbc is not None:
                        n = uninum(wbc[ws.title][c.coordinate].value)
                    if n is not None:
                        numbers.append(abs(n))
                    continue
                if hasattr(raw, "year") and (raw.year, raw.month, raw.day) == (2024, 12, 31):
                    dated = True
                n = uninum(raw)
                if n is not None:
                    numbers.append(abs(n))
                elif isinstance(raw, str) and raw.strip():
                    texts.append(uninorm(raw))
    damage = []

    def carried(want):
        tol = max(0.005, want * 0.001)
        scales = (1.0, 1e3, 1e6) if want >= 1e5 else (1.0,)
        return any(abs(n * f - want) <= tol for n in numbers for f in scales)

    blob = "\n".join(texts).lower()
    if not any(carried(value) for value in (88900000,87358659)):
        damage.append(("giveaway unit missing: disclosed share denominator", ["D06"]))
    for want in GIVEAWAY_FIGURES:
        if not carried(want):
            damage.append((f"giveaway unit missing: figure {want:g}", ["D06"]))
    for name in GIVEAWAY_NAMES:
        if name not in blob:
            damage.append((f"giveaway unit missing: named officer {name}", ["D06"]))
    for t in texts:
        m = EXTERNAL_SOURCE.search(t)
        if m and not EXTERNAL_NEGATOR.search(t[:m.start()]):
            damage.append((f"external source cited: {t[:80]}", ["D07"]))
            break
    if any(CJK.search(t) for t in texts):
        damage.append(("workbook text not in English", ["D08"]))
    dated = dated or any(REPORT_DATE.search(t) for t in texts)
    shares = re.search(r"\bshares?\b", blob) is not None
    dollars = re.search(r"\$|\busd\b|dollar", blob) is not None
    if not (dated and shares and dollars):
        damage.append(("disclosed units or reporting date missing", ["D09"]))
    if path.name != DELIVERABLE:
        damage.append((f"deliverable scored under another name: {path.name}", ["D10"]))
    if not cross_sheet:
        damage.append(("no cross-sheet formula", ["D11"]))
    return damage


# ---------------------------------------------------------------------------
# Lenient lens: the must-do contract
#
# Semantics: 0/1. It is 1 only when *every* item below is met. It is not a weighted score and it
# is not a threshold on the strict score; it answers a different question — "is this ledger
# usable at all", i.e. would a finance reviewer who received this workbook be able to use it.
#
# It is settled from the SAME parts the strict score is settled from (`parts["completion"]`,
# the per-item share of the reference cells each scored item carries, and `parts["damage"]`,
# the damage instances). Nothing is re-read from the workbook and no new criterion is
# introduced. A positive item R** is met only when its *own* completion is full (1.0) — not
# when its weighted contribution is large; a deduction item D** is met only when no damage
# instance charged it. An id outside the scored set is met=False (fail closed), and a workbook
# that cannot be parsed keeps lenient 0 through the error path in __main__ (fail closed).
#
# ---- Why each of these five, quoting the task's own wording -------------------------------
#
# R01  Option ledger movements.  instruction.md: the workbook must "cover every equity award
#      class and plan category disclosed in the materials". R01 is the option class's own
#      roll-forward (beginning 2,104,356; exercises 589,516; forfeitures 8,349; expirations
#      345,154) plus the two Inputs facts the rest of the workbook is built on — the full-value
#      pool multiplier and the aggregate options exercised. Without the option movements there
#      is no award roll-forward for the largest class, and the plan-pool and exercise sheets
#      have nothing to tie to.
#
# R03  Full-value grants, ENDING balances and the reconciliation control.  The RSU and PSU
#      ending balances (1,819,308 and 842,866) are the unvested populations that the entire
#      dilution calculation consumes — they are `rsu_potential` and `psu_target` in the summary.
#      A ledger that does not carry them cannot produce a dilution figure at all. The item also
#      carries the control line "Named subtotal + residual = aggregate", which is
#      instruction.md's "reconcile aggregate and named-employee activity" written down.
#
# R04  Diluted-share denominator.  RUBRIC.md R04: "The disclosed basic weighted-average share
#      count recorded as an input and carried into both the base and the maximum scenario."
#      instruction.md asks for "a formula-driven dilution analysis" and to "preserve the
#      disclosed units". Dilution % IS potential shares over this denominator; with the wrong
#      denominator (or with 88.9 left in millions, or with year-end outstanding substituted for
#      the disclosed weighted average) every dilution percentage in the workbook is wrong, and
#      the deliverable's headline output is unusable.
#
# R06  Residual population and option increment.  instruction.md: "reconcile aggregate and
#      named-employee activity". The residual "other employees / unassigned" figure (282,626)
#      IS that reconciliation — the proxy names five officers, the annual report gives the
#      589,516 company aggregate, and the residual is what bridges them. The item also carries
#      the treasury-stock option incremental shares on both scenario sides, which is the only
#      place options enter the diluted count.
#
# D01  Required sheets present.  instruction.md names the structures in so many words: the
#      workbook must "include an exercise and vesting ledger, reconcile aggregate and
#      named-employee activity, and show a formula-driven dilution analysis with cross-sheet
#      references and visible checks", and must let another analyst "trace inputs to the
#      roll-forwards, plan-pool usage, exercise proceeds, and diluted-share outputs without
#      reopening the source files". D01 is exactly the gate on source inputs / award
#      roll-forward / exercise-vesting ledger / dilution summary / control checks. RUBRIC.md's
#      rationale for it: "The workbook does not present a traceable ledger."
#
# D06  Give-away units present. The disclosed facts every ledger carries (source inputs, award
#      movements, named exercise population); a workbook missing any of them is not the ledger
#      instruction.md asks for.
#
# ---- Deliberately NOT required -------------------------------------------------------------
#
# R14  RSU and PSU forfeitures. A real movement, but a detail of the roll-forward: R03 already
#      requires the ending balances the dilution analysis consumes, so a ledger missing only the
#      forfeiture split is still usable and still produces the right dilution figures.
#
# R10  Available future capacity restated in the dilution summary on both scenario sides. This
#      is where a disclosed figure is *presented*, not whether it was derived; the capacity
#      number itself lives on the Inputs/plan sheet. Placement is not a must-do.
#
# R13  Exercise-value locators; R15 judgment-log evidence locators; R16 plan-maximum locator and
#      the in-the-money wording note. RUBRIC.md tags these "Evidence citation" / "Interpretive
#      judgment" / wording: they are citations and phrasing laid over figures that are scored
#      elsewhere. Valuable, and strict pays for them heavily, but a ledger whose numbers are
#      right and whose footnote pointer is missing is still a usable ledger.
#
# D02-D05  The stated-inversion deductions (PSU maximum treated as additive, named officers
#      asserted to be the whole population, pool multiplier called a dilution factor, withheld
#      shares re-issued). These are charged on what the workbook *says* — `spoken[k] == -1`,
#      a stance read from the prose of a row — and they can and do fire on workbooks whose own
#      figures take the defensible direction. They are wording-level conclusions rather than the
#      must-do substance of the ledger, and instruction.md never names them; they live in
#      RUBRIC.md's deduction table only. Strict already prices them, multiplicatively. Keeping
#      them out of the must-do contract is what separates "the ledger is unusable" from "the
#      ledger's commentary argues the wrong way".
LENIENT_REQUIRED_ITEMS = ["R01", "R03", "R04", "R06", "D01", "D06"]
LENIENT_FORMULA = ("1 when every must-do item is met (positive item completion == 1.0; "
                   "deduction item not charged), otherwise 0 (LENIENT_REQUIRED_ITEMS)")


def lenient_lens(parts):
    """(lenient, detail) from the settlement parts the strict score is built from."""
    completion = (parts or {}).get("completion") or {}
    fired = set()
    for _key, item_ids in ((parts or {}).get("damage") or []):
        fired.update(item_ids)
    met = {}
    for item_id in LENIENT_REQUIRED_ITEMS:
        if item_id.startswith("D"):
            met[item_id] = item_id not in fired
        else:
            try:
                met[item_id] = float(completion.get(item_id, 0.0)) >= 1.0
            except Exception:
                met[item_id] = False          # unknown / unreadable id: fail closed
    lenient = 1.0 if met and all(met.values()) else 0.0
    return lenient, {"required_items": list(LENIENT_REQUIRED_ITEMS), "met": met}


# ---------------------------------------------------------------------------
# pd-ledger-v1 settlement
PARAMS = Path(os.environ.get("SCORING_PARAMS") or (ROOT / "scoring_params.json"))
DELIVERABLE = "employee_equity_dilution_ledger.xlsx"
ZERO_PARTS = {"completion": {}, "damage": []}


def settle(result: dict) -> dict:
    """Settle the scored parts under the params file."""
    params = json.loads(PARAMS.read_text(encoding="utf-8"))
    weights, coefficients = params["positive_weights"], params["deduction_coefficients"]
    parts = result.pop("_parts", ZERO_PARTS)
    completion = {k: round(min(1.0, max(0.0, float(parts["completion"].get(k, 0.0)))), 10) for k in weights}
    instances = [{"key": key, "item_ids": items} for key, items in parts["damage"]]
    earned = sum(weights[k] * completion[k] for k in weights)
    # Damage remains monotone but bounded: repeated omissions should not turn a
    # single missing bookkeeping unit into an effectively unscorable workbook.
    retention = max(0.25, math.prod(min(coefficients[i] for i in inst["item_ids"]) for inst in instances))
    final = earned * retention
    result.setdefault("rewards", {"strict": 0.0, "lenient": 0.0})
    result.setdefault("reward_formulas", {})
    result["rewards"]["strict"] = final
    result["reward"] = final
    result["reward_formulas"]["strict"] = "positive_earned * retention (pd-ledger-v1; weights and coefficients from scoring_params.json)"
    result["scoring_ledger"] = {"schema_version": "pd-ledger-v1", "positive_completion": completion,
                                "damage_instances": instances, "positive_earned": earned,
                                "retention": retention, "final_score": final}
    return result


def deliverable(arg: str) -> Path:
    """The workbook: the path itself, or the deliverable found under a directory (artifacts/, golden/)."""
    path = Path(arg)
    if path.is_dir():
        hits = sorted(path.rglob(DELIVERABLE)) or sorted(path.rglob("*.xlsx"))
        return hits[0] if hits else path / DELIVERABLE
    return path


if __name__ == "__main__":
    target = deliverable(sys.argv[1] if len(sys.argv) > 1 else "/workspace/" + DELIVERABLE)
    try:
        result = main(target)
    except Exception as exc:  # emit a zero ledger rather than no output
        # Fail closed on both lenses: a workbook the scorer could not settle is not evidence
        # that the must-do contract was met.
        result = {"reward": 0.0, "rewards": {"strict": 0.0, "lenient": 0.0},
                  "reward_formulas": {"strict": "error", "lenient": "error"},
                  "lenient_detail": {"required_items": list(LENIENT_REQUIRED_ITEMS), "met": {},
                                     "note": "scorer error: fail closed"},
                  "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(settle(result), ensure_ascii=False, indent=2))
