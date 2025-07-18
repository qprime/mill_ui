import numpy as np

def generate_raster_toolpath(
    heightmap, scale_xy, tool_diameter, stepover,
    direction='x', z_safe=5.0, feedrate=300,
    ramp_distance=5.0, z_clamp=None, units='mm',
    header_lines=None, footer_lines=None
):
    gcode = list(header_lines) if header_lines else []

    if units == 'mm':
        gcode.append("G21 ; Set units to mm")
    elif units == 'inch':
        gcode.append("G20 ; Set units to inches")
    else:
        raise ValueError(f"Unsupported units: {units}")

    gcode.extend([
        "G90 ; Absolute positioning",
        f"G0 Z{z_safe:.3f}"
    ])

    rows, cols = heightmap.shape
    step_px = max(1, int(stepover / scale_xy))

    if direction in ['x', 'zigzag-x']:
        lines = range(0, rows, step_px)
        axis = 'x'
    elif direction == 'y':
        lines = range(0, cols, step_px)
        axis = 'y'
    else:
        raise ValueError(f"Unsupported raster direction: {direction}")

    for i_idx, i in enumerate(lines):
        serpentine = direction == 'zigzag-x'
        path = range(cols) if not serpentine or (i_idx % 2 == 0) else reversed(range(cols))
        ramp_started = False
        last_x = last_y = last_z = None

        for j_idx, j in enumerate(path):
            x = j * scale_xy if axis == 'x' else i * scale_xy
            y = i * scale_xy if axis == 'x' else j * scale_xy
            z = -heightmap[i, j] if axis == 'x' else -heightmap[j, i]
            if z_clamp is not None:
                z = max(z, z_clamp)

            if not ramp_started:
                ramp_zs = np.linspace(z_safe, z, num=max(2, int(ramp_distance / scale_xy)))
                ramp_path = list(path)[j_idx : j_idx + len(ramp_zs)]

                for jj, zz in zip(ramp_path, ramp_zs):
                    rx = jj * scale_xy if axis == 'x' else i * scale_xy
                    ry = i * scale_xy if axis == 'x' else jj * scale_xy
                    if z_clamp is not None:
                        zz = max(zz, z_clamp)
                    if (rx != last_x or ry != last_y or zz != last_z):
                        gcode.append(f"G1 X{rx:.3f} Y{ry:.3f} Z{zz:.3f} F{feedrate}")
                        last_x, last_y, last_z = rx, ry, zz
                ramp_started = True
                continue

            if (x != last_x or y != last_y or z != last_z):
                gcode.append(f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f} F{feedrate}")
                last_x, last_y, last_z = x, y, z

        if not serpentine:
            gcode.append(f"G0 Z{z_safe:.3f}")

    gcode.append(f"G0 Z{z_safe:.3f} ; Safe height")
    gcode.append("G0 X0 Y0 ; Return to origin")
    if footer_lines:
        gcode.extend(footer_lines)
    return gcode
