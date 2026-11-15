---
name: airfield-criteria-applicability
description: Resolve which requirements, tables, figures, notes, and revision marks govern an airfield or heliport design review. Use when a plan spans facility classes, operating modes, service-specific branches, old and current editions, or conditional visual-aid and approach criteria in long PDF standards.
---

# Airfield Criteria Applicability

Apply the Scope-Status-Condition framework before calculating geometry. A correct number from the wrong row is a failed design decision.

## Preserve the Review Inventory

Before interpreting criteria, inventory every independently reviewable property already represented by the baseline plan or required by the work request. Treat each `object + property + approach end`, when end-specific, as one topic. Length, start width, terminal width, slope, datum, and applicability are separate topics even when they share a table row or final disposition.

Persist the topic names in a small JSON manifest before drafting findings:

```json
{"topics": ["primary boundary size", "east clear-zone length", "east clear-zone width"]}
```

The example describes granularity only. Build the actual inventory from the supplied plan and requested scope. Do not limit the inventory to changed or noncompliant conditions. A professional inspection must positively close unchanged compliant properties, excluded nearby branches, per-end conditional properties, and facts that the supplied record cannot establish. Do not add unrelated criteria merely to increase the record count.

Use one final finding record per manifest topic. Every record must contain its own baseline observation, current governing criterion, disposition, and evidence; a shared bibliography or an omnibus finding cannot close several topics. Complete the ledger before writing summary prose or drawing geometry, then run:

```bash
python3 scripts/audit_decision_ledger.py output/inspection_report.json \
  --topic-manifest scratch/review_topics.json
```

Do not deliver until the command reports every manifest topic assigned to a different closed record. This coverage check is distinct from engineering correctness: it prevents a correct analysis from losing retained conditions or merging two independently auditable decisions during serialization.

## Trigger and Boundary

Use this method when at least one design choice depends on facility type, operator or service, flight-rule capability, use limitation, elevation, approach configuration, aircraft family, or installed visual aid. It is also appropriate when a legacy plan and a later marked revision are supplied together.

Do not use this skill to establish aircraft performance, structural capacity, pavement design, or obstacle survey elevations unless the supplied task and criteria provide those inputs. Record such matters as outside the geometric review or not assessable rather than importing outside assumptions.

## Build a Scope Card

Before reading dimensional rows, persist a compact scope card in scratch state:

```text
facility function:
operator/service branch:
operating rule/capability:
use limitation:
approach count and geometry:
visual aids that activate conditional criteria:
surface/elevation conditions:
controlling document status:
```

Populate only facts supplied by the work request or materials. Mark missing facts explicitly. Revise the card if later evidence conflicts with it.

## Apply Scope-Status-Condition

Treat one candidate requirement as one review unit. Close each unit before moving to the next.

1. **Scope:** identify the exact row, figure, or note branch whose labels match every relevant scope-card fact.
2. **Status:** determine whether the source is current, superseded, a marked change, an example, or a baseline under inspection.
3. **Condition:** evaluate every `if`, `when`, exception, note, and cross-reference that activates or disables the candidate.
4. **Decision:** retain, repair, exclude, or leave unresolved.
5. **Evidence:** bind the decision immediately to file, printed page, and section/table/figure/note.

Do not merge adjacent branches because they share a figure. Do not assume an unchanged-looking figure overrides a changed table row. Tables usually carry dimensions; figures show relationships; notes and marked changes can narrow both.

## Bind Values to Multi-Level Table Headers

Treat extracted table text as spatial data, not as a sentence. A value is not evidence until its row and complete column hierarchy are known. This is especially important when facility classes occupy adjacent columns or a table continues across PDF pages.

For every value that could change a drawing boundary:

1. extract the target page with layout preservation;
2. capture the table title, every header row, the item or row label, the value, and its unit;
3. trace the value vertically to its column header using alignment, not text reading order;
4. if the page lacks a repeated header, inspect the preceding table page before assigning the value;
5. persist a cell tuple: `table | item | row label | column hierarchy | condition | unit | value | printed page`;
6. compare the tuple's column hierarchy with the scope card before admitting it to the decision ledger.

Use `pdftotext -layout -f PAGE -l PAGE file.pdf -` for an initial alignment view. When columns remain ambiguous, inspect word bounding boxes or a rendered crop containing both header and row. Never assign a value from a flattened extraction merely because it is adjacent to the desired row label.

Before declaring a conflict, apply a same-object test to both evidence tuples. They must address the same facility branch, local condition, design quantity, datum, and unit role. If any part differs or one cell has no proven column owner, record a scope mismatch or unverified candidate instead of placing supported geometry on hold. A conflict exists only after two independently bound statements survive this test.

## Read Revision Marks as Operators

Revision bars, change delimiters, replacement figures, and split titles are instructions about status. They are not decoration.

For each marked change, ask:

- Was a former combined branch split into separate cases?
- Did the change replace a constant width with start/end widths?
- Did a new cross-reference narrow the local row?
- Does a figure note add a conditional envelope beyond the base case?
- Is nearby unchanged text still applicable to this facility?

Compare the current and baseline sources by professional concept, not by page number. Page and figure numbering may move between editions.

## Resolve Conflicting Source Statements

Treat a dimensional pair, conversion, cross-reference, or figure note as internally consistent only after its related statements agree. A repeated typographic label does not make a contradiction disappear.

When two locations conflict:

1. record both statements with their scopes and status;
2. check whether one is merely a reference-unit rendering of the other;
3. look for a third controlling relation, definition, or table row that resolves the conflict;
4. determine whether the conflict affects a boundary that must be drawn;
5. if the supplied record still does not close the dependency, issue a design hold for that boundary.

Do not silently select the value that appears more often. Do not repair a metric/reference mismatch by converting one side when the criteria declare that the units are not direct design conversions. A defensible correction requires a source rule that authorizes the choice.

## Adjudicate Conditional Requirements Per End

Reciprocal approach paths can share ground-zone criteria while differing in installed aids, operating restrictions, or available evidence. Maintain a separate condition card for each end whenever a conditional requirement is activated locally:

```text
end | shared facility class | local activating condition | controlling source | resolved inputs | missing inputs | disposition
```

Close the shared facility classification once, but do not copy a conditional decision from one end to the other. A mirrored plan is justified only when both the geometry and every activating condition are reciprocal.

## Extract Evidence from Long PDFs

Use the bundled search tool to preserve physical page locations while searching the text layer:

```bash
python3 scripts/pdf_evidence.py criteria.pdf --query 'primary surface' --query 'visual aid' --context 2
```

For a figure whose annotations are rasterized, first locate the figure title in the text layer, render only that physical page, and OCR the rendered page. Record both the physical PDF page used for extraction and the printed page or figure identifier shown on the page. Never treat OCR punctuation as authoritative; cross-check units and nearby labels visually or with a second rendering resolution.

## Maintain a Decision Ledger

Use one scratch row per candidate condition:

```text
topic | scope match | status | condition | baseline | current | decision | evidence
```

Write the row when the condition is resolved. A summary written only at the end invites branch drift. When a later note changes an earlier decision, update the earlier row and record why.

Keep each final review record self-contained. It must carry a topic, the baseline observation, the current governing criterion, an explicit `retain`, `repair`, `exclude`, or `hold` disposition, and resolvable evidence locations. Do not rely on a shared bibliography to supply a record's evidence, and do not combine several independently dispositioned conditions into one omnibus record.

Before delivery, run the bundled structural audit against the final report. Set the minimum to the number of rows in the completed scratch ledger so that serialization cannot silently drop a row:

```bash
python3 scripts/audit_decision_ledger.py output/inspection_report.json --minimum-records LEDGER_ROW_COUNT
```

When a topic manifest was created, prefer the `--topic-manifest` form above; it checks both record count and one-to-one topic coverage.

The audit checks record closure and evidence binding without knowing project criteria or correct answers. Treat warnings as a prompt to inspect the corresponding record; the tool cannot decide applicability for you.

Required closing checks:

- every repaired dimension traces to a current controlling location;
- every retained dimension has a positive compliance basis;
- every excluded near-neighbor names the scope mismatch;
- every unresolved item names the missing evidence;
- the drawing uses only the final admissible set of rows and notes.
- every conditional surface is traced to the approach end whose facts activate it;
- every source conflict that controls a coordinate is either resolved by supplied evidence or carried as a design hold.

Do not convert an unresolved input into a conservative numeric guess unless the governing criteria explicitly authorize that design convention.
