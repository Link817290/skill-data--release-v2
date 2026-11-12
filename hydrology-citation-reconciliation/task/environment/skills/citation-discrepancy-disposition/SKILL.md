---
name: citation-discrepancy-disposition
description: Turn citation-reference reconciliation findings into evidence-bound editorial actions without inventing missing metadata or deleting uncertain sources. Use when an editor needs confirmed discrepancies, author queries, cleared near matches, source locations, and a defensible manuscript-readiness decision.
---

# Citation Discrepancy Disposition

Convert a closed inventory and resolved candidate matrix into an editorial handoff. Keep the observed defect, the available evidence, and the proposed action distinct.

## Use an evidence hierarchy

Prefer evidence in this order:

1. exact callout and full matching reference record in the supplied manuscript;
2. repeated callout occurrences and the manuscript's stable local convention;
3. title words or surrounding claim context in the supplied reference list;
4. an explicit organization-acronym introduction in the manuscript;
5. author confirmation when the supplied file cannot close the issue.

Do not introduce external metadata, remembered titles, guessed coauthors, or online search results when the work is bounded to supplied files.

## Separate finding states

Use three substantive states, regardless of the report's headings:

- **Confirmed discrepancy:** the manuscript itself proves that the callout and end list cannot both remain as written.
- **Author decision required:** the manuscript proves a gap or ambiguity but does not contain enough evidence to choose the final wording or full record.
- **Cleared near match:** two forms look different but resolve to the same identity under a defensible normalization or citation grammar rule.

Do not use `confirmed` merely because a string comparison failed. Do not use `query` to avoid a decision the manuscript can make. Do not omit cleared near matches when a later editor could plausibly “correct” them incorrectly.

## Dispose cited-only items

When a body callout has no plausible end record:

- record every occurrence location;
- quote the exact author-year form;
- state that no corresponding end entry was found after the complete two-way inventory;
- request the full reference or removal/replacement of the unsupported callout;
- do not draft a complete reference from memory.

If claim context suggests one existing record but identity fields do not match, treat that as a candidate conflict rather than silently linking it.

## Dispose listed-only items

For an end record with no formal callout:

- distinguish a true reference list from a broader bibliography;
- check captions, notes, appendices, and narrative citations again;
- note any informal name mention that may show intended use;
- ask whether to insert a supported callout or remove the unused entry.

Do not recommend insertion solely to preserve the list. A callout must support an actual claim. Do not recommend deletion when the manuscript contains an unresolved informal attribution that may need conversion to a formal citation.

## Dispose identity and rendering conflicts

When the work identity is established but the callout form is wrong, propose the smallest local repair:

- correct the credited author token;
- use the locally consistent form for one, two, or multiple authors;
- add, remove, or change a year suffix only after examining its collision set;
- split compact multi-year prose when the years correspond to different author groups.

Preserve surrounding scientific prose. Citation reconciliation does not authorize rewriting the claim.

## Make repairs executable

For every confirmed repair occurrence, create a patch-register row with a stable identifier, the
occurrence or atomic-component location, the exact current form, the exact proposed form, the
governing reference record, and a short evidence reason. Repeated uses of one defective form
remain separate rows so production can check them off individually. A disposition such as “fix
citation” is not executable. If a compact multi-year construction must be split, give one patch
row per atomic component and state the order or separator needed to keep the author groups
distinct. Keep author-query items out of the confirmed patch register; they belong in the
unresolved queue with a precise question and the smallest supported alternatives.

The final handoff should also state the control totals for the two ledgers and the number of
patches that can be applied without author input. This lets production distinguish a known
copyediting workload from an open bibliographic decision.

Add an action-ownership matrix with one row per finding. Use a controlled owner such as
`author`, `editor`, or `copyeditor`, state whether the action is confirmed or on hold, and name
the precondition that permits execution. A copyeditor row should point to a retained supplied
record; an author/editor hold should name the missing confirmation or scope choice. This matrix
must agree with the confirmed patch register rather than silently promoting a query into a fix.

When the body names an organization but the candidate record credits people, state both possible dispositions and request author confirmation unless the manuscript itself establishes the credited form.

## Make each finding independently reviewable

Each finding must carry:

`state | location | exact item | counterpart or absence | evidence | recommended action`

Equivalent prose or table layouts are acceptable. The record must still let an editor verify the issue without searching the entire manuscript.

Use the manuscript's printed page and line numbers when present. Add physical page or a short anchor phrase when extraction makes the printed locator ambiguous. For missing-counterpart claims, cite both the occurrence and the completed end-list search; absence is a two-sided result.

If one malformed construction contains multiple works, create separate finding units when the works need different repairs. If repeated occurrences share exactly one defect and disposition, one finding may list all locations.

## Record cleared near matches

For every high-risk normalization, record:

`form A | form B | why they resolve | no-change decision`

Prioritize surname particles, diacritics, acronym expansions, capitalization, and inherited-year shorthand. Do not flood the report with ordinary whitespace or punctuation equivalence.

## Close the report

Reconcile the final handoff against both ledgers:

- every no-record callout has a finding;
- every no-callout record has a finding or a documented scope exception;
- every multiple-candidate item is resolved or queried;
- every callout-form defect has a minimal proposed correction;
- every tempting normalized identity is either used or cleared;
- no action adds facts absent from the manuscript.

State readiness in operational terms. A manuscript with unresolved missing records is not reference-ready even if all easy form corrections are known. Summarize what an author must supply separately from what a copyeditor can repair directly.

Stop when the evidence boundary is reached. The correct final action may be a precise query, not a confident repair.
