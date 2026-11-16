# Rubric

This is the adopted scoring contract for the parking barrier quotation task.
The package contains only the current contract; source-review history and
working notes are kept outside the deliverable.

Scoring contract: positive weights sum to 1.0, `raw = positive_earned - deduplicated_deductions`, `final = max(0, raw)`. Plain omission earns nothing and is not additionally penalised.

## 1. What the score buys

The commission is the formal quotation an estimator issues after a site visit. A careful reader with no trade experience can already carry every handwritten entry across, apply every house rule the instruction states, and wire the amounts to formulas; both earlier artifacts did so. What neither did is the part of the job that belongs to the trade: presenting the scope as the blocks a customer negotiates and an installer works by, and quoting site works on a measured, settle on actuals basis rather than as a copied lump. The score buys that.

## 2. Classes

**Guardrails, no positive credit.** Facts the instruction hands over: the issue date 2026.7.21, the 1 percent VAT inclusive basis, the two 10 percent charges, and the rule that installation is not billed as a lump sum. Present and correct is expected. Absent is a plain omission. Present and wrong fires D06.

**A class, completeness floor, 0.10 total.** Work reached by careful reading of the sheet or by applying a stated house rule. Necessary, kept scored with tiers, priced as a floor rather than as the scarce ability.

**F class, document form, 0.05 total.** What makes the file usable as a customer document independent of the scope judgement.

**B class, trade judgement, 0.85 total.** Two items, each split into three equal parts with a substantive t1.

Why these totals. A at 0.10 is a floor: wrong or missing floor work is either caught by a deduction (D01, D03, D04) or costs the customer a re read, while a wrong B decision produces a quotation the customer cannot negotiate by block or a site dispute over works that were quoted as a lump. F at 0.05 is smaller than A because every form defect here is recoverable by reformatting without touching a figure. B1 at 0.45 is above B2 at 0.40 because the block structure is the frame every later change to the quotation is made in, while the site works basis affects one block. No total was chosen to place any artifact anywhere.

## 3. Positive items

### Three part rule for B items

t1 assert, t2 closure, t3 binding, one third each. t1 has three tiers, full 1.0, half 0.5, zero 0.0, and t2 and t3 unlock in proportion: `fraction = (tier + tier * t2 + tier * t3) / 3`.

### B1 trade block structure, 0.45

Units: `G-SEC1`, `G-SEC2`, `G-SEC3`, `G-SUB1`, `G-SUB2`, `G-SUB3`, `G-TOTAL`.

* t1: named blocks must be coherent for customer negotiation and installation. Location, entrance, work package, subsystem and trade groupings are accepted; mixed trades may belong to the same location package. Required semantic judge uses the submitted block names and actual lines, not a reference placement map. Unassigned or arbitrarily grouped scope earns zero.
* t2: correctly scoped per-block subtotals **or** one formula pre-charge total over all priced lines.
* t3: formula pre-charge total may read the subtotals or all priced lines directly.
* Both closure parts unlock proportionately: `(t1 + t1*t2 + t1*t3)/3`.

### B2 site works on a measured basis, 0.40

* t1: physical site-work scope must be intelligible and separable for negotiation. A source-bound semantic judge accepts justified combined cabling, reused containment and no-trench routes; no fixed component list or row count is required. Full credit requires all quoted site-work lines to have measurable length/count units, quantities, rates and quantity-times-rate formulas; half if at least half of those lines meet the measurement contract, otherwise zero. Unexplained lump-sum/generic scope earns zero.
* t2: quantities are provisional and settle on actual works/design, with the statement bound to site works.
* t3: all quoted site-work lines have positive provisional quantities, an intelligible site/location estimate basis and actual-settlement terms. There is no private quantity band: photographs cannot establish exact route lengths. 100/100/100/20 is a reference estimate, not a mandatory takeoff.
* Settlement meaning and site-estimate basis are judged in context, including negation; keyword presence alone does not earn credit. Required semantic service failure publishes no reward. Each part carries one third with proportional t1 unlocking. The ledger reports per-part outcomes, component coverage, quantities, formulas/cell addresses, settlement statements and site tie, allowing the score to be reconstructed.

### A1 unit prices against the right goods, 0.03

Units: `G-R06-PRICE` plate recognition 2000, `G-R07-PRICE` barrier 2400, `G-R08-PRICE` radar 500, `G-R18` signs 600 a set (any sign, notice or tariff board), `G-R25` safety island 500, and the management computer with software 2500. Share 1/6 per family. A price earns its share only when the line it sits on names the goods the sheet records for that price. A line carried at zero quantity as an option still carries its price. Where the sheet writes a quantity beside a figure, the figure is read as a unit price or as a line amount by whichever reading closes the sheet's own total; for the signs, 2 sets 1200 closes only as a line amount, so the unit price is 600. A matching price on a line naming other goods earns nothing and fires D01.

### A2 site scope carried as the right goods, 0.04

Units: mounting hardware, plate-recognition quantity 4, barrier quantity 3,
radar quantity 3, parking software, signs quantity 2, safety-island quantity 3,
and one surveillance set comprising four cameras. Each unit carries one eighth
of A2. Equivalent goods names are accepted, but every source-recorded quantity
must be preserved.

### A3 charge and tax closure, 0.03

Units: `G-MARKUP` base binding, `G-TAX-SUM`. Half share: both charges computed by formula from a single pre levy total cell, directly or through one or more intermediate cell references that resolve to that cell. A single line charging both at 20 percent satisfies this share. Half share: the final total computed by formula from that total plus the two charges. Rates and the VAT wording are guardrails and earn nothing here.

### F1 self identification, 0.01

Units: `G-TITLE`, `G-SUBTITLE`. The workbook names itself as a quotation for a parking entrance barrier and plate recognition system. A configuration and price list (配置清单及价格, price list) is an allowed equivalent of quotation. Naming the barrier and the plate recognition system is sufficient; the words parking or entrance are not required.

### F2 per line description position, 0.04

Unit: `G-COLS`. Every quoted equipment line has a description position that
says what is supplied on that line (composition, function or configuration).
F2 is the proportion of described equipment lines. Placement or quantity
allocation text alone is not a description. Model codes, brands and
specifications are not required. Whether stated figures are source-supported is
judged separately by D02.

Weight check: 0.45 + 0.40 + 0.03 + 0.04 + 0.03 + 0.01 + 0.04 = 1.00

## 4. Deductions

| id | Trigger | Exclusions | Damage | Unit | Root cause key |
|---|---|---|---|---|---|
| D01 | A line names goods the sheet does not record, including a line that carries a recorded quantity and price under the name of different goods | A different name for the same goods; lines at zero charge or zero quantity marked optional or customer supplied; a reading the artifact itself flags as uncertain | The customer signs for, and installers order, the wrong goods, and the recorded goods go unquoted | 0.05 per misread recorded entry or fabricated item; lines whose error follows from the same misread entry, such as mounting hardware reassigned because the item it belongs to was misread, are charged once | wrong or fabricated goods, one key per recorded entry or fabricated item |
| D02 | A commercial or technical commitment neither the materials nor the instruction supplies: warranty period, delivery lead time, payment schedule, service hotline, model code, brand, or specification figure, including material designations carrying figures such as a cable cross section or category | Restating a house rule; a term stated as subject to contract without a figure; a scope condition stating what the customer provides | The customer can hold the firm to it | 0.05 per distinct commitment type | invented commitment, one key per commitment type |
| D03 | A unit price differs from the price the sheet records for the same goods | Differences under one yuan; lines carried at zero quantity as options, which bill nothing | Margin loss or dispute on a signed document | 0.04 per family | price drift |
| D04 | A stated total differs from what its own components produce inside the workbook. A total written in words is a form of the total it states and counts once if it disagrees | Differences under one yuan | A quotation that does not add up is returned | 0.06 per total line | broken total |
| D05 | The customer document discloses a cost figure the house rules say is not billed, such as the site recorded installation lump sum | None | Invites renegotiation against an internal figure | 0.04 per figure | internal cost disclosure |
| D06 | A handed fact is present and wrong: issue date, VAT basis, a charge rate, or a lump sum installation line billed | None | The document contradicts the firm's own rules | 0.04 per fact | handed fact wrong |

Deduplicate by root cause key. No cap. A price that drifts on a line naming the wrong goods is one D01 only.

## 5. Held out of scored truth

Equipment counts (`G-R06-QTY`, `G-R07-QTY`), billing status of the computer, surveillance and the camera mounting hardware written between the lines, 支杆 (`G-R11`, `G-R15-PRICE`, `G-R17-PRICE`), the unit rates of the measured site works (`G-R21_24` rates), and every vendor record fact (`G-R05-*`, model, brand, specification, images, commercial terms, `G-NOTE`, `G-SIG`, `G-I29`, `G-NUMBERING`).

## 6. Reference workbook conflicts recorded, scoring unchanged

The reference workbook is the quotation the firm actually issued, and it carries record facts no permitted input supplies: a 12 month warranty, a 90 working day lead time, a 24 hour service hotline, model codes and brands. Judged as a solver's output these would fire D02. Following the probe rule for a complete correct artifact (record the conflict, do not bend scoring to keep the reference at full marks), D02 is unchanged. The reference workbook must still reach full credit on every positive item.

## 7. Repaired scoring and historical evidence

Earlier reference-placement and quantity-band rules are retired. Required grouping semantics use
`tests/semantic_source.json` and environment-configured judge service; infrastructure failure exits 2
without publishing a reward. All prices, facts and formula closure checks retain their source basis.
The historical gpt-6.1 quotation artifact mentioned in the worksheet is absent from this checkout;
its score summary is historical and has not been presented as a verified rescoring.

## Lenient hand-off diagnostic

The package standard reports two lenses. **Strict** is the score this rubric
defines, as currently implemented: it is what `task/tests/mechanical_score.py` publishes, after the documented worksheet repairs.

**Lenient** is a separate binary diagnostic added during packaging, because the
scorer carried over from the source submission publishes one number and the
standard reports two. It defines no new criterion of its own — every condition
it reads is a signal the scorer already computes. It answers one question: could
the deliverable be handed on at all?

```text
lenient = 1 iff the workbook opens,
                 B1, B2, A1, A2 and A3 are each complete,
                 no deduction is confirmed,
                 and all seven items reach a decided state
lenient = 0 otherwise
```

It is a diagnostic, not a second opinion on quality. It is deliberately coarse:
the "at least half the positive weight" clause is a floor that separates a
usable draft from an empty or unusable one, and it is not a pass mark — the
reward in this package is a continuous score and there is no qualification line.
`reward` and `reward_strict` are aliases of the strict lens; `reward_lenient` is
reported alongside and never folded into it.
