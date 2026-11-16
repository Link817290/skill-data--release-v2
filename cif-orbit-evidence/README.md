# CIF Orbit Evidence

Create `/workspace/output/orbit_evidence.json` from the four original CIFs in `task/environment/workspace/materials`. Native scoring uses Python's standard library and no external crystallographic database. Numerical, affine-group, formula, pointer and structural conclusions are deterministically recomputed. A required source-bound semantic judge separately checks only open claim scope, evidence interpretation and source fidelity; it does not rejudge arithmetic.

Build from this package root:

```bash
docker build --target with-skill -t cif-orbit-actor-with-skill:1.0 task/environment
docker build --target no-skill -t cif-orbit-actor-no-skill:1.0 task/environment
docker build -f task/environment/Dockerfile.verifier -t cif-orbit-private-verifier:1.0 .
harbor run --path task --agent oracle --jobs-dir /tmp/cif-orbit-jobs
```

All three images derive from `harbor-claude-code-aggregated:1.3`. The actor runs as UID 20005 without network; only the with-skill image contains `/skills`. Golden, tests and Oracle assets are absent from actor images. The separate verifier runs as root with public judge access, private tests and original materials; credentials are verifier-only. To run the no-skill condition, materialize a copy of `task/` with `task_no_skill.toml` as `task.toml`; the inputs, instruction and private scorer are identical.

Private tests contain one exact Golden replay under `task/tests/golden_replay`,
binding artifact, evidence and request hashes and sealing raw fixture response,
validated review, validation and manifest. It is Golden-only, actor-invisible and
contains no credential or ordinary candidate response. New-artifact
misses require evaluator replay/fresh and otherwise are UNMEASURED.

Fresh review uses the OpenAI Responses API with `stream:false`, default model
`gpt-5.6-sol`, low reasoning effort, a compact strict JSON schema and a 16000-token
output ceiling. The parser accepts a complete JSON response or completed SSE envelope
and rejects incomplete responses without assigning a score. Configure
`LLM_JUDGE_BASE_URL`, `LLM_JUDGE_API_KEY` and optionally `LLM_JUDGE_MODEL`
(default `gpt-5.6-sol`) in the verifier environment.

The Oracle `task/solution/solve.sh` derives the register from CIF tokens and affine actions; it does not read Golden or evaluator truth. Golden is independently scored through the same entrypoint:

```bash
VERIFIER_OUTPUT_DIR=/tmp/cif-golden bash task/tests/test.sh golden
```

For host replay set `MATERIALS_DIR` to the original materials directory if `/workspace` exists. The entrypoint accepts a JSON file, a directory containing `orbit_evidence.json`, or a directory containing `output/orbit_evidence.json`. Strict quality is continuous; binary lenient completion checks the required evidence and scientific conclusions independently of weights. `reward.json` contains only numeric rewards; `reward_detail.json` records checks and deductions. Invalid/missing candidate JSON scores zero. Missing evaluator components, permission failures and malformed scoring output fail nonzero and remove stale rewards.
