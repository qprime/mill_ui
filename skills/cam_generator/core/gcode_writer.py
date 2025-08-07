# path: skills/cam_generator/core/gcode_writer.py
# type: utility module
# tags: gcode, file writing, cam
# owner: cliff
# depends_on: None
# description: Provides a function to write G-code lines to a file.

def write_gcode(gcode_lines, out_path):
    with open(out_path, "w") as f:
        f.write("\n".join(gcode_lines))
