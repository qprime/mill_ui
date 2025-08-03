# path: pipelines/cam_generator/analysis/curvature.py
# type: analysis_module
# tags: cam, analysis, curvature, numpy, scipy
# owner: cliff
# depends_on: numpy, scipy.ndimage.sobel
# description: Computes slope maps from heightmaps for curvature analysis in CAM generation.

import numpy as np
from scipy.ndimage import sobel


def compute_slope_map(heightmap, scale_xy=0.1):
    dz_dx = sobel(heightmap, axis=1) / (8.0 * scale_xy)
    dz_dy = sobel(heightmap, axis=0) / (8.0 * scale_xy)
    slope = np.sqrt(dz_dx**2 + dz_dy**2)
    return slope
