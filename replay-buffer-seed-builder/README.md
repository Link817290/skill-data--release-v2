# Replay buffer seed from a corrected grasp trajectory

## Value and scope

This skill-bench package represents a robotics data engineer turning an
already-processed pick-and-place episode into the compact seed file a
downstream learner is initialised from. The runtime workspace holds a corrected
state trajectory stored as a `.npz` array, a phase annotation file produced by a
separate pipeline, and the training script the seed is meant to feed. The final
artifact is one JSONL file, one record per sampled frame, in ascending time
order. The task exercises inspecting a binary state array, choosing which source
rows a compact seed should represent, joining each of those rows to exactly one
declared phase interval, reconciling the stretch of trajectory the annotation
never covers, recomputing each observation from the same bound source row, and
making action authority and downstream routing follow the phase. The public
package excludes raw rollout trajectories.

## 60-second verification

From this directory, run:

```bash
python3 task/tests/validator.py golden/replay_buffer_seed.jsonl \
  --materials task/environment/workspace/materials
```

The observed pre-run result is strict reward `1.000000` and lenient diagnostic
`1.000000`.

The full scoring entry point, which is what the platform calls, is:

```bash
sh task/tests/test.sh <workspace_root>
```

For measured candidates it writes `reward.txt`, `reward_strict.txt`,
`reward_lenient.txt`, `reward.json`, `reward_detail.json`, and
`verify_result.json` into `$VERIFIER_OUT` (default `/logs/verifier`). A judge
service failure or exact-cache miss exits nonzero with an `UNMEASURED` detail
and removes numeric reward files.

For fresh scoring, configure `LLM_JUDGE_BASE_URL`, `LLM_JUDGE_API_KEY`,
`LLM_JUDGE_MODEL=gpt-5.6-sol`, `LLM_JUDGE_MODE=fresh`,
`LLM_JUDGE_TIMEOUT_SECONDS`, and an evaluator-owned `LLM_JUDGE_CACHE_DIR`.
`LLM_JUDGE_MODE=replay` accepts only an exact request and runtime-bound cache.
The package contains one qualified replay fixture for the exact Golden request.

## Task authenticity

The materials are a cropped operational set from a real trajectory-processing
pipeline: a unified state array carrying both a corrected and an uncorrected
variant, a phase annotation file whose declared coverage stops short of the
corrected array, and the residual-RL training script the seed feeds. **The
material is array-borne.** Every observation value in the deliverable is
recomputed from the `.npz` array, so no transcript substitutes for opening it;
a solver that cannot read the binary array cannot attempt the task.

What the instruction hands over is the deliverable path, the six top-level
members of each record and the members nested inside them, and the requirement
that records be in ascending time order. No item pays for reproducing that
structure. What is not given is which source rows the seed should represent, how
the annotation clock relates to the corrected array, what to do with the
trajectory beyond the annotation endpoint, which coordinate carries base height,
or how action authority and routing should change across the phases. The runtime
skill teaches a replay-seed construction method and carries no time, value,
constant or reference conclusion from this episode.

## Scoring method

Scorer `task/tests/validator.py`, which wraps
`task/tests/program_judge/task_judge.py` against
`task/tests/program_judge/rubric-contract.json`; rubric `RUBRIC.md`. Strict
reward is the weighted sum over twenty-five positive items of weight times the
fraction of that item's own condition met, minus root-cause-deduplicated
deductions over twenty deduction items, floored at 0. Positive weight is
distributed across four families: the representative-time and local phase
relation at `0.102`, the corrected-row mean derivation and array width at
`0.031`, the corrected base-coordinate derivation at `0.026`, and the
sequence, authority, target, and downstream-routing relations at `0.841`. Per-record items are gated a second time on
whether the bound source row is the adopted representative row; an item correct
on a coherent alternative row earns one eighth of its weight. See
[RUBRIC.md](RUBRIC.md) for the family table, the gate and the deduction table.

The independent lenient diagnostic is a binary hand-off contract: the file
parses as non-empty JSONL, every record carries the six required top-level
members, no unsupported top-level field is introduced, and every item reaches a decided state with non-zero credit.
Non-zero credit does not require the adopted representative row, so this lens
reads whether the work was done correctly against the materials while the strict
lens additionally prices the sampling scaffold. Deductions are not re-applied on
this lens.

The reference answer scores `1.000000` on both lenses. All numeric, structural,
phase, target, and authority items are computed by
`task/tests/program_judge/task_judge.py`. P25 is the sole semantic item:
`task/tests/semantic_judge.py` binds the emitted routing labels to exact candidate
records and the supplied `ppo_script.py`, then asks `gpt-5.6-sol` whether the
precontact and later labels are professionally equivalent to the consumer's two
routes. Keyword matching is not used. A missing judge or invalid response makes
the score `UNMEASURED`; it does not become a candidate zero.

## Pre-release results

The reference answer in `golden/` is the package owner's own seed file,
byte-identical to the copy `task/solution/solve.sh` replays. It earns full
positive credit with no deduction fired and no item left undecided. The
with-skill and no-skill task definitions share the instruction, workspace,
reference answer and byte-identical condition-blind scorer; the no-skill copy
removes both the skill mount and the runtime skill directory.

## Directory and runtime

- `task/` contains the Harbor task, offline workspace, runtime skill, oracle replay and scorer.
- `golden/` contains only the reference answer.
- `task/tests/golden_replay/` contains the single request-bound Golden semantic fixture.

The container is pinned to `harbor-claude-code-aggregated:1.3` in
`task/environment/Dockerfile`, actor network access is disabled, and the
deliverable is written to `workspace/output/`. The verifier requires network
access only in fresh semantic mode.
