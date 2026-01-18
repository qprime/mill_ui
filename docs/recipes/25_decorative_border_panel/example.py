#!/usr/bin/env python3
"""Recipe 25: Decorative Border Panel.

Creates nested rectangular groove borders using domain insets and subtraction.
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


PANEL_WIDTH = 350
PANEL_HEIGHT = 450
GROOVE_DEPTH = 2.0
GROOVE_WIDTH = 3.0
INSETS = (15.0, 30.0, 45.0)


def build_ast() -> LayoutAST:
    panel = Domain.from_rectangle(PANEL_WIDTH, PANEL_HEIGHT, center=(175, 225))

    items = []
    items.extend(profile_generator(panel, ProfileParams(side="outside", depth="through")))

    for inset in INSETS:
        outer = panel.inset(inset).domains[0]
        inner = panel.inset(inset + GROOVE_WIDTH).domains[0]
        ring = outer.subtract(inner)
        for domain in ring:
            items.extend(flat_pocket_generator(domain, FlatPocketParams(depth_mm=GROOVE_DEPTH)))

    return LayoutAST(
        sheet=Sheet(width_mm=PANEL_WIDTH, height_mm=PANEL_HEIGHT, thickness_mm=19.0),
        items=tuple(items),
        project="recipe_25_decorative_border_panel",
    )


def main() -> None:
    output_dir = Path(__file__).parent / "output"
    ast = build_ast()
    write_recipe_outputs(ast, output_dir)


if __name__ == "__main__":
    main()
