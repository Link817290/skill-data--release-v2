# Scoring Rubric

The package defines two independent standards for the same deliverable.

`reward_strict` is a continuous professional capability score in `[0, 1]`. It asks how well the privacy review was performed. A missing or unreadable PDF, altered source material, a missing or reordered source page, or a recoverable direct employee identifier receives zero.

`reward_lenient` is a binary business-usability score in `{0, 1}`. It requires
both the complete delivery contract and the core privacy controls below.

`reward` is an alias of `reward_strict`.

| Dimension | Weight | What a high-scoring output demonstrates |
| --- | ---: | --- |
| Selective privacy | 15% | Removes direct contact and residential details, government identifiers, dates, signatures, person-specific tax choices, work-authorization declarations, other out-of-purpose responses, and every original name. Removal must hold across searchable text, widgets, annotations, metadata, image-backed pages, and the generated register. |
| Required retention | 10% | Preserves the application role, work location, education history, employing agency, payroll system and agency number, plus generic employer-side completion notes in the eligibility record. It distinguishes these needed review facts from private choices instead of blanking whole sections. |
| Pseudonym consistency | 5% | Replaces each source name component with the requested alias component in its original response region across AcroForm, flattened-text, and scan-backed records, without retaining the old value or turning name fields into black bars. |
| Purpose-based disposition | 50% | Classifies every omitted response by business meaning, places the applicable reason code in its original page region, and carries the same page/sequence/code/outcome decision into the register. Compact choice marks remain opaque and nearby prompts and rules remain legible. |
| Control and navigation | 5% | Provides a searchable control sheet with source-derived field-action counts and logical ranges, correct hierarchical bookmarks, logical page labels, and the specified controlled metadata. |
| Register structure | 5% | Provides three record-specific register pages with the requested headings, columns, field-row counts, and no original response values. |
| Document fidelity | 7% | Keeps all eight source pages in order after the control sheet with each source page's original box and rotation, preserves printed anchors, and keeps unaffected text searchable rather than rebuilding the source pages from images. |
| Delivery hygiene | 3% | Produces one valid PDF, removes XML metadata, and leaves no live widgets or annotations that could retain excluded values. |

The validator derives source response values, field-action counts, response-region classifications, page geometry, and the expected source order directly from the supplied PDFs. It does not compare the output to a golden PDF. Generic short checkbox states are assessed in their response regions rather than treated as global keywords.

## Strict scoring formula

Let `r` be the observed required-retention fraction. `reward_strict` is `required_retention + document_fidelity + r x (selective_privacy + pseudonym_consistency + purpose_based_disposition + control_and_navigation + register_structure + delivery_hygiene)`, where each named component is its listed weight times its own observed fraction. This dependency prevents an empty or rebuilt packet from earning credit merely because excluded data is absent. The purpose-based-disposition fraction is the mean of region-local reason decisions and the required register rows, so a missing, duplicate, miscoded, or out-of-sequence row loses its proportional share instead of multiplying the whole 50% dimension by a fixed factor. Full register reconciliation remains a Lenient must-have.

For private tax-declaration choices represented by source vector marks, the privacy and purpose-disposition components are additionally multiplied by the fraction of declaration regions whose source response mark was destructively removed. This confines a recoverable choice to the two professional controls it actually defeats while retaining continuous credit for independently correct source preservation, navigation, and other redactions. It still makes `reward_lenient = 0`. Readability failure, altered supplied PDFs, a missing or reordered source page, a recoverable source-derived direct identifier in text or metadata, or an unrequested embedded attachment sets the strict score to `0.0` because those defects compromise the identity or provenance of the whole packet. A missing or incomplete control sheet or register loses its own dimension rather than masking otherwise inspectable source-page work. Otherwise partial completion receives proportional credit within each dimension.

## Lenient scoring formula

`reward_lenient` is `1` only when every clause of the delivery contract holds
and the packet has no direct or recoverable private payload, preserves every
required response, applies aliases and reason codes consistently, reconciles
every register row, and carries a correct control sheet. It is `0` otherwise.
The delivery clauses are:

- the deliverable exists at the requested path;
- the file opens as a PDF, is not password protected, and has at least one page;
- the packet carries every requested part: the control sheet, the eight source pages, and the three register pages;
- the first page is the control sheet, announced by its heading and naming the review alias;
- the control sheet carries a field slot for the disposition-register range and for every action code, `ALIAS` plus each redaction reason code;
- every page of the source block yields extractable text rather than being handed over as bare imagery;
- every register page announces itself as a disposition register;
- every register page holds at least one disposed row, so the register is filled in rather than delivered as an empty template;
- the document carries bookmark and logical-page-label objects.

This lens is not the strict score put through a cutoff. It directly evaluates
the source-bound must-have privacy and delivery conditions; it does not cap or
otherwise change the continuous strict score.

The two lenses therefore dissociate in both directions. A packet built to the requested twelve-part shape, with a populated control sheet and populated register pages, but assembled over untouched source responses, satisfies the delivery contract and scores zero under the strict lens. Conversely, a packet whose surviving pages are edited to the reference standard scores zero here when it ships one register page short, when it ships without its control sheet, or when its bookmark and page-label objects are missing, while retaining most or nearly all of its strict credit. The verifier reports both lenses independently so infrastructure failures cannot be confused with a valid zero.

Because passing is defined by this lens, `pass_rate` is the mean of `reward_lenient` over a group. The package defines no other passing notion.

## Deterministic anchors

The checks accept different correct editing implementations. They observe source-derived excluded strings, retained values, region-local alias components and reason codes, black-pixel coverage, source-derived control totals and register rows, PDF outlines and page-label rules, controlled metadata, source page boxes and order anchors, and widget and annotation removal. Keyword stuffing outside the relevant response region, control-table row, or ordered register row cannot replace the page-order, region, and privacy checks.

## Worksheet repair clarification

A home-phone area code and number are one semantic response, with all source fragments inspected/redacted but one register row and action count. Ledger columns are located by their headers and may be reordered. Equivalent privacy-review control headings and logical-page ranges are accepted, including `to`, `through`, a hyphenated range, or an equivalent separated presentation. Register pages must identify their source record and carry the required disposition fields, but no fixed disclaimer sentence is required; the actual retention and leakage checks establish whether original response values survive. Unrequested embedded attachments and direct identifiers in PDF/XMP metadata set strict to zero. Source private-choice response marks surviving below opaque overlays proportionally reduce the privacy and purpose-disposition dimensions and fail the Lenient lens. Empty checkbox artwork and white layout strokes do not count as recoverable responses. The reference packet removes contained vector objects destructively.
