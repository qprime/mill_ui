"""
Generates G-code for smart pocket holer with configurable parameters.
"""

import yaml

def load_pocket_config(path="pocket_config.yaml"):
    with open(path, "r") as f:
        cfg = yaml.safe_load(f)
    return cfg

def generate_smart_pocket_holer_gcode(cfg):
    depths = cfg["pocket_depths"]
    spacing = cfg.get("spacing", 8.0)
    pocket_size = cfg.get("pocket_size", 15.0)
    tool_diameter = cfg.get("tool_diameter", 3.175)
    step_down = cfg.get("step_down", 1.0)
    safe_height = cfg.get("safe_height", 5.0)
    feedrate = cfg.get("feedrate", 300)
    plunge_rate = cfg.get("plunge_rate", 100)
    units = cfg.get("units", "mm")
    start_x = cfg.get("start_x", 0.0)
    start_y = cfg.get("start_y", 0.0)

    gcode = []

    gcode.append("G21" if units == "mm" else "G20")
    gcode.append("G90 ; Absolute positioning")
    gcode.append(f"G0 Z{safe_height:.3f}")

    x = start_x
    y = start_y

    for depth in depths:
        gcode.append(f"\n; Pocket depth {depth}mm")
        current_z = 0.0
        z_steps = []
        while current_z - step_down > -depth:
            current_z -= step_down
            z_steps.append(current_z)
        z_steps.append(-depth)

        for z in z_steps:
            gcode.append(f"G0 X{x:.3f} Y{y:.3f}")
            gcode.append(f"G1 Z{z:.3f} F{plunge_rate}")
            gcode.append(f"G1 X{x + pocket_size:.3f} Y{y:.3f} F{feedrate}")
            gcode.append(f"G1 X{x + pocket_size:.3f} Y{y + pocket_size:.3f}")
            gcode.append(f"G1 X{x:.3f} Y{y + pocket_size:.3f}")
            gcode.append(f"G1 X{x:.3f} Y{y:.3f}")
            gcode.append(f"G0 Z{safe_height:.3f}")

        x += pocket_size + spacing

    gcode.append("G0 Z5.000")
    gcode.append("G0 X0 Y0")
    return "\n".join(gcode)

if __name__ == "__main__":
    cfg = load_pocket_config()
    gcode_out = generate_smart_pocket_holer_gcode(cfg)
    with open("smart_pocket_holer.nc", "w") as f:
        f.write(gcode_out)
    print("G-code written to smart_pocket_holer.nc")