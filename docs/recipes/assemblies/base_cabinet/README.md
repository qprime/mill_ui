# Base cabinet

![Blueprint](output/base_cabinet_sheet_1.svg)

**Demonstrates:** A carcass assembly split across sheets by multi-sheet partitioning.

## What gets cut

A 600 × 560 × 720mm frameless cabinet with captured top, bottom and back, one
fixed shelf, and an open toe recess, cut from two 1220 × 1220 × 18mm MDF sheets.

| Member | Quantity | Blank dimensions |
|--------|----------|------------------|
| Sides | 2 | 560 × 720mm, with mirrored 75 × 100mm front toe cutouts |
| Top | 1 | 582 × 560mm |
| Bottom | 1 | 582 × 485mm |
| Back | 1 | 582 × 602mm |
| Fixed shelf | 1 | 582 × 530mm |

Caps, shelf and back engage their specified 9mm grooves. The bottom's lower face
is 100mm above the cabinet bottom; its inside face is at 118mm. The shelf starts
at 401mm and the top's inside face is at 702mm, leaving two 283mm clear openings.
Bottom side grooves start at the rear of the toe recess, preserving the front
overhang. The cutout's internal corner retains the normal cutter radius.

The back occupies depth 530–548mm: `back_inset: 12mm` is clear space behind its
rear face. Its height fits the raised bottom and top, and its width fits the side
grooves. The shelf stops at the back's front face; back shelf support is disabled.
There is no toe-cover panel. Every panel uses the specified 18mm stock.

Machine the inside faces upward. The right-side blank is mirrored; the top's
depth direction is also reversed, placing its rear groove at the correct edge.
Corrected parts pack onto two sheets; the earlier oversized back required three.

Sheet 1: 1220 × 1220 × 18mm mdf.

- `sheet_1.pocket-12.70mm.nc`: pocket, 12.7mm tool, 8 feature(s), to 9mm
- `sheet_1.dogbone-12.70mm.nc`: dogbone, 12.7mm tool, 32 feature(s), to 9mm
- `sheet_1.profile-3.17mm.nc`: profile, 3.175mm tool, 2 feature(s), to 18.2mm

Sheet 2: 1220 × 1220 × 18mm mdf.

- `sheet_2.pocket-12.70mm.nc`: pocket, 12.7mm tool, 2 feature(s), to 9mm
- `sheet_2.dogbone-12.70mm.nc`: dogbone, 12.7mm tool, 8 feature(s), to 9mm
- `sheet_2.profile-3.17mm.nc`: profile, 3.175mm tool, 4 feature(s), to 18.2mm

## Run

`python -m cli.mill --recipe docs/recipes/assemblies/base_cabinet`

## Outputs

- `base_cabinet_sheet_1.svg`
- `base_cabinet_sheet_2.svg`
- `machining_summary.json`
- `manifest.json`
- `metrics.json`
- `sheet_1.dogbone-12.70mm.nc`
- `sheet_1.pocket-12.70mm.nc`
- `sheet_1.profile-3.17mm.nc`
- `sheet_2.dogbone-12.70mm.nc`
- `sheet_2.pocket-12.70mm.nc`
- `sheet_2.profile-3.17mm.nc`
