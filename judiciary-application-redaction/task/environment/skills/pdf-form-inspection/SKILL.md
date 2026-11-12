---
name: pdf-form-inspection
description: Inspect mixed native, scanned, OCR-backed, and AcroForm PDFs before editing, including page geometry, text spans, widgets, annotations, images, and filled marks. Use when a PDF packet must be redacted, merged, compared, or audited without losing its original structure.
---

# PDF Form Inspection

## Inventory every representation

Open each source read-only with PyMuPDF. Record page count, page boxes, rotation, metadata, text length, image count, annotations, and widgets. A form can carry the same answer in several representations: a widget value, its appearance stream, searchable page text, OCR text over a scan, and pixels in an embedded page image. Inspecting only one representation is not enough for privacy work.

Use `page.get_text("dict")` for spans and bounding boxes, `page.widgets()` for field state, `page.annots()` for other annotations, and `page.get_images(full=True)` for image-backed pages. Render each page once for visual comparison; do not use the rendering to rebuild the deliverable.

## Distinguish shell from entered content

Printed labels, rules, instructions, revision marks, and blank checkboxes form the document shell. Entered content is text, handwriting, a selected mark, or a widget value added to a response area. Use font, baseline, geometry, and neighboring labels together. In scanned or flattened forms, entered marks may be part of a page image while OCR exposes only some of them.

Build a scratch inventory with these columns:

| Page | Representation | Bounding box | Nearby prompt | Observed content | Filled or shell | Review class |
| --- | --- | --- | --- | --- | --- | --- |

Do not place this inventory in the requested output directory.

## Resolve field identity by geometry

AcroForm names can be generated, duplicated, or unrelated to the visible prompt. Identify a field by `(page, rectangle, type, nearest prompt)` and treat its name as supporting evidence. For flattened forms, locate the prompt first and derive the response rectangle from the surrounding rule or column boundary. Keep rectangles in page coordinates so they remain valid across render resolutions.

A selected checkbox requires special attention. The label text may be searchable while the selection itself is vector art, a glyph, or pixels. Compare the rendered mark with nearby unselected boxes and include only the entered mark in the edit rectangle.

## Detect image-backed risk

If a page contains one image covering most of its media box, assume visible handwriting and typed entries may live in that image even when OCR also exposes them as text. A text-only deletion would leave the pixels intact. Record both the OCR span and the visual response region for the later redaction pass.

## Use the inspector

Run `scripts/inspect_pdf.py INPUT.pdf --json OUT.json` to emit a structural inventory. The script is observation-only. Read the rendered page alongside its output before deciding whether a region is shell, entered content, or both.

## Close the inventory

Before editing, account for every nonempty widget, every visibly selected choice, every handwritten region, and every response-area text span. Stop and re-inspect when an entered mark cannot be separated from a label or when a page's image/text relationship is unclear.

If the assignment requires disposition totals or ordered audit rows, load `pdf-disposition-ledgers` and record both retained and changed responses in its machine-checkable ledger. A list containing only planned redactions cannot prove that all filled responses were reviewed.
