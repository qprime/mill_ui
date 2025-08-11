# path: skills/cam_generator/core/gcode_writer.py
# # desc: Write G-code lines to disk.
# api: write_gcode
# tags: cam

def write_gcode(gcode_lines, out_path):
    with open(out_path, "w") as f:
        f.write("\n".join(gcode_lines))
