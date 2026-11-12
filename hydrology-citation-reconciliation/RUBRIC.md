# Scoring Rubric

This rubric is derived from the supplied manuscript, the reference editorial handoff in `golden/citation_reconciliation.md`, and the brief in `instruction.md`. The deliverable is the English Markdown report at `/workspace/output/citation_reconciliation.md`. Scoring evaluates the substance of the handoff — the records, locations, classifications and dispositions it carries — and does not require reproducing the reference report's headings, row identifiers, column order, sentence order or layout.

## Score Form

```text
strict = positive_earned * retention
         positive_earned = sum over the fourteen positive items of (weight * completion)
         retention       = product over damage instances of the smallest
                           coefficient among the deduction items in that instance
```

Weights and coefficients are read from `tests/scoring_params.json`. Q02, Q03, Q05-Q10 and Q14-Q16 score the fraction of all object-bound reference fields supported, rather than completing after any one match. Q14 uses source-bound semantic review for its substantive relationships and overall finding coherence, accepting professional equivalents. Q11, Q17 and Q18 remain per-reference, per-repair and per-clearance fractions. Additional completeness caps and control reconciliation are stated below.

`reward_lenient` is a must-have lens over the same ledger: 1.0 only when the printed-folio locators (Q02), occurrence reconciliation (Q05), and all source-bound exclusion contexts (Q15) are complete; the reference handoff is on hold rather than incorrectly released (D03/D04); it carries no affirmative bibliographic record invented outside the supplied material (D09); and the required record, owner, and mapping controls are present (D12). Otherwise it is 0.0. This is an independent usability test, not a threshold over the strict score. `reward` is a compatibility alias of the strict score.

Before comparison, both the reference value and the report line are normalised: case and accents are folded, soft hyphens dropped, Unicode minus signs and en/em dashes folded to a hyphen, curly quotes to straight ones, and accounting parentheses to a leading minus. A long prose value is met by a line sharing at least 70% of its content words.

## Scoring Dimensions

Each item is one positive item. Weights sum to 1.

| Item | Dimension | What is evaluated | Evidence | Weight | Capability tag |
| --- | --- | --- | --- | --- | --- |
| Q02 | Record and date locators | Printed folio bound to the reference head, year/suffix, occurrence, or exact date-like expression | End-reference ledger; exclusion register; occurrence ledger | 0.03 | Page-anchored extraction |
| Q03 | Title and stem anchors | Title anchor, exact date-like text and author-year stem bound to their record | End-reference ledger; exclusion register; collision and inheritance register | 0.02 | Record identification |
| Q05 | Occurrence reconciliation | Mapping state and record link for every body occurrence | Body-citation occurrence ledger | 0.04 | Ledger construction |
| Q06 | Grouped and compact callouts | Printed folio, exact callout group and form for multi-record and compact callout groups; PDF sheet numbers are optional and unscored | Body-citation occurrence ledger | 0.02 | Compact-callout handling |
| Q07 | Author/year explicitness | Whether each occurrence's author/year component is explicit or inherited | Body-citation occurrence ledger | 0.02 | Inheritance control |
| Q08 | Bidirectional mapping | Candidate/end-record links in both directions, including explicit absence | Occurrence ledger; reverse mapping | 0.21 | Mapping control |
| Q09 | Atomic components of occurrences | The atomic author-year components a callout group resolves into | Body-citation occurrence ledger | 0.08 | Identity resolution |
| Q10 | Reconciled controls | Counts and occurrence-to-record relations recomputed from the submitted ledgers agree with the report's control totals | All ledgers and control totals | 0.08 | Reconciliation control |
| Q11 | Credited-author cardinality | Share of the 28 end records whose single, two-author or multiple authorship the report states correctly | End-reference ledger | 0.03 | Identity resolution |
| Q14 | Source-bound findings | Exclusion meaning, record status, counterpart, evidence and compatible disposition are adopted by the report and supported by the manuscript | Exclusion register; end-reference ledger; findings | 0.22 | Editorial disposition |
| Q15 | Exclusion context | Every exclusion binds its exact expression and sufficiently specific local source context to the printed folio and exclusion reason | Non-citation date exclusion register | 0.19 | Date screening |
| Q16 | Operational ownership | Finding, owner, hold/confirmed state and precondition form a coherent instruction | Action-ownership matrix; findings | 0.03 | Handoff control |
| Q17 | Executable patch register | Share of the 19 confirmed repairs whose row carries the defective form and replacement in the declared direction | Patch register | 0.01 | Repair execution |
| Q18 | Cleared near matches | Share of the 8 plausible near matches (C01-C08) the report files with a no-change outcome for that record | Cleared-near-match register, or any row or block that names the record | 0.02 | False-repair control |

A register is located by what its rows carry, not by the heading above it: an occurrence ledger titled "in-text callout inventory" is read exactly like one titled "body-citation occurrence ledger", and a report that numbers its occurrence rows `B001` or its records `R010` is read exactly like one that adopts the reference's numbering. Report order and Markdown structure do not affect scoring; tables and lists are equally readable.

The weights reflect editorial risk rather than formatting effort. Bidirectional mapping (21%), source-bound disposition (22%), and exclusion evidence (19%) remain the three principal controls because wrong source identity, unsafe action, and unsupported rejection are the errors most likely to propagate into production. The former 21% physical-sheet-number item has been replaced by an 8% recomputed reconciliation control: PDF sheet numbers are optional conveniences, while ledger arithmetic is a material completeness check. Its remaining share is distributed across printed-folio traceability, occurrence coverage, cardinality, and operational ownership, which are independently necessary but partly cross-check the three principal controls. Patch formatting remains 1% because it becomes useful only after identity and disposition are correct; the 2% clearance share protects against destructive false repairs without letting a compact register dominate the audit.

Q11 reads the report's end-reference table rows or addressable field-list items record by record: the record is identified by its reference head and year, and cardinality is read from a labelled cardinality or credited-author field. Q17 counts only addressable patch items that state both the current and proposed form; a register of withdrawn or rejected candidates, or an item that declines the change, executes nothing.

### Accepted equivalent expressions

- Locations: the printed folio running from 4589 is required, because it is the number an editor and an author use to find the callout; the PDF sheet number may be given alongside it but does not replace it.
- Occurrence status: `linked`, `matched`, `mapped` or `resolved`, or the link itself (`B004.a -> R022`), all record a linked occurrence.
- Codes: a one-word value (explicit, narrative, parenthetical, grouped, compact, linked) may be written as the code the report defines in its own legend (`` `E` = author and year explicit ``, `` `E/E` ``, `` `A:E`/`Y:E` ``, `` `NAR` = narrative ``, `` `PAR` = parenthetical ``); a code is read as that value only when the report declares it, and never when the code is itself a name of the record (an institutional author such as IPCC).
- Cardinality: a category (single / two / multiple, one / two / three or more), a number (`4`, `3+`, `four`), a count inside the cell (`3 credited authors`, `(4 people)`), or a corporate marker (`corporate`, `institutional`, `corp.`) for an institution-authored record, which counts as one credited author.
- Reverse mapping: a record with no body occurrence is an explicit `none`, not an omitted row, and the link may use any separator that keeps the row identifiers the report's own occurrence ledger gave them.
- Exclusion reasons: equivalent labels such as date screen, non-citation register or exclusion log, and equivalent reasons such as study period, `Calibration period`, measurement period, scenario or simulation horizon, table value, figure-caption period, publication metadata and editorial furniture.
- Overall decision: any equivalent heading ("Editorial decision", "Readiness decision", "Overall readiness decision") is read, and the whole report is read when none is present. Hold wordings such as "not reference-ready", "not release-ready", "not cleared for release", "release is blocked" and "withheld from release" all count as a hold. A negated hold phrase is never read as its own opposite, so "NOT READY FOR RELEASE" is a hold.
- Roles and states: "author", "editorial office" and "copyeditor" may be named with equivalent role wording; a hold may be written as blocked, pending, deferred or awaiting confirmation when the precondition is clear.
- Clearances: a cleared near match may sit in a dedicated register, an audit matrix or an issue note; the word "cleared" is not required when the record unambiguously says no change is needed ("no accent repair", "do not correct the particle order", "same work", "compatible", "keep both suffixes").

## Deductions

Each damage instance multiplies the score by the smallest coefficient among its items. Deductions are independent of item completion. The reference handoff triggers none of them.

| Item | Error | Damage instances | Coefficient | Rationale |
| --- | --- | --- | --- | --- |
| D01 | The report is missing, unreadable, trivially short, or is not a citation report | once | 0.5 | No reviewable handoff was produced |
| D02 | The supplied manuscript PDF is missing or its digest differs from the frozen one | once | 0.1 | A plausible report against a changed manuscript is not evidence |
| D03 | The reference list is declared ready for release | once | 0.6 | Confirmed discrepancies and open author queries remain; this is the opposite conclusion, and the first line an editor acts on |
| D04 | No overall release/hold decision is stated anywhere in the report | once | 0.5 | The handoff leaves the decision it was commissioned for unstated |
| D05 | Release is asserted while the report's own findings or action-ownership matrix still carry open holds | once | 0.4 | The report contradicts itself on the line production acts on |
| D06 | A defect is claimed on a record the report itself filed as a cleared near match | one per cleared record, at most eight | 0.5 | A false repair on a record the report cleared is a destructive instruction |
| D07 | A locator is given as a PDF sheet number with no printed folio inside a register row | one per register (findings, patches, exclusions), at most three | 0.7 | The brief requires the printed folio; the sheet number does not replace it |
| D08 | A manuscript location is cited at a printed folio the manuscript does not have (outside 4589-4618) | once | 0.7 | A handoff that points at pages the manuscript lacks is not usable |
| D09 | Bibliographic facts from outside the supplied material: a full record for a work the reference list does not contain, or a volume and page range the manuscript never prints | one per register (findings, patches), at most two | 0.5 | The brief forbids relying on bibliographic facts absent from the supplied material |
| D10 | Repeated occurrences are collapsed into a single patch row | once | 0.7 | Production cannot execute a patch that does not say which occurrence it replaces |
| D11 | A credited-author cardinality that contradicts the supplied end record | once | 0.5 | A wrong cardinality drives a wrong callout form in every occurrence of that record |
| D12 | Gate: a required give-away unit is missing (see below) | one per missing unit | 0.2 | A handoff without its end records, cited-only findings, their owners or its mapping controls is not a finished handoff |
| D13 | Gate: the report was scored from a file not named `citation_reconciliation.md` | once | 0.1 | The brief fixes the deliverable path |

D12 units, each read on one line of the report with its key value: the 25 personally authored end records, each as its inverted head (`Surname, X.`) with its year and suffix; the four cited-only works (Bergstrom/Forsman 1973, Leander 2005, Van den Hurk 2005, Jacob 2007), each with a missing-record disposition; the action owner (author or editor, in its own table cell) of the Forsman 1973, Jacob 2007 and Leander 2005 holds; the reverse mapping of the listed-only SMHI 2007 record; and the control total of 28 end records.

Interactions:

- D03 and D04 are mutually exclusive: the decision is read once, from the report's own decision section when it has one and from the whole report otherwise.
- A release assertion made over the report's own open holds charges D03 and D05 as two separate instances, because one is the direction of the decision and the other is the report's internal contradiction.
- D06 is raised only against a clearance the report actually filed for that record, read on that record's own block (its own heading block, or its own row) and never on a window that can reach the register heading or a neighbouring row. The block must name the record itself (surname and year), not only a row id such as `C02` that a report may also use for its own occurrences; and a bare "missing", "uncited" or "unused" is not a defect claim when the same block states a no-change outcome.
- D07 to D10 are read inside the report's own registers, never in free prose, and each carries a negation guard, so a row that warns *against* the error is not charged for naming it. The sheet-to-folio arithmetic ("folio 4588 + n") is a correct statement of the mapping and is not a locator. D09's volume-and-pages reading compares against the manuscript's own text (`tests/manuscript_text.txt`, extracted once from the frozen PDF); a range the manuscript prints, a run of line numbers, and a row carrying a placeholder are not charged.
- D12 is not charged on a report D01 already found unreadable.
- D09 is a lenient veto only when its existing source-fabrication rule fires in an operational findings or patch register. Mentioning an unverified source as absent, requesting it from an author, or using a placeholder does not fire D09. The veto therefore rejects affirmative invented evidence without penalizing appropriate uncertainty.

## Automatic Failure

There is no automatic failure for formatting or for a missing section. A report that is unreadable or not a citation report earns no item credit, and every other error is a multiplicative deduction rather than a score cap.

## Known Limits

The score evaluates reconciliation and editorial disposition within the supplied manuscript. It does not establish external bibliographic truth, select a house citation style, or certify the scientific claims. The reference values each item is read from are enumerated in `tests/rebuilt_units.json`; the confirmed repairs and cleared near matches are those in `tests/ground_truth.json`.

## Evidence And Reconciliation Controls

Each rebuilt item scores all object-bound leaves rather than completing after any one match. Meaning, attribution, sufficiency, adopted status, disposition, exclusion context, clearance, and owner/state/precondition coherence use source-bound semantic review with exact candidate quotations. Identifiers, file digests, folios, source strings, mapping IDs, record cardinalities and counts use deterministic checks. A judge cache miss with no configured service is an infrastructure error and never becomes a candidate score.

Declared totals must agree with counts and relations recomputed from the candidate's own tables or addressable field lists. The distinct-identity control counts normalized transcribed author-year/suffix forms before proposed repairs: case, whitespace and diacritics are normalized while source name order is retained. It is a transcription control, not a count of unique people or works; particle/order variants remain visible until the collision register resolves them.
