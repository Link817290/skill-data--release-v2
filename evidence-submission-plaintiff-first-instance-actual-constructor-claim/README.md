# Evidence submission for an actual-constructor claim

This package asks counsel for the plaintiff to prepare a Chinese evidence-submission opinion from the supplied construction-dispute dossier. The declared deliverable is `artifacts/evidence-submission-opinion.md`.

## Package layout

The package has the standard six root entries: `README.md`, `dataset.toml`, `RUBRIC.md`, `MANIFEST.json`, `golden/`, and `task/`. Actor inputs live under `task/environment/workspace`; skills are visible only in the with-skill condition. Golden, Oracle code, evaluator sources and judge replay data are evaluator-only.

## Build

Both images use `harbor-claude-code-aggregated:1.3` as their declared base.

```bash
docker build --pull=false --target with-skill -f task/environment/Dockerfile -t evidence-submission:local task/environment
docker build --pull=false --target no-skill -f task/environment/Dockerfile -t evidence-submission-no-skill:local task/environment
docker build -f task/environment/Dockerfile.verifier -t evidence-submission-verifier:1.0 .
```

Both actor targets use the same instruction, materials and output contract. Only the
with-skill target copies `task/environment/skills` to `/skills`; the no-skill image
does not contain that path.

## Task contract

- Authoritative instruction: `task/instruction.md`.
- Candidate-visible dossier: `task/environment/workspace/materials/案件原始资料-某项目实际施工人纠纷.docx`.
- Required output: `<workspace>/artifacts/evidence-submission-opinion.md`.
- Oracle entry point: `task/solution/solve.sh`.
- Scoring entry point: `task/tests/test.sh`.

`task/instruction.md` and the workspace copy are byte-identical. The drafting actor has no network access. External semantic adjudication belongs only to the verifier.

## Mixed evaluator

The deterministic Program Judge owns file delivery, closed figures, evidence identifiers, party direction, filing structure, unsupported assertions and damage settlement. The source-bound semantic judge owns equivalent legal expression for P01-P16. Every nonzero semantic finding cites exact candidate and dossier spans; a deterministic source-anchor floor prevents ungrounded semantic credit.

Strict score is weighted positive completion multiplied once for each independent professional damage root. `RUBRIC.md` explains every weight, coefficient and the separate lenient filing-readiness gate. The two copies of `rubric-contract.json` are byte-identical.

## Fresh scoring

The verifier accepts exactly six external judge variables: `LLM_JUDGE_BASE_URL`, `LLM_JUDGE_API_KEY`, `LLM_JUDGE_MODEL`, `LLM_JUDGE_CACHE_DIR`, `LLM_JUDGE_MODE`, and `LLM_JUDGE_TIMEOUT_SECONDS`.

```bash
LLM_JUDGE_BASE_URL=https://api.openai.com/v1 \
LLM_JUDGE_API_KEY=... \
LLM_JUDGE_MODEL=gpt-5.6-sol \
LLM_JUDGE_MODE=fresh \
LLM_JUDGE_TIMEOUT_SECONDS=240 \
VERIFIER_OUTPUT_DIR=/tmp/evidence-verifier \
bash task/tests/test.sh /path/to/candidate-workspace
```

The response request is bound to the criteria, source and complete candidate content. Fresh results may be written only to the externally supplied cache directory.

## Exact Golden replay

The package contains one qualified, content-addressed Golden response under `task/tests/golden_replay/`. It permits offline reproduction of the exact Golden request:

```bash
LLM_JUDGE_MODE=replay \
LLM_JUDGE_MODEL=gpt-5.6-sol \
VERIFIER_OUTPUT_DIR=/tmp/evidence-golden \
bash task/tests/test.sh /path/to/golden-workspace
```

A changed candidate has a different request identity and replay fails closed. On verifier infrastructure failure, `test.sh` exits nonzero and writes `status: UNMEASURED`; it does not turn an unavailable judge into a business score of zero.
