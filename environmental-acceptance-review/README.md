# Environmental Acceptance Review

The task produces an annotated review draft and a supplementary opinion from the
issued environmental-acceptance dossier. The actor must preserve source text,
attach native comments to real anchors, and separate confirmed facts from open
evidence gaps.

Build from the package root:

~~~sh
docker build --target with-skill -t environmental-acceptance-review:1.3 task/environment
docker build --target no-skill -t environmental-acceptance-review-no-skill:1.3 task/environment
docker build -f task/environment/Dockerfile.verifier -t environmental-acceptance-review-verifier:1.3 .
~~~

Run task/solution/solve.sh /path/to/output for the Oracle. The scorer is
task/tests/test.sh. Fresh source-bound semantic review uses LLM_JUDGE_BASE_URL,
LLM_JUDGE_API_KEY, and optional LLM_JUDGE_MODEL. Request-bound Golden replay
cannot score a changed artifact.
