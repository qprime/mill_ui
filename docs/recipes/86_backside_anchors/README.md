# Recipe 86: Backside Anchors

**Status:** Draft
**Difficulty:** Intermediate
**Demonstrates:** Two-sided machining via `face: back`, cross-face web validation, back blueprint view

## Overview

A cabinet door machined in two setups. The show face carries the shaker field
pocket and the outside through-profile. The opposite face carries the hardware
anchor points: two 35mm hinge cups bored 12.5mm deep, and four 3mm pilot holes
for the hinge mounting screws.

All coordinates — including the back features — are authored in the front-face
frame. Positions read as if looking through the panel. The compiler mirrors the
back items about the X axis before planning.

`min_web: 4mm` sets the minimum material left between an overlapping front and
back feature. With 19mm stock, a front pocket and a back pocket sharing XY may
total no more than 15mm of depth.

## Setup Order

1. Load the sheet **back face up**. Run the `back-*.nc` programs.
2. Flip the sheet about the X axis — the top edge swaps with the bottom edge,
   left/right registration is unchanged.
3. Run the front programs. The through-profile is in this setup, so the door
   stays captive in the sheet until the last cut.

## Output

Running the example writes these files to `output/`:
- `back-pocket-12.70mm.nc`, `back-drill-6.35mm.nc` — setup 1 (back face up)
- `pocket-12.70mm.nc`, `profile-3.17mm.nc` — setup 2 (front face up)
- `86_backside_anchors.svg` — front view
- `86_backside_anchors.back.svg` — back view in setup-1 machine space
- `metrics.json`

## Run

```bash
python -m cli.mill --recipe docs/recipes/86_backside_anchors
```
