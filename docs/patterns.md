# Extension Patterns

<!-- spec-style -->

**As-Of:** 2026-01-19

Load this document when extending the system with new components, types, or capabilities.

---

## Pattern Index

| Pattern | When to use |
|---------|-------------|
| [Add a New Shape](#pattern-1-add-a-new-shape) | New geometric primitive (Ellipse, Polygon, etc.) |
| [Create a Template](#pattern-2-create-a-template) | Reusable parametric component |
| [Create a Generator](#pattern-3-create-a-generator) | New pattern or operation type |
| [Add a Domain Operation](#pattern-4-add-a-domain-operation) | New algebraic operation on domains |
| [Add a Validation Invariant](#pattern-5-add-a-validation-invariant) | New structural check for CAM artifacts |
| [Add a Metric](#pattern-6-add-a-metric) | New measurement from CAM artifacts |

---

## Pattern 1: Add a New Shape

**When:** New geometric primitive not currently in the system.

**Steps:**
1. AST already supports arbitrary shapes via `Item.type` field (no change needed)
2. Add bounds calculation in `adapters/hints_to_removal.py`
3. Add tests

**Files to modify:**
- `adapters/hints_to_removal.py` — extend `_geometry_to_bounds()` and `_item_geometry_to_bounds()`

**Test location:** `tests/test_removal_intent_model.py`

**Example:** Adding Ellipse bounds calculation

```python
def _item_geometry_to_bounds(item_type, geometry_data, cx, cy):
    if item_type == "Ellipse":
        rx = geometry_data["rx_mm"]
        ry = geometry_data["ry_mm"]
        return Bounds2D(
            x_min=cx - rx, x_max=cx + rx,
            y_min=cy - ry, y_max=cy + ry
        )
```

---

## Pattern 2: Create a Template

**When:** Reusable parametric component (cabinet door, mounting plate, etc.).

**Steps:**
1. Create class in `templates/`
2. Implement `expand_to_ast(params, sheet_thickness_mm) -> LayoutAST`
3. Register in `templates/__init__.py`
4. Add tests

**Files to modify:**
- `templates/new_template.py` (create)
- `templates/__init__.py` (register)

**Test location:** `tests/test_templates.py` or add to existing test module

**Example:** Mounting plate template

```python
from layout_ast.layout import LayoutAST, Sheet, Item, Geometry, Placement, Feature

class MountingPlate:
    @staticmethod
    def expand_to_ast(params: dict, sheet_thickness_mm: float) -> LayoutAST:
        width = params["width"]
        height = params["height"]
        hole_diameter = params["hole_diameter"]
        hole_offset = params.get("hole_offset", 10.0)

        items = [
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": width, "h_mm": height}),
                placement=Placement(center_xy_mm=(width/2, height/2)),
                feature=Feature(type="profile", side="outside", depth="through"),
                shape_id="plate_outer"
            ),
        ]

        for i, (x, y) in enumerate([
            (hole_offset, hole_offset),
            (width - hole_offset, hole_offset),
            (hole_offset, height - hole_offset),
            (width - hole_offset, height - hole_offset),
        ]):
            items.append(Item(
                kind="shape",
                type="Circle",
                geometry=Geometry(data={"diameter_mm": hole_diameter}),
                placement=Placement(center_xy_mm=(x, y)),
                feature=Feature(type="hole", depth="through"),
                shape_id=f"hole_{i}"
            ))

        return LayoutAST(
            sheet=Sheet(
                width_mm=width + 50,
                height_mm=height + 50,
                thickness_mm=sheet_thickness_mm
            ),
            items=tuple(items)
        )
```

---

## Pattern 3: Create a Generator

**When:** New pattern or operation type (spiral, zigzag, circle grid, etc.).

**Steps:**
1. Create parameter dataclass in `generators/base.py`
2. Implement generator function in `generators/area/` or `generators/loop/`
3. Export from `generators/__init__.py`
4. Add tests

**Files to modify:**
- `generators/base.py` (parameter class)
- `generators/area/new_generator.py` or `generators/loop/new_generator.py` (create)
- `generators/__init__.py` (export)

**Test location:** `tests/test_generators.py`

**Example:** Circle pattern generator

```python
@dataclass(frozen=True)
class CirclePatternParams(BaseParams):
    circle_diameter_mm: float
    spacing_mm: float
    depth_mm: float

    def __post_init__(self):
        if self.circle_diameter_mm <= 0:
            raise ValueError(f"circle_diameter_mm must be positive")
        if self.spacing_mm <= 0:
            raise ValueError(f"spacing_mm must be positive")

def circle_pattern_generator(
    domain: Domain,
    params: CirclePatternParams,
    *,
    allow_empty: bool = False,
) -> list[Item]:
    items = []
    bounds = domain.bounds
    spacing = params.spacing_mm + params.circle_diameter_mm

    y = bounds.y_min + spacing / 2
    row = 0
    while y < bounds.y_max:
        x = bounds.x_min + spacing / 2
        col = 0
        while x < bounds.x_max:
            if domain.contains_point((x, y)):
                items.append(Item(
                    kind="shape",
                    type="Circle",
                    geometry=Geometry(data={"diameter_mm": params.circle_diameter_mm}),
                    placement=Placement(center_xy_mm=(x, y)),
                    feature=Feature(type="pocket", depth=params.depth_mm),
                    shape_id=generate_shape_id("circle", f"r{row}c{col}"),
                ))
            x += spacing
            col += 1
        y += spacing
        row += 1

    if not items and not allow_empty:
        raise ValueError("Domain too small for circle pattern")

    return items
```

---

## Pattern 4: Add a Domain Operation

**When:** New algebraic operation on domains (union, convex hull, etc.).

**Steps:**
1. Add method to `Domain` class in `domains/domain.py`
2. Use Shapely for underlying geometry operation
3. Return `MultiDomain` for consistency
4. Add tests

**Files to modify:**
- `domains/domain.py`

**Test location:** `tests/test_domains.py`

**Example:** Union operation

```python
def union(self, other: "Domain") -> "MultiDomain":
    from shapely.ops import unary_union
    result = unary_union([self._polygon, other._polygon])
    return MultiDomain._from_shapely(
        result,
        local_origin=self.local_origin,
        local_rotation=self.local_rotation,
    )
```

---

## Pattern 5: Add a Validation Invariant

**When:** New structural check for CAM artifacts (safety check, quality rule, etc.).

**Steps:**
1. Add invariant ID and check function in `validation/invariants/*_invariants.py`
2. Add to `*_INVARIANT_IDS` list
3. Call from `check_*_invariants()` function
4. Add tests

**Files to modify:**
- `validation/invariants/gcode_invariants.py` (or svg variant)

**Test location:** `tests/test_*_invariants.py`

**Example:** Spindle speed limit check

```python
GCODE_INVARIANT_IDS = [
    "GCODE_SPINDLE_SPEED_LIMIT",
]

def _check_spindle_speed_limit(
    gcode_content: str,
    max_speed: float = 24000.0,
) -> InvariantResult:
    speeds = []
    for line in gcode_content.splitlines():
        if ("M3" in line or "M4" in line) and "S" in line:
            match = re.search(r"S([\d.]+)", line)
            if match:
                speeds.append(float(match.group(1)))

    violations = [s for s in speeds if s > max_speed]

    return InvariantResult(
        id="GCODE_SPINDLE_SPEED_LIMIT",
        category="safety",
        artifact="gcode",
        description=f"Spindle speed must not exceed {max_speed} RPM",
        status=Verdict.FAIL if violations else Verdict.PASS,
        details={"max_allowed": max_speed, "violations": violations},
    )
```

---

## Pattern 6: Add a Metric

**When:** New measurement from CAM artifacts for regression testing.

**Steps:**
1. Add field to `*Metrics` dataclass in `validation/metrics/*_metrics.py`
2. Extract value in `extract_*_metrics()` function
3. Add tests

**Files to modify:**
- `validation/metrics/gcode_metrics.py` (or svg variant)

**Test location:** `tests/test_*_metrics.py`

**Example:** Arc count metric

```python
@dataclass
class GCodeMetrics:
    arc_count: int = 0

def extract_gcode_metrics(gcode_path: str, config: GCodeConfig = None) -> GCodeMetrics:
    arc_count = sum(1 for line in lines if line.startswith(("G2", "G3")))
    return GCodeMetrics(arc_count=arc_count)
```
