---
name: airfield-protection-geometry
description: Convert airfield and heliport protection criteria into auditable plan-view station-offset geometry. Use for primary surfaces, clear zones, accident-potential zones, approach-departure envelopes, reciprocal ends, flared widths, and conditional visual-aid surfaces represented in CAD or GIS.
---

# Airfield Protection Geometry

Use station-offset construction to keep lengths, full widths, half-width offsets, and reciprocal ends distinct. Derive geometry only after applicability is closed.

## Define the Geometry Frame

Set the facility reference point at station zero. Put the principal approach axis on one coordinate axis and the transverse offset on the other. Record whether stations are measured from the facility center, a primary-surface edge, or a threshold.

For every zone, record:

```text
name | start station | end station | start full width | end full width | source
```

Do not enter half widths in a full-width field. If a criterion gives a square dimension, distinguish the central square boundary from the start of a longitudinal zone.

## Construct One End from Dependencies

Build one approach end in sequence:

1. central constructed or operational pad;
2. primary surface around it;
3. clear or protection zone beginning at the primary edge;
4. downstream land-use zone beginning at the clear-zone end;
5. any conditional approach-departure envelope beginning at its separately defined datum.

For a trapezoid with stations `s0`, `s1` and full widths `w0`, `w1`, the four plan vertices are:

```text
(s0, -w0/2), (s1, -w1/2), (s1, w1/2), (s0, w0/2)
```

This is a coordinate transformation, not a design rule. The values and their controlling applicability must come from the project evidence.

If the criteria define consecutive zones, force continuity: the downstream zone's start station and width must equal the upstream zone's end station and width unless the governing source expressly defines a discontinuity.

## Mirror Reciprocal Geometry

Derive the first end completely, then mirror coordinates through the facility reference point for a reciprocal straight end. Do not independently retype the second end. Mirroring prevents sign errors but does not establish that reciprocity is applicable; that is an upstream scope decision.

Keep left and right polygons separate even when they touch the same primary surface. This supports independent checking and future revision.

## Break Symmetry at a Conditional Boundary

Separate facility-wide geometry from end-specific geometry before mirroring. Shared primary, clear-zone, or land-use criteria may remain reciprocal while a visual aid or operational condition changes only one approach-departure surface.

Use one row per end for conditional surfaces:

```text
end | datum | activating condition | slope basis | terminal-height basis | length | terminal width | status
```

Mirror only rows whose activating conditions and resolved inputs match. If one end is fully resolved and the other is not, draw the resolved boundary once and place the unresolved end on hold. Do not mirror the resolved end merely to make the sheet look balanced.

## Separate Ground Zones from Airspace Surfaces

Land-use zones and sloped airspace surfaces can overlap in plan while representing different controls. Draw them as separate semantic objects.

- Ground zones commonly have staged lengths and plan widths.
- An approach-departure clearance surface may have a slope-derived length and a different terminal width.
- A visual-aid condition can enlarge the airspace surface without changing the underlying clear-zone or accident-potential-zone lengths.

Do not replace the staged ground-zone polygons with the outer airspace envelope. Do not truncate a conditional airspace surface merely because a shorter ground zone ends first.

## Generate Candidate Vertices

Use the bundled calculator after supplying values from the evidence ledger:

```bash
python3 scripts/station_offset.py \
  --start 20 --length 130 --start-width 60 --end-width 96 --both
```

The tool emits candidate vertices and measured invariants. It does not choose applicable values. Save its output as scratch evidence, then transfer the verified vertices into the DXF.

## Perform Geometric Closure

Reopen the final drawing and check:

- each boundary is closed and non-self-intersecting;
- start and end stations measure from the correct datum;
- measured full widths equal twice the absolute transverse offset;
- consecutive zones share the intended boundary;
- reciprocal ends are mirror images within drawing precision;
- centroids lie on the approach axis;
- the longest conditional envelope is not clipped by drawing extents;
- dimensions and labels name full width or offset unambiguously.

Revisit applicability if an impossible geometry appears, such as a downstream start width that conflicts with the upstream terminal width. Do not silently average conflicting values.

## Carry Uncertainty Correctly

A 2D plan cannot establish grades, elevations, object penetrations, structural capacity, or surface material unless those facts are explicitly present in the supplied record. Keep those conditions open and state what survey, profile, or design record would close them. An unverified property is not compliant merely because the plan contains no conflicting mark.

A parameterized surface is also unresolved when the supplied record states how it must be adjusted but omits an input to that relation. Do not infer an unstated relation from a single worked case. Persist the known datum, activating condition, conflicting values, and missing parameter; then omit the controlling polygon until the dependency is closed.
