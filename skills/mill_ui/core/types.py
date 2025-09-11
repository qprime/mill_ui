
from dataclasses import dataclass
from typing import Iterable, Tuple, List

@dataclass(frozen=True)
class Vec2:
    x: float; y: float
    def __add__(self, o:'Vec2')->'Vec2': return Vec2(self.x+o.x, self.y+o.y)
    def __sub__(self, o:'Vec2')->'Vec2': return Vec2(self.x-o.x, self.y-o.y)
    def scale(self, s: float)->'Vec2': return Vec2(self.x*s, self.y*s)
    def as_tuple(self)->Tuple[float,float]: return (self.x,self.y)

@dataclass(frozen=True)
class Bounds:
    minx: float; miny: float; maxx: float; maxy: float
    @staticmethod
    def from_points(pts: Iterable[Vec2])->'Bounds':
        xs=[p.x for p in pts]; ys=[p.y for p in pts]
        return Bounds(min(xs),min(ys),max(xs),max(ys))
    def expand(self, m: float)->'Bounds': return Bounds(self.minx-m,self.miny-m,self.maxx+m,self.maxy+m)
    def width(self)->float: return self.maxx - self.minx
    def height(self)->float: return self.maxy - self.miny

@dataclass(frozen=True)
class Transform2D:
    tx: float=0.0; ty: float=0.0
    def apply(self, p:Vec2)->Vec2: return Vec2(p.x+self.tx, p.y+self.ty)
