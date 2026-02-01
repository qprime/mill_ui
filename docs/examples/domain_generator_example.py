#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from domains import Domain, MultiDomain
from generators import (
    FlatPocketParams,
    ProfileParams,
    WaveParams,
    GridParams,
    BeadParams,
    flat_pocket_generator,
    profile_generator,
    wave_generator,
    grid_generator,
    bead_generator,
)
from layout_ast.layout import LayoutAST, Sheet, Item
from adapters.ast_to_removal import ast_to_removal_intents


def create_shaker_door(
    outer_w: float = 400.0,
    outer_h: float = 600.0,
    stile_w: float = 50.0,
    rail_h: float = 50.0,
    panel_recess: float = 6.0,
    sheet_thickness: float = 19.0,
) -> LayoutAST:
    print("\n=== Creating Shaker Door ===")
    print(f"Dimensions: {outer_w}mm x {outer_h}mm")
    print(f"Frame: {stile_w}mm stiles, {rail_h}mm rails")
    print(f"Panel recess: {panel_recess}mm")


    outer_domain = Domain.from_rectangle(
        width_mm=outer_w,
        height_mm=outer_h,
        center=(outer_w / 2, outer_h / 2),
    )
    print(f"\nOuter domain: {outer_domain.bounds.width}mm x {outer_domain.bounds.height}mm")
    print(f"  Area: {outer_domain.area_mm2:.0f}mm²")


    panel_result = outer_domain.inset(stile_w)

    if panel_result.is_empty:
        raise ValueError(f"Frame too wide: {stile_w}mm inset produces empty result")

    panel_domain = panel_result.domains[0]
    print(f"\nPanel domain: {panel_domain.bounds.width}mm x {panel_domain.bounds.height}mm")
    print(f"  Area: {panel_domain.area_mm2:.0f}mm²")


    profile_items = profile_generator(
        outer_domain,
        ProfileParams(
            side="outside",
            depth="through",
            loop_selection="outer_only",
        ),
    )
    print(f"\nProfile generator: {len(profile_items)} item(s)")


    pocket_items = flat_pocket_generator(
        panel_domain,
        FlatPocketParams(depth_mm=panel_recess),
    )
    print(f"Pocket generator: {len(pocket_items)} item(s)")


    all_items = profile_items + pocket_items


    margin = 25.0
    ast = LayoutAST(
        sheet=Sheet(
            width_mm=outer_w + 2 * margin,
            height_mm=outer_h + 2 * margin,
            thickness_mm=sheet_thickness,
        ),
        items=tuple(all_items),
    )

    print(f"\nLayoutAST created:")
    print(f"  Sheet: {ast.sheet.width_mm}mm x {ast.sheet.height_mm}mm x {ast.sheet.thickness_mm}mm")
    print(f"  Items: {len(ast.items)}")

    return ast


def create_wave_panel(
    width: float = 300.0,
    height: float = 200.0,
    amplitude: float = 8.0,
    wavelength: float = 25.0,
    pattern_depth: float = 2.0,
    sheet_thickness: float = 19.0,
) -> LayoutAST:
    print("\n=== Creating Wave Panel ===")
    print(f"Dimensions: {width}mm x {height}mm")
    print(f"Wave: {amplitude}mm amplitude, {wavelength}mm wavelength")


    panel = Domain.from_rectangle(width, height, center=(width / 2, height / 2))


    profile_items = profile_generator(
        panel,
        ProfileParams(side="outside", depth="through"),
    )


    wave_items = wave_generator(
        panel,
        WaveParams(
            amplitude_mm=amplitude,
            wavelength_mm=wavelength,
            depth_mm=pattern_depth,
            tool_width_mm=3.175,
        ),
    )

    print(f"\nGenerated {len(wave_items)} wave segments")


    margin = 25.0
    ast = LayoutAST(
        sheet=Sheet(
            width_mm=width + 2 * margin,
            height_mm=height + 2 * margin,
            thickness_mm=sheet_thickness,
        ),
        items=tuple(profile_items + wave_items),
    )

    print(f"LayoutAST: {len(ast.items)} total items")

    return ast


def create_beaded_frame_door(
    outer_w: float = 400.0,
    outer_h: float = 600.0,
    frame_width: float = 60.0,
    bead_offset: float = 15.0,
    bead_width: float = 6.0,
    bead_depth: float = 3.0,
    panel_recess: float = 6.0,
    sheet_thickness: float = 19.0,
) -> LayoutAST:
    print("\n=== Creating Beaded Frame Door ===")
    print(f"Dimensions: {outer_w}mm x {outer_h}mm")
    print(f"Frame: {frame_width}mm wide")
    print(f"Bead: {bead_width}mm wide, {bead_offset}mm offset, {bead_depth}mm deep")


    outer_domain = Domain.from_rectangle(
        outer_w, outer_h,
        center=(outer_w / 2, outer_h / 2),
    )

    panel_domain_result = outer_domain.inset(frame_width)
    if panel_domain_result.is_empty:
        raise ValueError("Frame too wide for door dimensions")
    panel_domain = panel_domain_result.domains[0]


    frame_result = outer_domain.subtract(panel_domain)
    if frame_result.is_empty:
        raise ValueError("Failed to create frame domain")
    frame_domain = frame_result.domains[0]

    print(f"\nFrame domain has {len(frame_domain.inner_boundaries)} inner boundary")


    profile_items = profile_generator(
        outer_domain,
        ProfileParams(side="outside", depth="through"),
    )


    pocket_items = flat_pocket_generator(
        panel_domain,
        FlatPocketParams(depth_mm=panel_recess),
    )


    bead_items = bead_generator(
        frame_domain,
        BeadParams(
            width_mm=bead_width,
            depth_mm=bead_depth,
            offset_mm=bead_offset,
            loop_selection="inner_only",
        ),
    )

    print(f"\nGenerated:")
    print(f"  Profile items: {len(profile_items)}")
    print(f"  Pocket items: {len(pocket_items)}")
    print(f"  Bead items: {len(bead_items)}")


    all_items = profile_items + pocket_items + bead_items
    margin = 25.0

    ast = LayoutAST(
        sheet=Sheet(
            width_mm=outer_w + 2 * margin,
            height_mm=outer_h + 2 * margin,
            thickness_mm=sheet_thickness,
        ),
        items=tuple(all_items),
    )

    return ast


def create_grid_panel(
    width: float = 250.0,
    height: float = 250.0,
    grid_spacing: float = 25.0,
    grid_depth: float = 2.0,
    sheet_thickness: float = 19.0,
) -> LayoutAST:
    print("\n=== Creating Grid Panel ===")
    print(f"Dimensions: {width}mm x {height}mm")
    print(f"Grid: {grid_spacing}mm spacing")

    panel = Domain.from_rectangle(width, height, center=(width / 2, height / 2))

    profile_items = profile_generator(
        panel,
        ProfileParams(side="outside", depth="through"),
    )

    grid_items = grid_generator(
        panel,
        GridParams(
            spacing_x_mm=grid_spacing,
            spacing_y_mm=grid_spacing,
            line_width_mm=3.175,
            depth_mm=grid_depth,
        ),
    )

    print(f"Generated {len(grid_items)} grid lines")

    margin = 25.0
    ast = LayoutAST(
        sheet=Sheet(
            width_mm=width + 2 * margin,
            height_mm=height + 2 * margin,
            thickness_mm=sheet_thickness,
        ),
        items=tuple(profile_items + grid_items),
    )

    return ast


def convert_to_ir(ast: LayoutAST) -> list:
    print("\n--- Converting to RemovalIntent IR ---")

    warnings = []
    intents = ast_to_removal_intents(ast, warnings=warnings)

    if warnings:
        print(f"Conversion warnings: {warnings}")

    print(f"Generated {len(intents)} RemovalIntent(s)")

    for i, intent in enumerate(intents):
        print(f"\n  Intent {i}:")
        print(f"    ID: {intent.region_id}")
        print(f"    Bounds: {intent.bounds}")
        print(f"    Depth: z_bottom={intent.depth_profile.z_bottom}")

    return intents


def visualize_domain_ascii(domain: Domain, width: int = 40, height: int = 20) -> str:
    bounds = domain.bounds
    x_scale = bounds.width / (width - 1) if bounds.width > 0 else 1
    y_scale = bounds.height / (height - 1) if bounds.height > 0 else 1


    grid = [[' ' for _ in range(width)] for _ in range(height)]


    for i in range(len(domain.outer_boundary)):
        x1, y1 = domain.outer_boundary[i]
        x2, y2 = domain.outer_boundary[(i + 1) % len(domain.outer_boundary)]


        gx1 = int((x1 - bounds.x_min) / x_scale)
        gy1 = int((bounds.y_max - y1) / y_scale)
        gx2 = int((x2 - bounds.x_min) / x_scale)
        gy2 = int((bounds.y_max - y2) / y_scale)


        steps = max(abs(gx2 - gx1), abs(gy2 - gy1), 1)
        for t in range(steps + 1):
            gx = int(gx1 + (gx2 - gx1) * t / steps)
            gy = int(gy1 + (gy2 - gy1) * t / steps)
            if 0 <= gx < width and 0 <= gy < height:
                grid[gy][gx] = '#'


    for inner in domain.inner_boundaries:
        for i in range(len(inner)):
            x1, y1 = inner[i]
            x2, y2 = inner[(i + 1) % len(inner)]

            gx1 = int((x1 - bounds.x_min) / x_scale)
            gy1 = int((bounds.y_max - y1) / y_scale)
            gx2 = int((x2 - bounds.x_min) / x_scale)
            gy2 = int((bounds.y_max - y2) / y_scale)

            steps = max(abs(gx2 - gx1), abs(gy2 - gy1), 1)
            for t in range(steps + 1):
                gx = int(gx1 + (gx2 - gx1) * t / steps)
                gy = int(gy1 + (gy2 - gy1) * t / steps)
                if 0 <= gx < width and 0 <= gy < height:
                    grid[gy][gx] = 'o'


    lines = ['┌' + '─' * width + '┐']
    for row in grid:
        lines.append('│' + ''.join(row) + '│')
    lines.append('└' + '─' * width + '┘')

    return '\n'.join(lines)


def main():
    print("=" * 70)
    print("Domain/Generator System - Integration Examples")
    print("=" * 70)


    shaker_ast = create_shaker_door()


    outer = Domain.from_rectangle(400, 600, center=(200, 300))
    panel = outer.inset(50).domains[0]
    print("\nOuter domain (# = boundary):")
    print(visualize_domain_ascii(outer))
    print("\nPanel domain:")
    print(visualize_domain_ascii(panel))


    convert_to_ir(shaker_ast)


    wave_ast = create_wave_panel()
    convert_to_ir(wave_ast)


    beaded_ast = create_beaded_frame_door()


    outer = Domain.from_rectangle(400, 600, center=(200, 300))
    panel = outer.inset(60).domains[0]
    frame = outer.subtract(panel).domains[0]
    print("\nFrame domain (# = outer, o = inner/hole):")
    print(visualize_domain_ascii(frame))

    convert_to_ir(beaded_ast)


    grid_ast = create_grid_panel()
    convert_to_ir(grid_ast)

    print("\n" + "=" * 70)
    print("All examples completed successfully!")
    print("=" * 70)


    print("\nSummary of generated LayoutASTs:")
    for name, ast in [
        ("Shaker Door", shaker_ast),
        ("Wave Panel", wave_ast),
        ("Beaded Frame", beaded_ast),
        ("Grid Panel", grid_ast),
    ]:
        print(f"  {name}: {len(ast.items)} items")


if __name__ == "__main__":
    main()
