# Client Effects Verification Handover

FX-301 through FX-305: repaired project, original assets, fresh previews and ticket register are supplied.

## Reproduction
Use the supplied task image (Godot4.4.1/Python3), from /workspace with this delivered directory at output/.
The image default user requires writable Godot user-data. Use a writable HOME, for example:
HOME=/tmp python3 /opt/fx-tools/export_effects.py --project output/project --output output/preview
From the delivery root, use --project project --output preview with the same writable HOME context.
For an independent fresh capture, change only the output path to /tmp/reference-repeat. Then compare state records and all decoded image channels:
python3 output/verification/compare_preview.py --submitted output/preview --fresh /tmp/reference-repeat --output /tmp/preview-correspondence.json
Different PNG encodings are acceptable when decoded image pixels match. Reproducibility does not by itself establish correctness; independent API and world/timing observations below remain separate.
The public API regression is: HOME=/tmp python3 output/project/tools/retest.py --output /tmp/api-repeat

## Observed Scope And Outcomes
verification/api/runtime-checks.csv and timing-observations.csv retain actual frame-by-frame public node/anchor/source-frame presence and release observations. Direct nearby spawn_hit calls produce two distinct objects and no impact notification. Hit release is11/30seconds within one60Hz sample; appearance starts at source04 at its ground anchor and is released after1.5seconds. Separate cast calls exercise both diagonal directions, constant-speed paths, event payloads/cardinality, arrival hit playback and final absence.
verification/world-heading.json retains independent engine-tick samples of actual global headings and world paths under identity and rigid caller rotations. It includes two directions per caller basis and actual public impact payloads. No candidate clock or completion flag is treated as the independent time/event recorder.
verification/demo.json observes the ordinary configured main scene with no verification bypass: impacts at0.65 and0.95seconds at(480,190), with no effects at2seconds. verification/tested-build.json binds the exact source files and engine invocations/results.
before/ contains actual checks run on the supplied faulty client project using the same external procedures. Those checks fail; the repaired project checks pass. The before-project source hashes identify the supplied baseline. This is causal issue-to-retest evidence, not a claim that a CPU picture alone proves a repair.

## Capture Model
The prescribed exporter samples real headless Godot state and runtime texture pixels, then composes dark/light images with Pillow. These are CPU reconstructions, not GPU framebuffer screenshots. The ordinary MIX/source-texture project uses supported features; arbitrary custom shaders, clipping or occluding/draw-order interventions are outside this preview model. The paired images support their declared state/artwork scope. The independent public-API checks support event/object/timing relations separately. A repeat export demonstrates artifact correspondence; reproducibility alone is not proof of correctness.

## Source Accounting
All73 original input PNGs remain byte-identical: hit11, appear49, fly13. There are69 played frame slots: hit11, appearance source04..48(45), fly13. The4 transparent appearance pre-roll images remain preserved on disk. Original sequence FPS is unknown; this delivery is configured to the required30FPS.

## Tested Runtime Source Identity
{
  "project.godot": "60be9d7d5066582966e87ca6d78c8c8255b95d4a8c2417b5433b1b0949f68d30",
  "stage.tscn": "1792bb2f2529b17a8aa3ddf01e1696bf494dff23ad85dca8d11b19a4e7d93974",
  "stage.gd": "71495363b0b28c5f9fd8094b2ead8d576c00552531b94e2959cfb9021f14ab47",
  "delivery.cfg": "0a1eaed866fba94cb9716412c014715329fe7e626cc6d88c3190d0723dd45792"
}
Original PNG identity manifest: project/tools/original_pngs.json; independently checked against every source PNG before the actual tests.
