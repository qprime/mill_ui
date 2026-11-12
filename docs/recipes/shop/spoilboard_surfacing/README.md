# Spoilboard surfacing

![Blueprint](output/spoilboard_surfacing.svg)

**Demonstrates:** Full-sheet facing with cooling retracts.

## What gets cut

A full-bed facing program for the spoilboard, with cooling retracts.

This is the owner-approved exception to the recipes' 10mm clamp margin. It
deliberately uses `margin: 0mm` and a 5mm edge overrun to face the full bed.
Its blueprint states that no clamp margin is configured; the part-cutting
recipes instead show a shaded 10mm no-cut border.

Sheet 1220 × 1220 × 19mm mdf.

- `surface-25.40mm.nc`: surface, 25.4mm tool, 1 feature(s), to 0.5mm

## Run

`python -m cli.mill --recipe docs/recipes/shop/spoilboard_surfacing`

## Outputs

- `machining_summary.json`
- `metrics.json`
- `spoilboard_surfacing.svg`
- `surface-25.40mm.nc`
