---
name: bibliographic-identity-resolution
description: Resolve whether author-date callouts and reference records identify the same work despite surname particles, diacritics, capitalization, abbreviations, author truncation, year suffixes, and organizational aliases. Use during bibliography reconciliation when raw string equality would create missed links or false corrections.
---

# Bibliographic Identity Resolution

Resolve identity in layers. Separate harmless presentation variation, a repairable callout-form defect, an ambiguous link, and a genuinely absent counterpart. Do not let one normalization rule erase evidence needed by another.

## Keep three representations

For every author or organization name, retain:

1. evidence form: exact manuscript text;
2. display-normalized form: whitespace and line-break repair only;
3. comparison form: controlled case, punctuation, Unicode, and diacritic folding.

Use comparison form to find candidates, never to quote evidence. Keep year suffixes separate from the four-digit year.

## Resolve personal surnames

Treat particles such as `de`, `van`, `van den`, `von`, `da`, and `le` as part of the surname identity when the reference list presents them that way. Reference inversion can move a particle after the core surname. For example, `de Rivera` in prose and `Rivera de` in an inverted list may be one candidate, not two.

Apply these checks before declaring a mismatch:

- same particle sequence after inversion;
- same core surname after case folding;
- same year and suffix;
- compatible first-author position;
- no competing record with the same normalized key.

Capitalization at sentence start does not change identity. Apostrophe shape and hyphen spacing normally do not either. Diacritic folding can establish a candidate, but retain the exact forms and investigate when two distinct surnames collapse to the same comparison form.

Do not reorder arbitrary words to force a match. Particle inversion is a bounded convention, not permission to anagram names.

## Resolve organizations and acronyms

Link an acronym to an organization only when the manuscript explicitly introduces the acronym, the reference entry itself supplies the relationship, or the expanded names are unambiguous within the supplied material. Shared topic or publisher status is insufficient.

Distinguish authorship from sponsorship, publisher, repository, or location. A body callout naming a publisher does not automatically match a personal-author reference merely because that publisher appears later in the entry.

When the body and list use different authoring entities for what might be the same work, record an identity conflict. If the manuscript alone cannot decide which entity is the credited author, preserve the uncertainty for editorial disposition.

## Check author cardinality separately from work identity

A callout can point to the correct record yet use the wrong author form. First resolve the work, then inspect how the manuscript abbreviates authors elsewhere.

Infer the local author-date convention from clear records:

- single-author records use one surname;
- two-author records normally show both surnames;
- longer records may use the first surname plus an abbreviation;
- a narrative construction must preserve the same authorship distinction as a parenthetical one.

Do not impose an outside style manual when none is supplied. Use the manuscript's dominant, unambiguous pattern. Flag a form defect only when the resolved record's author count and the local convention support it.

For a multi-year narrative that points to records with different author lists, test each year separately. One compact author token may be valid for one year and invalid for another.

## Resolve year suffixes by collision set

Year suffixes distinguish works only within the collision set defined by the applicable citation style and author identity. Build the set before judging `a`, `b`, or a missing suffix.

Check all three surfaces:

- suffix on the callout;
- suffix on the matched reference record;
- other records and callouts that could belong to the same collision set.

An isolated suffix can indicate a stale label, an omitted companion record, or a legitimate item excluded from the current scope. Do not remove it automatically. A callout and record that disagree on an otherwise established suffix are inconsistent even if the base year matches.

Do not treat different coauthor groups as automatically interchangeable. A single-author work and a multi-author work led by the same surname may be distinguishable without suffixes; use the manuscript's own consistent pattern to determine whether a suffix is functioning as part of identity.

## Use contextual evidence without overclaiming

When more than one record shares a candidate key, compare the claim context with title anchors already present in the reference list. Context can disambiguate a low-flow claim from a flood-frequency title, for example, but it cannot manufacture missing metadata.

Assign one of these reasoning outcomes in scratch work:

- exact identity;
- normalized identity;
- identity with callout-form defect;
- probable identity requiring author confirmation;
- no plausible supplied record;
- competing supplied records unresolved.

These labels guide reasoning; the final artifact may use equivalent professional language.

## Guard against false positives

Explicitly test tempting near matches:

- inverted surname particle versus a different person;
- accent loss versus a spelling change that changes the core surname;
- organization acronym versus a publisher mention;
- shared first author and year versus different coauthor groups;
- a repeated callout versus a duplicated reference entry;
- a multi-year shorthand versus separate records with different authorship.

For each cleared near match, retain the two compared forms and the reason no correction is needed. This negative evidence prevents a copyeditor from undoing a valid identity.

Stop at unresolved when the supplied manuscript cannot establish the credited author, full missing record, or intended work. Confidence is not a substitute for evidence.

## Publish collision decisions

For each collision set used by the handoff, preserve a compact decision row: the body
components, candidate record identifiers, explicit versus inherited suffix/year handling, and
the resulting state (`resolved`, `form defect`, `query`, or equivalent). Do not leave a suffix
decision implicit in a prose finding; the row is the control that lets production recheck a
later author response without rebuilding the entire comparison.
