# PML Parsing Invariants

**Applies to:** PML parser, syntax handling

---

## Invariants

| ID | Type | Invariant | Description |
|----|------|-----------|-------------|
| PM-1 | STRUCTURAL | DIMENSION_MM_SUFFIX | Accepts "NNNmm" format |
| PM-2 | STRUCTURAL | DIMENSION_BARE_NUMBER | Accepts bare numbers (int/float) |
| PM-3 | STRUCTURAL | THROUGH_SPECIAL | "through" is special depth value |
| PM-4 | HARD | SINGLE_TYPE_KEY | Each node mapping has exactly one key, its uppercase type key |
| PM-5 | HARD | FEATURE_REQUIRES_TYPE | Feature dict must have "type" key |
| PM-6 | POLICY | DEPTH_DEFAULT_THROUGH | depth defaults to "through" |
| PM-7 | HARD | KEEPOUT_NO_NESTING | Neither Keepout nor Island may contain either zone type; both require nonempty geometry-only children |
| PM-8 | HARD | INSET_REQUIRES_DISTANCE | Inset requires "distance" key |
| PM-9 | HARD | FRAME_REQUIRES_WIDTH | Frame requires "width" key |
| PM-10 | HARD | PROFILE_REQUIRES_SIDE | Profile requires "side" key |
| PM-11 | STRUCTURAL | PHYSICAL_OR_WORKING | Sheet uses physical or working dimensions |
| PM-12 | STRUCTURAL | CENTER_COORDS | at.x and at.y specify part CENTER |
| PM-13 | HARD | FACE_BACK_SCOPE | `face: back` valid only on pocket/hole/engrave with a finite depth |
| PM-14 | HARD | ISLAND_UNDER_POCKET_RECT | Island must be a direct child of a Rect with a pocket feature; unsupported placements raise |
| PM-15 | HARD | COMPONENT_BIND_BEFORE_PARSE | Bind each component use's arguments over its defaults before parsing parameterized body dimensions and counts. |
| PM-16 | HARD | COMPONENT_BINDING_ROUND_TRIP | Formatting preserves component templates, defaults and per-use arguments; reparsing recreates equal concrete instances. |
| PM-17 | HARD | ISLAND_SHAPE_PRESERVED | Island exclusion retains its resolved area geometry; nonrectangular islands lower to polygon pocket boundaries/holes instead of bounding-box exclusions. Curves conservatively approximate within 0.001mm before NC rounding. |
| PM-18 | HARD | CLOSED_KEY_SETS | Safety-critical parser contract: mappings admit only keys retained in the AST, NestJob or TemplateDef. Unknown or misplaced keys, standalone Feature nodes and unsupported parsed value shapes raise a parse error. |

---

## Dimension Formats

Both formats are valid:

```yaml
width: 100mm    # with suffix
width: 100      # bare number (interpreted as mm)
```

---

## Special Values

| Value | Meaning |
|-------|---------|
| `"through"` | Cut through entire material thickness |

---

## Node Structure

Each PML node mapping has exactly one key: the uppercase node type. All node options belong inside that mapping:

```yaml
# Correct
- Rect:
    at: {x: 100mm, y: 100mm, width: 100mm, height: 50mm}

# Wrong (multiple type keys)
- Rect: {}
  Circle: {}
```

---

## Closed Key Sets (PM-18)

Every parsed PML, nest and template mapping has a closed key set. Allowed
keys are those whose values reach the constructed AST, `NestJob` or
`TemplateDef`, under the syntax's default and override rules. Unknown or
misplaced keys raise `PMLParseError` (`NestParseError` for nest documents),
identifying the context, unknown keys, allowed keys and `(PM-18 violation)`.
Key checks precede required-key and value checks. The parser never guesses an
alias or silently ignores a typo.

Assembly keys are checked for the selected `box`, `carcass` or `cubby` type.
Options implemented only by another type raise even when their authored value
matches a default. The unimplemented PML `interfaces`, Assembly `children` and
Assembly `show_dimensions` fields are rejected. Shape joinery is configured with
the supported `top`, `bottom`, `back`, shelf or partition fields for that type.
Use `Sheet.show_dimensions` for sheet blueprint dimensions.

`Place.layout`, when supplied, must be a Grid configuration without children.
Place the content under `Place.children`; omit `layout` to use the parent region.
Other layout node types raise before resolution.

Alternate Sheet size keys must imply the same physical size on each axis.
`width` and `physical_width` specify physical width; `working_width` adds twice
the margin. Height follows the same rule. Equivalent declarations are accepted;
contradictory ones raise with the keys and implied sizes.

Assembly `dimensions` is a fallback list of one to three dimensions in width,
depth, height order. Explicit named dimensions override corresponding entries,
including zero; missing named dimensions use the list. Malformed lists and
invalid entries raise even when a named override is present. Duplicate
`back_thickness` and `back.thickness` must agree. Nonzero `back.inset` must match
an explicit `back_inset`; a zero joinery inset retains its existing meaning of
using the assembly setback. Existing downstream back-fit checks still apply.

Placement and size for Rect, RoundedRect and Ellipse belong in
`at: {x, y, width, height}`. Circle and Polygon accept only `x` and `y` in `at`;
their size comes from their shape parameters. Every supplied `at` requires
both `x` and `y`, including an empty mapping.

Line, Polyline and Spline accept `children` only as the single Feature-child
shorthand; geometric children are rejected because these nodes do not retain them.

A node that accepts a feature carries at most one: either `feature:` or one
Feature child. Extra Feature children, features on containers that discard them,
and generic `id`, `label` or `children` keys on nodes that do not retain them
raise. Standalone Feature nodes also raise at document roots, in component or
template bodies, as `AtPosition.child` and as `Place.layout`. A Feature must
attach to a shape; retaining it in a layout field cannot supply that attachment.
Parameterized component bodies are checked after binding, when instantiated.
An empty `feature: {}` raises under PM-5; empty `feeds: {}` remains valid.

A supplied `dogbone` accepts only a YAML boolean or a mapping of `style`,
`diameter` and `overcut`. Other scalar values, lists and explicit null raise
instead of selecting default relief. An omitted `dogbone` retains its existing
default behavior.

Assembly joinery values must be strings or mappings, and cubby `grid`
must be a two-element list. Nest template arguments must be declared by the
template; callers cannot supply the reserved `outer_w` or `outer_h` parameters.
Parameterized component bodies are checked when instantiated, preserving PM-15.

## Required Keys by Node Type

| Node Type | Required Keys |
|-----------|---------------|
| Feature | `type` |
| Inset | `distance` |
| Frame | `width` |
| Profile | `side` |

---

## Coordinate Semantics

`at.x` and `at.y` specify the CENTER of the part, not the corner.

```yaml
- Rect:
    at: {x: 100, y: 100, width: 50, height: 30}  # center at (100, 100)
# Actual bounds: x=[75, 125], y=[85, 115]
```

---

## Face Semantics

`Feature.face` (`front` / `back`, PM-13) selects the panel surface a feature is machined from. It is unrelated to `Feature.side` (`inside` / `outside`), which selects the offset side of a profile.

Beam primitives carry a separate `FaceFeature.face` (`assembly/beam.py`) naming a face of a beam blank. It selects which end of the lamination stack the feature depth counts inward from — `front` starts at layer 0, `back` at the last layer — and is consumed entirely by `BeamSpec.layers_reached`. It does not select a machining setup and must not be routed into the panel face mechanism; every item emitted from a beam feature carries `Feature.face == "front"`, because each layer panel lies flat on the sheet and is machined from one side.

---

## Reusable PML Components

These are reusable layout definitions, distinct from assembly members in
`components.md`. A definition containing parameter references keeps a
`ComponentTemplate` with its structured source. Each `UseComponent` becomes a
`ComponentInstance` pairing the original use with a separately parsed concrete
body. Binding happens at the PML boundary; the resolver receives typed dimensions
and counts and never imports the PML parser. Top-level instances remain
transparent to assembly sheet partitioning. During resolution, bound instances
and grouping Panels expand before a parent interprets its children. An Edge
treatment, Cell inset or Frame therefore has the same meaning directly or
through nested components, including list bodies. The original AST remains
unchanged for formatting. The inherited layout/domain context passes through
an instance to its concrete body.

Arguments override declared defaults for that use only. Nested uses receive
their own defaults and explicit arguments; callers forward values through
`args`. A whole-value `${name}` preserves the scalar's type, including bare
numeric counts and booleans. References embedded in text interpolate strings.
Substitution walks values in the loaded YAML tree, never serialized YAML, so a
string cannot inject nodes. Keys and arithmetic expressions are not substituted.
Parameter values must be concrete scalars; default-to-default references and
expression evaluation are not supported.

Unknown references, undeclared arguments, malformed references, non-mapping
parameter blocks, recursive uses and invalid bound dimensions/counts error
explicitly. A parameterized body is parsed and validated when instantiated.
Definitions and other instances are not mutated by binding or resolution.

The formatter emits an instance's original `UseComponent` and the definition's
template, defaults and arguments. Its concrete body is compiler-derived and is
recreated by parsing those inputs, rather than emitted as independent syntax.
Semantic AST equality and resolved machining intents survive this round trip.
External `Template:` files retain their existing separate loader contract.

## Sheet Dimensions

Sheet can specify either:
- `physical_width` / `physical_height` (total sheet size)
- `width` / `height` (legacy physical sheet dimensions)
- `working_width` / `working_height` (working dimensions; physical size adds twice the margin)

Working area = physical - 2*margin

---

## Invariant Types

| Type | Meaning |
|------|---------|
| HARD | Violation breaks the system |
| STRUCTURAL | Requires coordinated migration to change |
| POLICY | Current default, can change with care |
