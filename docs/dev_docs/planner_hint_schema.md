# Planner Hint Schema

Planner hints MUST follow this top-level schema:

```json
{
    "units": "mm",
    "kerf_width_mm": float,
    "min_channel_width_mm": float,
    "profiles": [<profile hint dict>],
    "pockets": [<pocket hint dict>],
    "holes": [<hole hint dict>],
    "engraves": [<engrave hint dict>]
}
```

**Profile hint required keys:** id, shape, geometry, center_xy_mm, depth_mm, side
**Profile hint optional keys:** tabs

**Pocket hint required keys:** id, shape, geometry, center_xy_mm, depth_mm
**Pocket hint optional keys:** start_depth_mm (only if z_top != 0)

**Planner consumption:**
- Profiles: reads geometry, center_xy_mm, depth_mm, side, tabs
- Pockets: reads shape, geometry, depth_mm, start_depth_mm
- Holes: reads geometry.diameter_mm, center_xy_mm, depth_mm
