# Recipe 94: Voronoi

**Status:** Draft
**Difficulty:** Intermediate
**Demonstrates:** The `Voronoi` node with seeded random seeds, `min_spacing`, engraved cell edges, and pocketed cells that leave a raised web, with rest machining for sharp cell corners

## Overview

Two 200mm panels on a 480x260mm sheet, each cut out with a through
profile. Each panel is partitioned into Voronoi cells around seed points
sampled with `seed`, so the same file always produces the same cells.

- `cracked_disc`: a 200mm disc with 40 seeds, `seed: 7`, at least 12mm
  apart. The shared cell edges are engraved 0.5mm deep, each edge once.
  The disc outline is not engraved; the profile cuts it.
- `cell_panel`: a 200mm square with 25 seeds, `seed: 3`, at least 18mm
  apart. Each cell is pocketed 3mm deep, inset so a 4mm web
  (`line_width: 4mm`) stands between neighboring pockets. The 12.7mm tool
  clears each cell and leaves its corners round; `rest_tool: 3.175mm` then
  runs the 3.175mm tool around each cell to cut the corners to a 1.6mm
  radius.

Change `seed` to get a different arrangement with the same count and
spacing.

## Output

Running the example writes these files to `output/`:
- `pocket-*.nc`, `pocket_rest-*.nc`, `engrave-*.nc`, `profile-*.nc`

Run `pocket-*.nc`, change to the 3.175mm tool, then run `pocket_rest-*.nc`.
- `94_voronoi.svg`
- `metrics.json`

```bash
python -m cli.mill --recipe docs/recipes/94_voronoi
```
