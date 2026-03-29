# Coordinate System Invariants

**Applies to:** All geometry, all dimensions, all coordinate transforms

---

## Primary (Axiomatic)

| ID | Type | Invariant | Description |
|----|------|-----------|-------------|
| CS-1 | HARD | ALL_MILLIMETERS | All dimensions use millimeters. No unit conversions. |
| CS-2 | HARD | RIGHT_HANDED_CARTESIAN | Right-handed Cartesian coordinate system |
| CS-6 | HARD | SHEET_XY_PLANE | 2D CAM output lies in X-Y plane, Z for cut depth only |
| CS-7 | HARD | Z_POSITIVE_AWAY | Z positive away from material, negative into material |

## Derived (Consequences)

| ID | Type | Invariant | Description |
|----|------|-----------|-------------|
| CS-3 | HARD | X_LEFT_RIGHT | X axis: Left ↔ Right in assembly space ("Length") |
| CS-4 | HARD | Y_FRONT_BACK | Y axis: Front ↔ Back in assembly space ("Width") |
| CS-5 | HARD | Z_BOTTOM_TOP | Z axis: Bottom ↔ Top in assembly space ("Height") |
| CS-8 | HARD | Z_TOP_ZERO | z_top typically 0.0 at stock surface |
| CS-9 | HARD | Z_BOTTOM_NEGATIVE | z_bottom MUST be negative for material removal |
| CS-10 | HARD | XY_CENTER_BASED | XY coordinates are center-based, stock origin is lower-left |
| CS-11 | HARD | THICKNESS_IS_Z | "Thickness" refers to material thickness along Z axis |
| CS-12 | HARD | DEPTH_IS_NEGATIVE_Z | "Depth" refers to distance along negative Z into material |
| CS-13 | HARD | WORKING_AREA_COORDS | All part coordinates relative to working area origin (0,0) |
| CS-14 | HARD | MARGIN_AT_EXPORT | Margin applied only at export, not internal coords (see scope below) |
| CS-15 | STRUCTURAL | NORMALIZED_TO_ABSOLUTE | Compositional AST uses 0.0-1.0 coords, resolved to absolute |

---

## Working-Area Coordinate System

PML specifies physical sheet dimensions (`physical_width`, `physical_height` or `width`, `height`) and margin. The working area is derived as `physical - 2*margin`. All part coordinates are relative to working area origin (0,0). The margin defines a physical offset applied only at export time.

**Wrong:**
```python
item_x = margin + offset
```

**Correct:**
```python
item_x = offset  # margin applied at export
```

**Why:** The margin zone is a physical no-cut zone reserved for clamps. No cutting operation may encroach on this zone—including tool paths for outside profiles.

**Tool clearance:** Outside profile cuts require part edges to be at least one tool diameter from working area boundaries.

### CS-14 Scope

**CAM pipeline** (`cam/post/gcode.py`): Margin is applied at G-code export via `_apply_margin_offset()`. Internal coordinates (RemovalIntent, planner, passes) remain in working-area space. This is the canonical CS-14 path.

**Diagram/SVG pipeline** (`adapters/layoutast_to_ir.py`): The adapter converts working-area coordinates to sheet-space during DiagramIR generation, baking margin into shape positions (e.g. `sx = margin + cx`, `flip_y` includes margin offset). This is intentional — the DiagramIR represents physical sheet layout for blueprint rendering, so coordinates must be in sheet space. The margin transform happens once in the adapter rather than at final SVG export.

---

## Axis Semantics

| Axis | Assembly Space | Sheet Space | Dimension Term |
|------|----------------|-------------|----------------|
| X | Left ↔ Right | Horizontal | "Length" |
| Y | Front ↔ Back | Vertical | "Width" |
| Z | Bottom ↔ Top | Cut depth | "Height" / "Thickness" |

**Critical:** In sheet space (2D CAM), `width_mm` = X dimension, `height_mm` = Y dimension. This differs from 3D assembly terminology where width = Y and height = Z.

---

## Invariant Types

| Type | Meaning |
|------|---------|
| HARD | Violation breaks the system |
| STRUCTURAL | Requires coordinated migration to change |
