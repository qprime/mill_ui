# Edge treatments

![Blueprint](output/edge_treatments.svg)

**Demonstrates:** Chamfer, roundover, and rough and finish allowances with a cross-section callout.

## What gets cut

Three small panels request different outside edges: a chamfer, a roundover, and a profile with rough and finish allowances shown as a cross-section callout.

The current tool library has no 6mm-radius roundover bit. This recipe reports a
design error and withholds all front-setup G-code; the blueprint remains available
for inspection. Add a tool only when that bit is available in the shop. The
profile/edge overlap reports are resolved; the missing tool remains an error.
The blueprint shows the planned chamfer centerline/depth and marks the roundover
boundary as `unplanned`.

The chamfer tip follows the nominal edge to produce the requested 6 × 6mm bevel
with the available 90° V-bit. See the
[before/after chamfer cross-section proof](../frames_and_trays/chamfer-proof.svg).

Sheet 900 × 400 × 19mm mdf.

## Run

`python -m cli.mill --recipe docs/recipes/panels/edge_treatments`

## Outputs

- `edge_treatments.svg`
- `machining_summary.json`
- `metrics.json`
