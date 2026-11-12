---
name: pdf-layout-text-extraction
description: Extract and inspect text-bearing PDF documents while preserving physical-page provenance, printed-page clues, column structure, and exact source anchors. Use for PDF evidence audits where downstream findings must survive line wrapping, headers, footers, hyphenation, or multi-column reading order.
---

# PDF Layout Text Extraction

Build a source view that supports both discovery and defensible citation. Treat extraction as an evidence-preservation step, not as a conversion that replaces the PDF.

## Establish the PDF contract

1. Inspect the file with `pdfinfo` before extracting it. Record page count, encryption state, page size, and whether text extraction is permitted.
2. Keep the supplied PDF immutable. Write all transient text into a scratch directory outside the requested deliverable path.
3. Confirm that the output file already exists when the task requires an early delivery skeleton. Extraction work must not displace artifact creation.
4. Use the physical PDF page index as the stable locator. Also capture any printed page number visible in the page text; do not assume the two numbering systems coincide.

## Produce complementary views

Use two text views because neither is authoritative by itself:

- `pdftotext -layout` preserves horizontal spacing and often keeps table columns, line numbers, and facing columns intelligible.
- `pdftotext -raw` follows content-stream order and can recover sentences that a layout pass interleaves.

Run the bundled helper when repeated page extraction is useful:

```bash
python /path/to/pdf-layout-text-extraction/scripts/extract_pdf_pages.py input.pdf scratch/pages
```

The helper creates one layout view and one raw view per physical page plus a manifest. It does not identify citations, reconcile records, or produce task conclusions.

For a quick whole-document orientation, also create temporary complete views:

```bash
pdftotext -layout input.pdf scratch/document.layout.txt
pdftotext -raw input.pdf scratch/document.raw.txt
```

## Map structure before searching

Create a compact page map with these fields:

`physical page | printed page | dominant section | column mode | recurring furniture | extraction warning`

Locate the front matter, body, appendices, notes, and end reference section from the document itself. Repeated navigation words, journal banners, running titles, and page footers are furniture, not section boundaries. A reference-section label repeated in an interactive PDF sidebar does not mark multiple bibliographies.

For multi-column pages, inspect both views around every candidate. Layout extraction may place the left and right columns on one output line; raw extraction may serialize columns correctly but break displayed equations or captions. Use the PDF page and local neighboring words to arbitrate.

## Preserve evidence anchors

For every downstream finding, retain:

- physical page index and printed page when visible;
- a short exact source phrase from the callout or reference entry;
- whether the phrase came from active body prose, a caption, a table note, an appendix, or the end list;
- enough neighboring text to distinguish repeated occurrences.

Quote from the original extraction, not from a normalized matching string. Normalize only in a separate comparison field.

## Normalize cautiously

For search and matching, make a comparison copy that:

- applies Unicode normalization;
- treats soft hyphens and line-end hyphenation as possible layout artifacts;
- collapses whitespace;
- maps typographic and straight apostrophes consistently;
- optionally folds case and diacritics.

Never overwrite the evidence form with the normalized form. A hyphen may belong to a name or compound, and a diacritic may distinguish people. Join a line-end fragment only when the raw view or adjacent PDF text supports the join.

## Handle page and line locators

If the manuscript prints line numbers, bind a finding to the printed page and line span when legible. Treat extracted margin numbers as locator candidates only after checking their position in the layout view. Years, table values, and equation numbers can resemble line numbers.

When no line numbering exists, use physical page plus section and a short anchor phrase. Do not manufacture paragraph numbers.

## Quality checks

Before handing extraction to a domain audit:

- verify that every physical page produced both views;
- compare text lengths and flag nearly blank pages;
- confirm the reference-section start and end in the PDF;
- sample pages before, within, and after the reference section;
- search for a known title fragment in both views;
- confirm that headers and footers are recognized as recurring furniture;
- re-open any page whose candidate text crosses columns or is visibly truncated.

Stop and report an extraction limitation when the PDF is encrypted, image-only, missing pages, or produces contradictory readings that cannot be settled from the supplied file. Do not turn uncertain OCR into confident evidence.
