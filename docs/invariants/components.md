# Component System

**Applies to:** Assembly members (panels, beams)

**Status:** DRAFT

---

## Overview

A **component** is something that expands to cuttable panels. The component system extends the existing panel/interface model to support laminated 3D members while maintaining compatibility with flat panel assemblies.

---

## Component Types

| Type | Description | Specification |
|------|-------------|---------------|
| **PanelSpec** | 2D shape with thickness | [assembly.md](assembly.md) |
| **BeamSpec** | Laminated 3D member | [beams.md](beams.md) |

---

## Type Hierarchy

```
PanelSpec (existing)
    - 2D shape with thickness
    - Has edges (top, bottom, left, right)
    - Receives notches, dados from joinery

BeamSpec (new)
    - Laminated 3D member
    - Has faces (front, back), edges (top, bottom), ends (left, right)
    - Contains features (face, end, edge)
    - Expands to PanelSpec per layer per segment

Assembly (extended)
    - Contains: dict[str, BeamSpec | PanelSpec]
    - Interfaces reference beam/panel names
    - resolve() expands beams, then applies interfaces
```

---

## Expansion Principle

All components expand to PanelSpec before entering the CAM pipeline:

- **PanelSpec** passes through unchanged
- **BeamSpec** expands to `list[PanelSpec]` (one per layer per segment)

This ensures the existing panel → RemovalIntent → G-code pipeline works unchanged.

---

## Mixed Assemblies

An Assembly can contain both PanelSpec and BeamSpec:

```python
Assembly(
    members={
        "post": BeamSpec(...),      # Laminated 3D member
        "infill": PanelSpec(...),   # Single panel
    },
    interfaces=[...]
)
```

---

## Invariants

| ID | Type | Invariant | Description |
|----|------|-----------|-------------|
| CM-1 | HARD | COMPONENT_EXPANDS_TO_PANELS | All components must expand to PanelSpec |
| CM-2 | HARD | MEMBER_NAMES_UNIQUE | All member names in assembly are unique |

---

## Related Documents

- [beams.md](beams.md) - Beam specification, features, expansion, BM-* invariants
- [assembly.md](assembly.md) - Panel interfaces, joinery rules, AJ-* invariants
- [beds.md](beds.md) - Bed-specific terminology and constraints, BD-* invariants

---

## Invariant Types

| Type | Meaning |
|------|---------|
| HARD | Violation breaks the system |
| STRUCTURAL | Requires coordinated migration to change |
