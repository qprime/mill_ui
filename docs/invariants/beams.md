# Beam Invariants

**Applies to:** Laminated 3D members (posts, rails, legs, aprons, stretchers, stiles, muntins)

**Status:** DRAFT - Architecture proposal

---

## Overview

Beams are fully-shapable laminated 3D members. A beam expands to PanelSpec per layer. All beam features are pre-lamination operations on individual layer panels.

**Core Constraint:** All beam features must be representable as 2.5D operations on panels. Post-lamination machining (true 3D machining on assembled beams) is out of scope.

---

## Manufacturing Phases

Spliced beams require a phased build workflow. The **unit of machining** varies by phase:

| Phase | Description | Unit of Machining |
|-------|-------------|-------------------|
| **A** | Cut segments | Segment (rectangle) |
| **B** | Glue segments end-to-end | — (assembly step) |
| **C** | Machine features on layer strip | Layer strip (full-length panel) |
| **D** | Laminate strips into beam | — (assembly step) |

**Key insight:** Phase C machining operates on a layer strip, which is a single rigid panel after segment glue-up. The strip has the full beam length, a consistent datum (U/V origin), and can receive features that would have crossed segment boundaries.

**Unspliced beams** (length ≤ sheet size): Phases A and B collapse—each layer is a single segment, which is also the layer strip. Phases C and D remain.

### Machining Stage

Features specify which stage they are machined at:

| Stage | When | Constraint |
|-------|------|------------|
| `segment` | Phase A (before segment glue-up) | Feature must not cross segment boundaries |
| `strip` | Phase C (after segment glue-up, before lamination) | Feature may cross segment boundaries |

Default is `strip` for most features, since it provides more flexibility. Features that must be `segment`-stage include edge profiles that affect segment ends.

### Datum Consistency

All layer strips share the same beam-local coordinate system. A feature at U=500mm maps to U=500mm on every layer strip. Physical alignment during lamination (Phase D) relies on edge registration—all strips have identical outer dimensions.

---

## Beam Local Frame

All beam geometry uses a consistent local coordinate frame:

| Axis | Direction | Description |
|------|-----------|-------------|
| **U** | Along member length | Primary dimension |
| **V** | Cross-section height | Perpendicular to length (visible dimension) |
| **W** | Lamination stack | Sheet thickness direction |

**Surface Names:**

| Surface Type | Names | Normal Direction |
|--------------|-------|------------------|
| Faces | front, back | W axis (perpendicular to lamination) |
| Edges | top, bottom | V axis (perpendicular to height) |
| Ends | left, right | U axis (perpendicular to length) |

---

## BeamSpec

A laminated beam with declarative features.

```python
@dataclass(frozen=True)
class BeamSpec:
    name: str
    length_mm: float          # Total beam length (U dimension)
    width_mm: float           # Cross-section height (V dimension)
    thickness_mm: float       # Per-layer sheet thickness

    layers: int | tuple[LayerSpec, ...]  # Uniform count or explicit specs

    face_features: tuple[FaceFeature, ...] = ()
    end_features: tuple[EndFeature, ...] = ()
    edge_features: tuple[EdgeFeature, ...] = ()

    role: BeamRole | None = None

    @property
    def layer_count(self) -> int:
        if isinstance(self.layers, int):
            return self.layers
        return len(self.layers)

    @property
    def total_thickness(self) -> float:
        return self.thickness_mm * self.layer_count

    def expand(self, sheet_size: float) -> list[PanelSpec]:
        """Expand to individual cuttable panels."""
        ...
```

---

## LayerSpec

An individual ply within a laminated beam.

```python
@dataclass(frozen=True)
class Cutout:
    start_mm: float           # Position along layer length
    length_mm: float          # Cutout length
    width_mm: float | None = None  # If None, full width
    offset_from_edge_mm: float = 0.0  # Offset from bottom edge

@dataclass(frozen=True)
class LayerSpec:
    length_mm: float          # Length of this layer
    offset_mm: float = 0.0    # Start offset from beam origin
    cutouts: tuple[Cutout, ...] = ()  # Gaps in this layer
```

**Uniform layers:** When all layers are identical (just staggered for splicing), use `layers: int` on BeamSpec.

**Explicit layers:** When layers differ (extensions, gaps), use `layers: tuple[LayerSpec, ...]`.

---

## Feature Types

Features are declarative specifications applied to beams. During expansion, features translate to panel-level operations (removals, cutouts, profiles).

### FaceFeature

Applied to front or back face of the beam. Replicated identically across all layers.

```python
MachiningStage = Literal["segment", "strip"]

@dataclass(frozen=True)
class DrillHole:
    x_mm: float               # Position along beam length
    y_mm: float               # Position along beam width
    diameter_mm: float
    depth_mm: float | None = None  # None = through-hole
    face: Literal["front", "back"] = "front"
    stage: MachiningStage = "strip"

@dataclass(frozen=True)
class SquareMortise:
    x_mm: float               # Position along beam length (center)
    y_mm: float               # Position along beam width (center)
    width_mm: float           # Mortise width (along length)
    height_mm: float          # Mortise height (along width)
    depth_mm: float           # Mortise depth into face
    face: Literal["front", "back"] = "front"
    stage: MachiningStage = "strip"

@dataclass(frozen=True)
class CarvedDesign:
    x_mm: float               # Origin position along length
    y_mm: float               # Origin position along width
    design: str               # Reference to design template
    depth_mm: float
    face: Literal["front", "back"] = "front"
    stage: MachiningStage = "strip"

@dataclass(frozen=True)
class GeometricPattern:
    x_mm: float
    y_mm: float
    pattern_type: str         # "grid", "diamond", "chevron", etc.
    params: dict              # Pattern-specific parameters
    depth_mm: float
    face: Literal["front", "back"] = "front"
    stage: MachiningStage = "strip"

FaceFeature = DrillHole | SquareMortise | CarvedDesign | GeometricPattern
```

### EndFeature

Applied to left or right end of the beam. May affect layer lengths differently.

```python
@dataclass(frozen=True)
class Tenon:
    end: Literal["left", "right"]
    extension_mm: float       # How far tenon projects past outer layers
    width_mm: float           # Tenon width (subset of beam width)
    height_mm: float          # Tenon height (subset of beam thickness)
    center_offset_mm: float = 0.0  # Offset from beam center
    layers: Literal["center", "outer", "all", tuple[int, ...]] = "center"

@dataclass(frozen=True)
class EndCap:
    end: Literal["left", "right"]
    profile: str              # "square", "rounded", "chamfered", etc.
    params: dict = field(default_factory=dict)

@dataclass(frozen=True)
class EndProfile:
    end: Literal["left", "right"]
    contour: list[tuple[float, float]]  # Profile points

EndFeature = Tenon | EndCap | EndProfile
```

### EdgeFeature

Applied to top or bottom edge of the beam. By default, edge features apply only to outer layers (first and last) since middle layer edges are hidden by lamination.

```python
@dataclass(frozen=True)
class Fillet:
    edge: Literal["top", "bottom"]
    radius_mm: float
    start_mm: float = 0.0
    end_mm: float | None = None
    layers: Literal["outer", "all"] = "outer"
    stage: MachiningStage = "strip"

@dataclass(frozen=True)
class Chamfer:
    edge: Literal["top", "bottom"]
    width_mm: float
    angle_deg: float = 45.0
    start_mm: float = 0.0     # Start position along length
    end_mm: float | None = None  # None = full length
    layers: Literal["outer", "all"] = "outer"
    stage: MachiningStage = "strip"

@dataclass(frozen=True)
class Rabbet:
    edge: Literal["top", "bottom"]
    width_mm: float
    depth_mm: float
    start_mm: float = 0.0
    end_mm: float | None = None
    layers: Literal["outer", "all"] = "outer"
    stage: MachiningStage = "strip"

@dataclass(frozen=True)
class EdgeDado:
    edge: Literal["top", "bottom"]
    position_mm: float        # Position along length
    width_mm: float
    depth_mm: float
    layers: Literal["outer", "all"] = "all"  # dados typically structural, all layers
    stage: MachiningStage = "strip"

@dataclass(frozen=True)
class EdgeNotch:
    edge: Literal["top", "bottom"]
    position_mm: float
    width_mm: float
    depth_mm: float
    layers: Literal["outer", "all"] = "all"  # notches typically structural, all layers
    stage: MachiningStage = "strip"

EdgeFeature = Fillet | Chamfer | Rabbet | EdgeDado | EdgeNotch
```

---

## Lamination-Derived Joinery

Certain joint types emerge from layer configuration rather than cutting:

### Integral Tenon

Center layer(s) extend past outer layers:

```python
BeamSpec(
    name="rail",
    length_mm=500,
    width_mm=100,
    thickness_mm=19,
    layers=3,
    end_features=(
        Tenon(end="right", extension_mm=38, width_mm=100, height_mm=19, layers="center"),
    ),
)
# Expands to:
#   rail_L0: length=500 (outer)
#   rail_L1: length=538, offset=0 (center extends right)
#   rail_L2: length=500 (outer)
```

### Integral Mortise

Gap in layer stack creates mortise without cutting:

```python
BeamSpec(
    name="post",
    length_mm=800,
    width_mm=76,
    thickness_mm=19,
    layers=(
        LayerSpec(length_mm=800),
        LayerSpec(length_mm=800, cutouts=(Cutout(start_mm=200, length_mm=38),)),
        LayerSpec(length_mm=800),
    ),
)
# Center layer has gap at 200mm - forms mortise when laminated
```

---

## Splicing

Splicing achieves beam lengths beyond sheet size through staggered lamination.

### Stagger Calculation

For uniform layers requiring splicing (length > sheet_size):

```python
@dataclass(frozen=True)
class Segment:
    start_mm: float
    end_mm: float
    layer: int
    index: int

    @property
    def length(self) -> float:
        return self.end_mm - self.start_mm

def compute_segments(length: float, sheet_size: float, layers: int) -> list[list[Segment]]:
    """
    Returns: list of layers, each containing list of segments.
    Segments are staggered across layers so butts never align.
    """
    stagger = sheet_size / layers

    result = []
    for layer_idx in range(layers):
        layer_offset = layer_idx * stagger
        layer_segments = []
        pos = 0.0
        seg_idx = 0

        while pos < length:
            if seg_idx == 0:
                seg_len = min(sheet_size - layer_offset, length)
            else:
                seg_len = min(sheet_size, length - pos)

            layer_segments.append(Segment(
                start_mm=pos,
                end_mm=pos + seg_len,
                layer=layer_idx,
                index=seg_idx,
            ))
            pos += seg_len
            seg_idx += 1

        result.append(layer_segments)

    return result
```

### Naming Convention

`{beam_name}_L{layer}_S{segment}`

Example: `rail_left_L0_S0`, `rail_left_L0_S1`, `rail_left_L1_S0`, etc.

---

## Expansion Rules

1. **Single-layer beams** (layers=1) expand to a single PanelSpec identical to a direct panel
2. **Multi-layer beams** expand to multiple panels with staggered segments and replicated features
3. Features are distributed to appropriate panels based on position
4. Same input always produces same output (deterministic)

```
BeamSpec.expand(sheet_size) → list[PanelSpec]
    ├─ Compute segments (if splicing needed)
    ├─ Apply layer specs (lengths, offsets, cutouts)
    └─ Distribute features to panels
```

---

## BeamRole

```python
class BeamRole(Enum):
    POST = auto()       # Vertical structural element
    RAIL = auto()       # Horizontal length-wise member
    LEG = auto()        # Vertical support (tables, chairs)
    APRON = auto()      # Horizontal frame member under tabletop
    STRETCHER = auto()  # Cross-member between legs/rails
    STILE = auto()      # Vertical frame member (doors, frames)
    MUNTIN = auto()     # Internal divider (frames, windows)
```

---

## Invariants

| ID | Type | Invariant | Description |
|----|------|-----------|-------------|
| BM-1 | HARD | BEAM_LOCAL_FRAME_DEFINED | U/V/W axes and surface names defined |
| BM-2 | HARD | LAYERS_POSITIVE | layers >= 1 |
| BM-3 | HARD | SINGLE_LAYER_EQUIVALENT | layers=1 expands to single PanelSpec identical to direct panel |
| BM-4 | HARD | FEATURES_PRE_LAMINATION | All features are per-layer operations |
| BM-5 | HARD | EXPANSION_DETERMINISTIC | Same input always produces same panels |
| BM-6 | HARD | FEATURE_WITHIN_BOUNDS | All features must fit within beam dimensions |
| BM-7 | HARD | CUTOUT_WITHIN_LAYER | Layer cutouts must fit within layer length |
| BM-8 | HARD | SEGMENT_FITS_SHEET | Each segment length <= sheet dimension |
| BM-9 | HARD | BUTTS_NEVER_ALIGN | No two layers share a butt joint position |
| BM-10 | HARD | STAGGER_MINIMUM | Stagger offset >= 2 × thickness (glue surface) |
| BM-11 | HARD | SEGMENT_FEATURE_NO_CROSS | Segment-stage features must not span segment boundaries |
| BM-14 | HARD | DATUM_CONSISTENT | All layer strips share the same beam-local origin; features at U=x align across layers |
| BM-15 | HARD | EDGE_FEATURES_OUTER_DEFAULT | Decorative edge features (fillet, chamfer) default to outer layers only |
| BM-12 | STRUCTURAL | TENON_LAYERS_VALID | Tenon layer specification must reference valid layers |
| BM-13 | STRUCTURAL | MORTISE_DEPTH_SUFFICIENT | mortise_depth >= tenon_length |

---

## Non-Goals

- **Post-lamination machining:** True 3D machining on assembled beams is out of scope
- **Alternative splice methods:** Box joints at splices may be added later; v1 uses stagger only

---

## Implementation Order

1. **LayerSpec, Cutout dataclasses** - simple data structures
2. **Feature dataclasses** - FaceFeature, EndFeature, EdgeFeature types
3. **BeamSpec dataclass** - with expand() stub
4. **Segment calculation** - pure function, testable in isolation
5. **BeamSpec.expand()** - generates PanelSpecs from layers and segments
6. **Feature expansion** - distribute features to appropriate panels
7. **Beam primitives** - post(), rail(), leg(), apron()

Each step is independently testable.

---

## Relationship to Other Invariants

- [components.md](components.md) - Component type hierarchy
- [assembly.md](assembly.md) - Panel interfaces and joinery rules (AJ-*)
- [beds.md](beds.md) - Bed-specific constraints (BD-*)

Beam invariants (BM-*) apply in addition to assembly invariants.

---

## Invariant Types

| Type | Meaning |
|------|---------|
| HARD | Violation breaks the system |
| STRUCTURAL | Requires coordinated migration to change |
