# Heightfield Relief Carving (IR-Only Phase)

**Status:** IR-only. G-code generation pending in issues #2 (rough) and #3 (finish).

## What a Heightfield Is

A Heightfield encodes per-pixel Z displacement as a grayscale raster — bas-relief ready to machine. Unlike `pocket` or `engrave` (globally-defined Z), each pixel's brightness maps to a carving depth.

## PML Syntax

```yaml
- Rect:
    id: relief_panel
    at: { x: 150mm, y: 150mm, width: 200mm, height: 200mm }
    children:
      - Heightfield:
          image: input/relief_dome.png        # path relative to the PML file
          size: { width: 128mm, height: 128mm }  # XY extent (required)
          depth: 5mm                           # maximum carve depth (required)
          white_is_high: true                  # default; true = white pixels stay highest
```

`Heightfield` is placed at the parent shape's center (per PM-12 CENTER_COORDS). No `at:` on the child node — wrap in `Frame` or `AtPosition` for offset placement.

## Image Requirements (strict; loader rejects anything else)

| Requirement | Reason |
|-------------|--------|
| PNG extension `.png` | Only format the loader accepts |
| PNG IHDR bit-depth == 16 | Required precision for finish carving |
| PNG IHDR color-type == 0 (single-channel grayscale) | No RGB, no alpha, no palette |
| Square pixels within ε=1e-4 | `width_mm / W_px` must equal `height_mm / H_px` |
| File exists on disk | Path resolved relative to PML file |

The loader reads the PNG IHDR chunk directly rather than relying on PIL's `mode` — PIL reports 16-bit PNGs as `mode='I'` (32-bit int container), which is ambiguous.

## Image Pipeline

mill_ui does not preprocess images. The external pipeline (e.g. gpt-image-2) is responsible for:

1. Generating the relief as grayscale
2. Converting to 16-bit precision
3. Smoothing and mask flattening
4. Honoring gpt-image-2 envelope constraints (long edge ≤ 3840, edges multiple of 16, aspect ≤ 3:1)

## `white_is_high` Semantics

- `true` (default): pure white (65535) stays at the top surface; pure black (0) carves to `depth`
- `false`: inverted — black stays highest, white carves deepest

## Pipeline Behavior

| Stage | Behavior |
|-------|----------|
| PML parser | Builds `HeightfieldGen` AST node |
| Layout resolver | Resolves image path against `source_dir`; emits flat `Item(type="Heightfield", feature.type="heightfield", Geometry.data={image_path, white_is_high, w_mm, h_mm})` |
| IR adapter | Emits `RemovalIntent` with `depth_profile.mode="heightfield"` carrying `image_path` + `white_is_high` |
| Validation | Loads image (16-bit check, square-pixel check), verifies depth ≤ sheet thickness |
| Planner input adapter | Filters out heightfield intents with a structured warning — no G-code planner yet |
| Blueprint SVG | Base64 PNG embedded in `HEIGHTFIELD_OVERLAYS` layer with a dashed border |

## Known Limitations (Phase 1)

- No G-code output. Use a heightfield recipe for IR/validation/blueprint checks only.
- `pixel_pitch_mm` is not stored on the IR (PL-8 NO_PASSTHROUGH_GEOMETRY). The planner (#2/#3) will derive it at consumption time from image dimensions and intent bounds.
- Square-pixel tolerance ε = 1e-4 relative. Stricter than typical float epsilon; designed to catch user errors, not numeric noise.

## Common Loader Errors

| Message | Fix |
|---------|-----|
| `Heightfield image must be 16-bit grayscale (got 8-bit)` | Run the image through an 8→16 bit converter before ingest |
| `Heightfield image must be single-channel grayscale, got color-type N` | Export as grayscale (PNG color-type 0), not RGB or indexed |
| `Heightfield pixel aspect inconsistent` | Match PML `size` aspect to the image pixel aspect |
| `Heightfield image not found` | Path is relative to the PML file; check `input/` subfolder convention |

## Recipe Reference

See `docs/recipes/82_heightfield_ir_only/` for a minimal IR-only example with a committed 16-bit synthetic PNG.
