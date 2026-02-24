from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, replace

from assembly.panel import PanelSpec, Point2D


@dataclass(frozen=True)
class LayoutConfig:
    gap_mm: float = 10.0
    margin_mm: float = 0.0
    max_width_mm: float | None = None
    max_height_mm: float | None = None


@dataclass(frozen=True)
class PlacedPanel:
    panel: PanelSpec
    origin: Point2D

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        ox, oy = self.origin
        hw = self.panel.width_mm / 2
        hh = self.panel.height_mm / 2
        return (ox - hw, oy - hh, ox + hw, oy + hh)


def layout_panels(
    panels: list[PanelSpec],
    config: LayoutConfig | None = None,
) -> list[PlacedPanel]:
    if config is None:
        config = LayoutConfig()
    sorted_panels = sorted(panels, key=lambda p: (-p.height_mm, -p.width_mm))

    placed: list[PlacedPanel] = []
    current_x = config.margin_mm
    current_y = config.margin_mm
    row_height = 0.0
    row_start_x = config.margin_mm

    for panel in sorted_panels:
        panel_half_w = panel.width_mm / 2
        panel_half_h = panel.height_mm / 2

        next_x = current_x + panel_half_w

        if config.max_width_mm and next_x + panel_half_w > config.max_width_mm:
            current_y += row_height + config.gap_mm
            current_x = row_start_x
            row_height = 0.0
            next_x = current_x + panel_half_w

        origin = (next_x, current_y + panel_half_h)

        placed_panel = PlacedPanel(
            panel=replace(panel, origin=origin),
            origin=origin,
        )
        placed.append(placed_panel)

        current_x = next_x + panel_half_w + config.gap_mm
        row_height = max(row_height, panel.height_mm)

    return placed


def panels_to_layout_ast(
    panels: list[PanelSpec],
    config: LayoutConfig | None = None,
) -> Iterator[tuple[PanelSpec, Point2D]]:
    placed = layout_panels(panels, config)
    for p in placed:
        yield p.panel, p.origin


__all__ = [
    "LayoutConfig",
    "PlacedPanel",
    "layout_panels",
    "panels_to_layout_ast",
]
