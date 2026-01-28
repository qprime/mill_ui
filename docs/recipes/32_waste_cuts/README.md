# Recipe: Waste Cuts Directive

**Status:** Production
**Difficulty:** Beginner
**Related:** [Profile with Tabs](../15_profile_with_tabs), [Nesting](../16_sheet_layout_nesting)

## Overview

This recipe demonstrates automatic waste decomposition using the `waste_cuts` directive. After cutting parts from a sheet, the remaining material is often an irregular polygon. The `waste_cuts` directive automatically identifies usable rectangular regions and generates profile cuts to separate them into clean, stackable pieces.

## Use Case

When cutting parts from a sheet:
- Leftover material is often irregular shapes
- Irregular waste requires manual trimming (table saw)
- Awkward shapes are hard to store and stack
- Usable material may be discarded due to inconvenient shapes

The `waste_cuts` directive solves this by:
1. Computing rectangular regions in the waste area
2. Filtering out pieces smaller than a minimum size
3. Generating profile cuts with tabs to separate them

## Basic Syntax

```pml
waste_cuts
    min_size <width>mm <height>mm
    margin <mm>
    tabs <count> height <height>mm
    strategy largest|simple
```

**Parameters:**
- `min_size`: Minimum dimensions for waste rectangles (default: 200mm × 200mm)
- `margin`: Holddown zone from sheet edges (default: 15mm)
- `tabs`: Required - tab configuration for waste cuts
- `strategy`: Decomposition algorithm (default: `largest`)
  - `largest`: Maximal rectangles - fewer, larger pieces
  - `simple`: Guillotine - recursive axis-aligned splits

## Examples

### Simple Panel with Waste Cuts

```pml
sheet 1200mm 800mm 19mm

rect panel at 400mm,400mm size 600mm,500mm
    profile outside through tabs 4 height 3mm

waste_cuts
    min_size 150mm 150mm
    margin 15mm
    tabs 4 height 3mm
    strategy largest
```

This creates a 600×500mm panel and decomposes remaining material into rectangles at least 150×150mm.

### Strategy Comparison

The `largest` strategy produces fewer, larger rectangles:
```pml
waste_cuts
    min_size 100mm 100mm
    margin 15mm
    tabs 4 height 3mm
    strategy largest
```

The `simple` strategy uses guillotine decomposition:
```pml
waste_cuts
    min_size 100mm 100mm
    margin 15mm
    tabs 4 height 3mm
    strategy simple
```

## How It Works

### Pipeline Flow

```
PML → Parse waste_cuts → Resolve layout → Compute waste rects → Inject synthetic rects → Normal pipeline
```

1. **Parser** ([pml/yaml_parser.py](../../../pml/yaml_parser.py)): Parses `WasteCuts` block into `WasteCuts` AST node
2. **Resolver** ([resolution/layout_resolver.py](../../../resolution/layout_resolver.py)): After resolving all parts, computes waste rectangles and injects them as synthetic `Item` nodes
3. **Algorithm** ([nesting/waste_decomposition.py](../../../nesting/waste_decomposition.py)): Implements both maximal rectangles and guillotine algorithms

### Ordering

Waste cuts are appended after all part definitions, ensuring they run last in the profile pass. This keeps parts fixtured until they are removed.

## Algorithm Details

### Maximal Rectangles (`strategy largest`)

1. Start with sheet bounds minus margin
2. For each part, split overlapping free rectangles
3. Prune rectangles fully contained within others
4. Filter by minimum size

Produces fewer, larger pieces - better for material reuse.

### Guillotine (`strategy simple`)

1. Start with sheet bounds minus margin
2. For each blocking part, recursively split the space
3. Continue until all regions are either free or below minimum size

Simpler algorithm with predictable axis-aligned cuts.

## Output

Waste rectangles appear as standard profile items in the G-code output. They have generated IDs like `waste_0`, `waste_1`, etc.

In the SVG blueprint, waste cuts are rendered alongside part profiles.
