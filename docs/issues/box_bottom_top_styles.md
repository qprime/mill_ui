# Box Bottom/Top Style Enhancement

**Status:** Closed
**Created:** 2026-01-27
**Closed:** 2026-01-27
**Commit:** a11452c
**Priority:** High (completes box generator feature)

## Summary

Enhance the box generator to support multiple bottom and top panel connection styles: captured, finger-jointed, and dado.

## Implementation Summary

All proposed features have been implemented:

**Phase 2a - Bottom/Top Styles:**
- `generators/assemblies/box.py` - Added `DadoSpec`, extended `BoxParams` and `PanelSpec`, updated `compute_box_panels()`
- `generators/assemblies/__init__.py` - Export `DadoSpec`
- `layout_ast/compositional.py` - Added new fields to `Box` AST node
- `pml/yaml_parser.py` - Added keywords and `parse_box()` updates
- `resolution/layout_resolver.py` - Updated `_handle_box()` for dado pocket generation
- `pml/syntax_spec.md` - Documented all new options
- `tests/test_box_assembly.py` - Added 15 new tests

**Phase 2b - SVG Visualization:**
- `labels` keyword - Adds part name labels centered on each panel (FRONT, BACK, LEFT SIDE, etc.)
- `edge_colors` keyword - Adds colored overlay lines showing mating edges:
  - Top: blue (#5ab9ea)
  - Bottom: orange (#ff9500)
  - Left: green (#4cd964)
  - Right: yellow (#ffcc00)
- `generators/panels/jointed_panel.py` - Added `label` parameter
- `generators/loop/profile.py` - Added `label` parameter to Item creation
- `export/blueprint_svg.py` - Added `EDGE_COLORS` group and `_render_edge_colors()` function
- Updated golden test files for new SVG layer

**New Recipe:**
- `docs/recipes/39_box_bottom_styles/` - Demonstrates dado bottom with labels and edge colors

**Test Coverage:**
- 37 total box-related tests passing
- All 1041 project tests passing

## Current Behavior

The box generator produces a "captured" bottom - a simple rectangle that sits inside the walls with no mechanical connection. The walls don't have finger joints on their bottom edges.

## Proposed Behavior

### Bottom Style Options

```pml
bottom_style captured              # Current behavior (default)
bottom_style finger                # Full finger joints on bottom edges
bottom_style dado [inset <mm>]     # Dado groove in walls for bottom panel
```

**`captured`**: Bottom panel sits inside walls. Simple rectangle sized `(width - 2t) x (depth - 2t)`. No mechanical lock - relies on glue.

**`finger`**:
- All four wall panels get finger joints on their bottom edges
- Bottom panel has matching finger joints on all four edges
- Phase coordination: front/back bottom edges = phase 0, side bottom edges = phase 1
- Bottom panel sized to interlock with wall fingers

**`dado`**:
- All four wall panels get a groove (pocket) cut on inside face
- Groove position controlled by optional `inset` parameter (distance from wall bottom to dado bottom, default 0 = flush)
- Groove depth = half material thickness
- Groove width = material thickness
- Bottom panel sized to fit into grooves: `(width - 2t + 2*dado_depth) x (depth - 2t + 2*dado_depth)`

### Top Style Options

```pml
top_style captured              # Default when lid specified
top_style finger                # Sealed box with finger-jointed top
top_style dado [drop <mm>]      # Dado groove for top panel
```

Same logic as bottom, mirrored:
- `drop` parameter controls distance from wall top to dado top (default 0 = flush with top)

### Wall Panel Changes

For `finger` style:
- Wall panels get taller: `height - thickness` instead of `height - 2*thickness` (bottom fingers extend down)
- If both top and bottom are `finger`, walls are full `height`

For `dado` style:
- Wall panels include pocket operations for the grooves
- Each wall gets one pocket per dado (bottom and/or top)
- Pocket geometry: full width of wall, height = material thickness, depth = half thickness

### PML Syntax Examples

```pml
# Finger-jointed bottom (structural)
box outer 200mm 150mm 100mm thickness 6mm joinery finger
    finger_width 12mm
    bottom_style finger

# Dado bottom raised 6mm from base (keeps contents off surface)
box outer 200mm 150mm 100mm thickness 6mm joinery finger
    finger_width 12mm
    bottom_style dado inset 6mm

# Sealed box with finger-jointed top and dado bottom
box outer 200mm 150mm 100mm thickness 6mm joinery finger
    finger_width 12mm
    bottom_style dado
    lid
    top_style finger

# Drop-in lid recessed 3mm from top
box outer 200mm 150mm 100mm thickness 6mm joinery finger
    finger_width 12mm
    lid
    top_style dado drop 3mm
```

## Implementation Changes

### 1. BoxParams (generators/assemblies/box.py)

Add fields:
```python
bottom_style: Literal["captured", "finger", "dado"] = "captured"
top_style: Literal["captured", "finger", "dado"] = "captured"
dado_inset_mm: float = 0.0      # For bottom dado
dado_drop_mm: float = 0.0       # For top dado
```

### 2. PanelSpec (generators/assemblies/box.py)

Add field for dado operations:
```python
@dataclass(frozen=True)
class DadoSpec:
    position_from_edge_mm: float  # Distance from edge to dado start
    width_mm: float               # Dado width (= material thickness)
    depth_mm: float               # Dado depth (= half thickness)
    edge: Literal["top", "bottom"]

@dataclass(frozen=True)
class PanelSpec:
    name: str
    width_mm: float
    height_mm: float
    edge_joints: dict[EdgeName, JointProfile | None]
    mating_edges: dict[EdgeName, str]
    dados: list[DadoSpec] = field(default_factory=list)  # NEW
```

### 3. compute_box_panels() Logic

Update panel dimension calculations:
- `finger` bottom: walls get `height - thickness` (or full height if top also finger)
- `dado` bottom: walls unchanged, but include DadoSpec
- Bottom panel sizing depends on style

### 4. Box AST Node (layout_ast/compositional.py)

Add fields matching BoxParams.

### 5. Parser (pml/yaml_parser.py)

Add keywords: `bottom_style`, `top_style`, `captured`, `dado`, `inset`, `drop`

### 6. Layout Resolver (resolution/layout_resolver.py)

Update `_handle_box()` to:
- Pass new params to BoxParams
- Generate pocket items for dado grooves on wall panels

## Testing

1. `bottom_style captured` - verify backward compatibility
2. `bottom_style finger` - verify bottom panel has fingers, walls have bottom edge fingers
3. `bottom_style dado` - verify walls have pocket operations, bottom sized for grooves
4. `bottom_style dado inset 10mm` - verify dado position
5. `top_style finger` with `lid` - verify sealed box geometry
6. `top_style dado drop 5mm` - verify recessed lid groove
7. Combined: `bottom_style dado` + `top_style finger`

## Future Considerations

- `dado_walls [front, back, left, right]` - selective dado (for cabinets with open sides)
- `dado_depth <mm>` - override default half-thickness
- Integration with shelf dados (same groove mechanism)

## Verification

Run tests:
```bash
python -m pytest tests/test_box_assembly.py tests/test_box_integration.py -v
```

Generate recipe output:
```bash
python -m cli.mill --input docs/recipes/39_box_bottom_styles/example.pml --out docs/recipes/39_box_bottom_styles/output
```
