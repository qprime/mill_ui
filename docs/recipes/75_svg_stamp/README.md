# Recipe 75: SVG Stamp

Demonstrates `SvgStamp` generator for milling vector artwork from inline SVG path data.

## Features Demonstrated

- **Engrave** (default): Star shape engraved at 0.3mm depth
- **Pocket**: Arrow shape pocketed at 4mm depth
- **Profile**: Freeform curve profile-cut through the stock

All three use inline SVG path data with `scale: fit` (default) to scale uniformly within their parent region.

## Run

```bash
python -m cli.mill --recipe docs/recipes/75_svg_stamp
```
