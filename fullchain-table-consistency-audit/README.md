# Full-Chain Table Consistency Audit

The actor audits all 97 native tables and four paragraph-form pseudo tables in
the issued proposal, then writes output/table-consistency-audit.md in Chinese.
The report distinguishes confirmed inconsistencies, matters requiring author
confirmation, and checked-consistent differences.

Build from the package root:

~~~sh
docker build --target with-skill -t fullchain-table-consistency-audit:1.3 task/environment
docker build --target no-skill -t fullchain-table-consistency-audit-no-skill:1.3 task/environment
~~~

Run task/solution/solve.sh /path/to/workspace for the Oracle and
task/tests/test.sh /path/to/workspace in the verifier.

Deterministic checks own arithmetic, source values, locations, and the 101-entry
coverage ledger. The integrity gate rejects padding, source dumping, and
unfinished structures. Configure it with LLM_JUDGE_BASE_URL,
LLM_JUDGE_API_KEY, and optional LLM_JUDGE_MODEL. No endpoint or credential is
stored in the package.
