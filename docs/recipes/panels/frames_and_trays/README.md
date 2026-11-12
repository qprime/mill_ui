# Frames and trays

![Blueprint](output/frames_and_trays.svg)

**Demonstrates:** Non-rectangular outlines, inside profiles, Subtract and Shell.

## What gets cut

A picture frame with a chamfered opening, a rounded serving tray, an oval tray, a pentagon frame, and a triangular trivet.

The pentagon's inside and outside profiles retain a 40mm frame. See the
[profile cutter-footprint proof](../../shop/calibration_coupon/nested-profile-proof.svg).
Its false overlap report is resolved; the picture-frame chamfer still has two
separate reports under #238.

Sheet 1000 × 700 × 19mm mdf.

- `pocket-12.70mm.nc`: pocket, 12.7mm tool, 2 feature(s), to 12mm
- `edge-12.70mm.nc`: edge, 12.7mm tool, 1 feature(s), to 5mm
- `profile-3.17mm.nc`: profile, 3.175mm tool, 7 feature(s), to 19.2mm

## Run

`python -m cli.mill --recipe docs/recipes/panels/frames_and_trays`

## Outputs

- `edge-12.70mm.nc`
- `frames_and_trays.svg`
- `machining_summary.json`
- `metrics.json`
- `pocket-12.70mm.nc`
- `profile-3.17mm.nc`
