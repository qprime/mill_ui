import numpy as np

def compute_row_slopes(heightmap, scale_xy=0.1):
    """
    Computes an average slope magnitude per raster row using np.gradient.
    Returns a 1D array of slope values (same length as number of rows).
    """
    grad_y, grad_x = np.gradient(heightmap, scale_xy)
    slope_mag = np.sqrt(grad_x**2 + grad_y**2)
    row_slopes = np.mean(slope_mag, axis=1)
    return row_slopes

def map_slopes_to_stepovers(row_slopes, min_step=0.4, max_step=1.0, invert=False):
    """
    Map normalized slopes [0–1] to stepover values [max_step–min_step] (inverse).
    If invert=False, high slope = small step.
    """
    norm_slopes = (row_slopes - np.min(row_slopes)) / max(1e-6, np.ptp(row_slopes))
    if invert:
        norm_slopes = 1.0 - norm_slopes
    stepovers = min_step + (1.0 - norm_slopes) * (max_step - min_step)
    return stepovers
