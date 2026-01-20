
from typing import List
from cam.types import Vec2
from cam.shape import Shape2D
def rectangle(w:float, h:float, origin:Vec2|None=None)->Shape2D:
    ox,oy=(origin.x,origin.y) if origin else (0.0,0.0)
    pts=[Vec2(ox,oy),Vec2(ox+w,oy),Vec2(ox+w,oy+h),Vec2(ox,oy+h),Vec2(ox,oy)]
    return Shape2D(pts)
def circle(center:Vec2, r:float, segments:int=64)->Shape2D:
    import math
    pts=[Vec2(center.x + r*math.cos(2*math.pi*i/segments),
              center.y + r*math.sin(2*math.pi*i/segments)) for i in range(segments)]
    pts.append(pts[0]); return Shape2D(pts)
def polygon(points: List[tuple], center: tuple[float, float] = (0.0, 0.0)) -> Shape2D:
    cx, cy = center
    pts = [Vec2(float(p[0]) + cx, float(p[1]) + cy) for p in points if isinstance(p, (tuple, list)) and len(p) >= 2]
    if len(pts) < 3:
        return Shape2D([])
    if pts[0].x != pts[-1].x or pts[0].y != pts[-1].y:
        pts.append(pts[0])
    return Shape2D(pts)

def rounded_rect(
    w: float,
    h: float,
    radii: dict[str, float] | float = 0.0,
    center: tuple[float, float] = (0.0, 0.0),
) -> Shape2D:
    import math
    if isinstance(radii, (int, float)):
        r_tl = r_tr = r_br = r_bl = float(radii)
    else:
        r_tl = float(radii.get('tl', radii.get('radius_mm', 0.0)))
        r_tr = float(radii.get('tr', radii.get('radius_mm', 0.0)))
        r_br = float(radii.get('br', radii.get('radius_mm', 0.0)))
        r_bl = float(radii.get('bl', radii.get('radius_mm', 0.0)))

    cx, cy = center
    ox, oy = cx - w / 2.0, cy - h / 2.0
    pts: List[Vec2] = []
    segs = 16

    def arc(acx: float, acy: float, r: float, start: float, end: float):
        if r <= 0:
            pts.append(Vec2(acx, acy))
        else:
            for i in range(segs + 1):
                t = start + (end - start) * i / segs
                pts.append(Vec2(acx + r * math.cos(t), acy + r * math.sin(t)))

    arc(ox + r_bl, oy + r_bl, r_bl, math.pi, 3 * math.pi / 2)
    arc(ox + w - r_br, oy + r_br, r_br, 3 * math.pi / 2, 2 * math.pi)
    arc(ox + w - r_tr, oy + h - r_tr, r_tr, 0, math.pi / 2)
    arc(ox + r_tl, oy + h - r_tl, r_tl, math.pi / 2, math.pi)
    pts.append(pts[0])
    return Shape2D(pts)
