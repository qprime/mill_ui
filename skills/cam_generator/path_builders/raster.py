# path: skills/cam_generator/path_builders/raster.py
# type: path generation
# tags: cam, raster, numpy, heightmap, utility
# owner: cliff
# depends_on: numpy
# description: Generates raster tool paths for CAM based on heightmaps and various parameters.

import numpy as np

def sample_smoothed_z(heightmap, x, y, kernel=3):
    half = kernel // 2
    x0, x1 = max(0, x - half), min(heightmap.shape[1], x + half + 1)
    y0, y1 = max(0, y - half), min(heightmap.shape[0], y + half + 1)
    region = heightmap[y0:y1, x0:x1]
    return np.mean(region)

def generate_raster_xyz_path(
    heightmap,
    scale_xy,
    stepover,
    direction="x",
    z_clamp=None,
    slope_map=None,
    adaptive=True,
    offset_x=0.0,
    offset_y=0.0,
    z_smooth_kernel=3,
    skip_mask=None,               # NEW: boolean array; True means skip at that pixel
):
    h, w = heightmap.shape
    base_dx = int(stepover / scale_xy)
    base_dx = max(1, base_dx)

    # Parse z_clamp
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

        # Zigzag order
        xs = list(range(w))
        if direction == "zigzag-x" and (i % 2 == 1):
            xs = list(reversed(xs))

        x_pos = 0
        ncols = len(xs)
        seg = []                  # accumulate a segment; flush on skip
        while x_pos < ncols:
            col_idx = xs[x_pos]
            x = col_idx * scale_xy + offset_x

            # Skip logic (diameter-aware keepout or other mask)
            if skip_mask is not None:
                # Protect bounds mismatch just in case
                if 0 <= row_idx < skip_mask.shape[0] and 0 <= col_idx < skip_mask.shape[1]:
                    if bool(skip_mask[row_idx, col_idx]):
                        if seg:         # flush current segment if any
                            path.append(seg)
                            seg = []
                        x_pos += 1
                        continue

            # Z sample (smoothed heightmap → machining Z is negative)
            z_val = sample_smoothed_z(heightmap, col_idx, row_idx, kernel=z_smooth_kernel)
            z = -z_val

            # Clamp
            if z_min is not None:
                z = max(z, z_min)
            if z_max is not None:
                z = min(z, z_max)

            seg.append((x, y, z))

            # Adaptive step (by slope if provided)
            if adaptive and slope_map is not None:
                s = slope_map[row_idx, col_idx]
                if s < 0.02:
                    local_dx = int(base_dx * 1.5)
                elif s > 0.1:
                    local_dx = int(base_dx * 0.5)
                else:
                    local_dx = base_dx
                local_dx = max(1, local_dx)
            else:
                local_dx = base_dx

            x_pos += local_dx

        if seg:
            path.append(seg)

    return path
