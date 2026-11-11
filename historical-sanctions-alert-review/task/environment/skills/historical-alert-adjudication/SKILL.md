---
name: historical-alert-adjudication
description: Adjudicate sanctions alerts on historical transactions by separating identity, transaction-time legal state, ownership coverage, restriction scope, and operational action. Use for sanctions lookbacks, legacy-payment screening, list refreshes, and corporate-group alerts.
---

# Historical sanctions alert adjudication

## Work in a bounded sequence

1. Create the requested deliverable from its template before deep analysis. Preserve every identifier and update the file as each case is resolved.
2. Inventory the supplied records and official sources with scripts or targeted searches. Do not read large documents repeatedly.
3. Build one compact ledger row per alert:
   `record | transaction period | screened party | candidate | identity evidence | legal event and date | ownership evidence and date | restriction type | scope facts | action | missing fact | sources`.
4. Decide each ledger column independently, then write the case. Do not wait to finish the entire queue before producing output.
5. Build cross-case controls from the completed ledger, not from memory.
6. Validate JSON, identifiers, empty fields, and record sets before stopping.

## Resolve identity before legal status

Test whether the transaction party is the candidate entity, not whether two strings share words. Prefer identifiers, entity type, jurisdiction, aliases, and supported corporate relations. Treat a generic shared token with conflicting country or entity type as weak evidence. Explain the decisive match or conflict.

Keep identity and applicability separate. A true current-list match can still have no applicable restriction during an earlier transaction. A false match closes the sanctions alert but says nothing about the activity's AML risk.

## Reconstruct the transaction-time state

Put the transaction start and end beside every relevant designation, directive, amendment, and ownership observation. Use the transaction period as the decision clock.

- Do not project a later designation or program tag backward.
- Do not treat the end of an aggregate period as every component's value date.
- If a period crosses an effective date, request component dates and keep the legal result open.
- Cite the event that actually supports the historical state, not only a current candidate record.

## Distinguish blocking from limited restrictions

For a blocking measure, confirm it was effective for the covered party at the transaction time before assigning a blocking action.

For a non-blocking measure, translate the source into a scope predicate: covered party, covered dealing or instrument, triggering date, issuance or contractual event, maturity or tenor, payment terms, nexus, and any supplied authorization. A payment involving a restricted institution does not by itself prove covered financing.

If a necessary scope fact is absent, do not convert uncertainty into either blocking or clearance. State the provisional status and request the smallest decisive fact set.

## Date ownership evidence

Represent each link as `owner -> stake or relation -> entity -> effective period -> source`. Separate ownership from control, branding, or group membership. A later corporate report proves ownership at its reporting date, not automatically at an earlier payment date.

Propagate only the parent's actual measure. Ownership under a limited financing restriction does not turn the subsidiary into a blocked person. If the chain cannot be dated to the transaction period, hold coverage open and request contemporaneous ownership evidence before testing transaction scope.

## Map state to action

- Different entity: close with differentiating evidence.
- Restriction effective only later: close the historical alert and name the later event.
- Blocking effective at transaction time: use the supported blocking workflow.
- Non-blocking restriction with all scope facts established: apply the source-supported consequence.
- Non-blocking restriction with missing scope facts: do not block or clear; request the missing instrument, issuance, maturity, tenor, or payment-term facts.
- Aggregate crossing an effective date: request component dates first.

Every action must follow from both identity and transaction-time state. Name missing facts precisely.

## Close cross-case controls

For each control, provide the complete affected-record set, the shared dependency, the present consequence, and the fact request that would resolve it. Keep these populations distinct:

- ownership that cannot be dated to the transaction period;
- aggregates crossing an effective date;
- confirmed post-effective cases under a non-blocking measure that still need scope facts.

Exclude false identities, wholly pre-effective records, straddles, and unresolved ownership chains from populations where they do not belong. Reconcile every control back to its case rows.

## Final checks

Reject current-state leakage, sectoral-as-blocking language, undated ownership assumptions, aggregate-date shortcuts, generic-token identity matches, and unsupported final actions. Confirm every requested entry is present, every unresolved case has a concrete retrieval request, evidence names stable source locations, and the saved deliverable parses as valid JSON.
