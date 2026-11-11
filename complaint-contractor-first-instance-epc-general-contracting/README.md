# EPC contractor complaint

This package asks a contractor to draft a Chinese civil complaint arising from an EPC general-contracting dispute. The declared deliverable is `artifacts/civil-complaint.md`.

## Six root entries

1. `README.md` — release usage and verification commands.
2. `RUBRIC.md` — strict owners, weights, dependencies, damage rules, and the lenient filing gate.
3. `dataset.toml` — package identity, declared output, and scorer entry point.
4. `MANIFEST.json` — file inventory with byte counts and SHA-256 digests.
5. `golden/civil-complaint.md` — the reference filing used for Oracle validation.
6. `task/` — executable task definition, environment, skill, solution, and tests.

## Build

The image copies `task/environment/workspace` to `/workspace`, verifies `/workspace/materials`, and creates `/workspace/artifacts` and `/workspace/output`.

```bash
docker build \
  -f task/environment/Dockerfile \
  -t epc-contractor-complaint:local \
  task/environment
docker build -f task/environment/Dockerfile.verifier -t epc-contractor-complaint-verifier:1.0 .
```

## With-skill and no-skill configurations

- With skill: `task/task.toml`; mounts `task/environment/skills/complaint-construction`.
- Without skill: `task/task_no_skill.toml`; uses the same instruction, workspace, output, and scorer without a skill mount.

Both configurations disable network access for the drafting agent. External semantic adjudication belongs to the verifier process.

## Instruction, materials, and output

- Authoritative instruction: `task/instruction.md`.
- Workspace copy: `task/environment/workspace/instruction.md`.
- Candidate-visible inputs: `task/environment/workspace/materials/`.
- Required output: `<workspace>/artifacts/civil-complaint.md`.
- Reference solution entry point: `task/solution/solve.sh`.

The two instruction files must remain byte-identical.

## Oracles and scorer

The scorer is `task/tests/test.sh`, as declared by `dataset.toml`.

- `task/tests/pjroot/task/tests/program_judge/task_judge.py` owns closed facts: amounts, dates, party sets, request order, and document structure.
- `task/tests/semantic_judge.py` owns open legal equivalence and professional-error meaning. Every affirmative semantic decision must bind exact candidate and source spans.
- `task/tests/validator.py` settles both Oracles into one strict and lenient ledger.
- `task/tests/rubric-contract.json` is the machine-readable scoring contract. It must be byte-identical to `task/tests/pjroot/rubric-contract.json`.

Strict is earned positive content multiplied by one coefficient per distinct adopted damage root. Lenient uses the explicit remedy-and-quantum hard gate in the contract; it is not derived from a strict threshold.

## External fresh adjudication

Place a candidate at the declared output path inside a workspace directory, then provide the verifier endpoint:

```bash
LLM_JUDGE_BASE_URL=https://api.openai.com/v1 \
LLM_JUDGE_API_KEY=... \
LLM_JUDGE_MODEL=gpt-5.6-sol \
LLM_JUDGE_TIMEOUT_SECONDS=240 \
python3 -B task/tests/validator.py /path/to/candidate-workspace
```

The semantic request is content-addressed and source-bound. A candidate with a new request identity is sent to the external judge.

The public verifier variables are `LLM_JUDGE_BASE_URL`, `LLM_JUDGE_API_KEY`, `LLM_JUDGE_MODEL`, `LLM_JUDGE_CACHE_DIR`, `LLM_JUDGE_MODE`, and `LLM_JUDGE_TIMEOUT_SECONDS`. Both task configurations declare a mixed judge with continuous reward and capture `/workspace/artifacts/civil-complaint.md`.

## Exact replay

An exact previously adjudicated request can be replayed without a live endpoint:

```bash
LLM_JUDGE_REPLAY_ONLY=1 \
python3 -B task/tests/validator.py /path/to/candidate-workspace
```

If no exact stored response exists, replay fails instead of falling back to a local-only result.

Only OpenAI Responses with a `gpt-*` judge is accepted. The packaged replay contains only the exact Golden request. New candidates require live adjudication or an explicitly configured external `LLM_JUDGE_CACHE_DIR`; a miss without live service is `UNMEASURED`. The replay directory is outside the actor workspace.

## Unified verifier output and `UNMEASURED`

```bash
VERIFIER_OUTPUT_DIR=/tmp/epc-complaint-verifier \
bash task/tests/test.sh /path/to/candidate-workspace
```

On success, read `reward.json` and `reward_detail.json` in `VERIFIER_OUTPUT_DIR`. If either required Oracle fails, `test.sh` exits nonzero and writes:

```json
{"status":"UNMEASURED","error":"verifier infrastructure failed; see validator.log"}
```

An infrastructure failure never becomes a business score and never reuses a partial local verdict.
