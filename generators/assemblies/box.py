from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from joints.profiles import FingerJointProfile, JointProfile


@dataclass(frozen=True)
class FingerStrategy:
    """Configuration for finger joint sizing.

    Attributes:
        mode: "by_count" for explicit finger count, "by_size" for target width
        value: finger count (int) for by_count, or target width in mm (float) for by_size
    """
    mode: Literal["by_count", "by_size"]
    value: int | float

    def __post_init__(self) -> None:
        if self.mode == "by_count":
            if not isinstance(self.value, int) or self.value < 1:
                raise ValueError(
                    f"FingerStrategy: by_count mode requires positive integer, got {self.value}"
                )
        elif self.mode == "by_size":
            if not isinstance(self.value, (int, float)) or self.value <= 0:
                raise ValueError(
                    f"FingerStrategy: by_size mode requires positive number, got {self.value}"
                )


@dataclass(frozen=True)
class DadoSpec:
    """Specification for a dado groove on a panel.

    Attributes:
        position_from_edge_mm: Distance from the panel edge to the dado start
        width_mm: Width of the dado groove (typically = material thickness)
        depth_mm: Depth of the dado groove (typically = half material thickness)
        edge: Which edge the dado is measured from ("top" or "bottom")
    """
    position_from_edge_mm: float
    width_mm: float
    depth_mm: float
    edge: Literal["top", "bottom"]


@dataclass(frozen=True)
class BoxParams:
    """Parameters for generating a finger-jointed or butt-jointed box.

    Dimensions are outer dimensions. Panel dimensions are computed by
    subtracting material thickness as appropriate.

    Attributes:
        outer_width_mm: Outer width of the box (X dimension)
        outer_depth_mm: Outer depth of the box (Y dimension)
        outer_height_mm: Outer height of the box (Z dimension)
        thickness_mm: Material thickness
        joinery: "butt" for simple butt joints, "finger" for finger joints
        finger_strategy: How to size fingers (required if joinery="finger")
        clearance_mm: Gap for joint fit (default 0.1mm)
        include_lid: Whether to generate a lid panel
        include_bottom: Whether to generate a bottom panel (default True)
        bottom_style: How bottom panel connects ("captured", "finger", "dado")
        top_style: How top panel connects ("captured", "finger", "dado")
        dado_inset_mm: Distance from wall bottom to dado bottom (for bottom dado)
        dado_drop_mm: Distance from wall top to dado top (for top dado)
    """
    outer_width_mm: float
    outer_depth_mm: float
    outer_height_mm: float
    thickness_mm: float
    joinery: Literal["butt", "finger"] = "finger"
    finger_strategy: FingerStrategy | None = None
    clearance_mm: float = 0.1
    include_lid: bool = False
    include_bottom: bool = True
    bottom_style: Literal["captured", "finger", "dado"] = "captured"
    top_style: Literal["captured", "finger", "dado"] = "captured"
    dado_inset_mm: float = 0.0
    dado_drop_mm: float = 0.0

    def __post_init__(self) -> None:
        if self.outer_width_mm <= 0:
            raise ValueError(f"outer_width_mm must be positive, got {self.outer_width_mm}")
        if self.outer_depth_mm <= 0:
            raise ValueError(f"outer_depth_mm must be positive, got {self.outer_depth_mm}")
        if self.outer_height_mm <= 0:
            raise ValueError(f"outer_height_mm must be positive, got {self.outer_height_mm}")
        if self.thickness_mm <= 0:
            raise ValueError(f"thickness_mm must be positive, got {self.thickness_mm}")
        if self.joinery == "finger" and self.finger_strategy is None:
            raise ValueError("finger_strategy required when joinery='finger'")
        if self.clearance_mm < 0:
            raise ValueError(f"clearance_mm must be non-negative, got {self.clearance_mm}")
        if self.dado_inset_mm < 0:
            raise ValueError(f"dado_inset_mm must be non-negative, got {self.dado_inset_mm}")
        if self.dado_drop_mm < 0:
            raise ValueError(f"dado_drop_mm must be non-negative, got {self.dado_drop_mm}")


EdgeName = Literal["top", "bottom", "left", "right"]


@dataclass(frozen=True)
class PanelSpec:
    """Specification for a single box panel.

    Attributes:
        name: Panel identifier ("front", "back", "left", "right", "top", "bottom")
        width_mm: Panel width in mm
        height_mm: Panel height in mm
        edge_joints: Mapping of edge name to joint profile (None = straight edge)
        mating_edges: Mapping of edge name to mating panel.edge (e.g., "right_side.left")
        dados: List of dado groove specifications for this panel
    """
    name: str
    width_mm: float
    height_mm: float
    edge_joints: dict[EdgeName, JointProfile | None]
    mating_edges: dict[EdgeName, str]
    dados: tuple[DadoSpec, ...] = ()


def _create_finger_profile(
    strategy: FingerStrategy,
    depth_mm: float,
    clearance_mm: float,
    phase: Literal[0, 1],
) -> FingerJointProfile:
    """Create a FingerJointProfile from strategy parameters."""
    if strategy.mode == "by_count":
        return FingerJointProfile(
            depth_mm=depth_mm,
            count=int(strategy.value),
            phase=phase,
            clearance_mm=clearance_mm,
        )
    else:
        return FingerJointProfile(
            depth_mm=depth_mm,
            width_mm=float(strategy.value),
            phase=phase,
            clearance_mm=clearance_mm,
        )


def compute_box_panels(params: BoxParams) -> list[PanelSpec]:
    """Compute panel specifications for a box.

    For finger joints, phase assignment ensures mating edges interlock:
    - Front/back horizontal edges get phase 0
    - Left/right vertical edges get phase 1
    - Bottom/top panels have all edges at phase 0

    Panel dimension conventions (for finger joints):
    - Front/back: full outer width × (height - 2*thickness)
    - Left/right: (depth - 2*thickness) × (height - 2*thickness)
    - Bottom/top: (width - 2*thickness) × (depth - 2*thickness)

    For butt joints, panels are full outer dimensions minus overlapping thickness.

    Args:
        params: Box configuration

    Returns:
        List of PanelSpec objects, one per panel
    """
    w = params.outer_width_mm
    d = params.outer_depth_mm
    h = params.outer_height_mm
    t = params.thickness_mm

    panels: list[PanelSpec] = []

    if params.joinery == "butt":
        panels.extend(_butt_joint_panels(w, d, h, t, params))
    else:
        panels.extend(_finger_joint_panels(w, d, h, t, params))

    return panels


def _butt_joint_panels(
    w: float, d: float, h: float, t: float,
    params: BoxParams,
) -> list[PanelSpec]:
    """Generate panel specs for butt-jointed box.

    For butt joints, only "captured" and "dado" bottom/top styles are supported.
    Finger-style bottom/top requires finger joinery.
    """
    panels: list[PanelSpec] = []
    dado_depth = t / 2

    bottom_dado = params.bottom_style == "dado"
    top_dado = params.top_style == "dado"

    front_dados: list[DadoSpec] = []
    back_dados: list[DadoSpec] = []
    left_dados: list[DadoSpec] = []
    right_dados: list[DadoSpec] = []

    if bottom_dado:
        dado_spec = DadoSpec(
            position_from_edge_mm=params.dado_inset_mm,
            width_mm=t,
            depth_mm=dado_depth,
            edge="bottom",
        )
        front_dados.append(dado_spec)
        back_dados.append(dado_spec)
        left_dados.append(dado_spec)
        right_dados.append(dado_spec)

    if top_dado:
        dado_spec = DadoSpec(
            position_from_edge_mm=params.dado_drop_mm,
            width_mm=t,
            depth_mm=dado_depth,
            edge="top",
        )
        front_dados.append(dado_spec)
        back_dados.append(dado_spec)
        left_dados.append(dado_spec)
        right_dados.append(dado_spec)

    panels.append(PanelSpec(
        name="front",
        width_mm=w,
        height_mm=h,
        edge_joints={"top": None, "bottom": None, "left": None, "right": None},
        mating_edges={
            "left": "left_side.front",
            "right": "right_side.front",
            "bottom": "bottom.front",
        },
        dados=tuple(front_dados),
    ))

    panels.append(PanelSpec(
        name="back",
        width_mm=w,
        height_mm=h,
        edge_joints={"top": None, "bottom": None, "left": None, "right": None},
        mating_edges={
            "left": "left_side.back",
            "right": "right_side.back",
            "bottom": "bottom.back",
        },
        dados=tuple(back_dados),
    ))

    panels.append(PanelSpec(
        name="left_side",
        width_mm=d - 2 * t,
        height_mm=h,
        edge_joints={"top": None, "bottom": None, "left": None, "right": None},
        mating_edges={
            "left": "back.left",
            "right": "front.left",
            "bottom": "bottom.left",
        },
        dados=tuple(left_dados),
    ))

    panels.append(PanelSpec(
        name="right_side",
        width_mm=d - 2 * t,
        height_mm=h,
        edge_joints={"top": None, "bottom": None, "left": None, "right": None},
        mating_edges={
            "left": "front.right",
            "right": "back.right",
            "bottom": "bottom.right",
        },
        dados=tuple(right_dados),
    ))

    if params.include_bottom:
        if params.bottom_style == "dado":
            bottom_width = w - 2 * t + 2 * dado_depth
            bottom_height = d - 2 * t + 2 * dado_depth
        else:
            bottom_width = w - 2 * t
            bottom_height = d - 2 * t
        panels.append(PanelSpec(
            name="bottom",
            width_mm=bottom_width,
            height_mm=bottom_height,
            edge_joints={"top": None, "bottom": None, "left": None, "right": None},
            mating_edges={
                "bottom": "front.bottom",
                "top": "back.bottom",
                "left": "left_side.bottom",
                "right": "right_side.bottom",
            },
        ))

    if params.include_lid:
        if params.top_style == "dado":
            lid_width = w - 2 * t + 2 * dado_depth
            lid_height = d - 2 * t + 2 * dado_depth
        else:
            lid_width = w - 2 * t
            lid_height = d - 2 * t
        panels.append(PanelSpec(
            name="top",
            width_mm=lid_width,
            height_mm=lid_height,
            edge_joints={"top": None, "bottom": None, "left": None, "right": None},
            mating_edges={
                "bottom": "front.top",
                "top": "back.top",
                "left": "left_side.top",
                "right": "right_side.top",
            },
        ))

    return panels


def _finger_joint_panels(
    w: float, d: float, h: float, t: float,
    params: BoxParams,
) -> list[PanelSpec]:
    """Generate panel specs for finger-jointed box.

    Wall height calculations based on bottom/top style:
    - captured: walls are h - 2*t (room for top/bottom thickness at each end)
    - finger: walls extend to edge, so h - t (only other end needs room)
    - dado: walls are full height, dado groove cut into inside face

    For finger-jointed bottom/top:
    - Front/back get bottom/top edge fingers at phase 0
    - Left/right get bottom/top edge fingers at phase 1
    - Bottom/top panel gets fingers on all edges at phase 0
    """
    panels: list[PanelSpec] = []
    strategy = params.finger_strategy
    clearance = params.clearance_mm
    dado_depth = t / 2

    def finger(phase: Literal[0, 1]) -> FingerJointProfile:
        return _create_finger_profile(strategy, t, clearance, phase)

    bottom_finger = params.bottom_style == "finger"
    top_finger = params.top_style == "finger"
    bottom_dado = params.bottom_style == "dado"
    top_dado = params.top_style == "dado"

    bottom_reduction = 0 if (bottom_finger or bottom_dado) else t
    top_reduction = 0 if (top_finger or top_dado) else t

    front_back_width = w
    front_back_height = h - bottom_reduction - top_reduction

    side_width = d - 2 * t
    side_height = h - bottom_reduction - top_reduction

    if params.bottom_style == "finger":
        bottom_top_width = w
        bottom_top_height = d
    elif params.bottom_style == "dado":
        bottom_top_width = w - 2 * t + 2 * dado_depth
        bottom_top_height = d - 2 * t + 2 * dado_depth
    else:
        bottom_top_width = w - 2 * t
        bottom_top_height = d - 2 * t

    if params.top_style == "finger":
        lid_width = w
        lid_height = d
    elif params.top_style == "dado":
        lid_width = w - 2 * t + 2 * dado_depth
        lid_height = d - 2 * t + 2 * dado_depth
    else:
        lid_width = w - 2 * t
        lid_height = d - 2 * t

    front_dados: list[DadoSpec] = []
    back_dados: list[DadoSpec] = []
    left_dados: list[DadoSpec] = []
    right_dados: list[DadoSpec] = []

    if bottom_dado:
        dado_spec = DadoSpec(
            position_from_edge_mm=params.dado_inset_mm,
            width_mm=t,
            depth_mm=dado_depth,
            edge="bottom",
        )
        front_dados.append(dado_spec)
        back_dados.append(dado_spec)
        left_dados.append(dado_spec)
        right_dados.append(dado_spec)

    if top_dado:
        dado_spec = DadoSpec(
            position_from_edge_mm=params.dado_drop_mm,
            width_mm=t,
            depth_mm=dado_depth,
            edge="top",
        )
        front_dados.append(dado_spec)
        back_dados.append(dado_spec)
        left_dados.append(dado_spec)
        right_dados.append(dado_spec)

    front_edge_joints: dict[EdgeName, JointProfile | None] = {
        "top": finger(0) if top_finger else None,
        "bottom": finger(0) if bottom_finger else None,
        "left": finger(0),
        "right": finger(0),
    }
    back_edge_joints: dict[EdgeName, JointProfile | None] = {
        "top": finger(0) if top_finger else None,
        "bottom": finger(0) if bottom_finger else None,
        "left": finger(0),
        "right": finger(0),
    }
    left_edge_joints: dict[EdgeName, JointProfile | None] = {
        "top": finger(1) if top_finger else None,
        "bottom": finger(1) if bottom_finger else None,
        "left": finger(1),
        "right": finger(1),
    }
    right_edge_joints: dict[EdgeName, JointProfile | None] = {
        "top": finger(1) if top_finger else None,
        "bottom": finger(1) if bottom_finger else None,
        "left": finger(1),
        "right": finger(1),
    }

    panels.append(PanelSpec(
        name="front",
        width_mm=front_back_width,
        height_mm=front_back_height,
        edge_joints=front_edge_joints,
        mating_edges={
            "left": "left_side.right",
            "right": "right_side.left",
            "bottom": "bottom.bottom",
            "top": "top.bottom" if params.include_lid else "",
        },
        dados=tuple(front_dados),
    ))

    panels.append(PanelSpec(
        name="back",
        width_mm=front_back_width,
        height_mm=front_back_height,
        edge_joints=back_edge_joints,
        mating_edges={
            "left": "right_side.right",
            "right": "left_side.left",
            "bottom": "bottom.top",
            "top": "top.top" if params.include_lid else "",
        },
        dados=tuple(back_dados),
    ))

    panels.append(PanelSpec(
        name="left_side",
        width_mm=side_width,
        height_mm=side_height,
        edge_joints=left_edge_joints,
        mating_edges={
            "left": "back.right",
            "right": "front.left",
            "bottom": "bottom.left",
            "top": "top.left" if params.include_lid else "",
        },
        dados=tuple(left_dados),
    ))

    panels.append(PanelSpec(
        name="right_side",
        width_mm=side_width,
        height_mm=side_height,
        edge_joints=right_edge_joints,
        mating_edges={
            "left": "front.right",
            "right": "back.left",
            "bottom": "bottom.right",
            "top": "top.right" if params.include_lid else "",
        },
        dados=tuple(right_dados),
    ))

    if params.include_bottom:
        if params.bottom_style == "finger":
            bottom_edge_joints: dict[EdgeName, JointProfile | None] = {
                "top": finger(1),
                "bottom": finger(1),
                "left": finger(0),
                "right": finger(0),
            }
        else:
            bottom_edge_joints = {
                "top": None,
                "bottom": None,
                "left": None,
                "right": None,
            }
        panels.append(PanelSpec(
            name="bottom",
            width_mm=bottom_top_width,
            height_mm=bottom_top_height,
            edge_joints=bottom_edge_joints,
            mating_edges={
                "bottom": "front.bottom",
                "top": "back.bottom",
                "left": "left_side.bottom",
                "right": "right_side.bottom",
            },
        ))

    if params.include_lid:
        if params.top_style == "finger":
            top_edge_joints: dict[EdgeName, JointProfile | None] = {
                "top": finger(1),
                "bottom": finger(1),
                "left": finger(0),
                "right": finger(0),
            }
        else:
            top_edge_joints = {
                "top": None,
                "bottom": None,
                "left": None,
                "right": None,
            }
        panels.append(PanelSpec(
            name="top",
            width_mm=lid_width,
            height_mm=lid_height,
            edge_joints=top_edge_joints,
            mating_edges={
                "bottom": "front.top",
                "top": "back.top",
                "left": "left_side.top",
                "right": "right_side.top",
            },
        ))

    return panels


__all__ = [
    "BoxParams",
    "DadoSpec",
    "FingerStrategy",
    "PanelSpec",
    "compute_box_panels",
]
