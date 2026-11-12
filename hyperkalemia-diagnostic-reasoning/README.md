# Hyperkalemia Diagnostic Reasoning

This benchmark asks the agent to read three issued Chinese clinical-record images and produce four editable Word documents:

- `hyperkalemia_reasoning_template.docx`
- `CASE-001_reasoning.docx`
- `CASE-002_reasoning.docx`
- `CASE-003_reasoning.docx`

The with-skill condition receives `clinical-diagnostic-reasoning-handbook`; the no-skill condition receives the same instruction and source images without the skill. The actor image contains neither Golden files nor evaluator code.

## Runtime

The actor image derives from `harbor-claude-code-aggregated:1.3` and runs offline. The same image and source workspace are used for both conditions; only the skill mount differs.

The verifier combines deterministic Golden-derived source-fact checks with a condition-blind semantic comparison of the submitted and Golden DOCX portfolios. Golden uses the single hash-bound replay record in `task/tests/golden_replay`. A new submission requires an OpenAI-compatible Responses endpoint configured with `LLM_JUDGE_BASE_URL` and `LLM_JUDGE_API_KEY`; `LLM_JUDGE_MODEL` defaults to `gpt-5.6-sol`. Missing judge infrastructure is reported as an evaluator error and never converted to a business score of zero.

Run the verifier in its standard container layout with:

```sh
bash /task/tests/test.sh /workspace/output
```

The verifier writes `reward.json`, `reward_strict.txt`, `reward_lenient.txt`, and the auditable component detail to `VERIFIER_OUTPUT_DIR` (default `/logs/verifier`).
