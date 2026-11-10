# Bookcase

![Blueprint](output/bookcase_sheet_1.svg)

**Demonstrates:** Carcass partitions and dadoed shelves.

## What gets cut

Blocked: carcass vertical partitions are not implemented. This recipe now fails explicitly. Its existing outputs omit both partitions and must not be used as a complete bookcase cut list.

A bookcase carcass with two vertical partitions and dadoed shelves.

3 sheets.

Sheet 1: 1220 × 1220 × 18mm mdf.

- `sheet_1.pocket-12.70mm.nc`: pocket, 12.7mm tool, 10 feature(s), to 9mm
- `sheet_1.dogbone-12.70mm.nc`: dogbone, 12.7mm tool, 40 feature(s), to 9mm
- `sheet_1.profile-3.17mm.nc`: profile, 3.175mm tool, 2 feature(s), to 18.2mm

Sheet 2: 1220 × 1220 × 18mm mdf.

- `sheet_2.profile-3.17mm.nc`: profile, 3.175mm tool, 3 feature(s), to 18.2mm

Sheet 3: 1220 × 1220 × 18mm mdf.

- `sheet_3.profile-3.17mm.nc`: profile, 3.175mm tool, 2 feature(s), to 18.2mm

## Run

`python -m cli.mill --recipe docs/recipes/assemblies/bookcase`

## Outputs

- `bookcase_sheet_1.svg`
- `bookcase_sheet_2.svg`
- `bookcase_sheet_3.svg`
- `machining_summary.json`
- `manifest.json`
- `metrics.json`
- `sheet_1.dogbone-12.70mm.nc`
- `sheet_1.pocket-12.70mm.nc`
- `sheet_1.profile-3.17mm.nc`
- `sheet_2.profile-3.17mm.nc`
- `sheet_3.profile-3.17mm.nc`
