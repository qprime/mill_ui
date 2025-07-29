def generate_border_path(width, height, depth, margin=1.0):
    """
    Create a rectangular path around (0,0) with optional inward margin.

    Args:
        width: total width of the carving area (mm)
        height: total height of the carving area (mm)
        depth: Z value (typically negative)
        margin: how far *inside* to pull the border (mm)

    Returns:
        List of list of (x, y, z) tuples
    """
    x0 = margin
    y0 = margin
    x1 = width - margin
    y1 = height - margin

    points = [
        (x0, y0, depth),
        (x1, y0, depth),
        (x1, y1, depth),
        (x0, y1, depth),
        (x0, y0, depth),
    ]
    return [points]
