# path: skills/cam_generator/core/time_estimator.py
# type: time estimation utility
# tags: CAM, G-code, time estimation, utility
# owner: cliff
# depends_on: math
# description: Estimates G-code cut time for CAM operations with configurable parameters.

import math


def estimate_cut_time(
    gcode_lines,
    default_feedrate=300,
    include_rapids=False,
    fudge_factor=1.15,
    debug=False,
):
    total_time_min = 0.0
    prev = {"X": None, "Y": None, "Z": None}
    current_feed = default_feedrate
    total_distance = 0.0
    for line in gcode_lines:
        line = line.strip()
        if ";" in line:
            line = line.split(";")[0].strip()
        if not line:
            continue
        if not line.startswith(("G0", "G1")):
            continue
        if line.startswith("G0") and not include_rapids:
            continue
        x = prev["X"]
        y = prev["Y"]
        z = prev["Z"]
        feed = current_feed
        parts = line.split()
        for part in parts:
            if part.startswith("X"):
                try:
                    x = float(part[1:])
                except ValueError:
                    continue
            elif part.startswith("Y"):
                try:
                    y = float(part[1:])
                except ValueError:
                    continue
            elif part.startswith("Z"):
                try:
                    z = float(part[1:])
                except ValueError:
                    continue
            elif part.startswith("F"):
                try:
                    feed = float(part[1:])
                except ValueError:
                    continue
        if x is not None and y is not None and z is not None:
            dx = (x - prev["X"]) if prev["X"] is not None else 0.0
            dy = (y - prev["Y"]) if prev["Y"] is not None else 0.0
            dz = (z - prev["Z"]) if prev["Z"] is not None else 0.0
            dist = math.sqrt(dx**2 + dy**2 + dz**2)
            total_distance += dist
            if feed > 0:
                time_min = dist / feed
                total_time_min += time_min
                if debug:
                    print(
                        f"Move: X{x :.3f} Y{y :.3f} Z{z :.3f} | d={dist :.4f} mm @ {feed :.0f} → {time_min :.4f} min"
                    )
        prev = {"X": x, "Y": y, "Z": z}
        current_feed = feed
    if debug:
        print(f"[Debug] Total distance moved: {total_distance :.3f} mm")
        print(f"[Debug] Raw runtime: {total_time_min :.2f} min")
        print(f"[Debug] Fudge factor applied: x{fudge_factor }")
    return total_time_min * fudge_factor
