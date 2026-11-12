# Case-Level Final-Review Activation Gate

This step determines whether a case should produce any final-review conclusion, not whether the source materials contain anything abnormal. Make the case-level decision first to avoid combining several weak clues into an abnormality list that should have remained empty.

## 1. Two candidate sets

Build two sets for each case before writing to the deliverable:

- `Core candidates`: the source record already provides an explicit classification or conclusion; or a specialty or imaging description reliably expresses a substantive finding; or the record is a **standing-readout item** as defined below.
- `Conditional candidates`: reference-range deviations that carry no named conclusion, status descriptions, non-specific imaging descriptions, values that require combining several indicators before they mean anything, and items that indicate risk rather than a current finding. Note what is not on this list: a finding is not conditional merely because it is mild, small, or frequently seen.

### Standing-readout items

Some quantitative records are read out by a fixed rule that belongs to the examination item itself, not to the reader's general medical knowledge. Such a record is a core candidate even though its source cell contains only a number. An item qualifies only when all three hold:

1. The readout depends on that single indicator alone; it does not require combining it with other indicators or with clinical history.
2. The rule is part of how the examining department defines the item, so every institution performing that examination applies the same rule.
3. The readout produces a named standard conclusion, not a direction word such as high, low, or out of range.

A record that fails any of the three stays in the conditional set. In particular, several indicators from one test panel drifting in the same direction never becomes a standing-readout item — that is inference, and it belongs in the conditional set no matter how consistent the drift looks.

Repeated occurrence does not automatically promote a conditional candidate to a core candidate. Repetition only increases confidence that the source was recorded that way; it does not change whether the institution would include it in the final review.

## 2. Activation rule

A case enters the “abnormal conclusion present” branch only if at least one core candidate passes all of the following checks:

1. It contains a clear core finding, not merely an arrow, asterisk, reference range, or risk notice.
2. It does not invent a diagnosis or grade by reasoning from general medical knowledge. Applying an examination item's own standing-readout rule is not inventing a diagnosis; deriving a disease name from indicators the item does not itself read out is.
3. It does not belong to the default exclusion group, unless a higher-level conclusion elsewhere in the materials explicitly supports inclusion.
4. The organ or location, laterality, quantity, degree, characteristics, and certainty in the conclusion are all supported by evidence from the same case.

If the core-candidate set is empty, the case must be marked `无异常结论` and all conditional candidates must be removed. Do not activate a case merely because something “looks slightly concerning.”

## 3. Default exclusion group

The following items cannot activate a case on their own by default, nor can multiple such items be combined to bypass the activation gate:

- Laboratory combinations containing only raw test values or reference-range deviations, without textual classifications or conclusion-bearing items, and not qualifying as standing-readout items; related indicators moving in the same direction do not automatically constitute an institutional final-review diagnosis.
- Records that describe only a prior procedure, absence, repair, postoperative state, or anatomical state without a current abnormal conclusion. When the same record also carries a present-tense finding alongside the historical state, the present-tense part is judged on its own merits and is not suppressed by the historical part.
- Findings whose only support is that they are common in the screened population. Degree words such as mild or slight describe how severe a finding is; they do not decide whether the institution records it. Grade the finding as the evidence states it and let the activation checks decide inclusion — do not drop an otherwise well-supported finding because it reads as minor, and do not drop a routine-department finding merely because the department is routine.
- Non-specific descriptions that name no definite finding — wording that reports an impression or a texture without identifying what was seen. A description is not excluded by sitting inside a long imaging sentence, nor by the smallness of what it describes: long sentences routinely carry definite focal findings after a clause reporting that the organ is otherwise normal, and those findings are read on their own terms. Measured size belongs in the conclusion as the source stated it, not as a reason to drop the finding.
- Risk or management language such as high risk, abnormal indicator, or recommended follow-up cannot substitute for the current finding itself.

These are inclusion boundaries, not medical judgments. Exclusion only means “do not reconstruct this as the institution's final-review conclusion”; it does not mean the item is clinically normal or unimportant.

## 4. Conservative review after activation

After a case passes the activation gate, review every candidate individually; do not admit all conditional candidates together. For each item, write one auditable reason explaining:

- why the item itself reaches the core-candidate level; or
- which higher-level evidence explicitly elevates its eligibility for inclusion.

A candidate must be removed if neither reason can be stated. If the last core candidate in a case is removed, revert the case to `无异常结论`.

## 5. Counterfactual empty-case check

Before delivery, perform a counterfactual check for every case: temporarily remove every conditional candidate — reference-range deviations carrying no named conclusion, pure status items, and incidental descriptions. Core candidates, including standing-readout items, stay in place; this check is aimed at cases held up only by weak evidence, not at trimming well-supported findings. If no core candidate remains, the case should be empty; do not select one of the removed conditional items and add it back.
