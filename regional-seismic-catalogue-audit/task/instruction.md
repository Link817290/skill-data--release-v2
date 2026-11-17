## Technical memorandum

**To:** The regional seismic-information review desk  
**Subject:** Reproducible register for supplied catalogue pages

Pursuant to the desk's evidence-custody and reproducibility clauses, three catalogue pages are being consolidated for a scientific screening note. The review record must retain each tabular observation while making time, coordinate, event grouping, sequence indicators, and the batch comparison auditable by another analyst.

**Requirements.** Before analysis, create `/workspace/output/seismic_catalogue_report.json` as a valid empty JSON object, then complete that same file as UTF-8 JSON in English. Cover every HTML file under `/workspace/materials`, leave the supplied pages unchanged, and work without network access. Preserve page and table evidence, normalize every listed event, expose unusable values instead of silently repairing them, derive a sequence assessment for each page, reconcile repeated event identities across pages, and close the comparative and aggregate summaries from the detailed records. Use this minimum skeleton (additional evidence fields are allowed):

```json
{
  "schema_version": "1.0",
  "input_manifest": {"files": [], "count": 0},
  "records": [{
    "file": "...",
    "source": {"tables": [], "event_rows": []},
    "events": [],
    "sequence_assessment": {},
    "status": "unknown"
  }],
  "cross_feed_reconciliation": {},
  "comparative_audit": {},
  "aggregate": {}
}
```

For `cross_feed_reconciliation`, state the deterministic canonical-occurrence
rule you used (for example, lexical source filename followed by the smallest
source row) and retain every occurrence in each duplicate group. Canonical is a
navigation choice, not permission to discard another row.

**Desk screening rule `regional-screen-v1`.** The desk publishes one versioned rule so that every analyst's sequence assessment is comparable. Apply it exactly as written; do not substitute your own cut values.

Statistics, computed over the quality-supported events of a page only:

- *completeness bin* — round each magnitude to the nearest tenth, take the modal bin, and break a tie toward the smaller bin;
- *b estimate* — maximum-likelihood slope `log10(e) / (mean magnitude of the usable set − completeness bin + 0.05)`, where the usable set is every event at or above the completeness bin. Fewer than two usable events, or a non-positive denominator, leaves b undefined;
- *primary event* — largest magnitude, ties resolved by earliest epoch and then by the stable event key;
- *dominance* — maximum magnitude minus median magnitude;
- *primary time fraction* — the primary's position within the page's epoch span, 0 at the first event and 1 at the last;
- *later events* — events strictly after the primary.

Dispositions, tested in this order, written into `sequence_assessment.classification` with the matching `sequence_assessment.confidence`:

1. `insufficient_evidence` (confidence `low`) — fewer than 8 events on the page, or b undefined;
2. `mainshock_aftershock` (confidence `high`) — dominance at least 1.0 magnitude unit, primary time fraction at most 0.25, and at least 5 later events;
3. `swarm_like` (confidence `moderate`) — dominance below 1.0 and b at least 0.9;
4. `mixed_or_uncertain` (confidence `moderate`) — everything else that cleared the evidence floor.

Record the rule name as `rule_version` at the top level of the report.

For every page, publish the state of the completeness estimate as
`sequence_assessment.completeness.status` and the state of the b estimate as
`sequence_assessment.b_value.status`. Use a controlled state such as
`supported` when the value is defined from the supplied rows and `unknown` (or
`undefined`) when the evidence floor or denominator makes it unavailable.
These states make the derived-statistic conclusions auditable; they are not
new calculations beyond the rule above.

The screening rule is an operational regional screen, not a physical
aftershock declaration. The supplied pages do not provide a governing spatial
cluster radius, so the spatial diagnostic may be reported as supporting
context, but spatial compactness must not silently change the four branches
above or be presented as proof of a physical sequence.

**Deliverable.** Submit `/workspace/output/seismic_catalogue_report.json`. Completion means that a second analyst can follow each value to a page row and recompute every reported classification and total. Only the materials under `/workspace` may support a conclusion; do not rely on information that is not supplied there.
