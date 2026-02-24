from __future__ import annotations

import json
import math
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Literal

from shapely import BufferJoinStyle
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import orient
from shapely.validation import make_valid

Point2D = tuple[float, float]
Boundary = tuple[Point2D, ...]


JoinStyle = Literal["mitre", "round", "bevel"]


def _normalize_boundary(
    coords: list[list[float]] | list[tuple[float, float]] | tuple[tuple[float, ...], ...] | tuple[Point2D, ...],
) -> tuple[Point2D, ...]:
    result = []
    for point in coords:
        if len(point) < 2:
            raise ValueError(f"Point must have at least 2 coordinates, got {len(point)}")
        result.append((float(point[0]), float(point[1])))
    return tuple(result)


def _shapely_join_style(style: JoinStyle) -> BufferJoinStyle:
    from shapely import BufferJoinStyle

    mapping: dict[str, BufferJoinStyle] = {
        "mitre": BufferJoinStyle.mitre,
        "round": BufferJoinStyle.round,
        "bevel": BufferJoinStyle.bevel,
    }
    if style not in mapping:
        raise ValueError(f"Invalid join_style '{style}'. Must be one of: mitre, round, bevel")
    return mapping[style]


@dataclass(frozen=True)
class Bounds2D:
    x_min: float
    x_max: float
    y_min: float
    y_max: float

    def __post_init__(self) -> None:
        if self.x_max < self.x_min:
            raise ValueError(f"x_max ({self.x_max}) < x_min ({self.x_min})")
        if self.y_max < self.y_min:
            raise ValueError(f"y_max ({self.y_max}) < y_min ({self.y_min})")

    @property
    def width(self) -> float:
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        return self.y_max - self.y_min

    @property
    def center(self) -> Point2D:
        return (
            (self.x_min + self.x_max) / 2,
            (self.y_min + self.y_max) / 2,
        )


@dataclass(frozen=True)
class Domain:
    outer_boundary: Boundary
    inner_boundaries: tuple[Boundary, ...] = field(default_factory=tuple)
    local_origin: Point2D | None = None
    local_rotation_rad: float = 0.0

    _polygon: Polygon | None = field(default=None, repr=False, compare=False, hash=False)

    def __post_init__(self) -> None:

        if len(self.outer_boundary) < 3:
            raise ValueError(f"Outer boundary must have at least 3 points, got {len(self.outer_boundary)}")

        for i, inner in enumerate(self.inner_boundaries):
            if len(inner) < 3:
                raise ValueError(f"Inner boundary {i} must have at least 3 points, got {len(inner)}")

        poly = self._build_polygon()

        if not poly.is_valid:
            valid_geom = make_valid(poly)
            if not valid_geom.is_valid:
                raise ValueError(f"Domain geometry is invalid: {valid_geom.is_valid}")
            if not isinstance(valid_geom, Polygon):
                raise ValueError("Domain geometry becomes invalid after normalization (splits into multiple regions)")
            poly = valid_geom

        poly = orient(poly, sign=1.0)

        outer_coords = tuple((float(x), float(y)) for x, y in poly.exterior.coords[:-1])
        inner_coords = tuple(
            tuple((float(x), float(y)) for x, y in interior.coords[:-1]) for interior in poly.interiors
        )

        object.__setattr__(self, "outer_boundary", outer_coords)
        object.__setattr__(self, "inner_boundaries", inner_coords)
        object.__setattr__(self, "_polygon", poly)

        outer_ring = Polygon(self.outer_boundary)
        for i, inner in enumerate(self.inner_boundaries):
            inner_poly = Polygon(inner)
            if not outer_ring.contains(inner_poly):
                raise ValueError(f"Inner boundary {i} is not fully contained within outer boundary")

        for i in range(len(self.inner_boundaries)):
            for j in range(i + 1, len(self.inner_boundaries)):
                inner_i = Polygon(self.inner_boundaries[i])
                inner_j = Polygon(self.inner_boundaries[j])
                if inner_i.intersects(inner_j) and not inner_i.touches(inner_j):
                    raise ValueError(f"Inner boundaries {i} and {j} overlap")

        if self.local_origin is None:
            centroid = self._centroid
            object.__setattr__(self, "local_origin", centroid)

    def _build_polygon(self) -> Polygon:
        if self.inner_boundaries:
            return Polygon(self.outer_boundary, self.inner_boundaries)
        return Polygon(self.outer_boundary)

    @property
    def polygon(self) -> Polygon:
        if self._polygon is None:
            object.__setattr__(self, "_polygon", self._build_polygon())
        assert self._polygon is not None
        return self._polygon

    @property
    def _centroid(self) -> Point2D:
        c = self.polygon.centroid
        return (float(c.x), float(c.y))

    @property
    def bounds(self) -> Bounds2D:
        minx, miny, maxx, maxy = self.polygon.bounds
        return Bounds2D(
            x_min=float(minx),
            x_max=float(maxx),
            y_min=float(miny),
            y_max=float(maxy),
        )

    @property
    def area_mm2(self) -> float:
        return float(self.polygon.area)

    @property
    def centroid(self) -> Point2D:
        return self._centroid

    def with_origin_at_centroid(self) -> Domain:
        return Domain(
            outer_boundary=self.outer_boundary,
            inner_boundaries=self.inner_boundaries,
            local_origin=self.centroid,
            local_rotation_rad=self.local_rotation_rad,
        )

    def inset(
        self,
        distance: float,
        join_style: JoinStyle = "mitre",
        mitre_limit: float = 5.0,
    ) -> MultiDomain:
        if distance < 0:
            raise ValueError(f"Inset distance must be non-negative, got {distance}")
        if distance == 0:
            return MultiDomain(domains=(self,))

        result = self.polygon.buffer(
            -distance,
            join_style=_shapely_join_style(join_style),
            mitre_limit=mitre_limit,
        )

        return self._geometry_to_multidomain(result)

    def offset(
        self,
        distance: float,
        join_style: JoinStyle = "mitre",
        mitre_limit: float = 5.0,
    ) -> MultiDomain:
        if distance < 0:
            raise ValueError(f"Offset distance must be non-negative, got {distance}")
        if distance == 0:
            return MultiDomain(domains=(self,))

        result = self.polygon.buffer(
            distance,
            join_style=_shapely_join_style(join_style),
            mitre_limit=mitre_limit,
        )

        return self._geometry_to_multidomain(result)

    def subtract(self, other: Domain) -> MultiDomain:
        result = self.polygon.difference(other.polygon)
        return self._geometry_to_multidomain(result)

    def intersect(self, other: Domain) -> MultiDomain:
        result = self.polygon.intersection(other.polygon)
        return self._geometry_to_multidomain(result)

    def _transform_point_to_local(self, point: Point2D) -> Point2D:
        ox, oy = self.local_origin if self.local_origin is not None else (0.0, 0.0)
        px, py = point

        dx, dy = px - ox, py - oy

        if self.local_rotation_rad != 0:
            cos_r = math.cos(-self.local_rotation_rad)
            sin_r = math.sin(-self.local_rotation_rad)
            lx = dx * cos_r - dy * sin_r
            ly = dx * sin_r + dy * cos_r
        else:
            lx, ly = dx, dy

        return (lx, ly)

    def _transform_point_to_sheet(self, local_point: Point2D) -> Point2D:
        ox, oy = self.local_origin if self.local_origin is not None else (0.0, 0.0)
        lx, ly = local_point

        if self.local_rotation_rad != 0:
            cos_r = math.cos(self.local_rotation_rad)
            sin_r = math.sin(self.local_rotation_rad)
            dx = lx * cos_r - ly * sin_r
            dy = lx * sin_r + ly * cos_r
        else:
            dx, dy = lx, ly

        return (ox + dx, oy + dy)

    def _transform_boundary_to_local(self, boundary: Boundary) -> Boundary:
        return tuple(self._transform_point_to_local(p) for p in boundary)

    def _transform_boundary_to_sheet(self, boundary: Boundary) -> Boundary:
        return tuple(self._transform_point_to_sheet(p) for p in boundary)

    def _to_local_domain(self) -> Domain:
        local_outer = self._transform_boundary_to_local(self.outer_boundary)
        local_inners = tuple(self._transform_boundary_to_local(inner) for inner in self.inner_boundaries)

        return Domain(
            outer_boundary=local_outer,
            inner_boundaries=local_inners,
            local_origin=(0.0, 0.0),
            local_rotation_rad=0.0,
        )

    def _from_local_domain(self, local_domain: Domain) -> Domain:
        sheet_outer = self._transform_boundary_to_sheet(local_domain.outer_boundary)
        sheet_inners = tuple(self._transform_boundary_to_sheet(inner) for inner in local_domain.inner_boundaries)

        return Domain(
            outer_boundary=sheet_outer,
            inner_boundaries=sheet_inners,
            local_origin=self.local_origin,
            local_rotation_rad=self.local_rotation_rad,
        )

    def split_horizontal(
        self,
        n: int,
        gap_mm: float = 0.0,
        local_coords: bool = False,
    ) -> MultiDomain:
        if n < 1:
            raise ValueError(f"split_horizontal: n must be >= 1, got {n}")
        if gap_mm < 0:
            raise ValueError(f"split_horizontal: gap_mm must be non-negative, got {gap_mm}")

        if local_coords and self.local_rotation_rad != 0:
            local_domain = self._to_local_domain()
            local_result = local_domain.split_horizontal(n, gap_mm, local_coords=False)

            domains = []
            for d in local_result:
                sheet_domain = self._from_local_domain(d)
                domains.append(sheet_domain)
            return MultiDomain(domains=tuple(domains))

        bounds = self.bounds
        total_gap = gap_mm * (n - 1)

        if total_gap >= bounds.height:
            raise ValueError(f"split_horizontal: total gap {total_gap}mm exceeds domain height {bounds.height}mm")

        available_height = bounds.height - total_gap
        cell_height = available_height / n

        domains = []
        for i in range(n):
            y_min = bounds.y_min + i * (cell_height + gap_mm)
            y_max = y_min + cell_height
            cell_center = (
                (bounds.x_min + bounds.x_max) / 2,
                (y_min + y_max) / 2,
            )

            cell = Domain.from_rectangle(
                width_mm=bounds.width,
                height_mm=cell_height,
                center=cell_center,
            )
            intersection = self.intersect(cell)

            for d in intersection:
                domain_with_origin = Domain(
                    outer_boundary=d.outer_boundary,
                    inner_boundaries=d.inner_boundaries,
                    local_origin=self.local_origin,
                    local_rotation_rad=self.local_rotation_rad,
                )
                domains.append(domain_with_origin)

        return MultiDomain(domains=tuple(domains))

    def split_vertical(
        self,
        n: int,
        gap_mm: float = 0.0,
        local_coords: bool = False,
    ) -> MultiDomain:
        if n < 1:
            raise ValueError(f"split_vertical: n must be >= 1, got {n}")
        if gap_mm < 0:
            raise ValueError(f"split_vertical: gap_mm must be non-negative, got {gap_mm}")

        if local_coords and self.local_rotation_rad != 0:
            local_domain = self._to_local_domain()
            local_result = local_domain.split_vertical(n, gap_mm, local_coords=False)

            domains = []
            for d in local_result:
                sheet_domain = self._from_local_domain(d)
                domains.append(sheet_domain)
            return MultiDomain(domains=tuple(domains))

        bounds = self.bounds
        total_gap = gap_mm * (n - 1)

        if total_gap >= bounds.width:
            raise ValueError(f"split_vertical: total gap {total_gap}mm exceeds domain width {bounds.width}mm")

        available_width = bounds.width - total_gap
        cell_width = available_width / n

        domains = []
        for i in range(n):
            x_min = bounds.x_min + i * (cell_width + gap_mm)
            x_max = x_min + cell_width
            cell_center = (
                (x_min + x_max) / 2,
                (bounds.y_min + bounds.y_max) / 2,
            )

            cell = Domain.from_rectangle(
                width_mm=cell_width,
                height_mm=bounds.height,
                center=cell_center,
            )
            intersection = self.intersect(cell)

            for d in intersection:
                domain_with_origin = Domain(
                    outer_boundary=d.outer_boundary,
                    inner_boundaries=d.inner_boundaries,
                    local_origin=self.local_origin,
                    local_rotation_rad=self.local_rotation_rad,
                )
                domains.append(domain_with_origin)

        return MultiDomain(domains=tuple(domains))

    def split_grid(
        self,
        rows: int,
        cols: int,
        gap_mm: float = 0.0,
        local_coords: bool = False,
    ) -> MultiDomain:
        if rows < 1:
            raise ValueError(f"split_grid: rows must be >= 1, got {rows}")
        if cols < 1:
            raise ValueError(f"split_grid: cols must be >= 1, got {cols}")
        if gap_mm < 0:
            raise ValueError(f"split_grid: gap_mm must be non-negative, got {gap_mm}")

        if local_coords and self.local_rotation_rad != 0:
            local_domain = self._to_local_domain()
            local_result = local_domain.split_grid(rows, cols, gap_mm, local_coords=False)

            domains = []
            for d in local_result:
                sheet_domain = self._from_local_domain(d)
                domains.append(sheet_domain)
            return MultiDomain(domains=tuple(domains))

        bounds = self.bounds
        total_h_gap = gap_mm * (cols - 1)
        total_v_gap = gap_mm * (rows - 1)

        if total_h_gap >= bounds.width:
            raise ValueError(f"split_grid: total horizontal gap {total_h_gap}mm exceeds domain width {bounds.width}mm")
        if total_v_gap >= bounds.height:
            raise ValueError(f"split_grid: total vertical gap {total_v_gap}mm exceeds domain height {bounds.height}mm")

        cell_width = (bounds.width - total_h_gap) / cols
        cell_height = (bounds.height - total_v_gap) / rows

        domains = []

        for row in range(rows):
            for col in range(cols):
                x_min = bounds.x_min + col * (cell_width + gap_mm)
                y_min = bounds.y_min + row * (cell_height + gap_mm)
                cell_center = (
                    x_min + cell_width / 2,
                    y_min + cell_height / 2,
                )

                cell = Domain.from_rectangle(
                    width_mm=cell_width,
                    height_mm=cell_height,
                    center=cell_center,
                )
                intersection = self.intersect(cell)

                for d in intersection:
                    domain_with_origin = Domain(
                        outer_boundary=d.outer_boundary,
                        inner_boundaries=d.inner_boundaries,
                        local_origin=self.local_origin,
                        local_rotation_rad=self.local_rotation_rad,
                    )
                    domains.append(domain_with_origin)

        return MultiDomain(domains=tuple(domains))

    def split_horizontal_with_gaps(
        self,
        n: int,
        gap_mm: float,
        local_coords: bool = False,
    ) -> tuple[MultiDomain, MultiDomain]:
        if n < 1:
            raise ValueError(f"split_horizontal_with_gaps: n must be >= 1, got {n}")
        if gap_mm <= 0:
            raise ValueError(f"split_horizontal_with_gaps: gap_mm must be positive, got {gap_mm}")

        if local_coords and self.local_rotation_rad != 0:
            local_domain = self._to_local_domain()
            local_cells, local_gaps = local_domain.split_horizontal_with_gaps(n, gap_mm, local_coords=False)

            cells = []
            for d in local_cells:
                cells.append(self._from_local_domain(d))
            gaps = []
            for d in local_gaps:
                gaps.append(self._from_local_domain(d))
            return MultiDomain(domains=tuple(cells)), MultiDomain(domains=tuple(gaps))

        bounds = self.bounds
        total_gap = gap_mm * (n - 1)

        if total_gap >= bounds.height:
            raise ValueError(
                f"split_horizontal_with_gaps: total gap {total_gap}mm exceeds domain height {bounds.height}mm"
            )

        available_height = bounds.height - total_gap
        cell_height = available_height / n

        cells = []
        gaps = []

        for i in range(n):
            y_min = bounds.y_min + i * (cell_height + gap_mm)
            y_max = y_min + cell_height
            cell_center = (
                (bounds.x_min + bounds.x_max) / 2,
                (y_min + y_max) / 2,
            )

            cell = Domain.from_rectangle(
                width_mm=bounds.width,
                height_mm=cell_height,
                center=cell_center,
            )
            cell_intersection = self.intersect(cell)

            for d in cell_intersection:
                domain_with_origin = Domain(
                    outer_boundary=d.outer_boundary,
                    inner_boundaries=d.inner_boundaries,
                    local_origin=self.local_origin,
                    local_rotation_rad=self.local_rotation_rad,
                )
                cells.append(domain_with_origin)

            if i < n - 1:
                gap_y_min = y_max
                gap_y_max = gap_y_min + gap_mm
                gap_center = (
                    (bounds.x_min + bounds.x_max) / 2,
                    (gap_y_min + gap_y_max) / 2,
                )

                gap_domain = Domain.from_rectangle(
                    width_mm=bounds.width,
                    height_mm=gap_mm,
                    center=gap_center,
                )
                gap_intersection = self.intersect(gap_domain)

                for d in gap_intersection:
                    domain_with_origin = Domain(
                        outer_boundary=d.outer_boundary,
                        inner_boundaries=d.inner_boundaries,
                        local_origin=self.local_origin,
                        local_rotation_rad=self.local_rotation_rad,
                    )
                    gaps.append(domain_with_origin)

        return MultiDomain(domains=tuple(cells)), MultiDomain(domains=tuple(gaps))

    def _geometry_to_multidomain(self, geom: BaseGeometry) -> MultiDomain:
        if geom.is_empty:
            return MultiDomain(domains=())

        polygons: list[Polygon] = []
        if isinstance(geom, Polygon):
            polygons.append(geom)
        elif isinstance(geom, MultiPolygon):
            polygons.extend(geom.geoms)
        elif isinstance(geom, GeometryCollection):
            for g in geom.geoms:
                if isinstance(g, Polygon):
                    polygons.append(g)
                elif isinstance(g, MultiPolygon):
                    polygons.extend(g.geoms)

            if not polygons:
                return MultiDomain(domains=())
        else:
            return MultiDomain(domains=())

        domains = []
        for poly in polygons:
            if poly.is_empty or poly.area < 1e-10:
                continue

            poly = orient(poly, sign=1.0)

            outer = tuple((float(x), float(y)) for x, y in poly.exterior.coords[:-1])
            inners = tuple(tuple((float(x), float(y)) for x, y in interior.coords[:-1]) for interior in poly.interiors)

            domain = Domain(
                outer_boundary=outer,
                inner_boundaries=inners,
                local_origin=self.local_origin,
                local_rotation_rad=self.local_rotation_rad,
            )
            domains.append(domain)

        return MultiDomain(domains=tuple(domains))

    @classmethod
    def from_rectangle(
        cls,
        width_mm: float,
        height_mm: float,
        center: Point2D = (0.0, 0.0),
        rotation_rad: float = 0.0,
    ) -> Domain:
        if width_mm <= 0:
            raise ValueError(f"Width must be positive, got {width_mm}")
        if height_mm <= 0:
            raise ValueError(f"Height must be positive, got {height_mm}")

        cx, cy = center
        half_w, half_h = width_mm / 2, height_mm / 2

        corners = [
            (-half_w, -half_h),
            (half_w, -half_h),
            (half_w, half_h),
            (-half_w, half_h),
        ]

        if rotation_rad != 0:
            cos_r = math.cos(rotation_rad)
            sin_r = math.sin(rotation_rad)
            rotated = []
            for x, y in corners:
                rx = x * cos_r - y * sin_r
                ry = x * sin_r + y * cos_r
                rotated.append((rx, ry))
            corners = rotated

        boundary = tuple((cx + x, cy + y) for x, y in corners)

        return cls(
            outer_boundary=boundary,
            inner_boundaries=(),
            local_origin=center,
            local_rotation_rad=rotation_rad,
        )

    @classmethod
    def from_arch(
        cls,
        width_mm: float,
        height_mm: float,
        arch_radius_mm: float,
        center: Point2D | None = None,
        arc_segments: int = 40,
    ) -> Domain:
        if width_mm <= 0:
            raise ValueError(f"Width must be positive, got {width_mm}")
        if height_mm <= 0:
            raise ValueError(f"Height must be positive, got {height_mm}")
        if arch_radius_mm <= 0:
            raise ValueError(f"Arch radius must be positive, got {arch_radius_mm}")
        if arch_radius_mm > width_mm / 2:
            raise ValueError(f"Arch radius ({arch_radius_mm}) cannot exceed half width ({width_mm / 2})")
        if arch_radius_mm > height_mm:
            raise ValueError(f"Arch radius ({arch_radius_mm}) cannot exceed height ({height_mm})")
        if arc_segments < 4:
            raise ValueError(f"arc_segments must be >= 4, got {arc_segments}")

        points: list[Point2D] = []

        points.append((0.0, 0.0))
        points.append((width_mm, 0.0))

        arch_start_y = height_mm - arch_radius_mm
        points.append((width_mm, arch_start_y))

        arch_center_x = width_mm / 2
        arch_center_y = arch_start_y

        for i in range(arc_segments + 1):
            angle = math.pi * i / arc_segments
            x = arch_center_x + arch_radius_mm * math.cos(angle)
            y = arch_center_y + arch_radius_mm * math.sin(angle)
            points.append((x, y))

        points.append((0.0, arch_start_y))

        if center is not None:
            cx, cy = center

            offset_x = cx - width_mm / 2
            offset_y = cy - height_mm / 2
            points = [(x + offset_x, y + offset_y) for x, y in points]
            local_origin = center
        else:
            local_origin = (width_mm / 2, height_mm / 2)

        return cls(
            outer_boundary=tuple(points),
            inner_boundaries=(),
            local_origin=local_origin,
            local_rotation_rad=0.0,
        )

    @classmethod
    def from_polygon(
        cls,
        vertices: list[Point2D] | tuple[Point2D, ...],
        holes: list[list[Point2D]] | None = None,
        local_origin: Point2D | None = None,
        local_rotation_rad: float = 0.0,
    ) -> Domain:
        outer = _normalize_boundary(vertices)
        inners = tuple(_normalize_boundary(h) for h in (holes or []))

        return cls(
            outer_boundary=outer,
            inner_boundaries=inners,
            local_origin=local_origin,
            local_rotation_rad=local_rotation_rad,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "outer_boundary": [[x, y] for x, y in self.outer_boundary],
            "inner_boundaries": [[[x, y] for x, y in inner] for inner in self.inner_boundaries],
            "local_origin": list(self.local_origin) if self.local_origin else None,
            "local_rotation_rad": self.local_rotation_rad,
            "computed": {
                "bounds": {
                    "x_min": self.bounds.x_min,
                    "x_max": self.bounds.x_max,
                    "y_min": self.bounds.y_min,
                    "y_max": self.bounds.y_max,
                },
                "area_mm2": self.area_mm2,
                "centroid": list(self.centroid),
            },
        }

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps({"domain": self.to_dict()}, indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Domain:

        if "domain" in data and isinstance(data["domain"], dict):
            data = data["domain"]

        outer = _normalize_boundary(data["outer_boundary"])
        inners = tuple(_normalize_boundary(inner) for inner in data.get("inner_boundaries", []))

        local_origin = None
        if data.get("local_origin"):
            lo = data["local_origin"]
            local_origin = (float(lo[0]), float(lo[1]))

        return cls(
            outer_boundary=outer,
            inner_boundaries=inners,
            local_origin=local_origin,
            local_rotation_rad=float(data.get("local_rotation_rad", 0.0)),
        )

    @classmethod
    def from_json(cls, json_str: str) -> Domain:
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass(frozen=True)
class MultiDomain:
    domains: tuple[Domain, ...] = field(default_factory=tuple)

    @property
    def is_empty(self) -> bool:
        return len(self.domains) == 0

    def __iter__(self) -> Iterator[Domain]:
        return iter(self.domains)

    def __len__(self) -> int:
        return len(self.domains)

    def __getitem__(self, index: int) -> Domain:
        return self.domains[index]

    def to_dict(self) -> dict[str, Any]:
        return {
            "domains": [d.to_dict() for d in self.domains],
            "count": len(self.domains),
        }

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps({"multi_domain": self.to_dict()}, indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MultiDomain:

        if "multi_domain" in data and isinstance(data["multi_domain"], dict):
            data = data["multi_domain"]

        domains = tuple(Domain.from_dict(d) for d in data.get("domains", []))
        return cls(domains=domains)

    @classmethod
    def from_json(cls, json_str: str) -> MultiDomain:
        data = json.loads(json_str)
        return cls.from_dict(data)
