# Pocket with island

![Blueprint](output/pocket_with_island.svg)

**Demonstrates:** A pocket that leaves an island of material standing.

## What gets cut

A 320 × 320 × 19mm panel with a 240 × 240mm pocket, 6mm deep, leaving a
Ø100mm circular island at full thickness and a 40mm outer rim. The pocket floor
remains 13mm thick.

Sheet 400 × 400 × 19mm mdf.

- `pocket-12.70mm.nc`: pocket, 12.7mm tool, 1 feature(s), to 6mm
- `profile-3.17mm.nc`: profile, 3.175mm tool, 1 feature(s), to 19.2mm

## Run

`python -m cli.mill --recipe docs/recipes/panels/pocket_with_island`

## Outputs

- `machining_summary.json`
- `metrics.json`
- `pocket-12.70mm.nc`
- `pocket_with_island.svg`
- `profile-3.17mm.nc`
