# Frames and trays

![Blueprint](output/frames_and_trays.svg)

**Demonstrates:** Non-rectangular outlines, inside profiles, Subtract and Shell.

## What gets cut

A picture frame with a chamfered opening, a rounded serving tray, an oval tray, a pentagon frame, and a triangular trivet.

The pentagon's inside and outside profiles retain a 40mm frame. See the
[profile cutter-footprint proof](../../shop/calibration_coupon/nested-profile-proof.svg).
Its false overlap report is resolved. The picture-frame chamfer now cuts a
5 × 5mm bevel on the opening rim and leaves 55mm of flat frame outside it.

![Chamfer cross-section before and after, reconstructed from G-code](chamfer-proof.svg)

The old offset path cut a V-groove behind the rim. The corrected V-bit tip
follows the nominal edge; its depth and the panel's outside dimensions are
unchanged. The profile/chamfer overlap reports are resolved.

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
