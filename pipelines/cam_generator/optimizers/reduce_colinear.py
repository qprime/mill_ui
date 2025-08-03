# path: pipelines/cam_generator/optimizers/reduce_colinear.py
# type: geometry_optimizer
# tags: optimization, cam, geometry, numpy
# owner: cliff
# depends_on: numpy
# description: Provides functions to optimize CAM paths by reducing colinear points.

import numpy as np


def is_colinear(p1, p2, p3, tolerance=1e-2):
    v1 = np.array([p2[0] - p1[0], p2[1] - p1[1]])
    v2 = np.array([p3[0] - p2[0], p3[1] - p2[1]])
    cross = np.cross(v1, v2)
    return abs(cross) < tolerance


def reduce_colinear_path(path, tolerance=1e-2):
    reduced_path = []
    total_removed = 0
    for row in path:
        if len(row) <= 2:
            reduced_path.append(row)
            continue
        new_row = [row[0]]
        for i in range(1, len(row) - 1):
            if not is_colinear(row[i - 1], row[i], row[i + 1], tolerance):
                new_row.append(row[i])
            else:
                total_removed += 1
        new_row.append(row[-1])
        reduced_path.append(new_row)
    return reduced_path, total_removed
