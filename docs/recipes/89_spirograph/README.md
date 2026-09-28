# Recipe 89: Spirograph

**Status:** Draft
**Difficulty:** Intermediate
**Demonstrates:** The `Curve` node with `type: spirograph`: `points` / `step` / `pen` layers, pen lists and sweeps, `rotation_step`, per-layer `depth`, and one shared scale per stack

## Overview

Three 200mm panels on a 700x260mm sheet, each engraved at 0.3mm depth and
cut out with a through profile. No curve sets `size`, so each stack fills
90% of its panel (180mm outer diameter).

- `nested`: one layer, `points: 7, step: 3`, with four pen values from
  `1.0` down to `0.4`. Each pen value draws one strand: seven lobes visited
  every third lobe, from cusps at `1.0` to rounded lobes at `0.4`. All four
  strands share one scale, so they nest inside each other.
- `swirl`: one layer, `points: 5, step: 2`, with a pen sweep of nine values
  from `1.2` to `0.4`. `rotation_step: 4` turns each strand 4° past the one
  before it, which twists the stack into a swirl.
- `combined`: two layers in one stack. An outside layer, `points: 6, step: 1,
  pen: 0.6`, draws six rounded outer lobes and sets the stack's outer
  diameter. An inside layer, `points: 12, step: 5, pen: 1.0`, draws a cusped
  twelve-point star at the same scale and engraves at `0.5mm` through its
  own `depth`.

The panels engrave about 4.4m, 6.7m and 2.2m, below the default
`max_cut_length` of 50m per node.

## Output

Running the example writes these files to `output/`:
- `engrave-*.nc`, `profile-*.nc`
- `89_spirograph.svg`
- `metrics.json`

```bash
python -m cli.mill --recipe docs/recipes/89_spirograph
```
