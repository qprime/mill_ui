
from skills.mill_ui.cam.types import Vec2, Transform2D
from skills.mill_ui.cam.shape import Shape2D
def place(shape:Shape2D, t:Transform2D)->Shape2D: return Shape2D([t.apply(p) for p in shape.points])
