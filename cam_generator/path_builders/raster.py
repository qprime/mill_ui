import numpy as np

def generate_raster_xyz_path(
    heightmap,
    scale_xy,
    stepover,
    direction='x',
    z_clamp=None,
    slope_map=None,
    adaptive=True,
    offset_x=0.0,
    offset_y=0.0
):
    """
    Generate XYZ toolpath using raster pattern (zigzag-x) with optional adaptive stepover.

    Args:
        heightmap: 2D numpy array
        scale_xy: float, mm per pixel
        stepover: float, base stepover in mm
        direction: 'x' or 'zigzag-x'
        z_clamp: [min, max] or dict or None
        slope_map: 2D array matching heightmap
        adaptive: bool — enable adaptive stepover if slope_map is present
        offset_x: float — shift X origin (e.g. for border alignment)
        offset_y: float — shift Y origin

    Returns:
        List of List of (x, y, z) tuples (raster path)
    """
    h, w = heightmap.shape
    base_dx = int(stepover / scale_xy)
    base_dx = max(1, base_dx)

    # Z clamping setup
    if isinstance(z_clamp, dict):
        z_min = z_clamp.get("min", None)
        z_max = z_clamp.get("max", None)
    elif isinstance(z_clamp, (list, tuple)) and len(z_clamp) == 2:
        z_min, z_max = z_clamp
    else:
        z_min = z_clamp
        z_max = None

    path = []
    for i, row_idx in enumerate(range(0, h, base_dx)):
        y = row_idx * scale_xy + offset_y
        row = []

        xs = list(range(w))
        if direction == 'zigzag-x' and (i % 2 == 1):
            xs = list(reversed(xs))

        x_pos = 0
        while x_pos < len(xs):
            col_idx = xs[x_pos]
            x = col_idx * scale_xy + offset_x
            z = -heightmap[row_idx, col_idx]

            if z_min is not None:
                z = max(z, z_min)
            if z_max is not None:
                z = min(z, z_max)

            row.append((x, y, z))

            # Adaptive stepover
            if adaptive and slope_map is not None:
                slope = slope_map[row_idx, col_idx]
                if slope < 0.02:
                    local_dx = int(base_dx * 1.5)
                elif slope > 0.1:
                    local_dx = int(base_dx * 0.5)
                else:
                    local_dx = base_dx
                local_dx = max(1, local_dx)
            else:
                local_dx = base_dx

            x_pos += local_dx

        path.append(row)

    return path
