# Heightfield Relief Carving

## What a Heightfield Is

A Heightfield encodes per-pixel Z displacement as a grayscale raster — bas-relief ready to machine. Each pixel's brightness maps to a carving depth.

## PML Syntax

```yaml
- Rect:
    id: relief_panel
    at: { x: 150mm, y: 150mm, width: 200mm, height: 200mm }
    children:
      - Heightfield:
          image: input/relief_dome.png
          size: { width: 128mm, height: 128mm }
          depth: 5mm
          white_is_high: true
          tools:
            - tool: "1/4 upcut spiral"
              role: rough
              stepover: 60%
              stepdown: 2mm
            - tool: "1/8 upcut spiral"
              role: rough
              stepover: 50%
              stepdown: 1mm
            - tool: "1/8 ball nose 2F"
              role: finish
              stepover: 12%
              angle: 0
```

`Heightfield` is placed at the parent shape's center (per PM-12 CENTER_COORDS).

## Tools List

Tools are ordered coarse→fine by role:

| Field | Required | Applies to | Notes |
|-------|----------|-----------|-------|
| `tool` | yes | both | Name from machine tool_db |
| `role` | yes | both | `rough` or `finish` |
| `stepover` | yes | both | Percentage of tool diameter |
| `stepdown` | yes | rough | Z-slice depth per pass; not valid on finish |
| `angle` | yes | finish | Raster direction, degrees; normalized to `[0, 180)` |

**Role rules:**
- `rough` — flat, ball, or V-bit; Z-slice raster following morphological barrier stacking.
- `finish` — **ball-end only**; single pass using spherical-cap dilation of the surface to compute a per-pixel no-gouge tool-center Z.

## Finish-Pass Tuning

Finish uses grayscale dilation of the surface with a spherical-cap kernel to compute the lowest safe tool-center Z at every pixel. The pass then sweeps scanlines at `angle`, sampling the dilated envelope at the nearest pixel. Nearest-neighbor sampling is deliberate: the safe-Z envelope is a maximum, so interpolating between pixels would drop below the true max and risk gouge. The toolpath resolution is therefore the image pixel pitch — pick `size`/`depth`/image resolution accordingly.

Recommended starting points (MDF, 16-bit source):

| Tool diameter | Stepover | Notes |
|---------------|----------|-------|
| 3mm ball | 10–15% | 0.3–0.45mm between scanlines |
| 1.5mm ball | 8–12% | Fine detail, 0.12–0.18mm between scanlines |

**Multi-angle finishing for directionality reduction:**

```yaml
- tool: "1/8 ball nose 2F"
  role: finish
  stepover: 12%
  angle: 0
- tool: "1/8 ball nose 2F"
  role: finish
  stepover: 12%
  angle: 90
```

Duplicate tool names aren't allowed per feature today; use different tool names for two-angle passes (or run as separate heightfield features).

## Rest-Material Floor

The finish safe-surface is floored by:

1. The finest rough tool's barrier — finish never cuts above material rough already cleared.
2. The previous finish tool's safe-surface — a second (smaller) ball never revisits ground the first already covered.

Both are applied automatically when both roles are present. No PML flag.

## Image Requirements (strict; loader rejects anything else)

| Requirement | Reason |
|-------------|--------|
| PNG extension `.png` | Only format the loader accepts |
| PNG IHDR bit-depth == 16 | Required precision for finish carving |
| PNG IHDR color-type == 0 (single-channel grayscale) | No RGB, no alpha, no palette |
| Square pixels within ε=1e-4 | `width_mm / W_px` must equal `height_mm / H_px` |
| File exists on disk | Path resolved relative to PML file |

The loader reads the PNG IHDR chunk directly rather than relying on PIL's `mode`.

## `white_is_high` Semantics

- `true` (default): pure white (65535) stays at the top surface; pure black (0) carves to `depth`
- `false`: inverted — black stays highest, white carves deepest

## Known Limitations

- **8-bit-sourced heightmaps show terracing.** The loader requires 16-bit; if your upstream pipeline outputs 8-bit and you convert without smoothing, the finish pass faithfully reproduces the terraces. Fix upstream.
- **No adaptive stepover.** Fixed stepover throughout. Adaptive (denser on high-curvature regions) is a future optimization.
- **Rotation angle is per-tool.** Crosshatch within a single tool is not supported — specify two tools at different angles instead.
- **No cross-feature barrier cache.** Each heightfield feature recomputes its own surface and barriers.
- **Flat-endmill finishing is not supported.** Finish requires a ball-end tool; flats have much higher gouge risk and use a different kernel.

## Common Loader Errors

| Message | Fix |
|---------|-----|
| `Heightfield image must be 16-bit grayscale (got 8-bit)` | Run the image through an 8→16 bit converter before ingest |
| `Heightfield image must be single-channel grayscale, got color-type N` | Export as grayscale (PNG color-type 0), not RGB or indexed |
| `Heightfield pixel aspect inconsistent` | Match PML `size` aspect to the image pixel aspect |
| `Heightfield image not found` | Path is relative to the PML file; check `input/` subfolder convention |
| `finish role requires kind='ball' tool` | Use a ball-nose endmill for finish entries |

## Recipes

| Recipe | What it shows |
|--------|---------------|
| `82_heightfield_ir_only` | Minimal IR-only example (no toolpath) |
| `83_heightfield_rough_synthetic` | Rough-only, two tools, morphological barrier stacking |
| `85_heightfield_full_synthetic` | Full pipeline — two rough tools + ball-nose finish with rest-floor |
