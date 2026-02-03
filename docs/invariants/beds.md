# Bed Assembly Invariants

**Applies to:** Bed primitives, bed-specific constraints

**Status:** DRAFT - Under development

---

## Overview

Beds are assemblies of beams (posts, rails) and panels (infill). This document covers bed-specific terminology and constraints. For beam mechanics (lamination, splicing, features), see [beams.md](beams.md).

---

## Terminology

| Term | Definition |
|------|------------|
| **Post** | Vertical structural element at bed corners; part of headboard/footboard assembly |
| **Side Rail** | Horizontal beam running bed length; connects headboard posts to footboard posts; removable |
| **Headboard** | Sub-assembly at head of bed; includes two posts and infill panel(s) |
| **Footboard** | Sub-assembly at foot of bed; includes two posts and infill panel(s); optional |
| **Stretcher** | Cross-member connecting side rails (TODO: future feature) |
| **Infill** | Panel(s) filling the space between posts in headboard/footboard |

---

## Panel Roles (Bed-Specific)

| Role | Description |
|------|-------------|
| POST | Vertical corner element (part of headboard/footboard) |
| SIDE_RAIL | Horizontal length-wise support; removable connection to posts |
| HEADBOARD_INFILL | Panel(s) filling headboard frame |
| FOOTBOARD_INFILL | Panel(s) filling footboard frame |

---

## Structural Components

### Posts

Posts are the primary vertical structural elements. They:
- Receive side rail connections (finger/box joints, mortise, or butt with external support)
- Support headboard/footboard infill panels
- Define bed height at corners
- Built as laminated beams (see [beams.md](beams.md))

**Post Parameters:**
- `height_mm`: Total post height
- `width_mm`: Post width (perpendicular to bed length)
- `depth_mm`: Post depth (parallel to bed length); may differ from width
- `layers`: Number of plywood layers (each layer = sheet thickness)

**Cross-Section:**
Posts can be rectangular. Cross-section = `width × depth` where:
- `width` = `layers × sheet_thickness`
- `depth` = cut dimension from sheet

Example: 3 layers of 19mm plywood, 76mm depth cut → 57mm × 76mm post

**Rail-to-Post Joinery Options:**
| Strategy | Description |
|----------|-------------|
| Finger | Box/finger joint at rail end meeting post face |
| Mortise | Pocket in post receives rail tenon |
| Butt | Simple butt joint (requires external bracket/bolt) |

### Side Rails

Side rails span from headboard posts to footboard posts. They:
- Built as laminated beams with splicing (bed length > sheet size)
- **Must be removable** - connect to posts via brackets, screws, or bolts (not glued)
- May have optional mid-span stretcher connections (TODO: future)

**Side Rail Parameters:**
- `length_mm`: Total rail length (mattress length + post allowance)
- `height_mm`: Rail height (visible height above mattress platform)
- `layers`: Number of plywood layers

**Rail-to-Post Connection (Removable):**
| Method | Description |
|--------|-------------|
| Bracket | Metal bed rail brackets (surface mount) |
| Bolt | Through-bolt with barrel nut or captured nut |
| Screw | Heavy-duty screws into post (least robust) |

Rail ends may have mortise/tenon for alignment, but structural connection is via hardware.

### Headboard / Footboard

These are **separate sub-assemblies** (their own Assembly objects) consisting of:
- Two posts (left and right)
- Infill panel(s) between posts
- Optional decorative elements

**Infill Styles (Initial Set):**
- `solid`: Single panel spanning between posts
- `slatted`: Vertical slats with gaps
- `framed`: Frame with inset panel (like a door)
- `none`: Posts only, no infill

**Post-to-Infill Joinery:**
- Captured in groove (dado in post face)
- Finger/box joint
- Butt with glue (permanent assembly)

Headboard and footboard can have different styles in the same bed.

---

## Invariants

| ID | Type | Invariant | Description |
|----|------|-----------|-------------|
| BD-1 | HARD | RAIL_LENGTH_VALID | Rail length = mattress_length + 2 × post_allowance |
| BD-2 | STRUCTURAL | RAIL_MIN_HEIGHT | Rail height >= 100mm for structural integrity |
| BD-3 | STRUCTURAL | POST_MIN_CROSS_SECTION | Post cross-section >= 50mm for joinery |
| BD-4 | HARD | RAIL_REMOVABLE | Side rails must use removable hardware connection (not glued) |

**Note:** Beam invariants (BM-*) from [beams.md](beams.md) also apply to posts and rails.

---

## Bed Dimensions Reference

| Mattress Size | Width (mm) | Length (mm) |
|---------------|------------|-------------|
| Twin | 990 | 1905 |
| Twin XL | 990 | 2030 |
| Full | 1370 | 1905 |
| Queen | 1525 | 2030 |
| King | 1930 | 2030 |
| Cal King | 1830 | 2135 |

**Note:** Bed frame dimensions = mattress + allowance for bedding tuck

---

## Open Design Questions

1. **Post-to-infill joinery**: Captured groove vs finger joint vs butt?
2. **Center support**: For wider beds (Queen+), do we need a center rail with legs?
3. **Stretchers**: How do stretchers connect to side rails? (TODO: future feature)
4. **Mattress support**: Slats, platform, bunkie board? (TODO: future feature)

---

## Related Documents

- [beams.md](beams.md) - Beam mechanics: lamination, splicing, features, BM-* invariants
- [components.md](components.md) - Component type hierarchy
- [assembly.md](assembly.md) - Panel interfaces, joinery rules, AJ-* invariants

---

## Invariant Types

| Type | Meaning |
|------|---------|
| HARD | Violation breaks the system |
| STRUCTURAL | Requires coordinated migration to change |
