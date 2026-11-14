# Side table frame

![Blueprint](output/side_table_frame.svg)

**Demonstrates:** Laminated beams with mortises, tenons, edge dados, rabbets and drill holes.

## What gets cut

Four laminated legs with mortises and four aprons with tenons for a small side table.

Sheet 1220 × 1220 × 19mm mdf.

- `pocket-9.53mm.nc`: pocket, 9.525mm tool, 8 operation(s), to 19mm
- `pocket-6.35mm.nc`: pocket, 6.35mm tool, 16 operation(s), to 19mm
- `bore-6.35mm.nc`: bore, 6.35mm tool, 8 operation(s), to 10mm
- `profile-9.53mm.nc`: profile, 9.525mm tool, 16 operation(s), to 19.2mm

## Run

`python -m cli.mill --recipe docs/recipes/beams/side_table_frame`

## Outputs

- `bore-6.35mm.nc`
- `machining_summary.json`
- `metrics.json`
- `pocket-6.35mm.nc`
- `pocket-9.53mm.nc`
- `profile-9.53mm.nc`
- `side_table_frame.svg`
