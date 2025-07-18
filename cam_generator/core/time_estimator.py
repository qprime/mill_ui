from math import sqrt

def estimate_cut_time(gcode_lines, include_rapids=False):
    last_x = last_y = last_z = None
    last_feed = 300  # default mm/min
    total_time_min = 0.0

    for line in gcode_lines:
        line = line.strip()
        if not line.startswith(("G0", "G1")):
            continue
        if line.startswith("G0") and not include_rapids:
            continue

        parts = line.split()
        x = y = z = None
        feed = None

        for part in parts:
            if part.startswith("X"):
                x = float(part[1:])
            elif part.startswith("Y"):
                y = float(part[1:])
            elif part.startswith("Z"):
                z = float(part[1:])
            elif part.startswith("F"):
                feed = float(part[1:])

        # Use last known positions if not specified
        x = x if x is not None else last_x
        y = y if y is not None else last_y
        z = z if z is not None else last_z
        feed = feed if feed is not None else last_feed

        if None in (x, y, z):
            continue

        dist = sqrt((x - last_x) ** 2 + (y - last_y) ** 2 + (z - last_z) ** 2) if all(v is not None for v in [last_x, last_y, last_z]) else 0

        if feed > 0:
            time_min = dist / feed  # mm / (mm/min) = min
            total_time_min += time_min

        last_x, last_y, last_z = x, y, z
        last_feed = feed

    return total_time_min
