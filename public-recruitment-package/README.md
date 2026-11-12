# Public Recruitment Package

This package asks an agent to prepare four publication-ready Chinese files for an
anonymous financing-guarantee company: a recruitment notice, a two-role position
schedule, the supplied professional directory, and a minimal integrity commitment.
Candidate resumes are private background evidence. They must not become public policy,
and their identifiers must not remain in visible or hidden document surfaces.

The task tests source authority, professional-directory hierarchy, evidence-bounded
review of unlisted professions, process-stage binding, privacy minimization, and typed
attachment closure. The runtime skill describes the method without supplying an
employer-specific answer.

## Layout

```text
README.md
RUBRIC.md
dataset.toml
MANIFEST.json
golden/
task/
```

`golden/` contains the four reference files. `task/` contains the instruction,
offline workspace, skill, solution copy, deterministic file/structure scorer, semantic
judge, and the packaged Golden judge replay. Rollout records, calibration traces,
local metrics, and repro scripts are not release inputs.

## Verification

The verifier runs the deterministic checks and then the evidence-bound
`gpt-5.6-sol` judge. The judge uses the standard variables below and OpenAI Responses
API semantics:

```text
LLM_JUDGE_BASE_URL
LLM_JUDGE_API_KEY
LLM_JUDGE_MODEL=gpt-5.6-sol
LLM_JUDGE_CACHE_DIR
LLM_JUDGE_MODE=fresh|replay
LLM_JUDGE_TIMEOUT_SECONDS
```

For an offline Golden replay, use `LLM_JUDGE_MODE=replay`; the package contains the
request-bound response under `task/tests/golden_replay/`. A cold clone must build the
declared Harbor 1.3 actor and verifier images before running `task/tests/test.sh`.

Strict scoring is `max(0, positive earned - deduplicated independent harms)`. The
lenient lens is a binary hand-off diagnostic. Strict scores have no cap, target clamp,
or forced band. See [RUBRIC.md](RUBRIC.md) for professional reasons, equivalence
rules, partial credit, and deduction roots.
