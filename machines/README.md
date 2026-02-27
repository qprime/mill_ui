# Machine Configuration

This directory contains configuration files for CNC machines, endmills, and spindles.

## Directory Structure

```
machines/
├── README.md           # This file
├── endmills.yml        # Endmill/bit library
├── spindles.yml        # Spindle specifications
└── cnc/                # CNC machine definitions
    ├── altmill_4x4.yml
    └── genmitsu_4040_pro.yml
```

## CNC Machine Schema

Machine configuration files define the physical envelope and spoilboard of a CNC router.

### Schema

```yaml
name: "Machine Name"           # Human-readable machine name

envelope:                      # Machine travel envelope (mm)
  x_min: 0                     # Minimum X position
  x_max: 800                   # Maximum X position
  y_min: 0                     # Minimum Y position
  y_max: 800                   # Maximum Y position

spoilboard:                    # Optional: spoilboard dimensions
  width_mm: 750                # Spoilboard width
  height_mm: 750               # Spoilboard height
  offset_x: 25                 # X offset from envelope origin
  offset_y: 25                 # Y offset from envelope origin

defaults:                      # Optional: default machining parameters
  safe_z_mm: 5.0              # Safe retract height
  feed_rate_mm_min: 1500      # Default XY feed rate
  plunge_rate_mm_min: 500     # Default Z plunge rate
```

### Coordinate System

All dimensions use millimeters (mm). The coordinate system follows the project convention:
- X axis: Left ↔ Right
- Y axis: Front ↔ Back
- Origin (0,0) is at the front-left corner of the envelope

### Derived Calculations

The machine loader computes:
- **Envelope dimensions**: `envelope_width = x_max - x_min`
- **Margins**: Distance from envelope edge to spoilboard edge
- **Effective envelope**: Envelope inset by tool radius (for clearance)
- **Center positions**: Geometric center of envelope and spoilboard

### Invariants

Machine configs are validated against these invariants:

| ID | Rule |
|----|------|
| `MCH_ENVELOPE_POSITIVE` | `envelope_x_max > envelope_x_min`, same for Y |
| `MCH_SPOILBOARD_FITS` | Spoilboard bounds ≤ envelope bounds |
| `MCH_EFFECTIVE_ENVELOPE_SHRINKS` | Effective envelope ≤ envelope (inset by bit radius) |

## Endmill Schema

The endmill library defines available cutting tools.

### Schema

```yaml
endmills:
  - name: "1/4 upcut spiral"   # Human-readable name
    diameter_mm: 6.35          # Cutting diameter
    flute_length_mm: 25.4      # Length of cutting flutes
    shank_diameter_mm: 6.35    # Shank diameter
    flutes: 2                  # Number of flutes
    type: upcut_spiral         # Tool type (see below)
    v_angle_deg: 60            # Optional: V-bit angle (for v_bit type)
```

### Tool Types

- `upcut_spiral` - Upcut spiral bit (good chip evacuation)
- `downcut_spiral` - Downcut spiral bit (clean top surface)
- `compression` - Compression bit (clean top and bottom)
- `straight` - Straight flute bit
- `v_bit` - V-carving bit (requires `v_angle_deg`)
- `engraving` - Fine engraving bit

### Invariants

| ID | Rule |
|----|------|
| `MCH_ENDMILL_POSITIVE` | `diameter_mm > 0`, `flute_length_mm > 0` |

## Spindle Schema

Spindle specifications define RPM ranges.

### Schema

```yaml
spindles:
  - name: "Dewalt DWP611"      # Spindle model name
    rpm_min: 16000             # Minimum RPM
    rpm_max: 27000             # Maximum RPM
```

### Invariants

| ID | Rule |
|----|------|
| `MCH_SPINDLE_RPM_ORDERED` | `rpm_min < rpm_max` |

## Usage

### Loading Configurations

```python
from config.machine_loader import (
    load_cnc_machine,
    load_endmills,
    load_spindles,
    load_machine_by_name,
    list_available_machines,
)
from pathlib import Path

# Load by path
machine = load_cnc_machine(Path("machines/cnc/altmill_4x4.yml"))

# Load by name (searches machines/cnc/ directory)
machine = load_machine_by_name("altmill_4x4")

# List available machines
print(list_available_machines())  # ['altmill_4x4', 'genmitsu_4040_pro']

# Load tool libraries
endmills = load_endmills(Path("machines/endmills.yml"))
spindles = load_spindles(Path("machines/spindles.yml"))
```

### Generating Machine Diagrams

```python
from adapters.cnc_config_to_ir import machine_config_to_diagram_ir
from diagram_render import render_diagram_svg

# Create diagram IR
diagram = machine_config_to_diagram_ir(
    machine,
    endmill=endmills[0],        # Optional: show effective envelope
    show_dimensions=True,
    show_centerlines=True,
)

# Render to SVG
svg = render_diagram_svg(diagram, theme="dark")
```

### Validating Job Bounds

```python
from validation.machine_checks import check_job_fits_machine
from ir.removal_intent import Bounds2D

job_bounds = Bounds2D(x_min=50, x_max=700, y_min=50, y_max=700)
result = check_job_fits_machine(job_bounds, machine, endmill)

if result.status.value == "fail":
    print("Job exceeds machine bounds!")
    for failure in result.failures:
        print(f"  - {failure}")
```

### Pipeline Integration

```python
from cam.pipeline import run_pipeline

result = run_pipeline(
    ast,
    machine_config=machine,
    endmill=endmill,
    validate_machine_bounds=True,  # Default: True
)

# Errors include machine bound violations
for error in result.errors:
    print(error)
```

## Adding New Machines

1. Create a new YAML file in `machines/cnc/`:
   ```yaml
   name: "My Custom CNC"

   envelope:
     x_min: 0
     x_max: 1000
     y_min: 0
     y_max: 1000

   spoilboard:
     width_mm: 950
     height_mm: 950
     offset_x: 25
     offset_y: 25

   defaults:
     safe_z_mm: 10.0
     feed_rate_mm_min: 2000
     plunge_rate_mm_min: 600
   ```

2. Test loading:
   ```python
   machine = load_machine_by_name("my_custom_cnc")
   print(f"Loaded: {machine.machine.name}")
   ```

3. Validate:
   ```python
   from validation.machine_checks import validate_machine_config

   results = validate_machine_config(machine)
   for r in results:
       print(f"{r.id}: {r.status.value}")
   ```
