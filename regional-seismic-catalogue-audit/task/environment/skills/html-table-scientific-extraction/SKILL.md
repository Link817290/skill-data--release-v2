---
name: html-table-scientific-extraction
description: Extract scientific observations from archived HTML tables while preserving row evidence, table context, header-driven column semantics, and malformed text.
license: Proprietary
metadata:
    domain: scientific-html-ingestion
---

# HTML table scientific extraction

## When to use

Use this method when measurements are embedded in HTML rather than delivered as a clean CSV. The objective is lossless, reviewable extraction; a convenient dataframe alone is not evidence.

## Discover table boundaries

Parse the document with an HTML-aware parser. Collect rows in source order, and keep table boundaries, header rows, captions or nearby section labels, and one-based row numbers. Ignore layout tables only after checking that they do not contain the measurement header. A row with fewer cells, an event-count footer, or a blank separator should remain visible in a diagnostic inventory even when it is not an observation.

Identify a data table from its semantic header, not from its position. Store the original header tokens and a normalized column map. If a page has several tables with the same schema, keep a distinct table index and section label for each one.

## Header-driven coordinate interpretation

Never assume the order of coordinate columns. Resolve the column containing latitude and the one containing longitude from the header tokens, then map each row through those indices. Preserve the unparsed cell strings beside parsed numbers. Check latitude in [-90, 90] and longitude in [-180, 180]; an out-of-range value is a quality finding, not a reason to swap columns or invent a correction.

## Text and date normalization

Keep Chinese or other source-language place text exactly after whitespace normalization. Non-breaking spaces and line breaks may be formatting, but do not translate identifiers or place names. For dates, retain the original display string, extract the supplied calendar components, attach an explicit timezone assumption, and keep an integer epoch for ordering. If seconds are absent, represent the chosen precision and do not imply a more precise observation than the page supplies. Digit spacing or punctuation variation can be normalized only when the resulting date is unambiguous; otherwise mark the row partial.

## Row evidence

Assign the source row before sorting or grouping. Each normalized record should carry `{source_file, source_row, table_index, row_number}` and the raw cell list. Keep a table inventory containing the header, coordinate-column indices, section text, and row count. The inventory lets a reviewer distinguish an omitted row from a deliberately unusable measurement.

## Quality and failure modes

Check for missing cells, non-numeric magnitude, impossible dates, invalid coordinate ranges, and duplicate-looking rows. Preserve raw values and attach machine-readable reasons. Do not repair a value from a place description or from a different table. A page title cannot substitute for an absent header, and visual row order cannot substitute for an epoch timestamp.

## Transferability

The same approach applies to HTML weather tables, ecological occurrence reports, instrument dashboards, and regulatory monitoring pages. Only the semantic header map changes; source custody and row evidence do not.
