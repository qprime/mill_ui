#!/usr/bin/env python3
"""Recipe 24: Shelf Dados Side Panel.

Creates a cabinet side with repeated dado grooves for shelves.
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
    FlatPocketParams,
    ProfileParams,
    flat_pocket_generator,
    profile_generator,
)
from layout_ast.layout import LayoutAST, Sheet
from recipe_utils import write_recipe_outputs


PANEL_WIDTH = 600
PANEL_HEIGHT = 800
GROOVE_WIDTH = 19
GROOVE_DEPTH = 10.0
GROOVE_SPACING = 150
GROOVE_COUNT = 5


def build_ast() -> LayoutAST:
    panel = Domain.from_rectangle(PANEL_WIDTH, PANEL_HEIGHT, center=(300, 400))

    items = []
    items.extend(profile_generator(panel, ProfileParams(side="outside", depth="through")))

    for i in range(GROOVE_COUNT):
        y = GROOVE_SPACING * (i + 1)
        groove = Domain.from_rectangle(PANEL_WIDTH, GROOVE_WIDTH, center=(300, y))
        items.extend(flat_pocket_generator(groove, FlatPocketParams(depth_mm=GROOVE_DEPTH)))

    return LayoutAST(
        sheet=Sheet(width_mm=PANEL_WIDTH, height_mm=PANEL_HEIGHT, thickness_mm=19.0),
        items=tuple(items),
        project="recipe_24_shelf_dados_side",
    )


def main() -> None:
    output_dir = Path(__file__).parent / "output"
    ast = build_ast()
    write_recipe_outputs(ast, output_dir)


if __name__ == "__main__":
    main()
