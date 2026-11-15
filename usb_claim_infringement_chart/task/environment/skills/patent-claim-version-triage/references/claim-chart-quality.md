---
name: claim-chart-artifact-quality
description: Validate the structural closure of machine-readable claim charts and version-impact matrices after substantive analysis. Use when the judgments are complete and the final JSON must cover Cartesian target/claim axes without duplicates, missing inherited rows, invalid citations, or contradictory rollups.
---

# Claim-chart artifact quality

## When to use

Use this skill at the delivery stage, after claim normalization and evidence
analysis. It checks whether the artifact faithfully contains the completed work;
it does not decide any technical or legal outcome.

For large charts, visual inspection is unreliable. Coverage defects usually arise
at the boundaries: one target omitted, a dependent claim missing inherited rows,
the same pair emitted twice, or one version written over another.

## Define the expected axes

Write the target identifiers and claim identifiers from the request before
counting rows. A complete comparison collection is the Cartesian product of those
axes. Count unique keys, not raw rows, because duplicates can hide an omission.

For a two-version task, define and validate each matrix separately. Version should
be a real key or a separate collection, never an unstated convention based on row
order. If only selected later-version target/claim pairs are requested, treat that
selection as its own explicit pair axis rather than mistakenly expanding it to the
earlier chart's full Cartesian product.

## Validate nested limitation closure

For each claim, derive its required element set from the frozen dependency tree.
Then compare the submitted row keys with that set. Report both missing and extra
keys. Extra keys matter because they can signal that a parent from another version
or another claim was imported accidentally.

Apply the same closure check inside every later-version comparison. A claim-version
mapping that lists the controlling feature set does not replace feature findings
for the target. Project each required feature into the later comparison and check
that every projected identifier occurs exactly once.

Do not validate dependent claims only by row count. Two wrong identifiers can
replace two required identifiers while leaving the count unchanged.

## Validate references and state closure

Build the allowed source-key set from the packet's index, then narrow it to the
source set assigned to each target and version. Every substantive finding should
cite that target-authorized set and give a usable locator. A known key about a
different product is still an invalid bridge. Do not treat a long reason string
as a substitute for a citation.

Check that each claim-level conclusion follows its elements. A favorable rollup
cannot coexist with an unresolved or incompatible required row. An unresolved
rollup should identify at least one open feature, and a negative rollup should
identify the feature that disposes of the comparison. Perform the same check after
projecting evidence into a later claim version.

## Validate analysis fields for substance

Presence alone is not enough during manual review. Confirm that actor, medium, and
time fields answer different questions and do not repeat boilerplate. A useful row
states:

- who performs or receives the act;
- which physical path carries it;
- where it occurs in the required event order.

Where the record is silent, the field should identify that precise gap rather than
invent a fact.

## Use the bundled matrix linter

`scripts/matrix_lint.py` checks Cartesian coverage, duplicate pair keys, required
fields, and duplicate nested keys. It is deliberately answer-blind. Supply the
artifact, dotted collection path, and expected axes explicitly.

Generic example:

```bash
python3 scripts/matrix_lint.py report.json \
  --collection analysis.rows \
  --axis unit_id=A,B,C \
  --axis item_id=X,Y \
  --required result,references \
  --nested observations:observation_id
```

Run it once for every comparison matrix. Treat a nonzero exit as a structural
failure and repair the artifact before substantive review.

## Manual checks after linting

The linter cannot determine whether:

- the selected claim version is controlling;
- a normalized feature retained its legal and technical meaning;
- a source supports the identified target and mode;
- a cited passage proves direction or timing;
- a terminal result follows the all-elements analysis;
- a scope relation between versions is correct.

Review these manually. Mechanical completeness and analytical correctness are
separate gates; passing one says nothing about the other.

## Delivery closure

Before final handoff:

1. parse the final file with the same language/runtime available to the consumer;
2. run the matrix linter on every matrix;
3. verify all source keys against the supplied index;
4. recompute rollups from element states;
5. confirm that both claim versions remain separately identifiable;
6. inspect the output path, encoding, and top-level type;
7. reopen the saved artifact rather than trusting in-memory data.

Do not declare completion while a required matrix is partial. If time is limited,
deliver a structurally valid artifact with explicit open findings rather than a
polished narrative that omits target/claim pairs.

## Failure modes and stop conditions

Stop on malformed JSON, duplicate pair keys, unknown source keys, missing required
rows, or a claim-level conclusion inconsistent with its elements. Stop if the
expected axes cannot be reconstructed from the request; ask for the missing scope
instead of guessing.

Never make the validator fill missing conclusions. A quality tool may expose
structural defects, but only the analyst may supply substantive judgments.
