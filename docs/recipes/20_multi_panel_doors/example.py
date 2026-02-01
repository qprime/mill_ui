#!/usr/bin/env python3

from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from domains import Domain
from generators import (
    profile_generator,
    flat_pocket_generator,
    raised_panel_generator,
    chamfer_generator,
    ProfileParams,
    FlatPocketParams,
    RaisedPanelParams,
    ChamferParams,
)
from layout_ast.layout import LayoutAST, Sheet


def example_1_two_panel_door():
    print("\n=== Example 1: Two-Panel Door ===")

    door = Domain.from_rectangle(400, 600, center=(200, 300))
    panel_region = door.inset(50).domains[0]


    panels = panel_region.split_horizontal(2, gap_mm=30)

    print(f"Created {len(panels)} panels")
    for i, panel in enumerate(panels):
        print(f"  Panel {i}: bounds = {panel.bounds}, area = {panel.area_mm2:.1f} mm²")


    profile_items = profile_generator(door, ProfileParams(side="outside", depth="through"))
    pocket_items = []
    for panel in panels:
        pocket_items.extend(flat_pocket_generator(panel, FlatPocketParams(depth_mm=6.0)))

    ast = LayoutAST(
        sheet=Sheet(width_mm=450, height_mm=650, thickness_mm=19.0),
        items=tuple(profile_items + pocket_items),
    )

    print(f"Total items: {len(ast.items)}")
    return ast


def example_2_six_panel_door():
    print("\n=== Example 2: Six-Panel Door ===")


    door = Domain.from_rectangle(610, 2032, center=(305, 1016))
    panel_region = door.inset(75).domains[0]


    panels = panel_region.split_grid(rows=3, cols=2, gap_mm=30)

    print(f"Created {len(panels)} panels")
    panel_names = [
        "bottom-left", "bottom-right",
        "middle-left", "middle-right",
        "top-left", "top-right",
    ]
    for i, (panel, name) in enumerate(zip(panels, panel_names)):
        print(f"  Panel {i} ({name}): area = {panel.area_mm2:.1f} mm²")

    profile_items = profile_generator(door, ProfileParams(side="outside", depth="through"))
    pocket_items = []
    for panel in panels:
        pocket_items.extend(flat_pocket_generator(panel, FlatPocketParams(depth_mm=6.0)))

    ast = LayoutAST(
        sheet=Sheet(width_mm=700, height_mm=2100, thickness_mm=19.0),
        items=tuple(profile_items + pocket_items),
    )

    print(f"Total items: {len(ast.items)}")
    return ast


def example_3_raised_panel():
    print("\n=== Example 3: Raised Panel ===")

    door = Domain.from_rectangle(400, 600, center=(200, 300))
    panel_region = door.inset(60).domains[0]

    profile_items = profile_generator(door, ProfileParams(side="outside", depth="through"))

    raised_items = raised_panel_generator(
        panel_region,
        RaisedPanelParams(
            border_width_mm=25.0,
            border_depth_mm=6.0,
            field_depth_mm=2.0,
            angle_degrees=15.0,
        ),
    )

    print(f"Raised panel generated {len(raised_items)} items:")
    for item in raised_items:
        print(f"  - {item.shape_id}: type={item.feature.type}, depth={item.feature.depth}")

    ast = LayoutAST(
        sheet=Sheet(width_mm=450, height_mm=650, thickness_mm=19.0),
        items=tuple(profile_items + raised_items),
    )

    return ast


def example_4_multi_raised_panel():
    print("\n=== Example 4: Multi-Panel Raised Door ===")

    door = Domain.from_rectangle(500, 700, center=(250, 350))
    panel_region = door.inset(65).domains[0]

    panels = panel_region.split_grid(rows=2, cols=2, gap_mm=35)
    print(f"Created {len(panels)} panel cells")

    profile_items = profile_generator(door, ProfileParams(side="outside", depth="through"))

    raised_items = []
    for i, panel in enumerate(panels):
        items = raised_panel_generator(
            panel,
            RaisedPanelParams(
                border_width_mm=20.0,
                border_depth_mm=6.0,
                field_depth_mm=1.5,
            ),
        )
        raised_items.extend(items)
        print(f"  Panel {i}: generated {len(items)} items")

    ast = LayoutAST(
        sheet=Sheet(width_mm=550, height_mm=750, thickness_mm=19.0),
        items=tuple(profile_items + raised_items),
    )

    print(f"Total items: {len(ast.items)}")
    return ast


def example_5_chamfered_door():
    print("\n=== Example 5: Chamfered Door ===")

    door = Domain.from_rectangle(400, 600, center=(200, 300))
    panel_region = door.inset(50).domains[0]

    profile_items = profile_generator(door, ProfileParams(side="outside", depth="through"))
    pocket_items = flat_pocket_generator(panel_region, FlatPocketParams(depth_mm=6.0))

    chamfer_items = chamfer_generator(
        door,
        ChamferParams(
            width_mm=5.0,
            depth_mm=3.0,
            loop_selection="outer_only",
        ),
    )

    print(f"Chamfer items: {len(chamfer_items)}")
    for item in chamfer_items:
        print(f"  - {item.shape_id}: angle={item.feature.chamfer_angle_deg:.1f}°")

    ast = LayoutAST(
        sheet=Sheet(width_mm=450, height_mm=650, thickness_mm=19.0),
        items=tuple(profile_items + pocket_items + chamfer_items),
    )

    return ast


def example_6_french_doors():
    print("\n=== Example 6: French Door Pair ===")

    sheet = Domain.from_rectangle(900, 600, center=(450, 300))


    doors = sheet.split_vertical(2, gap_mm=20)
    print(f"Created {len(doors)} doors")

    all_items = []
    for i, door in enumerate(doors):
        print(f"  Door {i}: width={door.bounds.width:.1f}mm")

        profile_items = profile_generator(door, ProfileParams(side="outside", depth="through"))
        all_items.extend(profile_items)

        panel = door.inset(50).domains[0]
        pocket_items = flat_pocket_generator(panel, FlatPocketParams(depth_mm=6.0))
        all_items.extend(pocket_items)

    ast = LayoutAST(
        sheet=Sheet(width_mm=950, height_mm=650, thickness_mm=19.0),
        items=tuple(all_items),
    )

    print(f"Total items: {len(ast.items)}")
    return ast


def example_7_split_operations_demo():
    print("\n=== Example 7: Split Operations Demo ===")

    domain = Domain.from_rectangle(300, 400, center=(150, 200))
    print(f"Original domain: {domain.bounds.width}mm × {domain.bounds.height}mm")


    h_split = domain.split_horizontal(3, gap_mm=10)
    print(f"\nsplit_horizontal(3, gap_mm=10):")
    print(f"  Expected height each: (400 - 2×10) / 3 = {(400 - 20) / 3:.1f}mm")
    for i, d in enumerate(h_split):
        print(f"  Row {i}: y=[{d.bounds.y_min:.1f}, {d.bounds.y_max:.1f}], height={d.bounds.height:.1f}mm")


    v_split = domain.split_vertical(2, gap_mm=20)
    print(f"\nsplit_vertical(2, gap_mm=20):")
    print(f"  Expected width each: (300 - 1×20) / 2 = {(300 - 20) / 2:.1f}mm")
    for i, d in enumerate(v_split):
        print(f"  Col {i}: x=[{d.bounds.x_min:.1f}, {d.bounds.x_max:.1f}], width={d.bounds.width:.1f}mm")


    g_split = domain.split_grid(rows=2, cols=3, gap_mm=15)
    print(f"\nsplit_grid(rows=2, cols=3, gap_mm=15):")
    print(f"  Expected cell: {(300 - 2 * 15) / 3:.1f}mm × {(400 - 1 * 15) / 2:.1f}mm")
    print(f"  Generated {len(g_split)} cells")
    for i, d in enumerate(g_split):
        row = i // 3
        col = i % 3
        print(f"  Cell [{row},{col}]: center=({d.centroid[0]:.1f}, {d.centroid[1]:.1f})")


def main():
    print("Recipe 20: Multi-Panel Doors with Split Operations")
    print("=" * 60)

    example_1_two_panel_door()
    example_2_six_panel_door()
    example_3_raised_panel()
    example_4_multi_raised_panel()
    example_5_chamfered_door()
    example_6_french_doors()
    example_7_split_operations_demo()

    print("\n" + "=" * 60)
    print("All examples completed successfully!")


if __name__ == "__main__":
    main()
