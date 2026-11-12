---
name: structural-evidence-extraction
description: Extract auditable structural-design inputs from a raw HTML/MathML calculation source and bind every input to a stable local evidence locator before calculation.
---

# Structural evidence extraction

## Trigger and boundary

Use this skill when a structural calculation is supplied as a raw HTML page containing prose, tables, or MathML and the requested deliverable must be independently reviewable. Start before copying any number into a workbook. This skill extracts and normalizes evidence; it does not decide whether a member passes, select reinforcement, or replace a code check.

Do not use it as a general web-scraping or design-generation method. Do not fetch a newer page, consult an external code edition, or infer an omitted value. The supplied local material is the source of truth.

## Business steps

1. **Inventory the source.** Enumerate files under `/workspace`, identify the calculation source, and record its byte size and hash in working notes. Preserve the raw file. If more than one candidate exists, record why one is in scope and the others are not.
2. **Parse the source structure.** Convert HTML markup to a searchable local representation while retaining heading text, paragraph boundaries, MathML formula blocks, and image alt text. Keep a locator for each extracted fragment such as a heading plus paragraph ordinal or a formula caption.
3. **Build the evidence ledger.** Create one row per input or reported result with `item_id`, `value`, `unit`, `source_locator`, `source_quote`, and `interpretation`. Separate geometry, material, load, reinforcement, action effects, and reported checks. Do not merge similarly named values from different sections.
4. **Normalize units and signs.** Store the source unit and a separate normalized unit. Convert only with an explicit factor in a calculation column. Record whether a value is unfactored, factored, nominal, design, provided, or required; a number without its state is not ready for use.
5. **Cross-check duplicate statements.** Where the source states the same quantity in prose, a formula, and a results paragraph, compare them and retain the distinction between rounded presentation and a governing input. A disagreement becomes a finding candidate, not a silent overwrite.
6. **Close the ledger.** Recount ledger rows by category, confirm that every number used later has a locator and unit, and list unresolved or conditional inputs explicitly. Only then hand the ledger to the calculation skill.

## Evidence rules

- A source locator must be local and reproducible: file name plus heading/paragraph or formula caption. A bare page title is insufficient.
- Keep source quotes short enough to identify the claim, but preserve the original wording and symbols when they disambiguate a variable.
- Treat MathML as data. Extract numerator, denominator, operators, subscripts, and comparison signs; do not rely on a screenshot or on a browser's rendered appearance.
- Distinguish `d` used for flexure from any alternate effective depth used in shear. They are separate ledger items until a detailing rationale closes the relation.
- Distinguish a reported result from a reviewer recomputation. The latter belongs in a calculation sheet and must cite the former as its comparison anchor.
- If a source omits a required operand, write `MISSING` with a locator for the surrounding section. Never fill an omission with a typical code value.

## Working sequence and revision trigger

Read the source inventory before extraction, then extract in section order, then normalize. If a later MathML block changes the meaning or state of an earlier prose value, revise the ledger row and add a change note before calculations proceed. A source hash change or a new candidate file also triggers a fresh inventory.

## Artifact contract

Leave an evidence ledger in the workbook's input sheet. Every row used by a formula must have a unit, source locator, and state label. The closing note must report the number of extracted inputs, the number with complete locators, and any unresolved rows. A final summary without this ledger is not an auditable extraction.

## Tooling

The bundled `scripts/extract_html_evidence.py` is a parser and indexer. It accepts a local HTML path and writes neutral JSON fragments; it does not calculate actions, capacities, or statuses. Use it to reduce copy errors, then inspect the retained fragments manually. Standard-library parsing is preferred so the method works in an offline container. Consult `references/mathml-locator-guide.md` when a repeated or ambiguous MathML block needs a stable locator.

## Failure branches

- If MathML cannot be parsed, retain the raw formula block and mark the item `UNPARSED`; do not substitute a remembered equation.
- If two paragraphs use the same symbol for different units or limit states, assign distinct item ids and carry the distinction into the calculation sheet.
- If an image contains the only value, record the alt text and mark the numeric field unavailable unless an accessible text representation is supplied.

## Closing check

Before calculation, verify that the ledger has coverage for geometry, material strengths, span and loads, reinforcement areas/locations, reported actions, and reported capacities. Verify that source quotes and locators are non-empty and that normalized values have explicit conversion factors. This check is a closure action, not a declaration in the final summary.
