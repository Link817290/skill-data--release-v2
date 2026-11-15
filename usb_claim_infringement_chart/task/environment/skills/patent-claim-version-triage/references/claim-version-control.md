---
name: patent-claim-version-control
description: Reconcile application, publication, amendment, and issued patent claim sets without confusing same-number claims. Use when a claim chart, clearance review, or litigation update contains more than one claim version or asks how an earlier chart changes after issuance.
---

# Patent claim version control

## When to use

Use this skill before claim construction or product comparison whenever the packet
contains multiple stages of a patent claim set. The danger is not merely choosing
the wrong document. Prosecution can preserve claim numbers while importing
limitations from several earlier claims, changing dependencies, cancelling text,
or renumbering subject matter. A same-number comparison is therefore a text-and-
dependency comparison, never an identifier lookup.

This is a document-control and scope-accounting method. It does not infer why an
amendment was made unless the supplied prosecution record says so.

## Freeze a version register

For each claim set, record:

- the stage represented by the document;
- the document's own date or status if present;
- the exact claim identifier;
- independent or dependent status;
- the complete dependency chain;
- the exact text used for analysis.

Assign an internal version key before paraphrasing. Keep quotations and normalized
features in separate fields so later editing cannot silently replace source text.
If the request designates a controlling set, mark it as controlling while retaining
the other set for lineage or impact analysis.

Stop if a version cannot be identified from supplied material. Do not resolve that
gap from memory, a patent number pattern, or an external database when browsing is
out of scope.

## Expand every dependency before comparing versions

Materialize each dependent claim as the union of its own clause and every ancestor
limitation. Perform this expansion independently for every version. A claim that
still says "of claim 1" may inherit a very different claim 1 after amendment.

Guard against three common defects:

- comparing only the terminal clause of a dependent claim;
- importing the parent from the wrong version;
- assuming an unchanged terminal clause means unchanged total scope.

For multi-level dependencies, walk one parent at a time and detect loops, missing
parents, or impossible references. Keep the defect visible rather than guessing a
corrected chain.

### Audit the printed dependency before expansion

Do not treat every syntactically present parent number as a usable dependency.
For each claim, first record the parent exactly as printed and classify the edge:

- standalone claim with no parent;
- valid same-version parent whose claim category can supply the recited subject;
- missing parent;
- self-reference or dependency loop;
- facial category mismatch, such as a storage medium said to depend from a method,
  or an apparatus said to depend from a medium claim.

Only a valid edge enters the controlling expanded feature set. For a broken edge,
preserve a no-repair state even when the intended parent looks obvious. You may
record a candidate parent in a separate review field when the packet supplies a
disciplined basis, such as a parallel independent claim followed by a matching
dependent family, or a unique semantic continuation. Label that basis and never
substitute the candidate into the controlling chart without authority to correct
the claim text.

This separation prevents a subtle circular result: silently repairing a claim
changes the feature set, which then makes the repair appear substantively
plausible. The printed edge, defect status, non-controlling candidate, and actual
expansion policy must remain independently reviewable.

## Normalize into semantic features

Create a feature registry that is stable across versions. A useful feature is small
enough to be added, removed, or changed independently, but retains its actor,
object, path, and temporal relationship.

Reuse a feature reference only when the propositions are substantively the same.
Create a new feature when an amendment changes any of these:

- sender or receiver;
- required information content;
- physical channel;
- trigger or response relationship;
- interval boundary;
- structural relationship;
- purpose that limits the act.

Do not use claim numbers as feature references. Numbers identify containers; they
do not establish semantic continuity.

## Build lineage by subject matter, not number

For each controlling claim, trace every earlier claim whose limitations appear in
the expanded text. An issued independent claim can combine an earlier independent
claim with several earlier dependent claims. Record all contributors, even when
one has the same number and the others do not.

The lineage question is: "Which earlier claim text supplied this required
proposition?" It is not: "Which earlier claim has this number?"

If language was rewritten rather than copied, bind the lineage at the feature
level and explain the match. Do not call two features identical merely because
they concern the same general subject, such as voltage, authentication, or data.

## Reconcile an entire claim family

Same-number analysis is only one view. When claims have been renumbered, folded
into a new independent claim, or moved between method, medium, and apparatus
families, build a second correspondence table keyed by subject matter.

For every earlier claim, separate its terminal contribution from what it would
inherit through its printed parent. Search the later set for the terminal
proposition, then classify the result:

- a base claim retained with additional limitations;
- dependent subject matter retained under a different number;
- subject matter absorbed into a later independent claim;
- a broken dependency repaired while the terminal subject matter was renumbered;
- rewritten or omitted subject matter with no reliable one-to-one destination.

After locating a candidate destination, expand that later claim through its real
later-version parent. Record the complete destination feature set, not only the
matching terminal clause. This exposes a common scope error: a dependent clause
can be textually retained while its new parent makes the expanded claim materially
different.

Keep semantic correspondence separate from legal control. Finding a convincing
later destination does not cure a self-reference or category mismatch in the
earlier printed dependency. The correspondence table can explain amendment
movement while the controlling analysis still marks the earlier expansion as
blocked.

## Classify same-number scope by set relations

After both expanded claims have been normalized, compare their required feature
sets:

- If the later set contains every earlier feature plus additional requirements,
  the later text is the narrower set for this technical comparison.
- If the earlier set contains every later feature plus additional requirements,
  the earlier text is narrower.
- If the sets match, they are equivalent at the chosen normalization level.
- If each set contains a feature absent from the other, neither contains the other;
  describe the relation as overlapping rather than forcing a narrower/broader call.

Open-ended transition language does not change this set accounting: adding a
required limitation still narrows the combinations that satisfy all requirements.
But replacing one requirement with a different one often produces overlap, not a
simple direction.

## Propagate amendments into a comparison matrix

Do not edit old results in place. Preserve the earlier chart, create a separate
matrix for the controlling claims, and project evidence feature by feature.

Reuse an earlier element finding only when the semantic feature, target identity,
source scope, and operating mode are unchanged. New or rewritten features require
new findings. Then recompute each claim-level result from the controlling claim's
full feature set.

An outcome may remain unchanged for different reasons. Record the decisive
features so a reviewer can see whether the amendment had no practical effect, made
an already-open comparison open for another reason, or introduced a new
incompatibility.

## Run collision checks

Before delivering, check for:

- one claim identifier linked to two versions without a version key;
- a dependent claim that inherited a parent from another stage;
- a lineage list containing only the same-number predecessor despite imported
  subject matter;
- a later claim labeled narrower even though each version has a unique required
  feature;
- controlling-claim results copied from the earlier chart without recomputation;
- decisive features that are not in the controlling claim's required set.

## Evidence and explanation discipline

Tie every version statement to claim text supplied in the packet. Keep amendment
facts separate from speculation about examiner intent, estoppel, disclaimer, or
claim construction. Those doctrines require their own records and legal scope.

A concise version-impact row should let a reviewer reconstruct three things: the
later required feature set, the earlier subject-matter lineage, and why the target
comparison did or did not change.

## Stop conditions

Stop rather than guess if the packet omits a parent claim needed for expansion, if
the document stage is ambiguous, or if a broken dependency cannot be resolved
within the supplied record. State exactly what version or claim text is missing.
Do not merge versions to manufacture a complete chain.
