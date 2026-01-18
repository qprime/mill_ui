#!/usr/bin/env python3
"""Recipe 30: Cathedral Arch Door.

Builds an arched door outline and a raised panel inset.
"""

from __future__ import annotations

import math
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


DOOR_WIDTH = 500
DOOR_HEIGHT = 800
ARCH_RADIUS = 250
FRAME_INSET = 60


def _arch_outline() -> list[tuple[float, float]]:
    center_x = DOOR_WIDTH / 2
    center_y = DOOR_HEIGHT - ARCH_RADIUS

    points: list[tuple[float, float]] = []
    points.append((0.0, 0.0))
    points.append((DOOR_WIDTH, 0.0))
    points.append((DOOR_WIDTH, center_y))

    steps = 40
    for i in range(steps + 1):
        angle = math.pi * i / steps
        x = center_x + ARCH_RADIUS * math.cos(angle)
        y = center_y + ARCH_RADIUS * math.sin(angle)
        points.append((x, y))

    points.append((0.0, center_y))
    return points


def build_ast() -> LayoutAST:
    outer = Domain.from_polygon(_arch_outline())
    panel = outer.inset(FRAME_INSET).domains[0]

    items = []
    items.extend(profile_generator(outer, ProfileParams(side="outside", depth="through")))
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
        sheet=Sheet(width_mm=DOOR_WIDTH, height_mm=DOOR_HEIGHT, thickness_mm=19.0),
        items=tuple(items),
        project="recipe_30_cathedral_arch_door",
    )


def main() -> None:
    output_dir = Path(__file__).parent / "output"
    ast = build_ast()
    write_recipe_outputs(ast, output_dir)


if __name__ == "__main__":
    main()
