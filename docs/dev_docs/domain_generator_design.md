# Domain & Generator System - Design Document

**Document Purpose:** Define architecture, contracts, and development stages for a math-based domain and generator system that replaces template proliferation with composable primitives.

**Primary Audience:** AI agents (Claude Opus for implementation, ChatGPT Codex for review)

**Last Updated:** 2026-01-17

---

## 1. System Overview

### 1.1 Problem Statement

mill_ui currently supports cabinet door and drawer front generation through templates (e.g., Shaker). While templates work well for common designs, they create structural problems as the system scales:

- **Template explosion**: Each new style requires a new template. Variations (different rail widths, panel treatments, border decorations) multiply the count further.
- **Redraw labor**: Size variations of the same design require manual parameter adjustment or template duplication.
- **Style-specific geometry**: Similar operations (profiling, pocketing, decorating) are reimplemented per template rather than shared.
- **SKU rigidity**: Adding a new SKU means adding code, not composing existing primitives.

The fundamental issue is that templates conflate *what* to machine with *how* to express it. A Shaker door and a flat-panel door with decorative border share most of their geometric logic, but this sharing is not captured in the template abstraction.

### 1.2 Solution: Math-Based Composition

This design introduces two primitives that separate concerns:

**Domains** are bounded 2D regions that define *where* operations may occur. They are purely geometric—polygonal boundaries with optional holes. Domains support algebraic operations (inset, offset, subtract, intersect) that derive new regions from existing ones.

**Generators** are deterministic functions that define *what* geometry to produce within a domain. They receive a domain and typed parameters, and emit zero or more LayoutAST items. Generators are unaware of sheets, tools, or G-code.

This separation enables:

- **Hundreds of SKUs from few primitives**: A wave pattern generator works on any domain. A border is just a domain with a hole. Combining domains and generators creates variety without new code.
- **Exact-size flexibility**: Domains are computed from parameters, not drawn. Any size is as easy as any other.
- **Zero design cost for mixed styles**: Swapping generators on the same domain changes the style without changing the structure.
- **Deterministic manufacturing**: Same domain + same generator + same params = same output, always.

### 1.3 Design Principles

| Principle | Rationale |
|-----------|-----------|
| **Polygonal domains** | Curves are lowered to polylines early; keeps domain algebra tractable and deterministic |
| **Typed generator params** | Validation happens at generator entry; prevents flat-dict rot and enables clear error messages |
| **Domain-local coordinates** | Generators operate in a normalized frame; rotation and translation handled by transform layer |
| **Generator-owned depth** | Domains define 2D scope only; depth is a machining decision made by generators |
| **Explicit loop selection** | Loop generators require caller to specify which boundaries to operate on; no implicit guessing |
| **Loud failures** | This is a manufacturing pipeline; silent degradation causes physical defects and waste |
| **Additive migration** | Domains coexist with existing templates; no flag day, no forced rewrites |

### 1.4 One-Line Summary

mill_ui becomes a software assembly line where cabinet doors are compiled, not drawn—domains define where, generators define what, constraints define limits, and the CNC is just the actuator.

---

## 2. Architecture

### 2.1 High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        DESIGN PIPELINE                          │
└─────────────────────────────────────────────────────────────────┘

  ┌──────────────┐
  │  PML / JSON  │
  │  / Template  │
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐     ┌─────────────────────────────────────────┐
  │   Domain     │────▶│            GENERATORS                   │
  │  Composition │     │  ┌─────────────┐    ┌────────────────┐  │
  │              │     │  │    Area     │    │     Loop       │  │
  │  inset()     │     │  │  Generators │    │   Generators   │  │
  │  subtract()  │     │  │             │    │                │  │
  │  intersect() │     │  │  - waves    │    │  - beads       │  │
  │  offset()    │     │  │  - grids    │    │  - grooves     │  │
  │              │     │  │  - textures │    │  - v-carves    │  │
  │              │     │  │  - flats    │    │  - profiles    │  │
  └──────────────┘     │  └──────┬──────┘    └───────┬────────┘  │
                       └─────────┼──────────────────┼────────────┘
                                 │                  │
                                 ▼                  ▼
                       ┌─────────────────────────────────────────┐
                       │         LayoutAST Items [0..n]          │
                       └──────────────────┬──────────────────────┘
                                          │
                                          ▼
                       ┌─────────────────────────────────────────┐
                       │       RemovalIntent IR [0..n]           │
                       └──────────────────┬──────────────────────┘
                                          │
                                          ▼
                       ┌─────────────────────────────────────────┐
                       │           Validation Checks             │
                       │   (overlap, depth, toolability)         │
                       └──────────────────┬──────────────────────┘
                                          │
                                          ▼
                       ┌─────────────────────────────────────────┐
                       │              CAM Planner                │
                       └──────────────────┬──────────────────────┘
                                          │
                                          ▼
                       ┌─────────────────────────────────────────┐
                       │                G-code                   │
                       └─────────────────────────────────────────┘
```

### 2.2 Module Structure

**Current state (unchanged by this design):**
```
mill_ui/
├── layout_ast/
│   └── layout.py           # LayoutAST, Item, Sheet, etc.
├── ir/
│   └── removal_intent.py   # RemovalIntent IR
├── adapters/
│   └── ast_to_removal.py   # AST → IR conversion
├── templates/
│   ├── __init__.py
│   └── shaker.py           # Existing Shaker template
├── validation/
│   ├── removal_checks.py   # IR-level validation
│   └── ...
└── ...
```

**Target state (after Stage 7):**
```
mill_ui/
├── domains/
│   ├── __init__.py         # Public exports: Domain, operations
│   ├── domain.py           # Domain dataclass and core operations
│   ├── transforms.py       # Local ↔ sheet coordinate transforms
│   └── loops.py            # Loop extraction from domain boundaries
│
├── generators/
│   ├── __init__.py         # Public exports: all generators
│   ├── base.py             # Generator protocol definition
│   ├── area/
│   │   ├── __init__.py
│   │   ├── flat.py         # Flat pocket generator
│   │   ├── wave.py         # Wave pattern generator
│   │   └── grid.py         # Grid pattern generator
│   └── loop/
│       ├── __init__.py
│       ├── profile.py      # Profile cut generator
│       └── bead.py         # Bead/groove generator
│
├── layout_ast/             # (unchanged)
├── ir/                     # (unchanged)
├── adapters/               # (unchanged)
├── templates/              # (unchanged, coexists)
├── validation/             # (unchanged)
└── ...
```

### 2.3 Key Architectural Decisions

**Domains are not LayoutAST nodes.** Domains exist at a higher conceptual level. They are used to compute geometry, then discarded. The LayoutAST receives the computed Items, not the domains that produced them.

**Generators are not templates.** Templates are monolithic functions that produce complete LayoutASTs. Generators are composable functions that produce Items for a single domain. A template might internally use multiple generators on multiple domains, but generators do not know about templates.

**The IR layer is unchanged.** RemovalIntent validation (overlap, depth feasibility, toolability) continues to work exactly as before. Generators simply produce more Items, which become more Intents.

---

## 3. Core Concepts

### 3.1 Domain

A Domain is a bounded 2D region represented as a simple polygon with optional holes.

**What a Domain is:**
- A polygonal outer boundary (ordered vertices, implicitly closed)
- Zero or more polygonal inner boundaries (holes/constraints)
- A local coordinate frame (origin, rotation)
- Purely geometric—no depth, no feature type, no machining semantics

**What a Domain is not:**
- Not a shape in the LayoutAST sense (no `kind`, no `feature`)
- Not depth-aware (depth belongs to generators)
- Not a toolpath or machining operation
- Not a visual element (no stroke, no fill, no style)

**How Domains are created:**
- From explicit vertex lists (programmatic construction)
- From rectangular parameters (convenience constructor)
- From domain operations on other domains (algebraic derivation)
- From PML region resolution (future integration)

**Domain properties:**
- `outer_boundary`: Ordered list of 2D points defining the outer edge
- `inner_boundaries`: List of ordered point lists defining holes
- `local_origin`: Point in sheet space that maps to (0,0) in domain-local space
- `local_rotation`: Angle (radians) of the domain's local X-axis relative to sheet X-axis

### 3.2 Domain Operations

Domains support four algebraic operations that derive new domains from existing ones. All operations return `MultiDomain` to handle cases where results may be empty or split into multiple regions.

**inset(distance, join_style="mitre", mitre_limit=5.0) → MultiDomain**

Contracts the outer boundary inward by the specified distance (uses `Shapely.buffer(-distance)`). Inner boundaries (holes) are expanded outward by the same distance, making holes larger. If the inset distance exceeds half the minimum dimension, the result is an empty MultiDomain. Default join style is `mitre` (sharp corners) for woodworking geometry; use `round` for decorative curves.

**offset(distance, join_style="mitre", mitre_limit=5.0) → MultiDomain**

Expands the outer boundary outward by the specified distance (uses `Shapely.buffer(distance)`). Inner boundaries (holes) are contracted inward. If a hole contracts to nothing, it is removed from the result. Default join style is `mitre` (sharp corners) for woodworking geometry.

**subtract(other) → MultiDomain**

Removes the region covered by another domain from this domain (uses `Shapely.difference()`). The subtracted region may create holes or split the domain into disjoint pieces. If the subtracted region fully contains this domain, the result is an empty MultiDomain. If they do not overlap, this domain is returned unchanged (as single-element MultiDomain).

**intersect(other) → MultiDomain**

Keeps only the region where this domain and another domain overlap (uses `Shapely.intersection()`). If they do not overlap, the result is an empty MultiDomain. May produce multiple disjoint regions if the intersection is non-contiguous.

**Edge cases:**
- Operations that produce empty results return an empty MultiDomain (`domains=()`), not null/none
- Operations that produce a single region return a single-element MultiDomain for API consistency
- Self-intersecting results from offset are resolved by Shapely (union of overlapping regions)
- Derived domains inherit `local_origin` and `local_rotation` from the source domain (preserves pattern alignment to original panel edges)
- To re-center a domain on its own geometry, use `domain.with_origin_at_centroid()`

### 3.3 Generators

Generators are deterministic functions that produce geometry within a domain.

**Two generator classes exist, distinguished by what they operate on:**

**Area generators** operate over the 2D interior of a domain. They fill regions with patterns, textures, or uniform treatments. Examples: flat pockets, wave patterns, grid patterns, raster textures, medallions. Area generators respect inner boundaries as constraints—patterns flow around holes, they do not cross them.

**Loop generators** operate on boundary loops (edges) of a domain. They follow paths and produce geometry along them. Examples: profile cuts, beads, grooves, v-carves, decorative borders. Loop generators require explicit specification of which loops to operate on.

**What generators share:**
- Receive a domain and typed parameters
- Operate in domain-local coordinates
- Emit zero or more LayoutAST Items
- Are deterministic (same inputs → same outputs)
- Are unaware of sheets, tools, G-code, or other generators

**What generators do not do:**
- Modify the domain they receive
- Depend on global state or external resources
- Produce partial output on failure
- Know about the broader design context

### 3.4 Constraints and Boundaries

The domain/generator model unifies several concepts that might otherwise be separate:

**Borders are constrained panels.** A "border region" is simply a domain with an inner hole. The same area generator that fills a full panel can fill a border—the inner boundary constrains where the pattern appears.

**Panel decorations are unconstrained borders.** A decorated panel is a full domain (no holes) with a pattern generator. The same generator works for both; only the domain differs.

**Layering is domain composition.** Foreground/background effects are achieved by subtracting regions, not by clipping. A raised medallion on a textured background is: (1) full domain with texture generator, (2) medallion domain subtracted, (3) medallion domain with flat generator at different depth.

**Loop selection is explicit.** When a loop generator operates on a domain with holes, the caller must specify which loops to use: outer only, inner only, all loops, or an explicit list by index. This prevents ambiguity about design intent.

### 3.5 Geometry Backend

Domain operations use **Shapely** (Python bindings to GEOS) for polygon boolean and offset operations.

**Why Shapely:**
- Mature, well-documented API familiar to Python developers
- Handles boolean ops (`difference`, `intersection`), offsets (`buffer`), and winding normalization (`orient`)
- Returns `MultiPolygon` naturally when operations split geometry
- Float-based coordinates in mm—no integer scaling needed for wood CAM tolerances

**Precision:**
- All coordinates are double-precision floats in millimeters
- Practical precision floor: 0.01mm (10 microns)—well under CNC positioning accuracy (±0.05-0.1mm)
- Final output coordinates may be rounded to 0.01mm before G-code generation
- Platform determinism is ensured by rounding to practical precision, not by integer arithmetic

**Winding Convention (OGC standard, enforced by `shapely.ops.orient()`):**
- Outer boundaries: Counter-clockwise (CCW), positive signed area
- Inner boundaries (holes): Clockwise (CW), negative signed area
- Domain construction normalizes all input boundaries to this convention

**Buffer Configuration (for inset/offset):**
- Default join style: `mitre` (sharp corners for rectangular woodworking geometry)
- Default mitre limit: `5.0` (prevents extremely sharp spikes on acute angles)
- Default cap style: `flat` (for any open path segments, though domains are closed)
- Override via `inset(distance, join_style="round")` for decorative curves

**Installation:** `pip install shapely`

### 3.6 MultiDomain

Boolean operations (`subtract`, `intersect`) and offset operations can produce multiple disjoint regions. These are represented as `MultiDomain`.

```python
@dataclass(frozen=True)
class MultiDomain:
    """Zero or more disjoint domains from boolean/offset operations."""
    domains: tuple[Domain, ...]

    @property
    def is_empty(self) -> bool:
        return len(self.domains) == 0

    def __iter__(self):
        return iter(self.domains)

    def __len__(self):
        return len(self.domains)
```

**Usage pattern:**
```python
# Subtract may split a domain into pieces
result: MultiDomain = outer_domain.subtract(center_cutout)

# Iterate over resulting domains
for domain in result:
    items.extend(flat_pocket_generator(domain, params))

# Or check for empty result
if result.is_empty:
    raise ValueError("Subtraction produced empty result")
```

**Single-domain convenience:** When an operation is guaranteed to produce a single domain (e.g., `inset` on a convex polygon), it still returns `MultiDomain` for API consistency. Callers can use `result.domains[0]` or iterate.

---

## 4. Interface Contracts

### 4.1 Domain Contract

**Inputs for construction:**
- Outer boundary: ordered list of 2D points (minimum 3 points)
- Inner boundaries: list of ordered point lists (each minimum 3 points), optional
- Local origin: 2D point, optional (defaults to centroid of outer boundary)
- Local rotation: angle in radians, optional (defaults to 0)

**Outputs:**
- Domain instance with computed properties (bounds, area, centroid)

**Invariants:**
- Outer boundary is always non-empty after successful construction
- Outer boundary vertices are counter-clockwise (CCW), enforced by `shapely.ops.orient()` on construction
- Inner boundaries are clockwise (CW), enforced by `shapely.ops.orient()` on construction
- Inner boundaries do not intersect outer boundary or each other
- Inner boundaries are fully contained within outer boundary
- Local origin and rotation define a valid coordinate transform

**Non-responsibilities:**
- Domain does not validate whether geometry is machinable
- Domain does not know about depth, tools, or features
- Domain does not render or visualize itself
- Domain does not serialize to PML (that is a separate concern)

**Error conditions:**
- Fewer than 3 outer boundary points: raise exception
- Inner boundary not contained in outer: raise exception
- Inner boundaries intersect each other: raise exception
- Self-intersecting boundary: raise exception

### 4.2 Generator Contract

**Inputs:**
- Domain: a valid Domain instance
- Parameters: a typed parameter object specific to the generator
- Optional configuration: `allow_empty` flag (default false)

**Outputs:**
- List of LayoutAST Item instances (may be empty if `allow_empty=True`)

**Invariants:**
- Output Items have geometry in sheet coordinates (transformed from domain-local)
- Output Items have valid `kind`, `type`, `geometry`, `placement`, `feature` fields
- Output is deterministic: same domain + same params → same Items
- Generator does not modify the input domain

**Non-responsibilities:**
- Generator does not validate the domain (assumes valid input)
- Generator does not know about sheets, other generators, or the broader design
- Generator does not produce RemovalIntents (that is the adapter's job)
- Generator does not handle tool selection or CAM planning

**Error conditions:**
- Domain too small for requested operation (e.g., wave amplitude exceeds domain width): raise exception unless `allow_empty=True`
- Invalid parameter values (negative dimensions, out-of-range angles): raise exception
- Parameters incompatible with domain geometry: raise exception with clear message

### 4.3 Coordinate Transform Contract

**Domain-local to sheet-space transform:**
- Input: point in domain-local coordinates (origin at domain's local_origin, X-axis at local_rotation)
- Output: point in sheet coordinates (origin at sheet corner, axes aligned with sheet)
- The transform applies rotation first, then translation

**Sheet-space to domain-local transform:**
- Inverse of the above
- Used when importing geometry into a domain's frame

**Invariants:**
- Round-trip transform preserves coordinates within floating-point precision
- Transform is linear (preserves lines, distances within the same frame)
- Rotation is counter-clockwise positive

**Non-responsibilities:**
- Transform does not scale (domains and sheets use the same units: mm)
- Transform is 2D only (no Z coordinate handling; depth is a separate generator concern)

### 4.4 Loop Extraction Contract

**Inputs:**
- Domain: a valid Domain instance
- Selection mode: one of `outer_only`, `inner_only`, `all_loops`, or explicit index list

**Outputs:**
- List of loops, where each loop is an ordered list of 2D points

**Invariants:**
- `outer_only` returns exactly one loop (the outer boundary)
- `inner_only` returns zero or more loops (inner boundaries only)
- `all_loops` returns outer boundary first, then inner boundaries in order
- Explicit index list returns loops in the order specified (0 = outer, 1+ = inner)

**Error conditions:**
- Index out of range in explicit list: raise exception
- Invalid selection mode: raise exception

---

## 5. Data Schemas

All data structures are JSON-serializable for debugging, logging, and potential persistence.

### 5.1 Domain Representation

```json
{
  "domain": {
    "outer_boundary": [[x1, y1], [x2, y2], ...],
    "inner_boundaries": [
      [[x1, y1], [x2, y2], ...],
      ...
    ],
    "local_origin": [ox, oy],
    "local_rotation_rad": 0.0,
    "computed": {
      "bounds": {"x_min": 0, "x_max": 100, "y_min": 0, "y_max": 100},
      "area_mm2": 10000.0,
      "centroid": [50, 50]
    }
  }
}
```

**Notes:**
- All coordinates are in millimeters
- `outer_boundary` and `inner_boundaries` use sheet coordinates
- `computed` fields are derived, not stored, but included in serialization for inspection

### 5.2 MultiDomain Representation

```json
{
  "multi_domain": {
    "domains": [
      { "outer_boundary": [...], "inner_boundaries": [...], ... },
      { "outer_boundary": [...], "inner_boundaries": [...], ... }
    ],
    "count": 2
  }
}
```

**Notes:**
- Each element in `domains` follows the Domain schema from 5.1
- `count` is derived (len of domains array) but included for convenience
- Empty MultiDomain has `"domains": []` and `"count": 0`

### 5.3 Generator Parameter Schemas

Each generator defines its own parameter schema. Parameters are typed and validated at generator entry.

**FlatPocketParams:**
```json
{
  "depth_mm": 6.0,
  "allowance_mm": 0.0
}
```

**ProfileParams:**
```json
{
  "side": "outside" | "inside" | "on",
  "depth": "through" | <number>,
  "tab_count": 0,
  "tab_width_mm": 10.0
}
```

**WaveParams:**
```json
{
  "amplitude_mm": 3.0,
  "wavelength_mm": 20.0,
  "phase_rad": 0.0,
  "direction_rad": 0.0,
  "depth_mm": 2.0,
  "tool_width_mm": 3.175,
  "wave_count": null
}
```

**GridParams:**
```json
{
  "spacing_x_mm": 25.0,
  "spacing_y_mm": 25.0,
  "line_width_mm": 3.0,
  "depth_mm": 2.0,
  "offset_x_mm": 0.0,
  "offset_y_mm": 0.0
}
```

**BeadParams:**
```json
{
  "width_mm": 6.0,
  "depth_mm": 3.0,
  "offset_mm": 0.0,
  "loop_selection": "outer_only" | "inner_only" | "all_loops" | [0, 2, ...]
}
```

**Notes:**
- All dimensions are in millimeters
- Angles are in radians
- `null` values indicate "compute automatically" (e.g., wave_count fits domain)
- Enums use string values for JSON compatibility

### 5.4 Generator Output

Generators output standard LayoutAST Items. The schema is defined in `layout_ast/layout.py`.

**Supported shape types:**
- `Polygon`: Closed polygon from points array (used by FlatPocket, Profile, Bead)
- `Rect`, `Circle`, `RoundedRect`: Standard primitives
- `Line`: Line segment from start/end points (used by Grid)
- `Polyline`: Open path from points array (used by Wave)

**Supported feature types:**
- `pocket`: Area removal (FlatPocket)
- `profile`: Boundary cut (Profile)
- `hole`: Drilling operation
- `engrave`: Surface marking/groove (Wave, Grid, Bead)

```json
{
  "kind": "shape",
  "type": "Polygon" | "Line" | "Polyline" | "Rect" | "Circle" | ...,
  "geometry": {"data": {...}},
  "placement": {"center_xy_mm": [x, y]},
  "feature": {
    "type": "pocket" | "profile" | "hole" | "engrave",
    "depth": 6.0 | "through",
    "side": "outside" | "inside" | "on"
  },
  "shape_id": "generated_wave_001"
}
```

**Geometry data by shape type:**
- `Polygon`/`Polyline`: `{"points": [[x, y], ...], "holes": [...]}` (holes for Polygon only)
- `Line`: `{"start": [x, y], "end": [x, y], "width_mm": 3.0}`
- `Rect`: `{"w_mm": 100, "h_mm": 50}`
- `Circle`: `{"diameter_mm": 25}`

---

## 6. Pipeline Integration

### 6.1 Domain → Generator → LayoutAST

The design flow proceeds as follows:

1. **Domain composition**: The caller creates domains using constructors and operations. This may involve multiple inset/subtract/intersect calls to build the desired regions.

2. **Generator invocation**: For each domain, the caller invokes one or more generators with appropriate parameters. Each generator returns a list of LayoutAST Items.

3. **Item collection**: Items from all generators are collected into a single list.

4. **AST construction**: The collected Items are combined with a Sheet definition to form a complete LayoutAST.

Domains are consumed during this process—they are not part of the LayoutAST. The AST contains only the resulting Items.

### 6.2 LayoutAST → RemovalIntent IR

The existing `ast_to_removal_intents` adapter converts LayoutAST Items to RemovalIntents. This adapter is unchanged by this design.

**Key behaviors:**
- Each Item produces one RemovalIntent (typically)
- The adapter extracts bounds, depth, feature type from the Item
- Complex Items (polygons) are converted to bounds; actual geometry travels separately

**Generator cardinality:**
- A generator may emit zero Items (empty domain, `allow_empty=True`)
- A generator may emit one Item (flat pocket, profile cut)
- A generator may emit many Items (grid produces multiple lines; wave may produce multiple paths)
- Each Item becomes one Intent, so one generator invocation may produce many Intents

### 6.3 Validation Integration

IR-level validation in `validation/removal_checks.py` applies unchanged:

- **Overlap detection**: Checks if RemovalIntents have conflicting regions
- **Depth feasibility**: Checks if depths are achievable given sheet thickness
- **Toolability**: Checks if geometry can be machined with available tools

Generators do not need to perform these checks. They produce geometry; validation catches conflicts.

**Future consideration:** Domain-level validation could catch some issues earlier (e.g., domain too small for requested pattern). This is not in initial scope but the architecture supports it.

### 6.4 CAM Planner Expectations

The CAM planner receives RemovalIntents and produces G-code. It is unchanged by this design.

**What the planner expects:**
- Valid RemovalIntents with bounds, depth, feature type
- No overlapping removal regions (caught by validation)
- Depths within sheet thickness (caught by validation)

**What the planner does not know:**
- That geometry came from domains and generators
- The original domain structure
- Generator parameters

This separation is intentional. The planner operates on machining semantics (RemovalIntent), not design semantics (domains/generators).

---

## 7. Determinism & Reproducibility

### 7.1 Coordinate Guarantees

Generators operate in domain-local coordinates to ensure consistent output regardless of where a domain is placed on the sheet.

**Domain-local coordinate system:**
- Origin at the domain's `local_origin` (default: centroid of outer boundary)
- X-axis rotated by `local_rotation` from sheet X-axis (default: aligned)
- All generator math happens in this frame
- Output geometry is transformed to sheet coordinates before returning

**Why this matters:**
- A wave pattern generated in a 100×100mm domain at sheet position (0,0) is identical to one at (200,300)
- Rotating a domain rotates the pattern with it
- Nesting the same part multiple times produces identical internal geometry

### 7.2 Reproducibility Contract

The system guarantees reproducibility within practical tolerances for wood CNC:

**PML + code revision = equivalent output**

Given:
- The same PML source (or equivalent programmatic input)
- The same mill_ui code revision (git commit)

The system produces:
- Identical LayoutAST
- Identical RemovalIntents
- G-code equivalent within 0.01mm (practical precision floor)

**Precision context (wood CNC):**
- CNC positioning accuracy: ±0.05-0.1mm
- End mill runout: 0.02-0.05mm
- Wood movement (humidity): 0.5-2mm across a panel
- Kerf width variation: 0.1-0.2mm

**Practical precision floor: 0.01mm**
- Coordinates are double-precision floats throughout
- Final output may round to 0.01mm before G-code generation
- Any platform differences below 0.01mm are irrelevant to physical outcomes
- This is 5-10x tighter than CNC positioning accuracy

**No external state:**
- Generators do not read files, clocks, random numbers, or environment variables
- All inputs are explicit parameters
- No caching affects output (caching may affect performance, not results)

### 7.3 Reproducibility Verification

To verify reproducibility:
1. Run the same input twice
2. Compare LayoutAST (structural equality)
3. Compare RemovalIntents (structural equality)
4. Compare G-code (byte equality, or metric equality via validation system)

Any difference indicates a bug in determinism.

---

## 8. Error Philosophy

### 8.1 Failure Categories

**Hard errors (exceptions):**
- Invalid domain construction (self-intersecting, too few points)
- Invalid generator parameters (negative dimensions, out-of-range values)
- Unsatisfiable constraints (domain too small for requested operation)
- These always raise exceptions with descriptive messages

**Soft failures (empty output with flag):**
- When `allow_empty=True`, generators that cannot produce output return an empty list instead of raising
- This is opt-in; default behavior is hard error
- Use case: conditional generation where absence is acceptable

**Never allowed (silent partial output):**
- A generator must never produce some geometry and silently skip the rest
- If a wave pattern cannot fit 10 waves, it does not produce 7 and hope nobody notices
- Either all requested geometry is produced, or an error is raised

### 8.2 Error Message Requirements

Error messages must be actionable. They must include:
- What operation failed
- What constraint was violated
- What the actual values were
- What values would be acceptable

**Good error message:**
"WaveGenerator: amplitude 15mm exceeds half of domain width 20mm. Maximum amplitude for this domain is 10mm."

**Bad error message:**
"Invalid parameter"

### 8.3 Error Surfacing

Errors surface to callers as exceptions. The caller decides how to handle them:
- Propagate to user with explanation
- Catch and try alternative parameters
- Catch and skip this domain (if `allow_empty` semantic is desired but exception was raised)

Generators do not log, warn, or print. They raise or return.

---

## 9. Migration & Coexistence

### 9.1 Existing Templates Remain Valid

Templates like Shaker continue to work exactly as before:
- `Shaker.expand_to_ast(params, sheet_thickness)` returns a LayoutAST
- The LayoutAST converts to RemovalIntents via existing adapter
- No changes required to template code

Templates and domain/generators coexist in the same codebase and can be used in the same project.

### 9.2 Domain as Additive Layer

Domains add capability; they do not replace existing abstractions:

- **LayoutAST**: Still the intermediate representation between design and IR. Generators emit Items into it.
- **Templates**: Still valid for monolithic, pre-packaged designs. May internally use domains in future.
- **PML**: Still the human-authored design language. May gain domain syntax in future.

There is no migration deadline. Existing code continues to work indefinitely.

### 9.3 Optional Template Refactoring

Templates may optionally be rewritten to use domains internally. This is not required but demonstrates the model.

**Shaker door expressed with domains (conceptual):**

The Shaker door consists of:
- Outer profile (outside cut around perimeter)
- Frame (the stile/rail border)
- Panel pocket (recessed center area)

With domains:
1. Create outer domain from door dimensions
2. Create panel domain by insetting outer domain by stile/rail widths
3. Apply profile generator to outer domain (outside cut, through)
4. Apply flat pocket generator to panel domain (recess depth)

The result is equivalent to the current Shaker template but composed from primitives.

**Why this is optional:**
- Existing Shaker template works and is tested
- Rewriting adds risk without immediate benefit
- New designs should use domains; old designs can stay as-is

---

## 10. Development Stages

### Stage 0: Design Document (THIS DOCUMENT)
**Status:** In progress

**Deliverables:**
- [x] Architecture definition
- [x] Interface contracts
- [x] Data schemas
- [x] Stage enumeration
- [x] Error philosophy
- [x] Migration strategy

**Outputs:** `docs/domain_generator_design.md`

**Exit Criteria:** Document reviewed and approved

---

### Stage 1: Domain Type and Operations
**Status:** Not started

**Scope:**
- Create `domains/domain.py` with Domain and MultiDomain dataclasses
- Implement `inset()`, `offset()`, `subtract()`, `intersect()` operations (all return MultiDomain)
- Handle empty domain results (empty MultiDomain)
- Handle edge cases (self-intersection resolution, containment validation)
- Winding normalization on construction via `shapely.ops.orient()`
- Unit tests for all operations

**Inputs:**
- Polygon vertices (outer boundary)
- Optional inner boundary vertices
- Optional local origin and rotation

**Outputs:**
- Domain instances with computed properties (bounds, area, centroid)
- MultiDomain instances from operations

**Dependencies:**
- Shapely (`pip install shapely`) — geometry backend for boolean ops and offsets

**Test Coverage Required:**
- Construction from vertices (valid and invalid cases)
- Rectangular convenience constructor
- Each operation with simple cases
- Each operation with edge cases (empty result, no overlap, full containment)
- Inner boundary handling
- Serialization to/from JSON

**Exit Criteria:**
- All four operations implemented and tested
- Empty domain handling works correctly
- Invalid inputs raise clear exceptions
- JSON serialization round-trips correctly

---

### Stage 2: Coordinate Transforms
**Status:** Complete

**Scope:**
- Create `domains/transforms.py` with transform functions
- Implement domain-local to sheet-space transform
- Implement sheet-space to domain-local transform
- Support rotation and translation
- Unit tests for transform correctness

**Inputs:**
- Point or list of points
- Domain (for its local_origin and local_rotation)

**Outputs:**
- Transformed point or list of points

**Dependencies:** Stage 1 (needs Domain type)

**Test Coverage Required:**
- Identity transform (zero rotation, origin at 0,0)
- Translation only
- Rotation only
- Combined rotation and translation
- Round-trip preservation
- Batch transform (list of points)

**Exit Criteria:**
- Transforms work correctly for all cases
- Round-trip preserves coordinates within floating-point tolerance
- Rotated domains produce correctly oriented output

**Implementation Notes (2026-01-17):**

Files created:
- `domains/transforms.py` - Core transform functions
- `tests/test_transforms.py` - 33 comprehensive tests

Functions implemented:
- `local_to_sheet(point, domain)` - Transform point from domain-local to sheet space
- `sheet_to_local(point, domain)` - Transform point from sheet space to domain-local
- `local_to_sheet_batch(points, domain)` - Efficient batch transform (computes trig once)
- `sheet_to_local_batch(points, domain)` - Efficient batch inverse transform
- `transform_boundary(boundary, domain, to_sheet)` - Transform complete polygon boundaries
- `compose_transforms(point, from_domain, to_domain)` - Transform between two domain frames
- `get_rotation_between(from_domain, to_domain)` - Get rotation difference between domains
- `get_translation_between(from_domain, to_domain)` - Get translation vector between domain origins

Design decisions:
- Transform order: rotation first, then translation (inverse: translation first, then rotation)
- Fast path for zero rotation avoids unnecessary trig computation
- Round-trip precision verified to 1e-10 tolerance
- Batch functions accept both list and tuple input (always returns list)
- 2D only - depth is a separate generator concern, not a transform concern

Test coverage:
- All 34 tests pass covering identity, translation, rotation, combined transforms
- Explicit CCW-positive rotation direction contract test (`test_rotation_is_counter_clockwise_positive`)
- Round-trip preservation verified with various coordinate magnitudes
- Edge cases: very small rotation, full 360°, large coordinates, negative coordinates

---

### Stage 3: Generator Interface and First Generators
**Status:** Complete

**Scope:**
- Create `generators/base.py` with generator protocol definition
- Create `generators/area/flat.py` with FlatPocket generator
- Create `generators/loop/profile.py` with Profile generator
- Integrate with LayoutAST (generators emit Items)
- End-to-end test: Domain → Generator → AST → IR

**Inputs:**
- Domain instance
- Typed parameter object (FlatPocketParams, ProfileParams)

**Outputs:**
- List of LayoutAST Items

**Dependencies:** Stage 1, Stage 2

**Test Coverage Required:**
- FlatPocket on simple rectangular domain
- FlatPocket on domain with hole
- FlatPocket with various depths
- Profile on rectangular domain (all sides: outside, inside, on)
- Profile with tabs
- Generator on empty domain (should raise or return empty based on flag)
- Invalid parameters (should raise)
- Output Items convert to valid RemovalIntents

**Exit Criteria:**
- Generator protocol is defined and documented
- FlatPocket generator works for basic cases
- Profile generator works for basic cases
- Output integrates with existing AST → IR pipeline
- End-to-end test passes: Domain → Generator → AST → IR → validation

**Implementation Notes (2026-01-17):**

Files created:
- `generators/__init__.py` - Public exports for generator system
- `generators/base.py` - Generator protocol, parameter classes, utilities
- `generators/area/__init__.py` - Area generator package
- `generators/area/flat.py` - FlatPocket generator implementation
- `generators/loop/__init__.py` - Loop generator package
- `generators/loop/profile.py` - Profile generator implementation
- `tests/test_generators.py` - 35 comprehensive tests

Generator Protocol:
- `Generator` protocol defined with `__call__(domain, params, *, allow_empty)` signature
- Generators are pure functions, not classes - simpler and more composable
- All generators operate on Domain instances and return `list[Item]`
- `allow_empty=True` enables graceful handling of edge cases (too small, no matching loops)

Parameter Classes:
- `FlatPocketParams(depth_mm, allowance_mm)` - validates depth > 0, allowance >= 0
- `ProfileParams(side, depth, loop_selection, tab_count, tab_width_mm, tab_height_mm)`
  - side: "outside" | "inside" | "on"
  - depth: "through" | float
  - loop_selection: "outer_only" | "inner_only" | "all_loops" | list[int]

FlatPocket Generator:
- Produces Polygon Items with pocket feature
- Supports optional inward allowance (contracts domain before generating)
- Includes holes from domain inner_boundaries in geometry output
- Uses domain centroid for Item placement center

Profile Generator:
- Produces Polygon Items with profile feature
- Supports all three side options (outside, inside, on)
- Supports both "through" depth and numeric depths
- Supports tab configuration (count, width, height)
- Loop extraction implemented inline (Stage 4 scope absorbed here)
  - "outer_only": profiles outer boundary only
  - "inner_only": profiles inner boundaries (holes) only
  - "all_loops": profiles all boundaries
  - list[int]: profiles specific loop indices (0=outer, 1+=inner)

Design Decisions:
- Generators emit Polygon type Items (not Rect) to preserve exact domain geometry
- Shape IDs use format: "generated_<prefix>_<suffix>" for traceability
- Coordinate system strategy:
  - Boundary-emitting generators (FlatPocket, Profile) emit domain boundaries directly
    - Domain boundaries are already in sheet coordinates, so no transform needed
  - Pattern-computing generators (Wave, Grid in Stage 5) will use domain-local coordinates
    - Compute patterns in local coords, then transform to sheet using `local_to_sheet_batch()`
    - This ensures rotation-invariant pattern alignment
  - Transform utilities in `domains/transforms.py`: local_to_sheet, sheet_to_local, batch variants
- `allow_empty` parameter enables defensive programming patterns

Test Coverage:
- 35 tests covering all parameter validations
- FlatPocket: simple rect, with holes, various depths, allowance, edge cases
- Profile: all sides, numeric depth, tabs, all loop selection modes, edge cases
- End-to-end tests: Domain → Generator → AST → IR pipeline verified
- Determinism test: same inputs produce identical outputs across multiple runs

IR Integration:
- All generator output types are fully supported through the adapter pipeline:
  - `adapters/ast_to_removal.py`: Entry point for AST → RemovalIntent conversion
  - `adapters/hints_to_removal.py`: Internal geometry → bounds conversion (calls core/geometry.py)
  - `core/geometry.py`: compute_shape_bounds() handles all types:
    - Polygon: Bounds from points array
    - Line: Bounds from start/end points
    - Polyline: Bounds from points array
  - `adapters/hints_to_removal.py`: engrave_hint_to_removal_intent() handles engrave feature type
- All feature types (pocket, profile, engrave) convert to RemovalIntents correctly
- Bounds computed from geometry for RemovalIntent validation
- If conversion fails, a ValueError is raised (loud failure, no silent degradation)

---

### Stage 4: Loop Extraction
**Status:** Absorbed into Stage 3

**Note:** Loop extraction was implemented inline within the Profile generator (`generators/loop/profile.py::_extract_loops()`). This scope reduction was appropriate because:
1. Loop extraction is simple enough to be a local helper function
2. Only Profile generator currently needs loop selection
3. If reuse becomes necessary, the function can be extracted to `domains/loops.py`

**Implemented Functionality (in Stage 3):**
- All selection modes: `outer_only`, `inner_only`, `all_loops`, explicit index list
- Loop orientation inherited from Domain (already normalized via Shapely)
- Clear error messages for invalid indices
- Full test coverage in `tests/test_generators.py`

**Original Scope (now complete via Stage 3):**
- ~~Create `domains/loops.py` with loop extraction functions~~ (inline in profile.py)
- ~~Support selection modes~~ (implemented)
- ~~Handle loop orientation~~ (inherited from Domain normalization)
- ~~Unit tests for all selection modes~~ (in test_generators.py)

**Exit Criteria:** All met via Stage 3 implementation.

---

### Stage 5: Additional Generators
**Status:** Complete (2026-01-17)

**Scope:**
- Create `generators/area/wave.py` with Wave generator
- Create `generators/area/grid.py` with Grid generator
- Create `generators/loop/bead.py` with Bead generator
- Each generator has typed params and full test coverage

**Inputs:**
- Domain instance
- Generator-specific typed parameters

**Outputs:**
- List of LayoutAST Items

**Dependencies:** Stage 3 (generator interface), Stage 4 (loop extraction for Bead)

**Test Coverage Required:**
- Wave generator: amplitude, wavelength, phase, direction variations
- Wave generator: domain too small for parameters
- Grid generator: spacing, offset variations
- Grid generator: domain with holes (grid respects boundaries)
- Bead generator: all loop selection modes
- Bead generator: width and depth variations
- All generators: determinism (same input → same output)

**Exit Criteria:**
- Three additional generators implemented and tested ✓
- Each generator handles edge cases correctly ✓
- Each generator produces valid LayoutAST Items ✓
- Determinism verified ✓

**Implementation Notes (2026-01-17):**

Files Created:
- `generators/base.py`: Added WaveParams, GridParams, BeadParams (lines 229-374)
- `generators/area/wave.py`: Wave pattern generator (~260 lines)
- `generators/area/grid.py`: Grid pattern generator (~220 lines)
- `generators/loop/bead.py`: Bead loop generator (~210 lines)
- `tests/test_stage5_generators.py`: Comprehensive test suite (42 tests)

Parameter Classes:
- `WaveParams`: amplitude_mm, wavelength_mm, depth_mm, direction_rad, phase_rad, tool_width_mm, wave_count
- `GridParams`: spacing_x_mm, spacing_y_mm, line_width_mm, depth_mm, offset_x_mm, offset_y_mm
- `BeadParams`: width_mm, depth_mm, offset_mm, loop_selection

Generator Outputs:
- Wave: Polyline Items with "engrave" feature (multiple wave lines clipped to domain)
- Grid: Line Items with "engrave" feature (horizontal and vertical lines clipped to domain)
- Bead: Polygon Items with "engrave" feature (offset boundary paths)

Coordinate Strategy (as planned in Stage 3 notes):
- Wave and Grid compute patterns in domain-local coordinates
- Use `local_to_sheet_batch()` and `sheet_to_local()` from `domains/transforms.py`
- Ensures rotation-invariant pattern alignment
- Bead uses Shapely buffer() for offset, then clips to domain

Test Coverage (42 tests):
- WaveParams validation: 5 tests
- GridParams validation: 4 tests
- BeadParams validation: 4 tests
- Wave generator: 8 tests (simple, direction, phase, amplitude limits, allow_empty)
- Grid generator: 8 tests (simple, offset, different spacing, holes, spacing limits)
- Bead generator: 12 tests (all selection modes, offset limits, allow_empty)
- Determinism: 3 tests (one per generator)
- Integration: 3 tests (combined generators, border decoration, end-to-end AST)

---

### Stage 6: SVG as Generator Input
**Status:** Complete (2026-01-17)

**Scope:**
- Implement SVG path parsing (subset: lines, cubic beziers, arcs)
- Convert SVG paths to polylines (curve flattening)
- Enable area generators to use SVG-derived geometry as stamps/fills
- Unit tests for SVG parsing and conversion

**Inputs:**
- SVG path string or file
- Curve flattening tolerance

**Outputs:**
- List of polylines (each polyline is ordered list of points)

**Dependencies:** Stage 3 (generators need input mechanism)

**Test Coverage Required:**
- Simple path (lines only) ✓
- Path with cubic beziers (verify flattening) ✓
- Path with arcs (verify flattening) ✓
- Complex real-world SVG paths ✓
- Invalid SVG handling ✓

**Exit Criteria:**
- SVG paths parse correctly ✓
- Curves flatten to polylines with configurable tolerance ✓
- Generators can use SVG-derived geometry ✓
- Invalid SVG raises clear exceptions ✓

**Implementation Notes (2026-01-17, updated 2026-01-17):**

Files Created:
- `generators/svg/__init__.py` - Package with public exports
- `generators/svg/parser.py` - SVG path string parser (~450 lines)
- `generators/svg/curves.py` - Curve flattening algorithms (~320 lines)
- `generators/svg/params.py` - SVGPathParams dataclass
- `generators/svg/stamp.py` - svg_stamp_generator implementation (~250 lines)
- `tests/test_svg_parser.py` - Comprehensive test suite (50+ tests)

SVG Path Commands Supported:
- M/m: Move to (absolute/relative)
- L/l: Line to (absolute/relative)
- H/h: Horizontal line to (absolute/relative)
- V/v: Vertical line to (absolute/relative)
- C/c: Cubic Bezier curve (absolute/relative)
- S/s: Smooth cubic Bezier (absolute/relative)
- Q/q: Quadratic Bezier curve (absolute/relative)
- T/t: Smooth quadratic Bezier (absolute/relative)
- A/a: Elliptical arc (absolute/relative)
- Z/z: Close path

Curve Flattening Algorithms:
- Cubic Bezier: Adaptive de Casteljau subdivision with flatness testing
- Quadratic Bezier: Adaptive subdivision with control point distance test
- Elliptical Arc: Endpoint-to-center parameterization per SVG spec F.6.5, then angular sampling

Key Functions:
- `parse_svg_path(path_data, tolerance)` → list[Polyline]
- `flatten_cubic_bezier(p0, p1, p2, p3, tolerance)` → list[Point2D]
- `flatten_quadratic_bezier(p0, p1, p2, tolerance)` → list[Point2D]
- `flatten_arc(p0, rx, ry, x_rot, large_arc, sweep, p1, tolerance)` → list[Point2D]
- `svg_stamp_generator(domain, params)` → list[Item]

Parameter Classes:
- `SVGPathParams`: svg_path, depth_mm, tolerance, feature_type, scale_mode, svg_unit_mm, center, invert_y

Design Decisions:
- Tolerance parameter controls curve flattening quality (smaller = more points)
- SVG Y-axis inversion handled via invert_y parameter (default True for SVG convention)
- Scale modes: "fit" (uniform fit within domain), "fill" (uniform fill), "none" (use svg_unit_mm)
- `svg_unit_mm` parameter for scale_mode="none" converts SVG units to mm (default: 1.0)
- Generator produces Polygon Items for closed paths, Polyline Items for open paths
- Feature types: "engrave" (default), "pocket", "profile"
- Parser handles implicit commands (coordinates after M become implicit L)
- Robust tokenizer handles various whitespace, negative numbers, scientific notation

**Known Limitations:**
- **Fill rules not interpreted:** All closed paths are treated as solid polygons.
  Even-odd and nonzero fill rules are not parsed or applied.
- **Holes not supported:** Nested paths (like holes in letters 'O', 'A', 'D') are
  returned as separate polylines, not as polygon holes. Pre-process SVGs with
  holes to separate inner/outer contours before use.
- **No file-based loading in generators:** To maintain generator determinism (pure
  functions of domain + params), file I/O is not supported. Load SVG content at a
  higher layer (template or orchestration) and pass the path string via `svg_path`.
- **Units are abstract:** SVG coordinates are unitless. Use `scale_mode="fit"` or
  `"fill"` for automatic scaling, or `scale_mode="none"` with `svg_unit_mm` for
  explicit unit conversion (e.g., `svg_unit_mm=25.4/96` for 96 DPI pixels to mm).

Test Coverage (50+ tests):
- Curve flattening: 7 tests (cubic, quadratic, arc, tolerance validation)
- Basic path parsing: 7 tests (lines, closed paths, relative commands, H/V, multiple subpaths)
- Curve parsing: 5 tests (C, S, Q, T, A commands)
- Edge cases: 6 tests (empty, whitespace, negatives, scientific notation, invalid input)
- Polyline utilities: 5 tests (bounds, scale, translate, center, normalize)
- SVGPathParams: 8 tests (valid, full options, all validation errors including svg_unit_mm)
- svg_stamp_generator: 10 tests (simple, curved, pocket, profile, scale modes, determinism)
- Transform tests: 4 tests (Y-inversion, svg_unit_mm with scale_mode="none", transform order)
- Integration: 3 tests (AST integration, complex paths)

---

### Stage 7: Production Readiness
**Status:** Complete (2026-01-17)

**Scope:**
- Review and improve all error messages
- Performance testing on complex domains (many vertices, many holes)
- Performance optimization if needed
- Developer documentation (docstrings, usage examples in docs/)
- Integration examples showing domain/generator with existing pipeline

**Inputs:**
- Complete implementation from prior stages

**Outputs:**
- Production-quality code with documentation

**Dependencies:** All prior stages

**Test Coverage Required:**
- Performance benchmarks (establish baselines) ✓
- Stress tests (large domains, many generators) ✓
- Integration tests with full pipeline ✓

**Exit Criteria:**
- All error messages are actionable ✓
- Performance is acceptable for expected use cases (define thresholds) ✓
- Documentation is complete ✓
- Integration examples work end-to-end ✓

**Implementation Notes (2026-01-17):**

Files Created:
- `tests/test_performance.py` - Performance benchmarks and stress tests (~400 lines)
- `docs/examples/domain_generator_example.py` - Complete integration example (~500 lines)

Performance Benchmarks (`tests/test_performance.py`):
Established baselines and validation thresholds for all operations:

| Operation | Threshold | Actual Performance |
|-----------|-----------|-------------------|
| Rectangle construction | < 1ms | ~0.07ms |
| Polygon (100 vertices) | < 10ms | ~0.12ms |
| Domain with 10 holes | < 50ms | ~1.17ms |
| Inset operation | < 5ms | ~0.08ms |
| Subtract operation | < 5ms | ~0.12ms |
| Flat pocket generator | < 5ms | ~0.01ms |
| Profile generator | < 5ms | ~0.01ms |
| Wave generator | < 100ms | ~56ms |
| Grid generator | < 100ms | ~0.43ms |
| Full pipeline (Domain → AST → IR) | < 200ms | ~0.18ms |

Stress Tests:
Stress tests verify scalability and stability, not numeric precision. They confirm:
1. Operations complete without exception on large inputs
2. Results are non-empty where expected (area > 0, item count > 0)
3. No memory errors or timeouts on complex geometry

Specific tests:
- 1000-vertex polygon: Construction succeeds, inset produces non-empty result with vertices
- 25-hole domain: Construction succeeds, all holes preserved in result
- 10 chained inset operations: Each produces non-empty result until domain collapses
- Dense grid (5mm spacing on 500x500mm): Generates items, count > 0
- Fine wave (10mm wavelength, 2mm spacing): Generates items, count > 0

Note: Numeric correctness is validated separately in unit tests (test_domain.py,
test_generators.py) with tolerance assertions. Stress tests focus on "does not crash"
and "produces output" for edge-case inputs.

Integration Example (`docs/examples/domain_generator_example.py`):
Demonstrates four complete design workflows:
1. Simple Shaker Door - Profile + Pocket
2. Wave Panel - Profile + Wave pattern
3. Beaded Frame Door - Profile + Pocket + Bead decoration
4. Grid Panel - Profile + Grid pattern

Each example shows:
- Domain composition from scratch
- Generator invocation with typed parameters
- LayoutAST construction
- Conversion to RemovalIntent IR
- ASCII domain visualization for debugging

Error Message Quality:
Reviewed all error messages across the system. All follow the design doc philosophy:
- Include what operation failed
- Include what constraint was violated
- Include actual values
- Include acceptable values

Example: "WaveGenerator: amplitude 15mm exceeds half of minimum domain dimension 20mm. Maximum amplitude for this domain is 10mm."

Run Tests:
```bash
# Performance validation tests
source venv/bin/activate && PYTHONPATH=. python3 -m tests.test_performance

# Full benchmarks with stress tests
source venv/bin/activate && PYTHONPATH=. python3 -m tests.test_performance --full

# Integration example
source venv/bin/activate && PYTHONPATH=. python3 docs/examples/domain_generator_example.py
```

---

### Stage 8: Documentation Audit
**Status:** Complete (2026-01-17)

**Scope:**
- Review and update all mill_ui documentation to reflect domain/generator system
- Ensure documentation accurately describes the new architecture layer
- Add domain/generator patterns and guidance
- Create or update relevant recipes

**Files Updated:**

1. **[CLAUDE.md](../CLAUDE.md)** - AI development guide ✓
   - Added Domain/Generator section to "Mental Model: Compiler Analogy"
   - Added domain/generator to "Reading Order for New Context"
   - Added "Task 7: Create a Design with Domains and Generators" to Common Tasks
   - Added "Pattern 6: Create a New Generator" to Extension Patterns
   - Added "Pattern 7: Add a New Domain Operation" to Extension Patterns

2. **[README.md](../README.md)** - Project overview ✓
   - Added section "2.6 Domain/Generator System (Math-Based Composition)"
   - Added `domains/` and `generators/` to Directory Structure
   - Included pipeline diagram and usage example

3. **[FEATURES.md](../FEATURES.md)** - Feature tracker ✓
   - Added F006: Domain/Generator System (Math-Based Composition)
   - Documented implementation status, design decisions, test coverage
   - Added usage example and links to documentation

4. **[docs/WORKFLOW.md](WORKFLOW.md)** - Development workflow ✓
   - Added "Stage 1B: Domain/Generator Composition" pipeline stage
   - Added Domain/Generator to input format decision table

5. **[docs/recipes/README.md](recipes/README.md)** - Recipe index ✓
   - Added "Domain/Generator Recipes" section
   - Added reference to Recipe 19

6. **New recipe documentation:** ✓
   - Created `docs/recipes/19_domain_generator_basics/README.md`
   - Includes domain composition examples
   - Includes generator usage examples (profile, pocket, wave, grid, bead)
   - Shows end-to-end flow: Domain → Generator → AST → IR

**Checks Completed:**
- ✓ All new modules (`domains/`, `generators/`) documented
- ✓ Public API functions have docstrings (module __init__.py files have extensive docs)
- ✓ Architecture diagrams reflect new layer (README.md Section 2.6)
- ✓ Extension patterns documented (CLAUDE.md Patterns 6 and 7)
- ✓ Error handling patterns documented (CLAUDE.md, design doc Section 8)
- ✓ No stale references to "planned" features that are now implemented

**Exit Criteria Met:**
- ✓ All documentation reflects actual implementation
- ✓ New users can understand domain/generator system from docs
- ✓ AI agents (Claude, Codex) have clear guidance for working with domains/generators
- ✓ Recipe 19 demonstrates the new system

---

### Stage 9: Cabinet Door Primitives
**Status:** Not started

**Goal:** Extend the domain/generator system to cover traditional cabinet door styles for solid panel milling (MDF, plywood, glulam).

**Scope:**
- Domain split operations for multi-panel layouts
- Raised panel generator for traditional door styles
- Chamfer generator for presentation edges
- Partial-depth profile support

#### 9A: Domain Split Operations

Add methods to `Domain` class for dividing domains into sub-regions:

| Method | Signature | Purpose |
|--------|-----------|---------|
| `split_horizontal` | `(n: int, gap_mm: float = 0) -> MultiDomain` | Divide into n stacked rows |
| `split_vertical` | `(n: int, gap_mm: float = 0) -> MultiDomain` | Divide into n side-by-side columns |
| `split_grid` | `(rows: int, cols: int, gap_mm: float = 0) -> MultiDomain` | Divide into rows × cols grid |

**Implementation notes:**
- Uses Shapely for subdivision geometry
- Gap parameter creates space between resulting domains (for rails/stiles)
- Returns MultiDomain with domains ordered left-to-right, bottom-to-top
- Preserves parent's local_origin/local_rotation

**Example usage:**
```python
# 6-panel door
outer = Domain.from_rectangle(400, 600, center=(200, 300))
frame = outer.inset(50)  # Frame domain
panels = frame.domains[0].split_grid(3, 2, gap_mm=20)  # 3 rows, 2 cols, 20mm rails

for panel in panels.domains:
    items.extend(flat_pocket_generator(panel, FlatPocketParams(depth_mm=6.0)))
```

**Files:**
- `domains/domain.py` - Add split_horizontal, split_vertical, split_grid methods
- `tests/test_domain.py` - Add split operation tests

#### 9B: Raised Panel Generator

Create generator for traditional raised panel look (angled profile around panel perimeter).

**Parameters:**
```python
@dataclass(frozen=True)
class RaisedPanelParams(BaseParams):
    """Parameters for raised panel generator.

    Creates the traditional "raised panel" look by cutting angled profiles
    around the panel perimeter, leaving a raised center field.
    """
    border_width_mm: float      # Width of the angled border
    border_depth_mm: float      # Depth at outer edge of border
    field_depth_mm: float       # Depth of center field (shallower = more raised)
    angle_degrees: float = 15.0 # Angle of the bevel (typical: 10-20°)
```

**Output:** List of Items representing:
- Angled profile cuts around perimeter (the "raise")
- Optional center field pocket

**Implementation approach:**
- Generate inset domain for the field
- Create border domain via subtraction
- Emit profile items with depth gradient metadata
- CAM planner interprets as angled toolpath or V-bit operation

**Files:**
- `generators/base.py` - Add RaisedPanelParams
- `generators/area/raised_panel.py` - Implement raised_panel_generator
- `generators/__init__.py` - Export new generator and params
- `tests/test_stage9_generators.py` - Generator tests

#### 9C: Chamfer Generator

Create generator for edge bevels along domain boundaries.

**Parameters:**
```python
@dataclass(frozen=True)
class ChamferParams(BaseParams):
    """Parameters for chamfer generator.

    Creates angled edge cuts along domain boundaries for presentation edges.
    """
    width_mm: float             # Horizontal width of chamfer
    depth_mm: float             # Vertical depth of chamfer
    loop_selection: LoopSelection = "outer_only"
```

**Output:** Profile items with chamfer metadata (angle derived from width/depth ratio).

**Files:**
- `generators/base.py` - Add ChamferParams
- `generators/loop/chamfer.py` - Implement chamfer_generator
- `generators/__init__.py` - Export new generator and params
- `tests/test_stage9_generators.py` - Generator tests

#### 9D: Partial-Depth Profile Support

Extend `ProfileParams` to accept numeric depth values (not just "through").

**Current:**
```python
ProfileParams(side="outside", depth="through")
```

**Extended:**
```python
ProfileParams(side="outside", depth=10.0)  # 10mm deep dado/rabbet
ProfileParams(side="outside", depth="through")  # Still works
```

**Implementation:**
- Change `depth` field type from `Literal["through"]` to `Union[float, Literal["through"]]`
- Update profile_generator to handle numeric depths
- Update IR conversion to pass depth to RemovalIntent

**Files:**
- `generators/base.py` - Update ProfileParams
- `generators/loop/profile.py` - Handle numeric depth
- `adapters/ast_to_removal.py` - Pass depth through to IR
- `tests/test_generators.py` - Add partial-depth tests

#### 9E: Documentation and Recipes

**Documentation updates:**
- `README.md` - Add Stage 9 generators to domain/generator section
- `CLAUDE.md` - Add raised panel and chamfer to generator list
- `generators/__init__.py` - Update module docstring with new generators
- `FEATURES.md` - Update F006 with Stage 9 additions

**New recipe:**
- `docs/recipes/20_multi_panel_doors/README.md` - Multi-panel door examples
  - 2-panel door (split_horizontal)
  - 6-panel raised panel door (split_grid + raised_panel_generator)
  - Chamfered edge panel

**Example integration:**
- `docs/examples/cabinet_door_catalog.py` - Demonstrates full catalog generation

#### Exit Criteria

- [ ] `domain.split_horizontal(n)` works for n=2,3,4 with gap support
- [ ] `domain.split_vertical(n)` works for n=2,3,4 with gap support
- [ ] `domain.split_grid(rows, cols)` works for common configurations (2×2, 3×2, 2×3)
- [ ] `raised_panel_generator` produces valid Items
- [ ] `chamfer_generator` produces valid Items
- [ ] `ProfileParams(depth=10.0)` works for partial-depth profiles
- [ ] All new code has tests
- [ ] Recipe 20 demonstrates multi-panel doors
- [ ] Documentation updated

#### Test Plan

**Domain split tests:**
```python
def test_split_horizontal_2():
    """Split into 2 stacked panels."""
    domain = Domain.from_rectangle(100, 200, center=(50, 100))
    result = domain.split_horizontal(2)
    assert len(result.domains) == 2
    assert result.domains[0].bounds.height == pytest.approx(100)
    assert result.domains[1].bounds.height == pytest.approx(100)

def test_split_horizontal_with_gap():
    """Gap reduces panel sizes."""
    domain = Domain.from_rectangle(100, 200, center=(50, 100))
    result = domain.split_horizontal(2, gap_mm=20)
    assert len(result.domains) == 2
    # Each panel is (200 - 20) / 2 = 90mm tall
    assert result.domains[0].bounds.height == pytest.approx(90)

def test_split_grid_3x2():
    """6-panel layout."""
    domain = Domain.from_rectangle(200, 300, center=(100, 150))
    result = domain.split_grid(3, 2)  # 3 rows, 2 cols
    assert len(result.domains) == 6
```

**Generator tests:**
```python
def test_raised_panel_basic():
    """Raised panel generates items."""
    domain = Domain.from_rectangle(200, 300, center=(100, 150))
    items = raised_panel_generator(
        domain,
        RaisedPanelParams(
            border_width_mm=25.0,
            border_depth_mm=6.0,
            field_depth_mm=2.0,
        ),
    )
    assert len(items) > 0
    # Should have border profiles and field pocket

def test_chamfer_generator():
    """Chamfer generates profile items."""
    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    items = chamfer_generator(
        domain,
        ChamferParams(width_mm=3.0, depth_mm=3.0),
    )
    assert len(items) == 1  # One chamfer profile

def test_partial_depth_profile():
    """Profile with numeric depth."""
    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    items = profile_generator(
        domain,
        ProfileParams(side="outside", depth=10.0),
    )
    assert items[0].feature.depth == 10.0
```

#### Performance Targets

| Operation | Target |
|-----------|--------|
| split_horizontal(4) | < 5ms |
| split_grid(3, 2) | < 10ms |
| raised_panel_generator | < 10ms |
| chamfer_generator | < 5ms |

---

### Stage 10: Variable-Depth and V-Bit Toolpath Support (Future)
**Status:** Not started

**Goal:** Enable true variable-depth machining for bevel/chamfer features, moving from metadata-only representation to full CAM planner support.

**Background:**
Stage 9 implemented bevel and chamfer generators that emit Items with metadata describing the depth gradient. The current IR (`RemovalIntent`) treats these as flat pockets/profiles with semantic metadata - the CAM planner ignores the gradient information.

**Scope:**

#### 10A: RemovalIntent Depth Gradient Extension

Extend `RemovalIntent` to represent non-uniform depth:

```python
@dataclass(frozen=True)
class DepthProfile:
    """Describes depth variation across a region."""
    type: Literal["uniform", "linear_gradient", "radial_gradient"]
    z_outer: float  # Depth at outer boundary
    z_inner: float  # Depth at inner boundary (for gradients)
    transition_width_mm: float | None = None  # Width of gradient zone
    angle_deg: float | None = None  # Computed bevel angle

@dataclass(frozen=True)
class RemovalIntent:
    # ... existing fields ...
    depth_profile: DepthProfile | None = None  # New field for Stage 10
```

**Files:**
- `ir/removal_intent.py` - Add DepthProfile dataclass
- `adapters/ast_to_removal.py` - Convert bevel/chamfer metadata to DepthProfile
- `validation/removal_checks.py` - Add depth profile validation

#### 10B: V-Bit Toolpath Generation

Implement CAM planner support for V-bit and chamfer mill toolpaths:

| Tool Type | Use Case | Depth Control |
|-----------|----------|---------------|
| V-bit (90°) | Chamfers, bevels | Depth determines width |
| Chamfer mill | Precise chamfers | Fixed angle, variable depth |
| Ball-nose | Smooth transitions | Scallop-controlled passes |

**Implementation approach:**
1. Add tool type specification to RemovalIntent constraints
2. Implement V-bit path planning in CAM backend
3. Generate ramped/spiral entries for V-bit operations

**Files:**
- `ir/removal_intent.py` - Add tool_type to Constraints
- Backend CAM planner (outside this repo) - V-bit path planning

#### 10C: Depth Gradient Validation

Add IR-level validation for depth gradients:

```python
def check_depth_gradient_feasibility(
    intent: RemovalIntent,
    available_tools: list[Tool],
) -> ValidationResult:
    """Check if depth gradient can be achieved with available tools."""
    if intent.depth_profile is None:
        return ValidationResult.pass_()

    # Check angle achievable with available V-bits
    # Check depth range within tool capabilities
    # Warn if approximation required
```

#### Exit Criteria (Stage 10)
- [ ] `RemovalIntent` supports depth gradients
- [ ] V-bit toolpaths generated for chamfer features
- [ ] Raised panel bevels produce correct gradient toolpaths
- [ ] Validation catches infeasible angle/depth combinations

---

### Stage 11: Local-Coordinate Split Operations (Future)
**Status:** Not started

**Goal:** Enable split operations in domain-local coordinates for rotated panels.

**Background:**
Stage 9 split operations (`split_horizontal`, `split_vertical`, `split_grid`) operate in sheet-space coordinates. For a domain with `local_rotation_rad != 0`, splits are aligned to sheet X/Y axes, not the domain's local axes.

**Scope:**

#### 11A: Local Coordinate Transform

Add `local_coords` parameter to split operations:

```python
def split_horizontal(
    self,
    n: int,
    gap_mm: float = 0.0,
    local_coords: bool = False,  # New parameter
) -> MultiDomain:
    """Divide domain into n stacked rows.

    Args:
        local_coords: If True, split along domain's local Y-axis
            (perpendicular to local_rotation). If False (default),
            split along sheet Y-axis.
    """
    if local_coords and self.local_rotation_rad != 0:
        # Transform domain to local space
        # Perform split
        # Transform results back to sheet space
        pass
```

**Implementation approach:**
1. Apply inverse rotation to domain boundaries
2. Compute AABB in local space
3. Create split cells in local space
4. Rotate cells back to sheet space
5. Intersect with original domain

#### 11B: Rotated Panel Example

Demonstrate rotated panel splitting:

```python
# Diamond-oriented door panel
door = Domain.from_rectangle(400, 600, center=(200, 300), rotation_rad=math.pi/4)
panels = door.inset(50).domains[0].split_grid(2, 2, gap_mm=30, local_coords=True)
# Panels are diamond-shaped, aligned to door's rotated axes
```

#### Exit Criteria (Stage 11)
- [ ] `split_horizontal/vertical/grid` accept `local_coords` parameter
- [ ] Rotated domain splits produce correctly oriented panels
- [ ] Recipe demonstrates diamond-oriented panel layout

---

## 11. Success Metrics

### 11.1 Coverage

| Target | Metric |
|--------|--------|
| Domain operations | All four ops (inset, offset, subtract, intersect) implemented |
| Generator types | At least 2 area generators, 2 loop generators |
| Pipeline integration | End-to-end Domain → G-code demonstrated |
| Edge cases | Empty domains, invalid params, constraint violations all handled |

### 11.2 Quality

| Target | Metric |
|--------|--------|
| Determinism | 100% reproducible output (verified by repeated runs) |
| Error clarity | All failures include actionable messages |
| Test coverage | All public interfaces have unit tests |
| No silent failures | Zero cases of partial output without error |

### 11.3 Usability

| Target | Metric |
|--------|--------|
| Template coexistence | Existing templates unaffected (regression test) |
| Composition simplicity | Basic door expressible in <20 lines of domain/generator code |
| Documentation | Every public function has docstring; usage examples exist |

---

## 12. Open Questions

### 12.1 Resolved

| Question | Resolution |
|----------|------------|
| Domain geometry type | Simple polygons only; curves lowered to polylines early |
| Generator params | Typed, structured per generator (not flat dicts) |
| Coordinate frame | Domain-local including rotation; output transformed to sheet |
| Depth ownership | Generator-owned; domains may carry hints but generators must not rely on them |
| Loop selection | Caller-specified explicitly (outer_only, inner_only, all_loops, explicit list) |
| Error handling | Fail loudly by default; optional allow_empty; never silent partial |
| Migration | Coexist with templates; Domain is additive layer emitting LayoutAST Items |
| SVG scope | Generator input (paths → polylines), not domains; deeper integration later |
| Geometry backend | Shapely (GEOS bindings); float coords in mm; no integer scaling needed |
| Multi-region results | Operations return MultiDomain; callers iterate over resulting domains |
| Winding convention | CCW outer, CW holes; enforced by `shapely.ops.orient()` on construction |
| Precision | 0.01mm practical floor; double floats throughout; wood CNC tolerances relaxed |
| Buffer join style | Mitre (sharp corners) default for woodworking; round available for decorative |
| Derived domain origin | Inherit parent's local_origin/local_rotation; preserves pattern alignment |

### 12.2 Pending

| Question | Context |
|----------|---------|
| Curve support timeline | Polygons only for MVP; when to add arc/spline domains? |
| Domain visualization | Debugging aid—should domains render to SVG for inspection? |
| Performance thresholds | What is "acceptable" for complex domains? 100 vertices? 1000? |
| PML integration | When/how do domains appear in PML syntax? |
| Nesting integration | How do domains interact with the nesting system? |

---

## 13. Code Review Protocol

**Before implementing any fixes suggested in code review:**

1. **Discuss the feedback** — Understand the reviewer's concern fully. Ask clarifying questions if the issue is unclear.

2. **Evaluate alternatives** — The review suggestion may not be the optimal solution. Consider whether there are better approaches that address the underlying concern.

3. **Agree on approach** — Explicit alignment between implementer and reviewer before any code changes. Document the agreed approach if it differs from the original suggestion.

4. **Then implement** — Only after discussion and agreement, make the code changes.

**Rationale:** Review feedback is valuable input, but it is not directive. The implementer retains decision authority after informed discussion. This prevents:
- Blindly implementing suggestions that introduce new problems
- Churn from implementing then reverting reviewer suggestions
- Miscommunication about what the reviewer actually wanted

**Exception:** Trivial fixes (typos, obvious bugs, style inconsistencies) may be implemented without discussion.

---

## 14. Review Checklist

For each stage review, verify:

- [ ] All deliverables listed in stage scope are present
- [ ] All tests pass
- [ ] Output is deterministic (verified by repeated runs)
- [ ] No silent failures (all error paths raise or return empty with flag)
- [ ] Error messages are actionable (include what, why, actual values, acceptable values)
- [ ] Integrates with existing pipeline (AST → IR → validation)
- [ ] Code follows project conventions (frozen dataclasses, mm units, no global state)
- [ ] Public functions have docstrings
- [ ] JSON serialization works for relevant types
- [ ] **Design document reconciliation**: Review this document against implementation; update any descriptions, schemas, or contracts that diverged during implementation. Record changes in the stage's Implementation Notes.

---

## Appendix A: Conceptual Examples

These examples illustrate design intent, not implementation. They use natural language to describe what the system should enable.

### A.1 Simple Flat Panel

**Intent:** A 400×600mm panel with a 6mm pocket.

**Domain composition:**
- Create rectangular domain 400×600mm

**Generator application:**
- Apply flat pocket generator with depth 6mm

**Result:** One LayoutAST Item (pocket), which becomes one RemovalIntent.

### A.2 Shaker-Style Door

**Intent:** A door with frame and recessed panel.

**Domain composition:**
- Create outer domain from door dimensions (400×600mm)
- Create panel domain by insetting outer domain (50mm stiles, 50mm rails)

**Generator application:**
- Apply profile generator to outer domain (outside, through)
- Apply flat pocket generator to panel domain (6mm depth)

**Result:** Two LayoutAST Items (profile, pocket), which become two RemovalIntents.

### A.3 Decorated Border

**Intent:** A panel with wave pattern only in the border region.

**Domain composition:**
- Create outer domain from panel dimensions
- Create inner domain by insetting outer domain (border width)
- Create border domain by subtracting inner from outer

**Generator application:**
- Apply wave generator to border domain
- Apply flat pocket generator to inner domain

**Result:** Multiple LayoutAST Items (wave pattern elements, center pocket).

### A.4 Raised Medallion

**Intent:** Textured background with raised smooth center.

**Domain composition:**
- Create full panel domain
- Create medallion domain (ellipse or custom shape)
- Create background domain by subtracting medallion from panel

**Generator application:**
- Apply texture generator to background domain (e.g., 4mm depth)
- Apply flat pocket generator to medallion domain (2mm depth, shallower = raised)

**Result:** Textured surround with smooth raised center, achieved through domain subtraction and different depths.

### A.5 Six-Panel Door (Stage 9)

**Intent:** Traditional 6-panel door with frame and flat panel recesses.

**Domain composition:**
- Create outer domain from door dimensions (400×700mm)
- Create panel region by insetting outer domain (60mm frame)
- Split panel region into 3×2 grid with 25mm gaps (for rails/stiles)

**Generator application:**
- Apply profile generator to outer domain (outside, through)
- Apply flat pocket generator to each of the 6 panel domains (6mm depth)

**Result:** Seven LayoutAST Items (1 profile, 6 pockets), arranged in classic 6-panel layout.

### A.6 Raised Panel Door (Stage 9)

**Intent:** Single panel door with traditional raised panel (beveled edges, raised center).

**Domain composition:**
- Create outer domain from door dimensions (400×600mm)
- Create panel domain by insetting outer domain (50mm frame)

**Generator application:**
- Apply profile generator to outer domain (outside, through)
- Apply raised panel generator to panel domain (25mm border, 6mm border depth, 2mm field depth)

**Result:** Profile cut for door outline, plus raised panel geometry with angled border and raised center field.

### A.7 Chamfered Display Panel (Stage 9)

**Intent:** Decorative panel with beveled presentation edges.

**Domain composition:**
- Create rectangular domain for panel (300×400mm)

**Generator application:**
- Apply profile generator (outside, through) for cutout
- Apply chamfer generator (3mm width, 3mm depth) for presentation edge

**Result:** Panel with 45° chamfered edges suitable for display or cabinet facing.

---

**End of Document**
