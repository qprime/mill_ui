from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from domains import Domain, apply_edge_joints
from generators.base import (
    BaseParams,
    GeneratorResult,
    generate_shape_id,
)
from generators.loop.profile import profile_generator
from generators.base import ProfileParams

if TYPE_CHECKING:
    from joints.profiles import JointProfile


EdgeName = Literal["top", "bottom", "left", "right"]

EDGE_NAME_TO_INDEX: dict[EdgeName, int] = {
    "bottom": 0,
    "right": 1,
    "top": 2,
    "left": 3,
}


@dataclass(frozen=True)
class JointedPanelParams(BaseParams):
    """Parameters for a rectangular panel with optional joints on each edge.

    Attributes:
        width_mm: Width of the panel in millimeters
        height_mm: Height of the panel in millimeters
        edge_joints: Mapping of edge names to joint profiles.
            Edges without entries remain straight.
        part_name: Optional name for the panel (e.g., "FRONT", "LEFT_SIDE")
        sheet_thickness_mm: Optional sheet thickness for profile through cuts
    """

    width_mm: float
    height_mm: float
    edge_joints: dict[EdgeName, JointProfile]
    part_name: str | None = None
    sheet_thickness_mm: float | None = None

    def validate(self) -> None:
        if self.width_mm <= 0:
            raise ValueError(
                f"JointedPanelParams: width_mm must be positive, got {self.width_mm}"
            )
        if self.height_mm <= 0:
            raise ValueError(
                f"JointedPanelParams: height_mm must be positive, got {self.height_mm}"
            )
        for edge_name in self.edge_joints:
            if edge_name not in EDGE_NAME_TO_INDEX:
                raise ValueError(
                    f"JointedPanelParams: invalid edge name '{edge_name}'. "
                    f"Must be one of: {list(EDGE_NAME_TO_INDEX.keys())}"
                )


def jointed_panel_generator(
    params: JointedPanelParams,
    *,
    center: tuple[float, float] = (0.0, 0.0),
    allow_empty: bool = False,
    shape_id_prefix: str = "panel",
    label: str | None = None,
) -> GeneratorResult:
    """Generate a rectangular panel with optional joint geometry on edges.

    Creates a panel profile cut. If edge_joints are specified, those edges
    get finger/notch patterns instead of straight edges.

    Args:
        params: Panel dimensions and joint configuration
        center: Center position for the panel in sheet coordinates
        allow_empty: If True, return empty list on invalid config
        shape_id_prefix: Prefix for generated shape IDs
        label: Optional label for the panel (displayed on SVG)

    Returns:
        List containing a single profile Item for the panel outline

    Example:
        >>> from joints.profiles import FingerJointProfile
        >>> params = JointedPanelParams(
        ...     width_mm=100,
        ...     height_mm=50,
        ...     edge_joints={
        ...         "bottom": FingerJointProfile(depth_mm=6.0, count=5),
        ...         "top": FingerJointProfile(depth_mm=6.0, count=5, phase=1),
        ...     },
        ... )
        >>> items = jointed_panel_generator(params, center=(50, 25))
    """
    params.validate()

    domain = Domain.from_rectangle(
        width_mm=params.width_mm,
        height_mm=params.height_mm,
        center=center,
    )

    if params.edge_joints:
        index_joints = {
            EDGE_NAME_TO_INDEX[name]: profile
            for name, profile in params.edge_joints.items()
        }
        domain = apply_edge_joints(domain, index_joints)

    profile_params = ProfileParams(
        side="outside",
        depth="through",
    )

    shape_id = shape_id_prefix
    if params.part_name:
        shape_id = f"{shape_id_prefix}_{params.part_name.lower()}"

    items = profile_generator(
        domain,
        profile_params,
        allow_empty=allow_empty,
        shape_id_prefix=shape_id,
        sheet_thickness_mm=params.sheet_thickness_mm,
        label=label,
    )

    return items


__all__ = ["JointedPanelParams", "jointed_panel_generator"]
