# Decorative panel faces

![Blueprint](output/decorative_panel_faces.svg)

**Demonstrates:** Six face decorations side by side: X-panel, louvers, wave, lattice, fluting and concentric border.

## What gets cut

Wave uses 6.35mm centerline spacing; its engraving width comes from the selected tool.

Six 300 × 400mm panels, one per face style: X-panel, louvers, wave, diamond lattice, fluting, concentric border.

The diamond lattice intentionally crosses two families of 6.35mm-wide grooves,
both 3mm deep, at right angles. Rotating the pattern does not change whether
those crossings are valid.

Sheet 1100 × 900 × 19mm mdf.

- `pocket-9.53mm.nc`: pocket, 9.525mm tool, 12 operation(s), to 6mm
- `pocket-3.17mm.nc`: pocket, 3.175mm tool, 26 operation(s), to 3mm
- `engrave-1.00mm.nc`: engrave, 1mm tool, 101 operation(s), to 4mm
- `profile-9.53mm.nc`: profile, 9.525mm tool, 6 operation(s), to 19.2mm

## Run

`python -m cli.mill --recipe docs/recipes/panels/decorative_panel_faces`

## Outputs

- `decorative_panel_faces.svg`
- `engrave-1.00mm.nc`
- `machining_summary.json`
- `metrics.json`
- `pocket-3.17mm.nc`
- `pocket-9.53mm.nc`
- `profile-9.53mm.nc`
