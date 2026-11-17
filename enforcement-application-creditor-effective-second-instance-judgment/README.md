# Creditor Application For Enforcement Of Effective Judgment

This package asks an agent acting for `A公司` to prepare a Chinese application for enforcement from the first- and second-instance judgments. Deliver one Word document at `artifacts/执行申请书.docx`. The agent environment has no network access; semantic adjudication runs only in the verifier.

## Package Layout

The release has six root entries: `MANIFEST.json`, `README.md`, `RUBRIC.md`, `dataset.toml`, `golden/`, and `task/`.

## Build And Conditions

Build the actor with `docker build -t enforcement-application-agent:1.0 task/environment` and the verifier with `docker build -f task/environment/Dockerfile.verifier -t enforcement-application-verifier:1.0 .`. `task/task.toml` enables the packaged enforcement-filing skill; `task/task_no_skill.toml` uses the same instruction, judgments, output contract, time limits, and evaluator without that skill.

The instruction is `task/instruction.md`; the actor copy and judgments are under `task/environment/workspace/`. The delivery gate checks the exact filename, Word carrier, Chinese filing content, and extra files.

## Authored Oracle

```bash
workdir="$(mktemp -d)"
bash task/solution/solve.sh "$workdir"
python3 -B task/tests/validator.py "$workdir"
```

The authored reference must report strict and lenient scores of `1.0` with semantic origin `golden_replay`. `task/tests/golden_replay/` contains exactly one response bound to the unchanged Golden semantic request. It contains no ordinary candidate response, provider history, or credential and is outside the actor image.

## Scorer

`task/tests/validator.py` invokes the program judge under `task/tests/pjroot/task/tests/program_judge/`, applies the delivery gate, and requires source-bound semantic review for unsupported adopted enforcement facts and the effective title's party reach. The machine contract is `task/tests/rubric-contract.json`; its packaged mirror must be byte-identical. Strict scoring is `positive_earned * product(distinct_damage_retention)`. Lenient scoring is a named legal-usability gate, independent of a strict threshold.

An unseen candidate requires a fresh OpenAI Responses GPT judge configured with `LLM_JUDGE_BASE_URL`, `LLM_JUDGE_API_KEY`, `LLM_JUDGE_MODEL` (default `gpt-5.6-sol`), `LLM_JUDGE_CACHE_DIR`, `LLM_JUDGE_MODE` (default `fresh`), and `LLM_JUDGE_TIMEOUT_SECONDS` (default `240`). The base URL is normalized to `/v1/responses`. Missing service, non-GPT model, non-Responses protocol, or an invalid evidence-bound result is `UNMEASURED` and exits nonzero.

Both task configurations declare a mixed judge with continuous reward and capture `/workspace/artifacts/执行申请书.docx`.
