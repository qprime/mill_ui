# Recipe 63: Roundover Edge

Demonstrates the `Roundover` edge feature — a quarter-circle rounded edge profile using a dedicated roundover bit.

## PML

```yaml
- Roundover:
    radius: 6mm
```

## What it does

1. Profiles the panel outline (through cut)
2. Applies a 6mm roundover to the panel edges using a roundover bit

## Tool requirements

- Flat endmill for profiling
- Roundover bit with matching radius (6mm)

## Key concepts

- Roundover bits have a concave quarter-circle cutting profile
- Cut depth equals the bit radius
- Toolpath offset from boundary equals the bit radius
- Distinct from V-bit edge features (chamfer/bevel) — no angle trig needed
