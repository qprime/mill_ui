# Production sheet

![Blueprint](output/production_sheet.svg)

**Demonstrates:** A whole-sheet job: tabs, onion skin, rough/finish allowances, waste cuts, safe Z, per-tool G-code, feed overrides and a kerf override.

## What gets cut

A full sheet of mixed parts held with tabs and onion skin, offcuts cut into usable blanks, a raised safe Z to clear clamps, and normal operations grouped per tool. Shelves combine allowances with tabs; the side panel combines allowances with onion skin. Roughing preserves a bottom web, then the final contours are finished before onion-skin release.

Sheet 1220 × 1220 × 19mm mdf.

- `9.53mm.nc`: pocket, 9.525mm tool, 1 operation(s), to 6mm
- `9.53mm-compression.nc`: profile, profile_finish, 9.525mm tool, 14 operation(s), to 19.2mm
- `12.70mm.nc`: bore, 12.7mm tool, 1 operation(s), to 12mm
- `6.35mm.nc`: bore, 6.35mm tool, 16 operation(s), to 12mm
- `release-9.53mm.nc`: release, 9.525mm tool, 3 operation(s), to 19.2mm

## Run

`python -m cli.mill --recipe docs/recipes/production/production_sheet`

Run the machining programs in the order listed above, with `release-9.53mm.nc`
last. The other parts retain their requested tabs. Release remains a separate
program even in per-tool mode.

## Outputs

- `12.70mm.nc`
- `6.35mm.nc`
- `9.53mm-compression.nc`
- `9.53mm.nc`
- `machining_summary.json`
- `metrics.json`
- `production_sheet.svg`
- `release-9.53mm.nc`
