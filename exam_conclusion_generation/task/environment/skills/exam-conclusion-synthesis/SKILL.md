---
name: exam-conclusion-synthesis
description: Reconstruct doctor-reviewed physical-exam conclusions from heterogeneous offline examination rows by applying evidence hierarchy, calibrated inclusion boundaries, semantic normalization, and case-level closure. Use when the goal is to reproduce an institution's review behavior rather than diagnose every abnormal value or transcribe every recorded one.
---

# Physical Examination Final-Conclusion Synthesis

The goal is to reconstruct the standard conclusions that a reviewing physician would enter in the final review, rather than perform a new clinical diagnosis or summarize every value marked with an arrow.

## When to use

Use this Skill when the input contains, by case, records from multiple departments, imaging descriptions, functional examinations, specialty findings, laboratory values, and reference ranges, and the task requires deduplicated final physical-examination conclusions with evidence references.

## How to use

1. First read `references/evidence-hierarchy.md` to distinguish conclusion-bearing items, translatable descriptions, raw values, and excluded items.
2. Then read `references/case-gating.md` and make the case-level final-review activation decision first; a case that does not pass the activation gate must retain an empty conclusion set.
3. Then read `references/normalization-rules.md` and form minimal but complete candidate conclusions by semantic slots, without using a term-by-term lookup table.
4. Build an evidence ledger and candidate set for each case, recording source rows, evidence level, core finding, qualifiers, conflicts, and the reason for inclusion.
5. Use `references/closure-checklist.md` to check false negatives and false positives separately, and explicitly review cases that may require an empty conclusion set.
6. After completing the deliverables, run `python /app/environment/skills/exam-conclusion-synthesis/scripts/check_deliverables.py <workspace>`; the script checks only structure and references and does not provide answers.

## Core principles

- Final-review conclusions are not a list of every abnormal value. A clinically noteworthy item is not necessarily something the institution's physician would enter in the final review.
- The task is to read what the examination items already recorded, not to reason past them and not to second-guess them. Both directions of error are failures: inventing a finding the materials never expressed, and dropping a finding they plainly did. Conservatism applies to the first and is not a licence for the second.
- First decide whether the case activates final review, and only then decide which conclusions to write. Multiple weak pieces of evidence cannot be stacked to turn an otherwise empty case into an abnormal case.
- Evidence priority: explicit classification or conclusion-bearing item ≈ standing-readout item > specialty or imaging description that reliably expresses a single finding > value needing indicators combined or a reader-supplied threshold > isolated laboratory deviation. A `standing-readout item` is a single quantitative indicator that the examination item's own fixed rule converts into a named standard conclusion; `references/case-gating.md` states the three tests it must pass.
- Normalization compresses meaning; it does not add or remove it. Preserve the organ, location, laterality, quantity, degree, characteristics, certainty, and status carried by the source evidence. Where a modality's settled vocabulary makes a description and a named finding equivalent, writing the name is the compressed form; where the description would admit more than one name, keep the description.
- Normal, negative, no-abnormality, and examination-not-performed records do not generate abnormal conclusions; an examination not performed also cannot be treated as normal.
- Write only one independent finding per row; merge duplicates only when their semantic slots are identical.
- The conclusion cell holds the name and nothing else. Measurements, modality signs, sub-location refinements and "appearance of" suffixes are evidence for the name, not part of it — they belong in the explanation column. Recognising a finding correctly and naming it correctly are scored as different things, and the naming step is the one that usually fails; `references/normalization-rules.md` §2b gives the rule and a self-check.
- Do not upgrade certainty: do not turn “possible” into a definite diagnosis, and do not name a finding the evidence only gestures at. Degree, by contrast, is not a reason to exclude — grade a finding as the source worded it.
