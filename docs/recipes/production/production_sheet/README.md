# Production sheet

![Blueprint](output/production_sheet.svg)

**Demonstrates:** A whole-sheet job: tabs, onion skin, waste cuts, safe Z, per-tool G-code, feed overrides and a kerf override.

## What gets cut

A full sheet of mixed parts held with tabs and onion skin, offcuts cut into usable blanks, a raised safe Z to clear clamps, and one G-code file per tool.

Sheet 1220 × 1220 × 19mm mdf.

- `12.70mm.nc`: pocket, 12.7mm tool, 1 feature(s), to 6mm
- `25.40mm.nc`: bore, 25.4mm tool, 1 feature(s), to 12mm
- `3.17mm-downcut.nc`: bore, 3.175mm tool, 16 feature(s), to 12mm
- `3.17mm-upcut.nc`: profile, 3.175mm tool, 9 feature(s), to 19.4mm

## Run

`python -m cli.mill --recipe docs/recipes/production/production_sheet`

## Outputs

- `12.70mm.nc`
- `25.40mm.nc`
- `3.17mm-downcut.nc`
- `3.17mm-upcut.nc`
- `machining_summary.json`
- `metrics.json`
- `production_sheet.svg`
