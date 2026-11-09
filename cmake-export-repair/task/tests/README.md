
Causal reasoning adjudication (batch 02)

D1–D5, P1–P3, E3 and L1–L3 require an evidence-bound semantic verdict using only semantic_source.json and the submitted diagnosis/report. Co-occurrence of keywords and paragraph or punctuation counts do not earn credit. Equivalent concise causal explanations and valid alternative repairs are accepted. Patch integrity, preserved source bytes and fresh native build/install/relocation/consumer tests remain deterministic hard gates; the judge cannot override them. E1/E2/V1/V2 retain their executed-evidence checks.

The evaluator (not the candidate) configures `LLM_JUDGE_BASE_URL`, `LLM_JUDGE_API_KEY`, `LLM_JUDGE_MODEL`, `LLM_JUDGE_CACHE_DIR`, `LLM_JUDGE_MODE`, and `LLM_JUDGE_TIMEOUT_SECONDS`; `LLM_JUDGE_REASONING_EFFORT` is optional. The production judge uses only OpenAI Responses `/v1/responses`, defaulting to `gpt-5.6-sol`. No credentials/endpoints are packaged. Unconfigured or failed adjudication is an explicit infrastructure error. Verdict fractions are schema-checked and every credited criterion requires an exact candidate quotation. Cache keys include the model, complete rubric, source and candidate; no universal cached score is accepted. Lenient remains a delivery-completeness lens.

The original package contained commands, not historical stdout/stderr. Fresh reproductions are labelled as such and do not purport to recover missing historical logs.
