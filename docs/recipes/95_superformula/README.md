# Recipe 95: Superformula

**Status:** Draft
**Difficulty:** Intermediate
**Demonstrates:** The `Curve` node with `type: superformula`, exponent-driven shapes, `size`, `rotation`, and the two-revolution trace for odd `m` with asymmetric terms

## Overview

Four 200mm panels on a 930x260mm sheet, each engraved at 0.3mm depth and
cut out with a through profile:

- `circle`: `m: 5` with `n1 = n2 = n3 = 2`, which draws a circle for any
  `m`, at `size: 150mm`.
- `star`: `m: 5` with all exponents 0.3, a five-point star with thin
  spikes, rotated 18 degrees so one spike points up. Default size, 90% of
  the panel.
- `rounded_square`: `m: 4` with all exponents 4, a superellipse between a
  circle and a square.
- `odd_asymmetric`: `m: 3, n1: 1, n2: 2, n3: 5, b: 1.5`. Odd `m` with
  `b ≠ a` repeats only after two revolutions, so the generator traces
  4π and the figure closes with three-fold symmetry.

## Output

Running the example writes these files to `output/`:
- `engrave-*.nc`, `profile-*.nc`
- `95_superformula.svg`
- `metrics.json`

```bash
python -m cli.mill --recipe docs/recipes/95_superformula
```
