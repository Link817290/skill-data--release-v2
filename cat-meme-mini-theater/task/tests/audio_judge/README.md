# Original Role Voices

`judge.mjs` extracts waveform correspondence from the actual film and five
source-derived role references, then invokes `judge.py` with actual frames,
source/film intervals and indexed candidate routing code. No private synthetic
effect is required. Dependencies are declared in the verifier Dockerfile.

```sh
node tests/audio_judge/judge.mjs --mode fresh --refresh --artifact OUTPUT --output LOGS/audio --cache-dir EXTERNAL_CACHE
node tests/audio_judge/judge.mjs --mode replay --artifact OUTPUT --output LOGS/audio --cache-dir EXTERNAL_CACHE
```

Fresh mode requires externally supplied `LLM_JUDGE_BASE_URL`, `LLM_JUDGE_API_KEY`
and optionally `LLM_JUDGE_MODEL`. Replay validates the exact artifact/source/
runtime binding and cached response integrity and performs no API call. Provider
caches are external evaluator data and do not ship in this package.

Source identity, meaningful original vocal performance, and narrative placement
are separately evidenced semantic facts. The model cannot assign a reward.
Actual qualified waveform candidates establish correspondence; source citations
and actual film frames establish routing and narrative claims. Unresolved facts
stay null. No hearing claim is made. A low energy-coverage fraction, different
crop length, silence removal or gain normalization alone cannot establish harm.
Unique source-energy coverage is diagnostic only. Replacing a role voice,
cutting away a key original expression, or using it on the wrong emotional/story
beat loses that role's credit. Designed effects and music are judged separately.
