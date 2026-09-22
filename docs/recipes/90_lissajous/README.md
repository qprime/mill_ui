# Recipe 90: Lissajous

**Status:** Draft
**Difficulty:** Intermediate
**Demonstrates:** The `Curve` node with `type: lissajous`, independent width and height, phase, and clipping to a disc

## Overview

Three 200mm panels on a 700x260mm sheet, each engraved at 0.3mm depth and
cut out with a through profile:

- `three_two`: `3:2` at the default phase of 90 degrees and the default
  box, 90% of the panel in each direction.
- `five_four`: `5:4` with `phase: 45` in an explicit 160x100mm box.
- `clipped_ellipse`: `1:1` at phase 90, which is an ellipse, drawn 240mm
  wide and 120mm tall inside a 200mm disc so the two ends are clipped away.

## Output

Running the example writes these files to `output/`:
- `engrave-*.nc`, `profile-*.nc`
- `90_lissajous.svg`
- `metrics.json`

```bash
python -m cli.mill --recipe docs/recipes/90_lissajous
```
