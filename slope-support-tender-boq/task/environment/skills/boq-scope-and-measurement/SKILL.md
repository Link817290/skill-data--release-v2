---
name: boq-scope-and-measurement
description: Use when turning engineering sources into priceable bill-of-quantities line items — setting contract scope boundaries, working each boundary to full construction scope, and writing item names, characteristics, and measurement rules a bidder can price without asking questions.
---

# Scope boundaries and priceable line items

A bill of quantities is a pricing instrument, not a summary of the design. Every
line exists so a bidder can attach a rate to it, and every boundary exists so the
commercial responsibility for a piece of work sits in exactly one place.

## 1. The boundary labels are contractual, not descriptive

The scope-defining record names the procurement's primary divisions — contract
phase, scheme revision, work package. Those labels are the contract structure.
Keep the exact source-defined section label or composite boundary when carrying it into the workbook.
Reproduce each one exactly as written.

Do not substitute a discipline, a support type, or a physical zone for a
source-defined boundary. Drilling, excavation, permanent support, drainage and
monitoring are *work families inside* each boundary, not boundaries themselves —
unless the source says otherwise. Collapsing a compound boundary into one of its
components, or shortening it for readability, destroys the boundary: work priced
under a label the contract does not contain cannot be awarded.

This is the most expensive mistake available here. Mixing an original scheme
with a later revision, or one phase with another, contaminates every line that
follows and produces duplication in one direction and omission in the other.

## 2. Each boundary must stand on its own

A bidder prices each division separately and takes separate commercial risk on
it. A division listed thinly is a pricing gap in that division, and no amount of
detail elsewhere repairs it: the thin division still goes out to tender
incomplete, and the difference surfaces as a claim during construction.

So work every boundary to comparable depth. Treat the least developed division
as the one that determines whether the list can go out at all, and spend effort
there before deepening a division that is already sound.

## 3. Sweep the construction chain inside every boundary

Build a boundary × work-family matrix before drafting lines. Walk the families a
slope-support package normally contains:

- enabling and site preparation works
- drilling and excavation
- permanent support elements
- reinforcement and connecting members
- dewatering and drainage
- access, platforms, and plant movement
- monitoring and testing
- temporary works
- spoil handling, disposal, and reinstatement

Mark every cell supported, not applicable, or unresolved, and keep the locator
for each supported cell. The matrix is a completeness instrument: it makes an
omission visible as an empty cell rather than as an absence nobody noticed.

Normal construction sequencing is a prompt for the sweep, never a licence to
invent. If the sequence implies an activity that no source supports, record the
gap — an unsupported quantity in a tender list is worse than a declared hole,
because it gets priced and then disputed.

## 4. One line = one priceable installed result

Name the line by what ends up installed and accepted, not by the activity or by
the design object. "Bored pile concrete" prices; "pile design" does not.

Split lines whenever a pricing driver changes, even if the installed result has
the same name. The usual drivers:

- ground class or stratum being worked
- diameter, thickness, or cross-sectional size
- material or strength grade, reinforcement grade
- installation method, including temporary casing or special plant
- depth band or working height, where it changes plant or productivity
- the measurement basis itself

Merging two rates into one line forces the bidder to price the worse case across
the whole quantity, which inflates the tender and hides the real cost structure.

## 5. Name the line the way the pricing code names it

Under the Chinese bill-of-quantities system (`GB 50500` and its companion
measurement codes) an item name is not free prose. It is built from the工艺 that
produces the installed result plus the identifying dimension, and a bidder reads
it as a rate category:

```
冲击成孔灌注桩 φ800(三类土)       construction method + element + size + ground class
C25挡墙                           grade + element
截（凿）桩头 φ800                 operation + size
```

Three conventions matter because they are what makes two lists comparable:

- **State the construction method in the name** when the method changes the rate.
  成孔 by 旋挖, 冲击, 回转 or 人工挖孔 are different rate categories for the same
  finished pile; a name that says only 支护桩成孔 has not identified the rate.
- **Write diameters in the `φ` form with millimetres** — `φ600`, `φ800` — taking
  the value from the design. Writing `0.8m` describes the same pile but does not
  match how the pricing code, the design drawings, and every other tender list
  write it.
- **Carry the distinguishing qualifier in the name**, in parentheses, when one
  installed result splits into several rate categories — ground class being the
  usual one for drilling and excavation.

## 6. Ground class splits drilling and excavation items

This is not a stylistic choice. 地层情况 is a required characteristic for
piling and earthwork items, and drilling rates differ by a large factor between
soft strata and dense or rocky ones. One line covering every stratum forces the
bidder to price the worst stratum across the whole length, so the code system
lists each ground class separately.

So when the investigation report classifies the strata a pile passes through,
the drilling item splits by ground class, and each split keeps its own diameter.
Diameter × ground class is therefore the normal shape of a piling section, not
diameter alone.

The same logic drives the other splits listed above: a driver that changes the
rate materially becomes its own line.

## 7. Characteristics follow the code's element list

Item characteristics exist so a bidder can price without querying, and the
pricing code fixes which elements have to appear. For a drilled pile the
customary set is:

```
1. 地层情况          the ground class this line covers
2. 土石比例          left to the bidder's assessment of the investigation data
3. 空桩长度          whether empty-bore length is separately paid or deemed included
4. 桩长              stated as per design, or the governing dimension
5. 桩径              in millimetres
6. 成孔方法          method, including whether dry and wet working are combined
7. 试桩费用归属      test-pile cost: separately measured or deemed included
8. 余渣与泥浆处理    spoil and slurry handling, loading, haulage, site clearance
9. 其他             compliance with design, tender documents, standard details,
                    and current construction and acceptance codes
```

Other element families have their own customary sets — concrete items state
grade, placement condition and what is deemed included; reinforcement states
steel grade and what laps and losses are covered; earthwork states material,
placement method, compaction requirement and gradation.

Write the elements as a numbered list in one cell, in the code's order. A bidder
scanning three tender lists expects the same element in the same position; free
prose that happens to contain the same facts is slower to price and easy to
misread.

Characteristics come from the sources, not from general practice. Where a source
states a technical requirement — a specification clause, a note on a drawing, a
design parameter — carry it in the characteristics with its locator, rather than
paraphrasing it into something generic. Where the code requires an element the
sources do not settle, state explicitly that it is left to the bidder's
assessment rather than leaving the element out.

## 8. The measurement rule decides what gets paid

State what the rule includes, what it excludes, and which installed dimension or
accepted record controls payment. A rule that does not say what governs payment
leaves the quantity unverifiable on site and turns every measurement into a
negotiation.

Where a recognised measurement standard governs, cite it and follow it. Where
the project's own documents impose a specific convention — a nominal length
allowance, a deduction rule, an item that is not measured separately because its
cost is deemed included — the project convention governs, and the rule should
say so explicitly rather than leaving a bidder to assume the standard default.

Keep the unit consistent with the rule. A quantity under a unit the rule does
not produce is not a smaller error than a wrong number; it is a different item.

## 9. Leave the commercial cells executable

The bidder enters rates, so the rate cells go out empty. The extended amount is
the one place the workbook does arithmetic: make it a live calculation over that
row's own quantity and rate cells, so the tender total recomputes as rates are
entered. A typed constant, a placeholder, or a pre-filled rate all break the
instrument in ways that are not visible until someone tries to use it.

## 10. Identifier continuity

Use a globally unique positive integer for each line, with Arabic positive integers only.
The sequence must not restart numbering between source-defined sections. Labels such as `Ⅰ-01`
may remain as source references, while the workbook's row identifier stays globally unique.
