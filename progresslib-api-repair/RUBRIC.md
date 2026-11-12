# Scoring rubric

## Scoring contract

The same submission is read through two independent lenses.

`reward_strict` is a continuous capability score in `[0, 1]`, and `reward` is its alias. It is computed from executable behavior plus evidence in the submitted repair report; it does not compare prose with a reference string. A missing source tree or report receives zero.

`reward_lenient` is a separate binary delivery-completion score in `{0, 1}`. It asks only whether the requested delivery arrived in a usable shape and never reads repair quality, defect coverage, contract outcomes, or diagnosis wording. It is defined below and is not a cut on the strict number.

```text
reward_strict  = 0.55 * behavioral_repair + 0.45 * root_cause_diagnosis
reward_lenient = 1 if every delivery-completion predicate holds, else 0
reward         = reward_strict
```

Passing is defined by the lenient result alone: `pass_rate_basis = "reward_lenient"` and `pass_rate = mean(reward_lenient)`. There is no threshold on `reward_strict`.

The strict score separates diagnosis from implementation. A source tree that passes one example but does not explain the cause earns only the corresponding behavior fraction. A fluent report with an unpatched source tree earns no implementation credit.

### Delivery completion — `reward_lenient`

`reward_lenient` is `1.0` only when all five predicates below hold, and `0.0` otherwise. Each predicate is a structural fact about the submitted files that a reader can confirm by opening them; none of them grades the repair.

1. **Report readable.** The requested report path exists as a regular file, decodes as UTF-8, and contains non-whitespace text.
2. **Requested skeleton present.** The report carries a top-level title heading and the three second-level sections the instruction asks for: summary, defect records, and verification. Presence of the headings is checked; nothing inside them is read.
3. **Defect records populated.** The defect-records section holds at least one third-level record heading, and every record heading there is followed by body text rather than left as an empty stub. Record titles and record wording are not inspected.
4. **Delivered sources parse.** Every Python module in the submitted source tree parses as Python source, so no module was emptied, truncated, or left syntactically broken by the handoff.
5. **Delivered tree loads.** The submitted tree imports as a library in a fresh interpreter and every name the package itself declares as an export resolves. No behavior is exercised and no result is asserted.

The two lenses read different properties of the submission and can disagree in either direction. A run that repairs source modules but hands back an empty report skeleton scores above zero under the strict lens and zero under the lenient one; a run that hands over a complete, loadable delivery whose repairs and diagnoses are mostly wrong scores `1.0` under the lenient lens and low under the strict one. Both are recomputed by `task/tests/validator.py` from the submitted files alone, and neither lens reads model identity, skill mounting, trajectory wording, or construction metadata.

## Capability dimensions

### Root-cause diagnosis and evidence binding — 45%

Capability: connect each caller-visible symptom to the owning public boundary, violated contract, source path, repair, and focused outcome.

Professional reason: latent release defects require maintainers to probe beyond a passing baseline and distinguish formatting, lifecycle, protocol dispatch, workload inference, warning policy, and shutdown ownership.

Anchor type: `source_location`, `relation`, and `expert_judgment_record`.

Verifier signal: the report's `## Defect Records` section contains one `###` record per independent cause. A record must locally connect an observation or reproducer, root cause, source path, change, focused check, and outcome. The eleven causal records contribute 90% of this dimension; the summary/records/verification handoff contributes 10%, including a rejected competing hypothesis and a command tied to its outcome. This split keeps technical diagnosis primary while requiring evidence that a maintainer can reproduce. Equivalent technical wording and record titles are accepted.

Rows:

- Negative interval formatting is tied to `format_interval` in `tqdm/std.py`, signed input, and separating sign from absolute magnitude before division.
- Infinite-total formatting is tied to `format_meter` in `tqdm/std.py`, remaining-time overflow, and normalization to the unknown-total policy.
- Width enforcement is tied to `ncols` and `format_meter` return branches in `tqdm/std.py` that omit the normal bar or total.
- Unavailable output is tied to `tqdm.write` and its context in `tqdm/std.py`, a missing standard stream, and guarded no-op behavior.
- Partial cleanup is tied to `close` in `tqdm/std.py`, construction that did not establish `disable`, and conservative attribute access.
- Reset consistency is tied to `reset` in `tqdm/std.py`, an infinite total, and the constructor's unknown-total normalization.
- Async dispatch is tied to `tqdm/asyncio.py`, an object whose `__aiter__` returns a distinct `__anext__` provider, and retaining that returned iterator.
- Concurrent total inference is tied to `tqdm/contrib/concurrent.py`, multiple sized inputs, and the shortest-input semantics of map.
- Unknown length handling is tied to `length_hint` in `tqdm/contrib/concurrent.py`, an unsized generator mixed with a sized input, filtering a negative unknown sentinel, and the all-unsized case where no finite bound is observable.
- Concurrent warning policy is tied to the chunksize warning in `tqdm/contrib/concurrent.py` and the shortest workload that can actually be mapped.
- Monitor shutdown is tied to `atexit` in `tqdm/_monitor.py`, a daemon blocked on a lock, and a non-joining signal distinct from ordinary explicit exit.

An API name or source path without the nearby causal and verification relation does not satisfy a row.

### Behavioral repair — 55%

Capability: restore latent public contracts with focused source changes while preserving the package entry points and passing baseline.

Professional reason: downstream callers depend on formatting, optional runtime states, Python iteration protocols, concurrent workload metadata, and prompt process shutdown even when ordinary tests pass.

Anchor type: `invariant` and `relation`.

Verifier signal: eleven independent executable checks import the submitted source tree:

1. Negative durations retain a sign and format their absolute clock magnitude.
2. An infinite total follows unknown-total formatter behavior without overflowing.
3. Width limits apply to custom no-bar and unknown-total return branches.
4. The write helper and its context tolerate an unavailable standard output stream.
5. Cleanup tolerates an object whose construction did not establish normal attributes.
6. Resetting to an infinite total applies the construction-time unknown-total policy.
7. An asynchronous iterable may create a distinct asynchronous iterator.
8. A concurrent map total follows the shortest of multiple sized inputs.
9. An unknown length hint does not erase a known concurrent workload bound.
10. The chunksize warning threshold follows the shortest mapped input.
11. The interpreter-exit monitor handler signals without joining a blocked daemon.

The behavioral dimension is weighted by method family because the four families require
different published contracts and have different failure impact: async iteration `0.35`,
concurrent mapping `0.35`, meter rendering `0.15`, and indicator lifecycle `0.15`.
Items within a family share that family's weight equally. The verifier does not require a
particular diff, helper name, or implementation spelling. This family weighting is why a
single concurrent protocol defect is not treated as interchangeable with one of four
small lifecycle edge cases; the rationale is method scope and downstream impact, not a
target score.

### Delivery and scope integrity — 0% strict (lenient delivery gate)

Capability: retain a usable library source tree and place the requested report at the requested path.

Professional reason: replacing a module with a stub or moving the answer into prose leaves downstream consumers unable to import the library.

Anchor type: `invariant`.

Verifier signal: the formatter, async adapter, monitor, and concurrent helper modules remain present and are the modules imported by behavior checks.

## With-skill and no-skill profiles

With-skill profile: the executor treats a passing suite as a baseline, builds boundary matrices for display and lifecycle modes, distinguishes asynchronous iterable and iterator roles, records concurrent delegation, and binds every repair to a local defect record. Focused probes reveal several latent contracts before broad regression testing.

No-skill profile: a competent executor may run the supplied suite and stop when it passes, or inspect only default synchronous rendering. It tends to conflate async iterable and iterator objects, accept a zero length hint as evidence, derive map metadata from one input, or use ordinary joining cleanup at interpreter exit. Its report often lacks independently reproducible causal records.

## Skill-attributable mapping

| Skill section | Business step | Scored dimension | Decay shape | Observable difference |
| --- | --- | --- | --- | --- |
| Python Debugging Deliverable: convert symptoms into contracts | investigate a passing baseline | diagnosis and behavioral repair | premature completion | independent focused reproducers exist before source edits |
| Progress Indicator Contracts: map lifecycle and compare modes | inspect formatter, reset, partial construction, and shutdown | diagnosis and behavioral repair | default-path fixation | optional and exit-time states are tested separately |
| ANSI Terminal Formatting: exercise a boundary matrix | preserve terminal width across serialized return paths | diagnosis and behavioral repair | sibling-branch omission | every width-producing path is checked with visible length |
| Async Iteration Protocols: separate iterable from iterator | preserve supported asynchronous sources | diagnosis and behavioral repair | protocol-role collapse | a distinct iterator factory is exercised lazily |
| Concurrent Map Contracts: derive workload and instrument delegation | infer totals and warnings from multiple inputs | diagnosis and behavioral repair | first/longest-input shortcut | sized and unsized input permutations produce coherent metadata |
| Python Debugging Deliverable: verify and hand off | produce maintainer evidence | diagnosis and delivery | prose-only closure | each record includes cause, change, check, and outcome |

The strict score is carried entirely by the two method-dependent dimensions. Keeping the delivered modules in place and giving the report its three sections are delivery obligations rather than professional ability, so they are checked by the lenient contract and carry no strict credit.

## Robustness checks

- **Passing baseline:** the unmodified candidate passes all supplied runnable tests yet scores `0.0000`, because the downstream contracts remain broken and no defect record is bound to a source location.
- **Synonym rewrite:** equivalent record titles and causal wording preserve all diagnosis rows because concept groups, not reference sentences, are checked.
- **Keyword list:** global API/path lists without per-defect observation, cause, change, check, and outcome fields receive no causal-record credit.
- **Report-only submission:** a complete report with unpatched source receives diagnosis credit but no behavioral credit.
- **Source-only submission:** a fully repaired source without a report receives behavioral credit only; the delivery obligations it satisfies are read by the lenient contract, not by the strict score.
- **Alternative solution:** different helper structure, check order, and patch layout are accepted when the public relations and local evidence remain intact.
- **Empty report skeleton:** a submission that patches source modules but leaves the requested report as bare headings keeps its behavioral credit under the strict lens and receives `0` under the lenient lens, because nothing was handed over to read.
- **Lens independence:** the two lenses can order the same pair of submissions differently. Neither is derived from the other's output, and the lenient lens never reads a strict component.

## Known limits

The verifier samples eleven high-risk boundaries and does not claim exhaustive platform-specific rendering or optional integrations that require unsupplied packages. The score evaluates this focused repair and evidence handoff, not general code style or full library coverage.

The lenient lens is deliberately a completion check and nothing more. It confirms that the artifacts exist, decode, parse, load, and carry the requested structure; it says nothing about whether the repair is right, and a submission can satisfy every lenient predicate while scoring low under the strict lens.

## Report wording equivalents

Report credit requires the same defect, source location, cause and repair relation.
For unknown concurrent hints, discard/drop/skip/exclude are equivalent to filter/ignore.
Partial cleanup accepts `tqdm.close` and missing-state tolerance via hasattr, getattr,
guards or try/except. These alternatives do not replace the eleven executable contracts.
