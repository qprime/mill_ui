# Recipe 89: Spirograph

**Status:** Draft
**Difficulty:** Intermediate
**Demonstrates:** The `Curve` node with `type: spirograph`, closure after the reduced denominator of `fixed_radius / rolling_radius` turns, and `size` scaling

## Overview

Three 200mm panels on a 700x260mm sheet, each engraved at 0.3mm depth and
cut out with a through profile:

- `hypotrochoid`: `60 / 21 / 15` inside. The ratio reduces to `20/7`, so the
  figure closes after 7 revolutions with 20 outer lobes.
- `deltoid`: `60 / 20 / 20` inside. Pen offset equals the rolling radius, so
  the figure is a hypocycloid with three cusps.
- `epitrochoid`: `40 / 10 / 8` outside. The pen loops four times around the
  fixed circle.

Each figure is scaled to a 180mm outer diameter with `size`.

## Output

Running the example writes these files to `output/`:
- `engrave-*.nc`, `profile-*.nc`
- `89_spirograph.svg`
- `metrics.json`

```bash
python -m cli.mill --recipe docs/recipes/89_spirograph
```
