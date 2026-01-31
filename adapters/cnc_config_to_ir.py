from __future__ import annotations

from config.machine_loader import MachineConfig, Endmill
from ir.removal_intent import Bounds2D
from export.dimensions import DimensionRequest
from diagram_ir import DiagramIR, LayerIR, Rect, Line, Circle, Text


def machine_config_to_diagram_ir(
    config: MachineConfig,
    endmill: Endmill | None = None,
    show_dimensions: bool = True,
    show_centerlines: bool = True,
) -> DiagramIR:
    machine = config.machine
    wasteboard = config.wasteboard

    bounds = Bounds2D(
        x_min=machine.envelope_x_min,
        x_max=machine.envelope_x_max,
        y_min=machine.envelope_y_min,
        y_max=machine.envelope_y_max,
    )

    layers: list[LayerIR] = []
    dims: list[DimensionRequest] = []

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

    if wasteboard:
        wasteboard_shapes = [
            Rect(
                x=wasteboard.x_min,
                y=wasteboard.y_min,
                width=wasteboard.width_mm,
                height=wasteboard.height_mm,
                style_token="wasteboard",
                id="wasteboard",
            )
        ]
        layers.append(LayerIR(name="WASTEBOARD", items=tuple(wasteboard_shapes)))

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

    origin_size = min(machine.envelope_width, machine.envelope_height) * 0.015
    origin_inset = origin_size + 2
    origin_shapes = [
        Circle(
            cx=machine.envelope_x_min + origin_inset,
            cy=machine.envelope_y_min + origin_inset,
            radius=origin_size,
            style_token="origin",
            id="origin_marker",
        ),
        Line(
            x1=machine.envelope_x_min + origin_inset,
            y1=machine.envelope_y_min + origin_inset,
            x2=machine.envelope_x_min + origin_inset + origin_size * 2.5,
            y2=machine.envelope_y_min + origin_inset,
            style_token="origin",
            id="origin_x_axis",
        ),
        Line(
            x1=machine.envelope_x_min + origin_inset,
            y1=machine.envelope_y_min + origin_inset,
            x2=machine.envelope_x_min + origin_inset,
            y2=machine.envelope_y_min + origin_inset + origin_size * 2.5,
            style_token="origin",
            id="origin_y_axis",
        ),
    ]
    layers.append(LayerIR(name="ORIGIN_MARKER", items=tuple(origin_shapes)))

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

        if wasteboard:
            dims.append(
                DimensionRequest(
                    orientation="horizontal",
                    a=wasteboard.x_min,
                    b=wasteboard.x_max,
                    anchor=wasteboard.y_max,
                    text=f"{wasteboard.width_mm:.0f}mm",
                )
            )
            dims.append(
                DimensionRequest(
                    orientation="vertical",
                    a=wasteboard.y_min,
                    b=wasteboard.y_max,
                    anchor=wasteboard.x_min,
                    text=f"{wasteboard.height_mm:.0f}mm",
                )
            )

            margins = config.compute_margins()
            if margins["left"] > 1:
                dims.append(
                    DimensionRequest(
                        orientation="horizontal",
                        a=machine.envelope_x_min,
                        b=wasteboard.x_min,
                        anchor=wasteboard.center_y,
                        text=f"{margins['left']:.0f}mm",
                    )
                )
            if margins["bottom"] > 1:
                dims.append(
                    DimensionRequest(
                        orientation="vertical",
                        a=machine.envelope_y_min,
                        b=wasteboard.y_min,
                        anchor=wasteboard.center_x,
                        text=f"{margins['bottom']:.0f}mm",
                    )
                )

    notes: list[Text] = [
        Text(
            x=machine.envelope_x_min + 10,
            y=machine.envelope_y_max - 10,
            content=f"Machine: {machine.name}",
            style_token="notes",
            anchor="start",
            baseline="text-top",
        ),
    ]
    if endmill:
        notes.append(
            Text(
                x=machine.envelope_x_min + 10,
                y=machine.envelope_y_max - 25,
                content=f"Bit: {endmill.name} (⌀{endmill.diameter_mm:.2f}mm)",
                style_token="notes",
                anchor="start",
                baseline="text-top",
            )
        )

    metadata = {
        "machine_name": machine.name,
        "envelope_width": str(machine.envelope_width),
        "envelope_height": str(machine.envelope_height),
    }
    if endmill:
        metadata["endmill_name"] = endmill.name
        metadata["endmill_diameter"] = str(endmill.diameter_mm)

    return DiagramIR(
        bounds=bounds,
        layers=tuple(layers),
        dims=tuple(dims),
        notes=tuple(notes),
        metadata=metadata,
    )


__all__ = ["machine_config_to_diagram_ir"]
