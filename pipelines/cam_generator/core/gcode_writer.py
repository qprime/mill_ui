"""
Writes lists of G-code lines to disk.
"""

def write_gcode(gcode_lines, out_path):
    with open(out_path, 'w') as f:
        f.write('\n'.join(gcode_lines))