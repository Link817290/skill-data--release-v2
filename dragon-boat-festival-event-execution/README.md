# Dragon Boat Festival event execution

The actor receives the supplied proposal/checklist and the event-operations skill.
It delivers `output/execution-plan.docx`.

The verifier combines deterministic source-bound checks with two semantic reviews.
It first aggregates thirty-six independent operating assertions into readiness
credit, then applies the shared four-stage readiness utility and deduplicated
business-harm deductions described in `RUBRIC.md`. Missing work loses its own
credit; an adopted wrong or unsafe instruction is handled separately as harm.
The binary lenient lens is an independent minimum-delivery check and does not
alter strict reward.
Release replay records are Golden-only and live under:

```text
task/tests/golden_replay/positive/<exact-request-key>/
task/tests/golden_replay/fact/<exact-request-key>/
```

Each directory binds the exact request, Golden artifact/evidence hashes, raw
response, validated decision/review and manifest. No ordinary candidate cache is
shipped. `LLM_JUDGE_MODE=replay` is offline and succeeds only for that
exact Golden request. A new or changed artifact must report an unmeasured cache miss
in replay mode and be evaluated with `LLM_JUDGE_MODE=fresh` plus evaluator-side
credentials.

Exact Golden replay performs zero model calls.

## Portable build and verification

Run these commands from this package directory. The actor build uses only the
declared base image and `task/environment`; the verifier then extends that actor
image with `task/tests`.

```bash
docker build --pull=false \
  -t dragon-boat-festival-event-execution:1.0 \
  task/environment

docker build --pull=false \
  -t dragon-boat-festival-event-execution-verifier:1.0 \
  task/tests
```

Golden verification is offline. Prepare a temporary workspace from repository
bytes and run the packaged verifier without judge credentials:

```bash
DRAGON_RUN_DIR="$(mktemp -d)"
mkdir -p "$DRAGON_RUN_DIR/workspace/output" \
  "$DRAGON_RUN_DIR/workspace/materials" \
  "$DRAGON_RUN_DIR/logs"
cp golden/execution-plan.docx "$DRAGON_RUN_DIR/workspace/output/execution-plan.docx"
cp task/environment/workspace/materials/event-proposal.docx \
  "$DRAGON_RUN_DIR/workspace/materials/event-proposal.docx"
cp task/environment/workspace/materials/materials-checklist.xlsx \
  "$DRAGON_RUN_DIR/workspace/materials/materials-checklist.xlsx"
chmod a+rx "$DRAGON_RUN_DIR" "$DRAGON_RUN_DIR/workspace" \
  "$DRAGON_RUN_DIR/workspace/output" "$DRAGON_RUN_DIR/workspace/materials"
chmod a+r "$DRAGON_RUN_DIR/workspace/output/execution-plan.docx" \
  "$DRAGON_RUN_DIR/workspace/materials/"*
chmod a+rwx "$DRAGON_RUN_DIR/logs"

docker run --rm --network none \
  -e LLM_JUDGE_MODE=replay \
  -v "$DRAGON_RUN_DIR/workspace:/workspace" \
  -v "$DRAGON_RUN_DIR/logs:/logs/verifier" \
  dragon-boat-festival-event-execution-verifier:1.0 \
  /tests/test.sh /workspace
```

For a new candidate, set `DRAGON_CANDIDATE_WORKSPACE` to a workspace containing
the unchanged `materials/` files and `output/execution-plan.docx`. Fresh scoring
requires an OpenAI Responses-compatible endpoint. The public judge interface for
this package is `LLM_JUDGE_MODE`, `LLM_JUDGE_BASE_URL`, `LLM_JUDGE_API_KEY` and
`LLM_JUDGE_MODEL`; evaluator-internal cache routing is not part of that interface.

```bash
DRAGON_FRESH_LOGS="$(mktemp -d)"
chmod a+rwx "$DRAGON_FRESH_LOGS"
docker run --rm \
  -e LLM_JUDGE_MODE=fresh \
  -e LLM_JUDGE_BASE_URL \
  -e LLM_JUDGE_API_KEY \
  -e LLM_JUDGE_MODEL="${LLM_JUDGE_MODEL:-gpt-5.6-sol}" \
  -v "$DRAGON_CANDIDATE_WORKSPACE:/workspace" \
  -v "$DRAGON_FRESH_LOGS:/logs/verifier" \
  dragon-boat-festival-event-execution-verifier:1.0 \
  /tests/test.sh /workspace
```
