---
name: rc-load-and-rebar-verification
description: Reconcile a reinforced-concrete beam's load effects, flexural strain compatibility, shear reinforcement and detailing decisions from source-bound inputs.
---

# RC load and rebar verification

## Trigger and boundary

Use this method after a source-evidence ledger exists and before writing the review disposition. It applies to a prismatic reinforced-concrete beam when gravity actions, section dimensions, material strengths and reinforcement data are available in the supplied material. It is a review method, not a design optimizer: never invent a load case, choose a bar size, or cite a code table that is absent from the workspace.

## Business steps

1. **Define the action path.** Classify each supplied load as unfactored dead, live, wind/seismic, or other and record its unit and limit-state state. Enumerate the combinations actually supported by the source. Calculate the factored line load and the simply-supported actions with explicit unit conversion. Reconcile the governing moment and the shear/moment at the stated critical section to the source's reported values.
2. **Lock section and material inputs.** Carry width, overall depth, effective depth for flexure, any alternate shear depth, compression-bar depth, concrete strength, steel strength, modulus, strain limit, reinforcement areas, and strength-reduction factors into a calculation sheet by cross-sheet references. Do not silently replace a rounded source value with a computed one.
3. **Run flexural strain compatibility.** Solve the neutral-axis equilibrium using the supplied compression and tension steel assumptions. Compute the compression block, compression-steel strain/stress, tension force, nominal moment, reduced design strength, and tension strain. Test the assumed yield states before accepting the capacity comparison. Report the ratio and the governing source action.
4. **Run shear candidate checks.** Preserve every concrete-shear candidate shown by the source, select the minimum by a formula, calculate the steel shear demand and capacity for each stated spacing, and apply the source's spacing limit. Every spacing the source states — trial, revised, or adopted — keeps its own row, its own capacity, and its own status taken from its own comparison; a branch the source later supersedes is dispositioned on its own terms rather than deleted.
5. **Reconcile detailing states.** Compare the effective depth used in flexure with the depth used in shear and compare each reinforcement area/spacing with the corresponding calculation. Where two uses of the same quantity disagree, record the explanation the source actually offers, record what evidence would settle it, and choose the status that matches how far the local material resolves the question — no further.
6. **Close the finding register.** Give every check a controlled status, a calculation reference, a source locator, and a rationale. Re-read the summary against the register. If a later calculation changes the governing case, revise earlier status rows and preserve the superseded value in a note.

## Calculation discipline

- Keep force, length and moment units visible in separate columns. A moment reported in force-length units must not be compared to a force-length value after a hidden conversion.
- Distinguish `provided` reinforcement from `required` reinforcement and distinguish the article's rounded values from recomputed values. A ratio above one is not enough if the state or location is wrong.
- For a nonlinear neutral-axis solve, use a bracket or an independently checkable numerical result and retain the equilibrium residual. Do not paste a target result from the verifier.
- Check the compression steel yield assumption and tension-control condition from computed strains; do not infer them from the final phi value.
- For shear, calculate the candidate concrete strengths before taking the minimum. Keep both trial and adopted spacing rows, with their own capacities and status.
- Treat a change of effective depth between checks as a relation that needs evidence: record which depth each branch uses, and record the source text that does or does not justify the difference.

## Dependencies and revision triggers

The load path precedes flexure and shear because their action effects are shared inputs. Section/material locking precedes both capacity checks. Shear detailing follows the concrete and steel capacity calculations. If the source ledger later distinguishes a reported action from an input, or if a unit/state error is found, recompute all dependent rows and revise the findings before finalizing.

## Artifact contract

Leave separate formula-bearing sections for action combinations, flexure, and shear. Each calculation row must show an input reference, a formula or derivation, a result, a comparison target where applicable, and a status. The finding register must cover every branch the calculation actually opened, including intermediate ones the source later supersedes; a summary-only answer does not close the review.

## Failure branches

- Missing combination factor or span: mark the action check `REVIEW` and do not backfill a customary factor.
- Inconsistent duplicate reinforcement areas: retain both values, identify rounding or state, and make the comparison explicit.
- A quantity the source uses two ways in two sections: keep both uses, carry the arithmetic through for each, and disposition the discrepancy as its own finding instead of silently adopting one value.
- A branch the source replaces with a later one: disposition the replaced branch against the limit that applied to it, and record the replacement in the rationale.

## Tools

The bundled `scripts/check_structural_chain.py` performs neutral structural-workbook checks: it detects formula-bearing rows, cross-sheet references, unit columns, and a non-empty finding register. It never computes a capacity or supplies a status. Use a spreadsheet engine or a separate independent calculation for numerical evaluation, then use this script as the closure pass. Consult `references/aci-review-boundaries.md` for the evidence boundary and `references/shear-branch-checklist.md` when retaining candidate and spacing branches.

## Closing check

Before delivery, verify that every reported action and capacity has a corresponding recomputation, every candidate/spacing branch remains visible with its own status, every cross-section comparison you ran is dispositioned, and the summary status agrees with every row that is not a clean pass. Preserve the raw source file and the evidence ledger.
