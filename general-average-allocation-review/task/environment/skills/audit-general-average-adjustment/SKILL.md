---
name: audit-general-average-adjustment
description: Review issued general-average adjustments and later liability records for maritime claims work. Use when reconciling general-average allowances, contributory values, mixed contractual rule sets, ship/cargo/freight/equipment/fuel allocations, securities and payments, or when a judgment or fault allegation changes recoverability without necessarily changing the historical quantum.
---

# Audit General Average Adjustments

## Outcome and operating boundary

Produce an auditable claims position, not a fresh adjustment from raw vouchers and not
an opinion on documents that were not supplied. Keep these four ledgers separate:

1. **Authority and regime**: contract populations, adjustment rules, propositions and
   their status through the decision chain.
2. **Allowances**: admitted general average, particular average, excluded or split
   expenditure, commission, interest and fees.
3. **Contributions**: distinct economic interests, contributory values, rates and funds.
4. **Recovery**: payment, security, deposits, disputed claims, operative entitlement and
   unresolved account actions.

An issued adjustment establishes its historical calculation. It does not alone prove that
each stated contribution remains enforceable. A later decision can change collection
without redrawing the historical fund.

## Execute in this order

Do not begin by reading every voucher page or every cited authority. The highest-risk
errors are misreporting a submission as a finding and assigning a cash or security action
to the wrong population.

1. Inventory the supplied files and identify the adjustment, account records, instruments,
   and each level of decision.
2. Read only the adjustment's basis, value, summary and distribution pages plus the last
   substantive paragraphs of each decision. Write a usable first version of both final
   deliverables: core values and fund bridge, a provisional recovery conclusion with citations,
   and at least one row for every economic interest. Never leave a headings-only placeholder.
3. Scan the decisions for issue-status language and the records for account-state statements.
   After each scan, inspect short excerpts in context and immediately add the supported rows or
   conclusions to the final deliverables.
4. Scan the classification notes, inspect the facing allocation columns, and add the material
   split, excluded, substitute-cost and rule-routing entries. Do not review the voucher sequence
   linearly.
5. Perform the final state and arithmetic checks before finishing.

Progressively writing the authority and recovery sections matters. If all drafting is deferred
until after the long adjustment review, low-visibility rejected grounds, ownership exceptions
and account-state boundaries disappear from the deliverable. Reserve the final evidence pass
for editing and controls, not first-time drafting.

## Fast evidence pass

Extract searchable text while preserving page layout:

```bash
pdfinfo <record.pdf>
pdftotext -layout <record.pdf> <scratch.txt>
```

For numbered judicial decisions, run the bundled status scanner before close reading:

```bash
python <skill-dir>/scripts/scan_decision_status.py <decision.pdf> [<decision.pdf> ...] \
  --max-per-document 16 --output <scratch-status.md>
```

The scanner finds candidate paragraphs; it does not decide their status. Read the
surrounding paragraph and relevant heading. Exclude discussions of cited cases unless the
court uses them to decide an issue in the case under review.

Run the account-state scanner across the adjustment, decisions, account records and
instruments:

```bash
python <skill-dir>/scripts/scan_account_states.py <record.pdf> [<record.pdf> ...] \
  --max-per-document 18 --output <scratch-accounts.md>
```

This scan is deliberately broad. Retain excerpts only after identifying the object and
population to which payment, security, custody or collection language refers.

For a long adjustment, surface classification notes before reading the voucher sequence:

```bash
python <skill-dir>/scripts/scan_adjustment_classifications.py <adjustment.pdf> \
  --max-per-document 24 --output <scratch-classifications.md>
```

For every retained hit, inspect the facing allocation columns as well as the prose note.
The prose explains the basis; the columns establish what was actually admitted or left out.

Keep tool output bounded. Do not print a whole extracted record or open more than about 80
source lines at once. Search the extracted text for a paragraph, page marker, voucher label or
amount, inspect only its immediate context, then write the result into the final deliverable
before opening another excerpt.

Create a scratch evidence register:

```text
proposition | speaker | source location | status at this level | later treatment | use
```

For legal propositions prefer numbered paragraphs. For amounts and classifications use
printed pages, schedules, vouchers or tables. A citation confirms a proposition only if
the cited location supports the entire statement.

## Pass 1: decision status and fault chain

### Attribute before concluding

For each material causal or legal account, identify who advanced it and what the court
did with it. Preserve the difference among:

- a party position or allegation;
- a trial finding of fact;
- a proposition assumed for argument;
- a ground accepted or rejected;
- an issue unnecessary to decide;
- a ground abandoned, withdrawn or not pursued;
- a finding expressly unchallenged or left undisturbed;
- the operative disposition.

Start with the first fact-finding decision. Review its conclusion and every immediately
following treatment of alternative theories. Then map each appeal ground and each
respondent alternative to its result. Finally read the last appellate summary and order.

An appeal dismissal normally leaves the order below in place. Do not turn successive
dismissals into separate contribution, refund or payment events. A rejected alternative
ground does not reverse a successful respondent's result on another ground. A proposition
repeated in an appellate introduction is not a new finding, but an expressly unchallenged
trial finding remains the factual platform.

Build the operative fault chain as a connected relation:

```text
act or defect -> duty and timing -> breach or exception -> factual causation
              -> actionable fault -> order -> affected recovery population
```

Do not award a protected navigation or management exception before testing the prior
seaworthiness obligation. If the governing material treats due diligence in work needed
to make the vessel seaworthy as non-delegable, competent personnel or adequate systems do
not establish due diligence when the entrusted work itself lacked reasonable care.

Before moving to arithmetic, write into the memo:

- the competing causal accounts and the court's resolution;
- each material trial alternative that was rejected or left undecided;
- the trial facts retained on appeal;
- the status of every actual appeal ground and respondent alternative;
- one cumulative disposition and its bounded collection effect.

Every relevant scanner hit labelled `scope`, `withdrawn`, `not_decided`, `rejected`, or
`result` must be represented in substance or marked irrelevant in scratch because it
concerns a cited authority rather than the case under review.

## Pass 2: recovery object and population

Before close reading, write the recovery table skeleton into the final memo, then populate
it from the account-state scan while sources are open. For every statement involving money,
identify the object paid or held. Payment of casualty
disbursement accounts, salvage, fees or another expenditure ledger does not establish
payment of contributions by cargo. Likewise, a percentage of consignments secured is not
a percentage of contributions paid.

Use one row per supported population:

```text
population | demand | security | deposit | contribution paid | litigation state
           | operative entitlement | action | missing evidence
```

Keep these states independent:

- security requested or posted;
- cash deposited on account;
- adjusted contribution stated;
- contribution actually paid;
- claim resisted or litigated;
- entitlement after the operative decision;
- refund, release, set-off or recourse status.

Record the source population and denominator of every percentage. A provisional deposit
rate is not the final contribution rate, and a bond or guarantee secures possible
liability rather than creating it.

For a statement that accounts were paid, locate the sentence defining which accounts were
examined and any exception. For security collection, separately record the secured
consignment population, who posted salvage security for whom, and any equipment interest
that provided security directly. For a trust or deposit account, distinguish historical
administration or allocation from a current balance and beneficial entitlement.

Scope the operative result to its parties and claim. Do not infer automatic refunds for
paid non-parties, blanket guarantee releases, coverage, limitation or recourse outcomes.
If account statements, instrument wording, settlement terms, limitation history or trust
ledger details are absent, state the specific open item and require account-level review.

## Pass 3: allowance ledger

Read the adjustment summary across all columns. A displayed gross invoice is not an
allowed amount. For each material control or note classify the amount before summing it:

- admitted common-safety sacrifice or expenditure;
- particular-average casualty damage;
- expense outside general average;
- split item with both admitted and remainder portions;
- commission, rule-dependent interest, fee or security cost;
- express zero allowance or unsupported sacrifice;
- unresolved item because supporting detail is absent.

Reconcile each printed section as:

```text
gross -> remainder or outside amount -> admitted general-average amount
```

Before aggregating, maintain a classification timeline:

```text
event/time | safety state | expenditure object | payer | gross | remainder | admitted
           | stated rule or saved-expense basis | source
```

Test each entry against three independent questions: when safety was obtained, whether the
cost substituted for an ordinary adventure expense, and whether the stated payer or payment
evidence says anything about the party that ultimately bears the allowance. A post-safety
cost may still be admitted on a saved-expense or refuge basis; an accident-related measure
may require a different rule route from a measure maintained for common safety.

Then bridge admitted principal through the stated commission base, applicable interest,
fees and each final fund. Keep different contractual rule columns separate. If the source
says detailed interest dates or bases are held elsewhere, reconcile the reported figures
but do not manufacture an independent recalculation.

Preserve negative findings. Original casualty repairs do not become sacrifice merely
because salvage occurred. A post-safety or split professional charge must follow the
adjuster's stated timing and basis, not the visual location of its gross invoice.

## Pass 4: contribution ledger

Reconstruct each economic interest before using the grand total:

- **Vessel**: sound value, particular-average deductions and any amount made good.
- **Cargo/freight**: destination or invoice basis, freight risk, casualty deductions and
  amounts made good. Do not add freight again if fully earned freight is embedded.
- **Containers/equipment**: ownership determines whether value is separate or already in
  cargo. Reconcile counts as well as values.
- **Bunkers/consumables**: follow what remained, was discharged, not returned, would have
  been consumed and was made good.

For mixed bill forms, record which population incorporates which adjustment rules. Do not
select the newest edition by preference. Identify the actual divergent item, allocate the
rule-specific funds to the applicable populations and only then present any blended rate.

Use a schedule with these concepts under any clear headings:

```text
row type | interest or population | basis | value | rate/share | contribution or amount
         | treatment/status | source
```

Check that interest values close to contributory capital, contributions close to the
applicable fund, mixed-population shares close to their property base, and the final
interest contributions close to the apportioned claim.

After choosing admissible interest rows, use the bundled arithmetic checker:

```bash
python <skill-dir>/scripts/check_allocation.py <scratch.csv> \
  --label-column <label> --value-column <value> --contribution-column <contribution>
```

The checker tests arithmetic only. It cannot decide ownership, classification, governing
rules or recoverability.

## Closing gate

Re-open both deliverables and check, in this order:

1. Every material decision-status row appears in the memo with its own pinpoint citation.
2. Party positions and rejected, withdrawn or unnecessary grounds are not stated as
   operative findings.
3. The recovery matrix distinguishes contribution payment from expense payment, security
   and deposits, and it scopes action to supported populations.
4. Gross, remainder and admitted columns close; commission, interest, fees and final funds
   bridge without moving an item between rule populations.
5. Freight, owned equipment and consumables are counted once on the correct economic basis.
6. Memo and schedule agree on values, statuses and unresolved actions.

If a requested action is unsupported, finish with a bounded open item rather than filling
the gap from general knowledge.
