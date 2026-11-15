---
name: audit-revenue-position-papers
description: Review an issuer's revenue-recognition position papers, regulatory correspondence, draft filings, and final financial-statement disclosures. Use when an audit reviewer must resolve version conflicts, assess performance obligations and recognition patterns, test principal-versus-agent conclusions, review contract-cost amortization, preserve unresolved evidence gaps, and produce a traceable issue ledger under ASC 606 or an equivalent control-transfer model.
---

# Audit Revenue Position Papers

## Objective

Turn a mixed record of staff questions, management assertions, interim drafts, and final reporting into an audit review that says what is established, what changed, and what still requires evidence.

Do not treat a persuasive response letter as audit evidence. Do not treat a later file as automatically correct. Establish what each document is, what reporting date it addresses, and whether later financial statements adopt, reject, or qualify the earlier position.

## Deliverable Standard

Build an issue ledger before drafting conclusions. Keep one row for each conclusion that can carry its own evidence state. Separate two topics when one is supported and the other remains open, even if management discussed them together.

Use the accounting proposition, not the document paragraph, as the row boundary. Split matters such as promise identification, transaction-price allocation, materiality or disclosure, and control remediation when each can reach a different conclusion. Likewise, assess contract-cost eligibility, economic commensurateness, and amortization pattern separately. Do not create a separate row merely because an adopted policy still needs ordinary audit testing: state the policy conclusion in the conclusion field and preserve the untested evidence in the residual-evidence field.

For every row, preserve these elements:

1. the accounting question;
2. the conclusion at the review date;
3. the financial-statement or control consequence;
4. the reason the evidence supports that conclusion;
5. a resolvable source location;
6. evidence still needed, including an explicit statement when none is needed; and
7. an audit response that would close the point.

A source reference is resolvable only when a reviewer can navigate to the controlling passage without repeating the research. Name the file and a comment number, note, page, heading, or other stable locator. A bare file name is not enough for a central conclusion.

## Prepare Searchable Evidence Views

Do not page through a large filing as raw HTML. Preserve the supplied originals, but create temporary plain-text views for search and comparison. From this skill directory, run:

```bash
python3 scripts/extract_evidence_text.py /workspace/*.pdf /workspace/*.htm /workspace/*.html --output-dir /tmp/revenue-evidence
```

The script ignores unmatched globs, extracts PDF text with `pdftotext`, removes HTML markup with the standard parser, and writes only under the requested temporary directory. Search those views by comment number, note heading, and distinctive accounting phrase. Cite the original file and its real page, comment, note, or section, never the temporary filename or generated line number.

Before reading details, create an issue inventory. For a platform or digital-goods record, make a separate inventory line for each applicable proposition in these families:

| Family | Separately testable propositions |
| --- | --- |
| contract unit | earlier accounting unit; final accounting unit; cash receipt versus transfer commencement |
| satisfaction | each item or service pattern; unclassified population; estimate used for an over-time pattern |
| presentation | each supplier or intermediary relationship analyzed for principal-agent presentation |
| contract costs | capitalization eligibility and recovery; fee commensurateness; amortization pattern |
| bundled offering | promised benefits; allocation and timing; materiality; policy disclosure or disaggregation |
| correction and control | accounting error; remediation implementation; management conclusion; formal management assessment; external-auditor opinion |
| later estimate | affected policy population; estimate-versus-error classification; effective dates; revenue and related-cost effects; audit coverage |

This table is a decomposition check, not a list of required findings. Include only propositions present and material in the supplied record. Do not create a generic chronology or “source hierarchy” row. Do not merge inventory lines merely to shorten the final ledger.

## The Review Sequence

### 1. Freeze the reporting snapshot

List the supplied documents in chronological and authority order. Record separately:

- the date and form of each document;
- whether it is a staff question, management response, draft disclosure, or final reporting record;
- the accounting period affected; and
- whether it contains an assertion, evidence, a revision, or an issued conclusion.

Use chronology to find changes, not to decide truth by itself. A final issued record generally controls the description of the adopted policy, while the earlier correspondence remains necessary to understand the disputed judgment and the evidence management offered.

### 2. Convert the record into issue chains

For each revenue topic, build a compact chain:

```text
question -> management position -> draft implementation -> final implementation -> residual evidence
```

Do not stop at a management promise to revise. Locate the actual revised wording. Conversely, do not call a response deficient merely because the final disclosure is shorter; determine whether the final text communicates the operative policy and whether the detailed support belongs in the audit file rather than the note.

When the chain changes direction, write the conflict explicitly. Classify the nature of the change before deciding its consequence: changed facts, better information, a revised estimate, a different accounting unit, a corrected error, or a disclosure clarification can look similar in prose but require different review responses.

After building the chains, perform an atomicity pass. A row is too broad when its conclusion needs “and” to join propositions that could have different record states, or when its audit response must test unrelated populations. Split it before drafting. Conversely, keep ordinary transaction or control testing in residual evidence when it supports application of an already-adopted policy rather than a different accounting conclusion.

### 3. Identify the accounting unit before timing or presentation

Do not begin with the cash receipt, invoice, platform label, or gross amount. First answer:

- Who is the customer for the contract under review?
- What promised good or service does that customer expect?
- Which promises are capable of providing benefit on their own or with available resources?
- Which promises are separately identifiable in the contract context?
- Is the entity integrating inputs into a combined output, or merely describing several features as one experience?

The contract unit drives the rest of the analysis. An error here propagates into recognition timing, deferral, gross-versus-net presentation, and cost amortization.

Cash collection is not evidence of satisfaction. A payment can establish enforceable rights and fund a contract liability while the promised transfer occurs later. If management starts recognition at purchase, identify what service begins transferring at that event and test whether that service is the actual promise rather than a convenient proxy.

### 4. Evaluate the satisfaction pattern from the promise's nature

Determine whether the promise transfers at a point in time or over time. For an over-time promise, determine what activity faithfully depicts progress. Do not accept a customer-tenure measure merely because the data exists.

Ask:

- What benefit remains after a customer action?
- Can the customer continue to use or display an item?
- Does an item disappear or cease to provide benefit when consumed?
- Is the entity standing ready to maintain availability?
- Is the population homogeneous enough for one pattern?
- If it is not homogeneous, can the entity identify or estimate the classes?

A lack of detailed systems data is an evidence gap, not an accounting objective. It may require an estimate or a temporary proxy, but the selected policy must still reflect the promise. Require management to explain why the proxy represents transfer and what process will refine the estimate when better data becomes available.

For digital-item and related-cost branches, read [digital-items-and-contract-costs.md](references/digital-items-and-contract-costs.md) before concluding.

### 5. Separate every principal-agent relationship

Do not perform one platform-wide gross-versus-net analysis. A content supplier, marketplace participant, app store, payment processor, and end user occupy different relationships. Each relationship can have a different customer, specified service, and control path.

Identify the specified good or service before using the control indicators. Primary responsibility, inventory exposure, and price discretion support the analysis but do not replace the control principle. Contract language that calls the entity a facilitator is relevant and must be reconciled with operating facts; it is not decisive by label alone.

For any gross-versus-net issue, read [principal-agent.md](references/principal-agent.md) and apply its evidence matrix.

### 6. Follow revenue changes into contract costs

For a deferred acquisition or processing cost, test three different questions:

1. Would the cost have been incurred without obtaining the contract?
2. Is recovery expected?
3. Does amortization follow the transfer of the goods or services to which the cost relates?

Do not assume the revenue period and cost period remain aligned after the revenue policy changes. Reperform the mapping by item or contract population. Treat statements about renewal or subsequent-sale charges as assertions that require rate schedules, channel contracts, and transaction data.

### 7. Treat immateriality as a measured conclusion

Management may conclude that an additional promise, revenue stream, or disclosure is immaterial. That conclusion requires both qualitative and quantitative support.

Ask for:

- the affected revenue and deferred balance;
- the standalone value or allocation basis;
- sensitivity to a separate accounting unit;
- whether the matter masks a change in trend or control failure; and
- whether the final note actually states the adopted policy clearly enough.

Treat disclosure and recognition as separate assertions. A note can omit detail that exists in the accounting file, and a detailed accounting analysis can still require disclosure. State which assertion the available evidence addresses and identify what would be needed to address the other.

### 8. Connect a correction to the control conclusion

When the final record identifies an error, restatement, or material weakness, trace it back to the decision that failed. Distinguish:

- the accounting correction;
- the affected periods and balances;
- the process or control that failed;
- the revised policy and estimate process; and
- the evidence needed to support remediation and current-period application.

Determine whether the formal reporting record supersedes an earlier position or merely adds context. Document the superseding language rather than relying on chronology or the amount of detail in either document.

When the record spans later reporting periods, do not use one “remediated” label for every date. Track separately: measures planned, measures implemented, management's conclusion about a specific deficiency, management's formal framework-based ICFR assessment, and the external auditor's ICFR opinion. A financial-statement audit opinion is not an ICFR opinion. A transition-period filing can report a specific weakness eliminated while expressly omitting formal management assessment and auditor attestation; preserve each scope boundary. A later dated control opinion supports that later date and does not retroactively create assurance for an earlier date.

### 9. Reconcile later estimate changes

For every later change to an estimate used in revenue recognition:

1. identify the accounting policy and exact population to which the estimate applies;
2. record each effective date and old-to-new input;
3. determine whether the issuer reports a change in estimate, error correction, or principle change;
4. trace both revenue and related contract-cost effects;
5. verify prospective or retrospective application; and
6. distinguish the financial-statement and control conclusions from any critical-audit-matter description.

Do not let shorthand elsewhere in a filing broaden a population-specific estimate. Read it with the complete accounting note. A critical audit matter can identify the estimates that required difficult auditor judgment and describe procedures performed; it does not create a standalone opinion on an input or replace the underlying audit evidence.

## Evidence Hierarchy

Use this hierarchy for the purpose it actually serves:

| Record | What it can establish | What it cannot establish alone |
| --- | --- | --- |
| final financial statements and final prospectus | adopted policy, recorded correction, disclosed control state | underlying operating evidence or design effectiveness |
| later annual report | subsequent policy, estimate, management-assessment, and remediation state at its own reporting date | retroactive assurance for an earlier date |
| independent auditor report | opinion within its stated financial-statement or ICFR scope; described critical-audit-matter work | a separate opinion on an estimate or a scope the report excludes |
| amended filing | policy stated at that draft date | that the policy survived to issuance |
| management response | management's rationale and promised revisions | audit support or final implementation |
| regulator comment | the challenged question and requested support | the entity's ultimate accounting answer |
| commercial description | product terms and user-facing features | accounting unit or recognition pattern by itself |

When sources conflict, cite both sides of the conflict. A conclusion that cites only the final line but never identifies the superseded position is not a closed review of the change.

## Conclusion Discipline

Keep two layers distinct:

1. **record state** - whether the issued reporting record adopts, supersedes, modifies, or omits the accounting proposition; and
2. **audit evidence state** - whether contracts, data, estimates, and controls substantiate application of that proposition.

The conclusion field should lead with the record state when the engagement is a filing-close review. A final disclosure can establish the policy even when transaction testing remains; put that testing gap in residual evidence. Use an unresolved conclusion when the accounting proposition itself is absent, depends on an unsubstantiated materiality or allocation assertion, or cannot be selected from the supplied record. For controls, a disclosed remediation plan does not establish operating effectiveness.

Use a conclusion state that expresses evidence, not tone. Equivalent labels are acceptable, but preserve these meanings:

- established by the final record and supported for review;
- prior position rejected or superseded by the final record;
- retained only with a modified basis or application;
- unresolved because the supplied evidence cannot close it.

Do not force every row into a favorable or adverse binary. An unresolved item is correct when the record lacks the evidence needed to evaluate the claim. State exactly what is absent and what procedure would resolve it.

Avoid vague conclusions such as “appears reasonable” or “needs further review.” State the accounting proposition, the evidence state, and the consequence.

## Audit-Response Design

Tie the procedure to the assertion that could fail. Choose among procedures such as:

- inspect executed customer, developer, and channel contracts;
- test system configuration and change management for item classification;
- reconcile source events to the revenue subledger and general ledger;
- sample transactions across each item class and distribution channel;
- reperform cohort, attrition, allocation, or amortization calculations;
- compare historical estimates with subsequent outcomes;
- inspect dispute, refund, chargeback, takedown, and support records;
- test the completeness of the unclassified population;
- evaluate management's quantitative and qualitative materiality analysis; and
- test remediation design and operating effectiveness.

“Obtain support” is not a complete response. Name the evidence, population, assertion, and expected decision.

## Final Quality Review

Before delivery, verify all of the following:

- Every material staff question related to revenue or associated contract costs is either closed or carried as open.
- Every earlier accounting position has been compared with the final record.
- No management response is treated as self-validating evidence.
- Every gross-versus-net conclusion identifies the relationship and specified service.
- Every recognition pattern follows the nature of the promise or explicitly documents an estimate limitation.
- Every cost-amortization conclusion follows the related transfer pattern.
- Every materiality claim has an identified quantitative basis or remains open.
- Every conclusion has a source locator and every open item has a closing procedure.
- The ledger does not contain two rows with incompatible conclusions about the same accounting unit.
- Each row carries only one accounting proposition and one record-state conclusion; independently supportable allocation, materiality, cost, and remediation questions are not bundled.
- Supporting audit work that remains open has not changed an otherwise adopted policy into an unresolved accounting conclusion.

Deliver only conclusions supportable at the review date. Preserve uncertainty where the record stops.
