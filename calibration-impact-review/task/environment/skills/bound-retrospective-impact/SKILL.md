---
name: bound-retrospective-impact
description: Turn detected process or quality failures into evidence-bounded historical impact and follow-up decisions when workload links are incomplete.
---

Build a chain from observed failure to applicable decision scope to identifiable affected records. Keep confirmed affected items, items requiring investigation and absent evidence distinct. Read [scope and closure](references/scope-and-closure.md) before extending a run-level finding to a day, shipment, product or client.

Use [propagate_groups.py](scripts/propagate_groups.py) only when the supplied procedure authorizes a group-level consequence and a real linking key is present. The helper returns known record IDs and unresolved groups; it never manufactures missing workload items.

Test both overreach and omission: a failed control may implicate known associated work, but incomplete links do not justify either declaring everything safe or inventing a precise affected quantity. Recommendations may differ while preserving the same evidence boundaries and closure conditions.

Completeness is separate evidence: a single valid link proves that item is associated, not that every associated item is listed. Supply `documented_complete_groups` only for groups whose full workload coverage is explicitly established by an authoritative register or closure evidence. Omitted coverage leaves the group unresolved even when known items exist; an invalid item in a declared complete group also leaves it unresolved. The helper cannot verify the truth of the completeness declaration.
