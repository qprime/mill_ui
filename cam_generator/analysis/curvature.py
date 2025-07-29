import numpy as np
from scipy.ndimage import sobel

def compute_slope_map(heightmap, scale_xy=0.1):
    """
    Compute slope (gradient magnitude) per pixel in mm/mm.
    """
    dz_dx = sobel(heightmap, axis=1) / (8.0 * scale_xy)
    dz_dy = sobel(heightmap, axis=0) / (8.0 * scale_xy)
    slope = np.sqrt(dz_dx ** 2 + dz_dy ** 2)
    return slope
