---
name: qualify-operational-claims
description: Turn incomplete operational evidence into a bounded decision note and follow-up register, distinguishing documented scope, actual holdings, completed actions and unresolved evidence. Use when a decision must be actionable without inventing missing transactions or quantities.
---

# Qualify operational claims

Attach each adopted claim to its evidence level: directly documented, calculated from documented records, conditional proposal, or unresolved. Read [claim boundaries](references/claim-boundaries.md) when an announcement is the main evidence. Read [action closure](references/action-closure.md) when writing dispositions or follow-up actions.

Keep the decision useful: say what can be acted on now, what cannot yet be quantified, who can supply the missing evidence, and what would permit closure. A missing quantity remains unknown; an empty field is not a zero balance.

Cross-check the report against the register. A count of rules is not a count of batches, units, customers or executed transactions. Distinguish a list of overall distribution states from evidence that every listed product was delivered into every state.

Before handing over a spreadsheet, use [register integrity](references/register-integrity.md) to distinguish an ambiguous repeated summary key from a valid repeated relationship, and an uncalculated formula from a wrong business value.

Use `scripts/count_relations.py` to compare product and relationship grains in structured records. It rejects incomplete key fields rather than silently combining unrelated unknowns. It measures the submitted records, not their completeness against reality.

When reviewing an earlier draft, compare its claims with original evidence. Prefer a narrower supported statement to a broad claim that the records cannot establish. Correct the draft when it conflicts with the source, preserving unresolved differences explicitly.
