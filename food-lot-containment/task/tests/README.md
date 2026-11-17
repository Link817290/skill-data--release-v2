# Evaluation

The public instruction lists three CSV registers, one trade-recall-notice.docx or .pdf, and preparation/. Numeric checks read all register rows using input/register-fields.csv. Run `python tests/verify.py --submission-dir DIR --input INPUT --report EXTERNAL_JSON` for numerical diagnostics only.

The complete entry is `python tests/evaluate.py --submission-dir DIR --input INPUT --out EXTERNAL_EMPTY_DIR`. It calls the text-only LLM Judge after numerical verification. Set LLM_JUDGE_BASE_URL and LLM_JUDGE_API_KEY; credentials are never bundled. Replay is restricted to the identical evidence request and does not count as a fresh model call. Final measurement applies the documented local-chain settlement to the seven atomic decisions; it has no global power transform. Both components are required. No appearance score applies.
