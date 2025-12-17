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
