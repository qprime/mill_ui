from __future__ import annotations

import math
from typing import Literal

from assembly.topology import AssemblyTopology, FaceSpec, MatingEdge, MatingFeature


def _rect_polygon(width: float, height: float) -> tuple[tuple[float, float], ...]:
    return (
        (0.0, 0.0),
        (width, 0.0),
        (width, height),
        (0.0, height),
    )


def box_topology(
    width_mm: float,
    depth_mm: float,
    height_mm: float,
    thickness_mm: float,
    joinery: Literal["butt", "finger"],
    include_top: bool = False,
    include_bottom: bool = True,
    bottom_style: Literal["captured", "finger", "dado"] = "captured",
    top_style: Literal["captured", "finger", "dado"] = "captured",
    dado_inset_mm: float = 0.0,
    dado_drop_mm: float = 0.0,
) -> AssemblyTopology:
    w = width_mm
    d = depth_mm
    h = height_mm
    t = thickness_mm
    dado_depth = t / 2

    if joinery == "butt":
        bottom_finger = False
        top_finger = False
    else:
        bottom_finger = bottom_style == "finger"
        top_finger = top_style == "finger"

    bottom_dado = bottom_style == "dado"
    top_dado = top_style == "dado"

    bottom_reduction = 0 if (bottom_finger or bottom_dado) else t
    top_reduction = 0 if (top_finger or top_dado) else t

    front_back_width = w
    front_back_height = h - bottom_reduction - top_reduction

    side_width = d - 2 * t
    side_height = h - bottom_reduction - top_reduction

    if bottom_style == "finger":
        bottom_width = w
        bottom_height = d
    elif bottom_style == "dado":
        bottom_width = w - 2 * t + 2 * dado_depth
        bottom_height = d - 2 * t + 2 * dado_depth
    else:
        bottom_width = w - 2 * t
        bottom_height = d - 2 * t

    if top_style == "finger":
        lid_width = w
        lid_height = d
    elif top_style == "dado":
        lid_width = w - 2 * t + 2 * dado_depth
        lid_height = d - 2 * t + 2 * dado_depth
    else:
        lid_width = w - 2 * t
        lid_height = d - 2 * t

    faces: dict[str, FaceSpec] = {}

    faces["front"] = FaceSpec(
        name="front",
        polygon=_rect_polygon(front_back_width, front_back_height),
        thickness_mm=t,
    )
    faces["back"] = FaceSpec(
        name="back",
        polygon=_rect_polygon(front_back_width, front_back_height),
        thickness_mm=t,
    )
    faces["left_side"] = FaceSpec(
        name="left_side",
        polygon=_rect_polygon(side_width, side_height),
        thickness_mm=t,
    )
    faces["right_side"] = FaceSpec(
        name="right_side",
        polygon=_rect_polygon(side_width, side_height),
        thickness_mm=t,
    )

    if include_bottom:
        faces["bottom"] = FaceSpec(
            name="bottom",
            polygon=_rect_polygon(bottom_width, bottom_height),
            thickness_mm=t,
        )

    if include_top:
        faces["top"] = FaceSpec(
            name="top",
            polygon=_rect_polygon(lid_width, lid_height),
            thickness_mm=t,
        )

    mating_edges: list[MatingEdge] = []

    mating_edges.append(MatingEdge(
        face_a="front",
        edge_index_a=3,
        face_b="left_side",
        edge_index_b=1,
        dihedral_angle_deg=90.0,
    ))
    mating_edges.append(MatingEdge(
        face_a="front",
        edge_index_a=1,
        face_b="right_side",
        edge_index_b=3,
        dihedral_angle_deg=90.0,
    ))
    mating_edges.append(MatingEdge(
        face_a="back",
        edge_index_a=1,
        face_b="left_side",
        edge_index_b=3,
        dihedral_angle_deg=90.0,
    ))
    mating_edges.append(MatingEdge(
        face_a="back",
        edge_index_a=3,
        face_b="right_side",
        edge_index_b=1,
        dihedral_angle_deg=90.0,
    ))

    if include_bottom and bottom_finger:
        mating_edges.append(MatingEdge(
            face_a="front",
            edge_index_a=0,
            face_b="bottom",
            edge_index_b=0,
            dihedral_angle_deg=90.0,
        ))
        mating_edges.append(MatingEdge(
            face_a="back",
            edge_index_a=0,
            face_b="bottom",
            edge_index_b=2,
            dihedral_angle_deg=90.0,
        ))
        mating_edges.append(MatingEdge(
            face_a="left_side",
            edge_index_a=0,
            face_b="bottom",
            edge_index_b=3,
            dihedral_angle_deg=90.0,
        ))
        mating_edges.append(MatingEdge(
            face_a="right_side",
            edge_index_a=0,
            face_b="bottom",
            edge_index_b=1,
            dihedral_angle_deg=90.0,
        ))

    if include_top and top_finger:
        mating_edges.append(MatingEdge(
            face_a="front",
            edge_index_a=2,
            face_b="top",
            edge_index_b=0,
            dihedral_angle_deg=90.0,
        ))
        mating_edges.append(MatingEdge(
            face_a="back",
            edge_index_a=2,
            face_b="top",
            edge_index_b=2,
            dihedral_angle_deg=90.0,
        ))
        mating_edges.append(MatingEdge(
            face_a="left_side",
            edge_index_a=2,
            face_b="top",
            edge_index_b=3,
            dihedral_angle_deg=90.0,
        ))
        mating_edges.append(MatingEdge(
            face_a="right_side",
            edge_index_a=2,
            face_b="top",
            edge_index_b=1,
            dihedral_angle_deg=90.0,
        ))

    mating_features: list[MatingFeature] = []

    if include_bottom and bottom_dado:
        dado_params = {
            "position_from_edge_mm": dado_inset_mm,
            "width_mm": t,
            "depth_mm": dado_depth,
            "edge": "bottom",
        }
        for face in ["front", "back", "left_side", "right_side"]:
            mating_features.append(MatingFeature(
                face=face,
                kind="dado",
                params=dado_params,
                mates_with="bottom",
            ))

    if include_top and top_dado:
        dado_params = {
            "position_from_edge_mm": dado_drop_mm,
            "width_mm": t,
            "depth_mm": dado_depth,
            "edge": "top",
        }
        for face in ["front", "back", "left_side", "right_side"]:
            mating_features.append(MatingFeature(
                face=face,
                kind="dado",
                params=dado_params,
                mates_with="top",
            ))

    return AssemblyTopology(
        faces=faces,
        mating_edges=tuple(mating_edges),
        mating_features=tuple(mating_features),
    )


def pyramid_topology(
    base_mm: float,
    slant_height_mm: float,
    thickness_mm: float,
) -> AssemblyTopology:
    half_base = base_mm / 2
    apothem = math.sqrt(slant_height_mm**2 - half_base**2) if slant_height_mm > half_base else slant_height_mm

    triangle_base = base_mm
    triangle_height = slant_height_mm

    tri_polygon = (
        (0.0, 0.0),
        (triangle_base, 0.0),
        (triangle_base / 2, triangle_height),
    )

    base_polygon = _rect_polygon(base_mm, base_mm)

    faces: dict[str, FaceSpec] = {
        "base": FaceSpec(name="base", polygon=base_polygon, thickness_mm=thickness_mm),
        "face_n": FaceSpec(name="face_n", polygon=tri_polygon, thickness_mm=thickness_mm),
        "face_e": FaceSpec(name="face_e", polygon=tri_polygon, thickness_mm=thickness_mm),
        "face_s": FaceSpec(name="face_s", polygon=tri_polygon, thickness_mm=thickness_mm),
        "face_w": FaceSpec(name="face_w", polygon=tri_polygon, thickness_mm=thickness_mm),
    }

    dihedral = math.degrees(math.atan2(apothem, half_base))

    mating_edges = (
        MatingEdge(face_a="face_n", edge_index_a=1, face_b="face_e", edge_index_b=2, dihedral_angle_deg=dihedral),
        MatingEdge(face_a="face_e", edge_index_a=1, face_b="face_s", edge_index_b=2, dihedral_angle_deg=dihedral),
        MatingEdge(face_a="face_s", edge_index_a=1, face_b="face_w", edge_index_b=2, dihedral_angle_deg=dihedral),
        MatingEdge(face_a="face_w", edge_index_a=1, face_b="face_n", edge_index_b=2, dihedral_angle_deg=dihedral),
        MatingEdge(face_a="base", edge_index_a=2, face_b="face_n", edge_index_b=0, dihedral_angle_deg=90.0),
        MatingEdge(face_a="base", edge_index_a=1, face_b="face_e", edge_index_b=0, dihedral_angle_deg=90.0),
        MatingEdge(face_a="base", edge_index_a=0, face_b="face_s", edge_index_b=0, dihedral_angle_deg=90.0),
        MatingEdge(face_a="base", edge_index_a=3, face_b="face_w", edge_index_b=0, dihedral_angle_deg=90.0),
    )

    return AssemblyTopology(
        faces=faces,
        mating_edges=mating_edges,
    )


def frameless_cabinet_topology(
    width_mm: float,
    depth_mm: float,
    height_mm: float,
    thickness_mm: float,
    joinery: Literal["butt", "finger"] = "butt",
    cap_style: Literal["between_sides", "over_sides"] = "between_sides",
    include_top: bool = True,
    include_bottom: bool = True,
    back: Literal["none", "captured"] = "none",
    back_thickness_mm: float | None = None,
    back_inset_mm: float = 0.0,
    back_dado_depth_mm: float | None = None,
    fixed_shelves: int = 0,
    shelf_dado_depth_mm: float | None = None,
    shelf_setback_front_mm: float = 0.0,
    shelf_setback_back_mm: float = 0.0,
    vertical_partitions: int = 0,
    partition_dado_depth_mm: float | None = None,
) -> AssemblyTopology:
    w = width_mm
    d = depth_mm
    h = height_mm
    t = thickness_mm

    if back_thickness_mm is None:
        back_thickness_mm = t
    if back_dado_depth_mm is None:
        back_dado_depth_mm = t / 2
    if shelf_dado_depth_mm is None:
        shelf_dado_depth_mm = t / 2
    if partition_dado_depth_mm is None:
        partition_dado_depth_mm = t / 2

    faces: dict[str, FaceSpec] = {}
    mating_edges: list[MatingEdge] = []
    mating_features: list[MatingFeature] = []

    side_width = d
    side_height = h
    faces["left_side"] = FaceSpec(
        name="left_side",
        polygon=_rect_polygon(side_width, side_height),
        thickness_mm=t,
    )
    faces["right_side"] = FaceSpec(
        name="right_side",
        polygon=_rect_polygon(side_width, side_height),
        thickness_mm=t,
    )

    if cap_style == "between_sides":
        cap_width = w - 2 * t
    else:
        cap_width = w

    if back == "captured":
        cap_depth = d - back_inset_mm
    else:
        cap_depth = d

    if include_top:
        faces["top"] = FaceSpec(
            name="top",
            polygon=_rect_polygon(cap_width, cap_depth),
            thickness_mm=t,
        )
    if include_bottom:
        faces["bottom"] = FaceSpec(
            name="bottom",
            polygon=_rect_polygon(cap_width, cap_depth),
            thickness_mm=t,
        )

    if back == "captured":
        back_width = w - 2 * t + 2 * back_dado_depth_mm
        back_height = h
        if include_top:
            back_height -= t
        if include_bottom:
            back_height -= t
        back_height += 2 * back_dado_depth_mm

        faces["back"] = FaceSpec(
            name="back",
            polygon=_rect_polygon(back_width, back_height),
            thickness_mm=back_thickness_mm,
        )

        back_dado_params = {
            "position_from_edge_mm": back_inset_mm,
            "width_mm": back_thickness_mm,
            "depth_mm": back_dado_depth_mm,
            "edge": "top",
        }
        mating_features.append(MatingFeature(
            face="left_side",
            kind="dado",
            params=back_dado_params,
            mates_with="back",
        ))
        mating_features.append(MatingFeature(
            face="right_side",
            kind="dado",
            params=back_dado_params,
            mates_with="back",
        ))
        if include_top:
            mating_features.append(MatingFeature(
                face="top",
                kind="dado",
                params={
                    "position_from_edge_mm": 0,
                    "width_mm": back_thickness_mm,
                    "depth_mm": back_dado_depth_mm,
                    "edge": "top",
                },
                mates_with="back",
            ))
        if include_bottom:
            mating_features.append(MatingFeature(
                face="bottom",
                kind="dado",
                params={
                    "position_from_edge_mm": 0,
                    "width_mm": back_thickness_mm,
                    "depth_mm": back_dado_depth_mm,
                    "edge": "top",
                },
                mates_with="back",
            ))

    if joinery == "finger":
        if cap_style == "between_sides":
            if include_top:
                mating_edges.append(MatingEdge(
                    face_a="left_side",
                    edge_index_a=2,
                    face_b="top",
                    edge_index_b=3,
                    dihedral_angle_deg=90.0,
                ))
                mating_edges.append(MatingEdge(
                    face_a="right_side",
                    edge_index_a=2,
                    face_b="top",
                    edge_index_b=1,
                    dihedral_angle_deg=90.0,
                ))
            if include_bottom:
                mating_edges.append(MatingEdge(
                    face_a="left_side",
                    edge_index_a=0,
                    face_b="bottom",
                    edge_index_b=3,
                    dihedral_angle_deg=90.0,
                ))
                mating_edges.append(MatingEdge(
                    face_a="right_side",
                    edge_index_a=0,
                    face_b="bottom",
                    edge_index_b=1,
                    dihedral_angle_deg=90.0,
                ))
        else:
            if include_top:
                mating_edges.append(MatingEdge(
                    face_a="top",
                    edge_index_a=3,
                    face_b="left_side",
                    edge_index_b=2,
                    dihedral_angle_deg=90.0,
                ))
                mating_edges.append(MatingEdge(
                    face_a="top",
                    edge_index_a=1,
                    face_b="right_side",
                    edge_index_b=2,
                    dihedral_angle_deg=90.0,
                ))
            if include_bottom:
                mating_edges.append(MatingEdge(
                    face_a="bottom",
                    edge_index_a=3,
                    face_b="left_side",
                    edge_index_b=0,
                    dihedral_angle_deg=90.0,
                ))
                mating_edges.append(MatingEdge(
                    face_a="bottom",
                    edge_index_a=1,
                    face_b="right_side",
                    edge_index_b=0,
                    dihedral_angle_deg=90.0,
                ))

    interior_height = h
    if include_top:
        interior_height -= t
    if include_bottom:
        interior_height -= t

    if fixed_shelves > 0:
        shelf_width = w - 2 * t + 2 * shelf_dado_depth_mm
        shelf_depth = d - shelf_setback_front_mm - shelf_setback_back_mm
        if back == "captured":
            shelf_depth -= back_inset_mm

        spacing = interior_height / (fixed_shelves + 1)

        for i in range(fixed_shelves):
            shelf_name = f"shelf_{i + 1:02d}"
            faces[shelf_name] = FaceSpec(
                name=shelf_name,
                polygon=_rect_polygon(shelf_width, shelf_depth),
                thickness_mm=t,
            )

            shelf_position = spacing * (i + 1)
            if include_bottom:
                shelf_position += t

            shelf_dado_params = {
                "position_from_edge_mm": shelf_position - t / 2,
                "width_mm": t,
                "depth_mm": shelf_dado_depth_mm,
                "edge": "bottom",
            }
            mating_features.append(MatingFeature(
                face="left_side",
                kind="dado",
                params=shelf_dado_params,
                mates_with=shelf_name,
            ))
            mating_features.append(MatingFeature(
                face="right_side",
                kind="dado",
                params=shelf_dado_params,
                mates_with=shelf_name,
            ))

    interior_width = w - 2 * t

    if vertical_partitions > 0:
        partition_height = interior_height + 2 * partition_dado_depth_mm
        partition_depth = d
        if back == "captured":
            partition_depth -= back_inset_mm

        spacing = interior_width / (vertical_partitions + 1)

        for i in range(vertical_partitions):
            partition_name = f"partition_{i + 1:02d}"
            faces[partition_name] = FaceSpec(
                name=partition_name,
                polygon=_rect_polygon(partition_depth, partition_height),
                thickness_mm=t,
            )

            partition_position = spacing * (i + 1) + t

            partition_dado_params = {
                "position_from_edge_mm": partition_position - t / 2,
                "width_mm": t,
                "depth_mm": partition_dado_depth_mm,
                "edge": "bottom",
            }
            if include_top:
                mating_features.append(MatingFeature(
                    face="top",
                    kind="dado",
                    params=partition_dado_params,
                    mates_with=partition_name,
                ))
            if include_bottom:
                mating_features.append(MatingFeature(
                    face="bottom",
                    kind="dado",
                    params=partition_dado_params,
                    mates_with=partition_name,
                ))

    return AssemblyTopology(
        faces=faces,
        mating_edges=tuple(mating_edges),
        mating_features=tuple(mating_features),
    )


def prism_topology(
    base_polygon: tuple[tuple[float, float], ...],
    height_mm: float,
    thickness_mm: float,
) -> AssemblyTopology:
    n = len(base_polygon)
    faces: dict[str, FaceSpec] = {}

    faces["base"] = FaceSpec(
        name="base",
        polygon=base_polygon,
        thickness_mm=thickness_mm,
    )
    faces["top"] = FaceSpec(
        name="top",
        polygon=base_polygon,
        thickness_mm=thickness_mm,
    )

    for i in range(n):
        p0 = base_polygon[i]
        p1 = base_polygon[(i + 1) % n]
        edge_length = math.sqrt((p1[0] - p0[0])**2 + (p1[1] - p0[1])**2)

        side_polygon = _rect_polygon(edge_length, height_mm)
        faces[f"side_{i}"] = FaceSpec(
            name=f"side_{i}",
            polygon=side_polygon,
            thickness_mm=thickness_mm,
        )

    mating_edges: list[MatingEdge] = []

    for i in range(n):
        next_i = (i + 1) % n
        mating_edges.append(MatingEdge(
            face_a=f"side_{i}",
            edge_index_a=1,
            face_b=f"side_{next_i}",
            edge_index_b=3,
            dihedral_angle_deg=180.0 - (360.0 / n),
        ))

    for i in range(n):
        mating_edges.append(MatingEdge(
            face_a=f"side_{i}",
            edge_index_a=0,
            face_b="base",
            edge_index_b=i,
            dihedral_angle_deg=90.0,
        ))
        mating_edges.append(MatingEdge(
            face_a=f"side_{i}",
            edge_index_a=2,
            face_b="top",
            edge_index_b=i,
            dihedral_angle_deg=90.0,
        ))

    return AssemblyTopology(
        faces=faces,
        mating_edges=tuple(mating_edges),
    )


__all__ = [
    "box_topology",
    "frameless_cabinet_topology",
    "pyramid_topology",
    "prism_topology",
]
