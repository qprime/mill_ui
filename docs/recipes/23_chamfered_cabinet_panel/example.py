#!/usr/bin/env python3
"""Recipe 23: Chamfered Cabinet Panel.

Shows a full panel pocket with a chamfered outer edge.
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
    ChamferParams,
    FlatPocketParams,
    ProfileParams,
    chamfer_generator,
    flat_pocket_generator,
    profile_generator,
)
from layout_ast.layout import LayoutAST, Sheet
from recipe_utils import write_recipe_outputs


def build_ast() -> LayoutAST:
    panel = Domain.from_rectangle(300, 400, center=(150, 200))

    items = []
    items.extend(profile_generator(panel, ProfileParams(side="outside", depth="through")))
    items.extend(flat_pocket_generator(panel, FlatPocketParams(depth_mm=6.0)))
    items.extend(chamfer_generator(panel, ChamferParams(width_mm=5.0, depth_mm=3.0)))

    return LayoutAST(
        sheet=Sheet(width_mm=300, height_mm=400, thickness_mm=19.0),
        items=tuple(items),
        project="recipe_23_chamfered_cabinet_panel",
    )


def main() -> None:
    output_dir = Path(__file__).parent / "output"
    ast = build_ast()
    write_recipe_outputs(ast, output_dir)


if __name__ == "__main__":
    main()
