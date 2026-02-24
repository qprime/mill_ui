# Extension Patterns

<!-- spec-style -->

**As-Of:** 2026-02-23

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
| [Add a Planner Feature Type](#pattern-7-add-a-planner-feature-type) | New machining operation the planner must handle |

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
                feature=Feature(type="profile", side="outside", depth_mm=0.0, is_through=True),
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
                feature=Feature(type="hole", depth_mm=0.0, is_through=True),
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
                    feature=Feature(type="pocket", depth_mm=params.depth_mm),
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

---

## Pattern 7: Add a Planner Feature Type

**When:** New machining operation that flows through the full pipeline: RemovalIntent → PlannerInput → planner pass → G-code. Examples: edge chamfer pass, v-carve pass, engraving with a new tool type.

This pattern covers the planner side. If the feature also needs PML syntax, AST nodes, and generators, combine this with Pattern 3 (Create a Generator) and the PML-First checklist in CLAUDE.md.

**Steps:**

1. Define typed input dataclass in `cam/planner/planner_input.py`
2. Add field to `PlannerInput` for the new feature bucket
3. Route from `RemovalIntent` in `adapters/removal_to_planner.py`
4. Implement pass function in `cam/planner/passes/`
5. Add tool selection in `cam/planner/passes/tools.py` if new tool type needed
6. Wire dispatch in `plan_passes()` in `cam/planner/passes/__init__.py`
7. Update `PLANNER_CAPABILITIES` in `cam/planner/capabilities.py`
8. Update support matrix in `docs/invariants/planner.md`
9. Add IR-level tests (invariant PL-4: test at IR, not CAM)

**Files to modify:**

| File | Change |
|------|--------|
| `cam/planner/planner_input.py` | New input dataclass, new field on `PlannerInput` |
| `adapters/removal_to_planner.py` | Extract from `RemovalIntent`, populate new bucket |
| `cam/planner/passes/new_pass.py` | **Create** — pass function |
| `cam/planner/passes/tools.py` | Tool selection for new operation (if needed) |
| `cam/planner/passes/__init__.py` | Call new pass from `plan_passes()` |
| `cam/planner/capabilities.py` | Update `PLANNER_CAPABILITIES` status |
| `docs/invariants/planner.md` | Update support matrix table |

**Test location:** `tests/test_planner_passes.py` or new test module

**Constraints:**

- Planner passes receive typed frozen dataclasses, not untyped dicts (invariant PC-3)
- Unsupported constraints must not silently pass — warn or error (invariant PC-1)
- Every pipeline run audits constraints and emits a summary (invariant PC-2)
- All Z values respect safe_z for rapids (invariant GC-1)
- Single plunge must not exceed max_stepdown (invariant GC-4)
- All XY coordinates within sheet + margin (invariant GC-8)

**Example:** Adding a hypothetical groove pass

### Step 1: Typed input dataclass

```python
@dataclass(frozen=True)
class GrooveInput:
    id: str
    shape: str
    geometry: GeometryInput
    center_xy_mm: tuple[float, float]
    depth_mm: float
    groove_width_mm: float
    start_depth_mm: float = 0.0
```

### Step 2: Add to PlannerInput

```python
@dataclass(frozen=True)
class PlannerInput:
    ...
    grooves: tuple[GrooveInput, ...] = field(default_factory=tuple)
```

### Step 3: Route from RemovalIntent

In `adapters/removal_to_planner.py`, extract the new feature type from RemovalIntent and populate the new bucket:

```python
def removal_intents_to_planner_input(...) -> PlannerInput:
    ...
    grooves: list[GrooveInput] = []

    for intent in intents:
        if intent.hint_type == "groove":
            grooves.append(_intent_to_groove_input(intent))
        else:
            ...

    return PlannerInput(
        ...
        grooves=tuple(grooves),
    )
```

### Step 4: Implement the pass

```python
def plan_groove_passes(
    grooves: tuple[GrooveInput, ...],
    *,
    accumulator: "PassAccumulator",
    tool_db: Sequence[ToolSelection],
) -> None:
    for entry in grooves:
        tool = pick_tool_for_groove(tool_db, groove_width_mm=entry.groove_width_mm)
        record = accumulator.get_record("groove", tool)

        moves = generate_groove_moves(
            center=entry.center_xy_mm,
            geometry=entry.geometry,
            depth_mm=entry.depth_mm,
            tool=tool,
            setup=record.setup,
        )
        record.add_moves(moves, increment=1)
```

### Step 5: Wire dispatch

In `cam/planner/passes/__init__.py`:

```python
def plan_passes(planner_input, *, config, tool_db, ...):
    ...
    plan_groove_passes(planner_input.grooves, accumulator=accumulator, tool_db=tool_db)
    ...
```

### Step 6: Update capabilities

```python
PLANNER_CAPABILITIES = {
    ...
    "groove": ConstraintStatus(ConstraintSupport.HONORED),
}
```

### Step 7: Update planner invariant support matrix

In `docs/invariants/planner.md`, add row to the support table:

```
| groove | HONORED | — | Boundary-following groove cut |
```

### Key conventions from existing passes

- Pass functions take a tuple of typed inputs + `accumulator` + `tool_db`
- Pass functions return `None` — they append moves to the accumulator
- `accumulator.get_record(operation, tool)` groups moves by operation+tool into separate `.nc` files
- Tool selection happens per-feature inside the pass, not before
- Depth stepping uses `stepdown_for_tool()` from `tools.py`
- Stepover uses `stepover_for_tool()` from `tools.py`
