# PML (Panel Machining Language) Syntax Specification

PML is a human-readable declarative language for defining CNC machining layouts. It compiles to LayoutAST.

## Design Principles

- **Declarative**: No control flow, no execution, pure data
- **Human-friendly**: Natural indentation, minimal punctuation
- **Dimension-explicit**: All dimensions use `mm` suffix for clarity
- **Type-safe**: Shape types, feature types, and parameters are explicit

## Syntax Overview

```pml
# This is a comment

sheet 400mm 600mm 19mm

# Shapes: type identifier at x,y with features
rect door:outer at 200mm,300mm size 400mm,600mm profile through outside
rect door:panel at 200mm,300mm size 300mm,500mm pocket 6mm

circle hole:1 at 50mm,50mm diameter 10mm hole 8mm

# Templates (future extension)
template Shaker door:shaker params {
  outer_w: 400.0
  outer_h: 600.0
  stile_w: 50.0
  rail_h: 50.0
  panel_recess: 6.0
}
```

## Grammar

### Sheet Declaration

```
sheet <width>mm <height>mm <thickness>mm
```

Example:
```pml
sheet 450mm 650mm 19mm
```

### Shape Declarations

#### Rectangle

```
rect <id> at <x>mm,<y>mm size <w>mm,<h>mm <feature>
```

Example:
```pml
rect outer at 100mm,200mm size 80mm,120mm profile through outside
rect panel at 100mm,200mm size 60mm,100mm pocket 5mm
```

#### Circle

```
circle <id> at <x>mm,<y>mm diameter <d>mm <feature>
circle <id> at <x>mm,<y>mm radius <r>mm <feature>
```

Example:
```pml
circle hole1 at 50mm,50mm diameter 10mm hole 8mm
circle hole2 at 150mm,50mm radius 6mm hole through
```

#### RoundedRect

```
roundedrect <id> at <x>mm,<y>mm size <w>mm,<h>mm radius <r>mm <feature>
```

Example:
```pml
roundedrect panel at 100mm,100mm size 80mm,60mm radius 5mm pocket 4mm
```

### Features

#### Profile (cut outline)

```
profile through [inside|outside|on] [tabs <count> height <height>mm [width <width>mm]]
profile <depth>mm [inside|outside|on] [tabs <count> height <height>mm [width <width>mm]]
```

**Optional tabs** (holding bridges during cutting):
- `tabs <count>`: Number of tabs (positive integer)
- `height <height>mm`: Tab height (material left uncut)
- `width <width>mm`: Tab width along boundary (optional, defaults to 2× tool diameter, minimum 6mm)

Example:
```pml
profile through outside
profile 10mm inside
profile through outside tabs 4 height 3mm width 12mm
profile 6mm inside tabs 6 height 2mm
```

#### Pocket (recessed area)

```
pocket <depth>mm [corner_cleanup <diameter>mm]
pocket through [corner_cleanup <diameter>mm]
```

**Optional corner_cleanup** (multi-tool workflow for square corners):
- `corner_cleanup <diameter>mm`: Tool diameter for corner finishing pass
- Enables two-tool strategy: large tool for roughing, small tool specified here for corners
- Small tool must be smaller than primary tool to reach into corners

Example:
```pml
pocket 5mm
pocket through
pocket 6mm corner_cleanup 3.175mm
```

#### Hole (circular bore)

```
hole <depth>mm
hole through
```

Example:
```pml
hole 12mm
hole through
```

#### Engrave (surface decoration)

```
engrave <depth>mm
```

Example:
```pml
engrave 0.5mm
```

### Template Invocation (Phase 2)

```
template <TemplateName> <id> params {
  <param_name>: <value>
  ...
}
```

Example:
```pml
template Shaker door:main params {
  outer_w: 400.0
  outer_h: 600.0
  stile_w: 50.0
  rail_h: 50.0
  panel_recess: 6.0
}
```

### Metadata (Optional)

```
project <name>
kerf <width>mm
```

Example:
```pml
project cabinet_door_001
kerf 0.2mm
```

## Comments

```pml
# Single-line comment (entire line only)
```

## Whitespace

- Indentation is insignificant (but recommended for readability)
- Blank lines are ignored
- Each declaration is a single logical line

## Canonical Formatting

When PML is emitted from LayoutAST (format_pml), the system produces:

1. Sheet declaration first
2. Optional metadata (project, kerf)
3. Items in order (shapes, then templates)
4. 2 decimal places for dimensions
5. Consistent spacing

## Example: Complete Layout

```pml
# Shaker cabinet door with anchor holes
project shaker_door_v1
kerf 0.15mm

sheet 450mm 650mm 19mm

rect door:outer at 225mm,325mm size 400mm,600mm profile through outside
rect door:panel at 225mm,325mm size 300mm,500mm pocket 6mm

circle door:anchor:1 at 95mm,545mm diameter 10mm hole 8mm
circle door:anchor:2 at 355mm,545mm diameter 10mm hole 8mm
circle door:anchor:3 at 95mm,105mm diameter 10mm hole 8mm
circle door:anchor:4 at 355mm,105mm diameter 10mm hole 8mm
```

## Compilation to LayoutAST

PML compiles directly to LayoutAST:

- `sheet` → Sheet(width_mm, height_mm, thickness_mm)
- `rect`/`circle`/`roundedrect` → Item(kind="shape", ...)
- `template` → Item(kind="template", ...)
- Feature syntax → Feature(type, depth, side, depth_mm)
- `project` → LayoutAST.project
- `kerf` → LayoutAST.kerf_width_mm

## Semantic Equivalence

PML → AST → PML produces canonical formatting, not original formatting:

- Comments are lost
- Whitespace is normalized
- Item ordering may be canonicalized (shapes before templates)
- Dimension precision normalized to 2 decimal places
- Geometry representation may differ (radius vs diameter)

This preserves **semantic equivalence** while losing **surface formatting**.
