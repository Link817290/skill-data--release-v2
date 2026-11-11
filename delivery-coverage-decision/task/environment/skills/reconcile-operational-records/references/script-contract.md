# Event reconciliation helper

Run with Python's standard library:

```bash
python scripts/reconcile_events.py events.csv selected.json --entity order_id --event event_id --revision revision --metadata received_at
```

The input is UTF-8 CSV (a BOM is accepted). Every row needs nonempty entity/event identifiers and an integer business revision; validate those fields before calling the helper. Field values are compared as strings. Normalize contractually equivalent values before use if necessary, while preserving raw evidence. The output parent directory must already exist.

The helper assumes complete state at every revision. It does not apply patch updates, interpret cancellation vocabulary, transform coordinates or check valid business dates. Do not treat its `selected` status as proof of a usable active order.

Exact repeated rows with one event identifier are duplicate deliveries. If the same event identifier has any differing field, the helper marks all affected entities as message conflicts. This comparison includes reception metadata. Use it directly only if a redelivery preserves the recorded envelope; when reception timestamps legitimately differ, normalize the transport envelope according to the contract first. Do not delete payload differences during normalization.

Across distinct event identifiers at the highest business revision, event identifiers and the specified metadata columns are ignored when comparing full states. Conflicting states produce `revision_conflict`; otherwise one governing record is returned along with all governing event identifiers. Old revisions cannot supersede a newer revision because they arrived later.

`unique_messages` counts unambiguous retained event groups, excluding conflicting groups. It is not the number of distinct event identifiers in a conflicted input. Reconcile conflict groups separately. The returned `events` list is not a complete historical lineage export; retain the input or a separate entity-to-event index if a full history is needed.

Before adopting the helper for a new interface, exercise identical redelivery, delayed old revision, conflicting current revision, reinstatement and shuffled row order. Check the selected business state and conflict classification, not incidental JSON formatting.
