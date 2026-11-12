---
name: layout-preserving-pdf-edits
description: Apply irreversible local redactions, add legible reason labels, flatten sanitized widgets, and assemble navigable PDF packets with PyMuPDF while preserving page boxes, printed labels, searchable text, and source order. Use when sensitive content must be removed from mixed PDF forms without reflow or rasterizing whole pages.
---

# Layout-Preserving PDF Edits

## Route companion capabilities first

This skill covers PDF mutation and assembly, not the full decision process. Before writing an edit script, load every companion skill whose trigger matches the assignment:

- `pdf-form-inspection` for mixed AcroForm, flattened, OCR, or image-backed inputs;
- `pdf-pseudonymization` when identity fields receive controlled replacements;
- `selective-record-redaction` when entered responses must be retained or removed by business purpose;
- `pdf-disposition-ledgers` when a control sheet, action totals, ordered audit rows, or field-level reconciliation is required.

Do not treat this general format skill as a substitute for a matching narrow method. Complete the inspection and decision ledger before authoring page edits.

## Work from copies

Open each source and write sanitized intermediates to a temporary directory. Never save incrementally over a source. Record each source page rectangle and rotation before editing; compare them after assembly.

## Sanitize widgets before flattening

For an AcroForm, classify every nonempty widget before editing. Clear excluded text fields, set excluded checkboxes or radios to their off state, call `update()`, and retain only permitted values. Then flatten the sanitized appearances with `Document.bake(widgets=True)` so widget dictionaries cannot carry an old value into the final packet.

Flattening before clearing preserves sensitive appearances. Drawing over a widget without clearing its value preserves recoverable object data. The safe order is classify, clear, update, bake, redact the former response rectangles, then save with garbage collection.

## Apply true region redactions

For flattened text or scans, use redaction annotations followed by `Page.apply_redactions()`. A drawn rectangle alone is only a cover. When the source page is image-backed, use an image-redaction mode that removes the overlapping image pixels as well as OCR text. Keep line art when practical, but privacy takes priority inside the response rectangle.

If visible redaction marks are required, use the requested opaque fill on the actual redaction annotation. Keep each rectangle inside the response area so the nearby prompt and column rules remain readable. Batch all redactions for a page and apply them once. Add any white reason label only after applying the destructive redaction, centered within the final bar. Use a font size that fits the bar and omit the label where the assignment permits an unlabelled compact mark.

## Rewrite object storage

Clear document metadata and XML metadata unless the assignment requires specific metadata. Save to a new file with full garbage collection, compression, and content cleaning. Re-open that saved file before merging. This rewrite matters because an incremental save can leave obsolete object streams recoverable.

## Assemble without normalizing pages

Create an empty destination and use `insert_pdf()` in the requested source order. Do not force all pages to Letter or A4, and do not print pages through a raster device. Page boxes, rotation, vector text, and source-specific width differences must survive the merge.

Generated control, register, or separator pages may use their specified size, but do not let their media box become a template for imported pages. After assembly, add the requested hierarchical table of contents with `set_toc()` and logical page-label rules with `set_page_labels()`. Page-label rule indices are zero-based even though outline destinations are one-based. A second-level outline entry must follow its level-one parent. Set controlled metadata only after all parts are merged so source metadata cannot win during insertion.

## Verify three layers

After saving:

1. Structure: page count, order, boxes, rotation, bookmarks, page labels, absence of widgets/annotations, and the final controlled metadata.
2. Content: control totals reconcile, required shell anchors and retained values remain searchable, and excluded values do not appear through a second extractor.
3. Pixels: render every page and inspect each response region for a continuous opaque mark, legible code, clipping, or damaged labels.

Use `scripts/render_check.py` for page images and geometry. Consult [redaction_and_widgets.md](references/redaction_and_widgets.md) for the operation order and common failure signatures.
