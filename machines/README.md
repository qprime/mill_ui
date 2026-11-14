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
  safe_z_mm: 5.0              # Retract height above the stock top; a PML Sheet safe_z overrides it
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
    purpose: general          # general | profile | pocket | surface; defaults to general
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

### AltMill recipe tooling

Recipes default to a 9.525mm (3/8-inch) profile cutter. These are modeled planning
tools, authorized for recipe comparisons, rather than a claim about a verified
make/model in the shop. The assumed spindle is a 1.5kW-class AltMill spindle;
its actual power and the user's exact cutters have not been supplied.

| Operation | Modeled cutter | Edges | RPM | Feed mm/min | Plunge mm/min | Stepdown mm | Stepover |
|---|---|---:|---:|---:|---:|---:|---:|
| Profile | 3/8 carbide mortise compression | 2 | 18,000 | 4,500 | 1,125 | 6 | 40% |
| Pocket / relief roughing | 3/8 PCD straight-plunge | 1 | 18,000 | 2,520 | 630 | 6 | 40% |

The compression model assumes an upcut section shorter than the initial cut
depth. The PCD model assumes a plunge-capable straight cutter, using Amana's
DRB-422 family as a reference; an actual non-plunging PCD cutter requires a
different entry strategy. Cutting diameter is modeled as exactly 9.525mm, with
25.4mm flute length and shank diameter 9.525mm. Confirm those dimensions and
entry capabilities against the actual cutter before using these modeled programs
on the machine. No coating-based speed multiplier is applied.

Dedicated tools participate only in automatic selection for their declared
purpose. Pocket selection tries a dedicated pocket cutter first, retaining
smaller general-purpose cutters where the geometry requires them. A diameter tie
in profile selection favors a dedicated profile cutter. Surface cutters cannot
be selected automatically for holes. Explicit named tools retain their existing
behavior. The library's later equal-diameter hole entry remains the tie-break,
preserving its longer-reach plunge tools.

Legacy detail tools also have updated MDF planning feeds: 1/8-inch upcut at
2,160mm/min and 2mm stepdown, 1/4-inch upcut at 3,600mm/min, 1mm engraving at
1,200mm/min, V-bits at 1,800mm/min, and the small ball-nose finish cutter at
1,800mm/min. Fine relief stepover and engraving depth are preserved. Existing
surfacing parameters remain unchanged. Dedicated main-tool entries cover MDF and
plywood; these are not automatic recommendations for other materials.

The profile values are a deliberately reduced engineering estimate relative to
[Centurion's two-flute compression chart](https://www.centuriontools.com/pages/cutting-chart),
with shallower passes than its one-diameter reference. The PCD feed is close to
the 100 IPM MDF reference at 18,000 RPM in
[Amana's PCD plunge chart](https://www.amanatool.com/pub/media/productattachments/PCD-Down-Shear-Straight-Plunge-Speed-Chart-v4.pdf).
Feed is computed as RPM × cutting edges × chipload; plunge rates are separate
planning choices. The selected rates are below the motion limits in
[Sienci's AltMill specifications](https://resources.sienci.com/view/am-about-your-altmill/).
Those limits do not establish a safe material-removal rate or spindle capability.

Recipe comparisons retain the existing rapid-rate estimator, safe-Z policy and
spindle dwell. Estimated times exclude acceleration, manual tool changes,
stock handling and physical cutting trials. See
[recipe timing evidence](../docs/evidence/altmill_recipe_tooling/timings.csv)
for every recipe's captured baseline and revised estimate.

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
