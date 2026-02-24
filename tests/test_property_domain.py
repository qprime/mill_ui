from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from domains.domain import Domain, MultiDomain


@st.composite
def rectangular_domain(draw: st.DrawFn) -> Domain:
    width = draw(st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False))
    height = draw(st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False))
    cx = draw(st.floats(min_value=-500.0, max_value=500.0, allow_nan=False, allow_infinity=False))
    cy = draw(st.floats(min_value=-500.0, max_value=500.0, allow_nan=False, allow_infinity=False))
    return Domain.from_rectangle(width, height, center=(cx, cy))


@given(
    domain=rectangular_domain(), offset=st.floats(min_value=0.1, max_value=50.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=50)
def test_offset_contains_original_centroid(domain: Domain, offset: float) -> None:
    from shapely.geometry import Point

    expanded = domain.offset(offset)
    if expanded.is_empty:
        return
    cx, cy = domain.centroid
    centroid_point = Point(cx, cy)
    combined_poly = expanded.domains[0].polygon
    for d in expanded.domains[1:]:
        combined_poly = combined_poly.union(d.polygon)
    assert combined_poly.contains(centroid_point), f"Offset domain does not contain original centroid {domain.centroid}"


@given(domain=rectangular_domain())
@settings(max_examples=50)
def test_intersect_self_equals_self_area(domain: Domain) -> None:
    result: MultiDomain = domain.intersect(domain)
    total_area = sum(d.area_mm2 for d in result.domains)
    assert abs(total_area - domain.area_mm2) < 1e-6, (
        f"intersect(self) area {total_area} != original area {domain.area_mm2}"
    )


@given(
    domain=rectangular_domain(), offset=st.floats(min_value=0.1, max_value=50.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=50)
def test_offset_increases_area(domain: Domain, offset: float) -> None:
    expanded = domain.offset(offset)
    if expanded.is_empty:
        return
    expanded_area = sum(d.area_mm2 for d in expanded.domains)
    assert expanded_area >= domain.area_mm2 - 1e-6, f"Offset area {expanded_area} < original area {domain.area_mm2}"
