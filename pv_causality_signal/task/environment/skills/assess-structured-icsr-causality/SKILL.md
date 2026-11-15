---
name: assess-structured-icsr-causality
description: Calibrate qualitative causality and evidence sufficiency from sparse structured individual case safety report fields. Use when report dates have mixed precision, therapy rows must be linked to suspect drugs, follow-ups conflict, or coded dechallenge and rechallenge evidence risks being overinterpreted.
---

# Assess structured ICSR causality

This method is independent of local filenames and output schema. First map the available fields to the requested product course, event, chronology, withdrawal, re-exposure, alternatives, and source locators; stop if the target course cannot be bound.

Evaluate the reported relationship, not whether the event is generally known for the product. Structured spontaneous-report fields are screening evidence; they rarely contain the clinical detail needed for high-certainty causality.

## Bind the evidence packet

Start from the retained report version. Assemble one packet containing:

- the case header and event onset field;
- every exact target reaction row;
- the target product's suspect drug row or rows;
- therapy rows linked by the drug sequence;
- other suspect and concomitant product rows;
- co-reported reactions and outcomes;
- earlier versions only when longitudinal change is requested.

Do not attach a therapy row to a product merely because it is the only dated row. Link on the drug sequence. Do not borrow a secondary-suspect course to repair a primary-suspect row, even when both rows name the same ingredient.

Cite the report identifier and source-row locator behind each material finding. If the source has duplicate reaction rows, describe the duplicated fact once while preserving all relevant locators.

## Test chronology with date intervals

Treat date precision as evidence. Convert each valid reported date into an interval:

- a year-only value spans that calendar year;
- a year-month value spans that calendar month;
- a complete date is a single day;
- a blank or malformed value is unknown.

Exposure definitely precedes the event only when the latest possible start is earlier than the earliest possible event date. Exposure definitely starts after the event only when the earliest possible start is later than the latest possible event date. All overlap, equality, missingness, and mutually inconsistent relevant courses are unresolved.

Do not pad partial dates with the first day and then claim order. Do not treat a same-day start and event as ordered when time of day is absent. An end date after an event does not establish when treatment began. A reported duration is a cross-check, not permission to invent an unreported start.

When several relevant suspect rows exist, evaluate each linked course. A clear course does not cancel a conflicting or unresolved course unless the source identifies which course pertains to the target event.

## Interpret withdrawal evidence conservatively

Map affirmative withdrawal response to supportive dechallenge and an explicit negative response to negative dechallenge. Unknown, not applicable, and blank values are unknown; they are not negative evidence.

If same-product suspect rows disagree, mark the field conflicting. Do not choose the more supportive value. Check the therapy end date for coherence, but do not invent symptom resolution timing from a withdrawal code.

Negative dechallenge can weaken a relationship only when continued symptoms after adequate withdrawal are actually represented. In a sparse extract, retain the coded negative result but state what clinical context is absent.

## Scope re-exposure correctly

Separate four questions:

1. Is a re-exposure response coded on the target product row?
2. Is the target event named as recurring?
3. Are multiple suspect products present, making attribution ambiguous?
4. Do therapy rows show a coherent later treatment course?

A positive product-row code may refer to one or more reactions in the case. An event recurrence field may refer to any suspect product. Neither alone proves that this product caused this event. Without a coherent later course, describe the positive coding as unverified re-exposure evidence, not decisive recurrence.

An explicit negative re-exposure is evidence against recurrence but does not automatically make the relationship unlikely; chronology and withdrawal evidence still matter. Unknown, not applicable, and blank remain unknown.

## Separate alternatives from missing alternatives

Co-medications, multiple suspect products, co-reported infections, disease progression, medication errors, and other clinical events can supply competing context. Record what is present without asserting an unreported diagnosis or mechanism.

An empty concomitant list is not affirmative exclusion of alternative causes. Structured exports omit narrative, history, tests, indications, and treatment response details. Unless alternatives are explicitly evaluated in supplied material, regard them as unresolved.

Do not use a quantitative signal, primary-suspect role, serious outcome, reporter profession, or known labeling as proof of individual causation.

## Calibrate the category

Test assessability before grading strength:

- **Unassessable:** chronology is unresolved, key fields conflict, or the event/exposure relationship cannot be placed from supplied evidence. Positive withdrawal or recurrence codes do not repair missing order.
- **Unlikely:** assessable evidence argues against the relationship, such as exposure definitely starting after the event or a coherent course inconsistent with withdrawal.
- **Possible:** exposure definitely precedes the event, but alternative causes remain unresolved or withdrawal evidence is absent, limited, or non-decisive.
- **Probable:** a reasonable chronology and supportive course are present, and supplied evidence affirmatively makes competing causes unlikely. Mere absence of listed competitors is insufficient.
- **Certain:** decisive event-specific clinical evidence, coherent re-exposure, and no material alternative explanation are supplied. Do not use this category from coded recurrence alone.

When evidence points in different directions, the weakest prerequisite sets the ceiling. Supportive withdrawal with unresolved chronology remains unassessable; a well-ordered chronology with unresolved alternatives remains possible.

## Compare versions without counting them twice

For longitudinal review, build the evidence packet separately for each version. Describe whether later information added, removed, or contradicted a target exposure, event, date, withdrawal field, or recurrence field.

Record product role and target-event presence before comparing causal strength. If the target event disappears, close the retained product-event assessment as absent rather than carrying the prior event forward. If a product appears only as concomitant or interacting, do not manufacture a suspect pair. When the pair exists in both states, compare chronology, withdrawal, re-exposure, competing context, and documentation sufficiency independently.

Do not call a category strengthened merely because the version number increased. Added event onset can improve temporal assessability, while removal of the target event can eliminate the relationship being assessed. A blank changed to unknown is not necessarily new clinical evidence.

Use a two-stage revision decision:

1. Decide whether pair membership changed.
2. If membership persisted, decide whether the new evidence crosses a category prerequisite or merely adds support around an unresolved prerequisite.

Revisit the earlier category whenever the event date, linked product course, product role, or scope of withdrawal or re-exposure changes. Leave the category unchanged when the new field does not repair the weakest prerequisite, and name that blocking prerequisite explicitly.

Base the final case category on the retained version. Keep prior-version observations as provenance for the change assessment, not as extra facts in the retained record.

## Write auditable evidence codes

Use short conceptual codes that name the binding fact, such as supported chronology, interval overlap, missing onset, start after event, supportive withdrawal, negative withdrawal, unverified recurrence, competing context, or unresolved alternatives. Pair each code with a rationale grounded in the packet.

Do not encode conclusions as evidence. A causality category is not an evidence code. Do not turn a blank into `no_concomitant`, `negative_rechallenge`, or `no_alternative_cause`.

## Close the assessment

Before delivery, verify:

- the target event and target suspect product are present in the retained version;
- every therapy date is linked by sequence;
- partial dates were compared as intervals;
- same-day order was not invented;
- blank, unknown, and negative values remain distinct;
- recurrence evidence is described at its documented scope;
- the category does not exceed the weakest prerequisite;
- source references support every binding code;
- no external product knowledge entered the rationale.
- each longitudinal consequence agrees with both version packets and does not import a removed fact.

Stop at unassessable when chronology cannot be established. State the missing or conflicting fact that blocks classification rather than filling it with clinical intuition.
