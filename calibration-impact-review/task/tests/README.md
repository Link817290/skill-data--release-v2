# Runtime evaluation

Use the declared private verifier image and `/tests/test.sh`. `/task/tests` is a
compatibility link for direct invocations. `VERIFIER_OUT`
selects an external results directory; an optional first argument selects the
submission directory. The default input is `/workspace/input` and the default
submission is `/workspace/output`.

The numerical stage is `verify_v2.py`. It reconstructs expected values before
candidate execution, checks all published fields and runs source-derived
metamorphic and invalid-input cases. Candidate execution requires the private root
verifier, which drops the candidate to UID 65534, strips judge variables and denies
IP sockets. Its private workspace copies are separate from the protected original
submission, issued inputs and grader files. Each call has a 60-second limit.

The semantic stage binds exact candidate/source quotations and assesses strict
quality separately from core completion. Configure `LLM_JUDGE_BASE_URL`,
`LLM_JUDGE_API_KEY` and optionally `LLM_JUDGE_MODEL`. An external
`LLM_JUDGE_CACHE_DIR` is indexed by the full Responses request hash. A cache hit works without
credentials; a miss requires the API. `SEMANTIC_REPLAY` can explicitly select an
archived response with its matching original manifest. Unavailable services,
missing runtime components or invalid replies are `UNMEASURED`, with no reward file.
