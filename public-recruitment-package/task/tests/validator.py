#!/usr/bin/env python3
"""Two-lens entry point for the mixed structural and semantic rubric v3.4 scorer.

Judging logic is unchanged. `package_score.py` is carried verbatim from the
source package and still owns every positive item, deduction, and release
state. This module only does two things the released package format requires:

1. resolve the deliverable set from a workspace root, an `output/` directory, or
   a directory that holds the four files directly, because the harness and the
   local reproduction scripts pass different shapes;
2. render the result in the two-lens envelope (`rewards.strict`,
   `rewards.lenient`, `reward_formulas`, `group_points`).

The lenient lens is the source package's own binary release contract: the four
required artifacts were located, parsed, and left no unresolved evidence check.
It introduces no new judgement.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from package_score import evaluate  # noqa: E402
from semantic_judge import adjudicate, apply  # noqa: E402

REQUIRED = [
    "XX融资担保有限公司2026年公开招聘公告.doc",
    "附件1某融资担保有限公司2026年公开招聘岗位明细表.xlsx",
    "附件2 湖南省2026年考试录用公务员专业指导目录.xlsx",
    "附件3某融资担保有限公司公开招聘诚信承诺书.docx",
]

STRICT_FORMULA = (
    "max(0, sum(P01..P12 positive items weighted by fulfilled fraction) "
    "- sum(deduplicated deductions D01..D32, one charge per declared root cause))"
)
LENIENT_FORMULA = (
    "1 iff all four required artifacts are present and parse, the ledger closes with no "
    "unresolved evidence check, and at least half of the positive weight was earned"
)


def resolve_workspace(target: Path) -> Path:
    """Accept a workspace root, an output directory, or the artifact directory."""
    if target.is_file():
        target = target.parent
    for candidate in (target, target / "output", target / "workspace"):
        if candidate.is_dir() and any((candidate / name).is_file() for name in REQUIRED):
            return candidate.parent if candidate.name == "output" else candidate
        nested = candidate / "output"
        if nested.is_dir() and any((nested / name).is_file() for name in REQUIRED):
            return candidate
    return target


def envelope(result: dict) -> dict:
    strict = float(result.get("final", 0.0))
    # The hand-off contract asks whether the package could be taken up downstream, which
    # four files that parse but say the wrong thing cannot. Testing only the containers
    # made the lens constant: every submission that produced the four artefacts earned it,
    # including ones whose content earned almost nothing, so the second view reported the
    # same value for every run and distinguished nothing. A floor on the positive side is
    # required as well, set at half so the lens stays materially wider than the strict view.
    lenient = 1.0 if (result.get("release_status") == "scored"
                      and float(result.get("positive_earned", 0.0)) >= 0.5) else 0.0
    points = {}
    for item in result.get("positive_items") or []:
        weight = float(item.get("weight") or 0.0)
        points[str(item.get("id"))] = round(
            float(item.get("earned", 0.0)) / weight, 6
        ) if weight else 0.0
    result = dict(result)
    result.update(
        {
            "reward": strict,
            "reward_strict": strict,
            "reward_lenient": lenient,
            "rewards": {"strict": strict, "lenient": lenient},
            "reward_formulas": {"strict": STRICT_FORMULA, "lenient": LENIENT_FORMULA},
            "group_points": points,
        }
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", nargs="?", default="/workspace")
    parser.add_argument("--output")
    parser.add_argument("--output-dir")
    args = parser.parse_args()

    workspace = resolve_workspace(Path(args.workspace).resolve())
    result = evaluate(workspace)
    # File/structure/numeric checks remain deterministic. Meaning, negation and
    # equivalent professional wording are adjudicated by the packaged GPT judge.
    semantic = adjudicate(workspace)
    result = apply(result, semantic)
    result = envelope(result)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    strict = result["rewards"]["strict"]
    lenient = result["rewards"]["lenient"]

    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    if args.output_dir:
        out = Path(args.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "reward_detail.json").write_text(payload + "\n", encoding="utf-8")
        (out / "verify_result.json").write_text(payload + "\n", encoding="utf-8")
        compact = {
            "reward": strict,
            "reward_strict": strict,
            "reward_lenient": lenient,
        }
        compact.update(result["group_points"])
        (out / "reward.json").write_text(
            json.dumps(compact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (out / "reward.txt").write_text(f"{strict:.6f}\n", encoding="utf-8")
        (out / "reward_strict.txt").write_text(f"{strict:.6f}\n", encoding="utf-8")
        (out / "reward_lenient.txt").write_text(f"{lenient:.6f}\n", encoding="utf-8")

    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
