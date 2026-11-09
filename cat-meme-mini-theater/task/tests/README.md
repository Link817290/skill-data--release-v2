# Production Verifier

Run `bash tests/test.sh /workspace` in the declared separate verifier image.
The candidate is `/workspace/output`; `--artifact PATH` is a trusted harness
override. The pipeline decodes actual media, renders the actual project in a
credential-free subprocess, compares source/video/audio correspondence, obtains
source/candidate-bound visual and role-audio judgments, checks intentional
soundtrack design, and applies `scoring_params.json`.

Fresh is the default. Supply `LLM_JUDGE_BASE_URL`, `LLM_JUDGE_API_KEY`, and
optionally `LLM_JUDGE_MODEL` in the trusted verifier environment. The endpoint
must support Responses with images and structured output. The default model is
`gpt-5.6-sol`. The base URL is normalized to the `/v1/responses` route before
any provider call. These credentials
never belong in actor images or source projects.

Fresh visual, role-audio, and soundtrack components make at most four calls when
a provider response fails the existing schema or evidence validation. Every call
uses the same artifact/source/runtime binding and is retained as a separate
verifier-owned record. Only a fully validated response updates `selected.json`;
retrying never relaxes citations, frame IDs, source identity, or other evidence.

`LLM_JUDGE_CACHE_DIR` defaults to `/tests/golden_replay`. Its release
`visual`, `audio`, `audio-resolution`, `ownership`, and `soundtrack` subdirectories
hold provider records bound to actual artifact, source, policy, and runtime
identities. `LLM_JUDGE_MODE=replay` accepts only the bundled exact Golden binding;
new artifacts require fresh evaluation. Ordinary candidate caches are not shipped. Replay
performs no provider calls and can run with networking disabled. Cache misses
and invalid/incomplete replies exit nonzero, clear stale numeric rewards, and
write `reward_detail.json` with an unmeasured diagnostic.

Successful `reward.json` has only numeric `strict` and `lenient` keys.
`reward_detail.json` records the independent checks, evidence, and settlement.
The runtime dependencies are at `/opt/remotion-runtime/node_modules`. A trusted
`--rerender-proof` can reuse a verifier-owned proof bound to the actual source
project and actual rendered output; ordinary grading performs the render.

Visual evidence includes every half-second overview sample and separately
sampled dense motion windows; source contact sheets retain every supplied media
preview. Contact sheets group images to respect provider budgets without
discarding temporal evidence. Source role voices are matched to the issued
originals, not private synthetic effects. Effects and music design are evaluated
semantically with decoded mix measurements and actual project evidence.
