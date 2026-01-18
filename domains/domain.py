"""Domain and MultiDomain dataclasses for bounded 2D regions.

A Domain is a bounded 2D region represented as a simple polygon with optional holes.
Domains support algebraic operations (inset, offset, subtract, intersect) that derive
new regions from existing ones.

This module is part of the domain/generator system that separates *what* to machine
from *how* to express it.

Usage:
    from domains import Domain, MultiDomain

    # Create a rectangular domain
    domain = Domain.from_rectangle(width_mm=100, height_mm=50, center=(200, 150))

    # Apply operations
    inset_result = domain.inset(10)  # Returns MultiDomain
    for d in inset_result:
        # Process each resulting domain
        pass
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any, Iterator, Literal

from shapely.geometry import Polygon, MultiPolygon, GeometryCollection
from shapely.ops import orient
from shapely.validation import make_valid

# Type alias for points
Point2D = tuple[float, float]
Boundary = tuple[Point2D, ...]

# Join style type for buffer operations
JoinStyle = Literal["mitre", "round", "bevel"]


def _normalize_boundary(coords: list[list[float]] | tuple[tuple[float, ...], ...]) -> tuple[Point2D, ...]:
    """Convert various boundary formats to tuple of (x, y) tuples."""
    result = []
    for point in coords:
        if len(point) < 2:
            raise ValueError(f"Point must have at least 2 coordinates, got {len(point)}")
        result.append((float(point[0]), float(point[1])))
    return tuple(result)


def _shapely_join_style(style: JoinStyle) -> int:
    """Convert join style string to Shapely constant."""
    from shapely import BufferJoinStyle
    mapping = {
        "mitre": BufferJoinStyle.mitre,
        "round": BufferJoinStyle.round,
        "bevel": BufferJoinStyle.bevel,
    }
    if style not in mapping:
        raise ValueError(f"Invalid join_style '{style}'. Must be one of: mitre, round, bevel")
    return mapping[style]


@dataclass(frozen=True)
class Bounds2D:
    """Axis-aligned bounding box."""
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
    """A bounded 2D region represented as a polygon with optional holes.

    Domains are purely geometric - they define *where* operations may occur,
    not what machining operations to perform.

    Attributes:
        outer_boundary: Ordered list of 2D points defining the outer edge (CCW winding)
        inner_boundaries: List of ordered point lists defining holes (CW winding)
        local_origin: Point in sheet space that maps to (0,0) in domain-local space
        local_rotation_rad: Angle (radians) of the domain's local X-axis relative to sheet X-axis

    All boundaries are automatically normalized to correct winding on construction:
        - Outer boundaries: Counter-clockwise (CCW)
        - Inner boundaries (holes): Clockwise (CW)
    """

    outer_boundary: Boundary
    inner_boundaries: tuple[Boundary, ...] = field(default_factory=tuple)
    local_origin: Point2D | None = None
    local_rotation_rad: float = 0.0

    # Cached Shapely polygon - not part of the frozen state
    _polygon: Polygon | None = field(default=None, repr=False, compare=False, hash=False)

    def __post_init__(self) -> None:
        # Validate outer boundary
        if len(self.outer_boundary) < 3:
            raise ValueError(
                f"Outer boundary must have at least 3 points, got {len(self.outer_boundary)}"
            )

        # Validate inner boundaries
        for i, inner in enumerate(self.inner_boundaries):
            if len(inner) < 3:
                raise ValueError(
                    f"Inner boundary {i} must have at least 3 points, got {len(inner)}"
                )

        # Build and validate the Shapely polygon
        poly = self._build_polygon()

        if not poly.is_valid:
            # Try to fix invalid geometry
            poly = make_valid(poly)
            if not poly.is_valid:
                raise ValueError(f"Domain geometry is invalid: {poly.is_valid}")
            if not isinstance(poly, Polygon):
                raise ValueError(
                    "Domain geometry becomes invalid after normalization (splits into multiple regions)"
                )

        # Normalize winding order using Shapely's orient function
        # orient() returns CCW outer, CW holes (OGC standard)
        poly = orient(poly, sign=1.0)

        # Extract normalized coordinates
        outer_coords = tuple((float(x), float(y)) for x, y in poly.exterior.coords[:-1])
        inner_coords = tuple(
            tuple((float(x), float(y)) for x, y in interior.coords[:-1])
            for interior in poly.interiors
        )

        # Update frozen dataclass fields using object.__setattr__
        object.__setattr__(self, 'outer_boundary', outer_coords)
        object.__setattr__(self, 'inner_boundaries', inner_coords)
        object.__setattr__(self, '_polygon', poly)

        # Validate containment - inner boundaries must be inside outer
        outer_ring = Polygon(self.outer_boundary)
        for i, inner in enumerate(self.inner_boundaries):
            inner_poly = Polygon(inner)
            if not outer_ring.contains(inner_poly):
                raise ValueError(
                    f"Inner boundary {i} is not fully contained within outer boundary"
                )

        # Check for overlapping inner boundaries
        for i in range(len(self.inner_boundaries)):
            for j in range(i + 1, len(self.inner_boundaries)):
                inner_i = Polygon(self.inner_boundaries[i])
                inner_j = Polygon(self.inner_boundaries[j])
                if inner_i.intersects(inner_j) and not inner_i.touches(inner_j):
                    raise ValueError(
                        f"Inner boundaries {i} and {j} overlap"
                    )

        # Set default local origin to centroid if not provided
        if self.local_origin is None:
            centroid = self._centroid
            object.__setattr__(self, 'local_origin', centroid)

    def _build_polygon(self) -> Polygon:
        """Build a Shapely Polygon from boundaries."""
        if self.inner_boundaries:
            return Polygon(self.outer_boundary, self.inner_boundaries)
        return Polygon(self.outer_boundary)

    @property
    def polygon(self) -> Polygon:
        """Get the Shapely Polygon representation."""
        if self._polygon is None:
            object.__setattr__(self, '_polygon', self._build_polygon())
        return self._polygon

    @property
    def _centroid(self) -> Point2D:
        """Compute the centroid of the domain."""
        c = self.polygon.centroid
        return (float(c.x), float(c.y))

    @property
    def bounds(self) -> Bounds2D:
        """Get the axis-aligned bounding box."""
        minx, miny, maxx, maxy = self.polygon.bounds
        return Bounds2D(
            x_min=float(minx),
            x_max=float(maxx),
            y_min=float(miny),
            y_max=float(maxy),
        )

    @property
    def area_mm2(self) -> float:
        """Get the area in square millimeters."""
        return float(self.polygon.area)

    @property
    def centroid(self) -> Point2D:
        """Get the centroid of the domain."""
        return self._centroid

    def with_origin_at_centroid(self) -> Domain:
        """Return a new Domain with local_origin at the domain's centroid."""
        return Domain(
            outer_boundary=self.outer_boundary,
            inner_boundaries=self.inner_boundaries,
            local_origin=self.centroid,
            local_rotation_rad=self.local_rotation_rad,
        )

    # =========================================================================
    # Algebraic Operations
    # =========================================================================

    def inset(
        self,
        distance: float,
        join_style: JoinStyle = "mitre",
        mitre_limit: float = 5.0,
    ) -> MultiDomain:
        """Contract the outer boundary inward by the specified distance.

        Inner boundaries (holes) are expanded outward by the same distance,
        making holes larger.

        Args:
            distance: Inset distance in mm (positive value)
            join_style: Corner join style - "mitre" (sharp), "round", or "bevel"
            mitre_limit: Limit for mitre joins on acute angles

        Returns:
            MultiDomain containing the resulting domain(s). May be empty if
            inset distance exceeds half the minimum dimension.
        """
        if distance < 0:
            raise ValueError(f"Inset distance must be non-negative, got {distance}")
        if distance == 0:
            return MultiDomain(domains=(self,))

        # buffer(-distance) contracts the polygon
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
        """Expand the outer boundary outward by the specified distance.

        Inner boundaries (holes) are contracted inward. If a hole contracts
        to nothing, it is removed from the result.

        Args:
            distance: Offset distance in mm (positive value)
            join_style: Corner join style - "mitre" (sharp), "round", or "bevel"
            mitre_limit: Limit for mitre joins on acute angles

        Returns:
            MultiDomain containing the resulting domain(s).
        """
        if distance < 0:
            raise ValueError(f"Offset distance must be non-negative, got {distance}")
        if distance == 0:
            return MultiDomain(domains=(self,))

        # buffer(distance) expands the polygon
        result = self.polygon.buffer(
            distance,
            join_style=_shapely_join_style(join_style),
            mitre_limit=mitre_limit,
        )

        return self._geometry_to_multidomain(result)

    def subtract(self, other: Domain) -> MultiDomain:
        """Remove the region covered by another domain from this domain.

        The subtracted region may create holes or split the domain into
        disjoint pieces.

        Args:
            other: The domain to subtract

        Returns:
            MultiDomain containing the resulting domain(s). May be empty if
            the other domain fully contains this domain.
        """
        result = self.polygon.difference(other.polygon)
        return self._geometry_to_multidomain(result)

    def intersect(self, other: Domain) -> MultiDomain:
        """Keep only the region where this domain and another domain overlap.

        Args:
            other: The domain to intersect with

        Returns:
            MultiDomain containing the overlapping region(s). May be empty if
            domains do not overlap.
        """
        result = self.polygon.intersection(other.polygon)
        return self._geometry_to_multidomain(result)

    # =========================================================================
    # Split Operations (Stage 9)
    # =========================================================================
    #
    # NOTE: Split operations use sheet-space (axis-aligned) coordinates.
    # For domains with local_rotation != 0, splits are still aligned to the
    # sheet X/Y axes, not the domain's local axes. This matches the common
    # case where cabinet doors are axis-aligned on the sheet.
    #
    # Future enhancement: Add local_coords parameter to split in domain-local
    # space for rotated panels (see Stage 10+ in domain_generator_design.md).
    # =========================================================================

    def split_horizontal(
        self,
        n: int,
        gap_mm: float = 0.0,
    ) -> MultiDomain:
        """Divide domain into n stacked rows (horizontal splits).

        Creates n equal-height domains stacked vertically, with optional
        gaps between them. Domains are ordered from bottom to top.

        Note: Splits are performed in sheet-space coordinates. For rotated
        domains, splits are still axis-aligned to sheet X/Y, not to the
        domain's local axes.

        Args:
            n: Number of rows to create (must be >= 1)
            gap_mm: Gap between rows in mm (for rails/dividers)

        Returns:
            MultiDomain containing n domains ordered bottom to top

        Raises:
            ValueError: If n < 1 or gaps don't fit within domain height

        Example:
            >>> domain = Domain.from_rectangle(200, 600, center=(100, 300))
            >>> panels = domain.split_horizontal(3, gap_mm=20)
            >>> len(panels)
            3
            >>> # Each panel is 200mm wide, (600 - 2*20) / 3 = 186.67mm tall
        """
        if n < 1:
            raise ValueError(f"split_horizontal: n must be >= 1, got {n}")
        if gap_mm < 0:
            raise ValueError(f"split_horizontal: gap_mm must be non-negative, got {gap_mm}")

        bounds = self.bounds
        total_gap = gap_mm * (n - 1)

        if total_gap >= bounds.height:
            raise ValueError(
                f"split_horizontal: total gap {total_gap}mm exceeds domain height {bounds.height}mm"
            )

        # Calculate cell height
        available_height = bounds.height - total_gap
        cell_height = available_height / n

        domains = []
        for i in range(n):
            # Calculate y position (bottom to top)
            y_min = bounds.y_min + i * (cell_height + gap_mm)
            y_max = y_min + cell_height
            cell_center = (
                (bounds.x_min + bounds.x_max) / 2,
                (y_min + y_max) / 2,
            )

            # Create rectangular cell and intersect with domain
            cell = Domain.from_rectangle(
                width_mm=bounds.width,
                height_mm=cell_height,
                center=cell_center,
            )
            intersection = self.intersect(cell)

            # Add all resulting domains (may be multiple if domain has holes)
            for d in intersection:
                # Preserve parent's origin/rotation
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
    ) -> MultiDomain:
        """Divide domain into n side-by-side columns (vertical splits).

        Creates n equal-width domains arranged horizontally, with optional
        gaps between them. Domains are ordered from left to right.

        Args:
            n: Number of columns to create (must be >= 1)
            gap_mm: Gap between columns in mm (for rails/dividers)

        Returns:
            MultiDomain containing n domains ordered left to right

        Raises:
            ValueError: If n < 1 or gaps don't fit within domain width

        Example:
            >>> domain = Domain.from_rectangle(400, 300, center=(200, 150))
            >>> panels = domain.split_vertical(2, gap_mm=20)
            >>> len(panels)
            2
            >>> # Each panel is (400 - 20) / 2 = 190mm wide, 300mm tall
        """
        if n < 1:
            raise ValueError(f"split_vertical: n must be >= 1, got {n}")
        if gap_mm < 0:
            raise ValueError(f"split_vertical: gap_mm must be non-negative, got {gap_mm}")

        bounds = self.bounds
        total_gap = gap_mm * (n - 1)

        if total_gap >= bounds.width:
            raise ValueError(
                f"split_vertical: total gap {total_gap}mm exceeds domain width {bounds.width}mm"
            )

        # Calculate cell width
        available_width = bounds.width - total_gap
        cell_width = available_width / n

        domains = []
        for i in range(n):
            # Calculate x position (left to right)
            x_min = bounds.x_min + i * (cell_width + gap_mm)
            x_max = x_min + cell_width
            cell_center = (
                (x_min + x_max) / 2,
                (bounds.y_min + bounds.y_max) / 2,
            )

            # Create rectangular cell and intersect with domain
            cell = Domain.from_rectangle(
                width_mm=cell_width,
                height_mm=bounds.height,
                center=cell_center,
            )
            intersection = self.intersect(cell)

            # Add all resulting domains
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
    ) -> MultiDomain:
        """Divide domain into a rows × cols grid.

        Creates a grid of equal-sized domains with optional gaps between
        them. Domains are ordered left-to-right, bottom-to-top (row-major
        from bottom).

        Args:
            rows: Number of rows (must be >= 1)
            cols: Number of columns (must be >= 1)
            gap_mm: Gap between cells in mm (for rails/dividers)

        Returns:
            MultiDomain containing rows * cols domains ordered left-to-right,
            bottom-to-top

        Raises:
            ValueError: If rows/cols < 1 or gaps don't fit within domain

        Example:
            >>> domain = Domain.from_rectangle(400, 600, center=(200, 300))
            >>> panels = domain.split_grid(3, 2, gap_mm=20)
            >>> len(panels)
            6
            >>> # 3 rows, 2 cols = 6-panel door layout
        """
        if rows < 1:
            raise ValueError(f"split_grid: rows must be >= 1, got {rows}")
        if cols < 1:
            raise ValueError(f"split_grid: cols must be >= 1, got {cols}")
        if gap_mm < 0:
            raise ValueError(f"split_grid: gap_mm must be non-negative, got {gap_mm}")

        bounds = self.bounds
        total_h_gap = gap_mm * (cols - 1)
        total_v_gap = gap_mm * (rows - 1)

        if total_h_gap >= bounds.width:
            raise ValueError(
                f"split_grid: total horizontal gap {total_h_gap}mm exceeds domain width {bounds.width}mm"
            )
        if total_v_gap >= bounds.height:
            raise ValueError(
                f"split_grid: total vertical gap {total_v_gap}mm exceeds domain height {bounds.height}mm"
            )

        # Calculate cell dimensions
        cell_width = (bounds.width - total_h_gap) / cols
        cell_height = (bounds.height - total_v_gap) / rows

        domains = []

        # Iterate bottom-to-top, left-to-right
        for row in range(rows):
            for col in range(cols):
                # Calculate cell position
                x_min = bounds.x_min + col * (cell_width + gap_mm)
                y_min = bounds.y_min + row * (cell_height + gap_mm)
                cell_center = (
                    x_min + cell_width / 2,
                    y_min + cell_height / 2,
                )

                # Create rectangular cell and intersect with domain
                cell = Domain.from_rectangle(
                    width_mm=cell_width,
                    height_mm=cell_height,
                    center=cell_center,
                )
                intersection = self.intersect(cell)

                # Add all resulting domains
                for d in intersection:
                    domain_with_origin = Domain(
                        outer_boundary=d.outer_boundary,
                        inner_boundaries=d.inner_boundaries,
                        local_origin=self.local_origin,
                        local_rotation_rad=self.local_rotation_rad,
                    )
                    domains.append(domain_with_origin)

        return MultiDomain(domains=tuple(domains))

    def _geometry_to_multidomain(self, geom) -> MultiDomain:
        """Convert a Shapely geometry result to MultiDomain.

        Handles Polygon, MultiPolygon, GeometryCollection, and empty results.
        Preserves local_origin and local_rotation from this domain.
        """
        if geom.is_empty:
            return MultiDomain(domains=())

        # Collect all polygons from the result
        polygons: list[Polygon] = []
        if isinstance(geom, Polygon):
            polygons.append(geom)
        elif isinstance(geom, MultiPolygon):
            polygons.extend(geom.geoms)
        elif isinstance(geom, GeometryCollection):
            # Extract polygons from geometry collection
            for g in geom.geoms:
                if isinstance(g, Polygon):
                    polygons.append(g)
                elif isinstance(g, MultiPolygon):
                    polygons.extend(g.geoms)
            # If no polygons found, return empty
            if not polygons:
                return MultiDomain(domains=())
        else:
            # Other geometry types (Point, LineString) are ignored
            return MultiDomain(domains=())

        # Convert each polygon to a Domain
        domains = []
        for poly in polygons:
            if poly.is_empty or poly.area < 1e-10:
                continue

            # Normalize winding
            poly = orient(poly, sign=1.0)

            outer = tuple((float(x), float(y)) for x, y in poly.exterior.coords[:-1])
            inners = tuple(
                tuple((float(x), float(y)) for x, y in interior.coords[:-1])
                for interior in poly.interiors
            )

            # Create domain with inherited origin and rotation
            domain = Domain(
                outer_boundary=outer,
                inner_boundaries=inners,
                local_origin=self.local_origin,
                local_rotation_rad=self.local_rotation_rad,
            )
            domains.append(domain)

        return MultiDomain(domains=tuple(domains))

    # =========================================================================
    # Constructors
    # =========================================================================

    @classmethod
    def from_rectangle(
        cls,
        width_mm: float,
        height_mm: float,
        center: Point2D = (0.0, 0.0),
        rotation_rad: float = 0.0,
    ) -> Domain:
        """Create a rectangular domain centered at the given point.

        Args:
            width_mm: Width of the rectangle in mm
            height_mm: Height of the rectangle in mm
            center: Center point (x, y) in mm
            rotation_rad: Rotation angle in radians (counter-clockwise positive)

        Returns:
            A Domain representing the rectangle
        """
        if width_mm <= 0:
            raise ValueError(f"Width must be positive, got {width_mm}")
        if height_mm <= 0:
            raise ValueError(f"Height must be positive, got {height_mm}")

        cx, cy = center
        half_w, half_h = width_mm / 2, height_mm / 2

        # Rectangle corners before rotation (CCW from bottom-left)
        corners = [
            (-half_w, -half_h),
            (half_w, -half_h),
            (half_w, half_h),
            (-half_w, half_h),
        ]

        # Apply rotation if needed
        if rotation_rad != 0:
            cos_r = math.cos(rotation_rad)
            sin_r = math.sin(rotation_rad)
            rotated = []
            for x, y in corners:
                rx = x * cos_r - y * sin_r
                ry = x * sin_r + y * cos_r
                rotated.append((rx, ry))
            corners = rotated

        # Translate to center position
        boundary = tuple((cx + x, cy + y) for x, y in corners)

        return cls(
            outer_boundary=boundary,
            inner_boundaries=(),
            local_origin=center,
            local_rotation_rad=rotation_rad,
        )

    @classmethod
    def from_polygon(
        cls,
        vertices: list[Point2D] | tuple[Point2D, ...],
        holes: list[list[Point2D]] | None = None,
        local_origin: Point2D | None = None,
        local_rotation_rad: float = 0.0,
    ) -> Domain:
        """Create a domain from explicit polygon vertices.

        Args:
            vertices: Ordered list of 2D points for the outer boundary
            holes: Optional list of ordered point lists for inner boundaries
            local_origin: Local coordinate origin (defaults to centroid)
            local_rotation_rad: Local rotation in radians

        Returns:
            A Domain representing the polygon
        """
        outer = _normalize_boundary(vertices)
        inners = tuple(_normalize_boundary(h) for h in (holes or []))

        return cls(
            outer_boundary=outer,
            inner_boundaries=inners,
            local_origin=local_origin,
            local_rotation_rad=local_rotation_rad,
        )

    # =========================================================================
    # Serialization
    # =========================================================================

    def to_dict(self) -> dict[str, Any]:
        """Serialize the domain to a dictionary.

        Includes computed properties for inspection.
        """
        return {
            "outer_boundary": [[x, y] for x, y in self.outer_boundary],
            "inner_boundaries": [
                [[x, y] for x, y in inner]
                for inner in self.inner_boundaries
            ],
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
        """Serialize the domain to a JSON string."""
        return json.dumps({"domain": self.to_dict()}, indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Domain:
        """Deserialize a domain from a dictionary.

        Accepts either a raw domain dict or a {"domain": {...}} wrapper.
        """
        # Handle wrapper format
        if "domain" in data and isinstance(data["domain"], dict):
            data = data["domain"]

        outer = _normalize_boundary(data["outer_boundary"])
        inners = tuple(
            _normalize_boundary(inner)
            for inner in data.get("inner_boundaries", [])
        )

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
        """Deserialize a domain from a JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass(frozen=True)
class MultiDomain:
    """Zero or more disjoint domains from boolean/offset operations.

    Boolean and offset operations can produce multiple disjoint regions.
    MultiDomain represents these results uniformly, whether empty,
    single, or multiple domains.

    Usage:
        result: MultiDomain = outer_domain.subtract(center_cutout)

        # Iterate over resulting domains
        for domain in result:
            items.extend(generator(domain, params))

        # Or check for empty result
        if result.is_empty:
            raise ValueError("Operation produced empty result")
    """

    domains: tuple[Domain, ...] = field(default_factory=tuple)

    @property
    def is_empty(self) -> bool:
        """True if no domains in the result."""
        return len(self.domains) == 0

    def __iter__(self) -> Iterator[Domain]:
        """Iterate over the domains."""
        return iter(self.domains)

    def __len__(self) -> int:
        """Number of domains in the result."""
        return len(self.domains)

    def __getitem__(self, index: int) -> Domain:
        """Get domain by index."""
        return self.domains[index]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary."""
        return {
            "domains": [d.to_dict() for d in self.domains],
            "count": len(self.domains),
        }

    def to_json(self, indent: int | None = 2) -> str:
        """Serialize to a JSON string."""
        return json.dumps({"multi_domain": self.to_dict()}, indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MultiDomain:
        """Deserialize from a dictionary."""
        # Handle wrapper format
        if "multi_domain" in data and isinstance(data["multi_domain"], dict):
            data = data["multi_domain"]

        domains = tuple(Domain.from_dict(d) for d in data.get("domains", []))
        return cls(domains=domains)

    @classmethod
    def from_json(cls, json_str: str) -> MultiDomain:
        """Deserialize from a JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)
