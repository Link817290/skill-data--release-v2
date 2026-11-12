# Residential egress plan repair

Inspect a residential first-floor HALL egress route against the supplied plan
and code excerpt, then issue a source-bound repair and coordination package.

## Package

The release package contains only `README.md`, `dataset.toml`, `RUBRIC.md`,
`MANIFEST.json`, `golden/` and `task/`. Build the actor image from the packaged
environment:

```sh
docker build --pull=false -t residential-egress-plan-repair:1.3 task/environment
```

The image derives from `harbor-claude-code-aggregated:1.3`. Both conditions use
the same image and byte-identical workspace inputs. `task/task.toml` mounts the
packaged skills; `task/task_no_skill.toml` omits that mount. The actor has no
network access, and Golden, Oracle and evaluator files are not actor-visible.

## Contract

The authoritative instruction is `task/instruction.md`. Required outputs under
`/workspace/output/` are:

- `inspection_report.json`
- `layer_inventory.json`
- `extracted_original_layout.json`
- `violations_before.json`
- `repaired_layout.json`
- `changes.json`
- `repair_memo.md`
- `repaired_plan.dxf`

The Oracle entry point is `task/solution/solve.sh`; the scoring entry point is
`task/tests/test.sh`.

The verifier accepts exactly six external judge variables:
`LLM_JUDGE_BASE_URL`, `LLM_JUDGE_API_KEY`, `LLM_JUDGE_MODEL` (default
`gpt-5.6-sol`), `LLM_JUDGE_CACHE_DIR`, `LLM_JUDGE_MODE` and
`LLM_JUDGE_TIMEOUT_SECONDS`. Fresh mode evaluates a new deliverable through the
OpenAI-compatible endpoint. Replay mode accepts only an exact request-bound
cache; a cache miss or judge/runtime failure does not become a business score.

## Scoring

`RUBRIC.md` is the public scoring contract and `task/tests/validator.py` is the
deterministic evaluator. It measures source integrity, target-object binding,
geometry, evidence closure and cross-file consistency. The unified LLM gate
checks on-task completeness and anti-gaming against the instruction; it does
not replace the geometry or source-fact checks.

`reward` aliases the continuous strict score. `reward_lenient` is the separate
binary coordination-readiness lens and is not derived from a strict-score
threshold. Golden must score strict and lenient `1.0` through
`task/tests/test.sh` in both fresh and exact-replay modes.
