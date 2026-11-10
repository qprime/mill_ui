# Joinery test coupons

![Blueprint](output/joinery_test_coupons.svg)

**Demonstrates:** Every joinery type as a small fit coupon.

## What gets cut

Offcut-sized coupons for each joinery type, cut before a big job to check fit and clearance on the machine.

Sheet 600 × 400 × 18mm mdf.

- `pocket-12.70mm.nc`: pocket, 12.7mm tool, 12 feature(s), to 9mm
- `dogbone-3.17mm.nc`: dogbone, 3.175mm tool, 28 feature(s), to 30mm
- `dogbone-12.70mm.nc`: dogbone, 12.7mm tool, 48 feature(s), to 9mm
- `profile-3.17mm.nc`: profile, 3.175mm tool, 32 feature(s), to 18.2mm

## Run

`python -m cli.mill --recipe docs/recipes/shop/joinery_test_coupons`

## Outputs

- `dogbone-12.70mm.nc`
- `dogbone-3.17mm.nc`
- `joinery_test_coupons.svg`
- `machining_summary.json`
- `metrics.json`
- `pocket-12.70mm.nc`
- `profile-3.17mm.nc`
