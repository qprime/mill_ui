from __future__ import annotations

from config.machine_loader import Endmill, MachineConfig
from diagram_ir import DiagramIR, LayerIR, Line, Rect
from diagram_ir.dimensions import DimensionRequest
from ir.removal_intent import Bounds2D


def machine_config_to_diagram_ir(
    config: MachineConfig,
    endmill: Endmill | None = None,
    show_dimensions: bool = True,
    show_centerlines: bool = True,
    t_track_width_mm: float = 0.0,
) -> DiagramIR:
    machine = config.machine
    spoilboard = config.spoilboard
    table = config.table

    bounds_x_min = machine.envelope_x_min
    bounds_x_max = machine.envelope_x_max
    bounds_y_min = machine.envelope_y_min
    bounds_y_max = machine.envelope_y_max

    layers: list[LayerIR] = []
    dims: list[DimensionRequest] = []

    if table is not None:
        table_w = table.rail_spacing_mm
        table_x = machine.envelope_center_x - table_w / 2.0
        table_y = machine.envelope_y_max - table.surface_height_mm
        table_shapes = [
            Rect(
                x=table_x,
                y=table_y,
                width=table_w,
                height=table.surface_height_mm,
                style_token="table",
                id="table_surface",
            )
        ]
        layers.append(LayerIR(name="TABLE", items=tuple(table_shapes)))

        bounds_x_min = min(bounds_x_min, table_x)
        bounds_x_max = max(bounds_x_max, table_x + table_w)
        bounds_y_min = min(bounds_y_min, table_y)
        bounds_y_max = max(bounds_y_max, table_y + table.surface_height_mm)

    if spoilboard and t_track_width_mm > 0:
        tw = t_track_width_mm
        bounds_x_min = min(bounds_x_min, spoilboard.x_min - tw)
        bounds_x_max = max(bounds_x_max, spoilboard.x_max + tw)
        bounds_y_min = min(bounds_y_min, spoilboard.y_min - tw)
        bounds_y_max = max(bounds_y_max, spoilboard.y_max + tw)

    bounds = Bounds2D(
        x_min=bounds_x_min,
        x_max=bounds_x_max,
        y_min=bounds_y_min,
        y_max=bounds_y_max,
    )

    if spoilboard:
        spoilboard_shapes = [
            Rect(
                x=spoilboard.x_min,
                y=spoilboard.y_min,
                width=spoilboard.width_mm,
                height=spoilboard.height_mm,
                style_token="spoilboard",
                id="spoilboard_surface",
            )
        ]
        layers.append(LayerIR(name="SPOILBOARD", items=tuple(spoilboard_shapes)))

    envelope_shapes = [
        Rect(
            x=machine.envelope_x_min,
            y=machine.envelope_y_min,
            width=machine.envelope_width,
            height=machine.envelope_height,
            style_token="envelope",
            id="envelope",
        )
    ]
    layers.append(LayerIR(name="ENVELOPE", items=tuple(envelope_shapes)))

    if endmill:
        bit_radius = endmill.radius_mm
        eff_x_min, eff_y_min, eff_x_max, eff_y_max = config.effective_envelope(bit_radius)
        effective_shapes = [
            Rect(
                x=eff_x_min,
                y=eff_y_min,
                width=eff_x_max - eff_x_min,
                height=eff_y_max - eff_y_min,
                style_token="effective-envelope",
                id="effective_envelope",
            )
        ]
        layers.append(LayerIR(name="EFFECTIVE_ENVELOPE", items=tuple(effective_shapes)))

    sl = machine.soft_limits
    if sl is not None:
        soft_limit_shapes = [
            Rect(
                x=machine.envelope_x_min,
                y=machine.envelope_y_max - sl.y_max_mm,
                width=sl.x_max_mm,
                height=sl.y_max_mm,
                style_token="soft-limit",
                id="soft_limit_boundary",
            )
        ]
        layers.append(LayerIR(name="SOFT_LIMITS", items=tuple(soft_limit_shapes)))

    if spoilboard and t_track_width_mm > 0:
        tw = t_track_width_mm
        wb = spoilboard
        t_track_shapes = [
            Rect(x=wb.x_min - tw, y=wb.y_min, width=tw, height=wb.height_mm, style_token="t-track", id="ttrack_left"),
            Rect(x=wb.x_max, y=wb.y_min, width=tw, height=wb.height_mm, style_token="t-track", id="ttrack_right"),
            Rect(x=wb.x_min, y=wb.y_min - tw, width=wb.width_mm, height=tw, style_token="t-track", id="ttrack_front"),
            Rect(x=wb.x_min, y=wb.y_max, width=wb.width_mm, height=tw, style_token="t-track", id="ttrack_back"),
        ]
        layers.append(LayerIR(name="T_TRACK", items=tuple(t_track_shapes)))

    if show_centerlines:
        center_x = machine.envelope_center_x
        center_y = machine.envelope_center_y
        centerline_shapes = [
            Line(
                x1=machine.envelope_x_min,
                y1=center_y,
                x2=machine.envelope_x_max,
                y2=center_y,
                style_token="centerline",
                id="centerline_horizontal",
            ),
            Line(
                x1=center_x,
                y1=machine.envelope_y_min,
                x2=center_x,
                y2=machine.envelope_y_max,
                style_token="centerline",
                id="centerline_vertical",
            ),
        ]
        layers.append(LayerIR(name="CENTERLINES", items=tuple(centerline_shapes)))

    if show_dimensions:
        dims.append(
            DimensionRequest(
                orientation="horizontal",
                a=machine.envelope_x_min,
                b=machine.envelope_x_max,
                anchor=machine.envelope_y_min,
                text=f"{machine.envelope_width:.0f}mm",
            )
        )
        dims.append(
            DimensionRequest(
                orientation="vertical",
                a=machine.envelope_y_min,
                b=machine.envelope_y_max,
                anchor=machine.envelope_x_max,
                text=f"{machine.envelope_height:.0f}mm",
            )
        )

        if spoilboard:
            dims.append(
                DimensionRequest(
                    orientation="horizontal",
                    a=spoilboard.x_min,
                    b=spoilboard.x_max,
                    anchor=spoilboard.y_max,
                    text=f"{spoilboard.width_mm:.0f}mm",
                )
            )
            dims.append(
                DimensionRequest(
                    orientation="vertical",
                    a=spoilboard.y_min,
                    b=spoilboard.y_max,
                    anchor=spoilboard.x_min,
                    text=f"{spoilboard.height_mm:.0f}mm",
                )
            )

            margins = config.compute_margins()
            if margins["left"] > 1:
                dims.append(
                    DimensionRequest(
                        orientation="horizontal",
                        a=machine.envelope_x_min,
                        b=spoilboard.x_min,
                        anchor=spoilboard.center_y,
                        text=f"{margins['left']:.0f}mm",
                    )
                )
            if margins["bottom"] > 1:
                dims.append(
                    DimensionRequest(
                        orientation="vertical",
                        a=machine.envelope_y_min,
                        b=spoilboard.y_min,
                        anchor=spoilboard.center_x,
                        text=f"{margins['bottom']:.0f}mm",
                    )
                )

        if sl is not None:
            if abs(sl.x_max_mm - machine.envelope_width) > 0.5:
                dims.append(
                    DimensionRequest(
                        orientation="horizontal",
                        a=machine.envelope_x_min,
                        b=machine.envelope_x_min + sl.x_max_mm,
                        anchor=machine.envelope_y_max - sl.y_max_mm,
                        text=f"$130={sl.x_max_mm:.0f}mm",
                    )
                )
            if abs(sl.y_max_mm - machine.envelope_height) > 0.5:
                dims.append(
                    DimensionRequest(
                        orientation="vertical",
                        a=machine.envelope_y_max - sl.y_max_mm,
                        b=machine.envelope_y_max,
                        anchor=machine.envelope_x_min + sl.x_max_mm,
                        text=f"$131={sl.y_max_mm:.0f}mm",
                    )
                )

    metadata = {
        "machine_name": machine.name,
        "envelope_width": str(machine.envelope_width),
        "envelope_height": str(machine.envelope_height),
    }
    if sl is not None:
        metadata["soft_limit_x"] = str(sl.x_max_mm)
        metadata["soft_limit_y"] = str(sl.y_max_mm)
        metadata["soft_limit_z"] = str(sl.z_max_mm)
    if endmill:
        metadata["endmill_name"] = endmill.name
        metadata["endmill_diameter"] = str(endmill.diameter_mm)
    if t_track_width_mm > 0:
        metadata["t_track_width"] = str(t_track_width_mm)

    return DiagramIR(
        bounds=bounds,
        layers=tuple(layers),
        dims=tuple(dims),
        metadata=metadata,
    )


__all__ = ["machine_config_to_diagram_ir"]
