import numpy as np

def is_colinear(p1, p2, p3, tolerance=1e-2):
    """
    Check if three 2D points are approximately colinear (ignores Z).
    """
    v1 = np.array([p2[0] - p1[0], p2[1] - p1[1]])
    v2 = np.array([p3[0] - p2[0], p3[1] - p2[1]])
    cross = np.cross(v1, v2)
    return abs(cross) < tolerance

def reduce_colinear_path(path, tolerance=1e-2):
    """
    Remove unnecessary colinear points from a raster path.

    Args:
        path: List of List of (x, y, z) tuples (i.e. rows of points)
        tolerance: float — max deviation to still consider colinear

    Returns:
        new_path: cleaned path with same shape
        total_removed: int — count of removed points
    """
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
