# path: skills/cam_generator/core/preview.py
# # desc: Matplotlib XY preview of G-code.
# api: preview_toolpath
# tags: cam

import matplotlib.pyplot as plt

def preview_toolpath(gcode_lines, z_fade=False, show=True, save_path=None):
    x_vals_cut, y_vals_cut, z_vals_cut = [], [], []
    x_vals_rapid, y_vals_rapid = [], []

    last_z = 0.0
    for line in gcode_lines:
        s = line.split(";", 1)[0].strip()
        if not s or not s.startswith(("G0", "G1")):
            continue

        parts = s.split()
        x = y = z = None
        for p in parts:
            if p.startswith("X"): x = float(p[1:])
            elif p.startswith("Y"): y = float(p[1:])
            elif p.startswith("Z"): z = float(p[1:])

        if s.startswith("G1"):
            if z is None: z = last_z
            if x is not None and y is not None:
                x_vals_cut.append(x); y_vals_cut.append(y); z_vals_cut.append(z)
            last_z = z
        else:
            if x is not None and y is not None:
                x_vals_rapid.append(x); y_vals_rapid.append(y)
            if z is not None: last_z = z

    fig, ax = plt.subplots(figsize=(10, 8))
    if z_fade and z_vals_cut:
        vmin = min(z_vals_cut); vmax = max(z_vals_cut)
        sc = ax.scatter(x_vals_cut, y_vals_cut, c=z_vals_cut, s=0.5, vmin=vmin, vmax=vmax, cmap="viridis")
        plt.colorbar(sc, label="Z Depth (mm)")
    else:
        ax.plot(x_vals_cut, y_vals_cut, linewidth=0.5)

    if x_vals_rapid:
        ax.plot(x_vals_rapid, y_vals_rapid, linewidth=0.2, alpha=0.25)

    ax.set_title("Toolpath Preview (cuts only)")
    ax.set_xlabel("X (mm)"); ax.set_ylabel("Y (mm)")
    ax.set_aspect("equal"); ax.grid(True)
    if save_path: plt.savefig(save_path, dpi=300)
    if show: plt.show()
    plt.close()
