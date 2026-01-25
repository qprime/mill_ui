"""Loop generators for the domain/generator system.

Loop generators operate on boundary loops (edges) of a domain, producing
geometry that follows paths along the boundaries. They require explicit
specification of which loops to operate on.

Available generators:
    - profile_generator: Profile cut along domain boundaries
    - bead_generator: Decorative groove/bead along boundaries
    - chamfer_generator: Angled edge cut for presentation edges
    - measurement_edge_generator: Ruler tick marks along selected edges

See Also:
    - docs/domain_generator_design.md Section 3.3 for generator concepts
    - generators/base.py for parameter classes
"""

from generators.loop.profile import profile_generator
from generators.loop.bead import bead_generator
from generators.loop.chamfer import chamfer_generator
from generators.loop.measurement_edge import measurement_edge_generator

__all__ = [
    "profile_generator",
    "bead_generator",
    "chamfer_generator",
    "measurement_edge_generator",
]
