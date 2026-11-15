---
name: quantity-parameter-closure
description: Use when quantities for a tender list must be derived from design geometry and then proved consistent — managing adopted parameters in one place, deriving quantities reproducibly, and running the forward, reverse, and paired closure checks that catch omissions and contradictions before the list goes out.
---

# Quantities, parameters, and closure

Two failures dominate quantity work. The first is an adopted number that appears
in several places with slightly different values because it was retyped. The
second is a list that looks complete because every row is plausible, while an
entire element of the works is missing and nothing in the document points at the
hole.

A parameter ledger fixes the first. Closure checking fixes the second.

## 1. Every adopted number lives in one place

Before deriving anything, collect the inputs the derivations will share:
excavation and embedment depths, element lengths and spacings, counts, diameters
and thicknesses, densities, lap and waste allowances, unit conversions, working
levels. Each entry records the value, where it came from, and whether it is
taken from the source or assumed.

Then derive *from the ledger*, never from memory and never by retyping. When an
input later changes — a revision, a resolved conflict, a corrected reading —
every dependent quantity moves with it, and the ones that did not move are
visible immediately.

Mark assumed entries as assumed. An assumption is legitimate in a tender list;
an assumption disguised as a source value is not, because the reviewer loses the
chance to reject it.

## 2. Derive, do not estimate

A quantity should be reconstructible by someone holding the same sources: a
short chain from identified inputs to the reported number, with the geometry
made explicit. Length × count, area × thickness, cross-section × length,
perimeter × depth — the arithmetic is simple, and its value comes from naming
which length, which count, and where each was read.

Carry full precision through the chain and round only at the reported value.
Rounding intermediate results and then multiplying is how a quantity drifts far
enough to matter while every individual step still looks right.

Where a design analyses several cross sections with different geometry, quantity
follows the section that actually applies to that stretch of the works. Applying
one section's depth across the whole boundary is a common and expensive
shortcut: it is invisible in the deliverable and wrong by whatever the sections
differ.

When two sources give different values and the conflict cannot be resolved from
what is supplied, do not pick the convenient one. Carry the more conservative
value if a value is needed to price, and record the conflict and its interim
treatment so the tender review can settle it.

## 3. Forward and reverse closure

Run both directions. They catch opposite errors.

**Forward:** walk every supported element in every boundary and confirm it
reaches at least one measurable line. This catches omission — work that exists
in the design and in no line item.

**Reverse:** walk every line and confirm it resolves to source evidence, a unit
the measurement rule produces, and a quantity basis someone else could
reproduce. This catches invention — lines that look professional and rest on
nothing.

Also reconcile the boundary labels themselves: the set of divisions in the
deliverable against the set the scope record defines. Every missing, invented,
or renamed label is a scope defect, not a formatting one.

## 4. Paired relationships

Some quantities are arithmetically bound to others, and comparing them is the
cheapest real check available. In slope-support work the usual pairs:

- drilled or bored length against the concrete placed in it
- reinforcement totals against the sum of the detailed reinforcement items
- sprayed or treated face area against the access and platform provisions
- dewatering wells against pumps, headers, and discharge
- excavated volume against spoil haulage and disposal
- anchor or nail counts against their grout, heads, and testing

A pair that does not reconcile is either a wrong quantity or a missing line, and
which one it is usually becomes obvious immediately.

A check earns its place only if it reports what it compared. "Checked and
consistent" cannot be re-performed by a reviewer; "drilled length 1 234 m
against concrete 1 210 m, difference within the declared over-break allowance"
can. State the two figures and the outcome.

## 5. Control records are the reviewer's entry points

The deliverable's control records exist so that a reviewer can enter the work at
three specific places, and each type answers a different question:

- **Adopted inputs** answer "what numbers is this list standing on, and where did
  each come from?" They only help if they name a real number, its source, and
  which lines depend on it — an input record that no line depends on controls
  nothing.
- **Open issues** answer "what did the compiler not know, and what did they do in
  the meantime?" An assumption or source conflict without its interim treatment
  leaves the reviewer knowing there is a problem and not what was done about it.
- **Consistency results** answer "what was proved, and against what?" These carry
  the paired comparisons above, with the figures.

Each type has to reach every contract division, because a division with no
control records is a division nobody checked — and that is exactly where the
unchecked error will be.

## 6. A control register is a table, not a narrative

The register is read by someone cross-checking it against the priced list, so it
is laid out as one record per row with the same columns throughout — the same
discipline the priced list itself follows. A register written as prose
paragraphs, or with each record shaped differently, cannot be walked
mechanically and stops being a control.

One row carries, in stable columns:

```
record type      which of the three questions above this row answers
record ID        unique across the register, so a later note can refer to it
division         the contract section this record applies to
linked items     the priced rows this record governs
source / input   where the number or the issue came from
adopted value    the number adopted, or the issue as stated
check / action   what was done: the comparison performed, or the interim treatment
status           how it stands now
```

Two habits make a register useless even when every column is filled: putting
more than one record's worth of content in a row, and leaving the linked-items
cell empty because "it applies generally". A record that governs nothing
specific proves nothing specific.

## 7. Make the links resolvable

Control records point back at line items, and a pointer that cannot be followed
is not a control. Identify the target line by the exact division label and the
row's own sequence number, both exactly as the deliverable prints them — the
division name in full, not shortened, and the sequence as written. If the
numbering changes during assembly, update the pointers in the same pass.

List the affected lines individually. A range written as a span, an abbreviated
label, or "all items in this family" each leave the reviewer to guess the
membership — and a control whose scope is a guess proves nothing.

## 8. Close the circuit before finishing

Follow one adopted input from its source, through its derivation, into every
line it touches, and back out through the control record that declares it. If that circuit closes, the document is auditable. If it
breaks anywhere, fix the break rather than the appearance of it.
