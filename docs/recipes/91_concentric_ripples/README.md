# Recipe 91: Concentric Ripples

**Status:** Draft
**Difficulty:** Intermediate
**Demonstrates:** The `ConcentricBorder` count form (`count`, `step`), engraved rings (`mode: engrave`), `join: round`, and rings that grow around a hole under a `Subtract` parent

## Overview

Three 200mm panels on a 700x260mm sheet, each cut out with a through
profile.

- `engraved_square`: a 200mm square with 8 rings engraved 0.5mm deep,
  `count: 8, step: 10mm`. Each ring is a single closed line, inset 10mm to
  80mm from the edge.
- `island_ripples`: a 200mm square whose `Subtract {inner_inset: 60mm}`
  leaves an 80mm square island. `count: 3, step: 8mm, groove: 4mm` pockets
  rings 2mm deep that shrink from the outer edge and grow around the island
  at the same time. `join: round` rounds the rings around the island's
  corners; the outer rings stay sharp, because an inward offset of a convex
  corner is always sharp. The Subtract ring is 60mm wide, so insets of 30mm
  or more would not fit; the last groove ends at 28mm.
- `engraved_disc`: a 200mm disc with 9 rings engraved 0.5mm deep,
  `count: 9, step: 10mm`. The rings follow the circle.

## Output

Running the example writes these files to `output/`:
- `pocket-*.nc`, `engrave-*.nc`, `profile-*.nc`
- `91_concentric_ripples.svg`
- `metrics.json`

```bash
python -m cli.mill --recipe docs/recipes/91_concentric_ripples
```
