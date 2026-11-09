# Native build repair package

This package evaluates evidence-based diagnosis and repair of an installed native-library interface. The runtime task, source materials, verifier, and workflow are kept in their respective directories; the package does not require network access.

Semantic adjudication is required through the OpenAI Responses API; configure `LLM_JUDGE_BASE_URL`, `LLM_JUDGE_API_KEY`, `LLM_JUDGE_MODEL`, `LLM_JUDGE_CACHE_DIR`, `LLM_JUDGE_MODE`, and `LLM_JUDGE_TIMEOUT_SECONDS` in the verifier environment. The default model is gpt-5.6-sol. See RUBRIC.md. No private endpoint or credential is included.

`golden/golden_replay/` contains the current Golden diagnosis/report's exact request-bound semantic replay: artifact/evidence/request hashes, the raw 12-item response, validated 16-atom/native evidence, review, and a file manifest. The directory is outside `task/` and is not actor-visible. Any diagnosis or report change produces a cache miss and requires fresh semantic review.

Build the offline actor/verifier toolchain from the repository root:

```sh
docker build --network none -t cmake-export-repair:local \
  -f task/environment/Dockerfile task/environment
```

The same image supplies the native verifier toolchain. Tests and Golden replay are verifier-only mounts. This disconnected Golden check must report strict and lenient `1.0`:

```sh
logs="$(mktemp -d)"
docker run --rm --network none \
  -e LLM_JUDGE_BASE_URL=http://127.0.0.1:9 \
  -e LLM_JUDGE_API_KEY=replay-only -e LLM_JUDGE_MODEL=gpt-5.6-sol \
  -e LLM_JUDGE_CACHE_DIR=/golden-replay -e LLM_JUDGE_MODE=replay \
  -v "$PWD/task/tests:/tests:ro" -v "$PWD/golden:/workspace:ro" \
  -v "$PWD/golden/golden_replay:/golden-replay:ro" -v "$logs:/logs" \
  cmake-export-repair:local python3 /tests/validator.py /workspace --out /logs
```
