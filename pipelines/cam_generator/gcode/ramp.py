# path: pipelines/cam_generator/gcode/ramp.py
# type: gcode utility
# tags: cam, gcode, ramp, numpy
# owner: cliff
# depends_on: numpy
# description: Generates z-axis ramp coordinates for G-code. Used in toolpath generation.

import numpy as np


def generate_z_ramp(x, y, z_start, z_end, step_mm=0.5):
    if z_start == z_end:
        return [(x, y, z_end)]

    step_count = max(2, int(abs(z_start - z_end) / abs(step_mm)))
    zs = np.linspace(z_start, z_end, step_count)
    return [(x, y, z) for z in zs]
