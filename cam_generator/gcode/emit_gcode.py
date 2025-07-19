from gcode.ramp import generate_z_ramp

def emit_gcode_from_path(
    path,
    feedrate=300,
    safe_height=5.0,
    ramp_distance=5.0,
    units='mm',
    header_lines=None,
    footer_lines=None
):
    gcode = []

    if header_lines:
        gcode.extend(header_lines)

    gcode.append("G21" if units == "mm" else "G20")
    gcode.append("G90 ; Absolute positioning")
    gcode.append(f"G0 Z{safe_height:.3f}")

    for row in path:
        if not row:
            continue

        start_x, start_y, start_z = row[0]
        gcode.append(f"G0 X{start_x:.3f} Y{start_y:.3f}")
        ramp_pts = generate_z_ramp(start_x, start_y, safe_height, start_z, step_mm=ramp_distance / 10)
        for rx, ry, rz in ramp_pts:
            gcode.append(f"G1 X{rx:.3f} Y{ry:.3f} Z{rz:.3f} F{feedrate}")


        for x, y, z in row[1:]:
            gcode.append(f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f} F{feedrate}")

        gcode.append(f"G0 Z{safe_height:.3f}")

    gcode.append(f"G0 Z{safe_height:.3f} ; Final retract")
    gcode.append("G0 X0 Y0 ; Return to origin")

    if footer_lines:
        gcode.extend(footer_lines)

    return gcode
