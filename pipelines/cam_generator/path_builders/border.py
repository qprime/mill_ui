"""
Generates a rectangular path around the carving area with an optional inward margin.
"""

def generate_border_path(width, height, depth, margin=1.0):
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
