# SVG Generation Invariants

**Applies to:** Blueprint SVG output (`diagram_render/render_svg.py`, `adapters/layoutast_to_ir.py`)

---

## Overview

The SVG generation system converts LayoutAST to visual blueprints via DiagramIR. The IR decouples layout semantics from SVG rendering.

Pipeline: `LayoutAST -> DiagramIR -> SVG`

---

## Invariants

| ID | Type | Invariant | Description |
|----|------|-----------|-------------|
| SVG-1 | HARD | SHAPE_REGISTRY_COMPLETE | All shape types in DiagramIR have registered renderers |
| SVG-2 | HARD | FEATURE_REGISTRY_COMPLETE | All feature types in LayoutAST map to DiagramIR layers |
| SVG-3 | HARD | THEME_STYLES_VALID | All StyleSpec values are valid (hex colors, positive widths) |
| SVG-4 | HARD | IR_BOUNDS_CONTAIN_SHAPES | All shapes in DiagramIR fall within declared bounds |
| SVG-5 | HARD | SINGLE_RENDER_PATH | Only one LayoutAST->SVG conversion path exists |
| SVG-6 | HARD | CONFIG_NOT_HARDCODED | All layout constants are named module-level constants, not inline literals |
| SVG-7 | HARD | VALID_XML_OUTPUT | Output is well-formed XML with proper escaping |
| SVG-8 | HARD | VIEWBOX_CONTAINS_CONTENT | All rendered elements fit within SVG viewBox |
| SVG-9 | HARD | DETERMINISTIC_OUTPUT | Same LayoutAST always produces identical SVG |
| SVG-10 | HARD | POCKET_REGION_FIDELITY | Pocket fills preserve all holes and islands, using the same region subtraction as machining. |
| SVG-11 | HARD | EDGE_PLAN_FIDELITY | Edge drawings use the planner's selected-tool contour and depth; unmachinable requests are marked unplanned. |
| SVG-12 | HARD | POCKET_LABEL_REGION | Pocket label anchors must lie in the recessed region, outside preserved holes/islands; an empty region has no label. |
| SVG-13 | HARD | CLAMP_MARGIN_IDENTIFIED | Layout blueprints identify the configured sheet margin; positive margins have translucent red border strips matching fixture keepouts and a no-cut note, while zero is explicitly identified as none. |

---

## Shape Types

Registered shape renderers in `diagram_render/render_svg.py`:

| Shape Type | SVG Element | Required Params |
|------------|-------------|-----------------|
| Rect | `<rect>` | x, y, width, height |
| Circle | `<circle>` | cx, cy, r |
| Line | `<line>` | x1, y1, x2, y2 |
| Polyline | `<polyline>` or `<path>` | points |
| Text | `<text>` | x, y, content |
| Path | `<path>` | d |

---

## Feature -> Layer Mapping

Pocket polygons with holes and Rect pockets with islands use an even-odd compound
`Path`. Island bounds are in working-area coordinates; polygon vertices and holes
are relative to their placement. `core.geometry.pocket_region()` owns the region
calculation for both the planner and drawing adapter, including unions of
overlapping islands, clipped edge-touching exclusions, and disconnected remnants.
Do not paint holes with a background-colored overlay: underlying cuts must remain
visible. Margin and Y-origin transforms apply once to every contour.

Pocket labels with holes/islands use this same region. Keep the existing center
when it is inside the recess; otherwise use a deterministic interior point.
This places the label anchor in the material-removal region rather than on a
preserved island. It does not guarantee that the entire text fits a narrow region.

Edge centerlines and depth labels come from `build_edge_cut_plan()`, the same pure
planner function used before G-code generation. The adapter converts through
RemovalIntent and honors supplied intents and the pipeline's selected tool set.
Standalone rendering uses the configured material/tool library. Never recompute
an ideal bevel from the requested angle when the planner selected another tool.

Unmachinable edges appear as dashed requested-boundary references labeled
`unplanned`; they are not presented as valid toolpaths. Valid plans remain visible
for diagnosis even if another error blocks the setup's G-code. Centerlines show
the current planner's contour and depth, not a verified 3D finished surface.
Existing edge-machining geometry errors must stay visible until fixed separately.
Diagram bounds may expand to show a problematic plan without relaxing CAM checks.

RaisedPanel uses that same compound edge plan: flat-pocket regions enter
POCKET_REGIONS and its V-tip contour enters BEVEL_CUTS, with angle/depth and
field-height labels. Region fills preserve holes and draw beneath centerlines.
They describe intended clearing regions, not finite-cutter corner coverage;
assess that coverage separately from the emitted machining paths.

Defined in `adapters/layoutast_to_ir.py`:

| Feature Type | DiagramIR Layer |
|--------------|-----------------|
| profile | PROFILE_CUTS |
| pocket | POCKET_REGIONS |
| hole | HOLES |
| engrave | ENGRAVE_PATHS |
| bevel | BEVEL_CUTS |
| raised_panel | BEVEL_CUTS and POCKET_REGIONS |
| chamfer | CHAMFER_CUTS |
| roundover | ROUNDOVER_CUTS |
| Unmachinable edge request | UNPLANNED_EDGES |
| notch | PROFILE_CUTS |
| surface | (none — excluded from diagram) |
| waste | WASTE_CUTS |
| Item kind keepout (non-machining) | KEEPOUT_ZONES |

---

## Style Tokens

Defined in `diagram_render/render_svg.py` DiagramTheme:

Sheet clamp margins and fixture keepouts share the theme's red no-cut color
and 15% fill opacity. This is the standard for every generated blueprint,
including recipe, production and back-setup views, in both dark and print
themes. Keep the physical sheet outline visually distinct. A zero margin has
no perimeter band and retains its explicit note; full-bed surfacing remains
the labeled exception.

| Token | Purpose |
|-------|---------|
| default | Fallback style |
| sheet-outline | Sheet boundary |
| profile | Profile cut lines |
| pocket | Pocket regions |
| hole | Drill holes |
| engrave | Engraving paths |
| waste | Waste cut lines |
| keepout | Fixture zone outlines and translucent fills |
| bevel / chamfer / roundover | Planned edge-tool centerlines |
| edge-unplanned | Requested boundary with no valid edge plan |
| edge-label | Edge operation and planned depth or unplanned status |
| toolpath | Toolpath preview |
| dimension | Dimension lines |
| dimension-text | Dimension labels |
| construction | Construction lines |
| label | Part labels |
| notes | Notes text |
| legend | Legend text |
| title | Title block text |
| margin-zone | Sheet margin areas |
| table | Machine table surface |
| envelope | Machine envelope boundary |
| spoilboard | Spoilboard area |
| effective-envelope | Effective work envelope |
| origin | Machine origin marker |
| centerline | Centerline construction |
| soft-limit | Soft limit lines |
| t-track | T-track areas |
| section-label | Edge profile callout title text |
| callout-box | Edge profile callout box outline |
| callout-detail | Edge profile cross-section geometry |
| callout-ref-text | Callout reference/items text |
| callout-dim-text | Callout dimension annotations |
| beam-assembly | Beam assembly outlines |
| beam-layer | Beam layer fills |
| beam-splice | Beam splice joints |
| beam-dim-text | Beam assembly dimension text |
| beam-segment-text | Beam segment and layer labels |
| title-subtitle | Title block subtitle text |

---

## Invariant Types

| Type | Meaning |
|------|---------|
| HARD | Violation breaks the system |
