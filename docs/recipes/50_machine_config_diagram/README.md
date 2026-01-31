# Recipe 50: Machine Config Diagram

This recipe demonstrates the machine configuration visualization system. It generates
SVG diagrams showing the CNC machine envelope, wasteboard, effective cutting area,
and key dimensions.

## Purpose

- Visualize CNC machine work envelope
- Show wasteboard placement and margins
- Display effective envelope (accounting for tool radius)
- Provide dimensional reference for job planning

## Usage

This recipe doesn't use PML files—it generates diagrams directly from machine configuration.

```bash
python -m cli.mill --recipe docs/recipes/50_machine_config_diagram
```

Or generate programmatically:

```python
from config.machine_loader import load_machine_by_name, load_endmills
from adapters.cnc_config_to_ir import machine_config_to_diagram_ir
from diagram_render import render_diagram_svg
from pathlib import Path

# Load machine and endmill
machine = load_machine_by_name("shapeoko_xxl")
endmills = load_endmills(Path("machines/endmills.yml"))
endmill = endmills[0]  # 1/4" upcut spiral

# Generate diagram
diagram = machine_config_to_diagram_ir(
    machine,
    endmill=endmill,
    show_dimensions=True,
    show_centerlines=True,
)

# Render to SVG
svg = render_diagram_svg(diagram, theme="dark")
Path("machine_diagram.svg").write_text(svg)
```

## Diagram Layers

The generated diagram includes these layers:

| Layer | Description |
|-------|-------------|
| `ENVELOPE` | Machine travel envelope (outer boundary) |
| `WASTEBOARD` | Wasteboard surface area |
| `EFFECTIVE_ENVELOPE` | Usable area after tool radius compensation |
| `ORIGIN_MARKER` | Machine origin (0,0) indicator |
| `CENTERLINES` | Envelope center reference lines |
| `DIMENSIONS` | Key measurements |

## Output Files

- `machine_diagram.svg` - Dark theme visualization
- `machine_diagram_print.svg` - Print-friendly theme

## Related

- [machines/README.md](../../../machines/README.md) - Machine config schema
- [config/machine_loader.py](../../../config/machine_loader.py) - Config loading
- [adapters/cnc_config_to_ir.py](../../../adapters/cnc_config_to_ir.py) - Diagram generation
