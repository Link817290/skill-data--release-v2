# Second-instance appellee defence

This package asks first-instance plaintiff A Company, as appellee, to answer B Company's civil appeal in Chinese. The declared output is `artifacts/appeal-defence-statement.md`.

## Release structure

- `RUBRIC.md`, `dataset.toml`, and `MANIFEST.json` define scoring and inventory.
- `golden/appeal-defence-statement.md` is the reference filing.
- `task/task.toml` is the with-skill configuration; `task/task_no_skill.toml` is the no-skill configuration.
- `task/instruction.md` and `task/environment/workspace/instruction.md` must be byte-identical.
- Materials are in `task/environment/workspace/materials/`; the skill is `task/environment/skills/litigation-responsive-pleadings/`.

## Build

```bash
docker build -f task/environment/Dockerfile -t appellee-defence:local task/environment
docker build -f task/environment/Dockerfile.verifier -t appellee-defence-verifier:1.0 .
```

## Oracles and scorer

`dataset.toml` declares `task/tests/test.sh`. The local Oracle owns closed amounts, dates, parties and structure. `task/tests/semantic_judge.py` owns open legal/technical equivalence and binds affirmative decisions to exact candidate and source spans. `task/tests/validator.py` settles both into one strict/lenient ledger.

Fresh external adjudication:

```bash
LLM_JUDGE_BASE_URL=https://api.openai.com/v1 \
LLM_JUDGE_API_KEY=... \
LLM_JUDGE_MODEL=gpt-5.6-sol \
LLM_JUDGE_TIMEOUT_SECONDS=240 \
python3 -B task/tests/validator.py /path/to/workspace
```

Exact replay:

```bash
LLM_JUDGE_REPLAY_ONLY=1 python3 -B task/tests/validator.py /path/to/workspace
```

Only OpenAI Responses with a `gpt-*` judge is accepted. The packaged replay contains only the exact Golden request. New candidates require live adjudication or an explicitly configured external `LLM_JUDGE_CACHE_DIR`; a miss without live service is `UNMEASURED`.

The public verifier variables are `LLM_JUDGE_BASE_URL`, `LLM_JUDGE_API_KEY`, `LLM_JUDGE_MODEL`, `LLM_JUDGE_CACHE_DIR`, `LLM_JUDGE_MODE`, and `LLM_JUDGE_TIMEOUT_SECONDS`. Both task configurations declare a mixed judge with continuous reward and capture `/workspace/artifacts/appeal-defence-statement.md`.

Verifier tests and the Golden semantic response are outside `task/environment/workspace`; they are not mounted into the drafting actor's workspace and are not candidate-visible.

Unified verifier:

```bash
VERIFIER_OUTPUT_DIR=/tmp/appellee-verifier bash task/tests/test.sh /path/to/workspace
```

If either required Oracle fails, the verifier exits nonzero and writes `status.json` with `UNMEASURED`; it never substitutes a partial local score.
