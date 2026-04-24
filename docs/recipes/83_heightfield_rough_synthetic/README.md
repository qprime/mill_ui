# Recipe 83: Heightfield Rough (Synthetic)

Demonstrates multi-tool heightfield roughing on a synthetic gradient image.

**Two rough tools:**
- `1/4 upcut spiral` (6.35mm) — coarse rough
- `1/8 upcut spiral` (3.175mm) — fine rough

The 1/4" tool stops above detail that the 1/8" tool will later reach (morphological
barrier computation). The 1/8" tool leaves residual material for a future finish pass.

**Note:** Output is G-code is noisy by design. Finish passes land in #3. Do not cut.
