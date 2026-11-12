---
name: evidence-handoff-json
description: Use when an engineering inspection must be handed over as linked JSON records, a repair drawing, and a concise memo with stable identifiers and reproducible evidence.
license: Proprietary
---

# Evidence-bound handoff

Treat the handoff as one record set. Give the inspected room, each opening, each finding, and each design change a stable identifier. Use the same identifier in `extracted_original_layout.json`, `violations_before.json`, `repaired_layout.json`, and `changes.json`; the memo should repeat those identifiers when it explains a disposition.

## Record shape

An inspection finding should contain the observed value, the requirement, the disposition, and an evidence array. Each evidence entry names a supplied file and a resolvable printed page, clause, table, figure, drawing layer, or entity handle. Keep source observations separate from repaired values so a later reviewer can distinguish what was found from what was changed.

## Closure pass

Before delivery, compare the JSON and DXF in both directions:

- every changed coordinate or door operation in the DXF is declared in `changes.json`;
- every numeric declaration in the JSON can be measured from the DXF or traced to a supplied clause;
- retained elements remain present and unchanged unless the record explains why;
- the memo distinguishes compliant retained items, repaired items, and review holds.

Use valid JSON, UTF-8 text, and a readable Markdown memo. Do not insert a citation to an unsupplied standard or a conclusion that relies on an external assumption.
