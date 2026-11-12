# Conclusion Normalization Principles

This document does not provide a term-by-term mapping from evidence phrases to standard answers. The goal of normalization is to compress meaning faithfully, not to guess answers from a dictionary.

## 1. Establish semantic slots

For each candidate finding, record:

- core organ or system;
- specific location and laterality;
- quantity information such as unilateral, bilateral, solitary, or multiple;
- degree or grade;
- characteristics or status such as morphology, echogenicity, calcification, effusion, or postoperative state;
- certainty such as definite, suggestive, or possible;
- supporting detail-row IDs.

When a slot is missing, leave it missing; do not fill it from another case, general knowledge, or an adjacent field. A slot is not missing when the source expresses it in words rather than in a grade label — intensity adverbs and hedging words in the original description carry the degree slot, and grading a finding as the source worded it is reading the slot, not filling it.

## 2. Form atomic conclusions

- Express only one independent finding in each conclusion; output coexisting findings from the same sentence separately.
- Use the shortest expression that preserves the source evidence's meaning; do not pack dimensions, examination procedures, or explanatory text into the term.
- When a direct classification or conclusion-bearing item already supplies stable wording, preserve it rather than replacing it with a more common near-synonym of different scope.
- Descriptive evidence may only be compressed into a semantically equivalent form. Where a modality's settled vocabulary makes a description and a named finding equivalent, writing the name is the compressed form and is expected. Where the description would still admit more than one named finding, keep the description and do not pick one of them.
- Do not upgrade certainty. Compression may change how a finding is worded; it may not change how sure the source was that the finding is there.

## 2b. The conclusion cell carries the name, nothing else

Recognising the finding and naming it are two different jobs, and the second one
is where reconstructed conclusions usually fail. A conclusion that is medically
correct but carries extra text is not the standard conclusion — the reviewer's
entry is a name, and everything that supports or qualifies it lives elsewhere.

Keep out of the conclusion cell:

- **Measurements.** Sizes, diameters, volumes, counts and the parentheses holding
  them belong in the explanation, never in the term.
- **Modality signs.** Acoustic shadowing, comet-tail artefacts, boundary and
  margin descriptions, echo texture wording and similar imaging observations are
  the evidence for the name, not part of it.
- **Sub-location refinements.** Use the location the standard name carries. Do not
  narrow it to the anatomical compartment the report happens to mention, and do
  not add a side or lobe the standard name does not carry.
- **Descriptive suffixes.** Do not turn a settled diagnosis into an observation by
  appending wording that means "appearance of" or "changes consistent with". If
  the modality's vocabulary has a settled name, the name stands alone.
- **Renaming across vocabularies.** When an examination item has its own name,
  keep that name. Substituting what the test detects for what the test is called
  is a different term even when both are clinically true.

The detail is not lost — it moves to the explanation and evidence columns, which
is where a reviewer would look for it.

**Self-check.** Strip every parenthesis and qualifier from each conclusion you
wrote. If what remains is the term you should have written, the extra text was
never part of the conclusion. If nothing recognisable remains, the finding was
described rather than named, and it needs the name.

## 2c. Detected is not the same as concluded

An examination records many findings that are real, correctly observed, and still
absent from a final review: incidental observations a reviewer treats as within
normal limits, minor degrees that carry no action, and routine remarks that
appear on nearly every report of that modality. Writing them all down does not
make the reconstruction more complete — it makes it a transcript instead of a
review, and each one dilutes the conclusion set.

Ask of each candidate: is this what the reviewer would enter, or is it what the
machine happened to see? The second kind belongs in the evidence trail, not in
the conclusion list. `references/case-gating.md` gives the activation tests;
this rule applies within an activated case, to the individual finding.

## 3. Qualifiers must not drift

- Location, laterality, quantity, degree, characteristics, certainty, and status all carry medical meaning.
- Similar degree terms, adjacent grades, and unilateral or bilateral expressions are not interchangeable.
- The fact that a broader concept can contain a narrower one does not make them synonymous, and the reverse is also true.
- “The standard item can cover the candidate item” does not mean “the two are synonyms.” Treat them as the same normalized conclusion only when the semantic slots above are consistent.

## 4. Merging and conflicts

- Merge duplicates only when the core finding and every qualifier slot are identical.
- Split multiple independent findings in the same row; when multiple rows jointly support the same finding, merge their evidence-row IDs.
- When qualifiers from two sources conflict, do not combine them into a new, stronger conclusion. Select the item with the higher evidence level and record the conflict in the explanation.
- One more-specific candidate cannot simultaneously replace multiple independent conclusions that a physician might retain separately.

## 5. Reverse check before output

For every proposed output item, trace backward from the conclusion to the evidence: does the evidence support every word; would removing a qualifier be more faithful; was any diagnosis, degree, or scope added that the evidence did not express? If these questions cannot be answered completely, return to the evidence ledger and reassess the item.
