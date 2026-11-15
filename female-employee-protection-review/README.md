# Female employee protection review

Review the supplied HR, scheduling, payroll, approval and legal-source records and deliver three editable Office files under `output/`: a review report, an employee audit workbook and an accountable action workbook.

The actor image is built from `task/environment/Dockerfile`; the verifier image is built from `task/environment/Dockerfile.verifier`. Both use `harbor-claude-code-aggregated:1.3`. The with-skill condition exposes `task/environment/skills/`; the no-skill condition receives the same source workspace without those skills.

Run the Oracle with `task/solution/solve.sh WORKSPACE`. Run scoring with `task/tests/test.sh --artifact WORKSPACE/output --output VERIFIER_OUTPUT`. Golden exact replay is bundled under `task/tests/llm_judge/cache`. New artifacts require the six verifier-only `LLM_JUDGE_*` settings declared in both task configurations.

Strict scoring is additive source-bound completion less unique business damage. Lenient scoring is an independent conjunction of current-review, evidence-safety and accountable-control necessities. Infrastructure or judge failures exit nonzero without publishing a candidate score.
