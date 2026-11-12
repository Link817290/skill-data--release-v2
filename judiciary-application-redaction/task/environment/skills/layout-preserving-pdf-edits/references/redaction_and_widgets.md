# Redaction and Widget Decision Table

| Source representation | Required removal | Safe operation order | Verification |
| --- | --- | --- | --- |
| Nonempty text widget | Value and appearance | Clear, update, bake, redact response rectangle | No widget; no extracted old value; visible mark |
| Selected checkbox or radio | Selection state and appearance | Set off, update, bake, redact only the choice box | Neighbor labels and unselected choices remain |
| Flattened searchable text | Text drawing operation | Redaction annotation, then apply redactions | Old span absent in two extractors |
| OCR text over a page scan | OCR text and underlying pixels | Redact text and overlapping image region together | Crop render contains only the opaque mark |
| Handwriting in a scan | Image pixels | Redact the measured writing area with image removal | No strokes visible around the mark |

A successful redaction changes the content underneath the mark. A successful packet assembly then performs a full rewrite so the removed representation is not retained in unreachable objects.

Common failure signatures:

- extracted sensitive text remains: the operation was a cover or a widget value was not cleared;
- text is gone but handwriting remains: OCR was removed without modifying the page image;
- a black mark appears but the source value is in an annotation: only the page content was inspected;
- labels disappear: the rectangle crossed from the response area into the form shell;
- every page has the same size after merging: the packet was normalized or printed instead of assembled from source pages.
