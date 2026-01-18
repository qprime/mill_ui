# Recipe 30: Cathedral Arch Door

**Status:** Draft
**Difficulty:** Intermediate
**Demonstrates:** Domain.from_polygon with arc approximation, raised panel inset

## Overview

This recipe builds a 500x800mm door with a semicircular arch (radius 250mm)
using a polygon approximation. The panel region is inset by 60mm and receives
a raised panel treatment.

## Output

Running the example writes these files to `output/`:
- `ast.json`
- `intents.json`
- `preview.svg`

## Run

```bash
PYTHONPATH=. python docs/recipes/30_cathedral_arch_door/example.py
```
