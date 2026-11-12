#!/usr/bin/env python3
"""Validate factual accuracy, Must-have compliance, and paired reasoning reviews."""
import argparse
import json
from pathlib import Path

from score_review import NAMES, aggregate, digest, scaffold

HERE = Path(__file__).resolve().parent
GOLDEN_REPLAY_DIR = HERE / "golden_replay"
TRUTH = json.loads((HERE / "ground_truth.json").read_text(encoding="utf-8"))


def output_directory(target):
    target = Path(target)
    if target.is_file():
        return target.parent
    if (target / "output").is_dir():
        return target / "output"
    return target


def exact_golden(output):
    expected = TRUTH["authoritative_golden"]
    return all(
        (output / name).is_file() and digest(output / name) == sha256
        for name, sha256 in expected.items()
    ) and set(expected) == set(NAMES.values())


def golden_replay(output: Path) -> dict:
    paths = sorted(GOLDEN_REPLAY_DIR.glob("*.json"))
    if len(paths) != 1:
        raise ValueError("Exactly one Golden replay record is required")
    envelope = json.loads(paths[0].read_text(encoding="utf-8"))
    review = envelope.get("review")
    if not isinstance(review, dict):
        raise ValueError("Golden replay record lacks review")
    if envelope.get("artifacts") != review.get("artifacts"):
        raise ValueError("Golden replay artifact binding mismatch")
    expected = {role: digest(output / name) for role, name in NAMES.items()}
    if envelope.get("artifacts") != expected:
        raise ValueError("Golden replay does not bind the submitted Golden artifacts")
    return review


def evaluate(target, review_path=None):
    output = output_directory(target)
    archived_review = output.parent / "verifier/review.json"
    if review_path is None and output.name == "artifacts" and archived_review.is_file():
        review_path = archived_review
    if review_path is not None:
        review = json.loads(Path(review_path).read_text(encoding="utf-8"))
        result = aggregate(output, review)
        result["score_valid"] = result.get("status") == "REVIEWED"
        return result
    if exact_golden(output):
        result = aggregate(output, golden_replay(output))
        if result.get("status") != "REVIEWED":
            raise ValueError("Packaged Golden review is invalid: " + "; ".join(result.get("issues", [])))
        result["status"] = "GOLDEN_REVIEW_VERIFIED"
        result["score_valid"] = True
        result["evaluation_mode"] = "packaged_source_audited_review"
        return result
    result = aggregate(output)
    factual = result["rewards"]["factual_accuracy"]
    lenient = result["rewards"]["lenient"]
    result.update(
        status="REVIEW_REQUIRED",
        reward=0.0,
        rewards={"strict": 0.0, "lenient": lenient, "factual_accuracy": factual, "reasoning_quality": None},
        score_100=0.0,
        scores_100={"strict": 0.0, "lenient": lenient * 100, "factual_accuracy": factual * 100, "reasoning_quality": None},
        score_valid=False,
        issues=["A non-Golden submission requires a Golden-paired Reasoning-quality review."],
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("target", type=Path)
    parser.add_argument("--review", type=Path)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.target, args.review), ensure_ascii=False, indent=2))
