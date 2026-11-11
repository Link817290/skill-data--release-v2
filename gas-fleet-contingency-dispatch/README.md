# Gas Fleet Contingency Dispatch

The actor produces dispatch_review.json, dispatch_trace.csv, and
dispatch_model.py from the two immutable source records. The program must
reproduce the artifacts from a clean workspace and react to a controlled source
change.

Build from the package root:

~~~sh
docker build --target with-skill -t gas-fleet-contingency-dispatch:1.3 task/environment
docker build --target no-skill -t gas-fleet-contingency-dispatch-no-skill:1.3 task/environment
~~~

Run task/solution/solve.sh for the Oracle and task/tests/test.sh in the verifier.
Program checks independently recompute source binding, bounds, balances, metrics,
and replay behavior. Limitations and conditional-decision meaning use a
source-bound judge configured with LLM_JUDGE_BASE_URL, LLM_JUDGE_API_KEY, and
optional LLM_JUDGE_MODEL.
