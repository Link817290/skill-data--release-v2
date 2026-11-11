---
name: network-constraint-reconciliation
description: Reconstruct auditable assignment eligibility from related demand, facility, product, customer, port, service, and tariff tables. Use when a network decision depends on several workbooks or sheets whose records have different grains, directional restrictions, historical choices, or incomplete joins.
---

# Network Constraint Reconciliation

## Trigger and boundary

Use this method before optimizing a supply-chain allocation when no single table
contains the complete feasibility rule. It is especially important when an order
history includes old routing choices beside current master data.

This method determines which demand-to-facility relationships the supplied records
support. It does not choose the final facility footprint, prove permanent closure,
invent missing lanes, or infer commercial terms from labels alone. Treat unresolved
semantics as an explicit uncertainty or exception, never as permission to join.

## Constraint Evidence Ledger framework

Maintain a **Constraint Evidence Ledger (CEL)** while working. A CEL is complete only
when every eligibility decision can be replayed from source identifiers and every
source table has a declared grain and role.

The framework has five judgment criteria:

1. **Grain:** one row means one stated business unit.
2. **Authority:** each field is classified as current rule, historical observation,
   descriptive attribute, or unresolved.
3. **Direction:** each restriction names its subject, allowed object, and direction.
4. **Conjunction:** a candidate survives only if every applicable rule is satisfied.
5. **Evidence binding:** every retained or rejected pair carries source identifiers or
   a recorded rule result.

Create the ledger before bulk joins. Add one row per source relation with at least:

```text
relation_id | source object | grain | key fields | role | direction | null policy | row count | notes
```

Use `scripts/profile_relation_tables.py` to inventory workbook sheets and likely key
columns. The report is a starting artifact, not a semantic conclusion:

```bash
python scripts/profile_relation_tables.py input.xlsx --output relation_profile.json
```

## Demand-grain declaration

Define the atomic planning unit before any merge. An order, order line, pallet, and
shipment are not interchangeable. Record the demand key, quantity unit, capacity
consumption unit, service field, weight field, and destination field.

Run these controls at this step:

- Count source rows, non-null keys, and distinct keys.
- Identify duplicate keys and decide whether they are duplicate records or a finer
  grain. Do not silently deduplicate.
- Record which numeric field drives handling cost, which drives freight, and which
  drives capacity. Similar column names do not establish common units.
- Preserve the original identifier as text. Avoid converting identifiers through
  floating point or dropping leading zeros.

The intermediate artifact is a **demand control row** containing source count,
distinct-key count, total relevant measures, and the declared atomic unit. Stop if the
grain is unresolved; a later optimizer cannot repair a many-to-many merge explosion.

## Table-role and relation-direction declaration

For each non-demand table, write a plain relation statement before using it. Use the
form:

```text
subject --predicate--> object | condition | source key
```

Examples of distinct meanings are:

```text
facility --can handle--> product
facility --may serve only--> listed customers
facility --can dispatch through--> origin port
origin + destination + service + weight band --selects--> tariff row
```

Direction is operational, not grammatical. A list of customers under a facility can
mean that the facility is restricted to those customers; it does not automatically
mean those customers are restricted to that facility. Check the table's labels,
population pattern, and any supplied notes together. Record the interpretation in the
CEL and keep the raw keys that support it.

Separate **current constraints** from **historical selections**. A historical plant,
port, carrier, transit time, or price is evidence of what happened, not automatically
a rule for the new plan. Historical fields may be used for reasonableness checks only
after the current feasible graph has been constructed.

If a later table contradicts an earlier role declaration, revise the declaration and
all affected eligibility rows. Never let a downstream calculation continue using a
relation already ruled non-authoritative.

## Candidate-edge construction

Decompose the problem into demand-facility pairs. Begin with the facility universe and
remove a pair for each failed applicable predicate. Keep a per-unit **edge register**:

```text
demand_id | facility_id | product_ok | customer_ok | dispatch_ok | service_ok | tariff_ok | eligible | evidence_ids
```

Apply predicates as an intersection, not a union. A product-capable facility with no
supported outbound path is not eligible. A valid tariff cannot override a customer
restriction. An absent mapping is not the same as a wildcard unless the supplied
material defines that behavior.

Use fail-closed handling for malformed references: unknown facilities, products,
ports, or services stay outside the feasible graph and enter the input audit. Do not
extend the master universe merely because a code occurs in a child table.

After each demand unit, persist its candidate count and elimination counts. This
per-unit cadence prevents the tail of a large population from disappearing into a
summary join.

## Transport-lane and tariff reconciliation

For company-arranged freight, prove a continuous path from facility to allowed origin,
origin to destination, service level, and an applicable weight interval. Bind the
selected tariff row or its full composite key to the pair.

For a banded rate table:

```text
freight charge = max(minimum charge, rate per weight unit * shipment weight)
```

Confirm interval endpoint policy from the material. If adjacent bands share a
boundary, record which row is selected and test the boundary explicitly. Never
multiply the freight result by order quantity unless the rate definition says that
weight is per unit.

Customer-arranged freight is a separate commercial state, not a missing tariff. When
the supplied scope makes company freight zero, record that state and retain handling
economics; do not manufacture a carrier or rate row to make the join complete.

The artifact from this step is a **route evidence row** for every retained edge:

```text
demand_id | facility_id | origin | destination | service | shipment_weight | tariff_key | freight_basis
```

## Exception-cause boundary

Classify exceptions only after the pre-capacity graph is frozen:

- **Structural:** the demand unit has zero feasible facility edges before capacity is
  applied.
- **Capacity-displaced:** at least one feasible edge exists, but the capacity-constrained
  allocation leaves the unit unserved.
- **Input unresolved:** a source defect prevents a defensible eligibility decision.

Do not call all unserved demand a capacity shortfall. Conversely, do not label a unit
structural merely because its historically used facility is now infeasible; another
current facility may still be eligible.

Keep one exception record per unserved demand identifier with the failed predicate or
the capacity state that caused it. If a later correction adds or removes an edge,
revisit both the exception class and every downstream capacity total.

## Event-specific graph revision

When a scenario removes a facility or lane, derive its feasible graph from the closed
current graph rather than rebuilding joins from history. Copy the evidence ledger,
mark the unavailable object, remove every incident candidate edge, and preserve all
other predicate results. This creates a reviewable delta between primary and recovery
feasibility.

Recompute candidate counts and exception causes after the removal. A unit may move
from capacity-displaced to structural when its last remaining edge belonged to the
failed facility; another unit may retain several recovery paths. Do not reuse the
primary exception label without this event-specific check.

Close each revised graph with three controls:

- every retained edge existed in the current graph and avoids the unavailable object;
- every rejected incident edge carries the event identifier and removed endpoint;
- retained-edge, zero-edge, and unresolved populations reconcile to the same demand
  grain as the primary graph.

## Closing reconciliation

Before passing the graph to network design, close all of these controls:

- Source demand units = units with at least one eligibility register result.
- Retained edges + rejected pair evaluations reconcile to the declared candidate
  universe or an explicitly documented pruning rule.
- Every retained edge has source-bound product, customer, dispatch, and service
  evidence.
- Every zero-edge demand unit appears in the structural or unresolved register.
- Historical selections have not entered the constraint graph as mandatory rules.
- Relation interpretations in the CEL match the logic used by downstream calculations.

Do not proceed on a mismatch. Persist the counts and the mismatch itself, correct the
upstream relation, and then regenerate affected rows.
