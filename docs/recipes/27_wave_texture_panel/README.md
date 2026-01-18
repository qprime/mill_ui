# Recipe 27: Wave Texture Panel

**Status:** Draft
**Difficulty:** Intermediate
**Demonstrates:** Sinusoidal groove generation with buffered polygons

## Overview

This recipe creates a 300x300mm panel with five parallel wave grooves.
Each groove follows a sine curve (10mm amplitude, 60mm wavelength) and is
buffered to a 3mm width before being pocketed to 2mm depth.

If numpy is available, the wave is sampled using numpy arrays; otherwise a
pure Python fallback is used.

## Output

Running the example writes these files to `output/`:
- `ast.json`
- `intents.json`
- `preview.svg`

## Run

```bash
PYTHONPATH=. python docs/recipes/27_wave_texture_panel/example.py
```
