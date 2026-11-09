#!/usr/bin/env python3
"""Condition-blind, source-bound final workbook scorer with required semantic review."""
from __future__ import annotations

import json
import hashlib
import os
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import workbook
import semantic_judge
import reference_calibration
import temporal_rules
import source_certificate

GROUND = json.loads((HERE / "ground_truth.json").read_text(encoding="utf-8"))
SOURCE = json.loads((HERE / "source_facts.json").read_text(encoding="utf-8"))
EXPECTED = {r["sample_id"]: r for r in GROUND["samples"]}
VALID_EVIDENCE = set(GROUND["valid_evidence_ids"])
VALID_ANCHORS = {v for v in VALID_EVIDENCE if v.startswith("E_")}
VALID_EVENTS = {v for v in VALID_EVIDENCE if v.startswith("EVT_")}
WEIGHTS = GROUND["weights"]
PACKAGED_REPLAY = HERE / "golden_replay"


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _packaged_evidence_path(name):
    """Resolve sealed evidence in both source and flattened `/tests` layouts."""
    relative = Path(name)
    if relative == Path("task/instruction.md"):
        candidates = [HERE.parent / "instruction.md", Path("/instruction.md")]
    elif relative.parts[:2] == ("task", "tests"):
        candidates = [HERE / Path(*relative.parts[2:])]
    else:
        candidates = []
    if len(HERE.parents) > 1:
        candidates.append(HERE.parents[1] / relative)
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise RuntimeError("packaged Golden evidence file unavailable: " + name)
    return path


def activate_packaged_golden_replay(path):
    """Expose the private parsed cache only for the exact sealed Golden group."""
    manifest_path = PACKAGED_REPLAY / "manifest.json"
    if not manifest_path.is_file() or not Path(path).is_file():
        return False
    manifest = json.loads(manifest_path.read_text())
    artifact_sha = _sha(path)
    group = manifest.get("groups", {}).get(artifact_sha)
    if group is None:
        return False
    evidence_files = group["evidence_files"]
    actual_evidence = {name: _sha(_packaged_evidence_path(name)) for name in evidence_files}
    if actual_evidence != evidence_files:
        raise RuntimeError("packaged Golden evidence binding changed")
    evidence_sha = hashlib.sha256(json.dumps(actual_evidence, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if evidence_sha != group["evidence_sha256"]:
        raise RuntimeError("packaged Golden evidence-set hash changed")
    cache_dir = (PACKAGED_REPLAY / group["cache_dir"]).resolve()
    if not cache_dir.is_relative_to(PACKAGED_REPLAY.resolve()):
        raise RuntimeError("packaged Golden cache path escapes trusted root")
    for name, expected in group["files_sha256"].items():
        if _sha(PACKAGED_REPLAY / name) != expected:
            raise RuntimeError("packaged Golden replay file changed: " + name)
    os.environ["LLM_JUDGE_CACHE_DIR"] = str(cache_dir)
    os.environ["LLM_JUDGE_REPLAY_ONLY"] = "1"
    return True
REGIME_SYNONYMS = {
    "SIGNAL": ("signal", "趋势", "信号", "确认", "confirmed", "信号确认"),
    "NOISE": ("noise", "噪声", "扰动", "短期", "shock", "噪声扰动"),
    "MIXED": ("mixed", "交织", "混合", "分歧", "矛盾", "证据混合"),
    "REVIEW": ("review", "复核", "待审", "存疑", "观察", "无法判定", "复核观察"),
}
ACTION_SYNONYMS = {
    "ADD_RISK": ("add_risk", "addrisk", "加仓", "增配", "提高风险", "riskon", "加风险"),
    "REDUCE_RISK": ("reduce_risk", "reducerisk", "减仓", "降风险", "降低风险", "riskoff"),
    "HOLD": ("hold", "维持", "持有", "观望", "不变"),
    "ROTATE_STYLE": ("rotate_style", "rotatestyle", "风格切换", "风格轮动", "切风格"),
    "ROTATE_INDUSTRY": ("rotate_industry", "rotateindustry", "行业轮动", "行业切换", "结构轮动"),
    "REVIEW_ONLY": ("review_only", "reviewonly", "仅复核", "复核", "只观察", "不交易"),
}
TRUE_WORDS = ("true", "yes", "y", "1", "是", "有", "需", "需要", "矛盾", "复核")
FALSE_WORDS = ("false", "no", "n", "0", "否", "无", "不需", "没有")


def _clean(value):
    return "" if value is None else str(value).strip()


def norm_sample_id(value):
    text = _clean(value).upper().replace(" ", "")
    match = re.fullmatch(r"S?0*(\d{1,3})", text)
    return f"S{int(match.group(1)):03d}" if match else text


def resolve_enum(value, synonyms):
    normalized = re.sub(r"[\s_-]+", "", _clean(value)).casefold()
    for label, words in synonyms.items():
        if any(normalized == re.sub(r"[\s_-]+", "", word).casefold() for word in (label, *words)):
            return label
    return None


def resolve_bool(value):
    text = _clean(value).lower()
    return "TRUE" if text in TRUE_WORDS else "FALSE" if text in FALSE_WORDS else None


def parse_evidence(value):
    # Preserve every supplied token, including unknown IDs; never filter mistakes.
    return list(dict.fromkeys(p for p in re.split(r"[|,，;；、\s]+", _clean(value).upper()) if p))


def rows_by_id(path):
    parsed = workbook.read_table(path, "regime_map")
    out, dupes, unknown = {}, [], []
    for row in parsed:
        sid = norm_sample_id(row.get("sample_id"))
        if sid not in EXPECTED:
            unknown.append(sid)
            continue
        if sid in out:
            dupes.append(sid)
        out[sid] = {"regime_label": resolve_enum(row.get("regime_label"), REGIME_SYNONYMS) or _clean(row.get("regime_label")) or None,
                    "action": resolve_enum(row.get("action"), ACTION_SYNONYMS) or _clean(row.get("action")) or None,
                    "evidence_ids": parse_evidence(row.get("evidence_ids")),
                    "contradiction_flag": resolve_bool(row.get("contradiction_flag")),
                    "review_flag": resolve_bool(row.get("review_flag")),
                    "rationale": _clean(row.get("rationale"))}
    return parsed, out, dupes, unknown


def contract_issues(got):
    issues = {}
    for sid, row in got.items():
        found = []
        if not row["regime_label"] or not row["action"]:
            found.append("invalid_or_missing_enum")
        for flag in ("review_flag", "contradiction_flag"):
            if row[flag] not in {"TRUE", "FALSE"}:
                found.append("invalid_or_missing_" + flag)
        if not row["rationale"]:
            found.append("missing_rationale")
        cited = set(row["evidence_ids"])
        if not cited & VALID_ANCHORS:
            found.append("missing_evidence_anchor")
        if cited - VALID_EVIDENCE:
            found.append("unknown_evidence_ids:" + "|".join(sorted(cited - VALID_EVIDENCE)))
        if cited & VALID_EVENTS != set(SOURCE["events_by_sample"][sid]):
            found.append("sample_event_mismatch")
        if found:
            issues[sid] = found
    return issues


def internal_consistency(got):
    issues = Counter()
    bad = 0
    for sid in EXPECTED:
        row = got.get(sid, {})
        failed = sid not in got
        if (row.get("regime_label") == "REVIEW") != (row.get("review_flag") == "TRUE"):
            issues["review_label_flag_mismatch"] += 1
            failed = True
        if (row.get("regime_label") == "REVIEW") != (row.get("action") == "REVIEW_ONLY"):
            issues["review_label_action_mismatch"] += 1
            failed = True
        bad += failed
    return 1 - bad / len(EXPECTED), dict(issues)


def impossible_action_pairs(got):
    return semantic_judge.canonical_action_conflicts(got)


def build_context(got):
    context = {key: value for key, value in SOURCE.items() if key != "reference_states"}
    context["nonbinding_reference_example"] = {"cut_lines": reference_calibration.oracle_thresholds(SOURCE["source_rows"]),
                                               "states": SOURCE["reference_states"], "outputs": GROUND["samples"]}
    context["candidate_panel"] = got
    extraction = semantic_judge.extract_calibration(got) if got else None
    if extraction and extraction["cut_lines"] is not None:
        cuts = extraction["cut_lines"]
        within_source = True
        for key, field in semantic_judge.CUT_FIELDS.items():
            absolute = field.startswith("absolute ")
            values = [float(row[field.removeprefix("absolute ")]) for row in SOURCE["source_rows"]]
            values = [abs(value) for value in values] if absolute else values
            within_source &= min(values) <= cuts[key] <= max(values)
        ordered = all(cuts[low] < cuts[high] for low, high in (("trend_ret_lo", "trend_ret_hi"), ("recent_lo", "recent_hi"),
                      ("breadth_lo", "breadth_hi"), ("earn_lo", "earn_hi"), ("valq_lo", "valq_hi"), ("erp_lo", "erp_hi"), ("liq_lo", "liq_hi")))
        if within_source and ordered:
            context["verified_candidate_calibration"] = {"cut_lines": cuts, "rationale_ids": extraction["rationale_ids"],
                "states": reference_calibration.classify_reference(SOURCE["source_rows"], SOURCE["events"], thresholds=cuts)}
            # A verified alternative needs its own witness, not a second competing state table.
            context.pop("nonbinding_reference_example")
        else:
            context["candidate_calibration_warning"] = "Disclosed cuts fall outside source ranges or invert low/high boundaries; no verified mathematical witness is supplied."
    return context, extraction


def grade(path):
    activate_packaged_golden_replay(path)
    parsed, got, dupes, unknown = rows_by_id(path)
    issues = contract_issues(got)
    context, extraction = build_context(got)
    contract_whole = bool(parsed) and set(got) == set(EXPECTED) and not dupes and not unknown and not issues
    certificate = {"status": "unsupported", "reason": "incomplete_contract", "api_called": False}
    if contract_whole:
        source_folder = HERE.parent / "environment" / "workspace"
        certificate = source_certificate.certify(got, SOURCE, extraction, row_count=len(parsed),
            duplicate_ids=dupes, unknown_ids=unknown,
            workspace=source_folder if source_folder.is_dir() else Path("/workspace"))
    action_conflicts = impossible_action_pairs(got)
    if action_conflicts:
        context["deterministic_action_conflicts"] = {
            sid: {"regime_label": got[sid]["regime_label"], "action": got[sid]["action"],
                  "violated_rule": reason,
                  "scope": "Zero joint-label/action credit; evidence and flags remain independent criteria."}
            for sid, reason in action_conflicts.items()}
    calibration = context.get("verified_candidate_calibration")
    source_witness = None
    if calibration:
        source_witness = {
            "authority": "mathematical_only",
            "calibration": {"cut_lines": calibration["cut_lines"], "rationale_ids": calibration["rationale_ids"]},
            "states": [{"sample_id": row["sample_id"],
                        "trend_dir": row["trend_dir"], "odds_dir": row["odds_dir"],
                        "fund_dir": row["fund_dir"], "event_intensity": row["event_load"] > 0}
                       for row in calibration["states"]],
        }
    trajectory = temporal_rules.evaluate_temporal(source_witness["states"]) if source_witness else []
    if source_witness:
        context["shared_source_trajectory"] = {
            "authority": source_witness["authority"],
            "calibration": source_witness["calibration"],
            "samples": [{**state, "possible_raw_labels": step["possible_raw_labels"],
                         "possible_final_labels": step["possible_final_labels"]}
                        for state, step in zip(source_witness["states"], trajectory)],
        }
    # An empty workbook is artifact failure; API failure propagates as infrastructure failure.
    if certificate["status"] == "supported":
        fields = {"joint_label_action": ["regime_label", "action", "rationale"],
                  "transition_support": ["regime_label", "rationale"],
                  "evidence_alignment": ["evidence_ids"],
                  "flag_joint": ["contradiction_flag", "review_flag"]}
        items = {}
        previous = None
        for state in certificate["states"]:
            sid = state["sample_id"]
            items[sid] = {"sample_id": sid, **{
                criterion: {"score": 1.0, "meets_brief": True, "candidate_fields": names,
                    "source_samples": [sid] if previous is None else [previous, sid],
                    "reason": "All business fields match one source-recomputed global model; independent semantic admission verifies method, actual source claims and any unknown enum equivalences. See source_certificate proof."}
                for criterion, names in fields.items()}}
            previous = sid
        adjudication = {"items": items, "batches": [], "origin": "source_certificate",
                        "model": certificate["semantic_admission"]["model"]}
    else:
        adjudication = semantic_judge.adjudicate(got, context) if got else {"items": {}, "batches": []}
    adjudication["calibration_extraction"] = extraction
    values = {sid: {key: float(row[key]["score"]) for key in WEIGHTS}
              for sid, row in adjudication["items"].items()}
    mathematical_checks = {}
    if calibration:
        for expected in calibration["states"]:
            sid = expected["sample_id"]
            if sid not in values:
                continue
            row = got[sid]
            evidence_exact = set(row["evidence_ids"]) == set(expected["evidence_ids"])
            old_evidence, old_flags = values[sid]["evidence_alignment"], values[sid]["flag_joint"]
            values[sid]["evidence_alignment"] = 1.0 if evidence_exact else min(old_evidence, 0.5)
            if row["regime_label"] in REGIME_SYNONYMS:
                review = "TRUE" if row["regime_label"] == "REVIEW" else "FALSE"
                values[sid]["flag_joint"] = (
                    int(row["contradiction_flag"] == expected["contradiction_flag"])
                    + int(row["review_flag"] == review)) / 2
            mathematical_checks[sid] = {
                "evidence_exact": evidence_exact,
                "expected_evidence_ids": expected["evidence_ids"],
                "semantic_evidence_credit": old_evidence,
                "settled_evidence_credit": values[sid]["evidence_alignment"],
                "semantic_flag_credit": old_flags,
                "settled_flag_credit": values[sid]["flag_joint"],
                "source_contradiction_flag": expected["contradiction_flag"],
            }
    temporal_resolution = {}
    for step in trajectory:
        sid = step["sample_id"]
        if sid not in values or got[sid]["regime_label"] not in REGIME_SYNONYMS:
            continue
        possible = step["possible_final_labels"]
        old = values[sid]["transition_support"]
        # Mathematical incompatibility can remove credit, never endorse a method.
        if got[sid]["regime_label"] not in possible:
            values[sid]["transition_support"] = 0.0
        temporal_resolution[sid] = {"semantic_credit": old,
                                    "settled_credit": values[sid]["transition_support"],
                                    "possible_final_labels": possible,
                                    "source_authority": source_witness["authority"],
                                    "mathematically_excluded": got[sid]["regime_label"] not in possible}
    for sid in action_conflicts:
        values[sid]["joint_label_action"] = 0.0
    for sid, problems in issues.items():
        if any(p.startswith(("unknown_evidence_ids", "sample_event_mismatch", "missing_evidence_anchor")) for p in problems):
            values[sid]["evidence_alignment"] = 0.0
        if "invalid_or_missing_enum" in problems:
            values[sid]["joint_label_action"] = values[sid]["transition_support"] = 0.0
        if any(p.startswith("invalid_or_missing_") and p != "invalid_or_missing_enum" for p in problems):
            values[sid]["flag_joint"] = 0.0
    dim = {key: sum(row[key] for row in values.values()) / len(EXPECTED) for key in WEIGHTS}
    weighted_rows = {sid: sum(WEIGHTS[key] * row[key] for key in WEIGHTS) for sid, row in values.items()}
    # Auxiliary fields cannot compensate for an unsupported final decision or temporal rule.
    row_credit = {sid: min(weighted_rows[sid], row["joint_label_action"], row["transition_support"])
                  for sid, row in values.items()}
    strict = round(sum(row_credit.values()) / len(EXPECTED), 6)
    completion = semantic_judge.completion(got, SOURCE, (HERE.parent / "instruction.md").read_text(encoding="utf-8"), context) if contract_whole else {"checks": {}, "origin": "incomplete_contract"}
    semantic_complete = bool(completion["checks"]) and all(value["passed"] for value in completion["checks"].values())
    lenient = float(contract_whole and semantic_complete)
    cons, cons_detail = internal_consistency(got)
    return {"reward": strict, "rewards": {"strict": strict, "lenient": lenient},
            "score_type": "ashare_source_bound_semantic_v5",
            "reward_formula": "mean(min(weighted_row_quality, joint_label_action, transition_support))",
            "reward_formulas": {"strict": "mean of weighted row credit bounded by its final-decision and professional temporal-rule credit",
                                "lenient": "1 iff the explicit output contract and independent whole-map completion checks pass; otherwise 0"},
            "dimension_scores": {key: round(value, 6) for key, value in dim.items()},
            "lenient_detail": {"contract_whole": contract_whole, "semantic_complete": semantic_complete,
                               "material_action_coherence": bool(completion["checks"].get("basic_decision_coherence", {}).get("passed")) if action_conflicts else True,
                               "reference_label_overlap_required": False, "completion_judgment": completion},
            "gates": {"workbook_readable": bool(parsed), "sample_coverage": len(got) / len(EXPECTED),
                      "unknown_sample_ids": unknown, "duplicate_sample_ids": dupes, "contract_issues": issues},
            "diagnostic_scores": {"internal_consistency_rate": cons,
                                  "unbounded_weighted_quality": round(sum(weighted_rows.values()) / len(EXPECTED), 6)},
            "checkpoint_scores": {"internal_consistency": cons_detail, "samples": values,
                                  "weighted_rows": weighted_rows, "row_credit": row_credit,
                                  "mathematical_checks": mathematical_checks,
                                  "temporal_resolution": temporal_resolution,
                                  "impossible_action_pairs": action_conflicts},
            "source_state_witness": source_witness, "source_trajectory": trajectory,
            "source_certificate": certificate,
            "semantic_review": adjudication}


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/workspace/regime_map.xlsx")
    print(json.dumps(grade(path), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
