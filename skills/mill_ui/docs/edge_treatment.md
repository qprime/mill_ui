# Edge Treatment Intent (Stage 18)

This document describes edge treatment semantics for profiles and pockets.

## Overview

**Edge** nodes specify edge treatment intent for finished edges, supporting:
1. **Allowance semantics** - Multi-pass rough/finish operations
2. **Decorative edges** - Fillet/chamfer hints for specialized toolpaths

Edge treatments influence RemovalIntent constraints/annotations for downstream toolpath planning.

## PML Syntax

```pml
edge allowance <rough_mm> <finish_mm> [id]
edge fillet <radius_mm> [id]
edge chamfer <distance_mm> [id]
```

## Examples

### Multi-Pass Allowance

```pml
sheet 400.00mm 400.00mm 19.00mm

rect panel profile through outside
    edge allowance 0.50mm 0.10mm
```

Creates a profile with:
- Rough pass leaving 0.5mm stock
- Finish pass leaving final 0.1mm allowance

### Decorative Fillet

```pml
sheet 400.00mm 400.00mm 19.00mm

rect panel profile through outside
    edge fillet 3.00mm
```

Specifies fillet intent (3mm radius) for finish toolpath.

### Chamfer

```pml
sheet 400.00mm 400.00mm 19.00mm

rect panel profile through outside
    edge chamfer 2.50mm
```

Specifies chamfer intent (2.5mm distance).

## Resolution Behavior

1. **Edge nodes are extracted** from shape children during resolution
2. **Edge treatment stored** in Item geometry data as `edge_treatment` dict
3. **Not emitted as separate items** (metadata only)

## Integration with RemovalIntent

Edge treatment automatically propagates to RemovalIntent via `item_to_removal_intent()`:

```python
from skills.mill_ui.v2.adapters.hints_to_removal import item_to_removal_intent

# Convert Item with edge treatment to RemovalIntent
removal = item_to_removal_intent(profile_item)

# Edge treatment in constraints
if removal.constraints.edge_treatment:
    if removal.constraints.edge_treatment.type == "allowance":
        rough = removal.constraints.edge_treatment.rough_allowance_mm
        finish = removal.constraints.edge_treatment.finish_allowance_mm
    elif removal.constraints.edge_treatment.type == "fillet":
        radius = removal.constraints.edge_treatment.radius_mm
```

### Multi-Tool Workflow (Rough + Finish Pass)

Edge allowance semantics enable multi-pass operations with different tools/strategies:

```python
# Given a profile with edge allowance
pml = """
rect panel profile through outside
    edge allowance 0.50mm 0.10mm
"""

# Parse and convert to RemovalIntent
removal = item_to_removal_intent(profile_item)

# Extract allowances for multi-pass planning
edge = removal.constraints.edge_treatment
rough_allowance = edge.rough_allowance_mm  # 0.5mm
finish_allowance = edge.finish_allowance_mm  # 0.1mm

# A multi-pass planner would generate two operations:
# 1. Rough pass: Cut to nominal boundary + rough_allowance offset (leaves 0.5mm stock)
#    - Use larger, faster tool (e.g., 6mm endmill)
#    - Optimize for rapid material removal
#
# 2. Finish pass: Cut to nominal boundary + finish_allowance offset (leaves 0.1mm final)
#    - Use smaller, precision tool (e.g., 3mm endmill)
#    - Optimize for surface finish and accuracy

# The RemovalIntent captures the intent; downstream toolpath planners
# implement the multi-pass strategy based on available tools and preferences.
```

**Key insight**: Edge allowances are *hints* for multi-tool sequencing, not rigid constraints. A planner may choose to:
- Generate 2 passes (rough + finish) with different tools
- Generate a single pass if only one tool is available
- Adjust allowances based on tool capabilities

### Kerf Compatibility

Edge treatment allowances are **per-edge intent**, distinct from **global kerf compensation**:

```python
from skills.mill_ui.v2.ir.removal_intent import RemovalIntent, Allowance, Constraints, EdgeTreatment

# Edge treatment: Per-edge finish strategy (multi-pass intent)
edge_treatment = EdgeTreatment(
    type="allowance",
    rough_allowance_mm=0.5,  # Per-edge: rough pass stock
    finish_allowance_mm=0.1  # Per-edge: finish pass stock
)

# Kerf compensation: Global tool property (compensates for tool width)
tool_kerf_mm = 3.175  # 1/8" endmill diameter
kerf_offset = tool_kerf_mm / 2.0  # 1.5875mm radius offset

# Both coexist in RemovalIntent
removal = RemovalIntent(
    region_id="profile_panel",
    bounds=bounds,
    z_top=0.0,
    z_bottom=-19.0,
    allowance=Allowance(outside=0.0, kerf_compensation=kerf_offset),  # Global kerf
    constraints=Constraints(edge_treatment=edge_treatment),  # Per-edge intent
    metadata={}
)

# A toolpath planner applies BOTH offsets:
# - Total rough offset = kerf_offset + rough_allowance_mm = 1.5875 + 0.5 = 2.0875mm
# - Total finish offset = kerf_offset + finish_allowance_mm = 1.5875 + 0.1 = 1.6875mm
#
# This separation allows:
# 1. Kerf to vary by tool selection (different diameter tools)
# 2. Edge allowances to remain constant (intent, not tool-dependent)
```

**Why separate?**
- **Kerf compensation** (`allowance.kerf_compensation`): Tool-dependent, global to the operation, compensates for tool radius
- **Edge allowances** (`constraints.edge_treatment`): Tool-independent, per-edge intent, describes multi-pass strategy

This design allows a planner to:
1. Choose different tools for rough/finish passes (each with different kerf)
2. Apply the same edge treatment intent regardless of tool selection
3. Combine both offsets additively for final toolpath geometry

## Constraints

### Supported Features

- **Edge with profile/pocket**: Primary use case
- **Allowance**: Rough/finish multi-pass semantics
- **Fillet**: Decorative rounded edges
- **Chamfer**: Decorative beveled edges
- **Per-edge treatment**: Compatible with kerf (not global)

### Limitations

- **Single edge per shape**: Only one Edge node per shape currently
- **Intent only**: Toolpath strategy not yet implemented (annotations only)
- **No validation**: Minimum tool clearance not yet enforced

## Testing

See `v2/tests/test_edge_intent.py` for acceptance tests covering:
- Edge allowance influences RemovalIntent
- Profile with fillet hint
- Chamfer treatment
- Round-trip preservation
- Pocket with edge treatment
- **Multi-tool scenario**: Rough + finish pass workflow (validates allowances enable multi-pass planning)
- **Kerf compatibility**: Per-edge allowances coexist with global kerf compensation

Run tests:
```bash
# Standalone runner (no pytest required)
PYTHONPATH=/home/squinlan/cliff_ai python3 -m skills.mill_ui.v2.tests.run_edge_tests

# Pytest module (if pytest available)
python3 -m pytest skills.mill_ui/v2/tests/test_edge_intent.py
```

All 5 acceptance criteria from Stage 18 spec are covered:
1. ✓ Edge allowance influences profile/pocket RemovalIntent
2. ✓ Profile with fillet hint emits RemovalIntent with fillet annotation
3. ✓ Multi-tool scenario: rough pass + finish pass with different allowances
4. ✓ Allowance semantics compatible with kerf (per-edge, not global)
5. ✓ Round-trip: edge intent preserved in PML

## Stage 18 Implementation Notes

**Files**:
- `v2/ast/compositional.py`: Edge node definition
- `v2/ir/removal_intent.py`: EdgeTreatment dataclass
- `v2/pml/compositional_parser.py`: Edge parsing
- `v2/pml/compositional_formatter.py`: Edge formatting
- `v2/resolution/layout_resolver.py`: Edge extraction logic
- `v2/adapters/hints_to_removal.py`: Item → RemovalIntent with edge treatment
- `v2/tests/test_edge_intent.py`: Acceptance tests
- `v2/tests/run_edge_tests.py`: Standalone test runner

**Compatibility**:
- Edge is additive; existing shapes unchanged
- RemovalIntent IR extended with EdgeTreatment constraint

**Next Steps** (future stages):
- Toolpath strategy: rough/finish pass planning
- Multi-tool operations: separate tools for rough/finish
- Validation: minimum tool size for fillet/chamfer radii
