import numpy as np

def is_colinear(p1, p2, p3, tolerance=1e-2):
    # Check if three points are approximately colinear (in 2D)
    v1 = np.array([p2[0] - p1[0], p2[1] - p1[1]])
    v2 = np.array([p3[0] - p2[0], p3[1] - p2[1]])
    cross = np.cross(v1, v2)
    return abs(cross) < tolerance

def reduce_colinear_path(path, tolerance=1e-2):
    """
    Reduce colinear moves in a raster path.

    Parameters:
        path: List[List[(x, y, z)]]
        tolerance: float — max deviation to still consider points colinear

    Returns:
        reduced_path: same shape as input, but with reduced inner points
        total_removed: number of skipped points
    """
    reduced_path = []
    total_removed = 0

    for row in path:
        if len(row) <= 2:
            reduced_path.append(row)
            continue

        reduced_row = [row[0]]
        for i in range(1, len(row) - 1):
            p1, p2, p3 = row[i - 1], row[i], row[i + 1]
            if not is_colinear(p1, p2, p3, tolerance):
                reduced_row.append(p2)
            else:
                total_removed += 1
        reduced_row.append(row[-1])
        reduced_path.append(reduced_row)

    return reduced_path, total_removed
