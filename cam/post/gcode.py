# path: skills/mill_ui/cam/post/gcode.py

from cam.native import core as native_core

DEFAULT_HEADER = ['(begin)', 'G90', 'G21', 'G17', 'G94']
DEFAULT_FOOTER = ['M5', 'M2', '(end)']

def write_gcode(moves, *, unit='mm', prec=3, safe_z=5.0, header=None, footer=None):
    if unit not in ('mm','inch'):
        raise ValueError("unit must be 'mm' or 'inch'")
    return native_core.post_gcode(
        moves,
        unit=unit,
        prec=prec,
        safe_z=safe_z,
        header=None if header is None else header,
        footer=None if footer is None else footer,
    )
