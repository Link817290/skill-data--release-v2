# Garbage Transport Jurisdiction

The task produces one court-facing jurisdiction filing and two property-manager
evidence requests. The documents must preserve the distinction between the
Jiangnan origin evidence, the Qingxiu property facts, and an unverified
destination.

Build from the package root:

~~~sh
docker build --target with-skill -t garbage-transport-jurisdiction:1.3 task/environment
docker build --target no-skill -t garbage-transport-jurisdiction-no-skill:1.3 task/environment
docker build -f task/environment/Dockerfile.verifier -t garbage-transport-jurisdiction-verifier:1.3 .
~~~

Run task/solution/solve.sh with AGENT_WORKSPACE set to the target workspace.
Run task/tests/test.sh in the verifier. File structure is deterministic;
jurisdiction meaning, factual status, polarity, and object/scope binding are
source-bound semantic owners configured through LLM_JUDGE_BASE_URL,
LLM_JUDGE_API_KEY, and optional LLM_JUDGE_MODEL.
