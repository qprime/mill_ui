# Recipe 85: Heightfield Full (Synthetic)

End-to-end heightfield machining on a synthetic gradient: rough (two tools) + finish (ball-nose).

**Three tools:**
- `1/4 upcut spiral` (6.35mm) — coarse rough
- `1/8 upcut spiral` (3.175mm) — fine rough
- `1/8 ball nose 2F` (3.19mm) — finish, 12% stepover, angle 0°

The rough passes use morphological barrier stacking (coarse tool stops above detail the
fine tool will reach). The finish pass uses spherical-cap dilation of the surface to
compute a per-pixel no-gouge tool-center Z map and rasters across the field.

**Rest-material floor:** the finish pass never cuts above the finest rough barrier, so
finish never redoes rough's work.

Closes the heightfield feature end-to-end (issues #175 → #176 → #177).
