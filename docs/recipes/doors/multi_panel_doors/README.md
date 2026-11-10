# Multi-panel doors

![Blueprint](output/multi_panel_doors.svg)

**Demonstrates:** A reusable door component with the split layouts: Split, SplitGrid, SplitHorizontal and SplitVertical.

## What gets cut

Four cabinet doors built from one reusable door outline: a 400 × 1000mm six-panel door, a 360 × 800mm two-panel door, and two 160 × 800mm narrow doors.

Sheet 1220 × 1220 × 19mm MDF, with a 10mm margin. Twelve panel recesses cut to 6mm with a 12.7mm tool. Four outside profiles cut through with a 3.175mm tool, leaving four 3mm-high tabs on each door.

## Run

`python -m cli.mill --recipe docs/recipes/doors/multi_panel_doors`

## Outputs

- `multi_panel_doors.svg`
- `pocket-12.70mm.nc`
- `profile-3.17mm.nc`
- `machining_summary.json`
- `metrics.json`
