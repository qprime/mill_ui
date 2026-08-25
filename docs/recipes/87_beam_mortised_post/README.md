# Recipe 87: Beam Mortised Post

**Status:** Draft
**Difficulty:** Intermediate
**Demonstrates:** Beam face and edge features expanded into per-layer removals, `face` depth selection, `layers: outer` vs `layers: all`

## Overview

A 500mm three-layer laminated post, machined flat before glue-up. Every feature is
authored once in beam-local coordinates and lands on whichever layer panels it
actually reaches.

- `SquareMortise` at `depth: 19mm` — one layer thickness, so it cuts through layer 0 only.
- `DrillHole` with no `depth` — through every layer, three holes on the sheet.
- `DrillHole` with `depth: 19mm` and `face: back` — counts inward from the far end of the
  stack, so it lands on layer 2.
- `EdgeDado` at `layers: all` — three grooves, one per layer.
- `Rabbet` at the default `layers: outer` — two steps, on layers 0 and 2 only.

Beam-local `x` runs along the length from the left end and `y` across the width from
the bottom edge. Beam `face` names an end of the lamination stack, not a CNC setup —
all three panels lie flat on the sheet and are machined from one side.

## Output

Running the example writes these files to `output/`:
- `pocket-*.nc`, `bore-3.17mm.nc`, `profile-3.17mm.nc` — one program per tool
- `87_beam_mortised_post.svg` — blueprint
- `metrics.json`

## Run

```bash
python -m cli.mill --recipe docs/recipes/87_beam_mortised_post
python -m cli.validate_cam --recipe docs/recipes/87_beam_mortised_post --summary
```

## Assembly

Machine all three panels, then laminate in index order: layer 0 (mortise face) at the
front, layer 2 (the `face: back` hole) at the back. The through hole registers the
stack during glue-up.
