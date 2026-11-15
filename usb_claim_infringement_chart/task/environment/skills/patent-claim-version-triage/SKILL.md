---
name: patent-claim-version-triage
description: Orchestrate an evidence-limited patent claim-version triage from original application, issued-claim, product, and technical-reference records through a complete machine-readable claim chart. Use immediately when one deliverable combines claim dependency auditing, cross-version lineage, target comparison, evidence bridges, construction sensitivity, and artifact closure.
---

# Patent claim-version triage orchestration

## Start here

Use this skill as the entry point for a multi-stage claim-version chart. Its job is
to keep the stages ordered and their handoffs explicit. Its four specialist
references contain no conclusions about a particular patent, target, or
protocol; read each one only at its actual decision point.

At the beginning, read the task's output contract and inspect the supplied source
files. Run the bundled answer-blind initializer **against a working draft path,
never the deliverable path**:

```bash
python3 scripts/init_claim_artifact.py CONTRACT.json WORKING_DRAFT.json
```

The script creates only contract-declared identifiers and blank fields, including
blank finding slots for published elements already enumerated by the contract.
It supplies no evidence classification, version mapping, issued feature set, or
conclusion, and refuses to overwrite an existing artifact. Keep that draft
parseable while work proceeds. An interrupted run should retain completed
analytical work in the draft, not end with no file.

The initialized draft is scaffolding, not an answer: every adjudication field in
it is null. Writing it to the deliverable path produces a file that looks
complete and decides nothing. The deliverable is written only by the compiler
below, and only once decisions exist. If you hand work to sub-agents, confirm the
compiled deliverable exists and carries those decisions before you finish — a run
that ends with only the draft has produced nothing.

Use the bundled compiler to make every completed decision durable without
hand-writing expanded finding objects:

```bash
python3 scripts/compile_claim_decisions.py CONTRACT.json DECISIONS.json OUTPUT.json
```

`DECISIONS.json` is an analyst-owned compact working file. Its optional
collections are `published`, `issued`, `same_number`, `bridges`, `construction`,
`sensitivity`, `dependencies`, `family`, and `assumptions_and_scope`. Key
published and issued rows as `TARGET::CLAIM`; give each a `call`, a `classes`
map keyed by feature, shared citation and analysis fields, and optional
`finding_overrides`. Issued rows also supply their independently derived
`feature_refs`. Other collections accept objects keyed by the identifier shown
in the output contract and contain the contract's row fields. The compiler only
expands those supplied judgments; omitted fields remain blank.

Compile after each substantive register closes. Do this before opening a new
class of technical sources, so evidence review cannot consume the run while all
completed claim work remains only in transient notes.

Do not open all four references merely to acknowledge their existence.

## Stage 1: freeze claims and version relationships

Read `references/claim-version-control.md` before comparing any target. Apply it
to:

- identify each claim set and keep version keys distinct;
- audit printed dependency edges before expanding them;
- normalize stable semantic features;
- trace same-number lineage and whole-family subject-matter movement;
- separate a non-controlling correction candidate from the printed dependency;
- materialize the complete later-version feature set for every destination used.

Write the version, dependency, and family-correspondence registers to the compact
decision map, compile the artifact, and reopen it before proceeding. If a printed
chain is broken, preserve that result; semantic correspondence does not authorize
repair.

## Stage 2: compare claims to evidence

Read `references/claim-chart-method.md` once the controlling feature sets are
frozen. Use it to build the source ledger, bind every record to its exact target
and mode, and test actor, message content, signaling path, and event order
independently.

Close one target/claim pair at a time and save after each target. Keep direct
disclosure, valid composite inference, silence, and incompatibility distinct.
Never borrow a component, design, standard, or patent example across targets
without first establishing the target-specific bridge.

## Stage 3: audit bridges and sensitivity

Read `references/claim-construction-sensitivity.md` when a proposed result
depends on mapping technical terminology or combining a target record with an
external rule. Build the bridge, construction-dependency, and sensitivity
registers from the same feature ledger used for the chart.

Change one sensitivity premise at a time, recompute the all-elements result, and
retain every unrelated open feature. Save and parse the artifact after completing
these advisory registers.

## Stage 4: close the artifact

Read `references/claim-chart-quality.md` only after the substantive registers
exist. Run its coverage, nested-feature, source-key, rollup, and saved-file
checks. Use `scripts/matrix_lint.py` for matrix-shaped collections, then manually
check the analytical questions the linter cannot decide.

Before finishing, verify:

- every requested axis and selected pair has exactly one row;
- each later claim is expanded through its own version;
- each family destination includes its full inherited later feature set;
- every composite finding exposes both premises;
- every open terminal result has a decisive open feature;
- every favorable result has all required features supported;
- the file at the required path parses after the last write.

## Handoff discipline

Keep a short working register of completed stages and unresolved items. A later
stage may send an item back for revision, but it must not silently overwrite the
claim version, target identity, dependency status, or baseline comparison fixed by
an earlier stage. Re-run the affected closure checks after any revision.

If execution time is constrained, preserve a valid artifact with honest unresolved
judgments and complete identifiers. Do not spend the entire run perfecting prose
while the required file remains absent.
