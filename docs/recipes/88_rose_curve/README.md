# Recipe 88: Rose Curve

**Status:** Draft
**Difficulty:** Intermediate
**Demonstrates:** The `Curve` node with `type: rose`, adaptive curve sampling, and clipping to a non-rectangular parent

## Overview

Three panels on a 700x260mm sheet, each engraved with a rose curve
(`r = cos(k·θ)`) at 0.3mm depth:

- `five_petals`: `lobes: 5` at the default size (90% of the panel).
- `eight_petals_rotated`: `lobes: 4`, which draws eight petals, rotated 22.5 degrees.
- `clipped_disc`: `lobes: 3` on a 200mm disc with `size: 240mm`, so the
  petal tips are clipped at the circle and pieces under 5mm are dropped.

The first two panels and the disc are cut out with through profiles.

## Output

Running the example writes these files to `output/`:
- `engrave-*.nc`, `profile-*.nc`
- `88_rose_curve.svg`
- `metrics.json`

```bash
python -m cli.mill --recipe docs/recipes/88_rose_curve
```
