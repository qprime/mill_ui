def emit_gcode_from_path(
    path,
    feedrate=300,
    safe_height=5.0,
    ramp_distance=5.0,
    units='mm',
    header_lines=None,
    footer_lines=None
):
    gcode = list(header_lines) if header_lines else []

    gcode.append("G21" if units == 'mm' else "G20")
    gcode.append("G90 ; Absolute positioning")
    gcode.append(f"G0 Z{safe_height:.3f}")

    last_x = last_y = last_z = None

    for row in path:
        if not row:
            continue
        start_x, start_y, start_z = row[0]

        # Ramp from safe_height to Z
        ramp_zs = [
            safe_height + (start_z - safe_height) * (i / max(1, len(row)))
            for i in range(len(row))
        ]
        for i, (x, y, z) in enumerate(zip(
            [pt[0] for pt in row], [pt[1] for pt in row], ramp_zs
        )):
            if (x != last_x or y != last_y or z != last_z):
                gcode.append(f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f} F{feedrate}")
                last_x, last_y, last_z = x, y, z

        # Full path after ramp
        for x, y, z in row[1:]:
            if (x != last_x or y != last_y or z != last_z):
                gcode.append(f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f} F{feedrate}")
                last_x, last_y, last_z = x, y, z

        # Lift to safe height
        gcode.append(f"G0 Z{safe_height:.3f}")

    gcode.append(f"G0 Z{safe_height:.3f} ; Safe height")
    gcode.append("G0 X0 Y0 ; Return to origin")
    if footer_lines:
        gcode.extend(footer_lines)

    return gcode
