---
name: structured-scientific-json
description: Use when several scientific source records must become one auditable JSON register with explicit provenance, uncertainty states, and a recomputable summary.
license: Custom
metadata:
  role: general-format-foundation
---

# Structured scientific JSON

## Scope

This method controls the report contract and evidence graph. It does not decide a domain result. Use it when a reviewer must be able to replay claims from supplied records rather than trust prose.

## Create a recoverable artifact

1. Create the exact requested output path before analysis.
2. Write `{}` and immediately parse it with the local JSON parser.
3. Keep the output UTF-8 and valid after every update; write to a temporary sibling and replace only after parsing succeeds when the report is large.
4. Do not leave a second answer file that could be mistaken for the deliverable.

The first write is an execution checkpoint, not a conclusion. A later failure must leave a valid object that can be resumed.

## Model the evidence graph

Use four layers for every unit of work:

* `source` preserves supplied paths, raw tokens, loop counts, identifiers, and source locations.
* `derived` contains normalized numbers, parsed structures, and calculations made only from source values.
* `assessment` carries `supported`, `conflict`, or `unknown` states and a short reason.
* `evidence` points back to source rows, tags, and identifiers used by the derived value.

Never overwrite a supplied token with a normalized value. Keep both when a normalized value is useful. A missing token is not zero; represent it as `null` or an object with an explicit state and reason. A disagreement keeps both operands and is `conflict`, not a repaired value.

## Stable records and pointers

Build a manifest from the files actually present in the named input directory. Sort paths deterministically unless source order is itself meaningful, and state the ordering rule in a machine field. Produce exactly one record per manifest file. A record is not complete until its source inventory, derived arrays, status, and evidence pointers are present.

Every derived claim needs at least one resolvable pointer. Prefer one-based loop row numbers plus the source line and the source identifier. For a calculation involving a set, retain the complete set of identifiers; a count alone is not evidence. Keep representative selection deterministic (for example, the first source row after the declared ordering).

## Interface discipline

When the task supplies a skeleton, treat its field names as an API. Preserve required keys even when their values are unknown. Add explanatory fields rather than renaming required fields. Keep state vocabulary finite and documented; use `supported`, `conflict`, and `unknown` consistently, and reserve `not_supplied` for an optional field that is genuinely absent.

Separate raw source arrays from normalized arrays. For numbers, retain the exact token and a finite derived value. For text, preserve quoting semantics after tokenization but do not silently strip meaningful punctuation. For lists, preserve source order where an identifier or operation order matters.

## Closing a report

Finish and validate each record before constructing the top-level summary:

1. Check that every manifest file has one record and no record points outside the input directory.
2. Re-resolve every row, tag, and identifier pointer against the source inventory.
3. Verify that all numeric values are finite and that null/unknown states have reasons.
4. Recompute status from detail arrays instead of hand-entering it.
5. Recompute aggregate counts by iterating records and their detail arrays.
6. Parse the final file again and compare the summary with the recomputation.

If a dependent calculation cannot be completed, retain the available partial arithmetic and propagate the unresolved state to the record and aggregate. Do not force a complete result to make the summary look tidy.

## Review checklist

Before handoff, inspect the JSON as a reviewer would: can a claim be located, can its arithmetic be repeated, and can a missing input be distinguished from a zero? Check duplicate record keys, duplicate site identifiers, dangling evidence pointers, accidental absolute paths, and summaries that disagree with detail. Verify that source files were not rewritten while producing the report.

This format transfers to laboratory registers, diffraction audits, and other structured scientific reviews. The domain methods decide what to calculate; this method makes those calculations inspectable and recoverable.

## Practical implementation pattern

Represent an evidence pointer as a small object rather than embedding a copied source sentence. For example, a pointer can carry a file name, loop name, one-based row, source line, and field name. Keep the pointer schema stable across records so a reviewer can write one resolver. For a derived map, store the contributing pointer list next to the map and retain the arithmetic inputs in their own fields.

When a record has competing interpretations, do not create two silently divergent records. Keep one record with a `conflict` assessment containing both candidate values and the evidence for each. When an input is absent, use one `unknown` assessment with a reason and a list of unaffected calculations. This makes later adjudication additive: a newly supplied value can update the dependent fields without reconstructing the source inventory.

For deterministic output, sort maps by their source identifier only when the consumer treats them as maps; preserve arrays in source order when array order is evidence. Avoid timestamps, host paths, random identifiers, and floating-point formatting that changes between runs. A stable report is easier to diff and makes a failed calculation reproducible.
