# Box bottoms and lids

![Blueprint](output/box_bottoms_and_lids.svg)

**Demonstrates:** Box top and bottom joinery: captured, dado, finger and plug.

## What gets cut

Four small boxes that differ only in how the bottom and lid attach: captured, dado, finger, plug.

All finger-jointed side profiles span the specified 100mm box depth. See the
[coupon cutter-footprint proof](../../shop/joinery_test_coupons/finger-side-proof.svg).
The captured/dado caps now measure 144 × 94mm, entering the 3mm wall grooves.
Finger caps span the full 150 × 100mm; their notches match the wall interfaces
and the two cap-relief overlap reports are resolved.

![Box-cap fit and cutter footprints before and after, reconstructed from G-code](cap-fit-proof.svg)

The caps that receive the wall ends also span 150 × 100mm. Their 6mm stock and
3mm grooves leave 3mm exposed beyond each wall end, so the walls measure 74mm
to preserve the specified 80mm overall height. The proof checks actual cap/wall
spans and groove cuts within 0.004mm NC rounding. Box dimensions, tooling,
groove depths, clearance and layout gap are unchanged.

Sheet 1200 × 800 × 6mm mdf.

- `pocket-3.17mm.nc`: pocket, 3.175mm tool, 24 feature(s), to 3mm
- `dogbone-3.17mm.nc`: dogbone, 3.175mm tool, 496 feature(s), to 6mm
- `profile-3.17mm.nc`: profile, 3.175mm tool, 24 feature(s), to 6.2mm

## Run

`python -m cli.mill --recipe docs/recipes/assemblies/box_bottoms_and_lids`

## Outputs

- `box_bottoms_and_lids.svg`
- `dogbone-3.17mm.nc`
- `machining_summary.json`
- `metrics.json`
- `pocket-3.17mm.nc`
- `profile-3.17mm.nc`
