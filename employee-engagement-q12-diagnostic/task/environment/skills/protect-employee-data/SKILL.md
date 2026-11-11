---
name: protect-employee-data
description: Protect employee-level data when survey responses are joined to personnel records, identity links have purpose or time limits, or results require disclosure control.
---

# Employee data protection

Handle pseudonymous identifiers as sensitive. Use the minimum identity and personnel information needed for the stated analysis.

## Limit identity use

Use only an authorized join key and honor any validity period, match quality and allowed-use field. Distinguish permission for enrichment, grouping and repeated-person analysis.

Keep join status and rejection reason visible. Never upgrade an uncertain or purpose-limited link.

## Align facts to time

Evaluate dated personnel facts at the response date. Derive time-dependent attributes from valid dates when needed.

Treat undated or later snapshots as snapshots, not historical truth. Keep unsupported attributes missing.

## Control disclosure

Remove direct identifiers, contact details, exact sensitive dates, unnecessary stable keys and unrestricted free text from summary outputs.

Apply supplied small-cell rules consistently to counts, statistics and narrative interpretation. Check cross-tab combinations as well as single dimensions.

Before delivery, scan every string cell in every output workbook for phone numbers, email addresses, government identifiers and copied free text. Inspect hidden sheets, comments, external links and document metadata as well. Remove the value rather than merely hiding its column, then reopen and rescan the packaged files.

## Report boundaries

Retain enough pseudonymous audit evidence to verify joins without publishing identity. State when the available data cannot support historical, causal or population claims.
