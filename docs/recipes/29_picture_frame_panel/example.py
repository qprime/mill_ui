#!/usr/bin/env python3
"""Recipe 29: Picture Frame Panel.

Uses subtract and multi-depth features for a frame with an inner opening.
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


OUTER_WIDTH = 300
OUTER_HEIGHT = 400
INNER_WIDTH = 200
INNER_HEIGHT = 300
RABBET_WIDTH = 10.0
RABBET_DEPTH = 5.0


def build_ast() -> LayoutAST:
    outer = Domain.from_rectangle(OUTER_WIDTH, OUTER_HEIGHT, center=(150, 200))
    inner = Domain.from_rectangle(INNER_WIDTH, INNER_HEIGHT, center=(150, 200))

    items = []
    items.extend(profile_generator(outer, ProfileParams(side="outside", depth="through")))
    items.extend(profile_generator(inner, ProfileParams(side="inside", depth="through")))

    rabbet_outer = inner.offset(RABBET_WIDTH).domains[0]
    rabbet_ring = rabbet_outer.subtract(inner)
    for domain in rabbet_ring:
        items.extend(flat_pocket_generator(domain, FlatPocketParams(depth_mm=RABBET_DEPTH)))

    items.extend(chamfer_generator(outer, ChamferParams(width_mm=5.0, depth_mm=3.0)))

    return LayoutAST(
        sheet=Sheet(width_mm=OUTER_WIDTH, height_mm=OUTER_HEIGHT, thickness_mm=19.0),
        items=tuple(items),
        project="recipe_29_picture_frame_panel",
    )


def main() -> None:
    output_dir = Path(__file__).parent / "output"
    ast = build_ast()
    write_recipe_outputs(ast, output_dir)


if __name__ == "__main__":
    main()
