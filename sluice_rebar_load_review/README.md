# Structural calculation review

This package asks a reviewer to inspect the supplied original-format engineering report and deliver `review.xlsx`. The workbook records load-combination arithmetic, stability and serviceability comparisons, reinforcement-area intermediates, and unresolved demand evidence with source locations.

## Package layout

- `task/environment/workspace/materials/` contains the only actor-visible source report.
- `task/environment/skills/` contains the three review procedures used by the with-skill condition.
- `task/solution/` derives the reference workbook from the supplied report.
- `task/tests/` contains the mixed program and source-bound semantic scorer.
- `golden/review.xlsx` is the reference deliverable.

## Scoring runtime

The verifier recalculates delivered Excel formulas on an isolated copy before reading formula-backed statuses. LibreOffice is therefore a verifier dependency; failure to calculate a workbook is an infrastructure error rather than a candidate zero.

Equivalent professional expressions, distributed evidence, negation, and approval-layer distinctions are adjudicated with the OpenAI Responses protocol using `gpt-5.6-sol`. Fresh scoring uses the verifier-only `LLM_JUDGE_BASE_URL`, `LLM_JUDGE_API_KEY`, and optional `LLM_JUDGE_MODEL`, `LLM_JUDGE_CACHE_DIR`, `LLM_JUDGE_MODE`, and `LLM_JUDGE_TIMEOUT_SECONDS` settings. A service or schema failure leaves the trial unmeasured and `test.sh` publishes no numeric reward.

The package contains a request-bound replay only for the exact Golden candidate. Any different artifact must use the fresh judge path. No actor-visible answer cache, rollout history, evaluator log, or credential is included.

Run the task solution with `task/solution/solve.sh /workspace/review.xlsx`. Run the scorer with `task/tests/test.sh /workspace/review.xlsx`; outputs are written under `VERIFIER_OUTPUT_DIR` (default `/logs/verifier`).
