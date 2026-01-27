# Box Generator Design

**Status:** Phase 1 & 2 Complete
**As-Of:** 2026-01-27

## Overview

Add support for CNC-cuttable box panels with extensible joinery, designed to serve as foundation for more complex furniture generators (cabinets, bookcases, etc.).

## Implementation Status

### Phase 1 (Complete)
- [x] `joints/profiles.py` - FingerJointProfile with compute_edge_geometry()
- [x] `domains/edge_joints.py` - apply_edge_joint(), apply_edge_joints()
- [x] `generators/panels/jointed_panel.py` - JointedPanelParams, jointed_panel_generator()
- [x] `generators/assemblies/box.py` - BoxParams, PanelSpec, compute_box_panels()
- [x] PML syntax: `box outer ... thickness ... joinery finger|butt`
- [x] Recipe 38: finger-jointed box example
- [x] 56 unit tests passing

### Phase 2 (Complete) - Bottom/Top Styles & SVG Visualization
- [x] `DadoSpec` dataclass for groove specifications
- [x] `BoxParams` extended with `bottom_style`, `top_style`, `dado_inset_mm`, `dado_drop_mm`
- [x] `PanelSpec` extended with `dados` tuple
- [x] `compute_box_panels()` updated for all three styles
- [x] PML parser updated with new keywords
- [x] Layout resolver generates dado pocket operations
- [x] `pml/syntax_spec.md` documented
- [x] Recipe 39: dado bottom box example
- [x] 15 new tests for bottom/top styles (37 total box tests)
- [x] SVG part labels (`labels` keyword)
- [x] SVG mating edge colors (`edge_colors` keyword)

**PML syntax:**
```pml
bottom_style captured|finger|dado [inset <mm>]
top_style captured|finger|dado [drop <mm>]
```

**Bottom/Top Style Options:**
- `captured` (default): Panel sits inside walls, no mechanical lock
- `finger`: Full finger joints connecting panel to all four walls
- `dado`: Groove cut into walls, panel slides into grooves
  - `inset`/`drop`: Distance from edge to dado position (0 = flush)

**Implementation details:**
- Wall panels get finger joints on bottom/top edges (for `finger` style)
- Wall panels get pocket operations for dado grooves (for `dado` style)
- Panel sizing adjusts based on style
- Phase coordination for bottom/top finger joints

## Design Principles

1. **Primitive-first** - Build reusable joint primitives, not monolithic box generators
2. **Domain-based** - Joints modify Domain geometry; generators clip to resulting polygons
3. **PML-expressible** - All capabilities accessible from PML syntax
4. **Extensible** - Architecture supports future joint types (dado, rabbet, dovetail) without refactoring
5. **Assembly-aware** - SVG output includes part labels and mating edge visualization

## Architecture

### Layer 1: Joint Profiles (Data Classes)

Location: `joints/profiles.py`

```python
from typing import Protocol, Literal
from dataclasses import dataclass

Point2D = tuple[float, float]

class JointProfile(Protocol):
    """Any joint profile must implement this."""
    depth_mm: float

    def compute_edge_geometry(
        self,
        edge_start: Point2D,
        edge_end: Point2D,
    ) -> list[Point2D]:
        """Return vertices for the modified edge."""
        ...

@dataclass(frozen=True)
class FingerJointProfile:
    depth_mm: float
    width_mm: float | None = None      # by_size mode
    count: int | None = None           # by_count mode
    phase: Literal[0, 1] = 0           # 0 = starts with finger, 1 = starts with notch
    clearance_mm: float = 0.1

    def __post_init__(self):
        if (self.width_mm is None) == (self.count is None):
            raise ValueError("Specify exactly one of width_mm or count")

    def compute_edge_geometry(self, edge_start: Point2D, edge_end: Point2D) -> list[Point2D]:
        """Generate finger joint vertices along edge."""
        ...

# Future: DadoProfile, RabbetProfile, DovetailProfile
# They'd implement the same JointProfile protocol
```

**Finger sizing strategies:**
- `by_count`: Explicit finger count, width computed from edge length
- `by_size`: Target finger width, count computed to fit evenly (adjusts width slightly to eliminate remainder)

### Layer 2: Edge Joint Application (Domain Extension)

Location: `domains/edge_joints.py`

```python
from domains import Domain
from joints.profiles import JointProfile

def apply_edge_joint(
    domain: Domain,
    edge_index: int,  # 0-based, CCW from first vertex
    profile: JointProfile,
) -> Domain:
    """Returns new Domain with joint geometry applied to specified edge."""
    ...

def apply_edge_joints(
    domain: Domain,
    edge_joints: dict[int, JointProfile],  # edge_index -> profile
) -> Domain:
    """Apply multiple joints at once."""
    ...
```

### Layer 3: Panel Generators

Location: `generators/panels/jointed_panel.py`

```python
from dataclasses import dataclass
from joints.profiles import JointProfile

@dataclass(frozen=True)
class JointedPanelParams:
    width_mm: float
    height_mm: float
    edge_joints: dict[str, JointProfile | None]  # "top"/"bottom"/"left"/"right" -> profile

def jointed_panel_generator(params: JointedPanelParams) -> list[Item]:
    """Generate a rectangular panel with optional joints on each edge."""
    domain = Domain.from_rectangle(params.width_mm, params.height_mm)

    edge_map = {"bottom": 0, "right": 1, "top": 2, "left": 3}
    for edge_name, profile in params.edge_joints.items():
        if profile:
            domain = apply_edge_joint(domain, edge_map[edge_name], profile)

    return [polygon_item_from_domain(domain, feature="profile through outside")]
```

### Layer 4: Box Assembly Logic

Location: `generators/assemblies/box.py`

```python
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class FingerStrategy:
    mode: Literal["by_count", "by_size"]
    value: int | float  # count or target_width_mm

@dataclass(frozen=True)
class BoxParams:
    outer_width_mm: float
    outer_depth_mm: float
    outer_height_mm: float
    thickness_mm: float
    joinery: Literal["butt", "finger"]
    finger_strategy: FingerStrategy | None = None
    clearance_mm: float = 0.1
    # Phase 2 additions:
    bottom_style: Literal["captured", "finger", "dado"] = "captured"
    top_style: Literal["captured", "finger", "dado"] = "captured"
    dado_inset_mm: float = 0.0   # Bottom dado distance from wall bottom
    dado_drop_mm: float = 0.0    # Top dado distance from wall top
    include_lid: bool = False
    include_bottom: bool = True

@dataclass(frozen=True)
class DadoSpec:
    """Specification for a dado groove on a panel."""
    position_from_edge_mm: float  # Distance from edge to dado start
    width_mm: float               # Dado width (= material thickness)
    depth_mm: float               # Dado depth (= half thickness typically)
    edge: Literal["top", "bottom"]

@dataclass(frozen=True)
class PanelSpec:
    name: str                           # "front", "back", "left", "right", "top", "bottom"
    width_mm: float
    height_mm: float
    edge_joints: dict[str, JointProfile | None]
    mating_edges: dict[str, str]        # "right" -> "right_side.left" (for SVG labels)
    dados: list[DadoSpec] = field(default_factory=list)  # Phase 2: dado grooves

def compute_box_panels(params: BoxParams) -> list[PanelSpec]:
    """
    Returns panel specifications with:
    - dimensions (computed from outer dims and thickness)
    - edge joint configs (with correct phase for mating)
    - mating information (for SVG labels)
    """
    ...
```

### Layer 5: PML Syntax

```pml
# Simple butt box
box outer 200mm 150mm 100mm thickness 6mm joinery butt

# Finger jointed box - by width
box outer 200mm 150mm 100mm thickness 6mm joinery finger
    finger_width 12mm
    clearance 0.1mm

# Finger jointed box - by count
box outer 200mm 150mm 100mm thickness 6mm joinery finger
    finger_count 5
    clearance 0.1mm

# With lid (captured, default)
box outer 200mm 150mm 100mm thickness 6mm joinery finger
    finger_width 12mm
    lid

# Phase 2: Bottom/top styles
# Finger-jointed bottom for structural strength
box outer 200mm 150mm 100mm thickness 6mm joinery finger
    finger_width 12mm
    bottom_style finger

# Dado bottom raised 6mm (keeps contents off surface)
box outer 200mm 150mm 100mm thickness 6mm joinery finger
    finger_width 12mm
    bottom_style dado inset 6mm

# Sealed box with finger-jointed top
box outer 200mm 150mm 100mm thickness 6mm joinery finger
    finger_width 12mm
    lid
    top_style finger

# Recessed lid in dado groove
box outer 200mm 150mm 100mm thickness 6mm joinery finger
    finger_width 12mm
    lid
    top_style dado drop 3mm

# With decorative front panel
box outer 200mm 150mm 100mm thickness 6mm joinery finger
    finger_width 12mm
    front
        inset 20mm
            pocket 3mm

# Front panel with inlay window
box outer 200mm 150mm 100mm thickness 6mm joinery finger
    finger_width 12mm
    front
        at 50mm 50mm width 50mm height 50mm
            pocket 3mm
```

### Layer 6: SVG Assembly Visualization

Location: `export/blueprint.py` (additions)

**Edge color scheme for mating visualization:**

| Edge | Color | Hex | Mnemonic |
|------|-------|-----|----------|
| top | cool blue | `#4A90D9` | Sky above |
| bottom | orange | `#E67E22` | Earth below |
| right | yellow | `#F1C40F` | Sun rises east |
| left | green | `#27AE60` | West/forest |

Mating edges share colors. If `front.right` mates with `right_side.left`, both edges render in the same color (green, since it's the left edge of the mating panel).

```python
def render_part_labels(items: list[Item], labels: dict[str, str]) -> list[SVGElement]:
    """Add text labels to parts (e.g., 'FRONT', 'LEFT SIDE')."""
    ...

def render_mating_edges(items: list[Item], connections: list[MatingConnection]) -> list[SVGElement]:
    """Add colored edge markers showing which edges mate."""
    ...
```

## Edge Naming Convention

For rectangular panels viewed from the front:

```
          top (index 2)
      ┌─────────────────┐
      │                 │
 left │                 │ right
 (3)  │                 │ (1)
      │                 │
      └─────────────────┘
         bottom (index 0)
```

Internal mapping: `{"bottom": 0, "right": 1, "top": 2, "left": 3}` (CCW from bottom-left vertex)

## Finger Joint Geometry

### Vector Convention

For a CCW-wound polygon:
- **Edge direction**: `d = normalize(p1 - p0)`
- **Outward normal**: `n_out = (d.y, -d.x)` (right-hand normal, points away from interior)
- **Inward normal**: `n_in = (-d.y, d.x)`

Fingers protrude in the outward normal direction.

### Finger Count Calculation

**Rule: No half-fingers at corners.** Both ends of an edge have the same feature type.

For `by_count` mode:
```python
count = specified_count
if count % 2 == 0:
    count += 1  # force odd
finger_width = edge_length / count
```

For `by_size` mode:
```python
count = round(edge_length / target_width)
count = max(3, count)  # minimum 3 fingers
if count % 2 == 0:
    count += 1  # force odd
finger_width = edge_length / count  # adjusted to fit exactly
```

Odd count ensures the pattern starts and ends with the same feature type, allowing clean corner merging.

### Phase Logic

Mating edges must have opposite phases to interlock:

- **Phase 0**: Edge starts with a finger (protrusion)
- **Phase 1**: Edge starts with a notch (gap)

For a box corner where `front.right` meets `right_side.left`:
- `front.right` gets phase 0 (fingers)
- `right_side.left` gets phase 1 (notches)

The `compute_box_panels()` function automatically assigns phases so all corners mate correctly.

### Corner Handling

Fingers extend to the exact corner - no margin or special treatment needed. The phase system ensures mating parts interlock correctly. The polygon closes cleanly because both ends of each edge have the same feature type (due to odd count).

### Clearance Application

Clearance is applied to finger sides only (not depth):
- Fingers are shrunk by `clearance_mm / 2` on each side
- Notches are expanded by `clearance_mm / 2` on each side

This creates symmetric gaps for glue and fit tolerance. Typical values:
- **0.1mm** - snug press-fit
- **0.15-0.25mm** - nice glueable fit for plywood/MDF

## File Layout

```
mill_ui/
├── joints/
│   ├── __init__.py
│   └── profiles.py              # JointProfile protocol, FingerJointProfile
├── domains/
│   ├── domain.py                # existing
│   └── edge_joints.py           # apply_edge_joint(), apply_edge_joints()
├── generators/
│   ├── panels/
│   │   ├── __init__.py
│   │   └── jointed_panel.py     # JointedPanelParams, jointed_panel_generator
│   └── assemblies/
│       ├── __init__.py
│       └── box.py               # BoxParams, PanelSpec, compute_box_panels()
├── pml/
│   └── compositional_parser.py  # add box syntax parsing
├── export/
│   └── blueprint.py             # add part labels, edge colors
├── templates/
│   └── box.pml                  # PML template (if needed beyond syntax)
└── docs/
    └── recipes/
        └── XX_finger_box/       # working example
```

## Implementation Order

### Phase 1 (Complete)
1. **`joints/profiles.py`** - FingerJointProfile with compute_edge_geometry()
2. **`domains/edge_joints.py`** - apply_edge_joint() that modifies a Domain
3. **`generators/panels/jointed_panel.py`** - produces polygon Items
4. **`generators/assemblies/box.py`** - computes panel specs from box dimensions
5. **PML syntax in parser** - `box` keyword support
6. **Recipe 38** - finger-jointed box example

### Phase 2 (Planned)
1. **`bottom_style`/`top_style` parameters** - captured/finger/dado options
2. **Bottom edge finger joints** - walls connect at base
3. **Dado groove generation** - pocket operations on wall panels
4. **Panel sizing adjustments** - based on style
5. **Parser updates** - new keywords
6. **Additional recipes** - dado box, sealed box examples

### Future Phases
- SVG edge coloring for mating visualization
- Part labels on SVG output

## Future Extensions

This architecture supports:

| Future Feature | How It Fits |
|----------------|-------------|
| Dado for shelves | Same dado mechanism as bottom/top, positioned anywhere |
| Rabbet joints | New `RabbetProfile` implementing `JointProfile` protocol |
| Dovetail joints | New `DovetailProfile` with angle parameter |
| Cabinet carcase | `compute_cabinet_panels()` using same primitives |
| Bookcase with shelves | Multiple dado positions on side panels |
| Drawers | Smaller boxes with drawer front overlay logic |
| Open-sided boxes | `dado_walls [front, back]` to selectively apply dados |

## Resolved Design Decisions

### 1. Lid Hinges - Compositional

Hinges are added via PML composition, not box parameters. This keeps the box generator focused and allows project-specific hinge choices.

```pml
box outer 150mm 100mm 75mm thickness 6mm joinery finger
    finger_width 12mm
    back
        # Manual placement
        at 20mm 5mm
            hinge_cup diameter 35mm depth 12mm
        at 130mm 5mm
            hinge_cup diameter 35mm depth 12mm

# Or with auto-placement pattern (future)
box outer 150mm 100mm 75mm thickness 6mm joinery finger
    back
        hinge_cups count 2 diameter 35mm depth 12mm inset 20mm from_edge top 5mm
```

Different hinge types would be separate generators:
- `hinge_cup` - Euro/cup hinges (35mm boring + mounting holes)
- `barrel_hinge` - Cylindrical pocket
- `piano_hinge` - Row of screw pilot holes

These are just area generators that happen to be hinge-shaped.

### 2. Nesting - Parts Bucket Approach

**Box generator outputs parts, not layouts.**

```
box params → list[PanelSpec] → list[Item] (unpositioned)
```

Layout and nesting are separate concerns:

```pml
# Single-sheet with explicit layout
sheet 600mm 400mm 6mm
box outer 150mm 100mm 75mm thickness 6mm joinery finger
    layout grid 3 2 gap 10mm

# Multi-box nesting (in .nest file)
nest maxrects
    sheet 1220mm 2440mm 6mm
    parts
        box outer 150mm 100mm 75mm thickness 6mm joinery finger x10
```

The `x10` means 10 boxes = 60 panels fed to the nester.

Mating edge metadata is preserved on each part for SVG visualization, but the nester treats them as independent polygons for packing.

### 3. Kerf vs Clearance - Separate Concerns

- **`clearance_mm`** - Joint fit tolerance (how loose/tight fingers mesh). Applied to finger geometry.
- **`kerf`** - Cut path offset from profile line. Handled by existing sheet/profile kerf parameter.

These are additive but conceptually distinct. A well-fitting joint needs correct clearance regardless of kerf compensation.

## SVG Labeling Strategy

Keep it simple initially:
- **Mating edges** get directional colors (top=blue, bottom=orange, right=yellow, left=green)
- **Part name** label centered on each panel ("FRONT", "LEFT", etc.)

Future enhancements (add when needed):
- Box ID prefix for multi-box nesting ("BOX1-FRONT", "BOX2-FRONT")
- Grain direction arrows
- Assembly sequence numbers

## Example: Complete Finger-Jointed Box

```pml
sheet 600mm 400mm 6mm margin 10mm

box outer 150mm 100mm 75mm thickness 6mm joinery finger
    finger_width 12mm
    clearance 0.15mm
    lid recessed
        recess_depth 3mm
        recess_inset 6mm
    front
        inset 15mm
            pocket 2mm
            lines angle 45 spacing 8mm width 2mm depth 1.5mm
```

This produces:
- 6 panels (front, back, left, right, bottom, lid)
- Finger joints on mating edges with correct phase
- Recessed lid with 3mm deep, 6mm inset lip
- Front panel with decorative inset pocket and diagonal line pattern
- SVG with part labels and color-coded mating edges
