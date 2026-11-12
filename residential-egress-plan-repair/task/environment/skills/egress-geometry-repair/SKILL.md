---
name: egress-geometry-repair
description: Use when a plan-view egress review requires measured wall and door geometry to be compared with a rule and repaired locally in a DXF while preserving unaffected layout.
license: Proprietary
---

# Egress geometry repair

Make the geometry answer the finding. Derive the route width from the two interior faces that bound the travel path, and derive a door's clear opening from its opening-line endpoints. Keep original and repaired coordinates in the same coordinate frame so a reviewer can see what moved.

## Measurement and conversion

Declare the drawing unit once, then convert the measured value into the rule's unit with full precision. Store both the native measurement and the converted value in the report. Round display values only after the comparison; retain a small tolerance for CAD rounding, not for a materially undersized route.

## Object identity and evidentiary limits

Bind each measurement to the entity that actually serves the reviewed route. Start from the room or route anchor, identify the wall face or opening on that route boundary, and record the source handle or coordinates that distinguish it from nearby openings. A line on an opening layer establishes its plan location and geometric span; by itself it does not establish the installed leaf, jamb deductions, hardware, swing, or effective clear opening. Keep those quantities on a coordination hold unless the supplied record establishes them.

Derive the reviewed room from topology before reading a nearby size label as its boundary. Seed the search at the room label, trace the nearest continuous opposing wall faces that enclose that anchor, and select a door only when its opening segment lies on one of those boundary faces. Room-size text and door tags are corroborating annotations: use them to cross-check the traced geometry, but do not extend a room through intervening wall returns or select a nearby tagged opening that does not intersect the traced room boundary. When two candidate openings are close, record both candidates and the boundary-intersection test that admits one and rejects the other.

Apply a code threshold only after its scope is established. When the record does not show whether an internal opening is a dwelling entrance, safety exit, or another classified door, record the relevant threshold as a conditional comparison and identify the missing classification evidence. Do not turn a geometric span into a compliant clear-width conclusion merely because the span exceeds a cited number.

## Local repair pattern

1. Identify the smallest wall face or door operation that causes the finding.
2. Preserve labels, adjacent rooms, and compliant openings unless they must move to clear the route.
3. Extend a route boundary parallel to itself when widening is the design action; keep the opposite boundary fixed so the change is auditable.
4. Represent a door swing explicitly. A leaf that enters the travel polygon is a plan-view conflict; an outward or sliding representation is acceptable only when the repaired lines show the clearance.
5. Add closed polylines for the repaired room/route and clear annotation text. Avoid self-intersections and duplicate coincident boundaries.

For a concept-level wall relocation, distinguish the retained face, the existing face proposed for removal, and the proposed replacement face. Show the short end connections or explicitly carry them as coordination items. Label the geometry as proposed until wall thickness, adjacent-room effects, structural/services impacts, and construction status are supported by the project record.

The repair drawing should contain a dedicated layer for each changed object and should not imply that a condition was resolved if the required dimensional input is missing. Keep an explicit hold or review marker for any unresolved item.

## Programmatic checks

Use `ezdxf` to reopen the saved drawing. Check that repaired polylines are closed, have finite coordinates, and match the JSON extents within the declared tolerance. Check that the door segment and its swing representation agree with the JSON disposition. A parser-based check is more reliable than a screenshot or entity order.
