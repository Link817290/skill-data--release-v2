---
name: reconcile-spontaneous-reports
description: Build reproducible case-level universes from versioned spontaneous-report exports. Use when safety reports arrive as quarterly relational tables with follow-ups, report identifiers, case identifiers, child records, or sensitivity analyses that intentionally retain every submitted version.
---

# Reconcile spontaneous reports

Create the population ledger before calculating any safety statistic. A report version is a submission state; it is not another patient and it is not automatically another independent case.

This method is independent of local filenames and output schema. First map the available fields to case identity, report identity, version order, receipt timing, and child-table roles; stop if any required role cannot be established.

## Freeze the population contract

Write a short internal contract containing:

- included extracts and the union or partition they represent;
- the case identifier, report-version identifier, and version ordering field;
- deterministic tie-break fields;
- whether the target is a latest-case universe, an as-received version universe, or both;
- the child-table inclusion rule;
- every subgroup definition and its missing-value bucket.

Keep distinct universes as separate named sets. Never overwrite the canonical latest-case set while preparing a deliberately naive or as-received sensitivity set.

## Select canonical versions

Pool all included demographic or case-header rows before deduplication. For each case:

1. Compare version numbers numerically, not lexically.
2. Retain the greatest version.
3. Break a same-version tie using the latest available regulatory receipt date.
4. Apply a stable report-identifier tie-break only if the first two keys still tie.
5. Record the selected report identifier and every rejected version identifier.

Do not assume the later file contains the later version. Do not deduplicate separately inside each quarter and then concatenate. Do not deduplicate on the report identifier, because report identifiers distinguish the very versions that need reconciliation.

If a tie cannot be resolved under the declared contract, stop and expose the ambiguity. Choosing whichever row happens to be last makes the result depend on file order.

## Filter child tables through the ledger

Build a set of retained report identifiers and semi-join every child table to it. Joining child rows by case identifier alone can pull an earlier version's drug or reaction state into the retained version.

After each semi-join, verify:

- every retained child row maps to exactly one retained report;
- no rejected report identifier remains;
- every retained case header remains unique;
- child rows absent from a case are represented as missing information, not a negative fact.

Keep the ledger immutable. Derive case-level drug, event, outcome, and therapy sets from it without adding columns back to the source files.

## Construct comparison universes without contamination

When a task requests an all-version sensitivity, use each report identifier as a separate observation only in that sensitivity. Do not call it case-level and do not merge its counts with canonical counts.

When a task requests source-period strata from the canonical universe, assign each retained case to the period printed on its retained header row. Those strata must partition the canonical universe: their sizes sum to the canonical size and no case appears twice.

This differs from building one latest-case snapshot inside each source period. Per-period snapshots can contain the same case in more than one period and therefore cannot be pooled as independent strata without an explicit repeated-case design.

For demographic or reporter subgroups, assign exactly one bucket per retained case. Preserve an other-or-missing bucket instead of silently dropping unclassified reports.

## Audit version impact

Maintain a version ledger with the case identifier, selected report identifier, rejected report identifiers, selected period, and selection rank. Use it to explain why canonical and all-version results differ.

Pre-index relational state before scanning candidate-case combinations. Build `versions_by_case`, the primary-suspect component set for each report identifier, and the reaction-term set for each report identifier once. Candidate exposure is then a set intersection against the mapped components, and event presence is a set lookup. Do not repeatedly filter a full child table inside candidate, case, or version loops: that turns a bounded reconciliation audit into a needlessly quadratic scan and makes completeness failures more likely.

For a candidate-level census, classify every multi-submission case from these indexed Boolean states before selecting any histories for detailed review. Keep separate counts for exposure change, event change, pair-membership change, state change without pair-membership change, and a return to an earlier state after an intervening version. These classifications can overlap; close them against the total number of multi-submission cases examined rather than forcing them into mutually exclusive buckets.

For any version-sensitive drug-event result, inspect changed cases rather than inferring the cause from the aggregate delta. A follow-up can:

- add or remove the suspect exposure;
- add or remove the event;
- change the drug's role;
- change dates or withdrawal information while leaving pair membership unchanged;
- leave the latest pair present while naive counting inflates its contribution.

Treat an added latest event and a duplicated persistent event differently. The first changes case state; the second changes only the number of version observations.

## Persist a version-comparison register

When individual histories require review, create one scratch register row per submitted report before interpreting the latest state. Carry the case identifier, report identifier, numeric version, selection rank, product role, target-event presence, linked-course availability, withdrawal and re-exposure fields, and source locators. Mark the selected row only after every version is present.

Compare adjacent submitted states field by field. Separate three outcomes that are often collapsed:

- membership changed because exposure, role, or event presence changed;
- membership persisted but evidence quality changed;
- only an unrelated field or duplicated row changed.

Write the field delta before writing its consequence. A new date can resolve chronology, contradict chronology, or leave it unresolved; a supportive code can be added while the decisive start date remains absent. If a later comparison changes the interpretation of an earlier row, revise the earlier scratch conclusion rather than appending a conflicting summary.

## Use the canonicalization helper

Run `scripts/canonicalize_rows.py` when a header table has one row per report version:

```bash
python3 scripts/canonicalize_rows.py \
  --input HEADER.csv --output LEDGER.csv \
  --case-col CASE_FIELD --version-col VERSION_FIELD \
  --report-col REPORT_FIELD --date-col RECEIPT_FIELD
```

The helper writes an intermediate ledger only. Inspect its duplicate and unresolved counts before using it; it does not join child tables or make safety conclusions.

## Close the state

Before handing the ledger to signal analysis, confirm all of the following:

- input header rows equal retained cases plus rejected versions;
- selected and rejected report identifiers are disjoint;
- period strata and reporter strata each close to their parent universe;
- every downstream case membership is keyed by a retained report identifier;
- the canonical and all-version objects remain separately addressable;
- row shuffling produces the same ledger.
- every requested history has a selected state, its rejected states, field deltas, and a consequence that agrees with those deltas.

Stop if identifiers change type during import, version fields cannot be ordered, tie-break data are missing for a real tie, or a child table lacks the report identifier needed to bind it to the selected version.
