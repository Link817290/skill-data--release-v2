---
name: verify-constrained-decisions
description: Verify multi-resource allocation and scenario-based decisions using feasibility checks, objective proofs and targeted counterexamples.
---

# Verify constrained decisions

Use this skill when a recommendation depends on constrained allocation or on comparing alternatives across operational scenarios. It supports the user's model and evidence; it does not prescribe a solver or substitute a fixed answer.

Separate four questions: Are the inputs interpreted correctly? Is each allocation feasible? Is its objective optimal under the stated priority order? Does the final recommendation follow the business selection rule?

Read [allocation and objective proofs](references/objectives.md) when several priorities interact. Read [scenario evidence](references/scenarios.md) for overrides, robust comparisons and audit design.

When constructing or inspecting a model, use [formulation and decomposition](references/formulation.md) to identify independent resources and valid subproblems. For a final recommendation, use [alternative comparison](references/alternative-comparison.md) to separate business priorities, trade-offs and Pareto dominance. The accompanying `scripts/compare_alternatives.py` compares already verified aggregate metrics; it does not solve assignments.

Use `scripts/check_resource_ledger.py` as a small integrity check on a long-form resource ledger. It checks finite, nonnegative values, duplicate resource keys and used-versus-limit bounds. Recompute usage from assignment records separately; a balanced self-reported ledger is not proof that an allocation is valid.

Maintain witnesses: selected entities, governing eligibility, consumed resources and, where relevant, actual directed paths. Accept distinct feasible assignments with the same proven objective. Do not compare a candidate to one arbitrary allocation row for row.

Challenge consequential assumptions with a small counterexample and execute the calculation. Label deliberately changed inputs as sensitivity checks, preserve the actual business records, and distinguish a demonstrated failure from an unresolved concern.

Read [verification and evidence delivery](references/verification-and-delivery.md) when designing independent checks or assembling the final files. Keep computed evidence, human-facing conclusions and review receipts traceable without presenting every intermediate file as a separate deliverable.

When the deliverable includes a business workbook, use [workbook presentation](references/business-workbooks.md) for role-specific tables, wide-sheet printing and data-preserving visual validation.

Before adopting the final recommendation, read [claim-to-evidence review](references/review-evidence.md) to trace each consequential claim to its calculation, source and operational boundary.
