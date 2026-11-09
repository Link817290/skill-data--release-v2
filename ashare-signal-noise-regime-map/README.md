# A-share Signal and Noise Regime Map

Read the supplied market snapshots, event table and indicator dictionary. Submit
`/workspace/regime_map.xlsx` containing all 100 samples, their regimes, actions,
evidence changes, contradiction/review flags and rationale.

## Package

`task/instruction.md` defines the delivery contract. Original CSVs and the template
are under `task/environment/workspace/`; skills are under
`task/environment/skills/`. `golden/regime_map.xlsx` is the authored reference.
`RUBRIC.md` defines the current strict and lenient criteria.

## Environment

Build from the package root:

```sh
docker build --target with-skill -t ashare-actor-with-skill:1.0 task/environment
docker build --target no-skill -t ashare-actor-no-skill:1.0 task/environment
docker build -t ashare-private-verifier:1.0 -f task/environment/Dockerfile.verifier .
```

The image uses `harbor-claude-code-aggregated:1.3` and Python 3.11.2. The Oracle
and workbook reader use the Python standard library. Actors run as UID 20005 on
`environment.network_mode = "no-network"`. Only the with-skill image contains
`/skills`, registered with `environment.skills_dir`; the no-skill image contains
no task skills. Actor images contain no Golden, solution code, tests or credentials.

Both configurations use a separate private verifier with a `public` network and
root execution. Its image bakes `/tests`, `/instruction.md`, and trusted issued
inputs. Build assertions check source hashes and agreement of the scorer's source
facts with the issued CSVs. Harbor transfers `/workspace/regime_map.xlsx` to that
verifier. `verifier.env` explicitly forwards the external API endpoint, key and
model only during verification. Direct reproduction uses `--network none` for
actors and `--user root --network bridge` for the verifier.

## Oracle

```sh
sh /solution/solve.sh --workspace /workspace
```

In a container, the default workspace is `/workspace`. The Oracle generates
`regime_map.xlsx` from the original CSVs and uses the evaluator's `workbook.py`
helper, packaged at `task/solution/workbook.py` with identical bytes to the general
reader/writer in tests. Harbor uploads the entire private solution directory for
Oracle execution. For direct trusted Oracle reproduction, mount only `task/solution`
at `/solution:ro`; do not mount `/tests` or the full package. The helper contains
no sample labels or scoring decisions. Neither helper nor Oracle is baked into
ordinary actor images. The checked-in Golden is not an input to generation.

## Evaluation

```sh
bash /tests/test.sh /workspace/regime_map.xlsx
```

Configure `LLM_JUDGE_BASE_URL`, `LLM_JUDGE_API_KEY` and optionally
`LLM_JUDGE_MODEL` (default `gpt-5.6-sol`) externally. Fresh evaluation requires
verifier-side API access. Mount the candidate read-only at `/workspace/regime_map.xlsx`
and writable logs at `/logs` in the private verifier. `LLM_JUDGE_CACHE_DIR`
optionally points to an external request-bound cache. Requests use the OpenAI
Responses API with `stream:false`; the parser also rejects incomplete event-stream
responses defensively. The private tests ship one
Golden-only replay group at `task/tests/golden_replay`: it is bound to the exact
Golden artifact, the trusted source-evidence file set and all three semantic
request hashes, and seals request metadata, raw fixture envelopes, validated
reviews, validation receipts and a per-file manifest. Provenance explicitly
identifies a deterministic source-contract fixture and does not claim production
model calls. No non-Golden candidate reply or credential is included. Any
non-Golden artifact misses this group and proceeds to
evaluator-owned replay or fresh judgment; without fresh configuration it is
UNMEASURED. Actor images contain only environment context and cannot read the
private tests or replay.

The evaluator checks the output contract, source identifiers and canonical enum
compatibility deterministically. Source-bound LLM decisions assess semantic
support and professional equivalents. A fully source-recomputable panel can earn
positive mathematical certification only after independent semantic admission of
its actual method, source claims and unknown enum meanings. Other panels use the
per-sample semantic path; absence of that sufficient certificate is not a deduction.
A coherent alternative calibration can receive full credit; original facts,
required fields and professional rules remain binding.

Strict averages weighted row credit bounded by the row's final-decision and
professional temporal-rule credit. Semantic blocks follow source chronology and
carry the preceding source review across block boundaries; independent workbooks
can run concurrently. Disclosed compatible calibrations also receive deterministic
evidence-set, flag and impossible-transition checks. Lenient independently checks whole-map
substantive completion without requiring every strict quality item to be perfect,
or using hidden reference-overlap or score thresholds.
The three substantive owners (decision, transition and evidence) are equally weighted;
the two control flags share the smaller remaining weight. Missing, partially completed
and unsupported work are distinguished, and one underlying error is not multiplied by
repeated wording. `RUBRIC.md` gives the owner boundaries and dependency rationale.
`reward.txt` mirrors strict; `reward_strict.txt`, `reward_lenient.txt` and
`reward_detail.json` expose the formal results. Oracle and Golden are validated
through this same entrypoint. Missing submissions score zero;
unavailable or invalid judgment returns an infrastructure error.
