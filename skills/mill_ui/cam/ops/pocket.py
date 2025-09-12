# path: skills/mill_ui/cam/ops/pocket.py
from skills.mill_ui.cad.shape import Shape2D
from skills.mill_ui.cam.model.setup import Setup
from skills.mill_ui.cam.path.toolpath import (
    move_comment, move_set_rpm, move_set_feed, move_rapid, move_cut, move_retract
)

def pocket_raster(shape: Shape2D, setup: Setup, *, depth: float, stepover: float, stepdown: float):
    """
    Layered raster pocket:
      - Descend in Z by 'stepdown' until reaching -abs(depth).
      - For each layer, run horizontal scanlines every 'stepover'.
    """
    b = shape.bounds()
    z_target = -abs(float(depth))
    sd = max(0.1, float(stepdown))
    so = max(0.1, float(stepover))

    moves = []
    moves.append(move_comment(f"pocket_raster so={so:.3f} sd={sd:.3f} depth={z_target:.3f}"))
    moves.append(move_set_rpm(setup.tool.rpm))
    moves.append(move_set_feed(setup.tool.feed_xy))

    # Build Z levels: e.g., 0 → -3 → -6 → ... → z_target
    z_levels = []
    z = 0.0
    while z > z_target + 1e-9:
        z_next = max(z_target, z - sd)
        z_levels.append(z_next)
        z = z_next

    direction = 1
    for z in z_levels:
        y = b.miny
        while y <= b.maxy + 1e-9:
            x_start = b.minx if direction == 1 else b.maxx
            x_end   = b.maxx if direction == 1 else b.minx
            moves.append(move_rapid(x=x_start, y=y, z=setup.safe_z))
            moves.append(move_cut(z=z, feed=setup.tool.feed_z))    # plunge to layer Z
            moves.append(move_set_feed(setup.tool.feed_xy))        # restore XY feed
            moves.append(move_cut(x=x_end, y=y))                   # scanline
            moves.append(move_retract(setup.safe_z))
            y += so
            direction *= -1

    return moves
