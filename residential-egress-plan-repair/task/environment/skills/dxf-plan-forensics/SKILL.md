---
name: dxf-plan-forensics
description: Use when a plan-review task supplies a DXF and you need a reproducible inventory of entities, layers, units, text anchors, wall runs, openings, or source geometry before making a drawing change.
license: Proprietary
---

# DXF plan forensics

Treat the supplied drawing as an evidence record. Work from a copy in memory or in the output file; never edit the mounted source. Record the DXF release, `$INSUNITS`, layer names, entity counts, and the entity types that carry the geometry you rely on. A layer name is a useful clue, not proof of meaning: confirm a wall, opening, or label by its coordinates and neighboring entities.

## Establish a coordinate ledger

Create a small ledger for each inspected element:

| field | purpose |
| --- | --- |
| stable id | survives extraction, review, and repair |
| source layer/entity handles | lets another drafter find the original |
| geometry | points, extents, orientation, and closure state |
| unit interpretation | drawing unit and any conversion used in the report |
| text anchor | nearby label or note, if present |

Use `ezdxf` or another structured parser rather than scanning DXF text with regular expressions. For a line, normalize its endpoints and orientation; for a polyline, preserve vertex order and its closed flag. Keep source coordinates at their native precision and round only presentation values.

## Locate a room or route

Start from the label anchor, then select the continuous interior wall faces that actually bound that label. Reject short returns, dimensions, hatches, and title-block graphics that happen to be nearby. When a wall has a gap, inspect the opening layer and the adjacent wall endpoints together; an opening is not a wall failure merely because the wall is discontinuous there.

## Inspect with the helper

The bundled `scripts/inspect_dxf.py` emits a JSON inventory and text-anchor list. It is intentionally descriptive: it does not decide compliance or generate repair conclusions.

```bash
python3 /workspace/skills/dxf-plan-forensics/scripts/inspect_dxf.py \
  /workspace/residential_floor_plan.dxf > /tmp/dxf_inventory.json
```

Use that inventory to seed the coordinate ledger, then re-check critical extents directly with the parser before writing the handoff.
