# path: skills/cam_generator/gcode/emit_gcode.py
# # desc: Emit G-code from path with staydown/retract logic.
# api: emit_gcode_from_path
# tags: cam

from skills.cam_generator.gcode.ramp import generate_z_ramp

_LINK_CLEARANCE = 0.6
_SAME_ROW_Y_TOL = 1e-4

def _fmt(val: float) -> str:
    return f"{val:.3f}"

def _g0_xyz(x=None, y=None, z=None) -> str:
    parts = ["G0"]
    if x is not None:
        parts.append(f"X{_fmt(x)}")
    if y is not None:
        parts.append(f"Y{_fmt(y)}")
    if z is not None:
        parts.append(f"Z{_fmt(z)}")
    return " ".join(parts)

def _g1_xyzf(x=None, y=None, z=None, f=None) -> str:
    parts = ["G1"]
    if x is not None:
        parts.append(f"X{_fmt(x)}")
    if y is not None:
        parts.append(f"Y{_fmt(y)}")
    if z is not None:
        parts.append(f"Z{_fmt(z)}")
    if f is not None:
        parts.append(f"F{int(round(f))}")
    return " ".join(parts)

def _emit_header(units: str, safe_z: float, header_lines):
    g = []
    if header_lines:
        g.extend(header_lines)
    g.append("G21" if units == "mm" else "G20")
    g.append("G90 ; Absolute positioning")
    g.append(_g0_xyz(z=safe_z))
    return g

def _emit_footer(safe_z: float, footer_lines):
    g = []
    g.append(f"{_g0_xyz(z=safe_z)} ; Final retract")
    g.append("G0 X0 Y0 ; Return to origin")
    if footer_lines:
        g.extend(footer_lines)
    return g

def _rapid_to_xy(g, x, y):
    g.append(_g0_xyz(x=x, y=y))

def _rapid_to_z(g, z):
    g.append(_g0_xyz(z=z))

def _plunge_to(g, z, plunge_feed):
    g.append(_g1_xyzf(z=z, f=plunge_feed))

def _ramp_entry(g, x, y, safe_z, target_z, ramp_distance, plunge_feed):
    ramp_pts = generate_z_ramp(x, y, safe_z, target_z, step_mm=ramp_distance / 10.0)
    for rx, ry, rz in ramp_pts:
        g.append(_g1_xyzf(x=rx, y=ry, z=rz, f=plunge_feed))

def _cut_segment(g, row, cut_feed):
    for (x, y, z) in row[1:]:
        g.append(_g1_xyzf(x=x, y=y, z=z, f=cut_feed))

def _same_raster_row(prev_row, start_y) -> bool:
    if not prev_row:
        return False
    prev_y = float(prev_row[0][1])
    return abs(float(start_y) - prev_y) <= _SAME_ROW_Y_TOL

def _staydown_link(g, start_x, start_y, start_z, safe_z, plunge_feed):
    target_link_z = start_z + _LINK_CLEARANCE
    z_up = target_link_z if target_link_z < safe_z else safe_z
    _rapid_to_z(g, z_up)
    _rapid_to_xy(g, start_x, start_y)
    _plunge_to(g, start_z, plunge_feed)

def _full_retract_move(g, start_x, start_y, start_z, safe_z, ramp_distance, plunge_feed):
    _rapid_to_z(g, safe_z)
    _rapid_to_xy(g, start_x, start_y)
    if ramp_distance > 0.0:
        _ramp_entry(g, start_x, start_y, safe_z, start_z, ramp_distance, plunge_feed)
    else:
        _plunge_to(g, start_z, plunge_feed)

def emit_gcode_from_path(
    path,
    feedrate=300,
    safe_height=5.0,
    ramp_distance=5.0,
    units="mm",
    header_lines=None,
    footer_lines=None,
):
    cut_feed = float(feedrate)
    plunge_feed = float(feedrate)

    g = []
    g.extend(_emit_header(units, safe_height, header_lines))

    if not path:
        g.extend(_emit_footer(safe_height, footer_lines))
        return g

    for i, row in enumerate(path):
        if not row:
            continue

        start_x, start_y, start_z = float(row[0][0]), float(row[0][1]), float(row[0][2])

        if i == 0:
            _rapid_to_xy(g, start_x, start_y)
            if ramp_distance > 0.0:
                _ramp_entry(g, start_x, start_y, safe_height, start_z, ramp_distance, plunge_feed)
            else:
                _plunge_to(g, start_z, plunge_feed)
        else:
            if _same_raster_row(path[i - 1], start_y):
                _staydown_link(g, start_x, start_y, start_z, safe_height, plunge_feed)
            else:
                _full_retract_move(g, start_x, start_y, start_z, safe_height, ramp_distance, plunge_feed)

        _cut_segment(g, row, cut_feed)

        last_z = float(row[-1][2])
        park_z = min(safe_height, last_z + _LINK_CLEARANCE)
        _rapid_to_z(g, park_z)

    g.extend(_emit_footer(safe_height, footer_lines))
    return g
