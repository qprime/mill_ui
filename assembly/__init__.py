from assembly.core import (
    Assembly,
    Interface,
    InterfaceType,
    RemovalKind,
)
from assembly.panel import (
    DadoSpec,
    Edge,
    NotchSpec,
    PanelRole,
    PanelSpec,
    validate_notch_fits_edge,
    validate_notches_no_overlap,
)
from assembly.joinery import (
    Butt,
    Captured,
    Dado,
    Finger,
    HalfLap,
    JoineryStrategy,
    Rabbet,
    Step,
)
from assembly.primitives import (
    box,
    carcass,
    cubby,
)
from assembly.layout import (
    LayoutConfig,
    PlacedPanel,
    layout_panels,
    panels_to_layout_ast,
)

from assembly.notches import (
    NotchSpec as LegacyNotchSpec,
    build_notched_polygon,
    finger_joints_to_notches,
    notch_to_polyline,
    validate_notch_fits_edge as legacy_validate_notch_fits_edge,
    validate_notches_no_overlap as legacy_validate_notches_no_overlap,
)

__all__ = [
    "Assembly",
    "Interface",
    "InterfaceType",
    "RemovalKind",
    "DadoSpec",
    "Edge",
    "NotchSpec",
    "PanelRole",
    "PanelSpec",
    "validate_notch_fits_edge",
    "validate_notches_no_overlap",
    "Butt",
    "Captured",
    "Dado",
    "Finger",
    "HalfLap",
    "JoineryStrategy",
    "Rabbet",
    "Step",
    "box",
    "carcass",
    "cubby",
    "LayoutConfig",
    "PlacedPanel",
    "layout_panels",
    "panels_to_layout_ast",
    "LegacyNotchSpec",
    "build_notched_polygon",
    "finger_joints_to_notches",
    "notch_to_polyline",
]
