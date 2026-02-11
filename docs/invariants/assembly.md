# Assembly & Joinery Invariants

**Applies to:** Joinery strategies, panel specifications, interfaces

---

## Invariants

| ID | Type | Invariant | Description |
|----|------|-----------|-------------|
| AJ-1 | HARD | INTERFACE_VALIDATES | Joinery must be valid for interface type |
| AJ-2 | HARD | PANEL_NAMES_EXIST | panel_a and panel_b must exist in assembly |
| AJ-3 | HARD | FINGER_MIN_3 | Finger joint count >= 3 |
| AJ-4 | HARD | FINGER_ODD | Finger count is always odd |
| AJ-5 | STRUCTURAL | BUTT_NO_REMOVAL | Butt joint has RemovalKind.NONE |
| AJ-6 | STRUCTURAL | BUTT_ALL_INTERFACES | Butt valid for all InterfaceTypes |
| AJ-7 | HARD | HALFLAP_INTERNAL_ONLY | HalfLap valid only for INTERNAL interfaces |
| AJ-8 | HARD | HALFLAP_REQUIRES_POSITION | INTERNAL interfaces require position_along_edge_a_mm |
| AJ-9 | HARD | CAPTURED_RECEIVING_NOT_INTERNAL | receiving='b' invalid for INTERNAL |
| AJ-10 | HARD | NOTCH_U_START_NON_NEGATIVE | u_start_mm >= 0 |
| AJ-11 | HARD | NOTCH_U_LEN_POSITIVE | u_len_mm > 0 |
| AJ-12 | HARD | NOTCH_DEPTH_POSITIVE | depth_mm > 0 |
| AJ-13 | STRUCTURAL | EDGE_INDICES_CCW | BOTTOM=0, RIGHT=1, TOP=2, LEFT=3 |
| AJ-14 | HARD | NOTCH_FITS_EDGE | u_start + u_len <= edge_length |
| AJ-15 | HARD | NOTCHES_NO_OVERLAP | Adjacent notches cannot overlap |
| AJ-16 | HARD | TOE_KICK_DADO_POSITION | bottom dado position_along_edge_a_mm = toe_kick_height (no thickness offset) |

---

## Interface Types and Valid Joinery

| Interface Type | Valid Joinery |
|----------------|---------------|
| SIDE_TO_SIDE | Finger, Butt, Captured |
| TOP | Finger, Butt, Captured |
| BOTTOM | Finger, Butt, Captured |
| INTERNAL | HalfLap, Butt, Captured |

---

## Finger Joint Rules

- Minimum 3 fingers
- Count is always odd (ensures symmetric joint)
- Width calculated from edge length and count

---

## Toe-Kick Dado Positioning

The bottom face of the bottom panel sits at `toe_kick_height` above the cabinet bottom. For the side-panel capture groove, `position_along_edge_a_mm` must equal `toe_kick_height`.

**Wrong:**
```python
bottom_dado_position = toe_kick_height + thickness
```

**Correct:**
```python
bottom_dado_position = toe_kick_height
```

**Why:** The groove's near edge aligns with the bottom panel's bottom face. Any visual offset comes from groove width and centering math in the resolver.

---

## Edge Indices

Edges are indexed counter-clockwise starting from bottom:

| Index | Edge |
|-------|------|
| 0 | BOTTOM |
| 1 | RIGHT |
| 2 | TOP |
| 3 | LEFT |

---

## Notch Constraints

- `u_start_mm >= 0` (position along edge)
- `u_len_mm > 0` (notch length)
- `depth_mm > 0` (notch depth)
- `u_start + u_len <= edge_length` (fits on edge)
- Adjacent notches cannot overlap

---

## Invariant Types

| Type | Meaning |
|------|---------|
| HARD | Violation breaks the system |
| STRUCTURAL | Requires coordinated migration to change |
