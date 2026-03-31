from __future__ import annotations

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from shapely.geometry.base import BaseGeometry

from domains.domain import Domain, MultiDomain

_finite_float = st.floats(allow_nan=False, allow_infinity=False)


@st.composite
def rectangular_domain(draw: st.DrawFn) -> Domain:
    width = draw(st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False))
    height = draw(st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False))
    cx = draw(st.floats(min_value=-500.0, max_value=500.0, allow_nan=False, allow_infinity=False))
    cy = draw(st.floats(min_value=-500.0, max_value=500.0, allow_nan=False, allow_infinity=False))
    return Domain.from_rectangle(width, height, center=(cx, cy))


@st.composite
def overlapping_domains(draw: st.DrawFn) -> tuple[Domain, Domain]:
    cx = draw(st.floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    cy = draw(st.floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    w1 = draw(st.floats(min_value=10.0, max_value=200.0, allow_nan=False, allow_infinity=False))
    h1 = draw(st.floats(min_value=10.0, max_value=200.0, allow_nan=False, allow_infinity=False))
    dx = draw(st.floats(min_value=-w1 / 2 + 1.0, max_value=w1 / 2 - 1.0, allow_nan=False, allow_infinity=False))
    dy = draw(st.floats(min_value=-h1 / 2 + 1.0, max_value=h1 / 2 - 1.0, allow_nan=False, allow_infinity=False))
    w2 = draw(st.floats(min_value=10.0, max_value=200.0, allow_nan=False, allow_infinity=False))
    h2 = draw(st.floats(min_value=10.0, max_value=200.0, allow_nan=False, allow_infinity=False))
    a = Domain.from_rectangle(w1, h1, center=(cx, cy))
    b = Domain.from_rectangle(w2, h2, center=(cx + dx, cy + dy))
    return a, b


@st.composite
def domain_with_safe_inset(draw: st.DrawFn) -> tuple[Domain, float]:
    width = draw(st.floats(min_value=10.0, max_value=500.0, allow_nan=False, allow_infinity=False))
    height = draw(st.floats(min_value=10.0, max_value=500.0, allow_nan=False, allow_infinity=False))
    max_inset = min(width, height) / 2 - 0.1
    inset = draw(st.floats(min_value=0.1, max_value=max(0.1, max_inset), allow_nan=False, allow_infinity=False))
    d = Domain.from_rectangle(width, height)
    return d, inset


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
    combined_poly: BaseGeometry = expanded.domains[0].polygon
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


@given(pair=overlapping_domains())
@settings(max_examples=50)
def test_intersect_commutativity(pair: tuple[Domain, Domain]) -> None:
    a, b = pair
    ab = a.intersect(b)
    ba = b.intersect(a)
    area_ab = sum(d.area_mm2 for d in ab.domains)
    area_ba = sum(d.area_mm2 for d in ba.domains)
    assert abs(area_ab - area_ba) < 1e-6, f"intersect not commutative: {area_ab} != {area_ba}"


@given(pair=overlapping_domains())
@settings(max_examples=50)
def test_subtract_intersect_conservation(pair: tuple[Domain, Domain]) -> None:
    a, b = pair
    sub = a.subtract(b)
    inter = a.intersect(b)
    sub_area = sum(d.area_mm2 for d in sub.domains)
    inter_area = sum(d.area_mm2 for d in inter.domains)
    assert abs(sub_area + inter_area - a.area_mm2) < 1e-3, (
        f"conservation violated: subtract({sub_area}) + intersect({inter_area}) = "
        f"{sub_area + inter_area} != {a.area_mm2}"
    )


@given(pair=overlapping_domains())
@settings(max_examples=50)
def test_subtract_produces_subset(pair: tuple[Domain, Domain]) -> None:
    a, b = pair
    sub = a.subtract(b)
    sub_area = sum(d.area_mm2 for d in sub.domains)
    assert sub_area <= a.area_mm2 + 1e-6, f"subtract area {sub_area} > original area {a.area_mm2}"


@given(data=domain_with_safe_inset())
@settings(max_examples=50)
def test_inset_monotonicity(data: tuple[Domain, float]) -> None:
    domain, d2 = data
    d1 = d2 / 2
    r1 = domain.inset(d1)
    r2 = domain.inset(d2)
    area1 = sum(d.area_mm2 for d in r1.domains)
    area2 = sum(d.area_mm2 for d in r2.domains)
    assert area1 >= area2 - 1e-6, f"inset({d1}) area {area1} < inset({d2}) area {area2}"


@given(data=domain_with_safe_inset())
@settings(max_examples=50)
def test_offset_inset_roundtrip(data: tuple[Domain, float]) -> None:
    domain, d = data
    d_small = min(d, 5.0)
    expanded = domain.offset(d_small)
    if expanded.is_empty:
        return
    contracted = expanded.domains[0].inset(d_small)
    if contracted.is_empty:
        return
    roundtrip_area = sum(dom.area_mm2 for dom in contracted.domains)
    assert abs(roundtrip_area - domain.area_mm2) < 1e-3 + domain.area_mm2 * 0.01, (
        f"roundtrip area {roundtrip_area} != original area {domain.area_mm2}"
    )


@pytest.mark.parametrize("bad_value", [math.nan, math.inf, -math.inf])
def test_inset_rejects_non_finite_distance(bad_value: float) -> None:
    d = Domain.from_rectangle(100.0, 100.0)
    with pytest.raises(ValueError, match="finite"):
        d.inset(bad_value)


@pytest.mark.parametrize("bad_value", [math.nan, math.inf, -math.inf])
def test_offset_rejects_non_finite_distance(bad_value: float) -> None:
    d = Domain.from_rectangle(100.0, 100.0)
    with pytest.raises(ValueError, match="finite"):
        d.offset(bad_value)


@pytest.mark.parametrize("bad_limit", [0.0, -1.0, math.nan, math.inf])
def test_inset_rejects_bad_mitre_limit(bad_limit: float) -> None:
    d = Domain.from_rectangle(100.0, 100.0)
    with pytest.raises(ValueError, match="mitre_limit"):
        d.inset(5.0, mitre_limit=bad_limit)


@pytest.mark.parametrize("bad_limit", [0.0, -1.0, math.nan, math.inf])
def test_offset_rejects_bad_mitre_limit(bad_limit: float) -> None:
    d = Domain.from_rectangle(100.0, 100.0)
    with pytest.raises(ValueError, match="mitre_limit"):
        d.offset(5.0, mitre_limit=bad_limit)
