---
name: pdf-disposition-ledgers
description: Build and validate closed field-decision ledgers for completed PDFs, including nonempty-widget coverage, multi-widget response grouping, geometric row order, action outcomes, and reconciled control totals. Use when a transformed PDF needs a control sheet, disposition register, per-code counts, or proof that every filled response received one decision.
---

# PDF Disposition Ledgers

## Pass the closure gate before editing

When an assignment requires action totals or register rows, use this sequence as a blocking gate:

1. Bootstrap a value-free ledger from every source PDF.
2. Replace every `UNREVIEWED` decision with `alias`, `remove`, or `retain` and add any entered regions that exist only in flattened text, vector art, handwriting, or pixels.
3. Merge widget fragments that form one semantic response field.
4. Run the validator and fix every error until it exits zero.
5. Author edits, control totals, and register pages only from the compiled ledger.

Do not begin page mutation while any bootstrapped response remains unreviewed.

## Separate review coverage from published actions

A closed review ledger contains every entered response, including responses retained unchanged. A published disposition register may contain only changed responses. Keeping both populations in one structured ledger prevents an omitted filled control from disappearing between inspection, editing, totals, and register authoring.

Use one JSON entry per semantic response field. If one response is split across several widgets or visible fragments, keep one entry and list every contributing widget reference or rectangle. Do not create one audit row per drawing rectangle.

## Use a value-free schema

Keep original response values out of the ledger. Field references and page geometry are enough to reconcile the transformation:

```json
{
  "sources": [
    {"record": "Record A", "pdf": "record-a.pdf"}
  ],
  "allowlist": [
    {
      "id": "required-professional-evidence",
      "records": ["Record A"],
      "basis": "The assignment requires this category of professional evidence."
    }
  ],
  "entries": [
    {
      "record": "Record A",
      "source_page": 1,
      "logical_page": "A-1",
      "rect": [72.0, 120.0, 210.0, 138.0],
      "field_refs": ["field_1", "field_2"],
      "decision": "remove",
      "action": "CONTACT",
      "outcome": "REMOVED",
      "publish": true
    },
    {
      "record": "Record A",
      "source_page": 1,
      "logical_page": "A-1",
      "rect": [72.0, 180.0, 210.0, 198.0],
      "field_refs": ["field_3"],
      "decision": "retain",
      "action": "RETAIN-PRO",
      "outcome": "RETAINED",
      "publish": false,
      "allowlist_rule": "required-professional-evidence"
    }
  ]
}
```

`source_page` is one-based. `rect` is the union rectangle of the response field in page coordinates. Use `publish: true` for rows that belong in the requested register. Retained entries normally use `publish: false` but remain necessary for coverage.

## Bootstrap and close AcroForm coverage mechanically

Create the initial ledger without copying response values:

```bash
python3 scripts/bootstrap_ledger.py \
  --sources-dir /workspace/materials \
  --output /tmp/ledger.json \
  record-a.pdf record-b.pdf
```

The bootstrap includes every source and creates one `UNREVIEWED` entry for each nonempty widget. Rename record and logical-page labels as needed, classify every entry, merge fragments belonging to one response, and add regions observed in non-widget representations.

Do not replace this inventory with a fresh hand-written `entries = []` list. That loses the mechanical complement which proves that no filled widget was silently omitted. Instead, write a small value-free policy file containing only the exceptions to the residual rule:

```json
{
  "records": {
    "record-a": {"name": "Record A", "logical_prefix": "A"}
  },
  "allowlist": [
    {
      "id": "required-professional-evidence",
      "records": ["record-a"],
      "basis": "The assignment requires this category of professional evidence."
    }
  ],
  "decisions": [
    {
      "record": "record-a",
      "field_refs": ["1:field_1", "1:field_2"],
      "decision": "alias",
      "action": "ALIAS"
    },
    {
      "record": "record-a",
      "field_refs": ["1:field_3"],
      "decision": "retain",
      "action": "RETAIN-PRO",
      "allowlist_rule": "required-professional-evidence"
    }
  ],
  "regions": [
    {
      "record": "record-a",
      "source_page": 2,
      "rect": [72, 180, 210, 198],
      "decision": "remove",
      "action": "SIGN"
    }
  ]
}
```

Every item in `decisions` overrides one or more bootstrapped widget entries. Listing several `field_refs` in one decision merges fragments of one semantic response. `regions` adds entered responses found only in flattened text, vector art, handwriting, or pixels. Do not place source response values in this file.

Declare allowlist rules before classifying fields. Each rule must state its narrow source-record scope and a short basis derived from the assignment, not from an observed response. Every retained widget decision or retained non-widget region must cite `allowlist_rule`; the closer rejects missing rules, unknown rules, and cross-record use. Do not create a generic administrative rule when the assignment names only particular systems, organizations, locations, or employer-side notes.

Close the ledger by applying the explicit policy and a residual removal action:

```bash
python3 scripts/close_ledger.py /tmp/ledger.json \
  --policy /tmp/policy.json \
  --default-removal OTHER \
  --output /tmp/ledger.closed.json
```

The closer applies the default removal to every bootstrapped widget not explicitly aliased, assigned a more specific removal reason, or justified by a record-scoped retain rule. It reports retained counts by allowlist rule for review. This makes an explicit retain list a real allowlist: an unrecognized filled response cannot disappear and cannot become retained by accident.

Run the validator before editing:

```bash
python3 scripts/validate_ledger.py /tmp/ledger.closed.json \
  --sources-dir /workspace/materials \
  --compiled /tmp/ledger.compiled.json
```

The validator scans nonempty widgets without printing their values. Every filled widget must appear in exactly one ledger entry. This detects skipped controls while still allowing several widget references to form one response field. For flattened or image-backed records, add the visually observed response regions to the same ledger; no widget scan can discover marks that exist only as page text, vector art, or pixels.

Fix every error before proceeding. Treat an `UNREVIEWED` entry or unexpected unaccounted widget as a review-coverage failure, not as permission to ignore it.

For every assignment with a register or action totals, the bootstrap, close, and validate commands are mandatory. Do not author the edit script, control sheet, or register until all three have run successfully and the compiled counts have been inspected.

## Compile one canonical register view

The validator sorts published entries within each record by source page, response top edge, then response left edge. It assigns two-digit row numbers starting at `01`, checks `REPLACED` for alias actions and `REMOVED` for removal actions, and emits:

- canonical `register_rows` for drawing register pages;
- action totals for the control sheet;
- per-record action totals for reconciliation;
- coverage and duplicate-reference checks.

Use the compiled rows as the only source for register cells and use the compiled counts as the only source for the control sheet. Do not independently sort, number, or count the same decisions in page-authoring code.

## Verify the round trip

After building the PDF, extract every register row and compare it to `register_rows` in order. Then compare control totals to the compiled totals. A visually plausible table is not reconciled if a row moved, a source label changed, an outcome drifted, or one response field was split into multiple rows.

Keep the ledger and compiled JSON outside the deliverable directory. They are scratch working files, not additional requested outputs.
