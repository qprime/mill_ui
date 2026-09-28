# Recipe 96: Harmonograph

**Status:** Draft
**Difficulty:** Intermediate
**Demonstrates:** The `Curve` node with `type: harmonograph`, multiple damped pendulums per axis, and `size` scaling

## Overview

One 200mm panel on a 240x240mm sheet, engraved at 0.3mm depth and cut out
with a through profile. The figure sums two damped pendulums on each axis
over 60 cycles:

- x: 60mm at frequency 2 with phase 90, and 25mm at frequency 3.01.
- y: 60mm at frequency 3 with phase 45, and 25mm at frequency 2.

The 3.01 frequency detunes the x axis slightly, so successive sweeps drift
instead of retracing. Damping between 0.01 and 0.02 shrinks the sweeps
toward the center. `size: 160mm` scales the figure so the larger side of
its bounding box is 160mm. The figure is centered on the panel's origin,
not on its bounding box.

A longer trace fills the sampler's 20,000-point budget: this figure fits at
`cycles: 150` and fails by `cycles: 200` with an error naming `cycles` and
`tolerance`.

## Output

Running the example writes these files to `output/`:
- `engrave-*.nc`, `profile-*.nc`
- `96_harmonograph.svg`
- `metrics.json`

```bash
python -m cli.mill --recipe docs/recipes/96_harmonograph
```
