import numpy as np

def generate_raster_xyz_path(heightmap, scale_xy, stepover, direction='x', z_clamp=None):
    rows, cols = heightmap.shape

    # Determine if we have adaptive stepovers (per-row list)
    if isinstance(stepover, (list, np.ndarray)):
        adaptive = True
        if len(stepover) != rows:
            raise ValueError("Adaptive stepover list must match number of heightmap rows")
    else:
        adaptive = False
        step_px = max(1, int(stepover / scale_xy))

    path = []

    if direction in ['x', 'zigzag-x']:
        lines = range(rows)
        axis = 'x'
    elif direction == 'y':
        lines = range(cols)
        axis = 'y'
    else:
        raise ValueError(f"Unsupported raster direction: {direction}")

    i_idx = 0
    while i_idx < rows:
        i = i_idx
        current_step_px = max(1, int(stepover[i] / scale_xy)) if adaptive else step_px

        serpentine = direction == 'zigzag-x'
        col_range = range(cols) if not serpentine or (i_idx % 2 == 0) else reversed(range(cols))

        row_points = []
        for j in col_range:
            x = j * scale_xy if axis == 'x' else i * scale_xy
            y = i * scale_xy if axis == 'x' else j * scale_xy
            z = -heightmap[i, j] if axis == 'x' else -heightmap[j, i]
            if z_clamp is not None:
                z = max(z, z_clamp)
            row_points.append((x, y, z))

        path.append(row_points)
        i_idx += current_step_px

    return path
