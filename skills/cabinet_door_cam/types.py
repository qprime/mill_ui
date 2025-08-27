# path: cliff_ai/skills/cabinet_door_cam/types.py
# desc: Minimal typed structures shared across modules. Small, explicit, deterministic.
# api: (types only)
# tags: types, dataclasses, geometry, planning

from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Optional, List, Dict, Tuple

# ---- Config & packs ----

@dataclass(frozen=True)
class MachinePack:
    work_origin: Literal["lower_left_top"]
    safe_z_mm: float
    max_feed_xy_mm_min: float
    max_plunge_z_mm_min: float
    post_dialect: Literal["grbl"]
    post_units: Literal["mm"]
    post_precision: int
    tool_change_mode: Literal["split_files"]
    flip_strategy: Literal["flip_about_Y_keep_left_fence"]

@dataclass(frozen=True)
class MaterialPack:
    default_feed_xy_mm_min: float
    default_plunge_z_mm_min: float
    finish_feed_xy_mm_min: float
    max_stepdown_mm: float
    raster_stepover_factor: float
    raster_angle_deg: float
    cooling: Literal["dry"]

@dataclass(frozen=True)
class ToolPack:
    tool_id: str
    type: Literal["flat_endmill", "boring_bit"]
    diameter_mm: float
    flutes: int
    rpm: int
    feed_xy_mm_min: float
    feed_z_mm_min: float
    finish_xy_mm_min: Optional[float]
    stepover_factor: float
    max_stepdown_mm: float
    lead_in_ramp_type: Literal["helical"]
    lead_in_ramp_angle_deg: float
    lead_in_min_radius_mm: float

@dataclass(frozen=True)
class StyleMultiStage:
    rough_tool_id: str
    rough_stock_to_leave_mm: float
    finish_tool_id: str
    finish_stock_to_leave_mm: float
    profile_tool_id: str
    onion_skin_mm: float
    hinge_tool_id: str
    hinge_job: Literal["back"]

@dataclass(frozen=True)
class StyleSpec:
    style_id: str
    version: int
    border_target_ratio: float
    border_min_mm: float
    border_max_mm: float
    border_clearance_mm: float
    panel_target_of_thickness: float
    panel_min_mm: float
    panel_max_mm: float
    panel_safety_floor_mm: float
    anchors_enabled_default: bool
    anchors_face_default: Literal["front", "back"]
    anchors_placement_mode_default: Literal["xy", "diagonal"]
    anchors_inset_xy_dx_default: float
    anchors_inset_xy_dy_default: float
    anchors_inset_diagonal_mm_default: float
    anchors_diameter_mm_default: float
    anchors_depth_mm_default: float
    anchors_clearance_mm: float
    hinge_enabled_default: bool
    hinge_diameter_mm: float
    hinge_depth_mm: float
    hinge_edge_offsets_mm: Tuple[float, str | float]  # e.g. (100.0, "mirror")
    hinge_from_side: Literal["left_right"]
    hinge_min_spacing_mm: float
    defaults_tabs: bool
    default_tab_width_mm: float
    default_tab_height_mm: float
    default_tab_count: int
    default_onion_skin_mm: float
    min_feature_width_factor_of_tool: float
    stages: StyleMultiStage

@dataclass(frozen=True)
class OrderSpec:
    width_mm: float
    height_mm: float
    thickness_mm: float
    panel_depth_mm: Optional[float]
    hinge_bores: bool
    hinge_side: Literal["left", "right"]
    hinge_offsets_mm: List[float]  # top/bottom or list positions; supports "mirror" in style
    anchors_enabled: bool
    anchors_face: Literal["front", "back"]
    anchors_mode: Literal["xy", "diagonal"]
    anchors_inset_dx: float
    anchors_inset_dy: float
    anchors_inset_diagonal_mm: Optional[float]
    anchors_diameter_mm: float
    anchors_depth_mm: float
    tool_strategy: Literal["multi"]
    use_back_hinge_job: bool
    safe_z_override_mm: Optional[float]
    origin_offset_dx_mm: float | None  
    origin_offset_dy_mm: float | None  
    gutter_mm: float | None            

@dataclass(frozen=True)
class MergedConfig:
    machine: MachinePack
    material: MaterialPack
    style: StyleSpec
    tools: Dict[str, ToolPack]         # keys: "rough","finish","hinge"
    order: OrderSpec
    output_root: str                   # resolved string path
    grbl_header: str                   # modal line to emit

# ---- Geometry primitives ----

@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    w: float
    h: float

@dataclass(frozen=True)
class Circle:
    x: float
    y: float
    r: float
    depth_mm: float

@dataclass(frozen=True)
class Geometry:
    stock_rect: Rect
    border_rect: Rect
    panel_rect: Rect
    panel_depth_mm: float
    anchors: List[Circle]           # may be empty
    hinge_centers: List[Tuple[float, float]]  # front-view XY
    hinge_diameter_mm: float
    hinge_depth_mm: float

# ---- Planning ----

MoveKind = Literal["rapid", "cut", "plunge", "retract", "set_feed", "set_spindle", "comment"]

@dataclass(frozen=True)
class Move:
    kind: MoveKind
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None
    f: Optional[float] = None
    s: Optional[int] = None
    text: Optional[str] = None

@dataclass(frozen=True)
class JobPlan:
    name: str
    tool: ToolPack
    moves: List[Move]
    face: Literal["front", "back"]
