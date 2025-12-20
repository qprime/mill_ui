#!/usr/bin/env python3
"""Generate SVG, STL, and G-code outputs for all recipes.

This script creates reference outputs for each recipe to demonstrate
the complete workflow and provide visual validation.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from layout_ast.layout import LayoutAST, Sheet, Item, Geometry, Placement, Feature
from adapters.ast_to_removal import ast_to_removal_intents
from adapters.removal_to_planner import removal_intents_to_v1_hints
from adapters.ast_to_cad import items_to_shape_dicts
from export.blueprint_svg import render_blueprint_svg
from cad.export.stl import export_stl
from cam.config import Config
from cam.planner.passes import plan_passes
from cam.post.gcode import write_gcode
from cam.model.stock import Stock
from cam.model.material import Material
from cam.model.machine import Machine


def generate_recipe_01():
    """Recipe 01: Simple Profile Cut."""
    print("Generating Recipe 01: Simple Profile Cut...")

    # Create LayoutAST
    ast = LayoutAST(
        sheet=Sheet(width_mm=450, height_mm=650, thickness_mm=19),
        items=(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 200, "h_mm": 150}),
                placement=Placement(center_xy_mm=(225, 325)),
                feature=Feature(type="profile", side="outside", depth="through"),
                shape_id="part",
            ),
        ),
    )

    output_dir = Path(__file__).parent / "01_simple_profile"
    output_dir.mkdir(exist_ok=True)

    # Generate SVG blueprint
    svg_string = render_blueprint_svg(ast, theme="light")
    (output_dir / "simple_profile.blueprint.light.svg").write_text(svg_string, encoding="utf-8")
    print(f"  ✓ SVG: {output_dir / 'simple_profile.blueprint.light.svg'}")

    # Generate STL
    shapes = items_to_shape_dicts(ast.items)
    export_stl(
        shapes=shapes,
        sheet_thickness_mm=ast.sheet.thickness_mm,
        output_path=output_dir / "simple_profile.stl",
    )
    print(f"  ✓ STL: {output_dir / 'simple_profile.stl'}")

    # Generate G-code
    intents = ast_to_removal_intents(ast)
    tool_db = [
        {
            "name": "6mm_endmill",
            "diameter": 6.0,
            "kind": "flat",
            "rpm": 18000,
            "feed_xy": 2000,
            "feed_z": 300,
        }
    ]

    config = Config(safe_z_mm=5.0, merge_epsilon_mm=0.1)
    material = Material(name="MDF")
    machine = Machine()
    stock = Stock(width=450, height=650, thickness=19)

    hints = removal_intents_to_v1_hints(intents, kerf_width_mm=3.175, min_channel_width_mm=6.0)
    passes, summary = plan_passes(
        hints,
        config=config,
        tool_db=tool_db,
        material=material,
        machine=machine,
        stock=stock,
    )

    # Generate G-code from all passes
    all_gcode_lines = []
    for pass_dict in passes:
        moves = pass_dict["moves"]
        if not moves:
            continue
        gcode = write_gcode(moves, safe_z=config.safe_z_mm)
        all_gcode_lines.extend(gcode.split("\n"))

    final_gcode = "\n".join(all_gcode_lines)
    (output_dir / "simple_profile.nc").write_text(final_gcode, encoding="utf-8")
    print(f"  ✓ G-code: {output_dir / 'simple_profile.nc'} ({len(final_gcode.splitlines())} lines)")


def generate_recipe_02():
    """Recipe 02: Pocket with Cleanup."""
    print("\nGenerating Recipe 02: Pocket with Cleanup...")

    # Create LayoutAST
    ast = LayoutAST(
        sheet=Sheet(width_mm=450, height_mm=650, thickness_mm=19),
        items=(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 400, "h_mm": 600}),
                placement=Placement(center_xy_mm=(225, 325)),
                feature=Feature(type="profile", side="outside", depth="through"),
                shape_id="door_outer",
            ),
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 300, "h_mm": 500}),
                placement=Placement(center_xy_mm=(225, 325)),
                feature=Feature(type="pocket", depth=6.0, depth_mm=6.0),
                shape_id="panel_pocket",
            ),
        ),
    )

    output_dir = Path(__file__).parent / "02_pocket_with_cleanup"
    output_dir.mkdir(exist_ok=True)

    # Generate SVG blueprint
    svg_string = render_blueprint_svg(ast, theme="light")
    (output_dir / "pocket_with_cleanup.blueprint.light.svg").write_text(svg_string, encoding="utf-8")
    print(f"  ✓ SVG: {output_dir / 'pocket_with_cleanup.blueprint.light.svg'}")

    # Generate STL
    shapes = items_to_shape_dicts(ast.items)
    export_stl(
        shapes=shapes,
        sheet_thickness_mm=ast.sheet.thickness_mm,
        output_path=output_dir / "pocket_with_cleanup.stl",
    )
    print(f"  ✓ STL: {output_dir / 'pocket_with_cleanup.stl'}")

    # Generate G-code
    intents = ast_to_removal_intents(ast)
    tool_db = [
        {
            "name": "6mm_endmill",
            "diameter": 6.0,
            "kind": "flat",
            "rpm": 18000,
            "feed_xy": 2000,
            "feed_z": 300,
        }
    ]

    config = Config(safe_z_mm=5.0, merge_epsilon_mm=0.1)
    material = Material(name="MDF")
    machine = Machine()
    stock = Stock(width=450, height=650, thickness=19)

    hints = removal_intents_to_v1_hints(intents, kerf_width_mm=3.175, min_channel_width_mm=6.0)
    passes, summary = plan_passes(
        hints,
        config=config,
        tool_db=tool_db,
        material=material,
        machine=machine,
        stock=stock,
    )

    # Generate G-code from all passes
    all_gcode_lines = []
    for pass_dict in passes:
        moves = pass_dict["moves"]
        if not moves:
            continue
        gcode = write_gcode(moves, safe_z=config.safe_z_mm)
        all_gcode_lines.extend(gcode.split("\n"))

    final_gcode = "\n".join(all_gcode_lines)
    (output_dir / "pocket_with_cleanup.nc").write_text(final_gcode, encoding="utf-8")
    print(f"  ✓ G-code: {output_dir / 'pocket_with_cleanup.nc'} ({len(final_gcode.splitlines())} lines)")


def generate_recipe_03():
    """Recipe 03: Shaker Door Template."""
    print("\nGenerating Recipe 03: Shaker Door Template...")

    from templates import Shaker

    # Generate Shaker door using template
    ast = Shaker.expand_to_ast(
        params={
            "outer_w": 400.0,
            "outer_h": 600.0,
            "stile_w": 50.0,
            "rail_h": 50.0,
            "panel_recess": 6.0,
        },
        sheet_thickness_mm=19.0,
    )

    output_dir = Path(__file__).parent / "03_shaker_door_template"
    output_dir.mkdir(exist_ok=True)

    # Generate SVG blueprint
    svg_string = render_blueprint_svg(ast, theme="light")
    (output_dir / "shaker_door.blueprint.light.svg").write_text(svg_string, encoding="utf-8")
    print(f"  ✓ SVG: {output_dir / 'shaker_door.blueprint.light.svg'}")

    # Generate STL
    shapes = items_to_shape_dicts(ast.items)
    export_stl(
        shapes=shapes,
        sheet_thickness_mm=ast.sheet.thickness_mm,
        output_path=output_dir / "shaker_door.stl",
    )
    print(f"  ✓ STL: {output_dir / 'shaker_door.stl'}")

    # Generate G-code
    intents = ast_to_removal_intents(ast)
    tool_db = [
        {
            "name": "6mm_endmill",
            "diameter": 6.0,
            "kind": "flat",
            "rpm": 18000,
            "feed_xy": 2000,
            "feed_z": 300,
        }
    ]

    config = Config(safe_z_mm=5.0, merge_epsilon_mm=0.1)
    material = Material(name="MDF")
    machine = Machine()
    stock = Stock(
        width=ast.sheet.width_mm,
        height=ast.sheet.height_mm,
        thickness=ast.sheet.thickness_mm,
    )

    hints = removal_intents_to_v1_hints(intents, kerf_width_mm=3.175, min_channel_width_mm=6.0)
    passes, summary = plan_passes(
        hints,
        config=config,
        tool_db=tool_db,
        material=material,
        machine=machine,
        stock=stock,
    )

    # Generate G-code from all passes
    all_gcode_lines = []
    for pass_dict in passes:
        moves = pass_dict["moves"]
        if not moves:
            continue
        gcode = write_gcode(moves, safe_z=config.safe_z_mm)
        all_gcode_lines.extend(gcode.split("\n"))

    final_gcode = "\n".join(all_gcode_lines)
    (output_dir / "shaker_door.nc").write_text(final_gcode, encoding="utf-8")
    print(f"  ✓ G-code: {output_dir / 'shaker_door.nc'} ({len(final_gcode.splitlines())} lines)")


def main():
    """Generate all recipe outputs."""
    print("=" * 60)
    print("Generating Recipe Outputs (SVG, STL, G-code)")
    print("=" * 60)

    try:
        generate_recipe_01()
        generate_recipe_02()
        generate_recipe_03()

        print("\n" + "=" * 60)
        print("✓ All recipe outputs generated successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ Error generating outputs: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
