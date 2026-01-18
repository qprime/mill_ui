#!/usr/bin/env python3
"""Recipe 21: Simple Shaker Door.

Generates a basic shaker door using domains and generators, then writes
AST, RemovalIntents, and SVG preview outputs.
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


def build_ast() -> LayoutAST:
    door = Domain.from_rectangle(400, 600, center=(200, 300))
    panel = door.inset(50).domains[0]

    items = []
    items.extend(profile_generator(door, ProfileParams(side="outside", depth="through")))
    items.extend(flat_pocket_generator(panel, FlatPocketParams(depth_mm=6.0)))

    return LayoutAST(
        sheet=Sheet(width_mm=400, height_mm=600, thickness_mm=19.0),
        items=tuple(items),
        project="recipe_21_simple_shaker_door",
    )


def main() -> None:
    output_dir = Path(__file__).parent / "output"
    ast = build_ast()
    write_recipe_outputs(ast, output_dir)


if __name__ == "__main__":
    main()
