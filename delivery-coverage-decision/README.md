# Delivery Coverage Decision

This package evaluates an evidence-grounded delivery-network investment decision.
The actor receives only task/environment/workspace and, in the with-skill
condition, task/environment/skills.

Build from the package root:

~~~sh
docker build --target with-skill -t delivery-coverage-decision:1.3 task/environment
docker build --target no-skill -t delivery-coverage-decision-no-skill:1.3 task/environment
docker build -f task/environment/Dockerfile.verifier -t delivery-coverage-decision-verifier:1.3 .
~~~

The actor writes output/analysis.xlsx, exactly one decision report, and
reproducible files under output/calculations/. Run task/solution/solve.sh to
materialize the Oracle. Run task/tests/test.sh in the verifier.

Fresh semantic scoring uses the OpenAI Responses API configured with
LLM_JUDGE_BASE_URL, LLM_JUDGE_API_KEY, and optional LLM_JUDGE_MODEL. Exact
Golden replay is request-bound; changed artifacts require a fresh call.
Infrastructure failures are UNMEASURED, never candidate zero.
