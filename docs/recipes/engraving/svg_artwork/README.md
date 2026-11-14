# SVG artwork

![Blueprint](output/svg_artwork.svg)

**Demonstrates:** Artwork from an SVG file, engraved, pocketed and cut through.

## What gets cut

Artwork from an SVG file in the recipe folder, cut three ways: engraved, pocketed, and cut through.

Sheet 600 × 400 × 19mm mdf.

- `pocket-9.53mm.nc`: pocket, 9.525mm tool, 3 operation(s), to 4mm
- `engrave-1.00mm.nc`: engrave, 1mm tool, 3 operation(s), to 0.5mm
- `profile-9.53mm.nc`: profile, 9.525mm tool, 3 operation(s), to 19.2mm

## Run

`python -m cli.mill --recipe docs/recipes/engraving/svg_artwork`

## Outputs

- `engrave-1.00mm.nc`
- `machining_summary.json`
- `metrics.json`
- `pocket-9.53mm.nc`
- `profile-9.53mm.nc`
- `svg_artwork.svg`
