---
name: pdf-pseudonymization
description: Replace identity fields with a consistent controlled alias across AcroForm, flattened-text, and scan-backed PDF records while removing original values from object data, appearances, OCR, pixels, and metadata. Use when a review copy must preserve identity-bearing field structure without exposing the source identity.
---

# PDF Pseudonymization

## Define the alias map before editing

Translate the assignment's alias into field roles such as first name, middle name or initial, last name, full name, and initials. Build a temporary mapping from each identity response region to exactly one required alias component. Do not infer extra variants, and do not use a full-name token in a narrow initial box unless the specification says to do so.

Track each mapped field by source document, page, rectangle, representation, original value, and replacement. Reconcile identity fields across all records before writing any one record so a flattened full-name field and three separate name fields cannot drift to different aliases.

## Remove before replacing

An alias is a replacement, not a cover. In an AcroForm, either update the widget to the controlled value and flatten its new appearance, or clear and flatten the widget before destructively removing the old response region. In flattened text, remove the original text drawing operation. In an OCR-backed scan, remove both the OCR text and the underlying image pixels in the response region.

Insert the alias only after destructive removal when working with flattened or scanned content. Fit the token inside the original response area using a plain embedded font and conservative size. Preserve the nearby prompt, baseline, and field border. Keep alias text searchable unless the assignment explicitly requires an image-only result.

## Keep aliasing distinct from redaction

Do not draw an opaque privacy bar over a field that the assignment says to pseudonymize. The review purpose often needs to show that an identity field was populated while hiding the actual identity. A controlled token satisfies that need; a black bar conveys omission instead.

Count each replaced source response field once for audit summaries, even when a full name is split into components in one record and combined in another.

## Verify consistency and erasure

For every mapped field, verify all four conditions:

1. the required alias component is searchable inside the original response rectangle;
2. the source value is absent from that rectangle and from whole-document extraction;
3. no widget, annotation, metadata entry, OCR layer, or retained image contains the source value;
4. the rendered alias fits the field and is not obscured by a redaction mark.

Run the consistency check by alias role as well as by page. A locally correct replacement can still be globally inconsistent.
