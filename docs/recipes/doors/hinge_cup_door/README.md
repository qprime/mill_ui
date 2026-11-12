# Hinge-cup door

![Blueprint](output/hinge_cup_door.svg)

**Demonstrates:** Two-sided machining: features cut on the back of the sheet after a flip.

## What gets cut

A Shaker door with two 35mm Euro hinge cups machined from the back. Two setups, with the sheet flipped between them.

Sheet 500 × 700 × 19mm mdf.

The 400 × 600mm door starts 13.2mm from the physical sheet's left/bottom edges
in the front authoring frame. This preserves the 10mm **sheet margin** (no-cut
zone) plus 3.2mm of outside-profile cutter clearance. The sheet size is retained.

The cups are 13mm deep, centered 22.5mm from the left door edge and 100mm from
each end. Their nearest edges leave 5mm of material at the door's left edge;
6mm of front-face material remains above each cup. The front has the same
50mm frame and 6mm-deep center recess as the Shaker example.

## Intent review

See the [front/back placement and cross-section](../shaker_door/placement-intent-review.svg).
Red cups on the front view are see-through references to back-face machining.
Machine the back cups first, then flip the whole sheet about X and machine the
front recess and tabbed outline. Back features mirror about the sheet center;
the door therefore appears toward the upper-left in the back setup. Keep the
sheet registration and use each setup's stated stock-surface Z zero.

The owner accepted the illustrated recipe design on 2026-11-12 after reviewing
the placement, door section and hinge-cup layout.
[Measurements and source/NC hashes](placement-measurements.json) verify the
translated front programs and mirrored back coordinates, unchanged part-relative
cup positions, depths, XY cup extents and full cutter-radius margin clearance.
All non-XY program words and final origin parking moves are unchanged. This is
computational evidence, not a physical cut or hardware-fit trial.

## Machining programs

- `back-bore-25.40mm.nc`: bore, 25.4mm tool, 2 feature(s), to 13mm
- `pocket-12.70mm.nc`: pocket, 12.7mm tool, 1 feature(s), to 6mm
- `profile-3.17mm.nc`: profile, 3.175mm tool, 1 feature(s), to 19.2mm

## Run

`python -m cli.mill --recipe docs/recipes/doors/hinge_cup_door`

## Outputs

- `back-bore-25.40mm.nc`
- `hinge_cup_door.back.svg`
- `hinge_cup_door.svg`
- `machining_summary.json`
- `metrics.json`
- `pocket-12.70mm.nc`
- `profile-3.17mm.nc`
