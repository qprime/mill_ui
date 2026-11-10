# Long spliced rail

![Blueprint](output/long_spliced_rail.svg)

**Demonstrates:** Beam splicing: layers longer than the sheet, spliced with staggered joints.

## What gets cut

A 2000mm laminated rail, longer than the sheet, spliced with staggered joints and tenoned at both ends.

Sheet 1220 × 1220 × 19mm mdf.

Eight segments across three layers, with a 38mm center-layer tenon at each end. The outer layers each total 2000mm; the center layer totals 2076mm. Each segment fits the sheet's working area with profile clearance.

- `profile-3.17mm.nc`: eight segment profiles, 3.175mm tool, to 19.2mm

## Run

`python -m cli.mill --recipe docs/recipes/beams/long_spliced_rail`

## Outputs

- `long_spliced_rail.svg`
- `machining_summary.json`
- `metrics.json`
- `profile-3.17mm.nc`
