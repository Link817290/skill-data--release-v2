from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import unicodedata

from openpyxl import load_workbook


INPUT_XLSX = "匿名体检检查明细.xlsx"
OUTPUT_XLSX = "体检总检结论.xlsx"

# Second, co-equal standard: how far an output may over-generate before it is
# treated as a raw dump of the detail rows rather than a set of conclusions.
FIDELITY_FLOOR = 0.42
DUMP_FACTOR = 4
# A truly-normal case still counts as "restrained" for the lenient completion
# check if it carries no more than this many spurious findings. The exact-string
# summary status is graded elsewhere and is not gated here.
# A normal case is a hard negative: one stray finding is tolerated for a
# transcription slip, but a majority of normal cases must remain clean.
RESTRAINT_FP_TOLERANCE = 1


def text(value: object) -> str:
    return "" if value is None else str(value).strip()


def canonical(value: object) -> str:
    """Only normalize orthography; do not broaden institutional terminology."""
    result = unicodedata.normalize("NFKC", text(value)).lower()
    result = result.replace("反流", "返流")
    result = result.replace("ⅰ", "i").replace("ⅱ", "ii")
    result = result.replace("ii度", "2度").replace("i度", "1度")
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", result)


def split_ids(value: object) -> set[str]:
    return {part for part in re.split(r"[;,；，|\s]+", text(value)) if part}


def recognition_keys(value: object) -> set[str]:
    """Generate conservative A-only clause keys without changing B/C text."""
    raw = text(value)
    parts = [raw]
    parts.extend(re.findall(r"[（(]([^）)]*)[）)]", raw))
    without_parentheses = re.sub(r"[（(][^）)]*[）)]", "", raw)
    parts.append(without_parentheses)
    parts.extend(
        part
        for part in re.split(r"[,，;；、]|(?:伴|并|提示|考虑)", raw)
        if part
    )
    keys = {canonical(part) for part in parts if canonical(part)}
    return keys


def f1_from_counts(true_positive: int, expected: int, actual: int) -> float:
    if expected == 0 and actual == 0:
        return 1.0
    if true_positive == 0:
        return 0.0
    return 2 * true_positive / (expected + actual)


def source_integrity(workspace: Path, tests: Path) -> float:
    manifest = json.loads((tests / "source_manifest.json").read_text(encoding="utf-8"))
    checks = []
    for filename, expected in manifest.items():
        # The filled-in template is a convenience carrier, not source evidence.
        # Requiring an unchanged template made an otherwise valid submission
        # fail when the workbook was recreated with the same required sheets.
        if filename != INPUT_XLSX:
            continue
        path = workspace / filename
        checks.append(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == expected)
    return sum(checks) / len(checks) if checks else 1.0


def source_row_owners(workspace: Path) -> dict[str, str]:
    """Return evidence-row ownership so fabricated/cross-case citations are detectable."""
    path = workspace / INPUT_XLSX
    if not path.is_file():
        return {}
    workbook = load_workbook(path, read_only=True, data_only=True)
    if "检查明细" not in workbook.sheetnames:
        return {}
    sheet = workbook["检查明细"]
    headers = [text(cell.value) for cell in sheet[1]]
    if not {"明细行号", "病例编号"}.issubset(headers):
        return {}
    row_index = headers.index("明细行号")
    case_index = headers.index("病例编号")
    return {
        text(values[row_index]): text(values[case_index])
        for values in sheet.iter_rows(min_row=2, values_only=True)
        if text(values[row_index]) and text(values[case_index])
    }


def match_case(
    gold_rows: list[dict], actual_rows: list[dict],
    semantic_scores: dict[tuple[int, int], tuple[float, float, float]] | None = None
) -> tuple[list[tuple[int, int]], float, float, float]:
    """Maximum one-to-one match, weighted by evidence precision.

    A conclusion earns credit in proportion to how much of what it cites actually
    supports it: `|cited ∩ gold| / |cited|`. Citing the one row that carries the
    finding earns full credit; padding the citation with an entire case's rows
    earns a small fraction of it. Recall is deliberately not penalised — gold
    conclusions supported by several rows do not require the model to find all of
    them — so this measures whether the evidence trail is honest, not exhaustive.

    Returns the chosen pairs (unweighted, for closure diagnostics) plus the
    precision-weighted A / B / C hit mass.
    """
    candidates: list[list[tuple[int, float, float, float]]] = []
    semantic_scores = semantic_scores or {}
    for actual_index, actual in enumerate(actual_rows):
        edges = []
        cited = actual["evidence"]
        for gold_index, gold in enumerate(gold_rows):
            semantic = semantic_scores.get((actual_index, gold_index), (0.0, 0.0, 0.0))
            exact = actual["label_key"] in gold["fidelity_keys"]
            same_finding = exact or bool(actual["recognition_keys"] & gold["alias_keys"]) or semantic[0] > 0
            # Even Golden wording must be certified against the supplied source;
            # exact-string identity cannot legitimize an unsupported diagnosis.
            terminology = semantic[1]
            qualifier_fidelity = semantic[2]
            overlap = cited & gold["evidence_set"]
            if same_finding and overlap:
                precision = len(overlap) / len(cited)
                edges.append(
                    (
                        gold_index,
                        precision,
                        precision * terminology,
                        precision * qualifier_fidelity,
                    )
                )
        candidates.append(edges)

    # mask -> (weighted A, weighted B, weighted C, chosen pairs)
    states: dict[int, tuple[float, float, float, list[tuple[int, int]]]] = {0: (0.0, 0.0, 0.0, [])}
    for actual_index, edges in enumerate(candidates):
        updated = dict(states)  # An unmatched output is retained as a false positive.
        for mask, (weight_a, weight_b, weight_c, pairs) in states.items():
            for gold_index, gain_a, gain_b, gain_c in edges:
                bit = 1 << gold_index
                if mask & bit:
                    continue
                new_mask = mask | bit
                proposal = (
                    weight_a + gain_a,
                    weight_b + gain_b,
                    weight_c + gain_c,
                    pairs + [(actual_index, gold_index)],
                )
                current = updated.get(new_mask)
                if current is None or proposal[:3] > current[:3]:
                    updated[new_mask] = proposal
        states = updated
    _, (weight_a, weight_b, weight_c, pairs) = max(
        states.items(),
        key=lambda item: (item[1][0], item[1][1], item[1][2]),
    )
    return pairs, weight_a, weight_b, weight_c


def adjudicate_equivalents(workspace: Path, gold_by_case: dict, actual_by_case: dict) -> tuple[dict, dict]:
    """Measure finding identity, terminology and qualifier fidelity independently."""
    requests = {}
    for case_id, gold_rows in gold_by_case.items():
        for actual_index, actual in enumerate(actual_by_case.get(case_id, [])):
            for gold_index, gold in enumerate(gold_rows):
                overlap = actual["evidence"] & gold["evidence_set"]
                if overlap:
                    key = f"{case_id}_A{actual_index}_G{gold_index}"
                    requests[key] = (case_id, actual_index, gold_index, overlap)
    if not requests:
        return {}, {"used": False, "reason": "no unresolved evidence-linked wording"}

    cited_rows = {}
    book = None
    try:
        book = load_workbook(workspace / INPUT_XLSX, read_only=True, data_only=True)
        sheet = book["检查明细"]
        rows = sheet.iter_rows(values_only=True)
        headers = [text(value) for value in next(rows)]
        required = ("明细行号", "病例编号", "小项名称", "检查结果")
        if not set(required).issubset(headers):
            raise ValueError("source detail headers incomplete")
        for row in rows:
            record = dict(zip(headers, row))
            cited_rows[text(record.get("明细行号"))] = {
                key: text(record.get(key)) for key in required
            }
    except Exception as exc:
        # Candidate source deletion/corruption keeps its existing integrity and
        # evidence penalties; it must not become a semantic service failure.
        return {}, {"used": False, "reason": "original source unavailable for equivalence",
                    "source_error_type": type(exc).__name__}
    finally:
        if book is not None:
            book.close()
    criteria, candidate_lines, source = {}, [], {}
    for key, (case_id, actual_index, gold_index, overlap) in requests.items():
        actual = actual_by_case[case_id][actual_index]
        gold = gold_by_case[case_id][gold_index]
        source_rows = [cited_rows[row_id] for row_id in sorted(overlap)
                       if row_id in cited_rows and cited_rows[row_id]["病例编号"] == case_id]
        if not source_rows:
            continue
        for dimension in ('A','B','C'):
            candidate_lines.append(json.dumps({"id": key+':'+dimension, "conclusion": actual["label"],
                "evidence": sorted(actual["evidence"]), "explanation": actual["explanation"]}, ensure_ascii=False))
        source[key] = {"case_id": case_id, "reference_conclusion": gold["label"],
                       "source_rows": source_rows}
        common=(f"Assess ONLY conclusion {key} against its same-key original source rows. The source rows "
                "are authoritative; the reference wording is only a matching aid and cannot supply an "
                "unstated diagnosis. Quote the SAME item's conclusion span. ")
        criteria[key+':A'] = common + (
            "Return 1 when the candidate identifies the same core observed finding, even if terminology, "
            "degree or certainty differs; return 0 for a different organ/finding, negation or unsupported finding.")
        criteria[key+':B'] = common + (
            "Return 1 when the adopted conclusion is a medically standard, source-supported name for the "
            "finding. Do not award an inferred diagnosis such as sinus rhythm, cholesterol crystal or urine-salt "
            "crystal when the source only records measurements or imaging signs.")
        criteria[key+':C'] = common + (
            "Return 1 when the adopted conclusion name preserves every material semantic qualifier that "
            "belongs in a concise final-review conclusion: organ, laterality, degree, quantity, finding "
            "nature, certainty and status where applicable. Measurements, dimensions, echo descriptions, "
            "boundaries and other evidence details need not be repeated in the conclusion-name column. "
            "Do not add a qualifier or diagnosis absent from the source.")
    if not candidate_lines:
        return {}, {"used": False, "reason": "no readable same-case original evidence"}
    from semantic_judge import adjudicate
    # Keep a large alternative submission within the judge's output budget.
    # Every batch has the same local evidence and binary matching contract.
    verdicts = []
    for start in range(0, len(candidate_lines), 36):
        batch = candidate_lines[start:start + 36]
        keys = [json.loads(line)["id"] for line in batch]
        base_keys={key.rsplit(':',1)[0] for key in keys}
        verdicts.append(adjudicate("\n".join(batch), {key: source[key] for key in sorted(base_keys)},
                                  {key: criteria[key] for key in keys}))
    measured = defaultdict(dict)
    values = defaultdict(dict)
    for verdict in verdicts:
        for key, row in verdict["items"].items():
            base,dimension=key.rsplit(':',1)
            values[base][dimension]=float(row['fraction'])
    for base,dimensions in values.items():
        if set(dimensions)=={'A','B','C'}:
            case_id, actual_index, gold_index, _ = requests[base]
            measured[case_id][(actual_index,gold_index)]=(dimensions['A'],dimensions['B'],dimensions['C'])
    return measured, {"used": True, "batches": verdicts}


def write_result(path: Path | None, detail: dict) -> None:
    # detail 落盘是可选的：其余任务的验证器只把 JSON 打到 stdout，
    # 统一签名后审计与归档脚本可以一视同仁地调用。
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(detail, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(detail, ensure_ascii=False))


def main() -> int:
    workspace = Path(sys.argv[1])
    detail_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    tests = Path(__file__).resolve().parent
    truth = json.loads((tests / "ground_truth.json").read_text(encoding="utf-8"))
    xlsx_path = workspace / OUTPUT_XLSX
    if not xlsx_path.is_file():
        write_result(
            detail_path,
            {
                "reward": 0.0,
                "score": 0.0,
                "rewards": {"strict": 0.0, "lenient": 0.0},
                "reward_strict": 0.0,
                "reward_lenient": 0.0,
                "error": "no formal deliverables found",
            },
        )
        return 0

    gold_by_case: dict[str, list[dict]] = {}
    for case in truth["cases"]:
        rows = []
        for item in case["conclusions"]:
            rows.append(
                {
                    **item,
                    "label_key": canonical(item["label"]),
                    "alias_keys": {canonical(alias) for alias in item["recognition_aliases"]},
                    # Fidelity aliases must preserve anatomy, laterality, count,
                    # degree, nature, certainty, and state. When omitted, only
                    # the institutional label itself earns C credit.
                    "fidelity_keys": {
                        canonical(alias)
                        for alias in item.get("fidelity_aliases", [item["label"]])
                    },
                    "evidence_set": set(item["evidence"]),
                }
            )
        gold_by_case[case["case_id"]] = rows
    gold_status = {case["case_id"]: case["status"] for case in truth["cases"]}
    expected_cases = set(gold_by_case)
    actual_by_case: dict[str, list[dict]] = defaultdict(list)
    actual_summary: dict[str, dict] = {}
    errors: list[str] = []
    duplicate_rows = 0

    if xlsx_path.is_file():
        try:
            workbook = load_workbook(xlsx_path, read_only=True, data_only=True)
            if not {"总检结论", "病例汇总"}.issubset(workbook.sheetnames):
                errors.append("工作簿缺少要求的工作表")
            else:
                conclusion_sheet = workbook["总检结论"]
                headers = [text(cell.value) for cell in conclusion_sheet[1]]
                required = ["病例编号", "结论序号", "标准体检结论", "证据明细行号", "判断说明"]
                if not set(required).issubset(headers):
                    errors.append("总检结论字段不完整")
                else:
                    indexes = {name: headers.index(name) for name in required}
                    seen_rows: set[tuple[str, str, tuple[str, ...]]] = set()
                    for row_number, values in enumerate(
                        conclusion_sheet.iter_rows(min_row=2, values_only=True), start=2
                    ):
                        case_id = text(values[indexes["病例编号"]])
                        label = text(values[indexes["标准体检结论"]])
                        if not case_id and not label:
                            continue
                        label_key = canonical(label)
                        if not case_id or not label_key:
                            errors.append(f"第{row_number}行存在空病例编号或空结论")
                            continue
                        evidence = split_ids(values[indexes["证据明细行号"]])
                        row_signature = (case_id, label_key, tuple(sorted(evidence)))
                        duplicate_rows += int(row_signature in seen_rows)
                        seen_rows.add(row_signature)
                        actual_by_case[case_id].append(
                            {
                                "row_number": row_number,
                                "label": label,
                                "label_key": label_key,
                                "recognition_keys": recognition_keys(label),
                                "evidence": evidence,
                                "explanation": text(values[indexes["判断说明"]]),
                            }
                        )
                summary_sheet = workbook["病例汇总"]
                summary_headers = [text(cell.value) for cell in summary_sheet[1]]
                summary_required = ["病例编号", "结论项数", "总检状态", "复核备注"]
                if not set(summary_required).issubset(summary_headers):
                    errors.append("病例汇总字段不完整")
                else:
                    indexes = {name: summary_headers.index(name) for name in summary_required}
                    for values in summary_sheet.iter_rows(min_row=2, values_only=True):
                        case_id = text(values[indexes["病例编号"]])
                        if not case_id:
                            continue
                        if case_id in actual_summary:
                            errors.append(f"病例汇总重复: {case_id}")
                            continue
                        actual_summary[case_id] = {
                            "count": text(values[indexes["结论项数"]]),
                            "status": text(values[indexes["总检状态"]]),
                            "note": text(values[indexes["复核备注"]]),
                        }
        except Exception as exc:
            errors.append(f"工作簿无法读取: {type(exc).__name__}")
    else:
        errors.append("缺少体检总检结论.xlsx")

    semantic_scores, semantic_detail = adjudicate_equivalents(workspace, gold_by_case, actual_by_case)
    a_macro_scores: list[float] = []
    b_macro_scores: list[float] = []
    c_macro_scores: list[float] = []
    total_gold = 0
    total_actual = sum(len(rows) for rows in actual_by_case.values())
    total_a_matches = 0.0
    total_b_matches = 0.0
    total_c_matches = 0.0
    total_pairs = 0
    closed_cases = 0
    closure_failures: list[dict] = []
    for case_id in sorted(expected_cases):
        gold_rows = gold_by_case[case_id]
        actual_rows = actual_by_case.get(case_id, [])
        pairs, weighted_a, exact_matches, faithful_matches = match_case(
            gold_rows, actual_rows, semantic_scores.get(case_id, {}))
        a_matches = len(pairs)  # unweighted, for closure diagnostics only
        total_gold += len(gold_rows)
        total_pairs += a_matches
        total_a_matches += weighted_a
        total_b_matches += exact_matches
        total_c_matches += faithful_matches
        # A/B/C macro scores cover cases with findings; blank-gold cases are scored
        # separately and any false positives there still enter the micro denominator.
        if gold_rows:
            a_macro_scores.append(f1_from_counts(weighted_a, len(gold_rows), len(actual_rows)))
            b_macro_scores.append(f1_from_counts(exact_matches, len(gold_rows), len(actual_rows)))
            c_macro_scores.append(
                f1_from_counts(faithful_matches, len(gold_rows), len(actual_rows))
            )

        stated_status = actual_summary.get(case_id, {}).get("status", "")
        derived_status = "有异常结论" if actual_rows else "无异常结论"
        missing_a = len(gold_rows) - a_matches
        extra_a = len(actual_rows) - a_matches
        status_wrong = stated_status != gold_status[case_id]
        status_inconsistent = stated_status != derived_status
        case_closed = not (
            missing_a or extra_a or status_wrong or status_inconsistent
        )
        closed_cases += int(case_closed)
        if not case_closed:
            closure_failures.append(
                {
                    "case_id": case_id,
                    "A_false_negative": missing_a,
                    "A_false_positive": extra_a,
                    "status_wrong": status_wrong,
                    "status_inconsistent": status_inconsistent,
                }
            )

    a_macro = sum(a_macro_scores) / len(a_macro_scores)
    b_macro = sum(b_macro_scores) / len(b_macro_scores)
    c_macro = sum(c_macro_scores) / len(c_macro_scores)
    a_micro = f1_from_counts(total_a_matches, total_gold, total_actual)
    b_micro = f1_from_counts(total_b_matches, total_gold, total_actual)
    c_micro = f1_from_counts(total_c_matches, total_gold, total_actual)
    # Preserve the former 5:2 macro/micro balance inside each semantic dimension.
    identification_a = (5 * a_macro + 2 * a_micro) / 7
    terminology_b = (5 * b_macro + 2 * b_micro) / 7
    fidelity_c = (5 * c_macro + 2 * c_micro) / 7

    # Case-level exact closure is reported as a diagnostic only. It is not part of
    # the reward: an all-or-nothing per-case gate over ~9 conclusions gives every
    # real attempt zero while handing a case's worth of credit to an output that
    # simply declares every case normal. Over-generation is instead priced through
    # the F1 denominators and the evidence-precision weighting inside A/B/C.
    case_closure_score = closed_cases / len(expected_cases)
    case_closure_points = 100.0 * case_closure_score

    summary_coverage = len(expected_cases & set(actual_summary)) / len(expected_cases)
    status_hits = sum(
        actual_summary.get(case_id, {}).get("status") == gold_status[case_id]
        for case_id in expected_cases
    ) / len(expected_cases)
    normal_cases = [case_id for case_id in expected_cases if not gold_by_case[case_id]]
    normal_score = sum(
        not actual_by_case.get(case_id)
        and actual_summary.get(case_id, {}).get("status") == "无异常结论"
        for case_id in normal_cases
    ) / len(normal_cases)
    case_status_score = 0.60 * status_hits + 0.40 * normal_score

    stated_count_hits = 0
    status_consistency_hits = 0
    for case_id in expected_cases:
        actual_count = len(actual_by_case.get(case_id, []))
        try:
            stated_count = int(float(actual_summary.get(case_id, {}).get("count", "nan")))
        except (TypeError, ValueError):
            stated_count = -1
        stated_count_hits += stated_count == actual_count
        expected_output_status = "有异常结论" if actual_count else "无异常结论"
        status_consistency_hits += (
            actual_summary.get(case_id, {}).get("status") == expected_output_status
        )
    stated_count_score = stated_count_hits / len(expected_cases)
    status_consistency_score = status_consistency_hits / len(expected_cases)
    cross_output_score = (
        0.40 * summary_coverage + 0.30 * stated_count_score + 0.30 * status_consistency_score
    )

    try:
        row_owners = source_row_owners(workspace)
    except Exception as exc:
        row_owners = {}
        errors.append(f"源明细无法读取: {type(exc).__name__}")
    evidence_hygiene: list[bool] = []
    explanation_presence: list[bool] = []
    for case_id, rows in actual_by_case.items():
        for row in rows:
            evidence_hygiene.append(
                bool(row["evidence"])
                and all(row_owners.get(row_id) == case_id for row_id in row["evidence"])
            )
            explanation_presence.append(len(row["explanation"]) >= 4)
    evidence_hygiene_score = (
        sum(evidence_hygiene) / len(evidence_hygiene) if evidence_hygiene else 0.0
    )
    explanation_score = (
        sum(explanation_presence) / len(explanation_presence) if explanation_presence else 0.0
    )
    auditability_score = 0.70 * evidence_hygiene_score + 0.30 * explanation_score

    structure_score = max(
        0.0,
        0.6 * summary_coverage
        + 0.2 * float(not errors)
        + 0.2 * float(duplicate_rows == 0),
    )
    integrity = source_integrity(workspace, tests)

    components = {
        "identification_A_macro": a_macro,
        "identification_A_micro": a_micro,
        "identification_A": identification_a,
        "terminology_B_macro": b_macro,
        "terminology_B_micro": b_micro,
        "terminology_B": terminology_b,
        "fidelity_C_macro": c_macro,
        "fidelity_C_micro": c_micro,
        "fidelity_C": fidelity_c,
        "case_closure_D": case_closure_score,
        "case_closure_D_points": case_closure_points,
        "case_status_and_normal": case_status_score,
        "case_status_and_normal_legacy_diagnostic": case_status_score,
        "cross_output_consistency": cross_output_score,
        "auditability": auditability_score,
        "evidence_hygiene": evidence_hygiene_score,
        "explanation_presence": explanation_score,
        "structure": structure_score,
        "source_integrity": integrity,
    }
    score = 0.45 * identification_a + 0.35 * terminology_b + 0.20 * fidelity_c
    score *= integrity
    score = max(0.0, min(1.0, score))

    # ---- Second, co-equal standard: a binary completion check. ----
    # The strict score above grades how close the conclusions come to the
    # doctor-reviewed gold. Lenient asks whether the deliverable is a whole, honest
    # attempt that engaged with the task instead of taking a degenerate shortcut,
    # and whether its conclusions carry the findings faithfully at or above a stated
    # floor. That floor is measured against gold, so lenient is not independent of
    # strict; it is still exactly 1.0 or 0.0 and never graded on exact-match count.
    n_abnormal = sum(1 for case_id in expected_cases if gold_by_case[case_id])
    engaged_abnormal_cases = sum(
        1
        for case_id in expected_cases
        if gold_by_case[case_id] and actual_by_case.get(case_id)
    )
    contract_whole = (not errors) and summary_coverage >= 1.0 and duplicate_rows == 0
    method_coherent = evidence_hygiene_score == 1.0
    # Restraint on the truly-normal cases is the exam's hard part: fabricating a
    # finding everywhere fails here even if it "covers" more rows. A normal case
    # counts as restrained when it carries at most RESTRAINT_FP_TOLERANCE spurious
    # findings; the summary-status wording is graded elsewhere, not gated here
    # (exact-string status is too brittle for a binary completion check).
    restraint_score = (
        sum(
            len(actual_by_case.get(case_id, [])) <= RESTRAINT_FP_TOLERANCE
            for case_id in normal_cases
        )
        / len(normal_cases)
        if normal_cases
        else 1.0
    )
    honored_restraint = restraint_score == 1.0
    # Engagement guards the opposite shortcut — declaring every case normal.
    engaged_abnormal = (
        engaged_abnormal_cases == n_abnormal if n_abnormal else True
    )
    lenient_flags = {
        "contract_whole": bool(contract_whole),
        "method_coherent": bool(method_coherent),
        "honored_restraint": bool(honored_restraint),
        "engaged_abnormal": bool(engaged_abnormal),
        "case_status_consistent": bool(case_status_score == 1.0),
    }
    lenient = 1.0 if all(lenient_flags.values()) else 0.0

    detail = {
        "semantic_equivalence": semantic_detail,
        "reward": round(score, 6),
        "score": round(score, 6),
        "rewards": {"strict": round(score, 6), "lenient": lenient},
        "reward_formulas": {
            "strict": "strict = weighted rubric components, continuous in [0, 1]",
            "lenient": (
                "lenient = 1 if contract_whole and method_coherent and "
                "honored_restraint and engaged_abnormal and case_status_consistent, else 0"
            ),
        },
        "reward_strict": round(score, 6),
        "reward_lenient": lenient,
        "lenient_detail": {
            **lenient_flags,
            "n_abnormal": n_abnormal,
            "engaged_abnormal_cases": engaged_abnormal_cases,
            "restraint_score": round(restraint_score, 6),
            "restraint_fp_tolerance": RESTRAINT_FP_TOLERANCE,
            "normal_score": round(normal_score, 6),
            "evidence_hygiene": round(evidence_hygiene_score, 6),
            "explanation_presence": round(explanation_score, 6),
            "total_actual": total_actual,
            "total_gold": total_gold,
            "dump_factor": DUMP_FACTOR,
        },
        "components": {key: round(value, 6) for key, value in components.items()},
        "expected_cases": len(expected_cases),
        "expected_conclusions": total_gold,
        "actual_conclusions": total_actual,
        "A_matches_weighted": round(total_a_matches, 4),
        "A_matches_unweighted": total_pairs,
        "B_exact_matches": round(total_b_matches, 4),
        "C_faithful_matches": round(total_c_matches, 4),
        "mean_evidence_precision": (
            round(total_a_matches / total_pairs, 4) if total_pairs else 0.0
        ),
        "closed_cases": closed_cases,
        "unclosed_cases": len(expected_cases) - closed_cases,
        "closure_failures": closure_failures,
        "weights": {
            "identification_A": 0.45,
            "terminology_B": 0.35,
            "fidelity_C": 0.20,
        },
        "duplicate_rows": duplicate_rows,
        "unknown_cases": sorted(set(actual_by_case) - expected_cases),
        "errors": errors,
    }
    write_result(detail_path, detail)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
