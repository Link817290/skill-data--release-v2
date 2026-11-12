"""Check mathematical support and source-derived changes without grading execution."""

import ast
import math
import re


def point(address):
    column, row = re.fullmatch(r"([A-Z]+)(\d+)", address).groups()
    x = 0
    for char in column:
        x = x * 26 + ord(char) - 64
    return x, int(row)


def polynomial(node):
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return {(): float(node.value)}
    if isinstance(node, ast.Name) and node.id.lower() in ("meanlog", "sdlog", "median", "mad"):
        return {(node.id.lower(),): 1.0}
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id.lower() == "median" and len(node.args) == 1
            and isinstance(node.args[0], ast.Name) and node.args[0].id.lower() in ("sir", "sir1")
            and not node.keywords):
        return {("median",): 1.0}
    if isinstance(node, ast.BinOp):
        left, right = polynomial(node.left), polynomial(node.right)
        if isinstance(node.op, (ast.Add, ast.Sub)):
            result = left.copy()
            sign = -1 if isinstance(node.op, ast.Sub) else 1
            for key, value in right.items():
                result[key] = result.get(key, 0) + sign * value
            return result
        if isinstance(node.op, ast.Mult):
            result = {}
            for a, x in left.items():
                for b, y in right.items():
                    key = tuple(sorted(a + b))
                    result[key] = result.get(key, 0) + x * y
            return result
    raise ValueError("Unsupported mathematical expression")


def calculation_support(text, evidence, refs, body_lines):
    lines = body_lines(text)
    equations = {name: [] for name in evidence["families"]}
    for line in lines:
        for match in re.finditer(r"(?<![A-Za-z0-9_])(LogSCP|LogTCP|CCP)\s*=\s*([^;,、。|`]+)", line, re.I):
            name = next(n for n in equations if n.casefold() == match[1].casefold())
            expression = match[2].strip().replace("×", "*").replace("−", "-")
            if len(expression) > 200:
                continue
            try:
                parsed = polynomial(ast.parse(expression, mode="eval").body)
            except (SyntaxError, ValueError, RecursionError):
                continue
            equations[name].append(parsed)
    checks = {}
    for name, family in evidence["families"].items():
        expected = {("median",): 1, ("mad",): family["coefficient"]} if name == "CCP" else {
            ("meanlog",): 1, ("sdlog",): family["coefficient"]}
        def same(actual):
            return all(math.isclose(actual.get(k, 0), expected.get(k, 0), abs_tol=1e-10)
                       for k in actual.keys() | expected.keys())
        formula_ok = bool(equations[name]) and all(same(p) for p in equations[name])
        population = set(family["numeric_cells"])
        numeric = {a: point(a) for a in family["sheet_numeric_cells"]}
        cited, accepted, ignored = set(), [], []
        for line in lines:
            for _, sheet, addresses in refs(line):
                if sheet != family["sheet"].casefold():
                    continue
                selected = set()
                for address in addresses:
                    ends = address.split(":")
                    x1, y1 = point(ends[0]); x2, y2 = point(ends[-1])
                    selected.update(a for a, (x, y) in numeric.items() if x1 <= x <= x2 and y1 <= y <= y2)
                # A reference list is one candidate scope; overview references
                # neither supply inputs nor invalidate separate precise scopes.
                if selected and selected <= population:
                    cited.update(selected)
                    accepted.append(addresses)
                elif selected & population:
                    ignored.append(addresses)
        input_ok = cited == population
        checks[name] = {"supported": (formula_ok or input_ok) and not any(not same(p) for p in equations[name]),
                        "formula_supported": formula_ok, "input_supported": input_ok,
                        "accepted_input_references": accepted, "ignored_broad_references": ignored,
                        "missing_input_cells": sorted(population - cited),
                        "conflicting_formula": any(not same(p) for p in equations[name]),
                        "scope": "Source input or threshold equation for the metric family; not proof of execution."}
    return checks


OLD = r"旧(?:因子|阈值)?|历史(?:因子|阈值)?|old(?:\s+(?:factor|threshold))?|historical(?:\s+(?:factor|threshold))?"
NEW = r"当前(?:因子|阈值)?|新(?:因子|阈值)|current(?:\s+(?:factor|threshold))?|new(?:\s+(?:factor|threshold))?"
STATE = r"(?<![A-Za-z])(?:PASS|FAIL)(?![A-Za-z])|不通过|未通过|通过|未达标|达标|>=|<=|<|>|="
PAIR = r"(?<![A-Za-z0-9_])Run\s*0*(\d+)\s*[:：]?\s*(?:样品\s*)?((?:NC|LPC|HPC|MPC|QC-[LH])\d+)(?![A-Za-z0-9_-])"


def states(text, role):
    result = set()
    for match in re.finditer(role, text, re.I):
        fragment = re.split(rf"(?:{OLD}|{NEW})|Run\s*\d+|[;。|]", text[match.end():], maxsplit=1, flags=re.I)[0]
        fragment = re.split(r"但|不过|\bbut\b|批级|batch.level", fragment, maxsplit=1, flags=re.I)[0]
        # Factor assignments are context, not sample comparison states.
        fragment = re.sub(r"\b(?:SCPF|SCPFloating|SCP\s+floating\s+factor)\s*=\s*[+-]?(?:\d+(?:\.\d*)?|\.\d+)", "factor", fragment, flags=re.I)
        if re.search(r"因子|阈值|factor|threshold", match[0], re.I):
            fragment = re.sub(r"^\s*=\s*[+-]?(?:\d+(?:\.\d*)?|\.\d+)", "factor", fragment)
        for value in re.finditer(STATE, fragment, re.I):
            if value.start() <= 48:
                result.add(value[0].upper())
    return result


def matches_state(values, relation):
    def matches(value):
        if value in ("PASS", "通过", "达标"):
            return relation == "<"
        if value in ("FAIL", "不通过", "未通过", "未达标"):
            return relation != "<"
        return value == relation or value == ">=" and relation in (">", "=")
    return bool(values) and all(matches(value) for value in values)


def historical_comparisons(text, evidence, diagnosis, table_rows):
    observations = []
    for paragraph in diagnosis.blocks(text):
        for _, sentences in diagnosis.topic_units(paragraph):
            unit = " ".join(sentences)
            observations.append(unit)
    for headers, cells, line in table_rows(text):
        if len(headers) != len(cells):
            continue
        old = [cells[i] for i, h in enumerate(headers) if re.search(OLD, h, re.I)]
        new = [cells[i] for i, h in enumerate(headers) if re.search(NEW, h, re.I)]
        if len(old) == len(new) == 1:
            observations.append(line + f" 历史因子下的 {old[0]} 当前因子下的 {new[0]}")
    claims = []
    # Each explicit run/sample starts its own scope; comparison signs from a
    # different pair must never be pooled. Paragraph context supplies the factor.
    for unit in observations:
        if re.search(r"TCPF|TCPFloating", unit, re.I) and not re.search(r"SCPF|SCPFloating|筛选浮动", unit, re.I):
            continue
        matches = list(re.finditer(PAIR, unit, re.I))
        shared_old, shared_new = set(), set()
        if len(matches) > 1 and all(re.fullmatch(r"[、,，\s]*", unit[a.end():b.start()]) for a,b in zip(matches,matches[1:])):
            tail = unit[matches[-1].end():]
            shared_old, shared_new = states(tail, OLD), states(tail, NEW)
        for i, match in enumerate(matches):
            fragment = unit[match.end():matches[i + 1].start() if i + 1 < len(matches) else len(unit)]
            if re.search(r"如果|假设|是否|未确认|未证实|并非|不是|未发生|没有发生|未改变|没有改变|并未|尚未|不曾|\bif\b|hypothetical|not\s+(?:confirmed|verified)|did\s+not|does\s+not", fragment, re.I):
                continue
            before, after = states(fragment, OLD) | shared_old, states(fragment, NEW) | shared_new
            # Explicit transitions bind old/new by direction, without requiring
            # a particular 'old factor/current factor' prose template.
            transition = re.search(r"(?:由|从|from)?\s*[‘'\"`“]?\s*(PASS|FAIL|<=|>=|<|>|=)\s*[’'\"`”]?\s*(?:变为|变成|变|改为|转为|→|->|\bto\b)\s*[‘'\"`“]?\s*(PASS|FAIL|<=|>=|<|>|=)(?![=<>])", fragment, re.I)
            if transition:
                before.add(transition[1].upper()); after.add(transition[2].upper())
            if before and after:
                pair = ["Run" + str(int(match[1])), match[2].upper()]
                claims.append({"pairs": [pair], "old": sorted(before), "new": sorted(after), "text": match[0] + fragment})
    checks = []
    for item in evidence["changed_comparisons"]:
        pair = [item["run"], item["sample"]]
        bound = [c for c in claims if pair in c["pairs"]]
        correct = [matches_state(c["old"], item["old_relation"]) and matches_state(c["new"], item["new_relation"]) for c in bound]
        checks.append({"run": item["run"], "sample": item["sample"], "matched": bool(correct) and all(correct),
                       "conflicting_claim": bool(correct) and not all(correct), "claims": bound})
    return sum(c["matched"] for c in checks) / len(checks), checks
