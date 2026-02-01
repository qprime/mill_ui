# G-Code Invariants

**Applies to:** Machine output, motion planning

---

## Invariants

| ID | Type | Invariant | Description |
|----|------|-----------|-------------|
| GC-1 | HARD | SAFE_Z_RESPECTED | Rapids (G0) only at or above safe_z |
| GC-2 | HARD | SPINDLE_BEFORE_CUT | M3/M4 before G1 at negative Z |
| GC-3 | HARD | ENDS_AT_SAFE | Program ends with Z >= safe_z |
| GC-4 | HARD | MAX_STEPDOWN | Single plunge <= max_stepdown |
| GC-5 | HARD | PARSEABLE | All lines valid G-code syntax |
| GC-6 | HARD | NO_NEGATIVE_FEED | Feed rates must be positive |
| GC-7 | HARD | Z_MONOTONIC_PLUNGE | Z decreases monotonically during plunge |
| GC-8 | HARD | XY_WITHIN_BOUNDS | All XY within sheet + margin |
| GC-9 | STRUCTURAL | TOOL_DECLARED | Tool declared before M6 |
| GC-10 | HARD | CONTINUOUS_PATH | No large XY jumps during cutting |
| GC-11 | STRUCTURAL | MODAL_MOTION | G0/G1/G2/G3 are modal |

---

## Safety Rules

### Safe Z
- All rapid moves (G0) must be at or above `safe_z_mm` (default: 5.0mm)
- Program must end with Z at or above safe_z
- Never rapid at cutting depth

### Spindle
- M3 (CW) or M4 (CCW) must be issued before any G1 move at negative Z
- Cutting without spindle running = broken tool

### Plunge Depth
- Single plunge must not exceed `max_stepdown_mm` (default: 25.0mm)
- Deeper cuts require multiple passes

---

## Motion Rules

### Continuity
- No large XY jumps during cutting (G1 at negative Z)
- Large jumps indicate missed retract or path error

### Monotonic Plunge
- During a plunge sequence, Z must decrease monotonically
- Z increasing during plunge indicates path error

### Bounds
- All XY coordinates must be within sheet dimensions + margin
- Out-of-bounds motion will crash the machine

---

## Feed Rates

- All feed rates (F parameter) must be positive
- Zero or negative feed = machine error

---

## Modal Commands

G0, G1, G2, G3 are modal—they persist until changed:

```gcode
G0 X0 Y0      ; rapid
X10           ; still rapid (G0 modal)
G1 X20 F500   ; feed move
Y30           ; still feed move (G1 modal)
```

---

## Invariant Types

| Type | Meaning |
|------|---------|
| HARD | Violation breaks the system (or the machine) |
| STRUCTURAL | Requires coordinated migration to change |
