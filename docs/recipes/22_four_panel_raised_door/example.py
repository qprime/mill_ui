#!/usr/bin/env python3
"""Recipe 22: Four-Panel Raised Door.

Demonstrates split_grid with raised panel generators in each cell.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
RECIPES_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(RECIPES_ROOT))

from domains import Domain
from generators import (
    ProfileParams,
    RaisedPanelParams,
    profile_generator,
    raised_panel_generator,
)
from layout_ast.layout import LayoutAST, Sheet
from recipe_utils import write_recipe_outputs


def build_ast() -> LayoutAST:
    door = Domain.from_rectangle(500, 700, center=(250, 350))
    panel_region = door.inset(65).domains[0]
    panels = panel_region.split_grid(rows=2, cols=2, gap_mm=35)

    items = []
    items.extend(profile_generator(door, ProfileParams(side="outside", depth="through")))

    for panel in panels:
        items.extend(
            raised_panel_generator(
                panel,
                RaisedPanelParams(
                    border_width_mm=25.0,
                    border_depth_mm=6.0,
                    field_depth_mm=2.0,
                ),
            )
        )

    return LayoutAST(
        sheet=Sheet(width_mm=500, height_mm=700, thickness_mm=19.0),
        items=tuple(items),
        project="recipe_22_four_panel_raised_door",
    )


def main() -> None:
    output_dir = Path(__file__).parent / "output"
    ast = build_ast()
    write_recipe_outputs(ast, output_dir)


if __name__ == "__main__":
    main()
