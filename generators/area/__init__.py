"""Area generators for the domain/generator system.

Area generators operate over the 2D interior of a domain, producing geometry
that fills or decorates the region. They respect inner boundaries as constraints.

Available generators:
    - flat_pocket_generator: Uniform pocket at specified depth
    - wave_generator: Sinusoidal wave pattern
    - grid_generator: Crosshatch grid pattern
    - raised_panel_generator: Traditional raised panel with beveled border

See Also:
    - docs/domain_generator_design.md Section 3.3 for generator concepts
    - generators/base.py for parameter classes
"""

from generators.area.flat import flat_pocket_generator
from generators.area.wave import wave_generator
from generators.area.grid import grid_generator
from generators.area.raised_panel import raised_panel_generator

__all__ = [
    "flat_pocket_generator",
    "wave_generator",
    "grid_generator",
    "raised_panel_generator",
]
