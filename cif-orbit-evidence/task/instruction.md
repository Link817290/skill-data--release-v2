## Technical memorandum

**To:** Structure-ingestion review group  
**Subject:** Evidence register for four supplied symmetry records

The review group is deciding whether four supplied CIF records are sufficiently traceable for ingestion.  The decision needs a single register that separates supplied tokens from derived site claims, exposes unresolved chemistry, and records whether the operation sets support a coherent group-level interpretation.

**Requirements.** First create `/workspace/output/orbit_evidence.json` as a valid empty JSON object, then complete that same file as UTF-8 JSON in English.  Inspect every CIF directly under `/workspace/materials`, leave those material files unchanged, and use no network access.  Include one source-bound record per CIF with preserved scalar and loop metadata, every inequivalent site and its source-row evidence, the complete ordered affine-operation evidence and per-site transformed-coordinate trace, an auditable ordered-pair composition witness, and an `operation_group` assessment containing the operation-order inventory, determinant classes, fixed-site profile, and a deterministic group signature.  Include every supplied formula scalar in a parsed inventory, occupancy-weighted formula reconciliation, and explicit unknown or conflict states when the record cannot support a determination.  Add a `comparative_audit` that relates the four record signatures and carries its evidence pointers.  The register must cover all files present in `/workspace/materials`; all conclusions must be grounded in the supplied `/workspace` records.  Use this minimum skeleton (additional explanatory keys are allowed):

```
{
  "schema_version": "1.0",
  "input_manifest": {"files": [], "count": 0},
  "records": [{
    "file": "...", "source": {}, "metadata": {},
    "sites": [{
      "site_id": "...", "representative_label": "...",
      "source_rows": [], "orbit_size": null,
      "stabilizer_order": null, "position_class": "unknown",
      "closure_check": {}, "supplied_multiplicity": {}, "evidence": {}
    }],
    "operation_group": {
      "identity_operation_id": null,
      "determinant_by_operation": {}, "operation_orders": {},
      "fixed_site_profile": {}, "group_signature": {}, "status": "unknown"
    },
    "formula_reconciliation": {}, "status": "partial"
  }],
  "comparative_audit": {},
  "aggregate": {}
}
```

For each record, the `source` object shall expose `affine_operations` in source order and an `operation_composition` object with the ordered-pair `composition_map` and `unmatched_pairs`.  Each site's `evidence` shall expose its complete `operation_trace`; the group object shall retain the per-operation determinant and order maps alongside the signature.

Keep each site's raw and reduced representative coordinate and the element provenance for its member labels. In `formula_reconciliation`, include a `contribution_ledger` (or `contributions` / `row_contributions`) with one item per atom-loop row: source row and line, label, site identifier, raw element/type token, normalized element and fallback flag, raw occupancy, parsed occupancy, orbit size, weighted contribution and status. Unknown or conflict rows must include a reason; supported rows do not require one. Missing source tokens, parsed values and contributions stay `null`; distinguish missing/unparseable occupancy, missing element and unresolved/non-closed orbit. Sum known contributions by element and reconcile that sum to `derived_totals`. Formula reconciliation must distinguish missing formula, formula-unit count, occupancy and unresolved orbit without inventing source evidence. Reasons may be concise standard reason codes; no minimum prose length applies.

**Deliverable.** Submit `/workspace/output/orbit_evidence.json`.  Completion means that a second curator can follow each site and group-level decision to supplied rows and operation entries, distinguish supported, conflict, and unknown states, and recompute both the comparative audit and aggregate from the records.
