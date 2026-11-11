---
name: capacitated-network-design
description: Design and audit facility-use and demand-allocation plans over a prevalidated eligibility graph with finite capacity and variable economics. Use for distribution, fulfillment, production, or service networks where coverage must be protected before cost is compared and unsupported closure claims must be separated from operating-use decisions.
---

# Capacitated Network Design

## Trigger and boundary

Use this method after demand grain and feasible demand-to-facility edges have been
reconciled. It applies when individual demand units compete for facility capacity and
the requested decision includes both allocation and facility use.

This method can support an operating-period **use / not used** recommendation from
flows. It cannot support permanent closure, greenfield construction, lease exit,
inventory policy, resilience, tax, or fixed-cost conclusions unless those inputs are
actually supplied. Preserve that boundary in the decision artifact.

## Service-First Network Design framework

Use the **Service-First Network Design (SFND)** framework. Its judgment criteria are:

1. **Feasibility before economics:** only prevalidated edges enter the model.
2. **Objective hierarchy:** protect the declared service objective before footprint
   compactness or variable cost is optimized.
3. **Unit-consistent capacity:** capacity consumption matches the capacity table's
   business unit.
4. **Flow-derived footprint:** a facility-use state follows from valid assigned flow.
5. **Closed population:** each demand unit is assigned once or retained once as an
   explicit exception.

The mandatory intermediate artifact is a model control record:

```text
demand unit | capacity unit | primary objective | secondary objective | tie rule | edge count | facility count
```

## Objective-hierarchy declaration

Write the optimization priority before solving. When the business request includes
both service and operating-footprint compactness, use a lexicographic sequence:

1. maximize feasible service under eligibility and capacity;
2. fix that service level;
3. minimize the number of facilities with positive flow;
4. fix both the service level and facility count;
5. minimize supported variable cost inside that frontier.

Do not replace the sequence with an arbitrary penalty unless the business has supplied
a defensible value for unserved demand. A one-dollar cost improvement must not trade
away a service unit merely because the objective coefficients share a formula.

Persist each objective value before starting the next stage. If a later data change
alters eligibility or capacity, invalidate all stages and solve again. A cost result
from the old feasible region is no longer admissible.

Define facility use through positive flow when fixed opening economics are absent. A
binary location variable must be linked in both directions: flow requires use, and a
published used facility must carry flow. Otherwise a count objective can spend its
allowance on arbitrary zero-flow sites.

If priorities differ by customer or service class, define the tiers and optimize them
in order. Do not assume all demand has equal priority, and do not invent priority
weights absent from the materials.

## Capacity-constrained allocation

Use one binary assignment decision for each eligible demand-facility edge. A standard
core has these constraints:

```text
for each demand i:    sum_j x[i,j] <= 1
for each facility j: sum_i load[i] * x[i,j] <= capacity[j]
```

Set `load[i]` to one only when capacity is stated in orders or jobs. If capacity is in
units, weight, pallets, labor hours, or another measure, use that measure explicitly.
Handling cost may use a different quantity basis from capacity.

Never create variables for ineligible edges. This makes an incorrect join visible
instead of allowing the optimizer to choose it and trying to filter it afterwards.
For every assigned unit, persist the selected facility and the eligibility evidence
key used to create its variable.

Use `scripts/check_assignment_feasibility.py` to audit an exported assignment table;
it does not produce an allocation:

```bash
python scripts/check_assignment_feasibility.py \
  decisions.csv capacities.csv \
  --unit-id order_id --facility-id facility_id \
  --status-column decision --assigned-value assigned \
  --capacity-column capacity --report feasibility.json
```

When allowed pairs are available as a separate file, add `--allowed-pairs` so the
audit also detects assignments outside the feasible graph.

## Variable-cost attachment

Attach cost only to eligible edges and keep components separately auditable. A common
per-edge structure is:

```text
handling = order quantity * facility handling rate
freight  = applicable transport charge, or the stated customer-arranged amount
variable cost = handling + freight
```

Use the correct basis for each component. Shipment weight selects and prices a freight
band; order quantity may price handling. Minimum charges apply after the band is
selected. Do not reuse historical freight totals where the current rate table supports
a recomputation.

Store the tariff evidence key and component values beside each assigned unit. An
aggregate cost with no edge-level lineage is not closed, even if the total is
plausible.

When no fixed cost, opening cost, or closure benefit is supplied, variable cost can
rank feasible allocations but cannot economically determine how many facilities
should exist permanently.

## Flow-derived facility footprint

Build one row per facility after allocation. At minimum, reconcile:

```text
facility_id | valid assigned load | capacity | unused capacity | utilization | period-use decision | boundary note
```

A facility with positive valid flow is used for the modeled period. A facility with
zero flow is not used by this plan. Neither result alone means the asset should be
permanently opened or closed.

Check facility status against detail, not the optimizer's variable name. If the model
contains a facility binary without a fixed charge, it may be one in an arbitrary
zero-flow facility; derive the published use state from actual flow instead.

If multiple service-optimal, cost-equivalent allocations exist, alternative facility
mixes may be equally defensible. Report the selected tie rule and avoid claiming
uniqueness unless tested.

## Residual-demand disposition

Every source demand unit must end in exactly one state:

- assigned to one eligible facility within capacity;
- structurally unsupported because it had no pre-capacity edge;
- capacity-displaced despite at least one pre-capacity edge;
- unresolved due to an explicit input defect.

Do not omit residual demand from the workbook and do not force it into fictitious
capacity. Persist one record per unassigned unit with its pre-capacity candidate count
and cause class. This makes service loss attributable to the network rather than to an
unexplained filtering step.

Reconcile capacity-displaced counts only after invalid assignments are removed. A
demand unit assigned over capacity remains an invalid assignment, not achieved
service.

## Optimality and sensitivity record

Record solver status, primary objective value, secondary objective value, and material
binding capacities. Distinguish proven optimality from a time-limited incumbent. If a
heuristic is used, provide its feasibility result and avoid an optimality claim.

Run at least these decision checks:

- Recompute facility loads from exported assignment rows.
- Recalculate cost components independently for a sample spanning service modes,
  tariff boundaries, and minimum-charge cases.
- Verify that no lower-cost comparison serves fewer primary-objective units.
- Identify whether small capacity additions would recover displaced demand, but do not
  present them as approved expansion without investment inputs.
- Revisit the facility footprint if an eligibility correction changes any assigned
  flow.

## Single-node failure screening

When the brief asks how the selected operating footprint behaves after a facility
loss, construct the event set from the primary **positive-flow** facility register.
Do not guess a few important sites and do not treat every candidate as a required
primary event unless the decision asks for that scope.

For each event:

1. remove exactly one required facility before variables are created;
2. retain the current product, customer, dispatch, service, and tariff rules;
3. allow only the recovery facilities authorized by the brief;
4. maximize recoverable demand under remaining capacity;
5. fix that recovery level and minimize supported variable cost;
6. record the unavailable facility, recovered and residual populations, minimum
   recovery cost, and solve status.

Recovery facility count is not automatically a decision objective. Do not carry a
primary compactness constraint into recourse unless the business says the same count
or same footprint must remain fixed.

Select the governing event with a declared comparison tuple. When lower recoverable
service governs and higher minimum recovery cost breaks a service tie, sort on exactly
those values and retain the full event table so the selection can be replayed. Do not
use primary throughput, cost alone, or a historical outage label as a proxy.

## Governing-event recourse closure

Produce a complete allocation for the governing event, not only its headline service
percentage. Rebuild the candidate edge set after the failed facility is removed and
reclassify residual demand against that event-specific graph:

- a unit whose only current path used the failed site is structurally unsupported in
  that event;
- a unit with a remaining path but no assignment at the recovery maximum is
  capacity-displaced;
- no recovered unit may consume capacity or a route at the unavailable facility.

Close recovery with the same controls used for the primary plan: population
conservation, unique assignment, remaining-edge eligibility, facility load, route and
cost evidence, and detail-to-summary reconciliation. A service maximum without an
order-level feasible realization is only an upper bound, not an operating plan.

## Closing reconciliation

Close the model only when:

- assigned units + explicit exception units = source demand units;
- each assigned unit appears once and uses an eligible edge;
- recomputed facility loads do not exceed capacity;
- reported service equals the count or load of valid, capacity-respecting assignments;
- facility use states agree with positive valid flow;
- detail cost components reconcile to facility and executive totals;
- permanent network claims do not exceed the economics supplied.

If any equality fails, leave the model in an exception state and repair the earliest
upstream artifact that introduced the difference.
