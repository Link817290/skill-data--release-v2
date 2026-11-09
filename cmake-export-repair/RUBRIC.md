# Scoring rules

The same deliverable is read by two independent lenses.

`reward_strict` is a continuous capability score. It is the weighted sum of the evidence-backed
reasoning atoms below, reduced to zero only when a required artifact, source integrity check, or
clean end-to-end validation gate fails.

`reward_lenient` is a binary delivery-completeness score, defined in its own section below. It is
computed from the submitted files alone and never from the strict result.

`reward` is a compatibility alias for `reward_strict`. Both lenses are implemented in
`task/tests/validator.py`. Native checks are deterministic. Reasoning requires the configured, evidence-bound semantic judge described below.

## Gates

The submitted workspace must contain the diagnosis, unified patch, report, and applied project
repair. The patch must reverse cleanly and stay within the build/package metadata files that own
the failures. The four protected implementation and public-header files must remain byte-for-byte
unchanged, the supplied failure-command evidence must remain byte-for-byte unchanged, and generated
build trees must not be left in the project. Reversing the patch from the submitted repaired tree
must reproduce the issued project snapshot; applying it again must reproduce the submitted tree.
Added patch lines must not contain conflict markers, machine-local absolute paths, or credentials.

Baseline runtime validation starts from a fresh producer copy, installs to the default staging
layout, copies the complete prefix, and deletes the original. The moved prefix must contain no
references to the old location. Independent CMake consumers must configure, build, and run against
both the shared core target and static utility target. A third consumer must compile and run using
only flags queried from the moved prefix's pkg-config metadata. Any artifact, integrity,
report-status, or baseline runtime gate failure makes the strict score zero. The captured
multi-component library layout is scored continuously in its own dimensions below.

## Strict capability dimensions

The positive score measures professional reasoning. Build and artifact checks are gates rather
than mechanical points.

### Baseline root-cause judgment: 30 points

- 5 points: separates downstream configure and link failures from producer compilation and
  identifies build/package metadata as the owning boundary.
- 7 points: explains why the absent static imported target becomes a raw linker item even though
  the producer installed an archive under a deliberately different output filename.
- 7 points: traces the moved-prefix CMake failure from generated import/config metadata back to
  absolute install destinations and explains relative-prefix reconstruction.
- 7 points: traces stale compiler/linker flags through the selected `.pc` files and identifies
  the configure-time prefix capture rather than treating successful pkg-config discovery as proof.
- 4 points: distinguishes CMake exports, CMake legacy config variables, and pkg-config files as
  separate generated contracts while ruling out implementation or ABI speculation.

### Baseline repair-boundary judgment: 15 points

- 5 points: exports both static targets so the utility target's transitive dependency is
  represented without changing public identifiers or archive output names.
- 5 points: uses relative CMake install destinations and a current-location-derived config prefix
  rather than patching generated import files or consumer paths.
- 5 points: makes both `.pc` templates derive their prefix from the installed metadata location,
  preserving build-system-selected library/include directory names and dependency declarations.

### Baseline evidence closure: 5 points

- 2 points: records a fresh producer build, staged install, removal of the original prefix, and
  moved-prefix shared/static CMake consumer results.
- 1.5 points: records the moved-prefix pkg-config default and `--static --libs` queries (including
  the private math dependency), compile, and executable result without an ambient fallback to the removed prefix.
- 1.5 points: states the limits of the smoke evidence instead of claiming general ABI, platform, or
  package-manager coverage.

### Layout-generalization judgment: 40 points

- 13 points: explains why a fixed parent-directory traversal that happens to fit the default
  `lib/pkgconfig` layout computes the wrong prefix for the captured multi-component library
  directory.
- 13 points: relates CMake legacy-variable reconstruction to the configured package destination and
  selected include directory, rather than assuming a fixed package-directory depth.
- 14 points: derives the `.pc` prefix relationship from the actual metadata install directory back
  to the package prefix while retaining the configured library and include directory names.

### Layout validation: 10 points

- 5 points: records and independently passes a fresh multi-component-layout install, removal of
  its original prefix, stale-metadata scan, legacy CMake include-variable check, static consumer
  build, and executable run.
- 5 points: records and independently passes the isolated moved-prefix pkg-config default and
  `--static --libs` queries, consumer compile, and executable run for that same layout.

Equivalent technical wording, equivalent CMake quoting/argument layout, and normalized
pkg-config field spelling and whitespace are accepted. Strict validation evidence uses the
published scenario names so every required consumer path can be bound to its own command and
outcome; the lenient lens accepts its documented family of equivalent command/result field names. The verifier values
cross-stage relations and independently reruns every claimed consumer path; a keyword stub or
fragment inventory cannot earn reasoning credit, and a fabricated report cannot earn validation
credit.

Report exit codes are interpreted with command semantics. Zero is success by default. A nonzero
code is accepted only when the same step declares a matching `expected_exit*`, or for the standard
negative search assertion where `grep`/`rg` returns exactly 1 and the step explicitly explains that
no matches are the passing outcome. Search execution errors (2+), unexpected compiler/build
failures, and an outer pass hiding a nested failure remain failures. Equivalent aggregate result
layouts, including an all-pass `final_validation` list, are accepted.

## Lenient completion score

`reward_lenient` answers a different question with a different method: did a usable handoff
arrive at all? It is `1.0` when every one of the following holds and `0.0` otherwise.

- The diagnosis, the unified patch, and the report all exist as files, and the project directory
  still carries its build definition so the applied repair can be inspected.
- The diagnosis opens as a text document with at least one nonempty body line. Markdown headings
  are accepted but are not required.
- The patch has the shape of a unified diff: an old/new file header pair, a hunk header, and at
  least one changed line inside that hunk.
- The report parses as a JSON object.
- The report records the commands it ran, under any field named for commands or invocations.
- The report records a successful, internally consistent outcome, under supported status/result/
  exit-code structures. A failed or contradictory validation is not a completed repair.
- The fresh baseline producer and independent moved-prefix consumers pass. This native minimum is
  shared with strict's baseline gate; lenient does not require the additional weighted reasoning
  or multi-component-layout dimensions.

The lenient lens reads the submitted handoff structure and recorded result, and uses the same
fresh baseline native validation as strict. It does not inspect diagnosis meaning, compare against
a reference repair, or require the weighted multi-component-layout and semantic dimensions. An
honest failed report is useful diagnostic evidence but is not a completed repair and scores `0.0`;
a handoff whose deliverable files were created and left empty also scores `0.0`.
The two lenses share no formula, no weight, and no scalar; either can be satisfied without the
other, and a submission can carry positive strict credit while failing the lenient contract, or
satisfy the lenient contract with no strict credit at all.

Passing is defined by the lenient result only, as `pass_rate = mean(reward_lenient)`. There is no
threshold anywhere in the strict score.

## Causal reasoning adjudication

D1–D5, P1–P3, E3 and L1–L3 require an evidence-bound semantic verdict using only semantic_source.json and the submitted diagnosis/report. Co-occurrence of keywords and paragraph or punctuation counts do not earn credit. Equivalent concise causal explanations and valid alternative repairs are accepted. Patch integrity, preserved source bytes and fresh native build/install/relocation/consumer tests remain deterministic hard gates; the judge cannot override them. E1/E2/V1/V2 retain their executed-evidence checks.

The evaluator (not the candidate) must configure `LLM_JUDGE_BASE_URL`, `LLM_JUDGE_API_KEY`, `LLM_JUDGE_MODEL`, `LLM_JUDGE_CACHE_DIR`, `LLM_JUDGE_MODE`, and `LLM_JUDGE_TIMEOUT_SECONDS`; `LLM_JUDGE_REASONING_EFFORT` is optional. The only production protocol is the OpenAI Responses API at `/v1/responses`, with default model `gpt-5.6-sol`. No credentials/endpoints are packaged. Unconfigured or failed adjudication is an explicit infrastructure error. Verdict fractions are schema-checked and every credited criterion requires an exact candidate quotation. Cache keys include the model, complete rubric, source and candidate; no universal cached score is accepted. Lenient remains a delivery-completeness lens.

## Evidence layers and UNMEASURED boundary

The verifier keeps three evidence layers distinct:

- Structural evidence parses the submitted artifact shape, unified patch, CMake target/export
  relations, pkg-config fields, protected source hashes, and report structure.
- Reproduction evidence comes from fresh producer configure/build/install runs, removal of the
  original prefix, metadata scans, and independent CMake and pkg-config consumer executions. E1
  and E2 cover the default-layout CMake and pkg-config paths. V1 and V2 alone carry the additional
  multi-component-library-layout credit.
- Semantic evidence supplies D1-D5, P1-P3, E3, and L1-L3 through source-bound criteria with exact
  candidate quotations. It cannot override a failed structural or reproduction gate.

A missing CMake/pkg-config toolchain, missing semantic endpoint or credential, transport failure,
invalid semantic response, or invalid bound cache is verifier infrastructure failure. The whole
evaluation is then `UNMEASURED`: `reward`, `reward_strict`, and `reward_lenient` are all JSON `null`,
and no candidate reward or pass-rate observation is published. The verifier may retain the seven
delivery checks as an internal `candidate_delivery_diagnostic`, but its `complete` flag is not a
reward. Candidate-caused missing/malformed artifacts, failed builds, failed consumers, report
contradictions, and incomplete required steps remain measured failures when the evaluation chain
is available; they are not infrastructure errors.
