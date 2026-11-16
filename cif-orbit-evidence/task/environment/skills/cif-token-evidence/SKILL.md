---
name: cif-token-evidence
description: Use when reading CIF-like crystallographic text while preserving raw scalar and loop tokens, source locations, uncertainty notation, and incomplete-input states.
license: Custom
metadata:
  role: crystallographic-format-method
---

# CIF token evidence

## Boundary

Run this method before symmetry or composition interpretation. It reconstructs what the record actually supplies. It must not fill in a conventional value from memory or repair a malformed record without retaining the original evidence.

## Tokenization rules

Use a format-aware parser when one is available and deterministic. Otherwise implement a small state machine with these rules:

* Skip comments only while outside a quoted value or a semicolon text block.
* Treat single- and double-quoted values as one token and retain their inner text.
* Treat a semicolon-delimited block as one value, recording its opening line.
* Preserve `?` and `.` as missing markers.
* Record a source line on every token, not merely on each loop.
* Keep `loop_`, `data_`, `stop_`, and `save_` control tokens distinct from values.

Do not split on whitespace before handling quotes and blocks. A token containing an uncertainty, a signed value, or an embedded comma remains one token.

## Scalar and loop reconstruction

Scan the token stream in order. A scalar tag consumes exactly its following value; an absent value is an explicit unknown. A loop first consumes all consecutive tags beginning with `_`, then consumes complete rows of the resulting width. Keep a final incomplete row as an incomplete-loop flag rather than shifting its values into the next loop.

Discover the atom loop by the presence of `_atom_site_label` and the three fractional-coordinate tags. Optional type, occupancy, multiplicity, and uncertainty tags are retained when present. Discover a symmetry loop by an operation-expression tag, accepting the standard aliases, and retain a supplied operation identifier when one exists; otherwise use the one-based loop row as a local identifier and mark that choice.

Keep the raw row tokens, one-based row number, and source line. A normalized row may be added beside the raw row, but it must never replace it. If required tags are absent or the loop is incomplete, record the rows that were read and expose the dependent analysis as `unknown`.

## Numeric normalization

Parse signed decimals, scientific notation, and rational strings into exact-enough values. A standard uncertainty suffix such as `0.123(4)` is removed only in the derived numeric field; the raw token and uncertainty-bearing form remain in evidence. Reduce fractional coordinates modulo one only in a derived comparison field. Values outside `[0,1)` are valid source tokens and must remain visible.

Never coerce an unparsable value, `?`, or `.` to zero. Keep a parse-status field and the reason for failure. Choose comparison tolerance from the least precise coordinate or occupancy token involved, and record that tolerance beside the claim.

## Formula and metadata inventory

Inventory every scalar whose tag denotes a formula, not only the first alias encountered. For each item retain `tag`, raw token, source line, parsed element/count map or `null`, and parse status. Compare parsed alternatives before selecting a value for downstream arithmetic. Apply the same discipline to space-group numbers, symbols, formula-unit counts, and cell parameters.

For element accounting, prefer `_atom_site_type_symbol`. If it is absent, derive a provisional leading capitalized token from the label and mark the fallback. Remove oxidation-state decorations only in the derived element field; preserve the supplied decorated token.

## Extraction checks

After parsing, check that the manifest and file contents agree, that every atom row has a row number and three coordinate slots, that every operation has an expression and identifier, and that at least one translation-bearing operation and one uncertainty-bearing coordinate remain in the inventory when supplied. These are extraction checks, not scientific conclusions.

The resulting token register is reusable for orbit derivation, disorder review, and formula reconciliation. It also provides a clear failure boundary: later methods can distinguish absent evidence from a value that was parsed and found to disagree.

## Parser edge cases

Treat a comment marker inside a quoted value as ordinary text. A semicolon block can contain blank lines and leading spaces; its opening line remains the location pointer. A loop may be followed immediately by another loop or a scalar, so stop value collection when a control token begins at a row boundary. If a loop has a partial final row, retain the raw trailing tokens in a diagnostic field and do not assign them to columns.

For aliases, keep a canonical derived role and a list of every source tag that supplied it. For example, several operation-expression tag names can feed one `operation` role while the raw tag names remain visible. When two aliases disagree, do not choose by lexical order; mark the relation as a conflict and let the downstream method decide whether any arithmetic is still safe.

A useful extraction smoke test is to select one quoted scalar, one uncertainty-bearing coordinate, one operation with a translation, and one missing token. Confirm that their raw text, parsed value, source line, and missing/uncertainty state survive a serialize-parse round trip. This catches most accidental whitespace and column-shift errors before scientific work begins.
