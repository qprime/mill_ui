# path: skills/mill_ui/cam/post/gcode.py

DEFAULT_HEADER = ['(begin)', 'G90', 'G21', 'G17', 'G94']
DEFAULT_FOOTER = ['M5', 'M2', '(end)']

def _fmt_num(v, prec):
    q = 10 ** prec
    return f"{round(v * q) / q:.{prec}f}"

def _g0(x, y, z, prec):
    parts = ['G0']
    if x is not None: parts.append(f"X{_fmt_num(x, prec)}")
    if y is not None: parts.append(f"Y{_fmt_num(y, prec)}")
    if z is not None: parts.append(f"Z{_fmt_num(z, prec)}")
    return " ".join(parts)

def _g1(x, y, z, f, prec):
    parts = ['G1']
    if x is not None: parts.append(f"X{_fmt_num(x, prec)}")
    if y is not None: parts.append(f"Y{_fmt_num(y, prec)}")
    if z is not None: parts.append(f"Z{_fmt_num(z, prec)}")
    if f is not None: parts.append(f"F{_fmt_num(f, max(0, prec - 2))}")
    return " ".join(parts)

def _rpm_line(s): 
    return None if s is None else f"M3 S{int(round(s))}"

def write_gcode(moves, *, unit='mm', prec=3, safe_z=5.0, header=None, footer=None):
    if unit not in ('mm','inch'):
        raise ValueError("unit must be 'mm' or 'inch'")
    lines = []
    hdr = list(DEFAULT_HEADER if header is None else header)
    if unit == 'inch':
        hdr = ['G20' if ln == 'G21' else ln for ln in hdr]
        if 'G20' not in hdr: hdr.insert(1, 'G20')
    else:
        if 'G21' not in hdr: hdr.insert(1, 'G21')
    lines.extend(hdr)

    current_feed = None
    current_rpm = None
    current_z = None

    for m in moves:
        k = m.get('kind')
        if k == 'comment':
            t = (m.get('text') or '').replace('(', '[').replace(')', ']')
            lines.append(f"({t})")
        elif k == 'set_rpm':
            rpm = m.get('rpm')
            if rpm != current_rpm:
                current_rpm = rpm
                ln = _rpm_line(rpm)
                if ln: lines.append(ln)
        elif k == 'set_feed':
            feed = m.get('feed')
            if feed is not None and feed != current_feed:
                current_feed = feed
                lines.append(f"F{_fmt_num(feed, max(0, prec - 2))}")
        elif k == 'rapid':
            x, y, z = m.get('x'), m.get('y'), m.get('z')
            lines.append(_g0(x, y, z, prec))
            if z is not None: current_z = z
        elif k == 'cut':
            x, y, z = m.get('x'), m.get('y'), m.get('z')
            lines.append(_g1(x, y, z, m.get('feed', current_feed), prec))
            if z is not None: current_z = z
            # NOTE: we intentionally do NOT update current_feed from a per-move feed,
            # because ops re-issue move_set_feed() after plunges.
        elif k == 'retract':
            z = m.get('z', safe_z)
            lines.append(_g0(None, None, z, prec))
            current_z = z
        else:
            lines.append(f"(unhandled move kind: {k})")

    if current_z is None or abs(current_z - safe_z) > 1e-9:
        lines.append(_g0(None, None, safe_z, prec))
    lines.extend(DEFAULT_FOOTER if footer is None else footer)
    return "\n".join(lines) + "\n"
