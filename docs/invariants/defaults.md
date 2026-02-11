# Default Values Reference

**Type:** All values in this file are POLICY — they can change with care.

---

## Safety Defaults

| Parameter | Default | Canonical Location |
|-----------|---------|-------------------|
| safe_z_mm | 5.0 mm | ir/removal_intent.py (Constraints), cam/config.py, validation/invariants/gcode_invariants.py |
| max_stepdown_mm | 25.0 mm | validation/invariants/gcode_invariants.py |

**Note:** safe_z_mm is defined in multiple places for different contexts but uses the same canonical value (5.0mm).

---

## Tolerance Defaults

| Parameter | Default | Location |
|-----------|---------|----------|
| tolerance_mm | 0.1 mm | ir/removal_intent.py (Constraints) |
| clearance_mm | 0.12 mm | layout_ast/compositional.py (Assembly) |
| fitment_mm | 0.2 mm | assembly/joinery.py (HalfLap, Captured) |

---

## Layout Defaults

| Parameter | Default | Location |
|-----------|---------|----------|
| margin_mm | 10.0 mm | nesting/types.py (SheetSpec) |
| margin_mm | 0.0 mm | layout_ast/layout.py (Sheet) |
| layout_gap_mm | 10.0 mm | layout_ast/compositional.py (Assembly) |

---

## Nesting Defaults

| Parameter | Default | Location |
|-----------|---------|----------|
| kerf_mm | 6.35 mm | nesting/types.py (DEFAULT_KERF_MM) |

---

## Joinery Defaults

| Parameter | Default | Location |
|-----------|---------|----------|
| finger_width_mm | 12.0 mm | assembly/joinery.py (Finger) |
| joinery | "finger" | layout_ast/compositional.py (Assembly) |
| bottom | "captured" | layout_ast/compositional.py (Assembly) |
| cap_style | "between_sides" | layout_ast/compositional.py (Assembly) |

---

## Generator Defaults

| Parameter | Default | Location |
|-----------|---------|----------|
| loop_selection | "outer_only" | generators/params/loop.py (ProfileParams) |
| tab_width_mm | 10.0 mm | generators/params/loop.py (ProfileParams) |
| tab_height_mm | 3.0 mm | generators/params/loop.py (ProfileParams) |
| tool_width_mm | 3.175 mm | generators/params/loop.py (WaveParams) |

---

## Notes

- These are current defaults, not invariants
- Changing a default may affect existing PML files that rely on implicit values
- When changing defaults, consider backwards compatibility
- Document default changes in commit messages
