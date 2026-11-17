# First-Instance Defendant Statement Of Defense

This package asks an agent acting for the defendant to prepare a Chinese statement of defense from the complaint and evidence bundle. Deliver one UTF-8 Markdown file at `artifacts/statement-of-defense.md`. The agent environment has no network access; semantic adjudication runs only in the verifier.

## Package Layout

The release has six root entries: `MANIFEST.json`, `README.md`, `RUBRIC.md`, `dataset.toml`, `golden/`, and `task/`.

## Build And Conditions

Build the actor with `docker build -t first-instance-defense-agent:1.0 task/environment` and the verifier with `docker build -f task/environment/Dockerfile.verifier -t first-instance-defense-verifier:1.0 .`. `task/task.toml` enables the packaged defense skill; `task/task_no_skill.toml` uses the same instruction, materials, output contract, time limits, and evaluator without that skill.

The instruction is `task/instruction.md`; the actor copy and source materials are under `task/environment/workspace/`. The output filename and location are exact.

## Authored Oracle

```bash
workdir="$(mktemp -d)"
bash task/solution/solve.sh "$workdir"
python3 -B task/tests/validator.py "$workdir"
```

The authored reference must report strict and lenient scores of `1.0`. `task/tests/golden_replay/` contains exactly one response bound to the unchanged Golden semantic request. It contains no ordinary candidate response, provider history, or credential and is outside the actor image.

## Scorer

`task/tests/validator.py` invokes the program judge under `task/tests/pjroot/task/tests/program_judge/`, applies the delivery gate, and requires evidence-bound semantic review for open legal positions and causation. The machine contract is `task/tests/rubric-contract.json`; its packaged mirror must be byte-identical. Strict scoring is `positive_earned * product(distinct_damage_retention)`. Lenient scoring is a named legal-usability gate, independent of a strict threshold: all six source-bound units P01, P03, P04, P05, P07 and P09 must be observably addressed, the adopted strategy must be source-supported, and no declared critical damage may fire.

An unseen candidate requires a fresh OpenAI Responses GPT judge configured with `LLM_JUDGE_BASE_URL`, `LLM_JUDGE_API_KEY`, `LLM_JUDGE_MODEL` (default `gpt-5.6-sol`), `LLM_JUDGE_CACHE_DIR`, `LLM_JUDGE_MODE` (default `fresh`), and `LLM_JUDGE_TIMEOUT_SECONDS` (default `240`). The base URL is normalized to `/v1/responses`. Missing service, non-GPT model, non-Responses protocol, or an invalid evidence-bound result is `UNMEASURED` and exits nonzero.

Both task configurations declare a mixed judge with continuous reward and capture `/workspace/artifacts/statement-of-defense.md`.
