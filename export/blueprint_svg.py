from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from layout_ast.layout import LayoutAST
from ir.removal_intent import RemovalIntent


@dataclass(frozen=True)
class Theme:
    background: str
    foreground: str
    profile_stroke: str
    profile_width: str
    pocket_stroke: str
    pocket_fill: str
    pocket_width: str
    hole_stroke: str
    hole_fill: str
    engrave_stroke: str
    engrave_width: str
    construction_stroke: str
    construction_dash: str
    dimension_stroke: str
    dimension_text: str
    gap_stroke: str
    gap_text: str
    notes_text: str
    legend_text: str
    label_text: str
    waste_stroke: str
    waste_dash: str


DARK_THEME = Theme(
    background="#1a1a1a",
    foreground="#e8e8e8",
    profile_stroke="#e8e8e8",
    profile_width="2",
    pocket_stroke="#6496c8",
    pocket_fill="#6496c8",
    pocket_width="1.5",
    hole_stroke="#e8e8e8",
    hole_fill="none",
    engrave_stroke="#888888",
    engrave_width="0.25",
    construction_stroke="#6b8e7f",
    construction_dash="2,2",
    dimension_stroke="#5ab9ea",
    dimension_text="#5ab9ea",
    gap_stroke="#ff9500",
    gap_text="#ff9500",
    notes_text="#cccccc",
    legend_text="#cccccc",
    label_text="#ffcc00",
    waste_stroke="#ff9500",
    waste_dash="8,4",
)

PRINT_THEME = Theme(
    background="#ffffff",
    foreground="#000000",
    profile_stroke="#000000",
    profile_width="2",
    pocket_stroke="#000000",
    pocket_fill="#f0f0f0",
    pocket_width="1.5",
    hole_stroke="#000000",
    hole_fill="none",
    engrave_stroke="#000000",
    engrave_width="0.25",
    construction_stroke="#666666",
    construction_dash="2,2",
    dimension_stroke="#333333",
    dimension_text="#333333",
    gap_stroke="#cc6600",
    gap_text="#cc6600",
    notes_text="#000000",
    legend_text="#000000",
    label_text="#333333",
    waste_stroke="#cc6600",
    waste_dash="8,4",
)

THEMES = {
    "dark": DARK_THEME,
    "print": PRINT_THEME,
}


def render_blueprint_svg(
    layout_ast: LayoutAST,
    removal_intents: Sequence[RemovalIntent] | None = None,
    theme: str = "dark",
    y_origin: str = "back",
) -> str:
    from adapters.layoutast_to_ir import layoutast_to_diagram_ir
    from diagram_render import render_diagram_svg
    from diagram_render.render_svg import DIAGRAM_THEMES
    from diagram_ir.diagram import ViewportSpec

    kerf_width = 0.0
    try:
        kerf_width = float(layout_ast.kerf_width_mm or 0.0)
    except (TypeError, ValueError):
        pass

    diagram_ir = layoutast_to_diagram_ir(
        ast=layout_ast,
        y_origin=y_origin,
        show_dimensions=getattr(layout_ast.sheet, 'show_dimensions', True),
        show_toolpaths=True,
        kerf_width_mm=kerf_width,
    )

    diagram_theme = DIAGRAM_THEMES.get(theme, DIAGRAM_THEMES["dark"])

    return render_diagram_svg(
        diagram=diagram_ir,
        viewport=ViewportSpec(y_flip=False),
        theme=diagram_theme,
    )


render_blueprint_svg_via_ir = render_blueprint_svg


__all__ = [
    "render_blueprint_svg",
    "render_blueprint_svg_via_ir",
    "Theme",
    "DARK_THEME",
    "PRINT_THEME",
    "THEMES",
]
