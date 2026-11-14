# Pattern coasters

![Blueprint](output/pattern_coasters.svg)

**Demonstrates:** Phyllotaxis, Voronoi, string art and concentric ripples.

## What gets cut

Four coasters: phyllotaxis holes, Voronoi cells, string art, concentric ripples.

Sheet 700 × 260 × 12mm mdf.

- `pocket-9.53mm.nc`: pocket, 9.525mm tool, 14 operation(s), to 2mm
- `pocket-3.17mm.nc`: pocket, 3.175mm tool, 6 operation(s), to 2mm
- `bore-3.17mm.nc`: bore, 3.175mm tool, 40 operation(s), to 4mm
- `engrave-1.00mm.nc`: engrave, 1mm tool, 70 operation(s), to 0.3mm
- `profile-9.53mm.nc`: profile, 9.525mm tool, 4 operation(s), to 12.2mm

## Run

`python -m cli.mill --recipe docs/recipes/patterns/pattern_coasters`

## Outputs

- `bore-3.17mm.nc`
- `engrave-1.00mm.nc`
- `machining_summary.json`
- `metrics.json`
- `pattern_coasters.svg`
- `pocket-3.17mm.nc`
- `pocket-9.53mm.nc`
- `profile-9.53mm.nc`
