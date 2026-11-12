#!/usr/bin/env python3
"""Condition-blind, deterministic validator for the immunoassay review report."""

from __future__ import annotations

import json
import importlib.util
import math
import re
import sys
import unicodedata
from pathlib import Path


HERE = Path(__file__).resolve().parent
_diagnosis_spec = importlib.util.spec_from_file_location("report_diagnosis", HERE / "diagnosis.py")
DIAGNOSIS = importlib.util.module_from_spec(_diagnosis_spec)
_diagnosis_spec.loader.exec_module(DIAGNOSIS)
_review_spec = importlib.util.spec_from_file_location("report_review_evidence", HERE / "review_evidence.py")
REVIEW = importlib.util.module_from_spec(_review_spec)
_review_spec.loader.exec_module(REVIEW)
_audit_spec = importlib.util.spec_from_file_location("report_formula_audit", HERE / "formula_audit.py")
AUDIT = importlib.util.module_from_spec(_audit_spec)
_audit_spec.loader.exec_module(AUDIT)
_semantic_spec = importlib.util.spec_from_file_location("immunoassay_semantic_judge", HERE / "semantic_judge.py")
SEMANTIC = importlib.util.module_from_spec(_semantic_spec)
_semantic_spec.loader.exec_module(SEMANTIC)
FORMULA_AUDIT_EVIDENCE = json.loads((HERE / "formula_audit_evidence.json").read_text(encoding="utf-8"))
REVIEW_EVIDENCE = json.loads((HERE / "review_evidence.json").read_text(encoding="utf-8"))
DIAGNOSIS_EVIDENCE = json.loads((HERE / "diagnosis_evidence.json").read_text(encoding="utf-8"))
GROUND_TRUTH = json.loads((HERE / "ground_truth.json").read_text(encoding="utf-8"))
EVIDENCE_MAP = json.loads((HERE / "evidence_map.json").read_text(encoding="utf-8"))
INPUT_POPULATIONS = json.loads((HERE / "input_populations.json").read_text(encoding="utf-8"))
NUMBER = r"[-+]?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?"
SCORER_VERSION = "5.0.0"
# The two source-comparison dimensions ask for the deepest findings in the
# workbook: the manual comparison table that disagrees with element data, and
# the four run/sample pairs whose acceptance relation flips between the
# historical and the current floating factor. They stay in the rubric as
# existence checks, but they cannot carry the bulk of the weight: a dimension
# that resolves to the same value for every submission ranks nothing and only
# rescales the rest. The weight sits instead on the review behaviours the task
# actually asks for throughout — an explicit state for every analytical run,
# element-level suitability limits, and the recalculation and formula audit.
WEIGHTS = {"global_metrics": 0.05, "system_adaptability": 0.20,
           "batch_conclusions": 0.30, "method_and_formula": 0.20,
           "traceability_and_impact": 0.10, "source_discrepancy_diagnosis": 0.05,
           "historical_comparison_changes": 0.10}
MISATTRIBUTION_PER_BATCH = 0.02
MISATTRIBUTION_CAP = 0.15
CELL_ADDRESS = r"\$?[A-Z]{1,3}\$?[1-9]\d{0,6}"
ADDRESS = rf"{CELL_ADDRESS}(?:\s*:\s*{CELL_ADDRESS})?(?![A-Za-z0-9_$:])"
ADDRESS_LIST = rf"{ADDRESS}(?:\s*[、,;]\s*{ADDRESS})*"


def column_number(column: str) -> int:
    number = 0
    for char in column.upper():
        number = number * 26 + ord(char) - ord("A") + 1
    return number


def canonical_references(text: str) -> str:
    """Normalize explicit sheet-name/cell bindings, never inherit across prose."""
    text = norm(text)
    quoted = rf"(?:`([^`\n!|]+)`|'([^'\n!|]+)'|\"([^\"\n!|]+)\")[ \t]*(?:![ \t]*|[ \t]+)(?={ADDRESS})"
    text = re.sub(quoted, lambda m: "'" + next(s for s in m.groups() if s is not None).strip() + "'!", text, flags=re.I)
    text = text.replace("`", "")
    # Unquoted whitespace notation is accepted only for explicit Sheet identifiers;
    # arbitrary prose such as 'mean A1' must not manufacture a worksheet anchor.
    return re.sub(rf"(?<![\w])\b(Sheet\d+)[ \t]+(?={ADDRESS})", r"\1!", text, flags=re.I)


def reference_groups(text: str):
    sheet = r"'[^'\n!|]+'|[A-Za-z_\u4e00-\u9fff][\w.\-]*(?:[ \t]*\([^()\n!|]+\))?"
    pattern = rf"(?<![\w])(?P<sheet>{sheet})![ \t]*(?P<addresses>{ADDRESS_LIST})"
    for match in re.finditer(pattern, text, re.I):
        addresses = []
        for address in re.findall(ADDRESS, match["addresses"], re.I):
            address = re.sub(r"[\s$]", "", address).upper()
            points = re.findall(r"([A-Z]+)(\d+)", address)
            x1, y1 = column_number(points[0][0]), int(points[0][1])
            x2, y2 = column_number(points[-1][0]), int(points[-1][1])
            if 1 <= x1 <= x2 <= 16384 and 1 <= y1 <= y2 <= 1048576:
                addresses.append(address)
        if addresses:
            yield match, match["sheet"].strip("'").casefold(), addresses


def norm(value: str) -> str:
    return unicodedata.normalize("NFKC", value).replace("\u00a0", " ")


def read_report(argument: str | None) -> tuple[str, str]:
    candidate = Path(argument or "workspace/output/review_report.md").expanduser()
    candidates: list[Path] = []
    if candidate.is_file():
        candidates = [candidate]
    elif candidate.is_dir():
        candidates = [
            candidate / "review_report.md",
            candidate / "output" / "review_report.md",
            candidate / "05_标准产出.md",
        ]
        candidates.extend(sorted(candidate.rglob("review_report.md")))
        candidates.extend(sorted(candidate.rglob("*.md")))
    for path in candidates:
        if path.is_file():
            raw = path.read_text(encoding="utf-8")
            return norm(raw), path.name
    # Keep verifier output reproducible: never echo an author/container path.
    raise FileNotFoundError("deliverable not found")


def plain(text: str) -> str:
    return canonical_references(text).replace("**", "").strip()


def table_rows(text: str):
    """Read pipe-table headers and rows; never repair a shifted/missing cell."""
    lines = text.splitlines()
    headers = None
    for index, line in enumerate(lines):
        if not line.strip().startswith("|"):
            headers = None
            continue
        cells = [plain(cell) for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if cells and all(re.fullmatch(r":?-+:?", cell.replace(" ", "")) for cell in cells):
            continue
        if index + 1 < len(lines) and re.fullmatch(r"[\s|:\-]+", lines[index + 1]):
            headers = cells
        elif headers is not None:
            yield headers, cells, line


def numeric_cell(value: str, label: str) -> float | None:
    # Precision notes qualify the leading result, not alternative answers.
    unrounded = (
        r"(?:(?:技能|工具|tool|calculator)(?:\s+[A-Za-z_]\w*)?\s*)?"
        r"(?:未(?:中间)?舍入(?:阈值|值|结果)?|unrounded(?:\s+(?:threshold|value|result))?"
        r"|without\s+intermediate\s+rounding)"
        rf"\s*(?:为|=|:)?\s*{NUMBER}\s*%?"
    )
    rounded = r"按源舍入链|按源(?:值)?舍入|按未舍入链|source[- ]rounded|rounded(?:\s+to\s+\d+\s+decimal\s+places)?"
    statistic = rf"(?:n|df|mean|SD|t|%?CV|样本量|自由度|均值|标准差)\s*[:=]\s*{NUMBER}\s*%?"
    statistics = rf"{statistic}(?:\s*[,;]\s*{statistic})*"
    annotation = rf"\(\s*(?:{unrounded}|{rounded}|{statistics})\s*\)"
    source_rounding = (
        r"(?:按源(?:表|值)?\s*(?:\d+\s*位小数\s*)?(?:舍入链|舍入)?\s*(?:为|[:=])"
        r"|(?:source[- ]rounded|rounded\s+to\s+\d+\s+decimal\s+places)\s*(?:is|[:=]))"
        rf"\s*{NUMBER}\s*%?"
    )
    # A source-rounded comparison never replaces the independent leading value.
    match = re.fullmatch(
        rf"\s*({NUMBER})\s*(%)?\s*(?:{annotation}\s*)*(?:,\s*{source_rounding})?\s*",
        plain(value), re.I)
    if not match:
        return None
    number = float(match[1].replace(",", "."))
    if label.upper() == "CCP" and 0 < number < 1 and not match[2]:
        number *= 100
    return number


def metric_label(value: str) -> str:
    value = plain(value)
    # Preserve metric identity; remove only compatible measurement/unit qualifiers.
    cleaned = re.sub(r"\s*\((?:OD|SIR|%)\)\s*", " ", value, flags=re.I)
    # The source workbook uses both ``LPC/NC 下限`` and ``(LPC/NC)下限``.
    # Parentheses are grouping punctuation, not a different metric.
    cleaned = re.sub(r"^\s*\(\s*((?:LPC|HPC)\s*/\s*NC)\s*\)\s*", r"\1 ", cleaned, flags=re.I)
    cleaned = cleaned.strip()
    m = re.fullmatch(r"(NC|LPC/NC|HPC/NC|NC-I|NCI|LPC-I|HPC-I)\s*(OD|SIR)?\s*(上限|下限|upper|lower)", cleaned, re.I)
    if m:
        identity, qualifier, direction = m.groups()
        identity = identity.upper().replace("NCI", "NC-I")
        allowed = "OD" if identity == "NC" else "SIR"
        if not qualifier or qualifier.upper() == allowed:
            direction = {"上限": "upper", "下限": "lower"}.get(direction, direction.lower())
            return identity.lower() + " " + direction
    for abbreviation, expanded in (("SCPF", "SCP floating factor"), ("TCPF", "TCP floating factor")):
        if re.fullmatch(factor_label_pattern(abbreviation, expanded), value, re.I):
            return abbreviation.lower()
    # Only known unit/expanded-name annotations are removable, not CV/MSR labels.
    value = re.sub(r"\s*\((?:OD|%)\)$", "", value, flags=re.I)
    return re.sub(r"\s+(?=上限|下限)", "", value).lower()


def factor_label_pattern(abbreviation: str, expanded: str) -> str:
    name = r"\s+".join(map(re.escape, expanded.split()))
    return rf"(?:{abbreviation}(?:\s*\(\s*{name}\s*\))?|{name}(?:\s*\(\s*{abbreviation}\s*\))?)"


def log_od_cell(value: str) -> float | None:
    """Extract only an explicit OD result from a bounded log/OD result pair."""
    match = re.fullmatch(
        rf"log(?:10)?\s*[:=]\s*{NUMBER}\s*;\s*OD\s*[:=]\s*({NUMBER})",
        plain(value), re.I)
    return float(match[1].replace(",", ".")) if match else None


def number_candidates_after(text: str, label: str) -> list[tuple[float, str, int]]:
    values = []
    label_pattern = (factor_label_pattern(label.upper(), label[:3].upper() + " floating factor")
                     if label.upper() in ("SCPF", "TCPF") else re.escape(label))
    for headers, cells, line in table_rows(text):
        if len(headers) != len(cells):
            continue
        label_columns = [i for i, cell in enumerate(cells) if metric_label(cell) == metric_label(label)]
        result_columns = [i for i, h in enumerate(headers) if re.search(
            r"复算|recalculated|computed|final|result|^值$|^value$", h, re.I)]
        for i in label_columns:
            for j in result_columns:
                # A result cell may append a separately labelled factor.
                value = numeric_cell(cells[j], label)
                if value is None:
                    primary = re.split(r"[;；]", cells[j])[0]
                    value = numeric_cell(primary, label)
                if value is not None:
                    values.append((value, line, 3))
        if label.upper() in ("SCP", "TCP") and any(re.fullmatch(
                rf"{label}\s+log(?:10)?\s*(?:阈值|threshold)", cell, re.I) for cell in cells):
            for j in result_columns:
                value = log_od_cell(cells[j])
                if value is not None:
                    values.append((value, line, 3))
        for j in result_columns:
            for part in re.split(r"[;；]", cells[j]):
                match = re.fullmatch(rf"{label_pattern}\s*(?:[=:：]\s*|\s+)({NUMBER}\s*%?)", part.strip(), re.I)
                if match:
                    value = numeric_cell(match[1], label)
                    if value is not None:
                        values.append((value, line, 3))
        # Wide tables are supported when the row explicitly identifies a result.
        for i, header in enumerate(headers):
            if metric_label(header) == metric_label(label) and any(re.search(
                    r"复算|recalculated|computed|final|result", c, re.I) for c in cells):
                value = numeric_cell(cells[i], label)
                if value is not None:
                    values.append((value, line, 3))
    pattern = re.compile(
        rf"(?<![A-Za-z0-9_/]){label_pattern}(?![A-Za-z0-9_!])"
        rf"\s*(?:=|:|：|为)\s*({NUMBER})\s*(%)?(?![\d.eE])", re.I)
    for line in text.splitlines():
        clean = plain(line)
        if clean.startswith("|") or re.search(
                r"历史|旧因子|旧\s*(?:SCPF|TCPF)|historical|old\s+factor|源值|source.value", clean, re.I):
            continue
        for match in pattern.finditer(clean):
            if re.match(r"\s*[/+*^=]|\s*[-–]\s*\d", clean[match.end():]):
                continue
            value = numeric_cell(match[1] + (match[2] or ""), label)
            if value is not None:
                values.append((value, line, 2))
    return values


def first_number_near(text: str, labels: list[str], expected: float | None = None) -> tuple[float | None, str, str]:
    candidates: list[tuple[float, str, str, int]] = []
    for label in sorted(labels, key=len, reverse=True):
        for value, snippet, context in number_candidates_after(text, label):
            candidates.append((value, snippet, label, context))
    if not candidates:
        return None, "", ""
    best_context = max(item[3] for item in candidates)
    contextual = [item for item in candidates if item[3] == best_context]
    # Extraction must not use the answer key to choose among conflicting values.
    chosen = contextual[0]
    if any(not math.isclose(item[0], chosen[0], rel_tol=1e-9, abs_tol=1e-9) for item in contextual):
        return None, "Conflicting result values: " + " ; ".join(item[1] for item in contextual), chosen[2]
    return chosen[0], chosen[1], chosen[2]


def close(actual: float | None, expected: float, relative: float = 0.002) -> bool:
    if actual is None or not math.isfinite(actual):
        return False
    return abs(actual - expected) <= max(0.001, abs(expected) * relative)


def metric_dimension(text: str) -> tuple[float, dict[str, object]]:
    aliases: dict[str, list[str]] = {
        "SCP": ["SCP", "SCPFloating / SCP"],
        "SCPF": ["SCPF"],
        "CCP": ["CCP"],
        "TCP": ["TCP"],
        "TCPF": ["TCPF"],
    }
    results: dict[str, object] = {}
    hits = 0
    for name, names in aliases.items():
        expected = float(GROUND_TRUTH["global_metrics"][name])
        actual, snippet, label = first_number_near(text, names, expected)
        ok = close(actual, expected, 0.004 if name == "CCP" else 0.003)
        hits += int(ok)
        results[name] = {"expected": expected, "actual": actual, "matched": ok, "label": label, "evidence": snippet}
    return hits / len(aliases), results


def system_dimension(text: str) -> tuple[float, dict[str, object]]:
    aliases: dict[str, list[str]] = {
        "NC upper": ["NC 上限", "NC upper", "NC上限", "NC OD 上限", "NC OD upper"],
        "LPC/NC lower": ["LPC/NC 下限", "LPC/NC lower", "LPC/NC下限", "LPC/NC SIR 下限", "LPC/NC SIR lower"],
        "HPC/NC lower": ["HPC/NC 下限", "HPC/NC lower", "HPC/NC下限", "HPC/NC SIR 下限", "HPC/NC SIR lower"],
        "NC-I upper": ["NC-I 上限", "NC-I upper", "NCI 上限", "NC-I上限", "NC-I SIR 上限", "NC-I SIR upper"],
        "LPC-I lower": ["LPC-I 下限", "LPC-I lower", "LPC-I下限", "LPC-I SIR 下限", "LPC-I SIR lower"],
        "HPC-I lower": ["HPC-I 下限", "HPC-I lower", "HPC-I下限", "HPC-I SIR 下限", "HPC-I SIR lower"],
    }
    results: dict[str, object] = {}
    hits = 0
    for name, names in aliases.items():
        expected = float(GROUND_TRUTH["system_metrics"][name])
        actual, snippet, label = first_number_near(text, names, expected)
        ok = close(actual, expected, 0.002)
        hits += int(ok)
        results[name] = {"expected": expected, "actual": actual, "matched": ok, "label": label, "evidence": snippet}
    return hits / len(aliases), results


def lines_for(text: str, token: str) -> list[str]:
    return [line for line in text.splitlines() if token.lower() in line.lower()]


def state(value: str) -> str | None:
    value = plain(value)
    value = re.sub(r"^(?:客观|正式|综合|objective|overall)(?:状态|status)?\s*[:：]?\s*", "", value, flags=re.I)
    # Interpret only the leading status declaration, not status words in its
    # explanation. Mixed declarations must not silently become PASS or FAIL.
    declaration = re.split(r"[:;；,(。.]|源状态|source_status", value, maxsplit=1)[0].strip()
    aliases = {"FAIL": r"FAIL|FAILED|不通过|失败|不合格|不PASS",
               "PASS": r"PASS|PASSED|通过|合格",
               "PENDING": r"PENDING|待确认|待定"}
    parts = re.split(r"\s*(?:/|、|\bor\b|\band\b|或|且)\s*", declaration, flags=re.I)
    states = []
    for part in parts:
        found = next((name for name, pattern in aliases.items() if re.fullmatch(pattern, part, re.I)), None)
        if found is None:
            return None
        states.append(found)
    return states[0] if len(set(states)) == 1 else "CONFLICT"


def batch_id(label: str) -> str | None:
    annotation = r"拒绝|拒收|排除|变更|正常|rejected|excluded|changed|amended"
    match = re.fullmatch(rf"(?:Run\s*)?0*(\d+)(?:\s*(?:\(\s*(?:{annotation})\s*\)|-\s*(?:{annotation})))?", plain(label), re.I)
    return "Run" + str(int(match[1])) if match else None


def batch_records(text: str, diagnostics: dict | None = None) -> tuple[dict, list[str]]:
    records = {}
    malformed = []
    listed = set()
    unparsed = []
    other = None
    accepted_ids = set(GROUND_TRUTH["batch_ids"]) | {"Run1"}
    for headers, cells, line in table_rows(text):
        batch_cols = [i for i, h in enumerate(headers) if re.search(r"分析批|批次|batch|^run$", h, re.I)]
        objective = [i for i, h in enumerate(headers) if re.search(r"客观|objective", h, re.I)]
        status_cols = objective or [i for i, h in enumerate(headers) if re.search(
            r"综合|正式状态|overall|^status$|^状态$|^结论$", h, re.I)]
        if not batch_cols or not status_cols:
            continue
        if batch_cols[0] < len(cells):
            batch = batch_id(cells[batch_cols[0]])
            if batch in accepted_ids:
                listed.add(batch)
        if len(cells) != len(headers):
            malformed.append(line)
            continue
        label = cells[batch_cols[0]]
        result = state(cells[status_cols[0]])
        if result is None:
            batch = batch_id(label)
            if batch in accepted_ids:
                unparsed.append({"batch_label": label, "status_text": cells[status_cols[0]], "evidence": line})
            continue
        source = " ".join(cells[i] for i, h in enumerate(headers) if re.search(r"源状态|source", h, re.I))
        record = {"status": result, "source": source, "evidence": line}
        batch = batch_id(label)
        if batch:
            if batch not in accepted_ids:
                continue
            if batch in records and records[batch]["status"] != result:
                record["status"] = "CONFLICT"
            records[batch] = record
        elif re.fullmatch(r"其他(?:实际)?分析批|所有其他批次|(?:all\s+)?other\s+(?:actual\s+)?(?:batches|runs)", label, re.I):
            other = record
    for line in text.splitlines():
        if line.lstrip().startswith(("|", "#")):
            continue
        clean = plain(line)
        match = re.match(r"^(?:[-*]\s*)?(Run[^:]+)\s*:\s*(.+)$", clean, re.I)
        if not match:
            continue
        batch = batch_id(match[1])
        declaration = re.split(r"[。;；]", match[2])[0]
        result = state(declaration)
        if result is None and not re.match(
                r"(?:客观|正式|综合|状态|objective|overall|status|PASS|FAIL|PENDING|CONFLICT|UNKNOWN|通过|不通过|待确认|待定|尚未审计)",
                declaration.strip(), re.I):
            # A batch-prefixed finding is not itself a status declaration.
            continue
        if batch in accepted_ids:
            listed.add(batch)
        if batch not in accepted_ids:
            continue
        if result is None:
            unparsed.append({"batch_label": batch, "status_text": match[2], "evidence": line})
            continue
        previous = records.get(batch)
        records[batch] = {"status": result if not previous or previous["status"] == result else "CONFLICT",
                          "source": match[2], "evidence": line}
    # A collective conclusion cannot repair an explicitly listed invalid row.
    if other:
        for batch in accepted_ids:
            if batch not in listed:
                records.setdefault(batch, other)
    if diagnostics is not None:
        diagnostics.update({"explicitly_listed_batches": sorted(listed, key=lambda s: int(s[3:])),
                            "unparsed_status_rows": unparsed})
    return records, malformed


def summary_counts(text: str) -> dict[str, list[int]]:
    counts = {"PASS": [], "FAIL": [], "PENDING": []}
    labels = {"PASS": r"通过|(?<!不)\bPASS(?:ED)?\b", "FAIL": r"不通过|失败|\bFAIL(?:ED)?\b",
              "PENDING": r"待确认|待定|\bPENDING\b"}
    for line in text.splitlines():
        if line.lstrip().startswith("|"):
            continue
        for status, label in labels.items():
            patterns = [
                rf"(?<![\w.])(?P<n>\d+)\s*(?:个\s*)?(?:有效\s*)?(?:分析批|批次|批)?\s*(?:{label})",
                rf"(?:{label})\s*[:：]\s*(?P<n>\d+)(?![\d.])",
            ]
            for pattern in patterns:
                counts[status].extend(int(m["n"]) for m in re.finditer(pattern, line, re.I))
    return counts


def batch_dimension(text: str) -> tuple[float, dict[str, object]]:
    parsing = {}
    records, malformed = batch_records(text, parsing)
    coverage = len(set(records) & set(GROUND_TRUTH["batch_ids"])) / len(GROUND_TRUTH["batch_ids"])
    run21 = records.get("Run21", {})
    run21_ok = run21.get("status") in ("PASS", "FAIL", "PENDING") and bool(re.search(
        r"EXCLUDED|拒绝|排除|拒收", run21.get("source", ""), re.I))
    totals = {s: sum(r["status"] == s for r in records.values()) for s in ("PASS", "FAIL", "PENDING", "CONFLICT")}
    reported = summary_counts(text)
    count_ok = (coverage == 1 and totals["CONFLICT"] == 0
                and not malformed and not parsing["unparsed_status_rows"]
                and all(n == totals[s] for s, counts in reported.items() for n in counts))
    status_variety = totals["PASS"] > 0 and totals["FAIL"] > 0
    # Missing acceptance rules cannot establish a required PASS/FAIL distribution.
    score = (coverage + float(run21_ok) + float(count_ok)) / 3
    return score, {
        **parsing,
        "coverage": coverage,
        "inventory_coverage": len(set(parsing["explicitly_listed_batches"]) & set(GROUND_TRUTH["batch_ids"])) / len(GROUND_TRUTH["batch_ids"]),
        "listed_batches": len(records),
        "optional_source_batches_included": sorted(set(records) - set(GROUND_TRUTH["batch_ids"])),
        "objective_totals": totals,
        "reported_counts": reported,
        "malformed_rows": malformed,
        "records": records,
        "run21_source_objective_split": run21_ok,
        "count_closure": count_ok,
        "status_variety": status_variety,
        "formal_dispositions_verified": False,
        "scope": "Inventory, internal count reconciliation, and recorded source-status separation only",
    }


def body_lines(text: str) -> list[str]:
    rows = {line for _, cells, line in table_rows(text)
            if any(cell and not re.search(r"待填写|IN_PROGRESS", cell) for cell in cells)}
    return [plain(line) for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
            and (not line.lstrip().startswith("|") or line in rows)
            and not re.search(r"待填写|IN_PROGRESS", line)]


def audit_counts(text: str) -> dict[str, bool]:
    aliases = {
        "replicate_mean": r"复孔均值|replicate\s+mean",
        "replicate_sd": r"复孔样本\s*SD|复孔标准差|replicate\s+(?:sample\s+)?SD",
        "replicate_cv": r"复孔\s*CV|replicate\s+CV",
        "sir": r"SIR",
        "mean_ncod": r"Mean\s*\(\s*NCOD\s*\)",
    }
    found = {key: [] for key in aliases}
    for headers, cells, _ in table_rows(text):
        if len(headers) != len(cells):
            continue
        count_cols = [i for i, h in enumerate(headers) if re.search(r"检查数量|检查数|checked|count", h, re.I)]
        for key, alias in aliases.items():
            if any(re.fullmatch(alias, c, re.I) for c in cells):
                for i in count_cols:
                    value = numeric_cell(cells[i], "count")
                    if value is not None:
                        found[key].append(value)
    for line in body_lines(text):
        if line.startswith("|"):
            continue
        for key, alias in aliases.items():
            match = re.search(rf"(?:{alias})\s*(?:实际检查|检查数量|检查|checked|count)\s*[:：=]?\s*(\d+)\b", line, re.I)
            if match:
                found[key].append(int(match[1]))
    return {key: bool(values) and all(v == GROUND_TRUTH["formula_checks"][key] for v in values)
            for key, values in found.items()}


def pattern_dimension(text: str) -> tuple[float, dict[str, object]]:
    """Check cited suitability populations, not claimed execution or method words."""
    results = system_dimension(text)[1]
    observations = {metric: [] for metric in results}
    labels = {metric_label(name): key for key, names in {
        "NC upper": ["NC 上限", "NC upper"],
        "LPC/NC lower": ["LPC/NC 下限", "LPC/NC lower"],
        "HPC/NC lower": ["HPC/NC 下限", "HPC/NC lower"],
        "NC-I upper": ["NC-I 上限", "NC-I upper", "NCI 上限"],
        "LPC-I lower": ["LPC-I 下限", "LPC-I lower"],
        "HPC-I lower": ["HPC-I 下限", "HPC-I lower"],
    }.items() for name in names}
    for headers, cells, line in table_rows(text):
        if len(headers) != len(cells):
            continue
        metrics = {labels[metric_label(c)] for c in cells if metric_label(c) in labels}
        if len(metrics) == 1:
            metric = next(iter(metrics))
            observations[metric].append(line)
            sheets = {sheet for _, sheet, _ in reference_groups(plain(line))}
            if len(sheets) == 1:
                sheet = next(iter(sheets))
                for header, cell in zip(headers, cells):
                    if not re.search(r"元素范围|输入范围|有效输入|input|population", header, re.I):
                        continue
                    if list(reference_groups(plain(cell))) or "!" in cell:
                        continue
                    # A unique sheet on the same metric row binds its input column.
                    for address in re.findall(rf"(?<![\w!]){ADDRESS}", cell, re.I):
                        observations[metric].append("'" + sheet + "'!" + address)
    # Prose accepts an explicit metric prefix; no format unique to Golden is required.
    for line in body_lines(text):
        if line.startswith("|"):
            continue
        prefix = re.split(r"[:=：]", line, maxsplit=1)[0].strip(" -*")
        if metric_label(prefix) in labels:
            observations[labels[metric_label(prefix)]].append(line)

    def point(address):
        col, row = re.fullmatch(r"([A-Z]+)(\d+)", address).groups()
        return column_number(col), int(row)

    numeric = {a: point(a) for a in INPUT_POPULATIONS["numeric_cells"]}
    checks = {}
    for metric, population in INPUT_POPULATIONS["populations"].items():
        expected = set(population["numeric_cells"])
        cited, extra, refs = set(), set(), []
        for line in observations[metric]:
            for _, sheet, addresses in reference_groups(plain(line)):
                if sheet != INPUT_POPULATIONS["sheet"].casefold():
                    continue
                for address in addresses:
                    ends = address.split(":")
                    left, top = point(ends[0])
                    right, bottom = point(ends[-1])
                    selected = {a for a, (x, y) in numeric.items() if left <= x <= right and top <= y <= bottom}
                    # Summary/result anchors do not describe an input population.
                    if selected & expected:
                        cited.update(selected & expected)
                        extra.update(selected - expected)
                        refs.append(address)
        matched = cited == expected and not extra and results[metric]["matched"]
        checks[metric] = {"matched": matched, "expected_numeric_count": len(expected),
                          "cited_numeric_count": len(cited), "extra_numeric_cells": sorted(extra),
                          "missing_numeric_cells": sorted(expected - cited), "references": sorted(set(refs)),
                          "result_correct": results[metric]["matched"]}
    return sum(c["matched"] for c in checks.values()) / len(checks), checks


def impact_dimension(text: str) -> tuple[float, dict[str, object]]:
    batch_detail = batch_dimension(text)[1]
    text = "\n".join(body_lines(text))
    anchors = {(sheet, address) for _, sheet, addresses in reference_groups(text) for address in addresses}
    evidence_hits = len(anchors)
    evidence = min(1.0, evidence_hits / 4)
    factors = all(any(re.search(rf"\b{name}\b", line, re.I) and value in line
                         and re.search(r"\bRun\s*\d+", line, re.I)
                         and re.search(r"浮动|Floating|插值|interpol", line, re.I)
                         for line in text.splitlines())
                  for name, value in GROUND_TRUTH["old_factors"].items())
    boundary = r"不受影响|不影响|不依赖|不改变|独立|unaffected|independent|do(?:es)? not (?:affect|depend|change)"
    no_global_impact = any(re.search(r"全局|系统适应性|global|system.suitability", paragraph, re.I)
                          and re.search(boundary, paragraph, re.I)
                          and re.search(r"旧因子|历史因子|旧浮动|historical|old.factor", paragraph, re.I)
                          for paragraph in re.split(r"[。\n]", text))
    separation = batch_detail["run21_source_objective_split"]
    pending = any(re.search(r"待确认|观察项|PENDING|undecided", line, re.I)
                  and re.search(r"CV|滴度|MPC|规则|依据|缺|titer|rule|evidence", line, re.I)
                  for line in text.splitlines())
    score = (evidence + float(factors) + float(no_global_impact) + float(separation) + float(pending)) / 5
    return score, {
        "evidence_anchor_count": evidence_hits,
        "old_factor_scope": factors,
        "global_scope_boundary": no_global_impact,
        "source_objective_separation": separation,
        "pending_items": pending,
    }


def evidence_attribution(text: str) -> dict[str, object]:
    checked = set()
    violations = []
    ambiguous = []
    skipped = set()
    failed_batches = set()

    def mentioned_batches(value):
        return {"Run" + str(int(m[1])) for m in re.finditer(
            r"(?<![A-Za-z0-9_])run\s*0*(\d+)(?![\d!])", value, re.I)}

    for headers, cells, line in table_rows(text):
        batch_columns = [i for i, h in enumerate(headers) if re.search(r"分析批|批次|batch|^run$", h, re.I)]
        if not batch_columns or batch_columns[0] >= len(cells):
            continue
        batch = batch_id(cells[batch_columns[0]])
        if not batch:
            continue
        row_mentions = mentioned_batches(" ".join(cells)) - {batch}
        for cell in cells:
            previous_reference_end = 0
            for group, sheet, addresses in reference_groups(cell):
                local_context = re.split(r"[;。]", cell[previous_reference_end:group.start()])[-1]
                local_mentions = mentioned_batches(local_context)
                previous_reference_end = group.end()
                if sheet != "sheet1":
                    continue
                # Omitted sheet names inherit only inside a contiguous reference list.
                for citation in addresses:
                    points = re.findall(r"([A-Z]+)(\d+)", citation)
                    start, end = points[0], points[-1]
                    x1, x2 = column_number(start[0]), column_number(end[0])
                    y1, y2 = int(start[1]), int(end[1])
                    if x1 > x2 or y1 > y2:
                        continue
                    owners = {block["batch"] for block in EVIDENCE_MAP["blocks"]
                              if x1 <= column_number(block["last_column"]) and x2 >= column_number(block["first_column"])
                              and y1 <= block["last_row"] and y2 >= block["first_row"]}
                    if not owners:
                        continue
                    claimed = next(iter(local_mentions)) if len(local_mentions) == 1 else batch
                    uncertain = len(local_mentions) > 1 or (
                        not local_mentions and batch not in owners and bool(row_mentions & owners))
                    if uncertain:
                        key = (batch, citation)
                        if key not in skipped:
                            skipped.add(key)
                            ambiguous.append({"row_batch": batch, "reference": "Sheet1!" + citation,
                                              "actual_batches": sorted(owners), "evidence": line,
                                              "reason": "Other batch explicitly mentioned; citation binding is ambiguous"})
                        continue
                    if (claimed, citation) in checked:
                        continue
                    checked.add((claimed, citation))
                    if claimed not in owners:
                        failed_batches.add(claimed)
                        violations.append({"claimed_batch": claimed, "row_batch": batch, "reference": "Sheet1!" + citation,
                                           "actual_batches": sorted(owners), "evidence": line})
    deduction = min(MISATTRIBUTION_CAP, MISATTRIBUTION_PER_BATCH * len(failed_batches))
    return {"checked_references": len(checked), "mismatched_batches": sorted(failed_batches),
            "ambiguous_references": ambiguous,
            "violations": violations, "deduction": round(deduction, 6),
            "scope": EVIDENCE_MAP["scope"]}


def _deterministic_evaluate(text: str) -> dict[str, object]:
    text = norm(text)
    readable = len(text.strip()) >= 300
    leakage = bool(re.search(r"ground[_ -]?truth|reference[_ -]?solution|hidden\s+oracle|隐藏答案|内部构造信息", text, re.I))
    global_score, global_detail = metric_dimension(text)
    system_score, system_detail = system_dimension(text)
    batch_score, batch_detail = batch_dimension(text)
    method_score, method_detail = pattern_dimension(text)
    suitability_input_score = method_score
    audit_score, audit_detail = AUDIT.evaluate(text, GROUND_TRUTH["formula_checks"], FORMULA_AUDIT_EVIDENCE,
                                             DIAGNOSIS, table_rows, lambda s: reference_groups(plain(s)))
    method_score = (2 * suitability_input_score + audit_score) / 3
    support = REVIEW.calculation_support(text, REVIEW_EVIDENCE, reference_groups, body_lines)
    family = {"SCP": "LogSCP", "SCPF": "LogSCP", "TCP": "LogTCP", "TCPF": "LogTCP", "CCP": "CCP"}
    raw_global_score, raw_system_score = global_score, system_score
    # Reporting the right value and showing the calculation that supports it are
    # two separate pieces of work, so they are credited separately. Requiring
    # both before either counts made a review that identified every limit
    # correctly, but had not finished the formula audit, score the same as one
    # that identified none of them — a difference the reviewer would care about.
    # The supported half stays worth more, because an unsupported figure is the
    # weaker result.
    SUPPORTED_SHARE = 0.6
    global_score = sum(
        (1.0 - SUPPORTED_SHARE) * bool(d["matched"])
        + SUPPORTED_SHARE * bool(d["matched"] and support[family[name]]["supported"])
        for name, d in global_detail.items()
    ) / len(global_detail)
    system_score = sum(
        (1.0 - SUPPORTED_SHARE) * bool(d["matched"])
        + SUPPORTED_SHARE * bool(d["matched"] and method_detail[name]["matched"])
        for name, d in system_detail.items()
    ) / len(system_detail)
    impact_score, impact_detail = impact_dimension(text)
    attribution = evidence_attribution(text)
    diagnosis_score, diagnosis_detail = DIAGNOSIS.evaluate(text, DIAGNOSIS_EVIDENCE,
                                                         lambda s: reference_groups(plain(s)))
    inventory_accuracy = DIAGNOSIS.inventory_penalty(text, DIAGNOSIS_EVIDENCE["counts"]["formula_cells"], body_lines)
    historical_score, historical_detail = REVIEW.historical_comparisons(text, REVIEW_EVIDENCE, DIAGNOSIS, table_rows)

    section_keywords = ["规则", "指标", "系统", "分析批", "公式", "待确认"]
    section_count = sum(keyword in text for keyword in section_keywords)
    totals = batch_detail["objective_totals"]
    status_dump = (batch_detail["coverage"] == 1
                   and not batch_detail["unparsed_status_rows"]
                   and not batch_detail["malformed_rows"]
                   and max(totals["PASS"], totals["FAIL"]) == len(GROUND_TRUTH["batch_ids"]))
    core_missing = raw_global_score == 0 and raw_system_score == 0
    completeness_factors = {}
    gate_factor = 1.0
    if not readable or core_missing:
        gate_factor = 0.0
    else:
        if batch_detail["coverage"] < 0.8:
            gate_factor *= 0.6
        if impact_detail["evidence_anchor_count"] < int(GROUND_TRUTH["evidence_minimum"]):
            gate_factor *= 0.7

    dimensions = {"global_metrics": global_score, "system_adaptability": system_score,
                  "batch_conclusions": batch_score, "method_and_formula": method_score,
                  "traceability_and_impact": impact_score,
                  "source_discrepancy_diagnosis": diagnosis_score,
                  "historical_comparison_changes": historical_score}
    weighted_score = sum(WEIGHTS[name] * score for name, score in dimensions.items())
    reward = max(0.0, min(1.0, gate_factor * weighted_score - attribution["deduction"] - inventory_accuracy["deduction"]))

    # Retain useful contract diagnostics without emitting another score.
    global_present = sum(item["actual"] is not None for item in global_detail.values()) >= 4
    system_present = sum(item["actual"] is not None for item in system_detail.values()) >= 5
    contract_whole = readable and section_count >= 5 and global_present and system_present and batch_detail["coverage"] >= 0.8
    method_coherent = method_score >= 0.70
    source_split = bool(impact_detail["source_objective_separation"] and batch_detail["run21_source_objective_split"])
    undecidable = bool(impact_detail["pending_items"])

    # Second lens: was a usable review delivered at all?  Strict weighs how well
    # each dimension was judged; this asks only whether the report is readable,
    # carries every required section, populates the global and system metrics,
    # covers the batches, and keeps source findings apart from objective ones --
    # the things the assignment states outright.  A run can satisfy this and
    # still judge badly, or judge well and hand back an unusable report.
    lenient_checks = {
        "report_readable": bool(readable),
        "all_sections_present": section_count >= 5,
        "global_metrics_populated": bool(global_present),
        "system_metrics_populated": bool(system_present),
        "batch_coverage_met": batch_detail["coverage"] >= 0.8,
        "source_and_objective_kept_apart": bool(source_split),
    }
    lenient = 1.0 if all(lenient_checks.values()) else 0.0

    return {
        "scorer_version": SCORER_VERSION,
        "reward": round(reward, 6),
        "reward_strict": round(reward, 6),
        "reward_lenient": lenient,
        "rewards": {"strict": round(reward, 6), "lenient": lenient},
        "reward_formulas": {
            "strict": "max(0, gate_factor * weighted_dimension_scores - itemized_deductions)",
            "lenient": "1 iff the report is readable with every required section, global and system metrics populated, batch coverage at or above 0.8, and source findings kept apart from objective ones",
        },
        "lenient_checks": lenient_checks,
        "reward_formula": "max(0, gate_factor * (0.05*global_metrics + 0.20*system_adaptability + 0.30*batch_conclusions + 0.20*method_and_formula + 0.10*traceability_and_impact + 0.05*source_discrepancy_diagnosis + 0.10*historical_comparison_changes) - evidence_misattribution_deduction - inventory_accuracy_deduction)",
        "dimension_scores": {
            "global_metrics": round(global_score, 6),
            "system_adaptability": round(system_score, 6),
            "batch_conclusions": round(batch_score, 6),
            "method_and_formula": round(method_score, 6),
            "traceability_and_impact": round(impact_score, 6),
            "source_discrepancy_diagnosis": round(diagnosis_score, 6),
            "historical_comparison_changes": round(historical_score, 6),
        },
        "group_points": {
            "global_metrics": round(global_score, 6),
            "system_adaptability": round(system_score, 6),
            "batch_conclusions": round(batch_score, 6),
            "method_and_formula": round(method_score, 6),
            "traceability_and_impact": round(impact_score, 6),
            "source_discrepancy_diagnosis": round(diagnosis_score, 6),
            "historical_comparison_changes": round(historical_score, 6),
        },
        "diagnostic_scores": {
            "gate_factor": round(gate_factor, 6),
            "numeric_agreement_before_support": {"global_metrics": raw_global_score, "system_adaptability": raw_system_score},
            "single_status_dump": status_dump,
            "weighted_score_before_gate": round(weighted_score, 6),
            "score_before_deduction": round(gate_factor * weighted_score, 6),
            "completeness_factors": completeness_factors,
            "formula_audit_complete": None,
            "formula_audit_scope": "Source-grounded summary coverage is scored; execution and sample eligibility are not certified",
            "formula_audit_summary_score": round(audit_score, 6),
            "suitability_input_score": round(suitability_input_score, 6),
            "declared_audit_counts_match": audit_counts(text),
            "formal_batch_dispositions_verified": False,
            "evidence_misattribution_deduction": attribution["deduction"],
            "inventory_accuracy_deduction": inventory_accuracy["deduction"],
            "section_count": section_count,
            "readable": readable,
            "leakage": None,
            "leakage_terms_present": leakage,
            "leakage_scope": "Report wording cannot establish hidden-file access; not a scoring gate",
            "contract_whole": contract_whole,
            "global_fields_present": global_present,
            "system_fields_present": system_present,
            "method_coherent": method_coherent,
            "objective_source_status_separated": source_split,
            "undecidable_items_preserved": undecidable,
        },
        "checks": {
            "global_metrics": global_detail,
            "system_adaptability": system_detail,
            "batch_conclusions": batch_detail,
            "method_and_formula": method_detail,
            "formula_audit_summaries": audit_detail,
            "traceability_and_impact": impact_detail,
            "evidence_attribution": attribution,
            "source_discrepancy_diagnosis": diagnosis_detail,
            "inventory_accuracy": inventory_accuracy,
            "calculation_support": support,
            "historical_comparison_changes": historical_detail,
        },
    }


def evaluate(text: str) -> dict[str, object]:
    """Mixed evaluation: deterministic facts plus evidence-bound semantic review."""
    deterministic = _deterministic_evaluate(text)
    semantic = SEMANTIC.evaluate(text)
    decisions = semantic["criteria"]
    contradictions = semantic["contradictions"]

    def semantic_completion(name):
        value = float(decisions[name]["completion"])
        if name == "formal_rule_sufficiency" and contradictions["unsupported_formal_rule"]["present"]:
            return 0.0
        if name == "source_discrepancy_diagnosis" and contradictions["discrepancy_negated_or_priority_reversed"]["present"]:
            return 0.0
        if name == "historical_impact_boundary" and contradictions["historical_change_negated_or_reversed"]["present"]:
            return 0.0
        if name == "conclusion_traceability" and contradictions["material_internal_contradiction"]["present"]:
            return min(value, 0.5)
        return value

    global_checks = deterministic["checks"]["global_metrics"]
    system_checks = deterministic["checks"]["system_adaptability"]
    global_numeric = sum(bool(row["matched"]) for row in global_checks.values()) / len(global_checks)
    system_numeric = sum(bool(row["matched"]) for row in system_checks.values()) / len(system_checks)
    metric_semantic = semantic_completion("metric_identity_and_input_binding")
    expected_global = json.loads((HERE / "semantic_contract.json").read_text(encoding="utf-8"))["verified_values"]["global"]
    expected_system = json.loads((HERE / "semantic_contract.json").read_text(encoding="utf-8"))["verified_values"]["system_suitability"]

    def mapped_score(expected):
        matched = 0
        for name, target in expected.items():
            actual = semantic["metrics"][name]["value"]
            matched += actual is not None and close(float(actual), float(target), 0.004 if name == "CCP_percent" else 0.003)
        return matched / len(expected)

    # The judge establishes semantic identity and binds an exact candidate quote;
    # program code then verifies the quoted number against workbook-derived truth.
    global_numeric = max(global_numeric, mapped_score(expected_global))
    system_numeric = max(system_numeric, mapped_score(expected_system))
    batch_inventory = float(deterministic["checks"]["batch_conclusions"]["inventory_coverage"])

    contract = json.loads((HERE / "semantic_contract.json").read_text(encoding="utf-8"))
    expected_audits = contract["verified_values"]["formula_audit_families"]
    audit_count_score = sum(semantic["audit_counts"][name]["count"] == target
                            for name, target in expected_audits.items()) / len(expected_audits)
    components = {
        "deterministic_global_values": (0.08, global_numeric),
        "deterministic_system_values": (0.12, system_numeric),
        "deterministic_batch_inventory": (0.10, batch_inventory),
        "deterministic_formula_counts": (0.05, audit_count_score),
    }
    for criterion in contract["criteria"]:
        scoring_weight = {"metric_identity_and_input_binding": 0.15,
                          "formula_audit_quality": 0.06}.get(criterion["id"], float(criterion["weight"]))
        components[criterion["id"]] = (scoring_weight, semantic_completion(criterion["id"]))
    if not math.isclose(sum(weight for weight, _ in components.values()), 1.0, abs_tol=1e-12):
        raise RuntimeError("Scoring weights do not sum to one")

    weighted = sum(weight * completion for weight, completion in components.values())
    attribution = deterministic["checks"]["evidence_attribution"]
    inventory = deterministic["checks"]["inventory_accuracy"]
    deduction = float(attribution["deduction"]) + float(inventory["deduction"])
    strict = max(0.0, min(1.0, weighted - deduction))

    required_sections = set("一二三四五六七")
    present_sections = set(re.findall(r"(?m)^##\s*([一二三四五六七])、", text))
    section_coverage = len(present_sections) / len(required_sections)
    readable = bool(text.strip())
    batch_detail = deterministic["checks"]["batch_conclusions"]
    batch_records = batch_detail["records"]
    every_batch_has_cell_reference = (
        len(batch_records) == len(GROUND_TRUTH["batch_ids"])
        and all(any(reference_groups(row["evidence"])) for row in batch_records.values()))
    all_core_metrics_mapped = all(row["value"] is not None for row in semantic["metrics"].values())
    all_formal_statuses_pending = (
        batch_detail["inventory_coverage"] == 1.0
        and batch_detail["objective_totals"]["PENDING"] == len(GROUND_TRUTH["batch_ids"])
        and batch_detail["objective_totals"]["PASS"] == 0
        and batch_detail["objective_totals"]["FAIL"] == 0
        and batch_detail["objective_totals"]["CONFLICT"] == 0)
    # Independent binary usability contract. This is a conjunction of minimum
    # viable deliverable requirements, never a threshold on the strict score.
    # Local analytical imperfections may coexist with a usable report; inventing
    # the absent governing rules cannot.
    lenient_checks = {
        "readable_markdown": bool(readable),
        "all_seven_sections_present": section_coverage == 1.0,
        "all_core_metrics_mapped": all_core_metrics_mapped,
        "all_36_batches_listed": batch_detail["inventory_coverage"] == 1.0,
        "all_formal_statuses_pending": all_formal_statuses_pending,
        "every_batch_has_cell_reference": every_batch_has_cell_reference,
        "no_unsupported_formal_rule": not contradictions["unsupported_formal_rule"]["present"],
        "no_material_internal_contradiction": not contradictions["material_internal_contradiction"]["present"],
    }
    lenient = 1.0 if all(lenient_checks.values()) else 0.0

    return {
        "scorer_version": SCORER_VERSION,
        "status": "MEASURED",
        "reward": round(strict, 6),
        "reward_strict": round(strict, 6),
        "reward_lenient": round(lenient, 6),
        "rewards": {"strict": round(strict, 6), "lenient": round(lenient, 6)},
        "reward_formulas": {
            "strict": "sum(documented deterministic and semantic weighted components) - itemized source deductions",
            "lenient": "1 iff every documented direct usability requirement is satisfied; otherwise 0",
        },
        "dimension_scores": {name: round(value, 6) for name, (_, value) in components.items()},
        "component_weights": {name: weight for name, (weight, _) in components.items()},
        "lenient_checks": lenient_checks,
        "diagnostic_scores": {
            "weighted_score_before_deduction": round(weighted, 6),
            "source_misattribution_deduction": attribution["deduction"],
            "inventory_accuracy_deduction": inventory["deduction"],
            "judge_origin": semantic["origin"],
            "judge_request_sha256": semantic["request_sha256"],
        },
        "checks": {
            "deterministic": deterministic["checks"],
            "semantic": decisions,
            "semantic_contradictions": contradictions,
        },
    }


def main() -> int:
    try:
        text, _ = read_report(sys.argv[1] if len(sys.argv) > 1 else None)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        # A run that produced nothing still has to emit the full dual-score
        # payload. Consumers read strict and lenient by key, so a short
        # fallback shape makes an honest zero unreadable to them and is
        # indistinguishable from a scorer that never ran.
        result = {
            "scorer_version": SCORER_VERSION,
            "reward": 0.0,
            "reward_strict": 0.0,
            "reward_lenient": 0.0,
            "rewards": {"strict": 0.0, "lenient": 0.0},
            "reward_formulas": {
                "strict": "no readable report => strict=0",
                "lenient": "no readable report => lenient=0",
            },
            "reward_formula": "unreadable => reward=0",
            "dimension_scores": {},
            "group_points": {},
            "lenient_checks": {},
            "diagnostic_scores": {"error": str(exc)},
            "checks": {},
        }
    else:
        try:
            result = evaluate(text)
        except SEMANTIC.JudgeInfrastructureError as exc:
            print(json.dumps({"scorer_version": SCORER_VERSION, "status": "UNMEASURED",
                              "error": str(exc)}, ensure_ascii=False, indent=2, sort_keys=True))
            return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
