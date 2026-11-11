---
name: chinese-record-schema-audit
description: Parse and reconcile Chinese CSV and JSON operational records while preserving original identifiers, encoding, row identity, missing-value semantics, and units. Use when calculations must remain traceable to mixed structured source files.
---

# Chinese Record Schema Audit

Treat source text, source identity, and numeric meaning as separate concerns. A parser can succeed
while silently changing an identifier, unit, or missing marker, so establish these invariants before
doing domain calculations.

## Read without changing the record

- Open UTF-8 CSV with a decoder that removes an optional byte-order mark; a mark attached to the
  first header is a schema defect in your parser, not part of the identifier.
- Preserve every header, object key, enum, and entity name exactly in source-facing output. Keep an
  internal ASCII variable name only as a local alias.
- Never rewrite the received file to “clean” it. Parse into memory and write derived artifacts under
  the requested output directory.
- Hash the received bytes before analysis. A reproducible report binds the digest, record count,
  first and last dated records, and the JSON observation timestamp.

## Keep physical identity

For CSV records, retain both the source date and the physical line number. With one header line,
the first data record is line 2. Do not substitute a filtered-array index for the line number.

For JSON arrays, retain the zero-based array index and the entity identifier. JSON key order is not
identity. A unit is located by its array index plus its exact name and type.

When selecting the latest `N` dated records:

1. Parse the date field, rejecting invalid dates.
2. Detect duplicate dates before sorting.
3. Sort chronologically and take the final `N` records.
4. Carry their original physical line numbers through the sorted view.
5. Assert that the resulting sequence is strictly increasing.

## Normalize values explicitly

Use a parser that distinguishes:

- a numeric zero;
- whitespace or an empty string;
- a printed missing marker such as `-`;
- a malformed numeric token.

Do not coerce all four to zero. A missing capacity cannot create dispatch headroom. A blank note is
an observed blank note, not a guessed availability state until the domain rule is applied.

Attach units at conversion time. If a source reports ten-megawatt units, multiply once at the input
boundary and retain the raw source value separately or bind it through a source pointer. Percent
strings require removal of `%` and division by 100 only when the internal quantity is a fraction.

## Reconcile cross-file clocks

Two records describing the same fleet are not automatically contemporaneous. Parse each timestamp,
compute the signed separation, and state the role of each source. Legitimate roles include current
state, historical stress shape, parameter boundary, and validation observation. Do not call a
scenario a replay of actual operations when a current parameter table is combined with older
telemetry.

## Release checks

- Re-open the raw files and verify their byte hashes have not changed.
- Recount selected dates and scoped entities from the raw records.
- Recompute every unit conversion from raw cells.
- Verify each reported source pointer resolves to the claimed row or array entry.
- Test the parser with reordered JSON keys and reordered non-key CSV columns.
