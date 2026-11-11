# Employee engagement analysis, two waves

We ran the engagement survey twice. The item wording changed between waves and the people who
answered are not the same both times, so this is a release that has to hold up to review, not
a before-and-after chart.

Work only from `/workspace/materials`. `analysis_requirements.xlsx` is the contract for this
job — read it first. It states the sections each workbook must contain, the modules to cover,
the required methods, and the closure checks the finished release must pass. Formula definitions
referenced by that contract are collected in `materials/formula_reference.md`.

Save two workbooks: `/workspace/output/cleaned_samples.xlsx` is the audit trail (where each
row came from, which responses were adopted, what weight each carries) and
`/workspace/output/engagement_analysis.xlsx` is the analysis release. Every figure in the
second should be traceable to the first.
