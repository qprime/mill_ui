# Raised-panel doors

![Blueprint](output/raised_panel_doors.svg)

**Demonstrates:** Three tool-matched raised-panel profiles in rectangular and arched doors.

## What gets cut

The doors are each 450 × 700mm, with a 60mm frame. The rectangular door has a
50mm gap between panel cells. All recess bottoms are 6mm below the original
face. A 2mm field is still 4mm above that bottom: “raised” refers to this relative
height, not material added above the board.

| Cell in blueprint | Profile | Center below face | Border to field |
|-------------------|---------|-------------------|-----------------|
| Bottom left | Flat gutter + 90° V-bit slope | 2mm | 25mm |
| Bottom right | Flat gutter + 60° V-bit slope | 2mm | 25mm |
| Top left | Plain 90° V-groove | 0mm, untouched | 12mm |
| Top right | 60° V-groove + pocketed center | 2mm | 5.774mm |
| Arched door | Flat gutter + 90° V-bit slope | 2mm | 25mm |

For the 90° gutter, 21mm of flat floor leads into a 4mm-wide 45° slope. The
60° gutter has a narrower 2.309mm slope and a 22.691mm floor. Offset-contour
pocket clearing cuts the gutter and field; layered V-bit contours form the
slope. There is no surface raster or ball-nose machining.

This resolves #241 under the owner's clarified profile choice. The previous
implementation ignored the 6mm border depth and ran a groove outside the cell
to 6.699mm. The original proposed continuous shallow 25mm slope was replaced
explicitly by these tool-matched profiles; that arbitrary slope is not supported.

Sheet 1100 × 800 × 19mm mdf.

- `pocket_offset-12.70mm.nc`: seven flat clearing regions, 12.7mm endmill, to 6mm (gutters) or 2mm (fields)
- `edge-12.70mm-90deg.nc`: three contours, 12.7mm 90° V-bit, to 6mm
- `edge-12.70mm-60deg.nc`: two contours, 12.7mm 60° V-bit, to 6mm
- `profile-3.17mm.nc`: profile, 3.175mm tool, 2 feature(s), to 19.2mm

Door outlines and their four 3mm-high tabs are unchanged. Estimated runtime is
144.6 minutes, including the newly required gutter clearing.

## Machining limits

The 12.7mm flat cutter leaves rounded internal corners and small areas of
retained stock there, including spots that retain the full original height.
Blueprint pocket fills describe the intended regions, not square-corner
clearance. No dogbones are added to decorative corners.
Arbitrary shallow slopes and shaped molding profiles need separate capabilities.
An unavailable angle or undersized bit is an error; tooling inventory is unchanged.

## Run

`python -m cli.mill --recipe docs/recipes/doors/raised_panel_doors`

## Outputs

- `edge-12.70mm-60deg.nc`
- `edge-12.70mm-90deg.nc`
- `machining_summary.json`
- `metrics.json`
- `pocket_offset-12.70mm.nc`
- `profile-3.17mm.nc`
- `raised_panel_doors.svg`
