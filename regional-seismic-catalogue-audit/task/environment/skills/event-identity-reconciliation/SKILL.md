---
name: event-identity-reconciliation
description: Reconcile repeated scientific event observations across reports without losing occurrences, while exposing conflicts and deterministic canonical choices.
license: Proprietary
metadata:
    domain: scientific-identity-resolution
---

# Event identity reconciliation

## When to use

Use this method when multiple reports may describe the same physical event, especially when one report is a partial time window or uses rounded fields. Identity resolution is a separate step from sequence classification.

## Build a stable fingerprint

Prefer an identifier explicitly supplied by the source. If no identifier exists, construct a documented fingerprint from fields that jointly distinguish an event: time at the supplied precision, place token, magnitude, and suitably rounded coordinates. Keep the raw fields and the fingerprint recipe. A row number alone is not stable across reports.

Do not deduplicate solely on place text, rounded coordinates, or a timestamp. Those fields can collide. Conversely, small display differences should not prevent a match when the reporting precision makes the observations equivalent; record the precision used for the comparison.

## Preserve all occurrences

Create an occurrence index from identity to every `{file, source_row}` pair. A duplicate group contains all occurrences and an occurrence count. Choose a canonical occurrence by a deterministic rule declared in the report, such as lexical filename followed by smallest source row, or greatest source update time with stable tie breaks. Canonical selection is for navigation; it must not delete or overwrite alternate values.

## Conflicts and partial coverage

Compare time, coordinates, and magnitude using tolerances tied to source precision. If values disagree beyond those tolerances, retain both and mark the affected identity or field `conflict`; do not average them. A shorter reporting window may legitimately contain a subset of another page, so distinguish missing coverage from contradiction. A place description or page label cannot override a numeric disagreement.

## Closure and comparisons

From the occurrence index derive total occurrences, unique identities, duplicate-group count, and duplicate-occurrence count. Keep these counts alongside the detailed groups and recompute them immediately before writing. For a comparative audit, use one signature per source page containing its classification, event count, valid-event count, and primary identity. Generate every unordered pair from those signatures and distinguish shared primary identity from merely shared classification.

## Review discipline

Every duplicate or conflict should point back to its source rows. Keep identity confidence separate from scientific sequence confidence. If a required field is missing, use an explicit partial or unknown state and retain the raw token so a later revision can revisit the decision.

## Transferability

The same occurrence-index pattern applies to repeated laboratory samples, sensor alerts, ecological sightings, and versioned administrative records where one fact may appear in several feeds.
