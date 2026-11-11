# Cooperative D2D relaying manuscript revision dataset

## Value and scope

This skill-bench package represents a researcher revising a conference paper
whose central proposition is loose. The final artifact is a compiled PDF
manuscript. The task exercises reading a proof to locate a defect, deciding
whether the old statement is wrong or merely imprecise, and propagating the
correction through every place that depends on it — the sparsity statement, the
convex-hull argument, the simplex dimensions, and the budget the algorithm
prunes against — while leaving the rest of the paper alone.

## 60-second verification

The execution environment must first provision the declared base image
`harbor-claude-code-aggregated:1.3`. From this package directory, build both task
images from repository-relative contexts; no previously built D2D task image is
used:

```bash
docker build --no-cache \
  -f task/environment/Dockerfile \
  -t d2d-manuscript-actor:local \
  task/environment

docker build --no-cache \
  -f task/environment/Dockerfile.verifier \
  -t d2d-manuscript-verifier:local \
  task
```

The actor build compiles the supplied draft and fails if the declared LaTeX or
PDF toolchain is incomplete. A network-disabled runtime smoke check is:

```bash
docker run --rm --network=none d2d-manuscript-actor:local \
  /bin/sh -lc 'test -r /workspace/materials/D2D_conf.zip && command -v pdflatex'
```

Golden scoring is offline because the exact request-bound replay is in the
verifier image:

```bash
VERIFY_DIR="$(mktemp -d)"
mkdir -p "$VERIFY_DIR/verifier" "$VERIFY_DIR/artifacts"
docker run --rm --network=none \
  -v "$PWD/golden:/input/output:ro" \
  -v "$VERIFY_DIR/verifier:/logs/verifier" \
  -v "$VERIFY_DIR/artifacts:/logs/artifacts" \
  d2d-manuscript-verifier:local /input
cat "$VERIFY_DIR/verifier/reward_strict.txt"
cat "$VERIFY_DIR/verifier/reward_lenient.txt"
```

For an ordinary candidate, replace the Golden mount with a directory containing
`revised_manuscript.pdf` and supply the fresh judge environment:

```bash
docker run --rm \
  -e LLM_JUDGE_BASE_URL \
  -e LLM_JUDGE_API_KEY \
  -e LLM_JUDGE_MODEL="${LLM_JUDGE_MODEL:-gpt-5.6-sol}" \
  -e LLM_JUDGE_REASONING_EFFORT="${LLM_JUDGE_REASONING_EFFORT:-high}" \
  -v "$CANDIDATE_DIR:/input/output:ro" \
  -v "$VERIFY_DIR/verifier:/logs/verifier" \
  -v "$VERIFY_DIR/artifacts:/logs/artifacts" \
  d2d-manuscript-verifier:local /input
```

## Task authenticity

The runtime workspace holds the complete LaTeX sources of the draft: the
manuscript body, three EPS figures, the conference style file, and the compiled
draft PDF. The supplied draft anchors the research question, authors and
experimental figures. The reference preserves those sources and
propagates the corrected support bound into the proof and algorithm.

The candidate container carries a LaTeX toolchain. The image builds the
supplied draft once at build time, so a run that cannot produce a PDF has hit
its own problem rather than a missing dependency. The runtime skill teaches a
revision method — audit the model and proof, close the algorithm's state, keep
unaffected content and unsupported claims out — and names no quantity, symbol,
or conclusion from this manuscript.

## Scoring method

Scorer version `2.2.0`. The ten component weights sum to 1.00; the five
correction-chain components sum to 0.59. The evaluator checks actual reasoning,
current claims, algorithm updates and archived figure evidence. Discussion that
explicitly rejects the superseded bound is allowed regardless of mention count.
See [RUBRIC.md](RUBRIC.md) for every weight, deduction and lenient rule.
The with-skill and no-skill task definitions use the same instruction,
workspace, reference and byte-identical condition-blind scorer; only the runtime
skill mount differs.

Strict uses the bounded-additive zero-floor formula
`max(0, sum(weight * completion) - sum(triggered deduction values))`.
Lenient is an independent completeness gate: native delivery, every correction
component and every listed integrity item must be complete, while at least one
original algorithm mechanism must remain. Both formulas and their owner lists
are machine-owned by `task/tests/scoring_params.json`; the same summaries are
published in `dataset.toml`.

An evidence-bound LLM judge is required. It receives column-ordered candidate
text, rendered candidate pages and independently rendered archived figures.
Model, source, criteria, candidate and images bind the cache key. Missing service
or invalid evidence is an infrastructure failure; there is no keyword fallback.
Fresh calls use OpenAI Responses at `/v1/responses`, default model
`gpt-5.6-sol`, and default reasoning effort `high`. Missing or malformed fresh
service is `UNMEASURED`; no Chat Completions, Anthropic or keyword fallback is
part of the scoring path.

The private verifier package includes one exact request-bound Golden replay at
`task/tests/golden_replay`. Its binding combines request, Golden artifact and
rendered-evidence hashes and seals the response decision, validated review,
validation receipt and per-file manifest. It was produced by a fresh OpenAI
Responses `gpt-5.6-sol` adjudication; encrypted reasoning payloads are excluded.
No ordinary-candidate response or credential is included. A non-Golden
binding miss proceeds to the evaluator-owned cache or configured fresh provider;
without fresh configuration it is an infrastructure error. Actor images receive
only `task/environment`, so the private replay is not actor-visible.

## Directory and runtime

- `task/` contains the Harbor task, offline workspace, runtime skill, oracle
  reference, and validator.
- `golden/` contains the reference manuscript.
- `task/tests/golden_replay/` contains only the trusted, request-bound Golden replay fixture.

The two task conditions capture the actor deliverable from
`/workspace/output/revised_manuscript.pdf` and archive it as
`output/revised_manuscript.pdf`. The `[solution]` entry is separate: it points to
`task/solution/solve.sh` and its private `reference_manuscript.pdf` input for
oracle verification only. It is not the actor artifact path and is not copied by
the actor Dockerfile. Both conditions declare a `mixed` judge with continuous
reward and expose the same four verifier variables for the OpenAI Responses
endpoint, API key, model and reasoning effort.

The container is pinned in `task/environment/Dockerfile`. Scoring uses the
PyMuPDF 1.28.2 available in that pinned image and the configured semantic service in the verifier environment.
No private endpoint or credential is included. Current 2.2.0 non-Golden
validation requires fresh source-bound adjudication or an exact request-bound
evaluator cache.
