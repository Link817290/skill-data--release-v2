---
name: docx-text-extraction
description: Extract paragraph-level text and stable locations from DOCX files when an audit must preserve supplied wording and section boundaries.
allowed-tools: Read Write Edit Bash
license: MIT
---

# DOCX Text Extraction

## Purpose

Use this skill when a review depends on the exact text and order of a Word document rather than on a rendered screenshot. A DOCX is a ZIP package containing XML parts; reading only a PDF conversion can lose paragraph boundaries, hidden runs, and the distinction between the document body and its tables. The extraction output is an evidence index, not a judgment.

## Operating contract

1. Work on a copy or a read-only view of the supplied DOCX. Do not rewrite the source package.
2. Read `word/document.xml` from the package and retain UTF-8 text exactly. Do not translate, spell-correct, or normalize punctuation in the evidence text.
3. Emit a paragraph index that is stable for the run. This skill's script uses zero-based indexes and records the convention in the JSON (`index_base`).
4. Keep empty paragraphs available while locating boundaries, then use non-empty text for ordered content lists. A blank paragraph may be a real layout separator and must not be silently merged into its neighbors.
5. Record the file name with every extracted collection. Never merge two documents into one undifferentiated text stream.

## XML handling

Use the standard WordprocessingML namespace and the `w:body/w:p` path for ordinary body paragraphs. A paragraph may contain many `w:r` runs and a run may contain multiple `w:t` nodes; concatenate text nodes in document order. Preserve tabs, line breaks, and non-ASCII characters when they are present in the text nodes.

Some documents put text in tables. Decide whether a table is part of the audit scope from the task, and if it is, extract it as a separate region with a region identifier. Do not silently append table cells to the surrounding body paragraph because that creates false citation adjacency. If the task only asks for body prose and a back-matter list, direct body paragraphs are usually the safest scope.

## Boundary discovery

The task's bibliography heading must be matched as a paragraph-level value after trimming only surrounding whitespace. Do not use a substring search because a table-of-contents line that appends a page number is not the bibliography section. When more than one exact heading occurs, choose the occurrence that is structurally the back-matter section and state the rule in the audit notes. A common deterministic rule is to select the last exact occurrence before the acknowledgement section.

Keep the paragraph index of the heading and of the first terminating heading. These locations let a reviewer reproduce which text was treated as body text and which text was treated as bibliography text. The extraction script leaves this decision to the caller; do not infer a heading from a table-of-contents line.

## Quality checks

Before using the extraction:

- open the ZIP and confirm `word/document.xml` exists;
- fail clearly on malformed XML or missing parts;
- compare the number of extracted paragraphs with a second lightweight read if the document is unusually large;
- inspect the first and last non-empty paragraphs around each discovered boundary;
- ensure Chinese punctuation and full-width brackets survive the round trip;
- never infer a missing reference from a failed extraction.

## Script

`scripts/extract_docx_paragraphs.py` produces an intermediate JSON index. It accepts a DOCX path and an output path, includes paragraph indices and text, and never decides whether a citation is valid. Use it to make later reconciliation reproducible. Its output is scratch evidence, not the requested report.

## Failure handling

If a DOCX has text boxes, tracked revisions, footnotes, or drawing objects that are not represented in the body paragraph path, record that limitation and inspect the relevant XML part before declaring a discrepancy. A visually present mark that is absent from the extracted body is an extraction issue, not evidence that the manuscript lacks the mark.
