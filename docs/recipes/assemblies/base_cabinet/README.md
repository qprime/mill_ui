# Base cabinet

![Blueprint](output/base_cabinet_sheet_1.svg)

**Demonstrates:** A carcass assembly split across sheets by multi-sheet partitioning.

## What gets cut

A 600mm frameless base cabinet with captured top, bottom and back, one fixed shelf, and a toe kick, split across 1220 × 1220 sheets.

Captured caps and the shelf now include their side-groove engagement in their
blank widths; the shelf level accounts for the raised toe-kick bottom. These
shared carcass rules are illustrated in the [bookcase fit proof](../bookcase/carcass-shelf-fit-proof.svg).
The cabinet's back placement and complete toe-kick assembly still require a
separate fit audit; this recipe's passing gate does not establish that full fit.

3 sheets.

Sheet 1: 1220 × 1220 × 18mm mdf.

- `sheet_1.pocket-12.70mm.nc`: pocket, 12.7mm tool, 8 feature(s), to 9mm
- `sheet_1.dogbone-12.70mm.nc`: dogbone, 12.7mm tool, 32 feature(s), to 9mm
- `sheet_1.profile-3.17mm.nc`: profile, 3.175mm tool, 2 feature(s), to 18.2mm

Sheet 2: 1220 × 1220 × 18mm mdf.

- `sheet_2.pocket-12.70mm.nc`: pocket, 12.7mm tool, 1 feature(s), to 9mm
- `sheet_2.dogbone-12.70mm.nc`: dogbone, 12.7mm tool, 4 feature(s), to 9mm
- `sheet_2.profile-3.17mm.nc`: profile, 3.175mm tool, 3 feature(s), to 18.2mm

Sheet 3: 1220 × 1220 × 18mm mdf.

- `sheet_3.pocket-12.70mm.nc`: pocket, 12.7mm tool, 1 feature(s), to 9mm
- `sheet_3.dogbone-12.70mm.nc`: dogbone, 12.7mm tool, 4 feature(s), to 9mm
- `sheet_3.profile-3.17mm.nc`: profile, 3.175mm tool, 1 feature(s), to 18.2mm

## Run

`python -m cli.mill --recipe docs/recipes/assemblies/base_cabinet`

## Outputs

- `base_cabinet_sheet_1.svg`
- `base_cabinet_sheet_2.svg`
- `base_cabinet_sheet_3.svg`
- `machining_summary.json`
- `manifest.json`
- `metrics.json`
- `sheet_1.dogbone-12.70mm.nc`
- `sheet_1.pocket-12.70mm.nc`
- `sheet_1.profile-3.17mm.nc`
- `sheet_2.dogbone-12.70mm.nc`
- `sheet_2.pocket-12.70mm.nc`
- `sheet_2.profile-3.17mm.nc`
- `sheet_3.dogbone-12.70mm.nc`
- `sheet_3.pocket-12.70mm.nc`
- `sheet_3.profile-3.17mm.nc`
