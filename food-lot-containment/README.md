# Food Lot Containment

The actor reconciles four issued notices into three CSV registers, an actionable
trade notice, and a reproducible preparation directory. Product identity,
amendments, named relationships, notice-level scope, and closure limits remain
distinct.

Build from the package root:

~~~sh
docker build --target with-skill -t food-lot-containment:1.3 task/environment
docker build --target no-skill -t food-lot-containment-no-skill:1.3 task/environment
docker build -f task/environment/Dockerfile.verifier -t food-lot-containment-verifier:1.3 .
~~~

Run task/solution/solve.sh /path/to/output for the Oracle. The formal scorer is
task/tests/test.sh. Fresh semantic scoring uses LLM_JUDGE_BASE_URL,
LLM_JUDGE_API_KEY, and optional LLM_JUDGE_MODEL. Source-supported notice-level
channel rows are reviewed semantically rather than by a channel keyword list.
