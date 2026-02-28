# Recipe 58: Dogbone Joinery

Demonstrates automatic dogbone fillets on assembly joinery for CNC router corner clearance.

**Key concepts:**
- Dogbone fillets are automatic for all corner-producing joinery (Captured, Finger, HalfLap)
- No `dogbone: true` needed — strategies emit dogbone bores by default
- Use `dogbone: false` on an interface to suppress, or `dogbone: { style: t-bone_x }` to override
