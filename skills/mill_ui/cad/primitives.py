
from typing import List
from skills.mill_ui.core.types import Vec2
from skills.mill_ui.cad.shape import Shape2D
def rectangle(w:float, h:float, origin:Vec2|None=None)->Shape2D:
    ox,oy=(origin.x,origin.y) if origin else (0.0,0.0)
    pts=[Vec2(ox,oy),Vec2(ox+w,oy),Vec2(ox+w,oy+h),Vec2(ox,oy+h),Vec2(ox,oy)]
    return Shape2D(pts)
def circle(center:Vec2, r:float, segments:int=64)->Shape2D:
    import math
    pts=[Vec2(center.x + r*math.cos(2*math.pi*i/segments),
              center.y + r*math.sin(2*math.pi*i/segments)) for i in range(segments)]
    pts.append(pts[0]); return Shape2D(pts)
def rounded_rect(w:float, h:float, r:float)->Shape2D:
    import math
    pts=[]; segs=16
    def arc(cx,cy,start,end):
        for i in range(segs+1):
            t=start+(end-start)*i/segs
            pts.append(Vec2(cx + r*math.cos(t), cy + r*math.sin(t)))
    arc(r, h-r, math.pi, math.pi/2)
    arc(w-r, h-r, math.pi/2, 0)
    arc(w-r, r, 0, -math.pi/2)
    arc(r, r, -math.pi/2, -math.pi)
    pts.append(pts[0]); return Shape2D(pts)
