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
| AJ-8 | HARD | HALFLAP_REQUIRES_POSITION | INTERNAL interfaces require position_along_edge_a_mm and position_along_edge_b_mm |
| AJ-9 | HARD | CAPTURED_RECEIVING_NOT_INTERNAL | receiving='b' invalid for INTERNAL |
| AJ-10 | HARD | NOTCH_U_START_NON_NEGATIVE | u_start_mm >= 0 |
| AJ-11 | HARD | NOTCH_U_LEN_POSITIVE | u_len_mm > 0 |
| AJ-12 | HARD | NOTCH_DEPTH_POSITIVE | depth_mm > 0 |
| AJ-13 | STRUCTURAL | EDGE_INDICES_CCW | BOTTOM=0, RIGHT=1, TOP=2, LEFT=3 |
| AJ-14 | HARD | NOTCH_FITS_EDGE | u_start + u_len <= edge_length |
| AJ-15 | HARD | NOTCHES_NO_OVERLAP | Adjacent notches cannot overlap |
| AJ-16 | HARD | TOE_KICK_DADO_POSITION | bottom dado position_along_edge_a_mm = toe_kick_height (no thickness offset) |
| AJ-17 | STRUCTURAL | DOGBONE_DEFAULT_ALL_CORNER_STRATEGIES | Dogbone fillets are default for all corner-producing strategies (Captured, Finger, HalfLap) |
| AJ-18 | HARD | DOGBONE_DEPTH_MATCHES_PARENT | Dogbone bore depth equals the parent cut's Z depth: dado depth for a face groove, through the stock for an edge notch. Notch depth measures XY reach into the panel, not Z. |
| AJ-19 | HARD | BOX_CAP_FIT | Box cap blanks reach their specified joints and account for exposed cap thickness without changing the declared outside dimensions. |
| AJ-20 | HARD | CUBBY_ASSEMBLED_FIT | Cubby blanks and interface positions derive from common assembly spans; captured members engage their grooves, the declared outside envelope is preserved, and crossing half-laps open from opposite ends. |
| AJ-21 | HARD | NOTCH_RELIEF_REFERENCE | Generated notch relief uses the cutout center as its directional reference, so its bores clear the mating corners. |
| AJ-22 | HARD | CARCASS_CAP_AND_SHELF_FIT | Carcass cap and shelf spans include their groove engagement; cap exposure preserves the declared height, and shelf positions leave equal clear openings between actual cap faces. |
| AJ-23 | HARD | CARCASS_BACK_AND_TOE_FIT | Carcass back spans, stock, depth placement and groove contacts share the actual inside frame; mirrored inside faces preserve the front toe recess and its overhang. |

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

Box side blanks joined to the front and back with Finger span the full declared
box depth. Their end fingers occupy the front/back thickness; subtracting those
thicknesses before cutting the fingers shortens the assembled box. The box
primitive establishes these blank dimensions before the strategy creates
notches. Resolution preserves the resulting PanelSpec dimensions. Other corner
strategies retain their existing sizing rules.

## Box Cap Fit

The box primitive establishes cap and wall dimensions before joinery strategies
create removals. Finger caps span the full outside width and depth, so their
edges match the explicit wall interfaces. Butt caps retain the inside span.

For Captured receiving `a`, each cap extends into the wall grooves: its edge
inset from the outside is wall thickness minus groove depth. For receiving `b`,
the cap spans the outside width/depth and projects beyond the wall ends by cap
thickness minus groove depth. Subtract each such projection from the wall height
so the assembled outside height remains the declared box height. Top and bottom
fits are independent. Groove depth uses the same resolution as Captured.apply;
an explicit zero depth is invalid rather than a request for the default.

Box cap groove depth must be positive and no greater than the receiving stock
thickness. Caps must leave positive panel spans and wall height. A receiving-`b`
box cap with nonzero groove inset requires explicit wall placement, which the
box primitive does not model; reject it rather than guessing a wall footprint.
Explicitly supplied panel/interface assemblies retain that placement control.

---

## Carcass Caps and Shelves

The carcass factory uses the same cap-fit calculation as the box factory.
Between-side Captured caps enter the side grooves; over-side Captured caps
receive the sides and expose only stock thickness minus groove depth. Each cap
is independent. Reject a receiving direction inconsistent with `cap_style`.
Missing caps contribute no height projection. Finger caps span the outside
width and interlock with full-height sides. Butt placement follows `cap_style`.

Captured shelves enter grooves in the sides and span the inside width plus
twice the groove depth, independently of cap width or placement. Subtract shelf
thicknesses before dividing the interior into equal clear openings. Positions
are relative to side-panel origins and account for cap insets, exposed cap
thickness and a raised toe-kick bottom. Groove depth must fit receiving stock;
panel spans and clear openings must stay positive.

The bookcase recipe is a carcass with full-width fixed shelves and no vertical
partitions. It is not a separate named assembly type. Nonzero carcass
`vertical_partitions` remains explicitly unsupported; cubby supplies the
continuous grid topology with HalfLap crossings.

Carcass `back_inset` is the clear gap behind the back's rear face, consistent
with cubby. Back thickness is actual member stock, not just a groove-width hint.
Back width and height extend from the actual inside side/cap faces into their
specified grooves; a rear setback never reduces those spans. A raised bottom
changes the lower receiving face. Missing caps provide no vertical engagement.
Back fit supports Butt or Captured receiving `a`; incompatible receiving
directions, conflicting joint inset, wrong groove width, nonpositive spans and
grooves deeper than receiving stock error explicitly. Preserve the configured
joint, including disabled dogbones, when supplying the inserted back thickness.

Shelves stop at the back's front face, adding only their actual back-support
engagement when requested. Support depth must fit back stock. Support groove
height subtracts the back's bottom origin, not the rear setback. The left side
depth axis runs front to rear; right side and top run rear to front, matching
their inside machining faces. Bottom and shelf depth axes run front to rear.

Captured interfaces may declare `contact_span_mm`, measured along the receiver's
groove axis in panel-local coordinates. Captured passes that explicit interval
to `DadoSpec.span_mm` without inferring assembly topology. A missing span retains
the existing full-panel groove. Spans are finite, positive and within the
receiver; resolution honors both endpoints through the ordinary pocket/relief
path. Toe-kick bottom grooves start behind the front recess, and shelf grooves
stop at the supported shelf extent. Do not remove an unsupported overhang with
a full-length groove. Shortened toe bottoms require Butt or between-side
Captured; full-length Finger and over-side cap interfaces need explicit topology.

Assembly panel stock must match the current PML sheet. A mixed-thickness back
requires separately prepared matching-stock jobs; do not silently cut it from
the frame's thicker stock. This applies to every resolved assembly member.

## Cubby Assembled Fit

The cubby factory owns panel spans and interface positions in a common assembly
frame: X left to right, Y front to rear, Z bottom to top. Finger caps span the
outside width. Captured shelves, partitions and backs extend into their
receiving grooves; a rear setback never reduces the back's width or height.
Equal clear openings account for divider thickness before computing positions.
Interface positions subtract the receiving panel's origin from these shared
planes rather than recomputing the grid in panel-local coordinates.

For cubby, `back_inset` is the clear distance from the rear outside edge to the
back panel's rear face. Its front face is another back thickness forward.
Internal members end at that front face, plus their actual support-groove
engagement when enabled. The back is installed during frame assembly.

The inside machining face determines each panel's local orientation. Top and
right-side depth axes run rear to front; bottom, left-side and divider depth
axes run front to rear. Shelf half-laps open at local bottom (front) and
partition half-laps at local right (rear). Continuous crossings require HalfLap
and matching depth extents. Butt/Captured crossings need explicit segmented
topology; unsupported receiving directions, conflicting insets, nonpositive
openings and grooves deeper than receiving stock raise errors.

Generated notch relief uses the notch rectangle's center, rather than the whole
panel center, to orient its bores. This reference describes the removed void;
it is not a point that must lie inside retained material. Explicit user-supplied
references retain their existing semantics. Relief depth still follows AJ-18.

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
