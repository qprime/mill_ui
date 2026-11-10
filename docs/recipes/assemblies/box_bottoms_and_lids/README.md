# Box bottoms and lids

![Blueprint](output/box_bottoms_and_lids.svg)

**Demonstrates:** Box top and bottom joinery: captured, dado, finger and plug.

## What gets cut

Four small boxes that differ only in how the bottom and lid attach: captured, dado, finger, plug.

Sheet 1200 × 800 × 6mm mdf.

- `pocket-3.17mm.nc`: pocket, 3.175mm tool, 24 feature(s), to 3mm
- `dogbone-3.17mm.nc`: dogbone, 3.175mm tool, 480 feature(s), to 6mm
- `profile-3.17mm.nc`: profile, 3.175mm tool, 24 feature(s), to 6.2mm

## Run

`python -m cli.mill --recipe docs/recipes/assemblies/box_bottoms_and_lids`

## Outputs

- `box_bottoms_and_lids.svg`
- `dogbone-3.17mm.nc`
- `machining_summary.json`
- `metrics.json`
- `pocket-3.17mm.nc`
- `profile-3.17mm.nc`
