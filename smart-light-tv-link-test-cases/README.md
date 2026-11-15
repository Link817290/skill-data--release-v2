# Smart light and TV link test cases

This package evaluates a source-grounded test plan for smart-light and TV linkage behavior. The task material is copied into the actor workspace by `task/environment/Dockerfile`; scoring runs through `task/tests/test.sh` and the verifier entrypoint. The Golden workbook is the exact reference candidate.

The deterministic layer checks workbook shape, source-file integrity, units, limits and executable relationships. Open wording, equivalent professional expressions, negation and adopted-versus-pending status are adjudicated by the single source-bound `gpt-5.6-sol` judge in `task/tests/mix_judge/semantic_live.py`; a keyword or co-occurrence is not a semantic verdict. Set `LLM_JUDGE_MODE=fresh` with the OpenAI-compatible `LLM_JUDGE_BASE_URL` and `LLM_JUDGE_API_KEY` for an unseen artifact. `LLM_JUDGE_MODE=replay` accepts only the request-bound Golden replay under `task/tests/mix_judge/cache/live/`.

The verifier reports `semantic_unmeasured` when an explicitly requested fresh/replay judge is unavailable. It does not turn a judge or source-material failure into a candidate zero. The source manifest is resolved from the mounted workspace in both host and verifier layouts.

Build the actor and verifier from the package root with the supplied Dockerfiles. The package contains no rollout history, evaluator logs, credentials, or local score artifacts.
