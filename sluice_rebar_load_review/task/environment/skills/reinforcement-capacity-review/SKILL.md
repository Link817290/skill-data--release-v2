---
name: reinforcement-capacity-review
description: Review reinforced-concrete capacity and serviceability evidence without confusing shown bars with demonstrated adequacy. Use when calculation books contain bar marks, required steel, section dimensions, crack widths, deflections, or missing demand inputs that must be kept distinct.
---

# Reinforcement-capacity review

Use this capability for reinforced-concrete member entries where a report gives bar marks, required steel, section dimensions, or serviceability results. The central discipline is to distinguish “bars are shown” from “capacity is demonstrated.”

## 1. Normalize the reinforcement notation

1. Preserve the source notation (`D`, `d`, diameter symbol, spacing, and top/bottom position) in a source column.
2. Parse count and nominal diameter separately. For distributed bars, retain both diameter and spacing and record the width or strip basis required to turn spacing into an area.
3. Record section width, depth, cover, concrete grade, steel grade, and the design action used for the check. A bar area without its basis is only an intermediate quantity.
4. Use consistent units. Nominal bar area is in mm2; a strip area from spacing depends on the strip width; moments and forces must not be silently converted.

## 2. Compute provided steel as an intermediate

For `nD d` bars, compute `n * pi * d^2 / 4`. For a bar mark with spacing, compute the area only over the explicitly stated strip width. Keep the formula in the workbook so a reviewer can change a diameter or count and see the intermediate update.

`tools/rebar_area.py` performs these mechanical calculations and reports a parsed area. It does not know a required area, select a bar size, or say PASS/FAIL.

If a notation is ambiguous (for example, a lowercase/uppercase convention is not defined), preserve the text and use `REVIEW` unless another supplied section resolves it.

## 3. Establish the demand side

Look for an explicit required steel area, a design moment/axial force/shear, and the formula inputs that connect the demand to the section. A report may provide a bar schedule but omit the required area or the governing action. In that case:

- do not call the reinforcement adequate merely because the bar area is large;
- do not invent a demand from a neighboring member;
- record the missing binding field and hold the capacity conclusion open (`REVIEW`).

When the report supplies both demand and provided steel, compare them in the same unit and at the same location (top/bottom, root/toe, wall face, or per-metre strip). A comparison across different bases is not a valid check.

## 4. Check serviceability independently

Use the report's environment class and explicit crack-width limit. Keep beam/column and pier/wall limits separate when the report distinguishes them. Compare each reported maximum crack width and deflection to its own limit; do not use the most generous limit for all members.

A missing crack limit, span, or allowable deflection is a binding omission. It is not evidence of failure, but it prevents a PASS claim. A dash in a serviceability column must be explained by scope text before it is accepted.

## 5. Review minimum and constructability evidence

Check whether the report identifies cover, bar grade, spacing, anchorage, and the governing environmental class. These are separate evidence rows. If the report gives a general material statement but not member-specific cover or anchorage, mark the member-specific conclusion `REVIEW` and cite the general statement as context.

Do not apply external code minima that are not supplied in the material. This task tests disciplined review of the provided calculation book, not a memory test of a standard.

## 6. Write the judgment chain

For each row, make the process auditable: source notation -> parsed area or service value -> demand/limit availability -> comparison -> status. The explanation should state whether a value was disclosed, derived mechanically, or absent. Keep a `REVIEW` row when the chain stops at a missing input.

## 7. Common traps

- treating a bar schedule as a completed capacity calculation;
- comparing total steel with a per-metre demand;
- losing top/bottom or face orientation;
- interpreting a dash as zero steel or zero crack width;
- using a crack limit from one environment class for another;
- replacing the supplied grade or cover with a remembered default.
