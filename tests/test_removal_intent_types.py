from __future__ import annotations

import dataclasses

import pytest

from ir.removal_intent import (
    BevelSpec,
    Bounds2D,
    ChamferSpec,
    DepthProfile,
    RemovalIntent,
    ShapeGeometry,
)


class TestBevelSpec:
    def test_basic_construction(self):
        bevel = BevelSpec(width_mm=10.0, angle_deg=45.0, inner_depth_mm=8.0)
        assert bevel.width_mm == 10.0
        assert bevel.angle_deg == 45.0
        assert bevel.inner_depth_mm == 8.0

    def test_frozen(self):
        bevel = BevelSpec(width_mm=10.0, angle_deg=45.0, inner_depth_mm=8.0)
        with pytest.raises(dataclasses.FrozenInstanceError):
            bevel.width_mm = 20.0  # type: ignore[misc]

    def test_replace(self):
        bevel = BevelSpec(width_mm=10.0, angle_deg=45.0, inner_depth_mm=8.0)
        modified = dataclasses.replace(bevel, angle_deg=60.0)
        assert modified.angle_deg == 60.0
        assert modified.width_mm == 10.0

    def test_equality(self):
        a = BevelSpec(width_mm=5.0, angle_deg=30.0, inner_depth_mm=4.0)
        b = BevelSpec(width_mm=5.0, angle_deg=30.0, inner_depth_mm=4.0)
        assert a == b

    def test_inequality(self):
        a = BevelSpec(width_mm=5.0, angle_deg=30.0, inner_depth_mm=4.0)
        b = BevelSpec(width_mm=5.0, angle_deg=45.0, inner_depth_mm=4.0)
        assert a != b


class TestChamferSpec:
    def test_basic_construction(self):
        chamfer = ChamferSpec(width_mm=3.0, angle_deg=45.0)
        assert chamfer.width_mm == 3.0
        assert chamfer.angle_deg == 45.0

    def test_frozen(self):
        chamfer = ChamferSpec(width_mm=3.0, angle_deg=45.0)
        with pytest.raises(dataclasses.FrozenInstanceError):
            chamfer.width_mm = 5.0  # type: ignore[misc]

    def test_replace(self):
        chamfer = ChamferSpec(width_mm=3.0, angle_deg=45.0)
        modified = dataclasses.replace(chamfer, width_mm=6.0)
        assert modified.width_mm == 6.0
        assert modified.angle_deg == 45.0

    def test_equality(self):
        a = ChamferSpec(width_mm=3.0, angle_deg=45.0)
        b = ChamferSpec(width_mm=3.0, angle_deg=45.0)
        assert a == b


class TestShapeGeometry:
    def test_defaults_all_none(self):
        sg = ShapeGeometry()
        assert sg.w_mm is None
        assert sg.h_mm is None
        assert sg.diameter_mm is None
        assert sg.points is None
        assert sg.radius_mm is None
        assert sg.radius_tl_mm is None
        assert sg.radius_tr_mm is None
        assert sg.radius_br_mm is None
        assert sg.radius_bl_mm is None
        assert sg.start is None
        assert sg.end is None

    def test_rect_geometry(self):
        sg = ShapeGeometry(w_mm=100.0, h_mm=50.0)
        assert sg.w_mm == 100.0
        assert sg.h_mm == 50.0
        assert sg.diameter_mm is None

    def test_circle_geometry(self):
        sg = ShapeGeometry(diameter_mm=25.0)
        assert sg.diameter_mm == 25.0
        assert sg.w_mm is None

    def test_polygon_geometry(self):
        pts = ((0.0, 0.0), (10.0, 0.0), (5.0, 8.66))
        sg = ShapeGeometry(points=pts)
        assert sg.points == pts
        assert len(sg.points) == 3

    def test_rounded_rect_uniform(self):
        sg = ShapeGeometry(w_mm=80.0, h_mm=60.0, radius_mm=10.0)
        assert sg.radius_mm == 10.0
        assert sg.radius_tl_mm is None

    def test_rounded_rect_selective(self):
        sg = ShapeGeometry(
            w_mm=80.0,
            h_mm=60.0,
            radius_tl_mm=15.0,
            radius_tr_mm=15.0,
            radius_br_mm=0.0,
            radius_bl_mm=0.0,
        )
        assert sg.radius_tl_mm == 15.0
        assert sg.radius_br_mm == 0.0
        assert sg.radius_mm is None

    def test_line_geometry(self):
        sg = ShapeGeometry(start=(0.0, 0.0), end=(10.0, 5.0))
        assert sg.start == (0.0, 0.0)
        assert sg.end == (10.0, 5.0)

    def test_frozen(self):
        sg = ShapeGeometry(w_mm=50.0)
        with pytest.raises(dataclasses.FrozenInstanceError):
            sg.w_mm = 100.0  # type: ignore[misc]

    def test_replace(self):
        sg = ShapeGeometry(w_mm=50.0, h_mm=30.0)
        modified = dataclasses.replace(sg, h_mm=40.0)
        assert modified.w_mm == 50.0
        assert modified.h_mm == 40.0

    def test_equality(self):
        a = ShapeGeometry(w_mm=100.0, h_mm=50.0)
        b = ShapeGeometry(w_mm=100.0, h_mm=50.0)
        assert a == b

    def test_inequality(self):
        a = ShapeGeometry(w_mm=100.0, h_mm=50.0)
        b = ShapeGeometry(w_mm=100.0, h_mm=60.0)
        assert a != b


class TestRemovalIntentTypedFields:
    def _base_intent(self, **kwargs) -> RemovalIntent:
        defaults = dict(
            region_id="test",
            bounds=Bounds2D(x_min=0, x_max=100, y_min=0, y_max=100),
            depth_profile=DepthProfile.constant(z_top=0, z_bottom=-10),
        )
        defaults.update(kwargs)
        return RemovalIntent(**defaults)

    def test_hint_type_field(self):
        intent = self._base_intent(hint_type="profile")
        assert intent.hint_type == "profile"

    def test_shape_field(self):
        intent = self._base_intent(shape="Rect")
        assert intent.shape == "Rect"

    def test_side_field(self):
        intent = self._base_intent(side="outside")
        assert intent.side == "outside"

    def test_original_id_field(self):
        intent = self._base_intent(original_id="panel_1")
        assert intent.original_id == "panel_1"

    def test_shape_geometry_field(self):
        sg = ShapeGeometry(w_mm=100.0, h_mm=50.0)
        intent = self._base_intent(shape_geometry=sg)
        assert intent.shape_geometry.w_mm == 100.0
        assert intent.shape_geometry.h_mm == 50.0

    def test_corner_cleanup_tool_diameter_field(self):
        intent = self._base_intent(corner_cleanup_tool_diameter_mm=3.175)
        assert intent.corner_cleanup_tool_diameter_mm == 3.175

    def test_bevel_field(self):
        bevel = BevelSpec(width_mm=8.0, angle_deg=45.0, inner_depth_mm=7.0)
        intent = self._base_intent(bevel=bevel)
        assert intent.bevel is not None
        assert intent.bevel.width_mm == 8.0
        assert intent.bevel.angle_deg == 45.0
        assert intent.bevel.inner_depth_mm == 7.0

    def test_chamfer_field(self):
        chamfer = ChamferSpec(width_mm=4.0, angle_deg=45.0)
        intent = self._base_intent(chamfer=chamfer)
        assert intent.chamfer is not None
        assert intent.chamfer.width_mm == 4.0

    def test_item_type_field(self):
        intent = self._base_intent(item_type="Rect")
        assert intent.item_type == "Rect"

    def test_feature_type_field(self):
        intent = self._base_intent(feature_type="profile")
        assert intent.feature_type == "profile"

    def test_shape_id_field(self):
        intent = self._base_intent(shape_id="panel_a")
        assert intent.shape_id == "panel_a"

    def test_defaults(self):
        intent = self._base_intent()
        assert intent.hint_type == ""
        assert intent.shape == ""
        assert intent.side is None
        assert intent.original_id is None
        assert intent.shape_geometry == ShapeGeometry()
        assert intent.corner_cleanup_tool_diameter_mm is None
        assert intent.bevel is None
        assert intent.chamfer is None
        assert intent.item_type is None
        assert intent.feature_type is None
        assert intent.shape_id is None

    def test_frozen(self):
        intent = self._base_intent(hint_type="profile")
        with pytest.raises(dataclasses.FrozenInstanceError):
            intent.hint_type = "pocket"  # type: ignore[misc]

    def test_to_dict_includes_typed_fields(self):
        bevel = BevelSpec(width_mm=8.0, angle_deg=45.0, inner_depth_mm=7.0)
        intent = self._base_intent(
            hint_type="profile",
            shape="Rect",
            side="outside",
            bevel=bevel,
        )
        d = intent.to_dict()
        assert d["hint_type"] == "profile"
        assert d["shape"] == "Rect"
        assert d["side"] == "outside"
        assert d["bevel"]["width_mm"] == 8.0
        assert d["bevel"]["angle_deg"] == 45.0
        assert d["bevel"]["inner_depth_mm"] == 7.0

    def test_to_dict_no_metadata_key(self):
        intent = self._base_intent()
        d = intent.to_dict()
        assert "metadata" not in d
