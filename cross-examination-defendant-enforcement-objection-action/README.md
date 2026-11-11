# Defendant Evidence Opinion In An Enforcement-Objection Action

This package asks an agent acting for the defendant to prepare a concise Chinese opinion on the plaintiff's evidence. The required deliverable is:

```text
artifacts/质证意见.docx
```

The agent environment has no network access. Semantic adjudication runs in the verifier, outside the agent environment.

## Package Layout

The documented release interface consists of six root entries:

```text
MANIFEST.json   File inventory with byte sizes and SHA-256 digests
README.md       Package operation guide
RUBRIC.md       Human-readable scoring and legal-usability contract
dataset.toml    Dataset identity, output contract, and scorer selection
golden/         Authored reference deliverable
task/           Instruction, environment, skill, solution, and evaluator
```

## Build

Build the agent environment from the package root:

```bash
docker build -t enforcement-evidence-opinion-agent:1.0 task/environment
```

The image copies `task/environment/workspace/` to `/workspace`, creates `/workspace/artifacts`, and starts in `/workspace`.

## With-Skill And Without-Skill Conditions

- The with-skill runner mounts the procedures under `task/environment/skills/`.
- The no-skill runner materializes the same task without that directory.

`task/task.toml` and `task/task_no_skill.toml` otherwise use the same canonical runtime configuration, instruction, materials, output path, time limits, and evaluator. The only condition difference is availability of the packaged evidence-opinion procedures.

## Instruction And Materials

- Agent instruction: `task/instruction.md`
- Container copy of the instruction: `task/environment/workspace/instruction.md`
- Source documents: `task/environment/workspace/materials/`

The materials contain the complaint and the evidence bundle for the enforcement-objection action.

The actor instruction states only the assignment, represented party, source boundary, unknown-fact policy, and delivery contract. It does not enumerate the professional method or the scored evidentiary analysis. Both arms receive this same instruction; only the with-skill arm receives the applicable working procedures.

## Output Contract

Write one Chinese Word document at:

```text
/workspace/artifacts/质证意见.docx
```

The delivery gate checks the exact name, Word carrier, Chinese content, extra files, and bulk source copying.
Both task configurations declare the same exact artifact capture path, `/workspace/artifacts/质证意见.docx`.

## Authored Oracle And Replay

The package includes a request-bound replay record for the unchanged authored reference. It can be evaluated without external credentials:

```bash
workdir="$(mktemp -d)"
bash task/solution/solve.sh "$workdir"
env -i PATH="$PATH" LANG="${LANG:-C.UTF-8}" \
  python3 -B task/tests/validator.py "$workdir"
```

The JSON result must report `final_score: 1.0`, `rewards.strict: 1.0`, `rewards.lenient: 1.0`, and semantic origin `golden_replay`.

`task/tests/golden_replay/` contains exactly one response keyed by the unchanged Golden's complete semantic-request SHA-256. It contains no ordinary candidate response, run/provider history or credential and is outside the actor image.

## Fresh Semantic Adjudication

An unseen candidate has no matching replay record. Configure the verifier with:

```text
LLM_JUDGE_BASE_URL             normalized to /v1/responses
LLM_JUDGE_API_KEY
LLM_JUDGE_MODEL            optional GPT model; defaults to gpt-5.6-sol
LLM_JUDGE_CACHE_DIR        optional external request-bound replay/cache directory
LLM_JUDGE_MODE             optional: auto (default), replay, or live
LLM_JUDGE_TIMEOUT_SECONDS  optional; defaults to 240
LLM_JUDGE_REASONING_EFFORT optional
```

Then evaluate a workspace containing the candidate:

```bash
python3 -B task/tests/validator.py /path/to/candidate-workspace
```

The semantic request binds the model, criteria, source, and candidate. Selected evidence spans resolve to exact candidate text. `auto` uses an exact request-bound replay when present and otherwise calls the live service; `replay` forbids a live fallback; `live` bypasses replay. Deterministic checks independently score document identities, delivery, and affirmative errors.

If a candidate has no matching replay record and the external judge is unavailable or returns an invalid evidence-bound response, the result is **UNMEASURED**: the evaluator exits with an infrastructure error. It is never converted to a business zero and never falls back to the authored reference.

## Scorer

`task/tests/validator.py` locates the exact deliverable, invokes the program judge under `task/tests/pjroot/task/tests/program_judge/`, and applies the delivery gate. The machine contract is `task/tests/rubric-contract.json`; its packaged mirror is required to be byte-identical.

Strict evaluation is:

```text
positive_earned * product(distinct_damage_retention)
```

Lenient evaluation is a named legal-usability gate over the issuing party, a case-bound merits objection, and blocking affirmative errors. It is not derived from a strict threshold or an error count.
