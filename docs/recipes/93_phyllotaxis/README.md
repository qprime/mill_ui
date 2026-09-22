# Recipe 93: Phyllotaxis

**Status:** Draft
**Difficulty:** Intermediate
**Demonstrates:** The `Phyllotaxis` node with `hole`, `pocket` and `svg` elements, radius scaling with `min_size`, and clipping to the parent

## Overview

Three 200mm panels on a 700x260mm sheet, each cut out with a through
profile. Every panel places motifs on a golden-angle spiral centered on the
panel; motifs that cross the panel edge are dropped.

- `sunflower`: a 200mm disc with 200 through holes, `spacing: 7mm`,
  `diameter: 5mm`. This is the node at its defaults.
- `scaled_pockets`: a 200mm disc with 150 circular pockets 3mm deep,
  `spacing: 8mm`, `diameter: 6mm`, `scale_with_radius: true`. Pockets grow
  from the center outward. Those scaled below `min_size: 4mm` are dropped,
  so every remaining pocket is larger than the 3.17mm flat tool that cuts it.
- `svg_motifs`: a 200mm square with 120 triangle motifs engraved 0.3mm deep,
  `spacing: 10mm`, `size: 6mm`, each turned to face outward.

## Output

Running the example writes these files to `output/`:
- `bore-*.nc`, `pocket-*.nc`, `engrave-*.nc`, `profile-*.nc`
- `93_phyllotaxis.svg`
- `metrics.json`

```bash
python -m cli.mill --recipe docs/recipes/93_phyllotaxis
```
