---
name: selective-record-redaction
description: Classify filled form content by review purpose, assign stable disposition reasons, and reconcile action counts so direct identifiers and person-specific declarations are removed while necessary professional and administrative context remains. Use when producing auditable privacy-minimized HR, compliance, case, or routing copies from completed records.
---

# Selective Record Redaction

## Start from purpose, not sensitivity alone

A useful review copy minimizes data without erasing the business evidence under review. Write a one-line purpose statement and classify every entered response against it. Use four decisions:

- `retain-professional`: role, qualification, education, or other work evidence required by the review;
- `retain-administrative`: organization, unit, routing code, or generic workflow note that does not identify the person;
- `redact-direct`: names, government identifiers, residential or contact details, signatures, and entered dates;
- `redact-declaration`: person-specific elections, attestations, eligibility status, financial choices, and optional disclosures.

An entered phrase that is neither professional evidence nor administrative routing information defaults to redaction. Printed template language is not an entered response and remains part of the shell.

## Classify the complement of an explicit retain list

When the assignment names the only response categories that may remain, treat that list as an allowlist rather than as examples. Apply one exhaustive decision pass in this order:

1. Before looking at entered values, translate each allowed category into the smallest record-scoped rule justified by the assignment.
2. Exclude printed shell content from the response inventory.
3. Assign required controlled aliases to identity responses.
4. Assign specific removal codes to direct contact, identifiers, dates, signatures, financial elections, declarations, and other named sensitive classes.
5. Retain a remaining response only when it positively matches one of the predeclared rules for that source record.
6. Assign the residual removal code to every other entered response.

Never use `retain` as the fallback for an unrecognized prompt. A response does not become professional history merely because it appears on an employment or compliance form, and it does not become administrative routing merely because an office might find it useful.

Professional history normally means evidence of roles, duties, qualifications, education, credentials, or work assignments named by the review purpose. Administrative routing normally means an organization, unit, system, agency code, work location, or generic employer-side completion note named by the purpose. Applicant- or employee-originated availability, scheduling, desired compensation, referral source, willingness, legal-history response, contact permission, attestation, acknowledgment, optional explanation, and similar logistics remain outside those classes unless the assignment explicitly retains them.

Rules are record-scoped. Permission to retain employer-side completion notes in one record does not authorize applicant-authored workflow text in another record. Do not invent an `administrative` catch-all when the assignment names narrower items.

Retain actual evidence, not a pointer to evidence. A response that refers a reviewer to an attachment is not itself a role, qualification, or education history. A completion directive, submission instruction, permission, willingness response, and template-like prose stored in a nonempty widget are entered responses, even when they look like document instructions. They remain in the residual class unless an allowlist rule expressly covers that response type in that record.

After classification, group retained ledger entries by the allowlist rule that justified them. Any retained entry without a named rule and matching record scope is an error. For each group, read the rule basis beside every nearby prompt and try to disprove the match; a rule derived from an observed answer rather than from the assignment is invalid. Then confirm that the union of alias, removal, and justified-retain entries equals the entire response inventory.

## Classify in context

Read the prompt, the entered value, and the stated review purpose together. A place can be professional context when it names a work assignment, but direct when it identifies a residence. An organization can be administrative context when it names the employer, but direct when it names a personal financial institution. A checkbox is data: its selected state can reveal tax, citizenship, medical, or demographic information even when no text was entered.

Do not use pattern matching alone. A short number can be a routing code that should remain or a personal identifier that must go. A generic note written in an employer-only section can remain even if the same words would be inappropriate as an applicant answer.

## Build a closed decision ledger

Use [mapping_ledger.md](references/mapping_ledger.md) as temporary working memory. Account for every nonempty widget and every visible entered region. Each ledger row needs a decision, an action code, and a reason tied to purpose. The ledger is not a deliverable and should not be stored with the output.

When the output requires action counts or a disposition register, load `pdf-disposition-ledgers` and validate a structured ledger before drawing either page. Its coverage check catches filled AcroForm controls that were never assigned a retain, alias, or removal decision.

Preserve exact spelling for retained content. Do not correct, infer, summarize, or replace excluded content with invented neutral values unless the assignment explicitly requires a controlled alias. When visible reason labels are required, select the code from the response's meaning, not from the shape of its value. A postal code is contact information; a similarly short agency number can be retained administrative routing information.

## Reconcile an action summary

Count source response fields, not drawing rectangles. A wrapped value may need two physical marks but remains one action; a single full-name field pseudonymized once remains one alias action. Summarize counts from the closed ledger and then reconcile the sum back to all affected fields before authoring a control sheet. Keep retained fields out of the action totals.

Use stable, mutually exclusive reason codes. Keep identity aliasing separate from omission codes; separate contact, government identifier, birth date, signature, entered date, financial election, authorization declaration, and residual out-of-purpose content when the review specification distinguishes them.

When a deliverable needs a field-level disposition register, sort ledger rows by source page and response geometry rather than by PDF object number or field name. Use the response rectangle's top edge and then left edge as stable reading-order keys. Number each record's sorted actions independently. Record the logical source page, sequence, action code, and result, but never repeat an excluded source value in the audit record.

## Resolve mixed sections

A single page can contain both permitted and excluded entries. Redact at field or response-region granularity. Do not remove an entire section merely because one response is private, and do not keep a whole section merely because one entry is useful.

Employee and applicant sections usually require field-by-field classification. Employer-only sections may contain generic operational examples that are administrative rather than personal. Voluntary, attestation, tax, and eligibility sections require special attention because selected states disclose information even without identifiers.

## Final privacy review

Review the output in two directions:

1. Starting from each source response, confirm a deliberate retain or redact decision.
2. Starting from each retained output entry, confirm that the stated purpose requires it and that it does not enable direct contact or reveal a person-specific declaration.

Then search the final object layer and rendered pages for each excluded source value. Confirm that every labeled bar carries the ledger's code and that the control totals equal the ledger totals. A field is not safely redacted until both representations are clear.
