# Rubric

> Scoring contract. Every positive item and every guardrail declares which of its aspects are bound and which are open, so a correct report written differently is not charged with a miss.

> Field definitions and authoring criteria: `notes/04-rubric-and-baseline.md`.

## 0. Metadata

| Item | Value |
|---|---|
| Package | expert_c4 (`expert/user-1545-task-20260909-01`) |
| Relation matrix + sha256 | `relation-matrix.md` `8727b462a72c4b41e4928d8248c0740c8a3346312fe588f4f50cb8b63c018663` |
| Fact list location | `relation-matrix.md` section 4 |
| Golden + sha256 | the single file under `golden/`, sha256 `0a53e5b703421cc0aacd4b6be69f7eb8738b9a268790fafc0204ae89b503a459`. Its filename carries a full width dash character, so it is referenced here by hash rather than by name |
| Mechanical scoring entry | `task/tests/validator.py`, which wraps `task/tests/mechanical_score.py`; see section 6 |
| Semantic protocol | `task/tests/semantic_protocol.md`, blind reviewer, sees rubric plus instruction plus materials plus candidate, does not see Golden, condition label, or the mechanical result |

## 1. Scoring contract

```text
positive_earned    = sum(weight_i * earned_share_i) over positive items
applied_deductions = sum(deduplicated deduction amounts)
raw                = positive_earned - applied_deductions
final              = max(0, raw)
```

Positive weights sum to exactly 1.0. A positive item not earned scores 0 on that item and carries no extra penalty. Deductions are per independent business harm, deduplicated by root cause, uncapped. There is no cap, multiplier, or veto item. Unrounded `final` is reported to at least four decimal places.

## 2. Positive items

Every item names the relation matrix unit it binds, and every unit's `rubric 倾向` from that matrix is honoured: units marked `主要正分` carry the positive ledger, units marked `完整性检查` are capped at 0.05 in total or converted to guardrails, units marked `待裁决不进真值` appear in section 4 and score nothing.

**Wording, structure and order (`notes/04` section 3a).** Every item's Equivalence allowed field declares wording, structure and order each as bound or open, with its basis. A bound aspect is part of the deliverable specification, and a departure from it loses share as the criterion states. An open aspect is judged on facts, relations and adoption only, and every legitimate way of writing it scores the same. A binding applies only to the aspect it names: where structure is bound and wording is open, rewording loses nothing. Two bases are used. **Instruction**: the instruction asks for the outer table kept exactly as it is, with the six section labels unchanged and in their existing order. **Golden shape**: the reference answer's measured shape, recorded in `relation-matrix.md` section 5b and applied under `notes/04` section 3b, bound by class or tolerance band rather than by the reference answer's own words or single values. The instruction leaves the layout inside each section to the author, so every binding inside a section rests on the Golden shape basis alone, not on a stated requirement.

### Cluster A. Schedule and data evidence (weight 0.35)

| id | Unit | Weight | Full mark | Partial shares | Equivalence allowed (wording, structure, order: bound or open, with basis) | Anchor | View |
|---|---|---|---|---|---|---|---|
| P01 | U011, U012 | 0.03 | A cell of the outer table contains a nested table whose one axis is the tracked items and whose other axis is a time scale with **one column per month, in calendar order,** from the reporting month through the latest commitment month, including the later phase supplied in the instruction. Verified through `Cell.tables`, not cell text | share = 0.5 for the items by time table + 0.5 x (months in that range that have their own column) / (months in that range). A merged range column such as `6-7月` does not give either month its own column, and neither does a column placed after a later month. 0 if the roadmap is prose or a bullet list | **Wording open**: any column labels and any notation of a month, such as `3月`, `3月份` or `2024年3月`; any host section. **Structure bound** (Golden shape: one column per month, March to July): items on one axis, one column per month on the other; month columns beyond the latest commitment month and any number of header rows are allowed. **Order bound** (Golden shape, and a time axis carries its information by position): month columns run in calendar order. Item row order is open | `invariant`: nested table present under a cell of the single outer table | mechanical |
| P02 | U013 | 0.06 | The table's row set is exactly the items carrying a time commitment in either the tracker or the public instruction, in both directions: no row lacks a commitment, and no committed item lacks a row | share = min(purity, coverage), where purity = (rows for an item carrying any time commitment) / (content rows) and coverage = (committed items present) / (all committed items). Relative commitments such as next week or the instruction's Friday feed count. Header rows are identified by cells that are pure month labels, so one-row and two-row headers are scored alike. | **Wording open**: item naming. **Structure bound** (current Golden shape: seven data rows, including the externally supplied Friday data-feed commitment): the row set as stated; merging two items that share a commitment is allowed. **Order open**: row order | `relation`: row set against tracker and instruction commitments | mechanical |
| P03 | U016 | 0.04 | The five items whose commitment names the end of May are filled continuously from the reporting month through May **and no later**. A row that runs past its commitment misstates it and is not correct. The one exception is the cloud storage item, whose later phase is supplied in the instruction, so its span legitimately extends to July | share = (correct rows) / 5, where a correct row both reaches May and stops at its effective end month | **Wording open**: any fill token. **Structure open**: coarser buckets that still cover March through May. **Order open**: a row's span is read from the column labels, not from column position | `numeric_derivation`: deadline phrase to month span | mechanical |
| P04 | U017 | 0.02 | The item whose commitment names a final version in April stops at April and is empty from May onward | all or nothing, this row is the single discriminator between parsing the commitments and filling every row identically | **Wording open**: any fill token. **Structure open**: coarser buckets, provided the last filled bucket does not extend past April. **Order open**, as in P03 | `numeric_derivation` | mechanical |
| P05 | U009 | 0.02 | The roadmap content appears once **within the section that hosts it**. Items carrying a time commitment are not written out as narrative entries in that section in addition to being tabulated; the narrative there carries at most a lead in line. Mentions in the forward looking section are out of scope for this item, because P12 requires those objects to be carried forward and the two items must not pull in opposite directions | Gate: the roadmap content must exist somewhere, in a table or in prose, or the item is confirmed missing and scores 0. Then 1.0 if no narrative paragraph names a committed item; 0.5 if such paragraphs exist but each is a single short line of at most 40 characters; 0 otherwise | **Wording open**: any lead in wording, or no lead in at all. **Structure bound** (Golden shape: the host section carries the table and no narrative entry for a committed item): committed items appear in the table and not again as narrative. **Order open** | `invariant`: count of narrative paragraphs naming a committed item | mechanical |
| P06 | U026 | 0.055 | The data section cell contains a nested table of weekly figures keyed by the sheet's own period labels | 0.5 if a table exists but is keyed by something other than the period labels | **Wording bound** for the period keys (Golden shape: the sheet's own period labels, verbatim); header wording open. **Structure bound** (Golden shape: a nested data table, one row per period): splitting across more than one nested table is allowed. **Order open**: column order and row order | `invariant` | mechanical |
| P07 | U027 | 0.07 | **Presupposes P06.** If no extract exists, this item is confirmed missing and scores 0; it is never satisfied vacuously by producing nothing. Given an extract, every column it carries is a business column of the sheet, and none of the six sheet columns whose header begins `公式：` or ends `占比` appears. **Which business columns to carry is the author's own choice**: an extract is a selection, and the standing procedure asks for as many columns as the reader needs and no more | 1 when at least two business columns are carried and no helper column appears; 0.5 for a single business column, which is a list rather than a table; 0 when any helper column appears. Carrying every column is allowed but earns no more than a considered selection | **Wording open**: renamed headers, number formatting within the rounding the values imply. **Structure bound** (Golden shape: all eleven business columns, no helper column): as stated. **Order open**: column order | `source_location`: sheet columns A to K against L to Q | mechanical |
| P08 | U028 | 0.055 | At least four consecutive most recent periods appear as rows | share = min(rows, 4) / 4 | **Wording bound** for the period keys, as in P06. **Structure bound** (Golden shape: the four most recent periods): at least four rows; more than four weeks allowed. **Order open** | `source_location` | mechanical |

### Cluster B. Decision support and organisation (weight 0.50)

| id | Unit | Weight | Full mark | Partial shares | Equivalence allowed (wording, structure, order: bound or open, with basis) | Anchor | View |
|---|---|---|---|---|---|---|---|
| P09 | U008 | 0.12 | Content is grouped under the author's own group names, standing on their own lines. **A label taken from the tracker is the source's own naming, not a grouping**: a second level classification value, a project name, a feature description from the tracker's description column, or a token shared by several project names (for example `专区项目`) | 1 when own group names stand on their own lines and at least one of them reappears in another section; 0.5 when own group names stand on their own lines but none is carried across, or when they are inline at the head of entries and one is carried across; 0.25 for inline names none of which is carried across; 0 when every label is tracker derived or there is no grouping. An inline prefix is the text before an entry's first colon, and counts as a group name only if it heads at least two entries | **Wording open** for the names themselves: any names the author coins, numbered or not, from two groups upward; a label taken from the tracker is not an own name, as the full mark states. **Structure bound** (Golden shape: group names on their own lines, `relation-matrix.md` section 5b): own lines earn full, inline at the head of entries earns half. **Order open**: group order | `relation`: group membership against tracker classification | mechanical for the name-on-own-line and classification-copy tests, semantic for whether the grouping serves a reader |
| P10 | U010 | 0.12 | The issues section carries the tracked items that have a live blocker or something to watch this period, and excludes items whose only content is a future milestone | share = (correct items carried) / (items meeting the criterion), with the exclusion test as a gate: carrying a pure milestone item zeroes the exclusion half | **Wording, structure and order open**: any carrier, a register table included, and either category where the tracker text supports either reading. No binding basis: the instruction leaves the layout to the author and the reference answer's issues layout is not a measured shape | `enum_status` | semantic |
| P11 | U035 | 0.10 | The progress section covers the active tracked items, including those absent from the issues section. **A row in the schedule table counts as coverage wherever that table is hosted** | share = covered / tracked items in scope. Out of scope, because Golden covers them in its progress section only through units held out of truth: the basic data framework (U032, pending owner ruling Q1 with recommendation `reference_only`) | **Wording, structure and order open**: any wording; merging two items that share a status. A mention of the category the tracker's project name carries after its prefix counts for every item in that category | `relation` | mechanical |
| P12 | U038 | 0.08 | The plan section's object set matches the progress section's, and each entry gives a forward action rather than a restatement of status. **Items with their own row in the schedule table carry their forward timeline there and need not be restated in the plan** | share = (objects carried forward with an action) / (objects in the progress section narrative that have no schedule row). If every progress object has a schedule row the share is 1; if the progress section is empty it is 0 | **Wording, structure and order open**: merging two objects into one plan line where they share an action. A mention of the shared category counts for every item in it | `relation` | semantic |
| P13 | U025 | 0.08 | The data section is organised under the group names the issues section established, so a reader can carry a group name across. **The scheme is the one P09 credits**: the author's own group names. A label taken from the tracker is the source's own naming and is not a scheme, including a project or item name used as a row key in both sections. A group name that appears only in the data section is that section's own naming, not reuse | 1 when at least one own group name of the issues section appears in the data section; 0.5 when the data section carries own group names but none of the issues section's; 0 when the issues section establishes no own group names, or the data section carries none | **Wording bound** (Golden shape: the same numbered names in both sections): the data section reuses the issues section's names; any suffix per section, such as `项目一数据`, is allowed, and because Golden itself drifts here one reused name suffices rather than a one to one mapping. **Structure open**: own line or inline. **Order open** | `relation` | semantic |

### Cluster C. Judgement under distraction (weight 0.10)

| id | Unit | Weight | Full mark | Partial shares | Equivalence allowed (wording, structure, order: bound or open, with basis) | Anchor | View |
|---|---|---|---|---|---|---|---|
| P14 | U022, U021 | 0.07 | The small tier's own period over period change is reported, and the tier's share of total is never presented as a change | 0.5 if the share is reported correctly labelled but the tier's own change is absent; 0 if the share is presented as a growth rate | **Wording open**: a percentage or an absolute delta with its base, rounded to one decimal or better. One decimal is the same value; requiring two would be a notation constraint that fails a correct report. **Structure and order open** | `numeric_derivation`: sheet column N against column P | mechanical |
| P15 | U037 | 0.015 | In the forward looking section, the settlement completion time appears as an absolute time point rather than the tracker's relative phrase | all or nothing | **Wording open**: end of March, the week of March 25, within next week stated with the dates. Anything landing in April or later is wrong, not merely unearned. **Structure and order open** | `numeric_derivation`: reporting cut off date plus one week | semantic |
| P16 | U036 | 0.015 | Both sections that have nothing to report are answered with a word or short phrase, with no clause explaining why there is nothing. Judged by clause structure, not by character count: a nil answer is a phrase when it carries neither a justification nor a second clause | share = (sections answered in a phrase) / 2. A sentence that adds a parenthetical justification is not a phrase and earns 0 for that section | **Wording open**: any nil wording. **Structure bound** (Golden shape: each nil section answered with a single word): a phrase with no justification and no second clause. **Order open** | `invariant`: presence of a justification or a second clause in the nil answer. No length threshold is used anywhere in this item | mechanical |

### Cluster D. Completeness (weight 0.05, capped)

| id | Unit | Weight | Full mark | Partial shares | Equivalence allowed (wording, structure, order: bound or open, with basis) | Anchor | View |
|---|---|---|---|---|---|---|---|
| P17 | U020, U021 | 0.02 | Both period over period percentages that the sheet already carries as computed columns are reported and match those columns | share = (correct values) / 2 | **Wording open**: rounding to one decimal or better, sign expressed as wording. **Structure and order open** | `source_location`: sheet columns C and N | mechanical |
| P18 | U003 to U007, U014, U015, U019, U029, U030, U031, U034, U039 | 0.03 | The tracker's own item text reaches the report without loss of object, value or status. Scored over the ten tracker rows, so that a reviewer without the relation matrix can adjudicate it from the materials alone: each row counts once wherever in the report it appears | share = (tracker rows present and correctly attributed) / 10 | **Wording, structure and order open**: any rewording, splitting or merging that preserves object and status | `source_location` | mechanical |

**Weight check**: Cluster A = 0.35; Cluster B = 0.50; Cluster C = 0.10; Cluster D = 0.05. **Sum = 1.0000**.

### Guardrails (weight 0, violation deducts)

Two units the relation matrix marks `完整性检查` are converted to guardrails under `notes/04` section 6, because doing them correctly is the baseline expectation of the deliverable rather than professional increment, while getting them wrong is an independent harm.

| id | Unit | Guarded property |
|---|---|---|
| G01 | U042, U002, U001 | The outer table keeps seven rows, six columns, the header row's six distinct cells, the six section labels unchanged and in order, and the file lands at the requested path |
| G02 | U018, U023, U024 | The three facts supplied outside the source files appear with their values and their stated time points unchanged |

**Guardrail declarations.** G01: structure bound for the outer table, wording bound and order bound for the six section labels (basis: instruction). Whitespace inside a label is formatting, and content written on the label's own line after the label leaves the label unchanged. The header value cells are open: filling the blank business name cell is allowed. G02: values and time points bound (basis: instruction); wording open, including any equivalent expression of 24:00.

**Weight basis for P09 and P13.** These two items carry 0.20 in total, enough to reward reusable organization without dominating schedule accuracy, issue coverage, actions, and factual completeness. The reference answer organises both its issues section and its data section under its own numbered group names, and carries that numbering across the two sections with a per-section suffix (`项目一` heading the issues entries, `项目一数据-收入` heading the data entries), which is what P13 credits as reuse. A group name heads its entries once; it is not expected to occur twice, and a section may nest a sub-group under a group name without either ceasing to group. The shape items in cluster A carry less weight; their criteria are unchanged.

### Fact list back reference

Every value scored by exact match traces to the relation matrix "必须明确出现的值" table:

| Item | Value matched exactly | Present in |
|---|---|---|
| P03, P04 | The six commitment phrases | `materials`, tracker F6 to F11 |
| P07 | The eleven business column headers | `materials`, sheet A1 to K1 |
| P08 | The period labels | `materials`, sheet A2 to A5 |
| P14, P17 | 16.89 percent and 17.29 percent | `materials`, sheet C2 and N2 |
| G02 | 675 with March 22 24:00, 5194 with March 9 24:00, the July second phase, the Friday feed | `instruction` |
| G01 | The output path | `instruction` |

No other value is scored by exact match. In particular `分众付费包`, `手机渠道一` and `手机渠道二` carry no criterion of any kind, per the relation matrix section 4 closing line.

## 3. Deduction items

| id | Trigger | Exclusions | Damage basis | Unit and coefficient | Counting | Dedup root key | Relation to positive items | View |
|---|---|---|---|---|---|---|---|---|
| D01 | A quantitative claim about the source data that the source data contradicts. Example root: stating a count of periods that the sheet does not contain | A claim the sheet supports; a value inside a stated tolerance; a candidate explicitly flagged as unconfirmed | The reader acts on reported figures without reopening the sheet, so a wrong one propagates | 0.03 per distinct false claim | One per claim proposition; the same claim repeated in two sections counts once | The claim proposition | Independent of every positive item. No positive item requires this claim, so nothing is charged twice | mechanical where the sheet settles it, otherwise semantic |
| D02 | A fact, date, figure or commitment that appears in the report and is supported by neither the two sheets nor the three notes in the instruction | Restatement or aggregation of supplied facts; explicit statements of what is not yet confirmed; wording choices | The instruction states that unconfirmed items do not go into this report, so an unsupported item defeats the reader's ability to trust the rest | 0.04 per distinct invented object, value or commitment | One per invented proposition | The invented proposition | Independent. Omitting the item would simply have earned nothing | semantic |
| D04 | G01 violated: the outer table's row count, column count, header grid cell count, section labels or their order changed, or the deliverable is not at the requested path. **Scope note**: the header test counts grid cells, not filled ones, since the template ships with the business name value cell empty and leaving it empty is not a structural break. The path half is adjudicable only by the mechanical view, because a blind reviewer receives the file renamed; a semantic reviewer records it as out of scope rather than as satisfied. **Labels**: a label is unchanged when, ignoring whitespace, the section's first line begins with it. Labels present in another order are one broken property, the order; any other label change is one broken property, the wording; neither is checked when the row count has already broken | Formatting inside cells; filling the blank header value cell; adding content under a label | The template is shared and consumed by position, so a shape change creates rework for the recipient | 0.08 per structural property broken | One per property | The property | G01 carries no positive weight, so this is not a second charge for a missed positive | mechanical |
| D05 | G02 violated: a supplied fact appears with a changed value or a changed or dropped time point | Rewording; converting 24:00 to an equivalent expression; omitting the fact entirely, which earns nothing but is not this harm; resolving a supplied note whose own date reference is ambiguous to a defensible absolute date. The feed note in the instruction says only that the feed arrives on Friday, while the reporting period itself ends on a Friday, so both that Friday and the following one are defensible readings and neither is drift. See `instruction-review.md` section 7 | These facts have no source document downstream, so drift here is never caught | 0.05 per fact whose value or time point drifted | One per fact | The fact | G02 carries no positive weight | mechanical |

**Deliberately absent**: the previous rubric's dominant deduction charged 0.0002 per excess character against a per section reference length, which made a character count the damage unit. `notes/04` section 2 rules that out: word count, line count and category labels are not damage units. Over length in this deliverable is priced where it is actually adjudicable, through P05, P11 sub-result b, and P16, each of which measures a named editorial decision rather than a length. See section 7.

## 4. Units held out of truth

| unit_id | Class | Pending question | Returned to owner | Ruling |
|---|---|---|---|---|
| U032 | 不支持 | `XX手机渠道一` numbering has no source in materials or instruction | 2026-09-10, `relation-matrix.md` section 6 decision 1 | pending, recommendation (d) keep original, mark `reference_only` |
| U033 | 不支持 | `分众付费包项目` appears in no material | same | pending, same |
| U040 | 不支持 | same item in the plan section | same | pending, same |
| U043 | 冲突 | Golden filename period differs from the in document period cell by one day | 2026-09-10, decision 2 | pending, recommendation (b) keep original, mark `disputed` |

None of these four carries a positive item or a deduction. A candidate that omits them loses nothing. A candidate that invents a comparable channel project is charged under D02, which is a different harm with its own evidence.

## 6. Probes

`task/tests/probes.py`, 53 assertions, **all passing against the shipped scorer**. Probe documents are built from the blank template plus material derived content, never from the reference answer's skeleton. Samples that are correct but written differently: 17. Samples whose content is wrong: 13. Samples that violate a bound aspect: 8.

Binding violations, each asserted to lose share as its criterion states: month columns out of calendar order (P01), committed items narrated again beside the table (P05), an extract keyed by week numbers instead of the period labels (P06), two periods instead of four (P08), own group names written inline (P09), data section group names that differ from the issues section (P13), two section labels swapped and one label renamed (G01 through D04). Open aspects, each asserted to score the same: month labels written as `2024年3月` and as `3月份`, groups reordered, whitespace inside a section label, content written on a label's own line.

Coverage by kind. Carrier: tables against paragraphs, merged span cells, one and two row schedule headers, a schedule table hosted in the issues section, a decoy month table. Notation: fill tokens, coarse time buckets, one decimal percentages, renamed extract headers. Counterexamples for every tightened predicate: a row filled past its commitment, a one row schedule table, a nil answer carrying a justification, a merged month bucket on the time axis, an extract carrying five of eleven business columns, group names taken entirely from the tracker. Scope rules: schedule rows counted as progress coverage wherever hosted, an object held out of truth leaving the P11 denominator, tabulated items not required in the plan. The six mechanical deduction assertions required by `notes/04` section 5 all pass. D02 is semantic only and is declared not applicable to the mechanical view.

## Lenient hand-off diagnostic

The package standard reports two lenses. **Strict** is the score this rubric
defines, unchanged: it is what `task/tests/mechanical_score.py` publishes, and nothing in this
packaging altered a single criterion, weight, tier or deduction of it.

**Lenient** is a separate binary diagnostic added during packaging, because the
scorer carried over from the source submission publishes one number and the
standard reports two. It defines no new criterion of its own — every condition
it reads is a signal the scorer already computes. It answers one question: could
the deliverable be handed on at all?

```text
lenient = 1 iff  the deliverable parses as a .docx carrying the outer template table,
                 no positive item is left undecided,
                 no deduction fired,
                 and positive_earned >= 0.5
lenient = 0 otherwise
```

It is a diagnostic, not a second opinion on quality. It is deliberately coarse:
the "at least half the positive weight" clause is a floor that separates a
usable draft from an empty or unusable one, and it is not a pass mark — the
reward in this package is a continuous score and there is no qualification line.
`reward` and `reward_strict` are aliases of the strict lens; `reward_lenient` is
reported alongside and never folded into it.

## P10 mixed-status clarification

A dated milestone does not erase an unresolved issue in the same source project. P10 includes source projects with pending evaluation/approval/blocking issues; their issue section must state the live issue tied to that project. Only projects whose source carries solely a future milestone are milestone-only intruders. The cloud project's pending gallery-first evaluation is a live issue.

P05 does not penalize a source-supported live issue merely because its project also appears in the roadmap; this is the content P10 requires, rather than duplicate milestone narration.
