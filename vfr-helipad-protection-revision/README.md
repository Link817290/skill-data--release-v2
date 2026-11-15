# VFR Helipad Protection Revision

This package contains one self-contained skill-bench task for revising a legacy
VFR helipad protection plan. The supplied criteria PDFs are the only design
sources. The deliverable is an English, metric issue-for-coordination handoff:
an inspection report, a repaired plan-view DXF, and a repair memo.

## Package Layout

```text
vfr-helipad-protection-revision/
  README.md
  RUBRIC.md
  MANIFEST.json
  dataset.toml
  golden/
    inspection_report.json
    repaired_plan.dxf
    repair_memo.md
  task/
    instruction.md
    task.toml
    task_no_skill.toml
    environment/
      Dockerfile
      workspace/
      skills/
      wheels/
    solution/
    tests/
```

The package intentionally contains no rollout trajectories, historical score
reports, calibration notebooks, or local audit directories. `MANIFEST.json`
lists every shipped file and its SHA-256 digest.

## Reproduce A Score

Build the task environment from `task/environment/Dockerfile`, mount the
workspace and a candidate output directory, then run:

```bash
python3 -B task/tests/validator.py <candidate-output-directory>
```

The reference output can be checked with:

```bash
python3 -B task/tests/validator.py golden
```

The evaluator must provide `LLM_JUDGE_BASE_URL` and
`LLM_JUDGE_API_KEY`. `LLM_JUDGE_MODEL` defaults to `gpt-5.6-sol` and may be
overridden by the evaluator. The semantic judge is source-bound: it evaluates
the adopted meaning, negation, scope, and equivalent wording from the supplied
criteria rather than awarding credit for keyword presence. Its returned quotes
are resolved to exact candidate spans before scoring. A judge or required input
failure is an unscorable run; it is never converted to a zero score.

`task/tests/test.sh` is the container entry point. It writes verifier results
outside the package and does not modify the candidate or the package tree.

## Scoring Contract

`RUBRIC.md` is the human-readable scoring contract. The executable weights and
deductions are in `task/tests/scoring_params.json`; `task/tests/validator.py`
is the sole program scorer. Strict and lenient are both reported, with strict
used as the dataset reward. The Golden output is a complete source-bound
reference and is intended to score `1/1` under both lenses after the evaluator
has configured its semantic judge.
