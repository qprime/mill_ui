# Edge treatments

![Blueprint](output/edge_treatments.svg)

**Demonstrates:** Chamfer, roundover, and rough and finish allowances with a cross-section callout.

## What gets cut

Three small panels request different outside edges: a chamfer, a roundover, and a profile with rough and finish allowances shown as a cross-section callout.

The current tool library has no 6mm-radius roundover bit. This recipe reports a
design error and withholds all front-setup G-code; the blueprint remains available
for inspection. Add a tool only when that bit is available in the shop. Existing
profile/edge overlap errors also remain under investigation in the recipe audit.

Sheet 900 × 400 × 19mm mdf.

## Run

`python -m cli.mill --recipe docs/recipes/panels/edge_treatments`

## Outputs

- `edge_treatments.svg`
- `machining_summary.json`
- `metrics.json`
