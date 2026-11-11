# Requirements clarification minutes

**Party A, system operations:** The current unit snapshot and the latest fourteen dated peak
records are to be used for a prospective N-1 review of the `大潭` and `通霄` gas fleets. The
historic records are a stress profile, not a claim that the two files are contemporaneous.

**Party B, controls analytics:** Before opening or analysing either material file, create empty
skeletons at `output/dispatch_review.json`, `output/dispatch_trace.csv`, and
`output/dispatch_model.py`. Do not alter the two files in `materials/`, and do not use network
access. The completed program must run with Python from `/workspace` and regenerate the JSON and
CSV from those two material files alone.

**Confirmed requirements:** Use Traditional Chinese for all explanatory text, decisions,
limitations, and status reasons in the deliverables; preserve source identifiers and enum values
exactly. `dispatch_review.json` must provide the top-level objects `source_binding`,
`unit_register`, `scenario`, `model`, `metrics`, `decision`, `evidence`, and `limitations`. It must
bind the two record dates, classify every in-scope snapshot unit, define and justify one credible
online single-unit loss, disclose the historical-to-current scenario boundary and all model
assumptions, report the constrained dispatch result, and give a conditional operational decision.

`dispatch_trace.csv` must contain one row for every in-scope dispatchable unit at every one of the
fourteen source dates, including the lost unit. Use this exact header:

`來源日期,來源列號,步序,歷史大潭_MW,歷史通霄_MW,歷史合計_MW,壓力指數,目標出力_MW,機組名稱,廠群,機組狀態,事故機組,快照出力_MW,裝置容量_MW,前步出力_MW,步調整上限_MW,下界_MW,上界_MW,指令出力_MW,實際出力_MW,機組負載率,步總出力_MW,步殘差_MW,步可達性`.

**Confirmed deliverable:** Completion is the three files at the exact paths above. Another
operations engineer must be able to rerun `output/dispatch_model.py`, trace each source record and
unit state, recompute every constraint and balance, and understand why the recommendation is
conditional without consulting anything outside `/workspace`.
