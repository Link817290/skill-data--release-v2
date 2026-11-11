# Equipment Changeover

The task prepares a Chinese operating instruction for a label-printer
changeover. It must resolve station capabilities, width and pressure settings,
consumables, setup state, exception handling, and first-article release.

Build from the package root:

~~~sh
docker build --target with-skill -t equipment-changeover:1.3 task/environment
docker build --target no-skill -t equipment-changeover-no-skill:1.3 task/environment
docker build -f task/environment/Dockerfile.verifier -t equipment-changeover-verifier:1.3 .
~~~

Run task/solution/solve.sh /path/to/output for the Oracle and task/tests/test.sh
in the verifier. Open professional meaning and equivalent Chinese expression use
a source-bound LLM judge configured through LLM_JUDGE_BASE_URL,
LLM_JUDGE_API_KEY, and optional LLM_JUDGE_MODEL. Numeric settings and file
structure remain deterministic.
