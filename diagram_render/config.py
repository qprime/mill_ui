from dataclasses import dataclass


@dataclass(frozen=True)
class SVGConfig:
    margin: float = 10.0
    dimension_rail_offset: float = 20.0
    dimension_text_offset: float = 5.0
    legend_x_offset: float = 8.0
    legend_line_height: float = 18.0
    notes_line_height: float = 12.0
    hole_mark_size: float = 3.0
    arrowhead_size: float = 3.0
    edge_color_width: float = 3.0
    gap_dimension_threshold: float = 5.0

    callout_box_width: float = 100.0
    callout_box_height: float = 70.0
    callout_box_spacing: float = 15.0
    callout_scale: float = 3.0
    callout_padding: float = 8.0

    title_font_size: float = 14.0
    notes_font_size: float = 9.0
    dimension_font_size: float = 9.0
    label_font_size: float = 8.0


DEFAULT_CONFIG = SVGConfig()


__all__ = ["DEFAULT_CONFIG", "SVGConfig"]
