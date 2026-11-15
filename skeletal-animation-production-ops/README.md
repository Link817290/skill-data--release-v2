# Skeletal animation production operations

Repair the Godot effects integration for FX-301 through FX-305 and deliver a
runnable project, fresh previews, and a ticket-level handover register.

## Package

The release root contains `README.md`, `dataset.toml`, `RUBRIC.md`,
`MANIFEST.json`, `golden/`, and `task/`. Build the shared actor and verifier
image from the packaged context:

```sh
docker build --pull=false -t skeletal-animation-production-ops:1.3 task/environment
```

The image derives from `harbor-claude-code-aggregated:1.3`, installs Godot
4.4.1, and copies the packaged producer runtime from
`task/environment/build-context/runtime/` to `/opt/fx-tools/`. Both skill
conditions use the same image and source workspace. The no-skill manifest
omits only the actor skills.

## Contract

The authoritative task is `task/instruction.md`. The actor writes the complete
replacement delivery under `/workspace/output/`, including `project/`,
`preview/`, and `delivery-register.xlsx`. Run the Oracle with
`task/solution/solve.sh` and score a workspace or delivery directory with
`task/tests/test.sh`.

The mixed verifier accepts six external judge variables:
`LLM_JUDGE_BASE_URL`, `LLM_JUDGE_API_KEY`, `LLM_JUDGE_MODEL` (default
`gpt-5.6-sol`), `LLM_JUDGE_CACHE_DIR`, `LLM_JUDGE_MODE`, and
`LLM_JUDGE_TIMEOUT_SECONDS`. Fresh mode measures a new delivery through an
OpenAI-compatible Responses endpoint. Replay mode accepts only an exact
request-bound cache. A cache miss or infrastructure failure is unmeasured.

## Scoring

`RUBRIC.md` defines the public scoring contract. Deterministic Godot execution
measures original assets, visual behavior, lifecycle, world-space flight,
notifications, cleanup, and the configured integration stage. The semantic
judge evaluates equivalent professional handover evidence and source-bound
claims. Strict is the positive weighted sum of ten business outcomes. Lenient
uses the same underlying functional observations and has no strict threshold.

Golden must score `strict=1.0` and `lenient=1.0` through the actual entrypoint
in fresh and exact-replay modes.
