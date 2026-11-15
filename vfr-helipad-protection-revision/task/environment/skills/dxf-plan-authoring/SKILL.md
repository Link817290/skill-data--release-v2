---
name: dxf-plan-authoring
description: Create, revise, and quality-check 2D engineering plans in DXF with explicit drawing units, stable coordinates, semantic layers, closed boundaries, dimensions, and machine-verifiable geometry. Use when a task requires a CAD-neutral DXF deliverable or when plan geometry must be generated and inspected from Python or the terminal.
---

# DXF Plan Authoring

Use a drawing contract that makes the engineering geometry both readable to a reviewer and independently measurable. Treat presentation and geometry as separate obligations.

## Establish the Drawing Contract

Before adding entities, write down four decisions in scratch state:

1. Modelspace unit and the corresponding DXF `$INSUNITS` code.
2. Origin and axis convention, including the meaning of positive station and offset.
3. Semantic object classes that need separate layers.
4. Which closed entities carry the controlling boundaries.

Do not infer the unit from annotation text. Set it in the DXF header. Do not use paper-space scale to encode model dimensions.

## Build Controlling Geometry First

Create geometry in dependency order:

1. reference axes and origin;
2. controlling boundaries as closed lightweight polylines or circles;
3. secondary construction lines;
4. dimensions and leaders;
5. notes and legend.

Keep one controlling boundary per semantic object. Hatches, duplicate outlines, and dimension extension lines are presentation entities, not alternative definitions of the boundary.

For a polygon, use a closed `LWPOLYLINE` with an explicit vertex sequence. Avoid a collection of disconnected lines when downstream review needs area, width, or containment checks. If a curve matters, use an arc or bulged polyline rather than many unlabelled short chords.

## Use Semantic Layers Without Encoding Answers

Choose short, professional names that describe object roles. Separate at least:

- reference or centerline geometry;
- operational or constructed surfaces;
- protective or clearance envelopes;
- dimensions;
- notes.

Do not encode pass/fail status or a required numeric value in a layer name. A reviewer should be able to turn reference geometry off without hiding a controlling boundary.

## Author with `ezdxf`

Use R2010 or a later broadly supported version unless the delivery contract says otherwise.

```python
import ezdxf

doc = ezdxf.new("R2010", setup=True)
doc.header["$INSUNITS"] = 6  # choose the code that matches the actual model unit
msp = doc.modelspace()

doc.layers.add("BOUNDARY", color=3)
points = [(0.0, -4.0), (12.0, -7.0), (12.0, 7.0), (0.0, 4.0)]
msp.add_lwpolyline(points, close=True, dxfattribs={"layer": "BOUNDARY"})
doc.saveas("candidate.dxf")
```

The example values illustrate API shape only. Supply coordinates derived from the governing project evidence.

Prefer ordinary `TEXT` or `MTEXT` for labels. Include units in dimension labels when the dimension entity style does not make them evident. Place annotations outside dense boundary intersections.

## Verify the Saved File

Saving without an exception is not a CAD check. Reopen the saved file and verify:

- the header unit matches the coordinate values;
- expected boundary entity types exist;
- every controlling polyline is closed;
- extents are finite and at the intended scale;
- vertices have the intended Z elevation for a plan view;
- no controlling boundary is a duplicate or self-intersecting loop;
- labels and dimensions exist in modelspace.

Run the bundled inspector:

```bash
python3 scripts/inspect_dxf.py candidate.dxf --json /tmp/dxf-inspection.json
```

Read its JSON summary. Resolve warnings before delivery. The tool reports structure and measurements; it does not know which geometry the project requires.

## Represent Design Holds Without False Geometry

When a required boundary cannot be dimensioned from the available record, do not draw a plausible closed polygon on a controlling layer. A reviewer or downstream parser may treat that polygon as approved geometry even if nearby text calls it provisional.

Instead:

- keep any known datum or reference axis as non-controlling construction geometry;
- add a visible note or leader that names the affected object, the open dependency, and the evidence needed to release it;
- place hold graphics on a distinct coordination or hold layer;
- ensure the layer name and note do not encode a guessed numeric answer;
- verify that no duplicate or mirrored controlling boundary remains beneath the hold annotation.

The final drawing can therefore be complete as an issue-for-coordination artifact while still refusing to fabricate a design boundary.

## Close the Handoff

Recompute declared widths and lengths from the saved DXF, not from the variables used to create it. Compare the reopened-file measurements with the report or memo. Reconcile the set of drawn controlling boundaries as well as their dimensions: a boundary reported on hold must not appear as completed geometry. A mismatch requires revising whichever artifact is wrong and repeating the check.

Stop and disclose a limitation instead of drawing guessed geometry when the unit, origin, or controlling boundary cannot be established from the supplied evidence.
