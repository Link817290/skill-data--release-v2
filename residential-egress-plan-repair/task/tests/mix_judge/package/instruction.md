# Project authorization

The first-floor residential plan is at permit-coordination review. Its internal hall and door arrangement needs an engineering fire-egress handoff because the dimensioned drawing and the governing safety document must support one release decision.

# Commission

Create empty placeholders for every requested deliverable before beginning the review. Use the supplied `/workspace` project record, keep both source files unchanged, and work without network material. Prepare an English handoff from `residential_floor_plan.dxf` and `fire_safety_code.pdf`, saving `inspection_report.json`, `layer_inventory.json`, `extracted_original_layout.json`, `violations_before.json`, `repaired_layout.json`, `changes.json`, `repair_memo.md`, and `repaired_plan.dxf` under `/workspace/output/`. Keep identifiers stable, preserve the source drawing context in the repaired DXF, and confine design changes to the first-floor `HALL` egress geometry and its immediately affected door operation.

# Record conventions

So the handoff stays machine-traceable, use these identifiers: the first-floor `HALL` egress route is `HALL-ROUTE-01`, its door is `HALL-DOOR-01`, and the three review items are `F-HALL-WIDTH` for the route clear width, `F-HALL-DOOR` for the door clear opening, and `F-HALL-SWING` for that door's operation. Repeat the same identifiers across the JSON records, the memo, and the change log. Give every finding its own separate fields for the observed measurement, for the requirement it is compared against, for its disposition, for its status, and for an evidence list that names the supplied file and the place inside it. Keep JSON coordinates and polygons in the drawing's native unit, and restate in metres any value that is compared with the safety document. Draw geometry you add to the repaired DXF on new layers whose names begin with `REPAIR-`.

# Issued package

The package is ready for coordination when it records the measured original condition, applicable findings with their evidence, a local plan-view repair, and a memo whose dimensions and dispositions agree with the JSON records and the readable DXF. The handoff must distinguish confirmed repairs from items that remain for coordination; decisions outside the supplied project record are not part of this issue.
