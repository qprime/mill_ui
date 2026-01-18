#!/usr/bin/env python3
"""Recipe 26: Faux Shutter Panel.

Uses split_horizontal to space louver grooves and applies chamfers.
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


PANEL_WIDTH = 250
PANEL_HEIGHT = 600
GROOVE_COUNT = 12
GROOVE_HEIGHT = 12.0
GROOVE_DEPTH = 8.0
CHAMFER_WIDTH = 4.0
CHAMFER_DEPTH = 2.0


def _gap_domains_from_split(domain: Domain, split_count: int, gap_mm: float) -> list[Domain]:
    slats = list(domain.split_horizontal(split_count, gap_mm=gap_mm))
    slats = sorted(slats, key=lambda d: d.bounds.y_min)

    gaps: list[Domain] = []
    for lower, upper in zip(slats, slats[1:]):
        gap_y_min = lower.bounds.y_max
        gap_y_max = upper.bounds.y_min
        if gap_y_max <= gap_y_min:
            continue
        gap_height = gap_y_max - gap_y_min
        center_y = (gap_y_min + gap_y_max) / 2
        gaps.append(
            Domain.from_rectangle(
                PANEL_WIDTH,
                gap_height,
                center=(PANEL_WIDTH / 2, center_y),
            )
        )
    return gaps


def build_ast() -> LayoutAST:
    panel = Domain.from_rectangle(PANEL_WIDTH, PANEL_HEIGHT, center=(125, 300))

    items = []
    items.extend(profile_generator(panel, ProfileParams(side="outside", depth="through")))

    gaps = _gap_domains_from_split(panel, GROOVE_COUNT + 1, GROOVE_HEIGHT)

    for gap in gaps:
        items.extend(flat_pocket_generator(gap, FlatPocketParams(depth_mm=GROOVE_DEPTH)))
        items.extend(
            chamfer_generator(
                gap,
                ChamferParams(width_mm=CHAMFER_WIDTH, depth_mm=CHAMFER_DEPTH),
            )
        )

    return LayoutAST(
        sheet=Sheet(width_mm=PANEL_WIDTH, height_mm=PANEL_HEIGHT, thickness_mm=19.0),
        items=tuple(items),
        project="recipe_26_faux_shutter_panel",
    )


def main() -> None:
    output_dir = Path(__file__).parent / "output"
    ast = build_ast()
    write_recipe_outputs(ast, output_dir)


if __name__ == "__main__":
    main()
