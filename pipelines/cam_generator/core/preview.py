"""
Renders toolpath previews as matplotlib images.
"""

import matplotlib.pyplot as plt

def preview_toolpath(gcode_lines, z_fade=False, show=True, save_path=None):
    x_vals = []
    y_vals = []
    z_vals = []
    for line in gcode_lines:
        if line.startswith("G1") or line.startswith("G0"):
            parts = line.split()
            x = y = z = None
            for part in parts:
                if part.startswith("X"):
                    x = float(part[1:])
                elif part.startswith("Y"):
                    y = float(part[1:])
                elif part.startswith("Z"):
                    z = float(part[1:])
            if x is not None and y is not None:
                x_vals.append(x)
                y_vals.append(y)
                z_vals.append(z if z is not None else z_vals[-1] if z_vals else 0)
    fig, ax = plt.subplots(figsize=(10, 8))
    if z_fade:
        sc = ax.scatter(x_vals, y_vals, c=z_vals, cmap='viridis', s=0.5)
        plt.colorbar(sc, label='Z Depth (mm)')
    else:
        ax.plot(x_vals, y_vals, linewidth=0.5, color='black')
    ax.set_title("Toolpath Preview")
    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Y (mm)")
    ax.set_aspect('equal')
    ax.grid(True)
    if save_path:
        plt.savefig(save_path, dpi=300)
    if show:
        plt.show()
    plt.close()
