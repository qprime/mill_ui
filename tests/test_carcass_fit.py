from __future__ import annotations

from itertools import combinations, pairwise

import pytest

from assembly.joinery import Captured, Finger
from assembly.primitives import carcass
from tests.test_cubby_fit import _Placement, _SectionPanel

_SOURCE = """Sheet: {width: 1220mm, height: 1220mm, thickness: 18mm, margin: 10mm}
children:
- Assembly:
    type: carcass
    width: 600mm
    depth: 560mm
    height: 720mm
    thickness: 18mm
    cap_style: between_sides
    top: {joinery: captured, dado_depth: 9mm}
    bottom: {joinery: captured, dado_depth: 9mm}
    back: {joinery: captured, dado_depth: 9mm}
    back_thickness: 18mm
    back_inset: 12mm
    fixed_shelves: 1
    shelf_joinery: {joinery: captured, dado_depth: 9mm}
    toe_kick_height: 100mm
    toe_kick_depth: 75mm
    toe_kick_cover: false
"""


def _cabinet(**changes):
    params = dict(
        width=600,
        length=560,
        height=720,
        thickness=18,
        top=Captured(dado_depth_mm=9, fitment_mm=0.12),
        bottom=Captured(dado_depth_mm=9, fitment_mm=0.12),
        back=Captured(dado_depth_mm=9, fitment_mm=0.12),
        back_thickness=18,
        back_inset=12,
        fixed_shelves=1,
        shelf_joinery=Captured(dado_depth_mm=9, fitment_mm=0.12),
        toe_kick_height=100,
        toe_kick_setback=75,
        toe_kick_cover=False,
    )
    return carcass(**{**params, **changes})


def test_back_spans_the_actual_side_and_raised_bottom_grooves():
    back = _cabinet().panels["back"]
    assert (back.width_mm, back.height_mm) == (582, 602)


def test_back_thickness_is_stock_and_not_just_a_groove_width():
    assembly = _cabinet(back_thickness=6)
    assert assembly.panels["back"].thickness_mm == 6
    assert all(i.joinery.dado_width_mm == 6 for i in assembly.interfaces if i.panel_b == "back")


def test_shelf_stops_at_the_back_front_face_unless_support_is_requested():
    assert _cabinet().panels["shelf_1"].height_mm == 530
    assert _cabinet(shelf_back_support=True).panels["shelf_1"].height_mm == 539


def test_rear_setback_changes_depth_and_never_the_back_width_or_height():
    a, b = _cabinet(back_inset=12), _cabinet(back_inset=24)
    assert a.panels["back"] == b.panels["back"]
    assert a.panels["shelf_1"].height_mm - b.panels["shelf_1"].height_mm == 12


def test_back_grooves_use_the_rear_of_each_inside_machining_face():
    edges = {i.panel_a: (i.edge_a, i.position_along_edge_a_mm) for i in _cabinet().interfaces if i.panel_b == "back"}
    assert edges == {
        "left_side": ("right", 12),
        "right_side": ("left", 12),
        "top": ("bottom", 12),
        "bottom": ("top", 12),
    }


def test_toe_kicks_mirror_on_the_two_inside_faces():
    panels = _cabinet().panels
    assert panels["left_side"].notches[0].u_start_mm == 0
    assert panels["right_side"].notches[0].u_start_mm == 485


def test_back_support_uses_the_back_origin_rather_than_the_rear_setback():
    support = next(i for i in _cabinet(shelf_back_support=True).interfaces if i.panel_a == "back")
    assert support.position_along_edge_a_mm == 292


@pytest.mark.parametrize("setback", [-1, 550])
def test_impossible_back_planes_are_rejected(setback):
    with pytest.raises(ValueError, match=r"[Bb]ack"):
        _cabinet(back_inset=setback)


def test_groove_contact_spans_keep_the_toe_and_stop_shelves_at_the_back():
    interfaces = _cabinet().interfaces
    bottom = {i.panel_a: i.contact_span_mm for i in interfaces if i.panel_b == "bottom"}
    shelves = {i.panel_a: i.contact_span_mm for i in interfaces if i.panel_b == "shelf_1"}
    assert bottom == {"left_side": (75, 560), "right_side": (0, 485)}
    assert shelves == {"left_side": (0, 530), "right_side": (30, 560)}


@pytest.mark.parametrize("support", [False, True])
def test_actual_panel_material_fits_through_all_depth_intervals(support):
    placements = {
        "left_side": _Placement("vertical", (0, 0, 0)),
        "right_side": _Placement("vertical", (582, 560, 0), True, -1),
        "top": _Placement("horizontal", (9, 560, 702), True, -1),
        "bottom": _Placement("horizontal", (9, 75, 100)),
        "back": _Placement("back", (9, 530, 109)),
        "shelf_1": _Placement("horizontal", (9, 0, 401)),
    }
    parts = {
        p.name: _SectionPanel.from_spec(p, placements[p.name]) for p in _cabinet(shelf_back_support=support).resolve()
    }
    breaks = {0.0, 560.0}
    for part in parts.values():
        breaks.update(d for d in part.depth_breaks() if 0 <= d <= 560)
    for lo, hi in pairwise(sorted(breaks)):
        depth = (lo + hi) / 2
        sections = {name: p.section(depth) for name, p in parts.items()}
        for a, b in combinations(sections, 2):
            assert sections[a].intersection(sections[b]).area < 1e-6, (depth, a, b)


def test_pml_contact_span_survives_resolution_into_the_pocket_intent():
    from adapters.ast_to_removal import ast_to_removal_intents
    from pml.yaml_parser import parse_pml_yaml
    from resolution.layout_resolver import resolve_layout_multi

    intents = [i for ast in resolve_layout_multi(parse_pml_yaml(_SOURCE)) for i in ast_to_removal_intents(ast)]
    left = next(i for i in intents if i.hint_type == "profile" and "assembly_left_side_" in i.region_id)
    grooves = [i for i in intents if i.hint_type == "pocket" and "assembly_left_side_" in i.region_id]
    bottom = next(i for i in grooves if i.bounds.y_min - left.bounds.y_min == 100)
    assert bottom.bounds.width == 485
    assert bottom.bounds.x_min - left.bounds.x_min == 75
    back = next(i for i in intents if i.hint_type == "profile" and "assembly_back_" in i.region_id)
    assert (back.bounds.width, back.bounds.height) == (582, 602)


def test_thin_back_cannot_silently_be_cut_from_thicker_sheet_stock():
    from pml.yaml_parser import parse_pml_yaml
    from resolution.layout_resolver import resolve_layout_multi

    with pytest.raises(ValueError, match=r"panel 'back' thickness .* does not match sheet thickness"):
        resolve_layout_multi(parse_pml_yaml(_SOURCE.replace("back_thickness: 18mm", "back_thickness: 6mm")))


def test_back_joint_keeps_an_explicitly_disabled_dogbone():
    assembly = _cabinet(back=Captured(dado_depth_mm=9, dogbone=None))
    assert all(i.joinery.dogbone is None for i in assembly.interfaces if i.panel_b == "back")


def test_back_support_depth_cannot_exceed_the_back_stock():
    with pytest.raises(ValueError, match="support groove depth must fit the back stock"):
        _cabinet(back_thickness=6, shelf_back_support=True)


def test_shortened_toe_bottom_cannot_inherit_full_length_finger_interfaces():
    with pytest.raises(ValueError, match="toe-kick bottom requires"):
        _cabinet(bottom=Finger())
