# Revision semantics

Determine whether the export contains snapshots, full-state events or patches. A latest-row filter is appropriate only when every revision contains a complete state.

For full-state records, distinguish four operations:

1. Deduplicate identical deliveries of the same message.
2. Detect a reused message identifier with conflicting payloads.
3. Select the highest business revision within each entity.
4. Compare all records at that revision using business fields, excluding transport metadata.

Arrival time establishes reception order, not business authority. A delayed older message must not undo a newer cancellation or reinstatement. Conflicts at the governing revision need an explicit business rule; choosing the last arrival silently invents one.

Retain all relevant event identifiers in a lineage ledger. Reconcile counts at both the message grain and entity grain. Two orders at the same coordinates remain two orders unless a domain rule explicitly merges them.

An unresolved coordinate system is not evidence that the numbers use the most common system in the file. Unknown systems, missing values and unsupported axis orders should follow the documented exception process.

The bundled script implements this state-selection boundary only. It intentionally does not validate location coordinates, interpret business actions, or impose a universal cancellation vocabulary.
# Reconcile duplicate and conflict counts separately

Do not derive exact duplicate deliveries as raw rows minus retained unique records when conflicting groups are also excluded. That subtraction silently counts rejected conflicting payloads as duplicates. Partition message groups under the declared precedence: clean retained messages, redundant deliveries in clean groups, and quarantined conflicting groups. Reconcile the partition to raw rows, then separately reconcile entity states. When an entire conflicting group is quarantined, account for its rows in that bucket rather than counting the same row as both a conflict and a duplicate. Keep message-level counts separate from affected entity counts.

