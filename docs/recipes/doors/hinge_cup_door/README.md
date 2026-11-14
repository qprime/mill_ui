# Hinge-cup door

![Blueprint](output/hinge_cup_door.svg)

**Demonstrates:** Two-sided machining: features cut on the back of the sheet after a flip.

## What gets cut

A Shaker door with two 35mm Euro hinge cups machined from the back. Two setups, with the sheet flipped between them.

Sheet 500 × 700 × 19mm mdf.

- `back-bore-12.70mm.nc`: bore, 12.7mm tool, 2 operation(s), to 13mm
- `pocket-9.53mm.nc`: pocket, 9.525mm tool, 1 operation(s), to 6mm
- `profile-9.53mm.nc`: profile, 9.525mm tool, 1 operation(s), to 19.2mm

## Run

`python -m cli.mill --recipe docs/recipes/doors/hinge_cup_door`

## Outputs

- `back-bore-12.70mm.nc`
- `hinge_cup_door.back.svg`
- `hinge_cup_door.svg`
- `machining_summary.json`
- `metrics.json`
- `pocket-9.53mm.nc`
- `profile-9.53mm.nc`
