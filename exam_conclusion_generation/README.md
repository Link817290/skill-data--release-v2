# Physical-Exam Conclusion Reconstruction

The actor reads 1,148 de-identified detail rows for ten cases and produces
体检总检结论.xlsx with the required conclusion and case-summary sheets. Every
conclusion cites at least one source row from the same case. Source rows are
authoritative; the evaluator reference is a reconstruction aid, not an
unprovided doctor review.

Build from the package root:

~~~sh
docker build --target with-skill -t exam-conclusion-generation:1.3 task/environment
docker build --target no-skill -t exam-conclusion-generation-no-skill:1.3 task/environment
~~~

Run task/solution/solve.sh with AGENT_WORKSPACE set to a copy of the issued
workspace. Run task/tests/test.sh in the verifier.

Strict scoring separates finding identification, medically supported terminology,
and material qualifier fidelity. Equivalent expressions use an evidence-bound
semantic judge configured by LLM_JUDGE_BASE_URL, LLM_JUDGE_API_KEY, and
optional LLM_JUDGE_MODEL. Measurements and descriptive evidence need not be
repeated in the concise conclusion-name column.
