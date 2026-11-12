---
name: author-date-citation-inventory
description: Build complete, occurrence-level inventories of author-date callouts and end-reference records. Use when a manuscript must be reconciled in both directions across parenthetical, narrative, grouped, inherited-author, institutional-author, caption, table-note, appendix, and multi-year citation forms.
---

# Author-Date Citation Inventory

Construct two independent ledgers before deciding whether anything matches. The first represents citation occurrences; the second represents reference records. Early identity guesses hide missing items and create false matches.

## Fix the audit scope

Determine which document regions are active scholarly content. Include body prose, captions, table notes, appendices, and other supplied components when they use the manuscript's citation system. Exclude navigation furniture, running headers, submission metadata, correspondence, and examples that are not adopted text.

Determine from the manuscript whether the end section is a reference list, a broader bibliography, or a mixed list. Do not assume that every listed-only record is defective until the document's own practice supports that rule.

## Build the occurrence ledger

Give every callout occurrence a stable scratch identifier and record:

`occurrence | location | exact callout | parsed author token | parsed year token | form | explicit/inherited status | context anchor`

Inventory each form separately:

1. Parenthetical: `(Rivera et al., 2018)`.
2. Narrative: `Rivera et al. (2018)`.
3. Grouped: `(Rivera, 2018; Chen and Okafor, 2020)`.
4. Shared-author years: `(Rivera, 2017, 2018a, 2021)`.
5. Narrative shared years: `Rivera (2017, 2018)`.
6. Institutional author: `(Coastal Authority, 2019)`.
7. Acronym author after an explicit introduction.
8. Citations embedded in captions, notes, or appendices.

Split a grouped callout into atomic author-year candidates while keeping the original group identifier. Carry the last explicit author only across year tokens that are grammatically attached to it. Never carry an author across a semicolon into a new citation unit.

For each row, classify the surface grammar as narrative, parenthetical, grouped, or compact. Mark a year or author as inherited when the text attaches it to an earlier author token rather than repeating the token. Preserve mixed status for a compact group whose components are not equally explicit; this is an audit fact, not a proposed correction.

Do not classify ordinary dates, study periods, page ranges, dimensions, equation tags, or publication-history dates as callouts. A year in parentheses is not enough: require an author expression in the same citation construction or a defensible narrative author immediately before it.

## Capture narrative citations

Search parenthetical patterns first for orientation, then scan every year occurrence to recover narrative forms. For a bare year such as `(2018)`, inspect the preceding clause for a person or organization functioning as the grammatical source.

Watch for line and column breaks between the author and year. A layout extractor may place the year on the next line; a raw extractor may insert headers between them. Bind the occurrence only after checking the physical page.

## Maintain a non-citation date register

During the same scan, retain date-like expressions that could be mistaken for citations: publication-history dates, study and calibration ranges, scenario horizons, table values, table periods, and figure-caption periods. Keep one row for each page-local expression, combining repetitions only when they have the same local meaning. Identical running furniture may instead be represented by one explicit scope rule with a representative page and the covered page range. Record the physical and printed page, the exact source expression, a short surrounding phrase, and the reason it is not an author-year callout. A bare year or a range is not a citation without an author expression in the same construction.

## Expand compact citation grammar

Preserve what is written while expanding the comparison candidates:

- `(Rivera et al., 2018, 2020)` becomes two candidates with the same author token.
- `(Rivera, 2018a,b)` becomes two suffix candidates.
- `Rivera (2018, 2020) and Chen (2021)` becomes three candidates, not one.
- `(Rivera and Chen, 2018; 2020)` is ambiguous unless the document's punctuation clearly assigns 2020 to the same authors; flag the parse for review.

Do not silently repair malformed punctuation during inventory. Preserve the exact form and add a parse note.

## Build the reference ledger independently

Start from the actual end-section boundary. Give each visible entry one record with:

`record | page | exact head | full author string | year/suffix | title anchor | continuation pages`

Identify entry starts from the local reference style rather than capitalization alone. Wrapped titles, URLs, publishers, and journal names are continuations. In multi-column PDFs, verify that a line from the opposite column was not attached to the record.

Capture all listed records, including records that appear unused. Do not begin with callout names and search only for those; that makes listed-only items impossible to discover.

Record credited-author cardinality from the supplied entry (one, two, or multiple/ellipsized). Also record the follow-up owner that the evidence supports: copyeditor for a confirmed form repair, author/editor for a missing or credited-author decision, or editor for a scope decision. Do not infer cardinality from `et al.` in the body.

## Create a candidate matrix

After both ledgers are closed, create candidate links rather than final links. For each atomic callout, list every plausible record and the evidence for candidacy:

- exact first-author token plus year;
- normalized surname variant plus year;
- explicit acronym-to-organization expansion plus year;
- compatible suffix family;
- title or nearby context that distinguishes candidates.

Likewise, for each reference record, list all occurrence candidates. A record with no candidate remains visible as a listed-only candidate. A callout with no candidate remains visible as a cited-only candidate.

## Close coverage

Reconcile counts at three levels:

- raw visible callout groups;
- atomic author-year candidates after expansion;
- unique author-year identities after normalization.

Keep repeated uses as separate occurrences even when they resolve to one record. Repetition proves use and supplies stronger location evidence; it is not a duplicate reference.

Finish with explicit queues for `unparsed`, `one candidate`, `multiple candidates`, `no record candidate`, and `no callout candidate`. These are scratch states, not final editorial decisions.

Re-read the first and last body pages, every page containing a multiline citation, and every end-list column transition. Do not declare the inventory complete while an unparsed year-bearing construction remains.

## Render a release-control ledger

When the deliverable is an editorial handoff, carry the closed ledgers into the report rather
than reporting only exceptions. Give every body callout occurrence a stable row identifier
and preserve repeated uses as separate rows. Give every end-list record its own row identifier,
including records that ultimately have no callout. Each row should expose its page anchor,
the exact evidence form, its atomic author-year components (or record year), and a mapping
status such as `linked`, `cited-only`, `listed-only`, `candidate`, or `ambiguous`.

Add a bidirectional control section that states the totals for raw callout groups, atomic
components, unique linked records, end-list records, cited-only components, listed-only records,
and unresolved candidate links. The totals must reconcile to the row identifiers. A mapping
table or explicit row-to-record lines should make it possible to trace a body row to its
counterpart without searching the whole report.

Do not collapse the ledger to a set of author-year strings. A compact group, a narrative
callout split across lines, and two occurrences of the same work remain distinct occurrence
rows even when their final identity is the same.

Add a collision register for every repeated author-year stem, suffix family, compact multi-year
construction, or unresolved candidate set. Each row names the body components, candidate
record identifiers, whether the year or suffix is explicit or inherited, and the resulting state.
