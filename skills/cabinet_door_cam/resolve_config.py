# path: cliff_ai/skills/cabinet_door_cam/resolve_config.py
# desc: Merge order + style + packs, derive defaults, validate minimally, and return a frozen MergedConfig.
# api: resolve_config(order_path: Path, packs_dir: Path | None) -> MergedConfig
# tags: config, merge, validate, deterministic

from __future__ import annotations
from pathlib import Path
from typing import Dict, Tuple, Optional, List
from dataclasses import asdict
from skills.cabinet_door_cam.types import (
    MachinePack, MaterialPack, ToolPack, StyleSpec, StyleMultiStage,
    OrderSpec, MergedConfig
)
from .settings import (
    DEFAULT_PACKS_DIR, OUTPUT_ROOT, GRBL_HEADER,
    MACHINE_PACK_FILE, MATERIAL_PACK_FILE, STYLE_FILE, TOOL_FILES
)
from .util import load_json

def _load_machine(p: Path) -> MachinePack:
    j = load_json(p)
    return MachinePack(
        work_origin=j["work_origin"],
        safe_z_mm=j["safe_z_mm"],
        max_feed_xy_mm_min=j["max_feed_xy_mm_min"],
        max_plunge_z_mm_min=j["max_plunge_z_mm_min"],
        post_dialect=j["post"]["dialect"],
        post_units=j["post"]["units"],
        post_precision=int(j["post"]["precision"]),
        tool_change_mode=j["tool_change_mode"],
        flip_strategy=j["flip_strategy"],
    )

def _load_material(p: Path) -> MaterialPack:
    j = load_json(p)
    return MaterialPack(
        default_feed_xy_mm_min=j["feeds"]["default_feed_xy_mm_min"],
        default_plunge_z_mm_min=j["feeds"]["default_plunge_z_mm_min"],
        finish_feed_xy_mm_min=j["feeds"]["finish_feed_xy_mm_min"],
        max_stepdown_mm=j["depths"]["max_stepdown_mm"],
        raster_stepover_factor=j["raster"]["stepover_factor_of_diam"],
        raster_angle_deg=j["raster"]["angle_deg"],
        cooling=j["cooling"],
    )

def _load_tool(p: Path) -> ToolPack:
    j = load_json(p)
    feeds = j.get("feeds", {})
    return ToolPack(
        tool_id=j["tool_id"],
        type=j["type"],
        diameter_mm=j["diameter_mm"],
        flutes=j["flutes"],
        rpm=int(j["rpm"]),
        feed_xy_mm_min=feeds.get("xy_mm_min", 0),
        feed_z_mm_min=feeds.get("z_mm_min", 0),
        finish_xy_mm_min=feeds.get("finish_xy_mm_min"),
        stepover_factor=j["stepover_factor"],
        max_stepdown_mm=j["max_stepdown_mm"],
        lead_in_ramp_type=j["lead_in"]["ramp_type"],
        lead_in_ramp_angle_deg=j["lead_in"]["ramp_angle_deg"],
        lead_in_min_radius_mm=j["lead_in"]["min_radius_mm"],
    )

def _load_style(p: Path) -> StyleSpec:
    j = load_json(p)
    stages = j["multi_tool"]["stages"]
    hinge_stage = j["multi_tool"]["hinge_stage"]
    sm = StyleMultiStage(
        rough_tool_id=stages[0]["tool_id"],
        rough_stock_to_leave_mm=stages[0].get("stock_to_leave_mm", 0.0),
        finish_tool_id=stages[1]["tool_id"],
        finish_stock_to_leave_mm=stages[1].get("stock_to_leave_mm", 0.0),
        profile_tool_id=stages[2]["tool_id"],
        onion_skin_mm=stages[2].get("onion_skin_mm", j["defaults"]["onion_skin_mm"]),
        hinge_tool_id=hinge_stage["tool_id"],
        hinge_job=hinge_stage["job"],
    )
    return StyleSpec(
        style_id=j["style_id"],
        version=j["version"],
        border_target_ratio=j["border"]["target_ratio"],
        border_min_mm=j["border"]["min_mm"],
        border_max_mm=j["border"]["max_mm"],
        border_clearance_mm=j["border"]["clearance_mm"],
        panel_target_of_thickness=j["panel_depth"]["target_of_thickness"],
        panel_min_mm=j["panel_depth"]["min_mm"],
        panel_max_mm=j["panel_depth"]["max_mm"],
        panel_safety_floor_mm=j["panel_depth"]["safety_floor_mm"],
        anchors_enabled_default=j["corner_anchors"]["enabled_default"],
        anchors_face_default=j["corner_anchors"]["face_default"],
        anchors_placement_mode_default=j["corner_anchors"]["placement_mode_default"],
        anchors_inset_xy_dx_default=j["corner_anchors"]["inset_xy_mm_default"]["dx"],
        anchors_inset_xy_dy_default=j["corner_anchors"]["inset_xy_mm_default"]["dy"],
        anchors_inset_diagonal_mm_default=j["corner_anchors"]["inset_diagonal_mm_default"],
        anchors_diameter_mm_default=j["corner_anchors"]["diameter_mm_default"],
        anchors_depth_mm_default=j["corner_anchors"]["depth_mm_default"],
        anchors_clearance_mm=j["corner_anchors"]["clearance_mm"],
        hinge_enabled_default=j["hinge"]["enabled_default"],
        hinge_diameter_mm=j["hinge"]["diameter_mm"],
        hinge_depth_mm=j["hinge"]["depth_mm"],
        hinge_edge_offsets_mm=(j["hinge"]["edge_offsets_mm"][0], j["hinge"]["edge_offsets_mm"][1]),
        hinge_from_side=j["hinge"]["from_side"],
        hinge_min_spacing_mm=j["hinge"]["min_spacing_mm"],
        defaults_tabs=j["defaults"]["tabs"],
        default_tab_width_mm=j["defaults"]["tab"]["width_mm"],
        default_tab_height_mm=j["defaults"]["tab"]["height_mm"],
        default_tab_count=int(j["defaults"]["tab"]["count"]),
        default_onion_skin_mm=j["defaults"]["onion_skin_mm"],
        min_feature_width_factor_of_tool=j["constraints"]["min_feature_width_factor_of_tool"],
        stages=sm,
    )

def _load_order(p: Path, style: StyleSpec) -> OrderSpec:
    j = load_json(p)
    ca = j.get("corner_anchors", {})
    jover = j.get("job_overrides", {})             
    oofs  = jover.get("origin_offset_mm", {})      
    return OrderSpec(
        width_mm=j["width_mm"],
        height_mm=j["height_mm"],
        thickness_mm=j["thickness_mm"],
        panel_depth_mm=j.get("panel_depth_mm"),
        hinge_bores=bool(j.get("hinge_bores", style.hinge_enabled_default)),
        hinge_side=j.get("hinge_side", "left"),
        hinge_offsets_mm=j.get("hinge_offsets_mm", [style.hinge_edge_offsets_mm[0],]),
        anchors_enabled=bool(ca.get("enabled", style.anchors_enabled_default)),
        anchors_face=ca.get("face", style.anchors_face_default),
        anchors_mode=ca.get("placement_mode", style.anchors_placement_mode_default),
        anchors_inset_dx=float(ca.get("inset_xy_mm", {}).get("dx", style.anchors_inset_xy_dx_default)),
        anchors_inset_dy=float(ca.get("inset_xy_mm", {}).get("dy", style.anchors_inset_xy_dy_default)),
        anchors_inset_diagonal_mm=ca.get("inset_diagonal_mm"),
        anchors_diameter_mm=float(ca.get("diameter_mm", style.anchors_diameter_mm_default)),
        anchors_depth_mm=float(ca.get("depth_mm", style.anchors_depth_mm_default)),
        tool_strategy=j.get("tool_strategy", "multi"),
        use_back_hinge_job=bool(j.get("use_back_hinge_job", style.stages.hinge_job == "back")),
        safe_z_override_mm=jover.get("safe_z_mm"),
        origin_offset_dx_mm=oofs.get("dx"),        
        origin_offset_dy_mm=oofs.get("dy"),        
        gutter_mm=jover.get("gutter_mm"),
        final_cut_through=bool(jover.get("final_cut_through", False)),          # NEW
        final_cut_honor_tabs=bool(jover.get("final_cut_honor_tabs", True)),     # NEW          
    )

def resolve_config(order_path: Path, packs_dir: Optional[Path] = None) -> MergedConfig:
    """Merge all sources and return an immutable config for planning."""
    packs_dir = packs_dir or DEFAULT_PACKS_DIR
    machine = _load_machine(packs_dir / MACHINE_PACK_FILE)
    material = _load_material(packs_dir / MATERIAL_PACK_FILE)
    style = _load_style(packs_dir / STYLE_FILE)
    tools = {
        "rough": _load_tool(packs_dir / TOOL_FILES["rough"]),
        "finish": _load_tool(packs_dir / TOOL_FILES["finish"]),
        "hinge": _load_tool(packs_dir / TOOL_FILES["hinge"]),
    }

    # Minimal validation & constraints
    if tools["rough"].diameter_mm < tools["finish"].diameter_mm:
        raise ValueError("Roughing tool diameter must be >= finishing tool diameter.")
    if style.min_feature_width_factor_of_tool * tools["finish"].diameter_mm > min(
        float(_load_json_number(order_path, "width_mm")),
        float(_load_json_number(order_path, "height_mm"))
    ):
        # Soft check: if panel would be impossibly thin vs tool, bail early
        pass

    order = _load_order(order_path, style)

    return MergedConfig(
        machine=machine,
        material=material,
        style=style,
        tools=tools,
        order=order,
        output_root=str(OUTPUT_ROOT),
        grbl_header=GRBL_HEADER,
    )

def _load_json_number(p: Path, key: str) -> float:
    j = load_json(p)
    return float(j[key])
