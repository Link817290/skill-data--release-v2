#!/usr/bin/env python3
"""Score semantic and facsimile fidelity of a diplomatic suzipu MEI."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from scoreio import parse_mei
from position_checks import evaluate_positions, metadata_grounding, source_geometry, fine_features, compact_features, owner
from content_checks import content_features


WEIGHTS = {"header_context": .04, "reading_order_text": .09,
           "pitch_classification": .28, "secondary_classification": .21,
           "boundary_decisions": .11, "facsimile_geometry": .03,
           "source_images": .01, "referential_closure": .01,
           "atemporal_fidelity": .01, "source_pairing_integrity": .03,
           "physical_source_order": .01, "joint_position_fidelity": .17}
STRICT_FORMULA = "sum(weight * independent_source_behavior_completion); additive-only; no caps or deductions"
LENIENT_VERSION = "mei-lenient-v3-binary-source-minimum"
LENIENT_THRESHOLDS = {
    "metadata_content": .90, "sung_text_fidelity": .90,
    "primary_source_fidelity": .80, "real_secondary_classes": .65,
    "secondary_absence": .90, "source_status_fidelity": .95,
    "physical_boundaries": .90, "source_region_quality": .80,
    "source_pairing_integrity": .90, "physical_reading_order": .90,
    "document_contract": 1.0,
}
LENIENT_FORMULA = "1 if all independent source completions meet LENIENT_THRESHOLDS else 0; per-run binary, no joint-position gate"


def lenient_completion(content: dict, expected: list[dict], actual: list[dict], records: list[dict]) -> dict:
    values = {key: content[key] for key in LENIENT_THRESHOLDS if key in content}
    correct = set()
    for event, record in zip(actual, records):
        index = record['intended_source_position']
        if index is not None and event.get('excluded') == expected[index].get('excluded'):
            correct.add(index)
    values['source_status_fidelity'] = len(correct) / max(len(expected), len(actual), 1)
    return values


def clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def harmonic(correct: int, expected: int, actual: int) -> float:
    if expected == actual == 0:
        return 1.0
    if correct <= 0:
        return 0.0
    precision = correct / max(actual, 1)
    recall = correct / max(expected, 1)
    return 2 * precision * recall / (precision + recall)


def count_similarity(expected: int, actual: int) -> float:
    return 1.0 if expected == actual == 0 else min(expected, actual) / max(expected, actual, 1)


def align_events(expected: list[dict], actual: list[dict]) -> list[tuple[int, int]]:
    rows, cols = len(expected), len(actual)
    scores = [[0.0] * (cols + 1) for _ in range(rows + 1)]
    moves = [[""] * (cols + 1) for _ in range(rows + 1)]
    for i in range(1, rows + 1):
        scores[i][0] = scores[i - 1][0] - 1.2
        moves[i][0] = "up"
    for j in range(1, cols + 1):
        scores[0][j] = scores[0][j - 1] - 1.2
        moves[0][j] = "left"
    for i in range(1, rows + 1):
        for j in range(1, cols + 1):
            exp, got = expected[i - 1], actual[j - 1]
            match = -1.5
            match += 3.0 if exp.get("text") == got.get("text") else 0.0
            match += 2.0 if exp.get("pitch") == got.get("pitch") else 0.0
            match += 0.5 if exp.get("secondary") == got.get("secondary") else 0.0
            options = [(scores[i - 1][j - 1] + match, "diag"), (scores[i - 1][j] - 1.2, "up"), (scores[i][j - 1] - 1.2, "left")]
            scores[i][j], moves[i][j] = max(options, key=lambda item: item[0])
    pairs = []
    i, j = rows, cols
    while i or j:
        move = moves[i][j]
        if move == "diag":
            pairs.append((i - 1, j - 1))
            i -= 1
            j -= 1
        elif move == "up":
            i -= 1
        else:
            j -= 1
    return list(reversed(pairs))


def field_f1(expected: list[dict], actual: list[dict], pairs: list[tuple[int, int]], field: str) -> float:
    correct = sum(expected[i].get(field) == actual[j].get(field) for i, j in pairs)
    return harmonic(correct, len(expected), len(actual))


def categorical_macro_f1(expected: list[dict], actual: list[dict], pairs: list[tuple[int, int]], field: str) -> float:
    categories = {item.get(field) for item in expected} | {item.get(field) for item in actual}
    if not categories:
        return 1.0
    scores = []
    for category in categories:
        expected_count = sum(item.get(field) == category for item in expected)
        actual_count = sum(item.get(field) == category for item in actual)
        correct = sum(expected[i].get(field) == category and actual[j].get(field) == category for i, j in pairs)
        scores.append(harmonic(correct, expected_count, actual_count))
    return sum(scores) / len(scores)


def positive_f1(expected: list[dict], actual: list[dict], pairs: list[tuple[int, int]], field: str) -> float:
    expected_count = sum(bool(item.get(field)) for item in expected)
    actual_count = sum(bool(item.get(field)) for item in actual)
    correct = sum(bool(expected[i].get(field)) and bool(actual[j].get(field)) for i, j in pairs)
    return harmonic(correct, expected_count, actual_count)


def metadata_f1(expected: list[dict], actual: list[dict]) -> float:
    exp = "".join(x.get("text", "") for x in expected if x.get("type") == "preface")
    got = "".join(x.get("text", "") for x in actual if x.get("type") == "preface")
    return text_f1(exp, got)


def text_f1(expected: str, actual: str) -> float:
    prev = [0] * (len(actual) + 1)
    for character in expected:
        current = [0]
        for j, got in enumerate(actual):
            current.append(prev[j] + 1 if character == got else max(prev[j + 1], current[-1]))
        prev = current
    return harmonic(prev[-1], len(expected), len(actual))


def iou(left: list[int] | None, right: list[int] | None) -> float:
    if left is None or right is None:
        return 0.0
    ix1, iy1 = max(left[0], right[0]), max(left[1], right[1])
    ix2, iy2 = min(left[2], right[2]), min(left[3], right[3])
    intersection = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    left_area = max(0, left[2] - left[0]) * max(0, left[3] - left[1])
    right_area = max(0, right[2] - right[0]) * max(0, right[3] - right[1])
    union = left_area + right_area - intersection
    return intersection / union if union else 0.0


def empty_result(errors: list[str]) -> dict:
    return {
        "reward": 0.0,
        "rewards": {"strict": 0.0, "lenient": 0.0},
        "lenient_version": LENIENT_VERSION,
        "lenient_thresholds": LENIENT_THRESHOLDS,
        "lenient_checks": {key: {"completion": 0.0, "threshold": threshold, "passed": False}
                           for key, threshold in LENIENT_THRESHOLDS.items()},
        "reward_formulas": {"strict": STRICT_FORMULA, "lenient": LENIENT_FORMULA},
        "group_points": {key: 0.0 for key in WEIGHTS},
        "atoms": {},
        "errors": errors,
    }


def score(answer: Path, truth_path: Path, workspace_root: Path | None = None) -> dict:
    errors = []
    if workspace_root is None:
        configured = os.environ.get("AGENT_WORKSPACE")
        workspace_root = Path(configured) if configured else Path("/workspace")
        if not workspace_root.is_dir():
            workspace_root = Path(__file__).resolve().parents[1] / "environment/workspace"
    try:
        actual = parse_mei(answer, workspace_root)
    except Exception as exc:
        return empty_result([f"MEI: {exc}"])
    expected = json.loads(truth_path.read_text(encoding="utf-8"))["mei"]
    exp_events, got_events = expected["events"], actual["events"]
    pairs = align_events(exp_events, got_events)

    title = text_f1(expected.get("title", ""), actual.get("title", ""))
    expected_composer = expected.get("composer", "")
    if isinstance(expected_composer, list):
        expected_composer = max(expected_composer, key=len, default="")
    composer_values = actual.get("composer", []) + [x["text"] for x in actual["metadata"] if x["type"] == "attribution"]
    composer = max((text_f1(expected_composer, value) for value in composer_values), default=0.0)
    exp_mode = "".join(x["text"] for x in expected["metadata"] if x["type"] == "mode")
    mode = float(any(exp_mode and exp_mode in value for value in actual.get("mode", [])))
    header = (title + composer + mode) / 3

    event_text = field_f1(exp_events, got_events, pairs, "text")
    metadata_text = metadata_f1(expected["metadata"], actual["metadata"])
    reading_order = 0.75 * event_text + 0.25 * metadata_text
    pitch = categorical_macro_f1(exp_events, got_events, pairs, "pitch")
    secondary = categorical_macro_f1(exp_events, got_events, pairs, "secondary")
    page = categorical_macro_f1(exp_events, got_events, pairs, "page")
    page *= sum(x.get("page_consistent", True) for x in got_events) / max(len(got_events), 1)
    boundary_events = [dict(e,line_break=False) if owner(e,exp_events,'text_box')==len(exp_events)-1 else e for e in got_events]
    line_break = positive_f1(exp_events, boundary_events, pairs, "line_break")
    excluded = positive_f1(exp_events, got_events, pairs, "excluded")
    boundaries = (page + line_break) / 2

    geometry_values = []
    for i, j in pairs:
        geometry_values.append(iou(exp_events[i].get("text_box"), got_events[j].get("text_box")))
        geometry_values.append(iou(exp_events[i].get("notation_box"), got_events[j].get("notation_box")))
    geometry = sum(geometry_values) / max(2 * len(exp_events), 1)

    surface_count = count_similarity(len(expected["surfaces"]), len(actual["surfaces"]))
    valid_pages = {x["page"] for x in actual["surfaces"] if x["target_valid"]}
    expected_pages = {x["page"] for x in expected["surfaces"]}
    source_images = harmonic(len(valid_pages & expected_pages), len(expected_pages), len(actual["surfaces"]))
    closure = actual["closure"]
    atemporal = float(not actual["invented_semantics"])
    document = min(source_images, closure, atemporal)

    groups = {
        "header_context": header,
        "reading_order_text": reading_order,
        "pitch_classification": pitch,
        "secondary_classification": secondary,
        "boundary_decisions": boundaries,
        "facsimile_geometry": geometry,
        "source_images": source_images,
        "referential_closure": closure,
        "atemporal_fidelity": atemporal,
    }
    position_features, position_records = evaluate_positions(exp_events, got_events)
    source_region_quality = source_geometry(exp_events, got_events, position_records)
    groups['facsimile_geometry'] = sum(source_region_quality.values()) / 2
    groups.update(position_features)
    feature_atoms = {'position_bindings':position_records,'line_break_f1':line_break,'excluded_f1':excluded,
                     'metadata_f1':metadata_text,'source_region_quality':source_region_quality}
    refined = fine_features(exp_events,got_events,groups,feature_atoms)
    compact = compact_features(exp_events,got_events,groups,feature_atoms)
    content = content_features(exp_events,got_events,groups,feature_atoms,valid_pages)
    params = Path(__file__).with_name("scoring_params.json")
    configuration = json.loads(params.read_text()) if params.is_file() else {}
    weights = configuration.get("weights", WEIGHTS)
    ledger = groups if set(weights) == set(groups) else content if set(weights) == set(content) else compact if set(weights) == set(compact) else refined
    if set(weights) != set(ledger) or abs(sum(weights.values()) - 1) > 1e-8 or any(v < 0 for v in weights.values()):
        raise ValueError("invalid additive weights")
    earned_before_prohibition = sum(weights[key] * ledger[key] for key in weights)
    invented_semantics = bool(actual["invented_semantics"])
    strict = 0.0 if invented_semantics else earned_before_prohibition

    lenient_values = lenient_completion(content, exp_events, got_events, position_records)
    lenient_checks = {key: {"completion": lenient_values[key], "threshold": threshold,
                            "passed": lenient_values[key] >= threshold}
                      for key, threshold in LENIENT_THRESHOLDS.items()}
    lenient = float(all(item['passed'] for item in lenient_checks.values()))

    strict_reward = round(clamp(strict), 6)
    lenient_reward = round(clamp(lenient), 6)
    return {
        "reward": strict_reward,
        "rewards": {"strict": strict_reward, "lenient": lenient_reward},
        "lenient_version": LENIENT_VERSION,
        "lenient_thresholds": LENIENT_THRESHOLDS,
        "lenient_checks": lenient_checks,
        "reward_formulas": {"strict": STRICT_FORMULA, "lenient": LENIENT_FORMULA},
        "rubric_version": configuration.get("rubric_version", "mei-semantic-v9-source-core-coverage"),
        "weights": weights,
        "group_points": {key: round(clamp(value), 6) for key, value in groups.items()},
        "active_group_points": {key: round(clamp(value), 6) for key, value in ledger.items()},
        "atoms": {
            "expected_event_count": len(exp_events),
            "actual_event_count": len(got_events),
            "aligned_pairs": len(pairs),
            "event_text_f1": event_text,
            "metadata_f1": metadata_text,
            "page_f1": page,
            "line_break_f1": line_break,
            "excluded_f1": excluded,
            "surface_count_similarity": surface_count,
            "source_image_targets": actual["surfaces"],
            "duplicate_ids": actual["duplicate_ids"],
            "broken_references": actual["broken_refs"],
            "invented_semantics": actual["invented_semantics"],
            "invented_semantics_prohibition_triggered": invented_semantics,
            "position_bindings": position_records,
            "source_region_quality": source_region_quality,
            "metadata_source_grounding_diagnostic_only": metadata_grounding(expected["metadata"], actual["metadata"]),
        },
        "semantic_events": got_events,
        "scoring_features":refined,
        "compact_scoring_features":compact,
        "content_scoring_features":content,
        "source_census":{"primary_positions":len(exp_events),"bare_positions":sum(e['secondary'] is None for e in exp_events),
                         "compound_positions":sum(e['secondary'] is not None for e in exp_events)},
        "scoring_ledger":{"positive_completion":ledger,"positive_earned":earned_before_prohibition,
                          "damage_instances":[{"id":"invented_semantics","effect":"fatal"}] if invented_semantics else [],
                          "retention":0.0 if invented_semantics else 1.0},
        "errors": errors,
    }


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: validator.py ANSWER.mei")
    answer = Path(sys.argv[1])
    if answer.is_dir():
        candidates = [answer / "揚州慢.mei", answer / "output/揚州慢.mei"]
        answer = next((path for path in candidates if path.is_file()), candidates[0])
    result = score(answer, Path(__file__).with_name("ground_truth.json"))
    result['reward_strict'] = result['rewards']['strict']
    result['reward_lenient'] = result['rewards']['lenient']
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
