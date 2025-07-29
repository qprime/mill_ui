def deduplicate_path(path, tolerance=1e-5):
    """
    Remove repeated or near-identical XYZ points from each row.

    Args:
        path: List of List of (x, y, z) tuples
        tolerance: distance under which points are considered duplicates

    Returns:
        cleaned_path: same shape, with fewer points
        total_removed: int
    """
    cleaned = []
    total_removed = 0

    for row in path:
        if not row:
            cleaned.append([])
            continue

        new_row = [row[0]]
        for pt in row[1:]:
            last = new_row[-1]
            if (
                abs(pt[0] - last[0]) > tolerance
                or abs(pt[1] - last[1]) > tolerance
                or abs(pt[2] - last[2]) > tolerance
            ):
                new_row.append(pt)
            else:
                total_removed += 1

        cleaned.append(new_row)

    return cleaned, total_removed
