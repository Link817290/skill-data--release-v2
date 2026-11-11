# Cooling Tower Workbook Rubric

The verifier recalculates the submitted workbook offline in LibreOffice for the original condition and nine perturbations of its original inputs. Missing or invalid deliverables receive zero. Environment or spreadsheet-engine failures are scoring errors and produce no reward.

## Strict Score

`strict = sum(weight * completion) * product(independent damage coefficients)`.

Each numerical item measures a complete prerequisite chain: every listed result must agree with the independently calculated value across all ten scenarios. Completions are binary. The eight numerical owners cover 103 original result cells. The four remaining original cells, E96/H96/H102/E103, belong exclusively to the thermal-decision deduction. Every original result has exactly one owner.

| Item | Weight | Calculation |
| --- | ---: | --- |
| P01 | 0.12 | Air-state boundary properties and hot-water saturation properties |
| P02 | 0.13 | Water-temperature grid and its saturation-pressure/enthalpy chain |
| P03 | 0.25 | Candidate airflow, evaporation correction, operating lines, transfer demand, available packing characteristic and selected-case transfer arithmetic |
| P08 | 0.10 | Complete air-path areas and moist-air density |
| P09 | 0.08 | Independent water loading and the two packing resistance coefficients |
| P10 | 0.12 | Component aerodynamic resistances and their total |
| P11 | 0.12 | Fan dynamic pressure, total pressure and consistently per-fan or aggregate shaft power in kW |
| P12 | 0.08 | Installed-specific-power calculation and its engineering verdict |

The weights follow engineering consequence and dependency breadth. The coupled
psychrometric, water-grid and thermal-selection chain (P01-P03) receives 0.50
because it establishes whether a tower size is feasible. Air-path, resistance
and fan duty (P08-P11) receive 0.42 because they determine hydraulic loss and
motor demand after selection. P09 and P12 receive 0.08 each: their five cells
remain material checks but cannot outweigh the upstream thermal and air-system
chains. This allocation prevents a five-cell downstream snapshot from scoring
above a live, correct thermal reconstruction.

More specifically, P01 and P02 are boundary/property prerequisites and receive
0.12 and 0.13; P03 owns the largest coupled candidate table and selected-case
thermal arithmetic and receives 0.25. P08 owns air-path geometry/density and
receives 0.10. P09's three empirical loading/resistance coefficients receive
0.08. P10 and P11 independently own component/total pressure and fan duty and
receive 0.12 each. P12's terminal installed-specific-power check receives 0.08.
These exact values are machine-owned by `task/tests/scoring_params.json`; the
verifier rejects a vocabulary mismatch or a sum other than 1.

### Owner-by-owner basis

All eight owners use `complete_prerequisite_chain`: an owner completes only when
every owned result agrees with the independent engineering calculation in all
ten recalculation cases. This calculation method prevents a baseline snapshot,
a disconnected terminal value or a few easy cells from standing in for a live
chain. The weighted sum still gives partial credit between independently useful
chains. Within an owner, a missing required result and a present but incorrect
result both make that chain incomplete: either leaves the corresponding
engineering responsibility unusable. The detail ledger distinguishes absence
from numerical/text mismatch at cell and scenario level; neither receives an
extra fixed penalty merely for being an error rather than an omission. Decision,
source-structure and chart damage are handled separately below.

**P01 — air-state boundary properties (13 cells, weight 0.12).** It measures
wet/dry-bulb conversions, saturation pressure, vapor state, moist-air density,
boundary enthalpy, hot-water saturation state and evaporation correction. These
values establish the thermodynamic boundary and mass basis used by candidate
airflow, transfer demand, air-path velocity and pressure loss. P01 depends only
on protected source operating inputs and published physical relationships; it
is upstream of P02, P03, P08, P10 and P11. Its 0.12 weight is a major prerequisite
share but remains below the coupled selection owner P03 because P01 alone does
not establish feasibility. Every owned result must pass all cases; a missing
property and a wrong property both set P01 completion to zero, with the specific
cell/scenario retained as evidence.

**P02 — water grid and saturation chain (40 cells, weight 0.13).** It measures
the segment interval, water-temperature grid, absolute temperatures and each
segment's saturation-pressure/enthalpy sequence. The transfer integral cannot
be interpreted without a coherent hot-to-cold or cold-to-hot water-side path.
P02 uses the protected hot/cold-water inputs and P01's thermodynamic context and
is a direct prerequisite for P03. Its 0.13 is close to P01 but slightly larger
because it owns the full 40-cell integration grid. The verifier accepts either
complete physical orientation, then requires that one orientation across every
case. A missing segment and a wrong/reversed subchain both make P02 incomplete;
a consistently equivalent full orientation remains correct.

**P03 — thermal candidate and packing feasibility (29 cells, weight 0.25).** It
measures five candidate airflows, evaporation correction, operating-line states,
transfer demand, available packing characteristic and selected-case transfer
arithmetic. This is the central cooling-tower selection responsibility: it turns
P01/P02 states and protected candidate inputs into a feasible minimum ratio. P03
depends on P01 and P02 and precedes the selected air-path, resistance and fan
chains. It receives the largest single weight, 0.25, because an otherwise polished
workbook without the live candidate/packing comparison cannot select a tower.
All 29 cells must pass all cases. Missing selected-case values in a feasible case
and values calculated from a wrong candidate both fail P03; a correct no-feasible
case must leave only the defined dependent results blank. E96 and the operative
verdicts are separately owned by `D_THERMAL_DECISION`, so they are not counted
again as P03 positive cells.

**P08 — air path and moist-air density (6 cells, weight 0.10).** It measures the
selected inlet path, fill/fan/outlet areas, fan annulus basis and moist-air density.
Those quantities convert the selected volumetric flow into component velocities.
P08 depends on protected geometry, P01's air state and the source-correct P03
selection and is prerequisite to P10/P11. Its 0.10 is below the thermal owner and
the complete resistance/fan pair because it supplies geometry and density rather
than the final pressure/power duty. All six results must pass every case; a blank
selected path when feasible and a wrong area/density basis both fail P08.

**P09 — independent loading/resistance coefficients (3 cells, weight 0.08).** It
measures water loading and the two empirical packing-resistance coefficients.
These values are professionally material inputs to packing resistance but are a
small, independently calculable subset, based on protected water flow/area and
the supplied correlation. P09 is used by P10 but does not establish candidate
feasibility or fan duty by itself. Its 0.08 deliberately prevents three terminal
coefficient cells from outweighing P01-P03 or P10-P11. All three must pass all
cases; omission and a wrong empirical/unit evaluation both make P09 incomplete.

**P10 — aerodynamic component resistance (7 cells, weight 0.12).** It measures
six component losses and their total. This chain determines the static pressure
the fan must overcome and exposes a wrong velocity, density or empirical factor
instead of accepting only a terminal total. P10 depends on P01 air properties,
P08 path geometry, P09 coefficients and the source-correct selected airflow; it
is a direct prerequisite for P11. Its 0.12 matches P01 and P11 because boundary
state, resistance and fan duty are comparably necessary engineering responsibilities.
All components and the total must pass every case. Missing one component and a
wrong component/total both fail P10; a correct total assembled from hidden wrong
components does not complete the chain.

**P11 — fan pressure and shaft power (3 cells, weight 0.12).** It measures fan
dynamic pressure, total pressure and shaft power in kW. This is the selected
equipment duty and catches Pa/kPa, seconds/hour and fan-count mistakes that can
turn a thermal selection into an unusable drive selection. P11 depends on P08
annulus/flow and P10 total resistance. Its 0.12 equals P10 because the required
pressure and resulting power are the coupled terminal air-system responsibility,
while remaining below P03's feasibility responsibility. A consistently per-fan
or aggregate power basis is accepted. Missing pressure/power and an incorrect
unit or fan multiplicity both fail P11 across the complete case set.

**P12 — installed specific power and verdict (2 cells, weight 0.08).** It measures
installed motor power per water flow and the stated pass/fail meaning against the
supplied limit. It is an important terminal adequacy check but uses only two
independent cells and does not replace thermal feasibility or calculated fan duty.
P12 depends on protected installed motor count/rating, water flow and the supplied
limit; it is intentionally independent of forcing a successful P03 selection.
Its 0.08 matches P09's small independent scope. Both cells must pass all cases
for strict completion. A missing value/verdict and an incorrect number/meaning
both fail P12. A correct meaning carrying an unsupported external standard
citation loses strict P12 credit as a provenance error, while lenient can still
recognize the usable positive/negative engineering conclusion.

These weights are based on engineering consequence, dependency position and
owned scope.

| Deduction | Retention | Trigger |
| --- | ---: | --- |
| D_THERMAL_DECISION | `max(0.3, 1 - 0.7e/40)` | `e` incorrect or missing required selection/feasibility decisions among E96/H96/H102/E103 across ten tested conditions |
| D_SOURCE_STRUCTURE | 0.9 | Original Chinese field labels, units or supplied engineering notes are overwritten |
| D_COMPARISON_CHART | 0.9 | The original thermal comparison chart no longer references both candidate demand and available-packing series |
| D_OPEN_SEMANTIC | 0.8 | Open engineering text invents source facts/standards or overstates what computed evidence establishes |

The damage calculation is multiplicative because each event reduces the value
of whatever positive engineering work remains, rather than inventing points or
applying a fixed total-score cap. `D_THERMAL_DECISION` scales continuously with
the number of affected decision cells: an isolated verdict error stays local,
while failure of all forty decisions retains 0.3. This reflects the growing
engineering harm without turning one equivalent-wording miss into a global
70% reduction. `D_SOURCE_STRUCTURE` and
`D_COMPARISON_CHART` each retain 0.9 because protected source interpretation and
the requested live comparison are local integrity responsibilities, not reasons
to erase otherwise correct thermodynamic and aerodynamic work. Missing and wrong
decision values trigger the same decision event; overwritten source text and
missing/incorrect chart series trigger their respective local event, with raw
evidence preserved in the ledger.

`D_OPEN_SEMANTIC` is source-bound and does not re-evaluate native calculations.
Its required binary IDs are `source_fidelity`, `conclusion_scope` and
`evidence_binding`. All three must pass the lenient `open_claim_scope` gate.
An invented external standard, catalog/test fact or universal/causal claim loses
20% of otherwise correct engineering work once; numerical P01-P12 credit remains
owned by the program judge. A conclusion explicitly limited to the same CASE
worksheet and to relationships directly controlled by the cited formulas is
bounded; universal, cross-condition or unsupported causal language is not.
Judge failure is infrastructure UNMEASURED.

Decision defects share one proportional event. Source preservation and chart
absence are separate integrity events. Selection and feasibility are not
additionally positive-scored. Once submitted E96 agrees within its published
tolerance, dependent arithmetic binds to the independently calculated
source-correct selection. A tolerant selector therefore cannot turn downstream
expectations into blanks. Verdict text accepts equivalent positive and negative
engineering conclusions after punctuation normalization.

Every calculated result is bound to its published source address, including E96
and the five-column candidate tables. This enforces the instruction to fill the
removed result cells in their original locations and prevents an unrelated
same-row blank from carrying a score. Original labels and unit cells are
protected; the three source worksheets retain their row/column bounds and
merged ranges. Numerical tolerances accept modern Kelvin conversion, equivalent
formulas, composite trapezoid integration within engineering tolerance and
equivalent Chinese verdicts.

The unbound segment numbering permits either a hot-to-cold or a cold-to-hot physical grid. The complete water-temperature, absolute-temperature and saturation-property chain must share one orientation across all scenarios. Operating lines and the resulting transfer integral remain independently checked across the same perturbations. Reversing one subchain or reversing the grid without the corresponding integral is not an equivalent solution.

The source names the fan annulus area and shaft power without specifying a single-fan or aggregate quantity. Either consistent area representation is accepted; the physical dynamic/full pressure must still be correct. Shaft power may consistently report one-fan or total-fan kW across all scenarios. Incorrect extra or missing fan-count factors in the coupled pressure/power chain are rejected. No model identity participates in binding a quantity basis.

## Lenient Score

Lenient is the conjunction of ten separately measured binary must-haves: air/water boundary properties; thermal/packing calculations; minimum feasible selection and operative verdicts; air path and independent coefficients; resistance; fan pressure/power; installed-specific power; original labels/units; comparison chart; and source-bounded open claims. Each verdict is backed by its atomic cell/scenario evidence or integrity evidence in `reward_detail.json`. It is not a threshold on the strict score.

Minimum usability preserves the exact air/water property chain, the correct minimum feasible selection and operative verdicts, and the exact installed-specific-power check. Candidate airflow, transfer integral, available packing performance, evaporation correction, air-path geometry, independent resistance coefficients, total resistance and fan pressure/power must agree within 5% across all ten cases. This explicitly permits engineering approximations while the strict lens retains its finer numerical tolerance and every original intermediate result. Selected-case transfer values and all six resistance components must be finite, positive and present when feasible, and blank when infeasible. Missing detailed outlet-enthalpy display cells can therefore lose strict credit without preventing a usable thermal selection. Missing fan power, incorrect unit factors, constants that fail perturbations, false thermal conclusions and inconsistent fan multiplicity fail the lenient conjunction. Original source labels/units and the live comparison chart remain mandatory.

The lenient hard gates correspond to operational dependencies, not local
editorial quality. P01/P02 supply boundary states; P03 and the four decision
cells establish a feasible minimum candidate; P08-P11 establish a calculable
air path, resistance and fan duty; P12 requires the correct specific-power
number and positive/negative engineering meaning; source labels/units preserve
interpretability; and the live demand-versus-capacity chart preserves the
requested comparison. An unsupported standard citation attached to an otherwise
correct verdict loses strict P12 credit but does not make the engineering check
unusable. Worksheet bounds or merged-range changes lose strict source-structure
credit, while lenient fails only when protected source labels/units are changed.
The exact required IDs are `air_state_and_water_saturation`,
`thermal_calculations_and_packing`,
`minimum_feasible_selection_and_verdicts`,
`air_path_and_independent_coefficients`, `aerodynamic_resistance`,
`fan_pressure_and_shaft_power`, `installed_specific_power`,
`original_labels_and_units`, `original_comparison_chart`, and `open_claim_scope`. They are declared
in `scoring_params.json`; the verifier refuses to score if its measured ID set
does not match that declaration exactly.

## Recalculation Cases

The ten cases are baseline, ambient pressure/temperature, water duty, water outlet, air path, flow/motor rating, motor rating, parallel fan count, humid boundary and candidate-center changes. Packing depth stays at the supplied empirical-correlation depth. Correct no-feasible cases leave the selected-case sizing values blank while preserving independent geometric/loading values and the installed-specific-power calculation.
