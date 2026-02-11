from __future__ import annotations

from typing import Sequence

from layout_ast.layout import LayoutAST
from ir.removal_intent import RemovalIntent


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
]
